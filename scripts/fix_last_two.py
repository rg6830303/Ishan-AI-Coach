"""Fix last 2 thin figures: Haile Gebrselassie + Mo Farah."""
import os, sys, io, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

PERSONAS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge", "corpus", "personas")

fixes = [
    ('energizer', 'haile_gebrselassie', [
        'https://en.wikipedia.org/wiki/Haile_Gebrselassie',
        'https://www.britannica.com/biography/Haile-Gebrselassie',
    ]),
    ('warrior', 'mo_farah', [
        'https://en.wikipedia.org/wiki/Mo_Farah',
        'https://www.britannica.com/biography/Mo-Farah',
    ]),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for persona, fig_key, urls in fixes:
        name = fig_key.replace('_', ' ').title()
        print(f'{name}...', end=' ', flush=True)
        content_list = []
        for url in urls:
            try:
                page.goto(url, timeout=15000, wait_until='domcontentloaded')
                time.sleep(1)
                content = page.inner_text('body')
                title = page.title()
                content = re.sub(r'\n{3,}', '\n\n', content)
                if len(content) > 300:
                    content_list.append({'url': url, 'title': title, 'content': content[:15000]})
            except Exception as e:
                print(f'({url.split("/")[-1]} failed)', end=' ')
            time.sleep(0.5)

        filepath = os.path.join(PERSONAS_DIR, persona, f'{fig_key}.md')
        if content_list:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f'# {name} - Deep Research\n\nPersona: {persona.title()}\n\n---\n\n')
                for item in content_list:
                    f.write(f"## {item['title']}\nURL: {item['url']}\n\n{item['content']}\n\n---\n\n")
            size = os.path.getsize(filepath) / 1024
            print(f'{len(content_list)} sources ({size:.0f} KB)')
        else:
            print('all blocked')

    page.close()
    browser.close()

print("\nDone.")
