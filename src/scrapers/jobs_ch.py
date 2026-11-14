"""Native REST API scraper for jobs.ch (Switzerland's #1 Job Portal)."""

import time
import urllib.parse
from typing import List, Dict, Optional

import requests

from src.config import cfg

DEFAULT_JOBS_CH_QUERIES = [
    "organic chemistry",
    "synthetic chemist",
    "chemist",
    "analytical chemist",
    "chemiker",
    "process chemist",
    "cleantech chemistry",
    "pfas",
    "water treatment chemistry",
    "formulation chemist",
    "laborant chemie",
]


def fetch_jobs_ch(queries: Optional[List[str]] = None, rows_per_query: int = 20) -> List[Dict]:
    """
    Directly queries jobs.ch public REST API for Swiss industry, CDMO, and SME openings.
    Endpoint: https://www.jobs.ch/api/v1/public/search
    Note: jobs.ch caps `rows` at maximum 20 per request (values > 20 return 422).
    """
    if queries is None:
        queries = cfg.JOBS_CH_QUERIES or DEFAULT_JOBS_CH_QUERIES
    # Enforce maximum rows allowed by jobs.ch API
    rows_per_query = min(20, rows_per_query)

    print(f"[3.5/6] Querying jobs.ch REST API across {len(queries)} target keywords...")
    results: List[Dict] = []
    seen_ids = set()

    for q in queries:
        try:
            encoded_q = urllib.parse.quote(q)
            url = f"https://www.jobs.ch/api/v1/public/search?query={encoded_q}&rows={rows_per_query}"
            r = requests.get(url, headers=cfg.HEADERS, timeout=8)
            if not r.ok:
                continue

            data = r.json()
            docs = data.get("documents", [])
            for doc in docs:
                jid = doc.get("job_id")
                if not jid or jid in seen_ids:
                    continue
                seen_ids.add(jid)

                title = str(doc.get("title", "")).strip()
                company = str(doc.get("company_name", "Unknown")).strip()
                location = str(doc.get("place", "Zurich")).strip()
                preview = str(doc.get("preview", "")).strip()

                # Get clean detail URL (prefer English, fallback to German or ID URL)
                links = doc.get("_links", {})
                job_url = (
                    links.get("detail_en", {}).get("href")
                    or links.get("detail_de", {}).get("href")
                    or f"https://www.jobs.ch/en/vacancies/detail/{jid}/"
                )

                if not title or len(title) < 5:
                    continue

                # Quick pre-filter: exclude obvious non-scientific hits
                if cfg.NEGATIVE_ROLE_KEYWORDS.search(title):
                    continue

                results.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": job_url,
                    "description": f"{company} in {location}: {title}. {preview}",
                    "source": "jobs.ch",
                })

            time.sleep(0.5)
        except Exception as e:
            print(f"  [!] jobs.ch error on '{q}': {e}")

    print(f"  -> Retrieved {len(results)} clean positions from jobs.ch.")
    return results
