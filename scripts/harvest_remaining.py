"""Harvest remaining APIs: CORE, SportRxiv, arXiv, ERIC."""

import json
import os
import sys
import io
import re
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_DIR = os.path.join(BASE_DIR, "knowledge", "corpus")
HEADERS = {"User-Agent": "SprintSociety-RAG/1.0 (research; ishan@sprintsociety.in)"}


def fetch(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return None


# ============================================================
# 1. CORE.ac.uk
# ============================================================
def harvest_core():
    print("[1/4] CORE.ac.uk...")
    queries = [
        "running training physiology", "motor skill learning",
        "endurance performance VO2max", "running injury biomechanics",
        "exercise motivation habit", "marathon nutrition fueling",
        "altitude training athletes", "sleep recovery exercise",
    ]
    papers = []
    for q in queries:
        url = f"https://api.core.ac.uk/v3/search/works?q={urllib.request.quote(q)}&limit=100"
        data = fetch(url, timeout=30)
        if not data:
            print(f"  FAIL: {q}")
            continue
        try:
            results = json.loads(data).get("results", [])
            count = 0
            for r in results:
                abstract = r.get("abstract", "") or ""
                title = r.get("title", "") or ""
                year = str(r.get("yearPublished", ""))
                if abstract and len(abstract) > 100 and title:
                    papers.append({"title": title, "year": year, "abstract": abstract[:800]})
                    count += 1
            print(f"  {q}: {count} papers")
        except Exception as e:
            print(f"  ERROR {q}: {e}")
        time.sleep(1)

    seen = set()
    unique = []
    for p in papers:
        key = (p.get("title") or "").lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(p)

    if unique:
        path = os.path.join(CORPUS_DIR, "research_core.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Research: CORE Open-Access Repository\n\nSource: CORE.ac.uk. {len(unique)} papers.\n\n")
            for p in unique:
                f.write(f"## {p['title']} ({p['year']})\n\n{p['abstract']}\n\n")
        print(f"  WRITTEN: research_core.md ({len(unique)} papers)")
    else:
        print("  SKIPPED: No papers retrieved")
    return len(unique)


# ============================================================
# 2. arXiv
# ============================================================
def harvest_arxiv():
    print("\n[2/4] arXiv...")
    queries = [
        "motor+learning", "exercise+physiology+performance",
        "gait+analysis+running", "reinforcement+learning+sport",
        "wearable+sensors+running", "biomechanics+locomotion",
    ]
    papers = []
    for q in queries:
        url = f"http://export.arxiv.org/api/query?search_query=all:{q}&max_results=50"
        data = fetch(url, timeout=20)
        if not data:
            print(f"  FAIL: {q}")
            continue
        entries = re.findall(r"<entry>(.*?)</entry>", data, re.DOTALL)
        count = 0
        for entry in entries:
            title_m = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            summary_m = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            if title_m and summary_m:
                title = title_m.group(1).strip().replace("\n", " ")
                abstract = summary_m.group(1).strip().replace("\n", " ")
                if len(abstract) > 100:
                    papers.append({"title": title, "abstract": abstract[:800]})
                    count += 1
        print(f"  {q}: {count} papers")
        time.sleep(3)  # arXiv rate limit

    seen = set()
    unique = []
    for p in papers:
        key = (p.get("title") or "").lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(p)

    if unique:
        path = os.path.join(CORPUS_DIR, "research_arxiv.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Research: arXiv (Motor Learning, Biomechanics, Wearables)\n\nSource: arXiv.org. {len(unique)} papers.\n\n")
            for p in unique:
                f.write(f"## {p['title']}\n\n{p['abstract']}\n\n")
        print(f"  WRITTEN: research_arxiv.md ({len(unique)} papers)")
    else:
        print("  SKIPPED: No papers")
    return len(unique)


# ============================================================
# 3. ERIC
# ============================================================
def harvest_eric():
    print("\n[3/4] ERIC...")
    queries = [
        "motor+skill+acquisition", "goal+setting+learning",
        "physical+education+motivation", "exercise+habit+formation",
        "feedback+motor+learning", "self-determination+physical+activity",
    ]
    papers = []
    for q in queries:
        url = f"https://api.ies.ed.gov/eric/?search={q}&format=json&rows=50"
        data = fetch(url, timeout=20)
        if not data:
            print(f"  FAIL: {q}")
            continue
        try:
            results = json.loads(data).get("response", {}).get("docs", [])
            count = 0
            for r in results:
                title = r.get("title", "")
                abstract = r.get("description", "") or ""
                year = r.get("publicationdateyear", "")
                if abstract and len(abstract) > 100 and title:
                    papers.append({"title": title, "year": str(year), "abstract": abstract[:800]})
                    count += 1
            print(f"  {q}: {count} papers")
        except Exception as e:
            print(f"  ERROR {q}: {e}")
        time.sleep(0.5)

    seen = set()
    unique = []
    for p in papers:
        key = (p.get("title") or "").lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(p)

    if unique:
        path = os.path.join(CORPUS_DIR, "research_eric.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Research: ERIC (Education, Motor Learning, Behavior)\n\nSource: ERIC/IES. {len(unique)} papers.\n\n")
            for p in unique:
                f.write(f"## {p['title']} ({p['year']})\n\n{p['abstract']}\n\n")
        print(f"  WRITTEN: research_eric.md ({len(unique)} papers)")
    else:
        print("  SKIPPED: No papers")
    return len(unique)


# ============================================================
# 4. SportRxiv (try OAI-PMH)
# ============================================================
def harvest_sportrxiv():
    print("\n[4/4] SportRxiv...")
    # Try the search page as HTML
    url = "https://sportrxiv.org/index.php/server/preprints"
    data = fetch(url, timeout=20)
    if not data:
        # Try OSF-based SportRxiv
        url2 = "https://osf.io/preprints/sportrxiv/?q=running&page=1"
        data = fetch(url2, timeout=20)

    if data and len(data) > 500:
        # Extract what we can
        titles = re.findall(r"<h[234][^>]*>(.*?)</h[234]>", data)
        print(f"  Found {len(titles)} title-like elements")
        if titles:
            path = os.path.join(CORPUS_DIR, "research_sportrxiv.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Research: SportRxiv Preprints\n\nSource: SportRxiv. Titles only (abstracts require individual page fetch).\n\n")
                for t in titles[:50]:
                    clean = re.sub(r"<[^>]+>", "", t).strip()
                    if clean and len(clean) > 10:
                        f.write(f"## {clean}\n\n")
            print(f"  WRITTEN: research_sportrxiv.md ({min(len(titles), 50)} entries)")
            return len(titles)

    print("  FAIL: SportRxiv not accessible or no structured API")
    return 0


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  HARVESTING REMAINING APIS")
    print("=" * 60)

    total = 0
    total += harvest_core()
    total += harvest_arxiv()
    total += harvest_eric()
    total += harvest_sportrxiv()

    # Final count
    corpus_files = [f for f in os.listdir(CORPUS_DIR) if f.endswith(".md")]
    total_lines = sum(sum(1 for _ in open(os.path.join(CORPUS_DIR, f), encoding="utf-8")) for f in corpus_files)
    total_mb = sum(os.path.getsize(os.path.join(CORPUS_DIR, f)) for f in corpus_files) / 1024 / 1024

    print(f"\n{'='*60}")
    print(f"  NEW papers this run: {total}")
    print(f"  FINAL CORPUS: {len(corpus_files)} files | {total_lines:,} lines | {total_mb:.1f} MB")
    print(f"{'='*60}")
