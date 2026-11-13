"""Scraper for ETH Spin-Off Directory, Bio-Technopark Schlieren, and JoinUp.ch."""

import urllib.parse
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

from src.config import cfg


def fetch_eth_spinoff_ecosystem(scan_spinoff_table: bool = True) -> List[Dict]:
    """
    Scans:
    1) Bio-Technopark Schlieren Job Board
    2) Official ETH Spin-Off Directory Table (filtering for target departments)
    """
    print("[3/6] Scanning ETH Spin-Off Directory, JoinUp.ch & Bio-Technopark Schlieren...")
    results: List[Dict] = []

    # A. Bio-Technopark Schlieren-Zürich
    btp_portals = [
        p for p in cfg.INSTITUTE_PORTALS
        if "bio-technopark" in p.get("url", "").lower()
    ]
    for portal in btp_portals:
        btp_url = portal["url"]
        try:
            r = requests.get(btp_url, headers=cfg.HEADERS, timeout=10)
            if r.ok:
                soup = BeautifulSoup(r.text, "lxml")
                for a in soup.find_all("a", href=True):
                    text = a.get_text(" ", strip=True)
                    href = a["href"]
                    if cfg.POSITIVE_ROLE_KEYWORDS.search(text) and len(text) > 10:
                        results.append({
                            "title": text,
                            "company": "Bio-Technopark Schlieren Member",
                            "location": "Schlieren",
                            "url": urllib.parse.urljoin(btp_url, href),
                            "description": f"Bio-Technopark Schlieren role: {text}",
                            "source": "Bio-Technopark Schlieren",
                        })
        except Exception as e:
            print(f"  [!] Bio-Technopark warning: {e}")

    # B. Official ETH Spin-offs Table (D-CHAB / D-MATL / Cleantech auto-discovery)
    if scan_spinoff_table:
        try:
            r = requests.get(cfg.ETH_SPINOFF_TABLE_URL, headers=cfg.HEADERS, timeout=12)
            if r.ok:
                soup = BeautifulSoup(r.text, "lxml")
                spinoffs_to_check = []
                for tr in soup.find_all("tr"):
                    tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                    if len(tds) >= 5:
                        name, _, year, _, dept = tds[0], tds[1], tds[2], tds[3], tds[4]
                        link_tag = tr.find("a", href=True)
                        if dept in cfg.ETH_TARGET_DEPTS and link_tag and link_tag["href"].startswith("http"):
                            spinoffs_to_check.append((name, dept, link_tag["href"]))

                # Probe the newest 25 chemistry/materials/env spin-offs for open career links
                for name, dept, base_url in spinoffs_to_check[:25]:
                    for suffix in ["/careers", "/jobs", "/career", ""]:
                        target_url = base_url.rstrip("/") + suffix
                        try:
                            sr = requests.get(target_url, headers=cfg.HEADERS, timeout=4)
                            if sr.ok and sr.status_code == 200:
                                ssoup = BeautifulSoup(sr.text, "lxml")
                                for a in ssoup.find_all("a", href=True):
                                    t = a.get_text(" ", strip=True)
                                    if (
                                        10 < len(t) < 95
                                        and cfg.POSITIVE_ROLE_KEYWORDS.search(t)
                                        and not cfg.NEGATIVE_ROLE_KEYWORDS.search(t)
                                    ):
                                        results.append({
                                            "title": t,
                                            "company": f"{name} (ETH {dept})",
                                            "location": "Zürich / Schlieren",
                                            "url": urllib.parse.urljoin(target_url, a["href"]),
                                            "description": f"ETH {dept} Spin-off ({name}): {t}",
                                            "source": "ETH Spin-Off Directory",
                                        })
                                if suffix != "":
                                    break
                        except Exception:
                            continue
        except Exception as e:
            print(f"  [!] ETH Spin-off table scan warning: {e}")

    print(f"  -> Found {len(results)} potential roles from ETH Spin-off & Schlieren portals.")
    return results
