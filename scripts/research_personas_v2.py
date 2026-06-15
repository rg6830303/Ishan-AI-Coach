"""Deep persona research v2 — broader scraping, more sources per figure.

Fixes from v1:
- Accept ALL domains from Google (not just whitelisted)
- Use DuckDuckGo as backup search
- Try multiple Wikipedia variants
- Extract much more content per page (up to 15K chars)
- Target: get as many unique pages as possible per figure
"""

import os
import sys
import io
import time
import re
import urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONAS_DIR = os.path.join(BASE_DIR, "knowledge", "corpus", "personas")

FIGURES = {
    "scientist": [
        "Jack Daniels running coach",
        "Tim Noakes exercise scientist",
        "Steve Magness sports science",
        "Stephen Seiler polarized training",
        "Inigo San Millan Zone 2",
        "Andrew Huberman neuroscience exercise",
        "Phil Maffetone MAF method",
        "Yannis Pitsiladis Sub2 genetics",
        "Trent Stellingwerff sports nutrition",
        "Ross Tucker Science of Sport",
    ],
    "energizer": [
        "Eliud Kipchoge marathon",
        "Patrick Sang coach Kenya",
        "Renato Canova marathon coach",
        "Shalane Flanagan marathon",
        "Des Linden Boston Marathon",
        "Courtney Dauwalter ultra running",
        "Milind Soman running India",
        "Avinash Sable steeplechase India",
        "Haile Gebrselassie distance running",
        "Hima Das Indian sprinter",
    ],
    "warrior": [
        "Percy Cerutty coach Australia",
        "David Goggins ultramarathon mental",
        "Kenenisa Bekele distance runner",
        "Mo Farah Olympic champion",
        "Emil Zatopek Olympic 1952",
        "Lalita Babar steeplechase India",
        "Jock Semple Boston Marathon history",
    ],
    "sage": [
        "Arthur Lydiard running coach",
        "Yuki Kawauchi citizen runner marathon",
        "Kathrine Switzer Boston Marathon woman",
        "Kipchoge Keino Olympic Kenya",
        "Deena Kastor Let Your Mind Run",
        "Haruki Murakami running memoir",
        "Budhia Singh child runner India",
    ],
}


def scrape_url(page, url, max_chars=15000):
    """Scrape one URL, return content."""
    try:
        page.goto(url, timeout=12000, wait_until="domcontentloaded")
        time.sleep(0.5)
        content = page.inner_text("body")
        title = page.title()
        # Clean content
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        return {"url": url, "title": title, "content": content[:max_chars]}
    except Exception:
        return None


def google_search_urls(page, query, num_results=20):
    """Get URLs from Google search."""
    urls = []
    try:
        encoded = urllib.parse.quote_plus(query)
        page.goto(f"https://www.google.com/search?q={encoded}&num=20", timeout=12000)
        time.sleep(1)

        # Get all links
        all_links = page.eval_on_selector_all(
            "a",
            "els => els.map(el => el.href).filter(h => h && h.startsWith('http'))"
        )

        # Filter out Google's own links
        skip = ['google.', 'gstatic.', 'youtube.com/watch', 'accounts.', 'support.google',
                'maps.google', 'translate.google', 'chrome.google', 'play.google']

        for link in all_links:
            if not any(s in link for s in skip):
                if link not in urls:
                    urls.append(link)

    except Exception:
        pass

    return urls[:num_results]


def duckduckgo_search_urls(page, query, num_results=10):
    """Backup: DuckDuckGo search."""
    urls = []
    try:
        encoded = urllib.parse.quote_plus(query)
        page.goto(f"https://duckduckgo.com/html/?q={encoded}", timeout=12000)
        time.sleep(1)

        all_links = page.eval_on_selector_all(
            "a.result__a",
            "els => els.map(el => el.href)"
        )
        urls = [l for l in all_links if l.startswith('http')][:num_results]
    except Exception:
        pass

    return urls


def research_one_figure(page, figure_query, persona):
    """Research one figure — get as many unique sources as possible."""
    name = figure_query.split(" ")[0] + " " + figure_query.split(" ")[1] if len(figure_query.split(" ")) > 1 else figure_query
    all_content = []
    seen_urls = set()

    # Variant searches
    searches = [
        figure_query,
        f"{figure_query} philosophy quotes",
        f"{figure_query} training methodology interview",
        f"{figure_query} coaching approach principles",
        f"{name} biography career achievements",
    ]

    for search_q in searches:
        # Google
        urls = google_search_urls(page, search_q, num_results=10)

        # Fallback to DuckDuckGo if Google gives nothing
        if len(urls) < 3:
            urls += duckduckgo_search_urls(page, search_q, num_results=8)

        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)

            result = scrape_url(page, url)
            if result and result["content"] and len(result["content"]) > 200:
                all_content.append(result)

            if len(all_content) >= 15:  # Cap at 15 sources per figure
                break

            time.sleep(0.3)

        if len(all_content) >= 15:
            break
        time.sleep(1)

    # Always try Wikipedia
    wiki_name = name.replace(" ", "_")
    wiki_variants = [
        f"https://en.wikipedia.org/wiki/{wiki_name}",
        f"https://en.wikipedia.org/wiki/{wiki_name.replace('_', '_(')}coach)",
        f"https://en.wikipedia.org/wiki/{wiki_name}_(runner)",
    ]
    for wurl in wiki_variants:
        if wurl not in seen_urls:
            result = scrape_url(page, wurl)
            if result and "does not have an article" not in result.get("content", ""):
                all_content.append(result)
                break

    return all_content


def save_research(persona, figure_query, content_list):
    """Save all scraped content for a figure."""
    name = figure_query.split(" ")[0] + "_" + figure_query.split(" ")[1] if len(figure_query.split(" ")) > 1 else figure_query
    safe_name = name.lower().replace(" ", "_").replace("'", "")
    filepath = os.path.join(PERSONAS_DIR, persona, f"{safe_name}.md")

    sources_count = len(content_list)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {figure_query} — Deep Research\n\n")
        f.write(f"Persona: {persona.title()}\n")
        f.write(f"Sources found: {sources_count}\n\n")
        f.write("---\n\n")

        for i, item in enumerate(content_list):
            f.write(f"## Source {i+1}: {item['title']}\n")
            f.write(f"URL: {item['url']}\n\n")
            f.write(f"{item['content']}\n\n")
            f.write("---\n\n")

    return filepath, sources_count


def main():
    print("=" * 65)
    print("  DEEP PERSONA RESEARCH v2 — Playwright")
    print("=" * 65)

    total = sum(len(figs) for figs in FIGURES.values())
    print(f"  Figures: {total}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        total_sources = 0
        completed = 0

        for persona, figures in FIGURES.items():
            print(f"\n  [{persona.upper()}]")

            for fig_query in figures:
                print(f"    {fig_query}...", end=" ", flush=True)

                try:
                    content = research_one_figure(page, fig_query, persona)
                    _, count = save_research(persona, fig_query, content)
                    total_sources += count
                    completed += 1
                    print(f"{count} sources")
                except Exception as e:
                    print(f"ERROR: {str(e)[:40]}")
                    completed += 1

                time.sleep(1)

        page.close()
        browser.close()

    # Final stats
    total_files = 0
    total_kb = 0
    for persona in FIGURES.keys():
        pdir = os.path.join(PERSONAS_DIR, persona)
        if os.path.exists(pdir):
            files = [f for f in os.listdir(pdir) if f.endswith('.md')]
            total_files += len(files)
            total_kb += sum(os.path.getsize(os.path.join(pdir, f)) for f in files) / 1024

    print(f"\n{'=' * 65}")
    print(f"  DONE: {completed}/{total} figures")
    print(f"  Total sources scraped: {total_sources}")
    print(f"  Files: {total_files}")
    print(f"  Size: {total_kb:.0f} KB")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
