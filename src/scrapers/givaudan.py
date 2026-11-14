"""Direct Phenom People scraper for Givaudan Switzerland (Kemptthal / Dübendorf / Volketswil)."""

import json
import re
from typing import Dict, List

import requests

from src.config import cfg

GIVAUDAN_SEARCH_URL = "https://careers.givaudan.com/global/en/search-results"


def fetch_givaudan_jobs() -> List[Dict]:
    """Scrapes active Givaudan postings across Kemptthal, Dübendorf, and Switzerland via Phenom People."""
    print("[*] Polling Givaudan Phenom People portal (Kemptthal / Dübendorf)...")
    results: List[Dict] = []
    seen_ids = set()

    headers = {
        **cfg.HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    offset = 0
    max_offset = 60

    while offset <= max_offset:
        url = f"{GIVAUDAN_SEARCH_URL}?keywords=Switzerland&from={offset}"
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if not r.ok:
                break
            matches = re.findall(r"phApp\.ddo\s*=\s*({.*?});\s*phApp", r.text, re.DOTALL)
            if not matches:
                break
            data = json.loads(matches[0])
            jobs = data.get("eagerLoadRefineSearch", {}).get("data", {}).get("jobs", [])
            if not jobs:
                break

            new_in_page = 0
            for j in jobs:
                jid = str(j.get("jobId", "")).strip()
                if not jid or jid in seen_ids:
                    continue
                seen_ids.add(jid)
                new_in_page += 1

                title = str(j.get("title", "")).strip()
                city = str(j.get("city", "")).strip() or "Kemptthal"
                country = str(j.get("country", "")).strip()

                # Filter strictly to Swiss locations (ignore foreign postings appearing in search)
                if country and country.lower() not in {"switzerland", "schweiz", "ch"}:
                    continue

                # Filter to commutable Zurich / Eastern Switzerland sites (Kemptthal, Dübendorf, Volketswil)
                city_lower = city.lower()
                if any(k in city_lower for k in ["vernier", "geneva", "genève"]):
                    continue

                # Positive & Negative keyword guardrails
                if not cfg.POSITIVE_ROLE_KEYWORDS.search(title) or cfg.NEGATIVE_ROLE_KEYWORDS.search(title):
                    continue

                job_url = f"https://careers.givaudan.com/global/en/job/{jid}"

                desc = j.get("descriptionTeaser") or ""
                if not desc or len(desc) < 80:
                    desc = f"Position: {title} at Givaudan in {city}, Switzerland."

                results.append({
                    "title": title,
                    "company": "Givaudan",
                    "location": f"{city}, Switzerland",
                    "url": job_url,
                    "description": desc,
                    "source": "Givaudan Phenom",
                })

            if new_in_page == 0:
                break
            offset += 10
        except Exception as e:
            print(f"  [!] Error scraping Givaudan Phenom page at offset {offset}: {e}")
            break

    print(f"  -> Found {len(results)} relevant Swiss candidate openings at Givaudan.")
    return results
