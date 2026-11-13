"""Scraper for curated direct company career pages from config/targets.yaml."""

import urllib.parse
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

from src.config import cfg


# Common non-job URL patterns (marketing, products, services, media)
IGNORED_URL_FRAGMENTS = {
    "/our-products/", "/products/", "/services/", "/innovations/",
    "/news/", "/press/", "/events/", "/about-us/", "/about/",
    "/leasing/", "/contact/", "/our-commitment/", "/privacy/",
    "/terms/", "/cookie", "/wp-content/uploads/", "#",
}

IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".mp4", ".pdf",
}

IGNORED_EXACT_TITLES = {
    "careers", "jobs", "open positions", "offene stellen", "read more",
    "apply now", "learn more", "contact us", "view all", "see all",
    "synthetic diesel", "synthetic gasoline", "synthetic wax", "synthetic waxes",
    "offices and laboratories", "zurich: a life sciences hotspot",
    "collaboration and memberships", "quality policy (iso)", "quality policy",
    "applications", "research and development", "scientific citations",
    "life sciences", "spark application packages",
}


# Legitimate job URL indicators (must contain at least one of these to be considered a real vacancy link)
JOB_URL_INDICATORS = (
    "/job", "/jobs", "/career", "/careers", "/vacancy", "/vacancies",
    "/position", "/positions", "/opening", "/openings", "/stelle", "/stellen",
    "/pub/", "/posting", "/apply", "icims.com", "greenhouse.io", "lever.co",
    "workday", "personio", "recruitee", "join.com", "smartrecruiters", "bamboohr",
    "teamtailor", "successfactors", "myworkday", "taleo", "avature", "ashbyhq",
    "notion.site", "breezy.hr", "starhunter.software", "starhunter", "job-ad",
    "prospective.ch", "refline.ch", "softgarden", "prescreen", "onlyfy",
)


def fetch_curated_career_pages() -> List[Dict]:
    """Polls the curated list of local Cleantech/Biotech/Chemistry company career pages."""
    n = len(cfg.DIRECT_CAREER_PAGES)
    print(f"[5/6] Polling Curated Local Watchlist ({n} companies from config/targets.yaml)...")
    results: List[Dict] = []
    seen_urls = set()

    for item in cfg.DIRECT_CAREER_PAGES:
        try:
            r = requests.get(item["url"], headers=cfg.HEADERS, timeout=8)
            if not r.ok:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                # Find heading inside card link if present, else whole link text
                heading = a.find(["h1", "h2", "h3", "h4", "h5", "strong"])
                text = heading.get_text(" ", strip=True) if heading else a.get_text(" ", strip=True)
                text = text.replace("Title", "").strip()
                t_lower = text.lower()

                # Basic length and keyword filter
                if not (8 < len(text) < 130):
                    continue
                if not cfg.POSITIVE_ROLE_KEYWORDS.search(text) or cfg.NEGATIVE_ROLE_KEYWORDS.search(text):
                    continue

                # Skip known marketing or generic titles
                if t_lower in IGNORED_EXACT_TITLES:
                    continue

                # Skip if text is simply the company name or too close to it
                co_lower = item["company"].lower()
                if t_lower == co_lower or (co_lower in t_lower and len(text) < len(item["company"]) + 5):
                    continue

                full_url = urllib.parse.urljoin(item["url"], href)
                url_lower = full_url.lower()

                # Must look like an actual job vacancy URL
                if not any(ind in url_lower for ind in JOB_URL_INDICATORS):
                    continue

                # Skip media files & anchors
                if any(url_lower.endswith(ext) for ext in IGNORED_EXTENSIONS):
                    continue
                if any(frag in url_lower for frag in IGNORED_URL_FRAGMENTS):
                    continue
                if url_lower.startswith("javascript:") or url_lower.startswith("mailto:"):
                    continue

                # Determine specific location if present in URL/text
                job_loc = item["location"]
                for candidate_loc in ["Bubendorf", "Stein", "Hunzenschwil", "Aarau", "Fehraltorf", "Kemptthal", "Schlieren", "Zofingen", "Baden", "Pratteln", "Muttenz", "Basel", "Zurich"]:
                    if candidate_loc.lower() in url_lower or candidate_loc.lower() in t_lower:
                        job_loc = candidate_loc
                        break

                # Deduplicate by URL
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                results.append({
                    "title": text,
                    "company": item["company"],
                    "location": job_loc,
                    "url": full_url,
                    "description": f"Direct career listing at {item['company']} ({job_loc}): {text}",
                    "source": "Curated Watchlist",
                })
        except Exception:
            continue
    print(f"  -> Found {len(results)} clean candidate links on curated career pages.")
    return results
