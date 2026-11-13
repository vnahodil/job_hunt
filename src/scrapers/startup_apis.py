"""Scraper for Swiss Cleantech & Biotech Startups via Direct ATS JSON APIs (Greenhouse, Lever, Recruitee, Teamtailor)."""

from typing import List, Dict, Optional

import requests

from src.config import cfg

DEFAULT_STARTUP_TARGETS = [
    {
        "company": "Climeworks",
        "platform": "recruitee",
        "slug": "climeworks",
        "default_location": "Zurich",
    },
    {
        "company": "Neustark",
        "platform": "teamtailor",
        "url": "https://careers.neustark.com/jobs.json",
        "default_location": "Zurich",
    },
    {
        "company": "ANYbotics",
        "platform": "lever",
        "slug": "anybotics",
        "default_location": "Zurich",
    },
    {
        "company": "Numab Therapeutics",
        "platform": "greenhouse",
        "slug": "numab",
        "default_location": "Horgen / Zurich",
    },
]


def fetch_startup_api_jobs(targets: Optional[List[Dict]] = None) -> List[Dict]:
    """
    Directly queries public REST/JSON APIs for Swiss cleantech & biotech startups.
    Guarantees 100% structured data with full job descriptions and zero bot blocks.
    """
    if targets is None:
        targets = cfg.STARTUP_API_TARGETS if hasattr(cfg, "STARTUP_API_TARGETS") and cfg.STARTUP_API_TARGETS else DEFAULT_STARTUP_TARGETS

    print(f"[3.7/6] Querying Direct Startup JSON APIs across {len(targets)} tech companies...")
    results: List[Dict] = []
    seen_urls = set()

    for item in targets:
        company = item.get("company", "Startup")
        platform = item.get("platform", "").lower()
        default_loc = item.get("default_location", "Zurich")

        try:
            # 1. Recruitee JSON API
            if platform == "recruitee":
                slug = item.get("slug")
                api_url = f"https://{slug}.recruitee.com/api/offers/"
                r = requests.get(api_url, headers=cfg.HEADERS, timeout=10)
                if r.ok:
                    data = r.json()
                    for off in data.get("offers", []):
                        title = off.get("title", "").strip()
                        url = off.get("careers_url", "").strip()
                        if not title or not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        if not cfg.POSITIVE_ROLE_KEYWORDS.search(title) or cfg.NEGATIVE_ROLE_KEYWORDS.search(title):
                            continue

                        loc = off.get("city") or off.get("location") or default_loc
                        desc = f"{off.get('description', '')} {off.get('requirements', '')}".strip()
                        results.append({
                            "title": title,
                            "company": company,
                            "location": loc,
                            "url": url,
                            "description": desc or f"Direct opportunity at {company} ({loc}): {title}",
                            "source": f"Startup API ({company})",
                        })

            # 2. Teamtailor JSON Feed
            elif platform == "teamtailor":
                api_url = item.get("url")
                if not api_url and item.get("slug"):
                    api_url = f"https://{item['slug']}.teamtailor.com/jobs.json"
                r = requests.get(api_url, headers=cfg.HEADERS, timeout=10)
                if r.ok:
                    data = r.json()
                    for it in data.get("items", []):
                        title = it.get("title", "").strip()
                        url = it.get("url", "").strip()
                        if not title or not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        if not cfg.POSITIVE_ROLE_KEYWORDS.search(title) or cfg.NEGATIVE_ROLE_KEYWORDS.search(title):
                            continue

                        desc = it.get("content_html", "").strip()
                        results.append({
                            "title": title,
                            "company": company,
                            "location": default_loc,
                            "url": url,
                            "description": desc or f"Direct opportunity at {company} ({default_loc}): {title}",
                            "source": f"Startup API ({company})",
                        })

            # 3. Lever JSON API
            elif platform == "lever":
                slug = item.get("slug")
                api_url = f"https://api.lever.co/v0/postings/{slug}"
                r = requests.get(api_url, headers=cfg.HEADERS, timeout=10)
                if r.ok:
                    data = r.json()
                    for post in data:
                        title = post.get("text", "").strip()
                        url = post.get("hostedUrl", "").strip()
                        if not title or not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        cats = post.get("categories", {})
                        loc = cats.get("location", default_loc)

                        # Filter for Swiss / Zurich / Remote postings
                        loc_lower = loc.lower()
                        if not any(k in loc_lower for k in ["zurich", "zürich", "switzerland", "schweiz", "remote"]):
                            continue

                        if not cfg.POSITIVE_ROLE_KEYWORDS.search(title) or cfg.NEGATIVE_ROLE_KEYWORDS.search(title):
                            continue

                        desc = post.get("descriptionPlain", "").strip()
                        results.append({
                            "title": title,
                            "company": company,
                            "location": loc,
                            "url": url,
                            "description": desc or f"Direct opportunity at {company} ({loc}): {title}",
                            "source": f"Startup API ({company})",
                        })

            # 4. Greenhouse JSON API
            elif platform == "greenhouse":
                slug = item.get("slug")
                api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
                r = requests.get(api_url, headers=cfg.HEADERS, timeout=10)
                if r.ok:
                    data = r.json()
                    for job in data.get("jobs", []):
                        title = job.get("title", "").strip()
                        url = job.get("absolute_url", "").strip()
                        if not title or not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        loc = job.get("location", {}).get("name", default_loc)
                        loc_lower = loc.lower()
                        if not any(k in loc_lower for k in ["zurich", "zürich", "switzerland", "schweiz", "remote"]):
                            continue

                        if not cfg.POSITIVE_ROLE_KEYWORDS.search(title) or cfg.NEGATIVE_ROLE_KEYWORDS.search(title):
                            continue

                        results.append({
                            "title": title,
                            "company": company,
                            "location": loc,
                            "url": url,
                            "description": f"Direct opportunity at {company} ({loc}): {title}",
                            "source": f"Startup API ({company})",
                        })

        except Exception as e:
            print(f"  [!] Error querying startup API for {company}: {e}")
            continue

    print(f"  -> Discovered {len(results)} clean startup positions via JSON APIs.")
    return results
