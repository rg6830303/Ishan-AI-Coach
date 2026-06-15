"""Deep persona research — 50 sources per figure using Playwright.

Scrapes Wikipedia, coaching sites, interviews, articles for each of the 34 figures.
Extracts: philosophy, quotes, methods, iconic moments, coaching decisions.
Saves unique findings per person into persona subfolders.
"""

import os
import sys
import io
import json
import time
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONAS_DIR = os.path.join(BASE_DIR, "knowledge", "corpus", "personas")
os.makedirs(os.path.join(PERSONAS_DIR, "scientist"), exist_ok=True)
os.makedirs(os.path.join(PERSONAS_DIR, "energizer"), exist_ok=True)
os.makedirs(os.path.join(PERSONAS_DIR, "warrior"), exist_ok=True)
os.makedirs(os.path.join(PERSONAS_DIR, "sage"), exist_ok=True)


# All figures with their search queries
FIGURES = {
    "scientist": [
        {"name": "Jack Daniels", "search_terms": ["Jack Daniels running coach VDOT", "Jack Daniels training philosophy", "Jack Daniels Running Formula principles", "Jack Daniels interval training methodology", "Jack Daniels easy pace importance"]},
        {"name": "Tim Noakes", "search_terms": ["Tim Noakes Lore of Running", "Tim Noakes central governor theory", "Tim Noakes hydration science", "Tim Noakes exercise physiology", "Tim Noakes running advice"]},
        {"name": "Steve Magness", "search_terms": ["Steve Magness Science of Running", "Steve Magness coaching philosophy", "Steve Magness Do Hard Things", "Steve Magness toughness", "Steve Magness training stress"]},
        {"name": "Stephen Seiler", "search_terms": ["Stephen Seiler polarized training", "Stephen Seiler 80/20 training", "Stephen Seiler training intensity distribution", "Stephen Seiler endurance research", "Stephen Seiler lactate threshold"]},
        {"name": "Inigo San Millan", "search_terms": ["Inigo San Millan Zone 2 training", "Inigo San Millan Pogacar", "Inigo San Millan mitochondria", "Inigo San Millan metabolic testing", "Inigo San Millan fat oxidation"]},
        {"name": "Andrew Huberman", "search_terms": ["Andrew Huberman running performance", "Andrew Huberman exercise neuroscience", "Andrew Huberman sleep athletes", "Andrew Huberman cold exposure", "Andrew Huberman dopamine motivation"]},
        {"name": "Phil Maffetone", "search_terms": ["Phil Maffetone MAF method", "Phil Maffetone 180 formula", "Phil Maffetone aerobic training", "Phil Maffetone Mark Allen", "Phil Maffetone fat burning"]},
        {"name": "Yannis Pitsiladis", "search_terms": ["Yannis Pitsiladis Sub2 project", "Yannis Pitsiladis genetics running", "Yannis Pitsiladis East African runners", "Yannis Pitsiladis marathon research", "Yannis Pitsiladis exercise genetics"]},
        {"name": "Trent Stellingwerff", "search_terms": ["Trent Stellingwerff sports nutrition", "Trent Stellingwerff fuel for the work", "Trent Stellingwerff periodized nutrition", "Trent Stellingwerff energy availability", "Trent Stellingwerff endurance nutrition"]},
        {"name": "Ross Tucker", "search_terms": ["Ross Tucker Science of Sport", "Ross Tucker pacing running", "Ross Tucker fatigue brain", "Ross Tucker marathon analysis", "Ross Tucker endurance performance"]},
    ],
    "energizer": [
        {"name": "Eliud Kipchoge", "search_terms": ["Eliud Kipchoge philosophy", "Eliud Kipchoge quotes motivation", "Eliud Kipchoge training Kaptagat", "Eliud Kipchoge no human is limited", "Eliud Kipchoge INEOS 159"]},
        {"name": "Patrick Sang", "search_terms": ["Patrick Sang coaching philosophy", "Patrick Sang Kipchoge coach", "Patrick Sang Kaptagat camp", "Patrick Sang training methods", "Patrick Sang Kenyan running"]},
        {"name": "Renato Canova", "search_terms": ["Renato Canova marathon training", "Renato Canova specific endurance", "Renato Canova coaching philosophy", "Renato Canova training methods", "Renato Canova Kenyan athletes"]},
        {"name": "Shalane Flanagan", "search_terms": ["Shalane Flanagan running philosophy", "Shalane Flanagan NYC Marathon", "Shalane Flanagan coaching", "Shalane Flanagan motivation", "Shalane Flanagan comeback"]},
        {"name": "Des Linden", "search_terms": ["Des Linden Boston Marathon 2018", "Des Linden keep showing up", "Des Linden running philosophy", "Des Linden consistency", "Des Linden training approach"]},
        {"name": "Courtney Dauwalter", "search_terms": ["Courtney Dauwalter ultra running", "Courtney Dauwalter pain cave", "Courtney Dauwalter philosophy", "Courtney Dauwalter mental toughness", "Courtney Dauwalter training"]},
        {"name": "Milind Soman", "search_terms": ["Milind Soman running India", "Milind Soman barefoot running", "Milind Soman fitness philosophy", "Milind Soman ultra marathon", "Milind Soman motivation"]},
        {"name": "Avinash Sable", "search_terms": ["Avinash Sable steeplechase", "Avinash Sable training", "Avinash Sable Indian athletics", "Avinash Sable Olympics", "Avinash Sable village background"]},
        {"name": "Haile Gebrselassie", "search_terms": ["Haile Gebrselassie running philosophy", "Haile Gebrselassie quotes", "Haile Gebrselassie training Ethiopia", "Haile Gebrselassie world records", "Haile Gebrselassie joy running"]},
        {"name": "Hima Das", "search_terms": ["Hima Das Dhing Express", "Hima Das Indian sprinter", "Hima Das gold medals", "Hima Das motivation", "Hima Das training background"]},
    ],
    "warrior": [
        {"name": "Percy Cerutty", "search_terms": ["Percy Cerutty coaching philosophy", "Percy Cerutty Herb Elliott", "Percy Cerutty Portsea", "Percy Cerutty stotan", "Percy Cerutty training methods"]},
        {"name": "David Goggins", "search_terms": ["David Goggins running philosophy", "David Goggins 40 percent rule", "David Goggins mental toughness", "David Goggins ultramarathon", "David Goggins callous mind"]},
        {"name": "Kenenisa Bekele", "search_terms": ["Kenenisa Bekele training", "Kenenisa Bekele racing tactics", "Kenenisa Bekele philosophy", "Kenenisa Bekele comeback", "Kenenisa Bekele Ethiopian training"]},
        {"name": "Mo Farah", "search_terms": ["Mo Farah training philosophy", "Mo Farah marathon transition", "Mo Farah coaching", "Mo Farah motivation", "Mo Farah Olympic training"]},
        {"name": "Emil Zatopek", "search_terms": ["Emil Zatopek training method", "Emil Zatopek interval training", "Emil Zatopek philosophy", "Emil Zatopek Olympic 1952", "Emil Zatopek quotes"]},
        {"name": "Lalita Babar", "search_terms": ["Lalita Babar steeplechase", "Lalita Babar Olympics", "Lalita Babar Indian athletics", "Lalita Babar training", "Lalita Babar background"]},
        {"name": "Jock Semple", "search_terms": ["Jock Semple Boston Marathon", "Jock Semple running philosophy", "Jock Semple marathon history", "Jock Semple Kathrine Switzer", "Jock Semple coaching"]},
    ],
    "sage": [
        {"name": "Arthur Lydiard", "search_terms": ["Arthur Lydiard training philosophy", "Arthur Lydiard base building", "Arthur Lydiard periodization", "Arthur Lydiard aerobic conditioning", "Arthur Lydiard miles make champions"]},
        {"name": "Yuki Kawauchi", "search_terms": ["Yuki Kawauchi marathon philosophy", "Yuki Kawauchi citizen runner", "Yuki Kawauchi Boston 2018", "Yuki Kawauchi consistency", "Yuki Kawauchi 100 marathons"]},
        {"name": "Kathrine Switzer", "search_terms": ["Kathrine Switzer Boston Marathon 1967", "Kathrine Switzer running philosophy", "Kathrine Switzer women running", "Kathrine Switzer marathon woman", "Kathrine Switzer quotes"]},
        {"name": "Kipchoge Keino", "search_terms": ["Kipchoge Keino philosophy", "Kipchoge Keino humanitarian", "Kipchoge Keino Olympic", "Kipchoge Keino Kenyan athletics", "Kipchoge Keino legacy"]},
        {"name": "Deena Kastor", "search_terms": ["Deena Kastor Let Your Mind Run", "Deena Kastor positive thinking", "Deena Kastor marathon philosophy", "Deena Kastor US record", "Deena Kastor mental training"]},
        {"name": "Murakami Haruki", "search_terms": ["Murakami Haruki running memoir", "Murakami What I Talk About Running", "Murakami running philosophy", "Murakami marathon writing", "Murakami discipline running"]},
        {"name": "Budhia Singh", "search_terms": ["Budhia Singh child runner", "Budhia Singh controversy", "Budhia Singh story", "Budhia Singh running India", "Budhia Singh lesson"]},
    ],
}


def scrape_page(page, url, timeout=15000):
    """Scrape a single page, return text content."""
    try:
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        content = page.inner_text("body")
        title = page.title()
        return {"url": url, "title": title, "content": content[:8000]}
    except Exception as e:
        return {"url": url, "title": "FAILED", "content": f"Error: {str(e)[:100]}"}


def search_and_scrape(page, query, max_results=10):
    """Search Google and scrape top results."""
    results = []
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num={max_results}"

    try:
        page.goto(search_url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(1)

        # Extract search result links
        links = page.eval_on_selector_all(
            "a[href^='http']:not([href*='google']):not([href*='youtube.com/watch'])",
            "els => els.map(el => el.href).filter(h => h && !h.includes('google') && !h.includes('accounts.'))"
        )

        # Filter to relevant domains
        good_domains = ['wikipedia', 'runnersworld', 'podiumrunner', 'outsideonline',
                       'scienceofsport', 'strengthrunning', 'runningmagazine', 'letsrun',
                       'triathlete', 'marathonhandbook', 'athletic', 'bbc.com/sport',
                       'theguardian.com/sport', 'nytimes.com', 'espn', 'olympics.com']

        filtered = []
        for link in links[:30]:
            if any(d in link for d in good_domains):
                filtered.append(link)

        # Scrape top results
        for url in filtered[:5]:
            result = scrape_page(page, url)
            if result["content"] and "Error:" not in result["content"]:
                results.append(result)
            time.sleep(0.5)

    except Exception as e:
        pass

    return results


def research_figure(browser, figure_name, search_terms, persona):
    """Research one figure across multiple sources."""
    page = browser.new_page()
    all_content = []

    # 1. Wikipedia (always try first)
    wiki_name = figure_name.replace(" ", "_")
    wiki_urls = [
        f"https://en.wikipedia.org/wiki/{wiki_name}",
        f"https://en.wikipedia.org/wiki/{wiki_name}_(coach)",
        f"https://en.wikipedia.org/wiki/{wiki_name}_(runner)",
        f"https://en.wikipedia.org/wiki/{wiki_name}_(athlete)",
    ]

    for wiki_url in wiki_urls:
        result = scrape_page(page, wiki_url)
        if "does not have an article" not in result["content"] and "FAILED" not in result["title"]:
            all_content.append(result)
            break

    # 2. Search for each search term
    for term in search_terms:
        results = search_and_scrape(page, term, max_results=5)
        all_content.extend(results)
        time.sleep(1)  # Rate limit Google

    # 3. Direct known URLs per figure
    direct_urls = get_direct_urls(figure_name)
    for url in direct_urls:
        result = scrape_page(page, url)
        if "FAILED" not in result["title"]:
            all_content.append(result)
        time.sleep(0.3)

    page.close()
    return all_content


def get_direct_urls(name):
    """Known URLs for specific figures."""
    urls = {
        "Jack Daniels": [
            "https://runsmartproject.com/coaching/jack-daniels/",
        ],
        "Eliud Kipchoge": [
            "https://olympics.com/en/athletes/eliud-kipchoge",
        ],
        "Arthur Lydiard": [
            "https://www.lydiardfoundation.org/",
        ],
        "David Goggins": [
            "https://davidgoggins.com/",
        ],
    }
    return urls.get(name, [])


def extract_unique_findings(content_list, figure_name):
    """Extract unique coaching insights from scraped content."""
    combined = "\n\n".join([
        f"[Source: {c['title']}]\n{c['content'][:3000]}"
        for c in content_list if c.get('content') and "Error:" not in c.get('content', '')
    ])

    # Return raw collected content — the LLM will synthesize later
    return combined


def save_figure_research(persona, figure_name, content, sources_count):
    """Save research for one figure."""
    safe_name = figure_name.lower().replace(" ", "_").replace("'", "")
    filepath = os.path.join(PERSONAS_DIR, persona, f"{safe_name}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {figure_name} — Deep Research\n\n")
        f.write(f"Persona: {persona.title()}\n")
        f.write(f"Sources scraped: {sources_count}\n\n")
        f.write(f"---\n\n")
        f.write(content[:50000])  # Cap at 50K chars per file

    return filepath


def main():
    print("=" * 65)
    print("  DEEP PERSONA RESEARCH — Playwright Scraping")
    print("=" * 65)

    total_figures = sum(len(figs) for figs in FIGURES.values())
    print(f"  Figures to research: {total_figures}")
    print(f"  Search terms per figure: 5")
    print(f"  Target: 50+ unique sources per figure")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        completed = 0
        for persona, figures in FIGURES.items():
            print(f"\n  [{persona.upper()}] — {len(figures)} figures")
            print(f"  {'-'*50}")

            for fig in figures:
                name = fig["name"]
                terms = fig["search_terms"]

                print(f"    Researching: {name}...", end=" ", flush=True)

                try:
                    content_list = research_figure(browser, name, terms, persona)
                    sources = len([c for c in content_list if c.get("content") and "Error:" not in c.get("content", "")])

                    if sources > 0:
                        combined = extract_unique_findings(content_list, name)
                        filepath = save_figure_research(persona, name, combined, sources)
                        print(f"{sources} sources -> saved")
                    else:
                        print(f"0 sources (all failed)")

                    completed += 1

                except Exception as e:
                    print(f"ERROR: {str(e)[:50]}")

                time.sleep(1)  # Rate limit between figures

        browser.close()

    # Final count
    total_files = 0
    total_size = 0
    for persona in FIGURES.keys():
        pdir = os.path.join(PERSONAS_DIR, persona)
        files = [f for f in os.listdir(pdir) if f.endswith('.md')]
        total_files += len(files)
        total_size += sum(os.path.getsize(os.path.join(pdir, f)) for f in files)

    print(f"\n{'=' * 65}")
    print(f"  COMPLETE: {completed}/{total_figures} figures researched")
    print(f"  Files: {total_files}")
    print(f"  Total size: {total_size/1024:.0f} KB")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
