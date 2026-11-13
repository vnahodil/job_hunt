"""Scraper for Swiss federal research institutes: Eawag, Empa (Refline), and PSI."""

import urllib.parse
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

from src.config import cfg


def fetch_eawag_empa_psi() -> List[Dict]:
    """Scrapes federal research institutes: Eawag (Dübendorf), Empa (Dübendorf), and PSI (Villigen)."""
    print("[2/6] Scanning Eawag, Empa (Refline) & PSI Villigen...")
    results: List[Dict] = []

    # Refline portals (Eawag, Empa) from config
    refline_portals = [
        p for p in cfg.INSTITUTE_PORTALS
        if "refline" in p.get("url", "").lower()
    ]
    for portal in refline_portals:
        inst = portal["name"].split("(")[0].strip()
        default_loc = portal["location"]
        url = portal["url"]
        # Ensure overview query param is present for Refline to list jobs rather than empty search form
        if "listAll" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}form.buttons.listAll=1&target=overview"
        try:
            resp = requests.get(url, headers=cfg.HEADERS, timeout=10)
            if resp.ok:
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    title = a.get_text(" ", strip=True)
                    if "/pub/" in href and len(title) > 8:
                        full_url = urllib.parse.urljoin(url, href)
                        results.append({
                            "title": title,
                            "company": inst,
                            "location": default_loc,
                            "url": full_url,
                            "description": f"{inst} research position in {default_loc}: {title}",
                            "source": f"{inst} Refline",
                        })
        except Exception as e:
            print(f"  [!] {inst} scrape warning: {e}")

    # PSI Villigen
    psi_portals = [
        p for p in cfg.INSTITUTE_PORTALS
        if "psi.ch" in p.get("url", "").lower()
    ]
    for portal in psi_portals:
        psi_url = portal["url"]
        try:
            resp = requests.get(psi_url, headers=cfg.HEADERS, timeout=10)
            if resp.ok:
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    title = a.get_text(" ", strip=True)
                    if "/hr/job-opportunities/" in href and len(title) > 10:
                        results.append({
                            "title": title,
                            "company": "Paul Scherrer Institute (PSI)",
                            "location": portal["location"],
                            "url": urllib.parse.urljoin(psi_url, href),
                            "description": f"PSI {portal['location']} position: {title}",
                            "source": "PSI Career Portal",
                        })
        except Exception as e:
            print(f"  [!] PSI scrape warning: {e}")

    print(f"  -> Found {len(results)} listings across Eawag, Empa & PSI.")
    return results
