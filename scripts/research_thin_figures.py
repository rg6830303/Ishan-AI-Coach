"""Research the 15 thin figures with alternative URLs that don't block."""

import os
import sys
import io
import time
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONAS_DIR = os.path.join(BASE_DIR, "knowledge", "corpus", "personas")

# Alternative URLs for the 15 thin figures
# Using: Wikipedia (always works), WorldAthletics, TrainingPeaks, MarathonHandbook,
# LetsRun, StrengthRunning, ScienceOfRunning, personal sites
THIN_FIGURES = {
    "scientist": {
        "ross_tucker": [
            "https://en.wikipedia.org/wiki/Ross_Tucker_(sports_scientist)",
            "https://sportsscientists.com/about/",
            "https://sportsscientists.com/2019/10/the-eliud-kipchoge-sub-2-marathon/",
            "https://theconversation.com/profiles/ross-tucker-91937",
            "https://www.linkedin.com/pulse/ross-tucker-sports-scientist",
        ],
        "trent_stellingwerff": [
            "https://en.wikipedia.org/wiki/Trent_Stellingwerff",
            "https://www.mysportscience.com/post/fuel-for-the-work-required",
            "https://www.trainingpeaks.com/blog/nutrition-periodization/",
            "https://link.springer.com/article/10.1007/s40279-019-01066-2",
            "https://journals.humankinetics.com/view/journals/ijsnem/ijsnem-overview.xml",
        ],
        "yannis_pitsiladis": [
            "https://en.wikipedia.org/wiki/Yannis_Pitsiladis",
            "https://www.brighton.ac.uk/staff/yannis-pitsiladis.aspx",
            "https://theconversation.com/profiles/yannis-pitsiladis-170853",
            "https://www.nature.com/articles/s41598-019-45427-7",
            "https://link.springer.com/article/10.1007/s40279-015-0341-0",
        ],
    },
    "energizer": {
        "courtney_dauwalter": [
            "https://en.wikipedia.org/wiki/Courtney_Dauwalter",
            "https://www.irunfar.com/courtney-dauwalter",
            "https://trailrunnermag.com/people/courtney-dauwalter-interview.html",
            "https://strengthrunning.com/courtney-dauwalter/",
            "https://freetrail.com/athlete/courtney-dauwalter/",
        ],
        "milind_soman": [
            "https://en.wikipedia.org/wiki/Milind_Soman",
            "https://timesofindia.indiatimes.com/entertainment/hindi/bollywood/news/milind-soman",
            "https://www.ndtv.com/topic/milind-soman",
            "https://www.mensxp.com/health/celebrity-fitness/milind-soman",
        ],
        "avinash_sable": [
            "https://en.wikipedia.org/wiki/Avinash_Sable",
            "https://www.worldathletics.org/athletes/india/avinash-sable-14595214",
            "https://indianexpress.com/article/sports/sport-others/avinash-sable/",
            "https://www.olympics.com/en/athletes/avinash-sable",
            "https://sportstar.thehindu.com/athletics/avinash-sable",
        ],
        "haile_gebrselassie": [
            "https://en.wikipedia.org/wiki/Haile_Gebrselassie",
            "https://www.worldathletics.org/athletes/ethiopia/haile-gebrselassie-14205196",
            "https://www.theguardian.com/sport/haile-gebrselassie",
            "https://marathonhandbook.com/haile-gebrselassie/",
            "https://www.independent.co.uk/sport/general/athletics/haile-gebrselassie",
        ],
        "hima_das": [
            "https://en.wikipedia.org/wiki/Hima_Das",
            "https://www.worldathletics.org/athletes/india/hima-das-14677498",
            "https://indianexpress.com/article/sports/sport-others/hima-das/",
            "https://sportstar.thehindu.com/athletics/hima-das",
            "https://www.thehindu.com/sport/athletics/hima-das",
        ],
    },
    "warrior": {
        "percy_cerutty": [
            "https://en.wikipedia.org/wiki/Percy_Cerutty",
            "https://en.wikipedia.org/wiki/Herb_Elliott",
            "https://www.runnerstribe.com/features/percy-cerutty-the-stotan/",
            "https://marathonhandbook.com/percy-cerutty/",
            "https://www.theguardian.com/sport/blog/2012/jan/percy-cerutty",
        ],
        "david_goggins": [
            "https://en.wikipedia.org/wiki/David_Goggins",
            "https://davidgoggins.com/about/",
            "https://marathonhandbook.com/david-goggins/",
            "https://strengthrunning.com/david-goggins-running/",
            "https://www.menshealth.com/fitness/a19530623/david-goggins-workout/",
        ],
        "emil_zatopek": [
            "https://en.wikipedia.org/wiki/Emil_Z%C3%A1topek",
            "https://www.worldathletics.org/athletes/czech-republic/emil-zatopek-14168308",
            "https://marathonhandbook.com/emil-zatopek/",
            "https://www.olympicchannel.com/en/athletes/detail/emil-zatopek/",
            "https://www.theguardian.com/sport/emil-zatopek",
        ],
        "mo_farah": [
            "https://en.wikipedia.org/wiki/Mo_Farah",
            "https://www.worldathletics.org/athletes/great-britain-ni/mohamed-farah-14170028",
            "https://marathonhandbook.com/mo-farah/",
            "https://www.independent.co.uk/sport/general/athletics/mo-farah",
            "https://www.telegraph.co.uk/athletics/mo-farah/",
        ],
        "jock_semple": [
            "https://en.wikipedia.org/wiki/Jock_Semple",
            "https://en.wikipedia.org/wiki/Boston_Marathon",
            "https://www.baa.org/races/boston-marathon/history",
            "https://marathonhandbook.com/boston-marathon-history/",
        ],
    },
    "sage": {
        "arthur_lydiard": [
            "https://en.wikipedia.org/wiki/Arthur_Lydiard",
            "https://marathonhandbook.com/lydiard-training/",
            "https://www.scienceofrunning.com/2010/05/arthur-lydiard-training-system.html",
            "https://www.trainingpeaks.com/blog/lydiard-base-building/",
            "https://en.wikipedia.org/wiki/Peter_Snell",
        ],
        "deena_kastor": [
            "https://en.wikipedia.org/wiki/Deena_Kastor",
            "https://www.worldathletics.org/athletes/united-states/deena-kastor-14261648",
            "https://marathonhandbook.com/deena-kastor/",
            "https://strengthrunning.com/deena-kastor-interview/",
            "https://www.podiumrunner.com/culture/deena-kastor-let-your-mind-run/",
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
    except Exception:
        return None


def main():
    print("=" * 65)
    print("  RESEARCHING 15 THIN FIGURES — Alternative URLs")
    print("=" * 65)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        total_new = 0

        for persona, figures in THIN_FIGURES.items():
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

                # Append to existing file or create new
                filepath = os.path.join(PERSONAS_DIR, persona, f"{fig_key}.md")

                if content_list:
                    mode = "a" if os.path.exists(filepath) and os.path.getsize(filepath) > 200 else "w"
                    with open(filepath, mode, encoding="utf-8") as f:
                        if mode == "w":
                            f.write(f"# {name} — Deep Research\n\n")
                            f.write(f"Persona: {persona.title()}\n\n---\n\n")
                        else:
                            f.write(f"\n\n# === ADDITIONAL SOURCES ===\n\n")

                        for item in content_list:
                            f.write(f"## {item['title']}\nURL: {item['url']}\n\n")
                            f.write(f"{item['content']}\n\n---\n\n")

                    total_new += len(content_list)
                    size_kb = os.path.getsize(filepath) / 1024
                    print(f"{len(content_list)}/{len(urls)} sources ({size_kb:.0f} KB)")
                else:
                    print(f"0/{len(urls)} (all blocked)")

                time.sleep(0.5)

        page.close()
        browser.close()

    # Final stats
    print(f"\n{'=' * 65}")
    print(f"  New sources added: {total_new}")

    total_files = 0
    total_kb = 0
    rich = 0
    thin = 0
    for persona in ['scientist', 'energizer', 'warrior', 'sage']:
        pdir = os.path.join(PERSONAS_DIR, persona)
        files = [f for f in os.listdir(pdir) if f.endswith('.md')]
        total_files += len(files)
        for f in files:
            size = os.path.getsize(os.path.join(pdir, f)) / 1024
            total_kb += size
            if size > 5:
                rich += 1
            else:
                thin += 1

    print(f"  Total files: {total_files}")
    print(f"  Total size: {total_kb:.0f} KB")
    print(f"  RICH (>5KB): {rich}")
    print(f"  Still thin (<5KB): {thin}")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
