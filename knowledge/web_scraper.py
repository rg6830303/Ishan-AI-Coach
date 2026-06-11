import urllib.parse
import urllib.request
import re
import json

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

def scrape_web(query: str) -> list[dict]:
    """
    Scrapes the web live for the query using DuckDuckGo HTML or Wikipedia API fallback.
    Returns a list of dicts: [{"title": ..., "url": ..., "snippet": ...}]
    """
    results = []
    
    # 1. DuckDuckGo HTML Scraper
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": USER_AGENT}
        )
        
        with urllib.request.urlopen(req, timeout=6) as response:
            html = response.read().decode("utf-8", errors="ignore")
            
        # Parse results using regex
        # Results are contained in divs with class "web-result" or similar
        # Links: <a class="result__snippet" ...>...</a>
        # Titles/URLs: <a class="result__url" href="URL">Title</a>
        result_blocks = html.split('<div class="result results_links results_links_deep web-result')
        
        for block in result_blocks[1:5]:  # top 4 organic results
            # Extract URL
            url_match = re.search(r'class="result__url"\s+href="([^"]+)"', block)
            # Extract Title
            title_match = re.search(r'class="result__snippet"[^>]*>([^<]+)</a>', block)
            if not title_match:
                # Alternate title pattern
                title_match = re.search(r'class="result__snippet"[^>]*>(.+?)</a>', block, re.DOTALL)
            
            # Extract Snippet
            snippet_match = re.search(r'class="result__snippet"[^>]*>(.+?)</a>', block, re.DOTALL)
            if not snippet_match:
                snippet_match = re.search(r'class="result__snippet"[^>]*>([^<]+)', block)
                
            # Fallback title extraction from link text
            link_match = re.search(r'<a class="result__url"[^>]*>(.+?)</a>', block, re.DOTALL)
            
            url_str = url_match.group(1) if url_match else ""
            if url_str:
                if "uddg=" in url_str or "/l/?" in url_str:
                    try:
                        if url_str.startswith("//"):
                            url_str = "https:" + url_str
                        parsed_url = urllib.parse.urlparse(url_str)
                        query_params = urllib.parse.parse_qs(parsed_url.query)
                        if "uddg" in query_params:
                            url_str = query_params["uddg"][0]
                    except Exception:
                        pass
            
            # Clean HTML tags from parsed strings
            title_raw = link_match.group(1) if link_match else "Search Result"
            title_str = re.sub(r'<[^>]+>', '', title_raw).strip()
            
            snippet_raw = snippet_match.group(1) if snippet_match else ""
            snippet_str = re.sub(r'<[^>]+>', '', snippet_raw).strip()
            
            if url_str and snippet_str:
                results.append({
                    "title": title_str,
                    "url": url_str,
                    "snippet": snippet_str
                })
    except Exception as e:
        # Fallback to Wikipedia API if DuckDuckGo is throttled
        pass
        
    if not results:
        # 2. Wikipedia search API fallback
        try:
            wiki_query = urllib.parse.quote(query)
            wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={wiki_query}&utf8=&format=json"
            req = urllib.request.Request(
                wiki_url,
                headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            search_results = data.get("query", {}).get("search", [])
            for r in search_results[:3]:
                title = r.get("title")
                snippet = re.sub(r'<[^>]+>', '', r.get("snippet", "")).strip()
                pageid = r.get("pageid")
                results.append({
                    "title": title,
                    "url": f"https://en.wikipedia.org/?curid={pageid}",
                    "snippet": snippet + "..."
                })
        except Exception:
            pass

    return results
