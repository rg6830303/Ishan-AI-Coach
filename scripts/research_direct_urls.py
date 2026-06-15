"""Deep persona research v3 — DIRECT URLs only (no search engines).

Google/DuckDuckGo block automated search. But direct URLs work fine.
This script has a curated list of 10-20 direct URLs per figure.
"""

import os
import sys
import io
import time
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONAS_DIR = os.path.join(BASE_DIR, "knowledge", "corpus", "personas")

# Direct URLs per figure — Wikipedia + known coaching/sports sites
FIGURE_URLS = {
    "scientist": {
        "jack_daniels": [
            "https://en.wikipedia.org/wiki/Jack_Daniels_(coach)",
            "https://runsmartproject.com/coaching/jack-daniels/",
            "https://www.runnersworld.com/advanced/a20801762/lessons-from-jack-daniels/",
            "https://marathonhandbook.com/jack-daniels-running-formula/",
            "https://www.scienceofrunning.com/2009/07/jack-daniels-training.html",
            "https://www.podiumrunner.com/training/jack-daniels-best-workouts/",
        ],
        "tim_noakes": [
            "https://en.wikipedia.org/wiki/Tim_Noakes",
            "https://thenoakesfoundation.org/",
            "https://www.outsideonline.com/health/running/tim-noakes-lore-of-running/",
            "https://www.runnersworld.com/advanced/a20825471/the-central-governor-theory/",
            "https://www.theguardian.com/lifeandstyle/2012/jul/15/tim-noakes-rewrite-science-sport",
        ],
        "steve_magness": [
            "https://en.wikipedia.org/wiki/Steve_Magness",
            "https://www.stevemagness.com/",
            "https://www.scienceofrunning.com/",
            "https://www.outsideonline.com/health/running/steve-magness-do-hard-things/",
            "https://www.podiumrunner.com/culture/steve-magness-science-of-running/",
        ],
        "stephen_seiler": [
            "https://en.wikipedia.org/wiki/Stephen_Seiler",
            "https://www.researchgate.net/profile/Stephen-Seiler",
            "https://marathonhandbook.com/polarized-training/",
            "https://www.trainingpeaks.com/blog/what-is-polarized-training/",
            "https://www.runnersworld.com/training/a20812270/the-80-20-rule-of-training/",
        ],
        "inigo_san_millan": [
            "https://en.wikipedia.org/wiki/I%C3%B1igo_San_Mill%C3%A1n",
            "https://www.trainingpeaks.com/blog/zone-2-training-guide/",
            "https://peterattiamd.com/inigosanmillan/",
            "https://www.bicycling.com/training/a39459791/zone-2-training-guide/",
        ],
        "andrew_huberman": [
            "https://en.wikipedia.org/wiki/Andrew_Huberman",
            "https://hubermanlab.com/",
            "https://www.hubermanlab.com/newsletter/fitness-toolkit-protocol-and-tools",
        ],
        "phil_maffetone": [
            "https://en.wikipedia.org/wiki/Phil_Maffetone",
            "https://philmaffetone.com/",
            "https://philmaffetone.com/180-formula/",
            "https://marathonhandbook.com/maf-training/",
            "https://www.runnersworld.com/training/a20828651/maffetone-method/",
        ],
        "yannis_pitsiladis": [
            "https://en.wikipedia.org/wiki/Yannis_Pitsiladis",
            "https://www.sub2hrs.com/",
            "https://www.brighton.ac.uk/staff/yannis-pitsiladis.aspx",
        ],
        "trent_stellingwerff": [
            "https://www.researchgate.net/profile/Trent-Stellingwerff",
            "https://www.mysportscience.com/post/periodised-nutrition-for-athletes",
            "https://bjsm.bmj.com/content/52/7/439",
        ],
        "ross_tucker": [
            "https://en.wikipedia.org/wiki/Ross_Tucker_(sports_scientist)",
            "https://sportsscientists.com/",
            "https://www.theguardian.com/sport/blog/ross-tucker-sport-science",
        ],
    },
    "energizer": {
        "eliud_kipchoge": [
            "https://en.wikipedia.org/wiki/Eliud_Kipchoge",
            "https://olympics.com/en/athletes/eliud-kipchoge",
            "https://www.ineos159challenge.com/",
            "https://www.runnersworld.com/runners-stories/a20823062/eliud-kipchoge/",
            "https://www.bbc.com/sport/athletics/50025543",
            "https://www.theguardian.com/sport/eliud-kipchoge",
        ],
        "patrick_sang": [
            "https://en.wikipedia.org/wiki/Patrick_Sang",
            "https://www.worldathletics.org/athletes/kenya/patrick-sang-14282308",
            "https://www.bbc.com/sport/athletics/46090498",
        ],
        "renato_canova": [
            "https://en.wikipedia.org/wiki/Renato_Canova",
            "https://www.letsrun.com/forum/flat_read.php?thread=4551025",
            "https://runningscience.co.za/renato-canova/",
        ],
        "shalane_flanagan": [
            "https://en.wikipedia.org/wiki/Shalane_Flanagan",
            "https://olympics.com/en/athletes/shalane-flanagan",
            "https://www.runnersworld.com/runners-stories/a20854364/shalane-flanagan-nyc-marathon/",
            "https://www.nytimes.com/2017/11/05/sports/shalane-flanagan-new-york-city-marathon.html",
        ],
        "des_linden": [
            "https://en.wikipedia.org/wiki/Desiree_Linden",
            "https://www.runnersworld.com/runners-stories/a20013706/des-linden-boston-marathon-2018/",
            "https://olympics.com/en/athletes/desiree-linden",
        ],
        "courtney_dauwalter": [
            "https://en.wikipedia.org/wiki/Courtney_Dauwalter",
            "https://www.irunfar.com/courtney-dauwalter",
            "https://trailrunnermag.com/people/courtney-dauwalter.html",
            "https://www.outsideonline.com/outdoor-adventure/exploration-survival/courtney-dauwalter-pain-cave/",
        ],
        "milind_soman": [
            "https://en.wikipedia.org/wiki/Milind_Soman",
            "https://www.hindustantimes.com/fitness/milind-soman-fitness",
            "https://timesofindia.indiatimes.com/life-style/health-fitness/fitness/milind-soman",
        ],
        "avinash_sable": [
            "https://en.wikipedia.org/wiki/Avinash_Sable",
            "https://olympics.com/en/athletes/avinash-sable",
            "https://www.worldathletics.org/athletes/india/avinash-sable-14595214",
        ],
        "haile_gebrselassie": [
            "https://en.wikipedia.org/wiki/Haile_Gebrselassie",
            "https://olympics.com/en/athletes/haile-gebrselassie",
            "https://www.worldathletics.org/athletes/ethiopia/haile-gebrselassie-14205196",
            "https://www.bbc.com/sport/athletics/24985804",
        ],
        "hima_das": [
            "https://en.wikipedia.org/wiki/Hima_Das",
            "https://olympics.com/en/athletes/hima-das",
            "https://www.worldathletics.org/athletes/india/hima-das-14677498",
        ],
    },
    "warrior": {
        "percy_cerutty": [
            "https://en.wikipedia.org/wiki/Percy_Cerutty",
            "https://www.runnerstribe.com/percy-cerutty/",
            "https://www.theguardian.com/sport/2012/jan/21/percy-cerutty-herb-elliott-coach",
        ],
        "david_goggins": [
            "https://en.wikipedia.org/wiki/David_Goggins",
            "https://davidgoggins.com/",
            "https://www.runnersworld.com/runners-stories/a36005659/david-goggins-running/",
            "https://www.outsideonline.com/culture/books-media/david-goggins-cant-hurt-me/",
        ],
        "kenenisa_bekele": [
            "https://en.wikipedia.org/wiki/Kenenisa_Bekele",
            "https://olympics.com/en/athletes/kenenisa-bekele",
            "https://www.worldathletics.org/athletes/ethiopia/kenenisa-bekele-14205192",
            "https://www.bbc.com/sport/athletics/49804752",
        ],
        "mo_farah": [
            "https://en.wikipedia.org/wiki/Mo_Farah",
            "https://olympics.com/en/athletes/mo-farah",
            "https://www.bbc.com/sport/athletics/mo-farah",
            "https://www.theguardian.com/sport/mo-farah",
        ],
        "emil_zatopek": [
            "https://en.wikipedia.org/wiki/Emil_Z%C3%A1topek",
            "https://olympics.com/en/athletes/emil-zatopek",
            "https://www.runnersworld.com/runners-stories/a20783621/emil-zatopek/",
        ],
        "lalita_babar": [
            "https://en.wikipedia.org/wiki/Lalita_Babar",
            "https://olympics.com/en/athletes/lalita-babar",
            "https://www.worldathletics.org/athletes/india/lalita-babar-14369222",
        ],
        "jock_semple": [
            "https://en.wikipedia.org/wiki/Jock_Semple",
            "https://www.baa.org/about/history",
        ],
    },
    "sage": {
        "arthur_lydiard": [
            "https://en.wikipedia.org/wiki/Arthur_Lydiard",
            "https://www.lydiardfoundation.org/",
            "https://marathonhandbook.com/lydiard-training/",
            "https://www.runnersworld.com/advanced/a20816051/arthur-lydiard/",
            "https://www.scienceofrunning.com/2010/05/arthur-lydiard.html",
        ],
        "yuki_kawauchi": [
            "https://en.wikipedia.org/wiki/Yuki_Kawauchi",
            "https://www.runnersworld.com/runners-stories/a20805472/yuki-kawauchi/",
            "https://www.bbc.com/sport/athletics/43802953",
        ],
        "kathrine_switzer": [
            "https://en.wikipedia.org/wiki/Kathrine_Switzer",
            "https://kathrineswitzer.com/",
            "https://www.runnersworld.com/runners-stories/a20783810/kathrine-switzer-boston-marathon/",
            "https://www.bbc.com/sport/athletics/39tried625083",
        ],
        "kipchoge_keino": [
            "https://en.wikipedia.org/wiki/Kipchoge_Keino",
            "https://olympics.com/en/athletes/kipchoge-keino",
            "https://www.worldathletics.org/athletes/kenya/kipchoge-keino-14236440",
        ],
        "deena_kastor": [
            "https://en.wikipedia.org/wiki/Deena_Kastor",
            "https://olympics.com/en/athletes/deena-kastor",
            "https://www.runnersworld.com/runners-stories/a20791tried755/deena-kastor/",
        ],
        "murakami_haruki": [
            "https://en.wikipedia.org/wiki/What_I_Talk_About_When_I_Talk_About_Running",
            "https://en.wikipedia.org/wiki/Haruki_Murakami",
            "https://www.theguardian.com/books/2008/aug/10/fiction",
        ],
        "budhia_singh": [
            "https://en.wikipedia.org/wiki/Budhia_Singh",
            "https://www.bbc.com/news/world-asia-india-36355tried723",
        ],
    },
}


def scrape_url(page, url, max_chars=15000):
    """Scrape one URL."""
    try:
        page.goto(url, timeout=12000, wait_until="domcontentloaded")
        time.sleep(0.5)
        content = page.inner_text("body")
        title = page.title()
        content = re.sub(r'\n{3,}', '\n\n', content)
        return {"url": url, "title": title, "content": content[:max_chars]}
    except Exception as e:
        return None


def main():
    print("=" * 65)
    print("  DEEP PERSONA RESEARCH v3 — Direct URLs")
    print("=" * 65)

    total_urls = sum(len(urls) for persona_figs in FIGURE_URLS.values() for urls in persona_figs.values())
    print(f"  Total URLs to scrape: {total_urls}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        total_sources = 0

        for persona, figures in FIGURE_URLS.items():
            print(f"\n  [{persona.upper()}]")

            for fig_key, urls in figures.items():
                name = fig_key.replace("_", " ").title()
                print(f"    {name}...", end=" ", flush=True)

                content_list = []
                for url in urls:
                    result = scrape_url(page, url)
                    if result and result["content"] and len(result["content"]) > 300:
                        content_list.append(result)
                    time.sleep(0.3)

                # Save
                filepath = os.path.join(PERSONAS_DIR, persona, f"{fig_key}.md")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"# {name} — Deep Research\n\n")
                    f.write(f"Persona: {persona.title()}\n")
                    f.write(f"Sources: {len(content_list)}\n\n---\n\n")
                    for item in content_list:
                        f.write(f"## {item['title']}\nURL: {item['url']}\n\n")
                        f.write(f"{item['content']}\n\n---\n\n")

                total_sources += len(content_list)
                print(f"{len(content_list)}/{len(urls)} sources")

        page.close()
        browser.close()

    # Stats
    total_files = 0
    total_kb = 0
    for persona in FIGURE_URLS.keys():
        pdir = os.path.join(PERSONAS_DIR, persona)
        files = [f for f in os.listdir(pdir) if f.endswith('.md')]
        total_files += len(files)
        total_kb += sum(os.path.getsize(os.path.join(pdir, f)) for f in files) / 1024

    print(f"\n{'=' * 65}")
    print(f"  Total sources scraped: {total_sources}/{total_urls}")
    print(f"  Files: {total_files}")
    print(f"  Size: {total_kb:.0f} KB")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
