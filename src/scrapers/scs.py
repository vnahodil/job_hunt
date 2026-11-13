"""Scraper for Swiss Chemical Society (SCS / SCG) job directory and member portals."""

import urllib.parse
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

from src.config import cfg

SCS_JOBS_URL = "https://scg.ch/jobs"


def fetch_scs_jobs() -> List[Dict]:
    """
    Crawls the official Swiss Chemical Society (scg.ch/jobs) portal and tracks
    member company vacancy hubs, direct listings, and partner opportunities.
    """
    print("[3.8/6] Querying Swiss Chemical Society (SCG / SCS) Portal (scg.ch/jobs)...")
    results: List[Dict] = []
    seen_urls = set()

    try:
        r = requests.get(SCS_JOBS_URL, headers=cfg.HEADERS, timeout=10)
        if not r.ok:
            print(f"  [!] SCS portal returned status {r.status_code}")
            return results

        soup = BeautifulSoup(r.text, "html.parser")

        # 1. Scan all anchor links on the SCS jobs page
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(" ", strip=True)
            if not href or href.startswith("mailto:") or href.startswith("javascript:") or "#" in href:
                continue

            # Ignore social media, equipment/product catalogs, and general SCS home links
            h_lower = href.lower()
            if any(dom in h_lower for dom in ["linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com"]):
                continue
            if any(frag in h_lower for frag in ["glasreaktoren", "druckreaktoren", "prozessanlagen", "produkte", "equipment"]):
                continue

            full_url = urllib.parse.urljoin(SCS_JOBS_URL, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Check if this is a direct job posting, graduate program, or specific vacancy
            t_lower = text.lower()
            if any(k in h_lower or k in t_lower for k in ["job", "career", "karriere", "stellen", "internship", "graduate", "trainee", "associate"]):
                if cfg.POSITIVE_ROLE_KEYWORDS.search(text) and not cfg.NEGATIVE_ROLE_KEYWORDS.search(text):
                    results.append({
                        "title": text,
                        "company": "SCS Partner",
                        "location": "Switzerland",
                        "url": full_url,
                        "description": f"Swiss Chemical Society (SCS) vacancy / program: {text}",
                        "source": "Swiss Chemical Society (SCS)",
                    })

    except Exception as e:
        print(f"  [!] Error checking SCS portal: {e}")

    # 2. Check Buchiglas Uster (Büchi AG Uster - specialized glass & synthesis equipment near Zurich)
    buchiglas_url = "https://www.buchiglas.ch/de/unternehmen/stellenangebote.html"
    try:
        r_buchi = requests.get(buchiglas_url, headers=cfg.HEADERS, timeout=8)
        if r_buchi.ok:
            soup_buchi = BeautifulSoup(r_buchi.text, "html.parser")
            # Buchiglas lists openings in accordion items on stellenangebote.html (never in nav links)
            for it in soup_buchi.find_all("div", class_="item"):
                title_el = it.find(class_="accordion-titles")
                if not title_el:
                    continue
                t = title_el.get_text(" ", strip=True).replace("Stellenangebot", "").strip()
                if not (8 < len(t) < 120):
                    continue
                # Exclude administration, export, assembly, and AVOR production planning
                t_lower = t.lower()
                if any(x in t_lower for x in ["monteur", "avor", "produktionsplanung", "sachbearbeiter", "personaladministration"]):
                    continue
                if cfg.POSITIVE_ROLE_KEYWORDS.search(t) and not cfg.NEGATIVE_ROLE_KEYWORDS.search(t):
                    content_el = it.find(class_="accordion-content")
                    desc = content_el.get_text(" ", strip=True) if content_el else t
                    if buchiglas_url not in seen_urls:
                        seen_urls.add(buchiglas_url)
                        results.append({
                            "title": t,
                            "company": "Büchi AG (Buchiglas Uster)",
                            "location": "Uster",
                            "url": buchiglas_url,
                            "description": f"Direct career opportunity at Büchi AG Uster: {desc[:400]}",
                            "source": "Buchiglas Uster",
                        })
    except Exception as e:
        print(f"  [!] Error checking Buchiglas: {e}")

    print(f"  -> Discovered {len(results)} vacancies via Swiss Chemical Society network.")
    return results
