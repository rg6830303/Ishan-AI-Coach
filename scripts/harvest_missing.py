"""Fix and complete ALL missing harvests.

Fixes:
1. Europe PMC — fix abstract extraction (field is 'abstractText')
2. Semantic Scholar — retry with delays (rate limit)
3. DOAJ — new source, never called
4. Remaining GitHub repos — clone all listed
5. Verify everything wrote correctly
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_DIR = os.path.join(BASE_DIR, "knowledge", "corpus")
SOURCES_DIR = os.path.join(BASE_DIR, "knowledge", "sources")
os.makedirs(CORPUS_DIR, exist_ok=True)
os.makedirs(SOURCES_DIR, exist_ok=True)

HEADERS = {"User-Agent": "SprintSociety-RAG/1.0 (research; ishan@sprintsociety.in)"}


def fetch_url(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return None


def fix_europe_pmc():
    """Re-harvest Europe PMC with correct field parsing."""
    queries = [
        "running economy", "endurance training periodization",
        "running injury prevention", "exercise motivation adherence",
        "heat acclimation athletes", "VO2max training",
        "marathon nutrition fueling", "lactate threshold running",
        "running biomechanics gait", "strength training runners",
        "sleep recovery athletes", "iron deficiency endurance",
        "relative energy deficiency sport", "altitude training performance",
        "heart rate variability exercise", "mental toughness sport",
    ]

    all_papers = []
    print(f"  Queries: {len(queries)}")

    for query in queries:
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={urllib.request.quote(query)}%20AND%20OPEN_ACCESS:Y&format=json&pageSize=100&resultType=core"
        data = fetch_url(url, timeout=30)
        if not data:
            print(f"    FAIL: {query}")
            continue
        try:
            parsed = json.loads(data)
            results = parsed.get("resultList", {}).get("result", [])
            count = 0
            for r in results:
                # Europe PMC uses 'abstractText' field
                abstract = r.get("abstractText", "") or r.get("abstract", "") or ""
                title = r.get("title", "")
                if abstract and len(abstract) > 100 and title:
                    all_papers.append({
                        "title": title,
                        "year": r.get("pubYear", ""),
                        "doi": r.get("doi", ""),
                        "abstract": abstract[:800],
                    })
                    count += 1
            print(f"    '{query}': {count} papers with abstracts (of {len(results)} results)")
        except Exception as e:
            print(f"    ERROR {query}: {e}")
        time.sleep(0.5)

    # Deduplicate
    seen = set()
    unique = []
    for p in all_papers:
        key = (p.get("title") or "").lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(p)

    filepath = os.path.join(CORPUS_DIR, "research_europe_pmc.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Research: Europe PMC Open-Access Collection\n\n")
        f.write(f"Source: Europe PMC REST API. {len(unique)} peer-reviewed studies with abstracts.\n\n")
        for p in unique:
            f.write(f"## {p['title']} ({p['year']})\n")
            if p['doi']:
                f.write(f"DOI: {p['doi']}\n")
            f.write(f"\n{p['abstract']}\n\n")

    print(f"  WRITTEN: research_europe_pmc.md ({len(unique)} papers)")
    return len(unique)


def fix_semantic_scholar():
    """Re-harvest Semantic Scholar with proper rate limiting."""
    queries = [
        "running economy determinants",
        "endurance training periodization",
        "running injury prevention biomechanics",
        "exercise motivation self-determination",
        "altitude training endurance athletes",
        "marathon pacing strategy",
        "VO2max improvement training",
        "lactate threshold running performance",
        "heat acclimation endurance",
        "strength training distance runners",
        "sleep athletic recovery performance",
        "running cadence injury",
    ]

    all_papers = []
    print(f"  Queries: {len(queries)}")

    for query in queries:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.request.quote(query)}&fields=title,year,abstract&limit=100"
        data = fetch_url(url, timeout=20)
        if not data:
            print(f"    FAIL: {query}")
            time.sleep(3)  # Back off on failure
            continue
        try:
            results = json.loads(data).get("data", [])
            count = 0
            for r in results:
                abstract = r.get("abstract", "")
                title = r.get("title", "")
                if abstract and len(abstract) > 100 and title:
                    all_papers.append({
                        "title": title,
                        "year": r.get("year", ""),
                        "abstract": abstract[:800],
                    })
                    count += 1
            print(f"    '{query}': {count} papers")
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(3)  # Semantic Scholar needs 3s between calls

    seen = set()
    unique = []
    for p in all_papers:
        key = (p.get("title") or "").lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(p)

    filepath = os.path.join(CORPUS_DIR, "research_semantic_scholar.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Research: Semantic Scholar Collection\n\n")
        f.write(f"Source: Semantic Scholar API. {len(unique)} studies.\n\n")
        for p in unique:
            f.write(f"## {p['title']} ({p['year']})\n\n{p['abstract']}\n\n")

    print(f"  WRITTEN: research_semantic_scholar.md ({len(unique)} papers)")
    return len(unique)


def harvest_doaj():
    """Harvest from Directory of Open Access Journals."""
    queries = [
        "running training",
        "exercise physiology",
        "sports nutrition endurance",
        "motor learning skill",
        "running injury prevention",
        "marathon performance",
        "heart rate variability athletes",
        "strength training runners",
    ]

    all_papers = []
    print(f"  Queries: {len(queries)}")

    for query in queries:
        url = f"https://doaj.org/api/search/articles/{urllib.request.quote(query)}?pageSize=100"
        data = fetch_url(url, timeout=30)
        if not data:
            print(f"    FAIL: {query}")
            continue
        try:
            results = json.loads(data).get("results", [])
            count = 0
            for r in results:
                bibjson = r.get("bibjson", {})
                title = bibjson.get("title", "")
                abstract = bibjson.get("abstract", "")
                year = bibjson.get("year", "")
                if not year:
                    year = r.get("created_date", "")[:4]
                doi_obj = bibjson.get("identifier", [])
                doi = ""
                for ident in doi_obj:
                    if ident.get("type") == "doi":
                        doi = ident.get("id", "")
                        break

                if abstract and len(abstract) > 100 and title:
                    all_papers.append({
                        "title": title,
                        "year": year,
                        "doi": doi,
                        "abstract": abstract[:800],
                    })
                    count += 1
            print(f"    '{query}': {count} papers with abstracts (of {len(results)} results)")
        except Exception as e:
            print(f"    ERROR {query}: {e}")
        time.sleep(1)

    seen = set()
    unique = []
    for p in all_papers:
        key = (p.get("title") or "").lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(p)

    filepath = os.path.join(CORPUS_DIR, "research_doaj.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Research: DOAJ (Directory of Open Access Journals)\n\n")
        f.write(f"Source: DOAJ API. {len(unique)} open-access journal articles.\n\n")
        for p in unique:
            f.write(f"## {p['title']} ({p['year']})\n")
            if p['doi']:
                f.write(f"DOI: {p['doi']}\n")
            f.write(f"\n{p['abstract']}\n\n")

    print(f"  WRITTEN: research_doaj.md ({len(unique)} papers)")
    return len(unique)


def clone_remaining_repos():
    """Clone ALL remaining repos from both source files."""
    repos = [
        # From source file 1 — not yet cloned
        "EmmanuelDav/Smart-Run",
        "v-pramod/RunningCoach",
        "GermanAlonzo/RunningCoachingApp",
        "raptors2019-ai/running-coach",
        "RonRan123/running-app",
        "EmmanuelDiaz95/trail-running-coach",
        "mdmedley/cadence-coach",
        "ZacBlanco/vdot",
        "tlgs/vdot",
        "oliverbeal/Running-Calculator",
        "johnjdavisiv/gap-app",
        "thehivemakes/hive-run-calc",
        "markwk/qs_ledger",
        "mattambrogi/strava-data-analysis",
        "newns92/MarathonTrainingAnalysis",
        "aaronzpearson/PhysAndSportSciData",
        # From source file 2 — not yet cloned
        "jeff3388/awesome-injury-prevention-science",
        "danielgtr/running_analysis",
        "Mohamedreda333-crypto/FitAI-Pro-Multi-Agent-AI-Fitness-Coaching-Platform",
        "saisrujanseelam/AI-multi-agentic-consensus-fitness-trainer-",
        "CHANDRA294/multi-agent-gym-buddy",
        "LI-explorer/LLM-Fitness-Coach",
        "Coding-Phantom/FitnessForge",
        "oscartiz/hermes-agent",
        "Ahmosys/garmin-metrics-api",
        "COLINZH26/garmin-ai-skill",
        "hoovercj/time-to-run",
        "supermitch/runblueprint.com",
        "furgerf/TrainingPlanner",
        "SKOHscripts/workout-planner",
        "selesse/marathon-trainer",
    ]

    print(f"  Repos to clone: {len(repos)}")
    cloned = 0
    failed = 0

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
            print(f"    FAIL: {repo_name} ({result.strip()[:60]})")
            failed += 1

        time.sleep(0.3)

    # Re-extract all markdown from ALL sources
    print(f"\n  Extracting markdown from all repos...")
    all_content = []

    for repo_name in sorted(os.listdir(SOURCES_DIR)):
        repo_path = os.path.join(SOURCES_DIR, repo_name)
        if not os.path.isdir(repo_path):
            continue
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__', '.venv', 'dist', 'build', 'vendor', '.next')]
            for f in files:
                if f.endswith(('.md', '.rst')) and f.upper() not in ('LICENSE.MD', 'LICENSE.TXT', 'CHANGELOG.MD', 'CODE_OF_CONDUCT.MD', 'CONTRIBUTING.MD'):
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                            content = fh.read()
                        if len(content) > 300:
                            all_content.append({
                                "repo": repo_name,
                                "file": f,
                                "content": content[:4000],
                            })
                    except Exception:
                        pass

    # Write expanded github corpus
    filepath = os.path.join(CORPUS_DIR, "research_github_repos.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Research: GitHub Open-Source Knowledge\n\n")
        f.write(f"Source: {cloned + failed} repos attempted, {len(all_content)} knowledge files extracted.\n\n")
        for item in all_content[:150]:  # Cap at 150 files
            f.write(f"## [{item['repo']}] {item['file']}\n\n")
            f.write(f"{item['content']}\n\n---\n\n")

    print(f"  WRITTEN: research_github_repos.md ({min(len(all_content), 150)} sources from {cloned} repos)")
    return cloned


def verify_corpus():
    """Final verification — check every file has content."""
    print("\n  VERIFICATION:")
    corpus_files = sorted([f for f in os.listdir(CORPUS_DIR) if f.endswith('.md')])
    total_lines = 0
    total_kb = 0
    empty = []

    for f in corpus_files:
        path = os.path.join(CORPUS_DIR, f)
        lines = sum(1 for _ in open(path, encoding='utf-8'))
        kb = os.path.getsize(path) / 1024
        total_lines += lines
        total_kb += kb
        if lines < 5:
            empty.append(f)

    print(f"    Files: {len(corpus_files)}")
    print(f"    Lines: {total_lines:,}")
    print(f"    Size: {total_kb:.0f} KB ({total_kb/1024:.1f} MB)")
    if empty:
        print(f"    EMPTY/BROKEN files: {empty}")
    else:
        print(f"    All files have content: YES")

    return len(corpus_files), total_lines


if __name__ == "__main__":
    print("=" * 60)
    print("  FIXING INCOMPLETE HARVESTS")
    print("=" * 60)

    total_new = 0

    print("\n[1/4] Europe PMC (RE-HARVEST with correct parsing)...")
    total_new += fix_europe_pmc()

    print("\n[2/4] Semantic Scholar (RE-HARVEST with rate limiting)...")
    total_new += fix_semantic_scholar()

    print("\n[3/4] DOAJ (NEW — never harvested before)...")
    total_new += harvest_doaj()

    print("\n[4/4] Remaining GitHub repos (clone ALL listed)...")
    clone_remaining_repos()

    print("\n" + "=" * 60)
    files, lines = verify_corpus()
    print(f"\n  NEW papers added this run: {total_new}")
    print(f"  FINAL CORPUS: {files} files | {lines:,} lines")
    print("=" * 60)
