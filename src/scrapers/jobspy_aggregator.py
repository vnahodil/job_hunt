"""Indeed / LinkedIn / Google Jobs aggregator via python-jobspy."""

import time
from typing import List, Dict, Optional

from src.config import cfg

try:
    from jobspy import scrape_jobs
    HAS_JOBSPY = True
except ImportError:
    HAS_JOBSPY = False


def _scrape_single_site(site: str, query: str, hours_old: int) -> List[Dict]:
    """Helper to query a single aggregator site with site-specific parameters."""
    # Site-specific parameter configuration
    if site == "linkedin":
        loc = "Zurich, Switzerland"
        country_ind = None
        limit = 15
    elif site == "indeed":
        loc = "Zurich"
        country_ind = "switzerland"
        limit = 20
    else:
        loc = "Zurich, Switzerland"
        country_ind = None
        limit = 15

    results: List[Dict] = []
    try:
        kwargs = {
            "site_name": [site],
            "search_term": query,
            "location": loc,
            "distance": 35 if site == "linkedin" else 50,
            "hours_old": hours_old,
            "results_wanted": limit,
            "fetch_description": False,
            "verbose": 0,
        }
        if country_ind:
            kwargs["country_indeed"] = country_ind

        df = scrape_jobs(**kwargs)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                title = str(row.get("title", "")).strip()
                company = str(row.get("company", "Unknown")).strip()
                location = str(row.get("location", "Zurich")).strip()
                url = str(row.get("job_url_direct") or row.get("job_url", "")).strip()
                if not title or not url:
                    continue
                results.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": url,
                    "description": str(row.get("description", "")),
                    "source": f"JobSpy ({site.title()})",
                })
    except Exception as e:
        print(f"    [!] JobSpy {site} warning on '{query}': {e}")
    return results


def fetch_jobspy_aggregators(hours_old: int = 72, sites: Optional[List[str]] = None) -> List[Dict]:
    """Scrapes aggregator job boards (defaults to Indeed & LinkedIn Switzerland)."""
    if not HAS_JOBSPY:
        print("[WARN] python-jobspy not installed. Skipping aggregator stage.")
        return []

    if sites is None:
        sites = ["indeed", "linkedin"]

    print(f"[1/7] Scanning Aggregators ({', '.join(sites).title()}) (last {hours_old}h)...")
    collected: List[Dict] = []

    for q in cfg.AGGREGATOR_QUERIES:
        for site in sites:
            items = _scrape_single_site(site, q, hours_old)
            collected.extend(items)
            time.sleep(0.5)

    print(f"  -> Retrieved {len(collected)} raw listings from aggregators.")
    return collected
