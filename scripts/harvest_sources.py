"""Harvest open-access running science from APIs and repos into the RAG corpus.

Usage: python scripts/harvest_sources.py

Sources:
- OpenAlex API (millions of OA papers)
- Cloned GitHub repos (knowledge-rich markdown/docs)

Output: knowledge/corpus/harvested_*.md files (chunked, cited)
"""

import json
import os
import sys
import urllib.request
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge", "corpus")
SOURCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge", "sources")


def fetch_openalex(query: str, max_results: int = 50) -> list[dict]:
    """Fetch open-access papers from OpenAlex API."""
    url = f"https://api.openalex.org/works?search={urllib.request.quote(query)}&filter=open_access.is_oa:true&per-page={min(max_results, 200)}&select=title,publication_year,doi,abstract_inverted_index,open_access"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SprintSociety/1.0 (mailto:ishan@sprintsociety.in)"})
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        results = []
        for work in data.get("results", []):
            # Reconstruct abstract from inverted index
            abstract = ""
            aii = work.get("abstract_inverted_index")
            if aii:
                word_positions = []
                for word, positions in aii.items():
                    for pos in positions:
                        word_positions.append((pos, word))
                word_positions.sort()
                abstract = " ".join(w for _, w in word_positions)

            if abstract and len(abstract) > 100:
                results.append({
                    "title": work.get("title", "Untitled"),
                    "year": work.get("publication_year", ""),
                    "doi": work.get("doi", ""),
                    "abstract": abstract,
                })
        return results
    except Exception as e:
        print(f"  Error fetching '{query}': {e}")
        return []


def harvest_openalex():
    """Harvest papers from OpenAlex across all categories."""
    categories = {
        "training_science": [
            "running training periodization",
            "polarized training endurance",
            "threshold training running performance",
            "tapering endurance performance",
            "high intensity interval training runners",
        ],
        "physiology": [
            "VO2max running determinants",
            "running economy biomechanics",
            "lactate threshold endurance",
            "cardiac adaptations endurance training",
            "muscle fiber type running",
        ],
        "injury_prevention": [
            "running injury prevention risk factors",
            "acute chronic workload ratio injury",
            "return to running after injury",
            "stress fracture runners prevention",
            "achilles tendinopathy eccentric loading",
        ],
        "nutrition_recovery": [
            "carbohydrate loading marathon performance",
            "protein recovery endurance athletes",
            "iron deficiency runners",
            "sleep recovery athletic performance",
            "hydration electrolytes endurance",
        ],
        "psychology_motivation": [
            "self-determination theory exercise motivation",
            "habit formation physical activity",
            "mental toughness endurance athletes",
            "exercise adherence behavior change",
            "flow state athletic performance",
        ],
        "environment": [
            "heat acclimation running performance",
            "altitude training endurance athletes",
            "air pollution exercise performance",
        ],
        "special_populations": [
            "masters athletes running performance aging",
            "female athletes menstrual cycle training",
            "RED-S relative energy deficiency sport",
        ],
    }

    all_papers = {}
    for category, queries in categories.items():
        print(f"\n  Category: {category}")
        papers = []
        for query in queries:
            results = fetch_openalex(query, max_results=20)
            papers.extend(results)
            print(f"    '{query}': {len(results)} papers")
            time.sleep(0.5)  # Rate limit respect
        all_papers[category] = papers
        print(f"  Total for {category}: {len(papers)}")

    return all_papers


def write_harvested_corpus(papers_by_category: dict):
    """Write harvested papers into corpus markdown files."""
    for category, papers in papers_by_category.items():
        if not papers:
            continue

        filename = f"research_{category}.md"
        filepath = os.path.join(CORPUS_DIR, filename)

        lines = [f"# Research: {category.replace('_', ' ').title()}\n"]
        lines.append(f"Source: OpenAlex open-access papers. {len(papers)} studies.\n\n")

        seen_titles = set()
        for paper in papers:
            title = paper["title"]
            if title in seen_titles:
                continue
            seen_titles.add(title)

            year = paper.get("year", "")
            doi = paper.get("doi", "")
            abstract = paper["abstract"]

            # Truncate very long abstracts
            if len(abstract) > 600:
                abstract = abstract[:600] + "..."

            lines.append(f"## {title} ({year})\n")
            if doi:
                lines.append(f"DOI: {doi}\n")
            lines.append(f"\n{abstract}\n\n")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"  Written: {filename} ({len(seen_titles)} unique papers)")


def harvest_github_repos():
    """Extract knowledge from cloned repos into corpus."""
    print("\n  Scanning cloned repos for knowledge content...")

    # Look for markdown files in sources
    knowledge_content = []

    for repo_name in os.listdir(SOURCES_DIR):
        repo_path = os.path.join(SOURCES_DIR, repo_name)
        if not os.path.isdir(repo_path):
            continue

        # Find markdown files
        for root, dirs, files in os.walk(repo_path):
            # Skip .git and node_modules
            dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__', '.venv')]
            for f in files:
                if f.endswith('.md') and f.upper() != 'LICENSE.MD':
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                            content = fh.read()
                        if len(content) > 200:  # Skip tiny files
                            knowledge_content.append({
                                "repo": repo_name,
                                "file": f,
                                "content": content[:5000],  # Cap per file
                            })
                    except Exception:
                        pass

    if not knowledge_content:
        print("  No knowledge content found in repos.")
        return

    # Write combined repo knowledge file
    filepath = os.path.join(CORPUS_DIR, "research_github_repos.md")
    lines = ["# Research: GitHub Repository Knowledge\n"]
    lines.append(f"Source: {len(knowledge_content)} files from cloned open-source repos.\n\n")

    for item in knowledge_content[:30]:  # Cap at 30 files
        lines.append(f"## [{item['repo']}] {item['file']}\n\n")
        # Truncate content
        content = item['content'][:2000]
        lines.append(f"{content}\n\n---\n\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  Written: research_github_repos.md ({len(knowledge_content)} sources)")


if __name__ == "__main__":
    print("="*60)
    print("  Sprint Society RAG Harvest")
    print("="*60)

    print("\n[1/2] Harvesting OpenAlex (open-access papers)...")
    papers = harvest_openalex()
    write_harvested_corpus(papers)

    print("\n[2/2] Harvesting GitHub repos...")
    harvest_github_repos()

    # Recount corpus
    corpus_files = [f for f in os.listdir(CORPUS_DIR) if f.endswith('.md')]
    total_lines = sum(
        sum(1 for _ in open(os.path.join(CORPUS_DIR, f), encoding='utf-8'))
        for f in corpus_files
    )
    print(f"\n{'='*60}")
    print(f"  CORPUS NOW: {len(corpus_files)} files, {total_lines} lines")
    print(f"{'='*60}")
