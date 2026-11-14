"""Scraper for LifeScienceWork.ch (Switzerland's Specialized Life Science & Chemistry Job Portal)."""

import urllib.parse
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from src.config import cfg

DEFAULT_LIFESCIENCE_QUERIES = [
    "chemistry",
    "chemist",
    "chemie",
    "synthese",
    "analytical",
    "analytik",
    "laborant",
    "formulation",
    "quality assurance",
    "regulatory",
]

BASE_URL = "https://lifesciencework.ch"


def fetch_lifesciencework_jobs(queries: Optional[List[str]] = None) -> List[Dict]:
    """
    Scrapes lifesciencework.ch for specialized Swiss biotech, pharma, CDMO,
    and chemical laboratory openings across Basel, Zurich, Zug, and surrounding cantons.
    """
    if queries is None:
        queries = DEFAULT_LIFESCIENCE_QUERIES

    print(f"[3.6/6] Querying Life Science Work Portal across {len(queries)} target keywords...")
    results: List[Dict] = []
    seen_urls = set()

    for q in queries:
        try:
            encoded_q = urllib.parse.quote(q)
            url = f"{BASE_URL}/jobs?q={encoded_q}"
            r = requests.get(url, headers=cfg.HEADERS, timeout=10)
            if not r.ok:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            articles = soup.find_all("article", class_=lambda c: c and "job" in c)

            for art in articles:
                title_el = art.find("h3")
                if not title_el:
                    continue
                title = title_el.get_text(" ", strip=True)

                link_el = art.find("a", href=lambda h: h and h.startswith("/jobs/"))
                if not link_el:
                    continue
                full_url = urllib.parse.urljoin(BASE_URL, link_el["href"])
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Keyword pre-filtering
                if not cfg.POSITIVE_ROLE_KEYWORDS.search(title) or cfg.NEGATIVE_ROLE_KEYWORDS.search(title):
                    continue

                meta = art.find("p", class_="meta")
                company = "Life Science Employer"
                location = "Zurich / Switzerland"

                if meta:
                    co_link = meta.find("a")
                    if co_link:
                        company = co_link.get_text(strip=True)

                    meta_text = meta.get_text(" ", strip=True)
                    # Extract location after middle dot '·'
                    for part in meta_text.split("·"):
                        p_strip = part.strip()
                        if p_strip and p_strip != company and not any(
                            k in p_strip.lower() for k in ["hybrid", "remote", "full-time", "part-time", "100%", "80%"]
                        ):
                            location = p_strip
                            break

                results.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": full_url,
                    "description": f"Specialized Life Sciences vacancy at {company} ({location}): {title}",
                    "source": "Life Science Work",
                })
        except Exception as e:
            print(f"  [!] Error scraping lifesciencework for query '{q}': {e}")
            continue

    print(f"  -> Discovered {len(results)} specialized roles on Life Science Work portal.")
    return results
