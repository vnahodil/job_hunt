"""Scraper for myScience.ch — the Swiss portal for scientific and research jobs."""

import re
import time
from typing import List, Dict
import requests
from bs4 import BeautifulSoup

from src.config import cfg

# Known Swiss locations commonly appearing in myScience metadata
SWISS_LOCATIONS = [
    "Zurich", "Zürich", "Basel", "Muttenz", "Dübendorf", "Duebendorf",
    "Villigen", "Schlieren", "Baden", "Winterthur", "Zug", "Luzern",
    "Lucerne", "Schaffhausen", "Bern", "Lausanne", "Geneva", "St. Gallen",
    "Neuchâtel", "Fribourg", "Solothurn", "Aarau", "Olten", "Kemptthal",
    "Wädenswil", "Waedenswil", "Uster",
]


def _extract_location_from_meta(meta_text: str) -> str:
    """Extract location from myScience metadata text (e.g., 'Environment - Chemistry Zurich - 15 Oct')."""
    meta_lower = meta_text.lower()
    for loc in SWISS_LOCATIONS:
        if re.search(rf"\b{re.escape(loc.lower())}\b", meta_lower):
            return loc

    # If foreign country is mentioned, indicate it
    if "germany" in meta_lower or "deutschland" in meta_lower:
        return "Germany"
    if "france" in meta_lower:
        return "France"
    if "austria" in meta_lower:
        return "Austria"

    return "Zurich"


def fetch_myscience_jobs(queries: List[str] = None) -> List[Dict]:
    """Scrapes active scientific & research vacancies from myScience.ch."""
    if queries is None:
        queries = getattr(cfg, "MYSCIENCE_QUERIES", ["chemistry", "chemist", "analytical", "cleantech"])

    print(f"[3/7] Scanning myScience.ch ({len(queries)} science search queries)...")
    collected: List[Dict] = []
    seen_urls = set()

    for q in queries:
        url = f"https://www.myscience.ch/jobs/search?q={requests.utils.quote(q)}"
        try:
            resp = requests.get(url, headers=cfg.HEADERS, timeout=10)
            if not resp.ok:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href.startswith("/jobs/id"):
                    continue

                full_url = f"https://www.myscience.ch{href}"
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                res_div = a.find("div", class_="results")
                if not res_div:
                    continue

                title_div = res_div.find("div", class_="results_title")
                title = title_div.get_text(strip=True) if title_div else a.get_text(strip=True)

                org_div = res_div.find("div", class_="results_organization_department")
                org_desc = org_div.get_text(" ", strip=True) if org_div else ""

                block_div = res_div.find("div", class_="block")
                block_text = block_div.get_text(" ", strip=True) if block_div else ""

                # Extract company name from organization field
                company_match = re.match(r"^([^,\.\n\–\-]+)", org_desc)
                company = company_match.group(1).strip() if company_match else "myScience Research"
                if not company or len(company) > 50:
                    company = "Swiss Research / Industry"

                location = _extract_location_from_meta(block_text)

                # Skip explicitly foreign roles outside Switzerland
                if location in ("Germany", "France", "Austria"):
                    continue

                collected.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": full_url,
                    "description": f"{title}. Organization: {org_desc}. Field: {block_text}",
                    "source": "myScience.ch",
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"    [!] myScience warning on '{q}': {e}")

    print(f"  -> Discovered {len(collected)} positions from myScience.ch.")
    return collected
