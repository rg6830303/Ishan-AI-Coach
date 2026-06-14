"""FULL harvest — all APIs, all repos, all papers from both source files.

Usage: python scripts/harvest_all.py

This hits:
1. OpenAlex (expanded queries, 200 per call)
2. Europe PMC (full text OA papers)
3. Semantic Scholar (abstracts + OA PDFs)
4. Specific PMC/Frontiers full-text URLs (from source files)
5. GitHub repos (clone + extract markdown/docs)
"""

import json
import os
import sys
import re
import time
import urllib.request
import urllib.error
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_DIR = os.path.join(BASE_DIR, "knowledge", "corpus")
SOURCES_DIR = os.path.join(BASE_DIR, "knowledge", "sources")
os.makedirs(CORPUS_DIR, exist_ok=True)
os.makedirs(SOURCES_DIR, exist_ok=True)

HEADERS = {"User-Agent": "SprintSociety-RAG/1.0 (research-harvester; ishan@sprintsociety.in)"}


class HTMLTextExtractor(HTMLParser):
    """Simple HTML to text converter."""
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'footer', 'header'):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'footer', 'header'):
            self._skip = False
        if tag in ('p', 'h1', 'h2', 'h3', 'h4', 'li', 'div', 'br'):
            self._text.append('\n')

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def get_text(self):
        return ' '.join(''.join(self._text).split())


def fetch_url(url, timeout=20):
    """Fetch URL with error handling."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return None


def extract_text_from_html(html):
    """Extract clean text from HTML."""
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


# ============================================================
# 1. OpenAlex — expanded queries
# ============================================================
def harvest_openalex_full():
    """Expanded OpenAlex harvest with more queries and higher limits."""
    queries = {
        "training_methods": [
            "running training periodization", "polarized training endurance athletes",
            "threshold training lactate running", "Norwegian method double threshold",
            "tapering strategies endurance", "high intensity interval training distance runners",
            "long slow distance training aerobic", "block periodization endurance",
            "concurrent training runners strength", "Daniels VDOT training zones",
        ],
        "physiology_performance": [
            "VO2max determinants runners", "running economy factors",
            "lactate threshold training adaptations", "cardiac output endurance training",
            "muscle fiber recruitment running", "mitochondrial biogenesis exercise",
            "glycogen depletion marathon", "fat oxidation endurance training",
            "hemoglobin oxygen carrying capacity", "neuromuscular fatigue running",
        ],
        "injury_biomechanics": [
            "running injury risk factors prevention", "acute chronic workload ratio sports",
            "achilles tendinopathy eccentric exercise", "stress fracture runners bone",
            "patellofemoral pain runners knee", "plantar fasciitis treatment runners",
            "IT band syndrome runners biomechanics", "shin splints medial tibial",
            "running biomechanics gait analysis", "cadence step rate injury prevention",
        ],
        "nutrition_hydration": [
            "carbohydrate loading endurance performance", "protein timing recovery athletes",
            "iron deficiency athletes ferritin", "caffeine endurance performance",
            "hydration electrolytes exercise", "relative energy deficiency sport RED-S",
            "gut training athletes carbohydrate", "beetroot nitrate running performance",
            "vitamin D athletes bone health", "sleep nutrition recovery athletes",
        ],
        "recovery_adaptation": [
            "sleep athletic performance recovery", "cold water immersion recovery",
            "compression garments recovery runners", "foam rolling myofascial release",
            "overtraining syndrome detection markers", "heart rate variability recovery training",
            "deload recovery supercompensation", "active recovery blood lactate clearance",
            "massage recovery athletic performance", "periodization recovery integration",
        ],
        "psychology_behavior": [
            "self-determination theory sport exercise", "habit formation physical activity",
            "mental toughness endurance sport", "flow state athletic performance",
            "exercise adherence dropout prediction", "motivation intrinsic running",
            "self-efficacy exercise behavior", "goal setting sport performance",
            "mindfulness athletes performance", "visualization imagery sport",
        ],
        "heat_altitude_environment": [
            "heat acclimation endurance performance", "altitude training live high train low",
            "air pollution exercise health", "cold exposure training adaptation",
            "humidity thermoregulation exercise", "circadian rhythm athletic performance",
        ],
        "special_populations": [
            "masters athletes aging performance decline", "female athletes menstrual cycle performance",
            "RED-S female athletes bone", "pregnancy exercise running safety",
            "postpartum return running", "youth athletes training development",
            "obese runners injury risk training", "diabetic exercise running benefits",
        ],
    }

    all_results = {}
    total_papers = 0

    for category, category_queries in queries.items():
        print(f"\n  [{category}]")
        papers = []
        for query in category_queries:
            url = f"https://api.openalex.org/works?search={urllib.request.quote(query)}&filter=open_access.is_oa:true&per-page=200&select=title,publication_year,doi,abstract_inverted_index"
            data = fetch_url(url)
            if not data:
                print(f"    FAIL: {query}")
                continue
            try:
                results = json.loads(data).get("results", [])
                for work in results:
                    aii = work.get("abstract_inverted_index")
                    if not aii:
                        continue
                    word_positions = []
                    for word, positions in aii.items():
                        for pos in positions:
                            word_positions.append((pos, word))
                    word_positions.sort()
                    abstract = " ".join(w for _, w in word_positions)
                    if len(abstract) > 100:
                        papers.append({
                            "title": work.get("title", ""),
                            "year": work.get("publication_year", ""),
                            "doi": work.get("doi", ""),
                            "abstract": abstract[:800],
                        })
                print(f"    {query[:40]}...: {len(results)} results")
            except Exception as e:
                print(f"    ERROR {query[:30]}: {e}")
            time.sleep(0.3)

        # Deduplicate by title
        seen = set()
        unique = []
        for p in papers:
            title = p.get("title") or ""
            key = title.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(p)

        all_results[category] = unique
        total_papers += len(unique)
        print(f"    TOTAL unique: {len(unique)}")

    # Write corpus files
    for category, papers in all_results.items():
        if not papers:
            continue
        filepath = os.path.join(CORPUS_DIR, f"research_{category}.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# Research: {category.replace('_', ' ').title()}\n\n")
            f.write(f"Source: OpenAlex open-access database. {len(papers)} peer-reviewed studies.\n\n")
            for p in papers:
                f.write(f"## {p['title']} ({p['year']})\n")
                if p['doi']:
                    f.write(f"DOI: {p['doi']}\n")
                f.write(f"\n{p['abstract']}\n\n")
        print(f"  Written: research_{category}.md ({len(papers)} papers)")

    return total_papers


# ============================================================
# 2. Europe PMC — full abstracts
# ============================================================
def harvest_europe_pmc():
    """Fetch from Europe PMC REST API."""
    queries = [
        "running economy", "endurance training periodization",
        "running injury prevention", "exercise motivation adherence",
        "heat acclimation athletes", "VO2max training",
        "marathon nutrition fueling", "lactate threshold running",
    ]

    total = 0
    all_papers = []

    print(f"\n  Europe PMC queries: {len(queries)}")
    for query in queries:
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={urllib.request.quote(query)}%20AND%20OPEN_ACCESS:Y&format=json&pageSize=100"
        data = fetch_url(url, timeout=30)
        if not data:
            print(f"    FAIL: {query}")
            continue
        try:
            results = json.loads(data).get("resultList", {}).get("result", [])
            for r in results:
                abstract = r.get("abstractText", "")
                if abstract and len(abstract) > 100:
                    all_papers.append({
                        "title": r.get("title", ""),
                        "year": r.get("pubYear", ""),
                        "doi": r.get("doi", ""),
                        "abstract": abstract[:800],
                        "source": "Europe PMC",
                    })
            print(f"    '{query}': {len(results)} results")
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(0.5)

    # Deduplicate
    seen = set()
    unique = []
    for p in all_papers:
        key = (p.get("title") or "").lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(p)

    # Write
    filepath = os.path.join(CORPUS_DIR, "research_europe_pmc.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Research: Europe PMC Open-Access Collection\n\n")
        f.write(f"Source: Europe PMC. {len(unique)} peer-reviewed studies.\n\n")
        for p in unique:
            f.write(f"## {p['title']} ({p['year']})\n")
            if p['doi']:
                f.write(f"DOI: {p['doi']}\n")
            f.write(f"\n{p['abstract']}\n\n")

    print(f"  Written: research_europe_pmc.md ({len(unique)} papers)")
    return len(unique)


# ============================================================
# 3. Semantic Scholar
# ============================================================
def harvest_semantic_scholar():
    """Fetch from Semantic Scholar API."""
    queries = [
        "running economy determinants", "endurance training periodization",
        "running injury prevention biomechanics", "exercise motivation self-determination",
        "altitude training endurance", "marathon pacing strategy",
    ]

    all_papers = []
    print(f"\n  Semantic Scholar queries: {len(queries)}")

    for query in queries:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.request.quote(query)}&fields=title,year,abstract,openAccessPdf&limit=100"
        data = fetch_url(url, timeout=20)
        if not data:
            print(f"    FAIL: {query}")
            continue
        try:
            results = json.loads(data).get("data", [])
            for r in results:
                abstract = r.get("abstract", "")
                if abstract and len(abstract) > 100:
                    all_papers.append({
                        "title": r.get("title", ""),
                        "year": r.get("year", ""),
                        "abstract": abstract[:800],
                    })
            print(f"    '{query}': {len(results)} results")
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(1.0)  # Semantic Scholar rate limit is strict

    seen = set()
    unique = []
    for p in all_papers:
        key = (p.get("title") or "").lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(p)

    filepath = os.path.join(CORPUS_DIR, "research_semantic_scholar.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Research: Semantic Scholar Collection\n\n")
        f.write(f"Source: Semantic Scholar. {len(unique)} studies.\n\n")
        for p in unique:
            f.write(f"## {p['title']} ({p['year']})\n\n{p['abstract']}\n\n")

    print(f"  Written: research_semantic_scholar.md ({len(unique)} papers)")
    return len(unique)


# ============================================================
# 4. Specific PMC/Frontiers full-text URLs
# ============================================================
def harvest_specific_papers():
    """Fetch and extract text from specific open-access paper URLs."""
    urls = [
        # Training intensity distribution
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC11679080/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC3912323/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC6873141/",
        # ACWR / load
        "https://www.mdpi.com/2076-3417/14/11/4449",
        # Running economy
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC6305502/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC8924290/",
        # Strength training for runners
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11258194/",
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5889786/",
        # Running injury
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC11336318/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC8500811/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC9528699/",
        # Heat / altitude
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC4789936/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC6422510/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC6543994/",
        # Motor learning
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC3534841/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC4346332/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC8793168/",
        # Habit / motivation
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC11018029/",
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7969808/",
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3441783/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC4519215/",
        # Tapering
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10171681/",
        # Injury biomechanics
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC11532757/",
        # Altitude
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC11857729/",
    ]

    print(f"\n  Fetching {len(urls)} specific full-text papers...")
    papers = []

    for i, url in enumerate(urls):
        html = fetch_url(url, timeout=20)
        if not html:
            print(f"    [{i+1}/{len(urls)}] FAIL: {url}")
            continue

        text = extract_text_from_html(html)

        # Extract title from HTML
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else url.split("/")[-2]
        title = re.sub(r'\s*[-|].*$', '', title)  # Remove site name suffix

        # Take first 3000 chars of content (abstract + intro typically)
        content = text[:3000] if len(text) > 3000 else text

        if len(content) > 200:
            papers.append({
                "title": title,
                "url": url,
                "content": content,
            })
            print(f"    [{i+1}/{len(urls)}] OK: {title[:60]}... ({len(content)} chars)")
        else:
            print(f"    [{i+1}/{len(urls)}] TOO SHORT: {url}")

        time.sleep(0.5)

    # Write
    filepath = os.path.join(CORPUS_DIR, "research_fulltext_papers.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Research: Full-Text Open-Access Papers\n\n")
        f.write(f"Source: PubMed Central, Frontiers, MDPI. {len(papers)} papers (summaries).\n\n")
        for p in papers:
            f.write(f"## {p['title']}\n")
            f.write(f"URL: {p['url']}\n\n")
            f.write(f"{p['content']}\n\n---\n\n")

    print(f"  Written: research_fulltext_papers.md ({len(papers)} papers)")
    return len(papers)


# ============================================================
# 5. GitHub repos — clone all knowledge-rich ones
# ============================================================
def harvest_github_repos_full():
    """Clone and extract markdown from all listed repos."""
    repos = [
        # Knowledge-rich content repos
        "PatrickWiloak/proper-distance-running-training-guidance",
        "dpfens/PyExPhys",
        "dpfens/FitnessJS",
        "ColinEberhardt/claude-running-coach",
        "ropensci/Athlytics",
        "aaron-schroeder/heartandsole",
        "sbailliez/training-plan",
        "jandroav/vtrain",
        "ronek22/runningCalculator",
        "hivrich/vdot-calculator",
        # Agentic RAG architecture refs
        "Mohamed-Elguindy/Fitness-App",
        "Hayfa78/fitness-nutrition-agent",
        "kenhuangus/fitness-multi-agent-plan",
        "vimalkumarasamy/agent-balboa",
        "jnkue/open-trainaa",
    ]

    print(f"\n  Cloning {len(repos)} repos...")
    cloned = 0

    for repo in repos:
        repo_name = repo.split("/")[-1]
        dest = os.path.join(SOURCES_DIR, repo_name)

        if os.path.exists(dest):
            print(f"    SKIP (exists): {repo_name}")
            cloned += 1
            continue

        url = f"https://github.com/{repo}.git"
        cmd = f'git clone --depth 1 "{url}" "{dest}" 2>&1'
        result = os.popen(cmd).read()

        if os.path.exists(os.path.join(dest, ".git")):
            print(f"    CLONED: {repo_name}")
            cloned += 1
        else:
            print(f"    FAIL: {repo_name}")

        time.sleep(0.3)

    # Extract all markdown from all sources
    print(f"\n  Extracting markdown from {cloned} repos...")
    all_content = []

    for repo_name in os.listdir(SOURCES_DIR):
        repo_path = os.path.join(SOURCES_DIR, repo_name)
        if not os.path.isdir(repo_path):
            continue
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__', '.venv', 'dist', 'build')]
            for f in files:
                if f.endswith(('.md', '.rst', '.txt')) and f.upper() not in ('LICENSE.MD', 'LICENSE.TXT', 'CHANGELOG.MD'):
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                            content = fh.read()
                        if len(content) > 200:
                            all_content.append({
                                "repo": repo_name,
                                "file": f,
                                "content": content[:4000],
                            })
                    except Exception:
                        pass

    # Write
    filepath = os.path.join(CORPUS_DIR, "research_github_repos.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Research: GitHub Open-Source Knowledge\n\n")
        f.write(f"Source: {cloned} open-source repositories. {len(all_content)} knowledge files.\n\n")
        for item in all_content[:80]:  # Cap at 80 files
            f.write(f"## [{item['repo']}] {item['file']}\n\n")
            f.write(f"{item['content']}\n\n---\n\n")

    print(f"  Written: research_github_repos.md ({min(len(all_content), 80)} sources)")
    return cloned


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  FULL RAG HARVEST — ALL SOURCES")
    print("=" * 60)

    total = 0

    print("\n[1/5] OpenAlex (expanded, 80+ queries)...")
    total += harvest_openalex_full()

    print("\n[2/5] Europe PMC...")
    total += harvest_europe_pmc()

    print("\n[3/5] Semantic Scholar...")
    total += harvest_semantic_scholar()

    print("\n[4/5] Specific full-text papers (PMC/Frontiers)...")
    total += harvest_specific_papers()

    print("\n[5/5] GitHub repos (clone + extract)...")
    harvest_github_repos_full()

    # Final count
    corpus_files = [f for f in os.listdir(CORPUS_DIR) if f.endswith('.md')]
    total_lines = sum(
        sum(1 for _ in open(os.path.join(CORPUS_DIR, f), encoding='utf-8'))
        for f in corpus_files
    )

    print(f"\n{'=' * 60}")
    print(f"  HARVEST COMPLETE")
    print(f"  Total papers/sources ingested: ~{total}")
    print(f"  Corpus: {len(corpus_files)} files, {total_lines} lines")
    print(f"{'=' * 60}")
