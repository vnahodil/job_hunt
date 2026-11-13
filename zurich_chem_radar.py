#!/usr/bin/env python3
"""
Zurich Chemistry & Cleantech Job Radar (One-Shot Pipeline)
Tailored for: MSc Organic Chemistry + 2y PhD Research + 6m ETH + 1y Oxyle (Cleantech)
Commute origin: Glattbrugg / Zurich Area (<= 60 min transit or car)
"""

import os
import re
import sys
import json
import time
import sqlite3
import hashlib
import argparse
import webbrowser
import urllib.parse
from datetime import datetime
from typing import List, Dict, Optional

import requests
import pandas as pd
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

try:
    from jobspy import scrape_jobs
    HAS_JOBSPY = True
except ImportError:
    HAS_JOBSPY = False
    print("[WARN] python-jobspy not installed. Skipping Indeed/LinkedIn/Google aggregator stage.")

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# =====================================================================
# 1. CONFIGURATION & WATCHLISTS
# =====================================================================

HOME_ORIGIN = os.getenv("JOB_ORIGIN", "Glattbrugg")
MAX_COMMUTE_MINS = int(os.getenv("MAX_COMMUTE_MINS", "60"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # Optional: falls back to heuristic scorer if empty
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chem_jobs.db")
REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,de-CH;q=0.8,de;q=0.7",
}

# Realistic driving times (minutes) from Glattbrugg/Zurich North to industrial hubs
DRIVING_OVERRIDES = {
    "glattbrugg": 5, "opfikon": 5, "kloten": 8, "zürich": 15, "zurich": 15,
    "oerlikon": 10, "dübendorf": 12, "dubendorf": 12, "wallisellen": 10,
    "schlieren": 20, "urdorf": 22, "dietikon": 22, "otelfingen": 16,
    "regensdorf": 14, "kemptthal": 15, "winterthur": 20, "fehraltorf": 20,
    "illnau": 18, "volketswil": 15, "schaffhausen": 30, "neuhausen": 30,
    "baden": 25, "dättwil": 25, "turgi": 28, "brugg": 30, "villigen": 33,
    "würenlingen": 30, "stein": 40, "stein ag": 40, "dottikon": 32,
    "lenzburg": 30, "aarau": 38, "zug": 38, "baar": 35, "rotkreuz": 40,
    "stäfa": 30, "hombrechtikon": 30, "wädenswil": 30, "horgen": 28,
    "bülach": 15, "rafz": 22, "aadorf": 28, "frauenfeld": 30,
    "basel": 60, "allschwil": 62, "muttenz": 55, "pratteln": 52, "kaiseraugst": 48,
}

# Search queries for JobSpy (Indeed CH, LinkedIn, Google Jobs)
AGGREGATOR_QUERIES = [
    "Organic Chemistry",
    "Research Associate Chemistry",
    "Associate Scientist Chemistry",
    "R&D Chemist",
    "Analytical Chemist",
    "Process Chemist",
    "Chemiker",
    "Wissenschaftlicher Mitarbeiter Chemie",
    "Chemical Engineer R&D",
    "Application Specialist Chemistry",
    "PFAS Water Treatment",
]

# Workday CaaS JSON API Endpoints (Direct zero-browser querying for major Swiss employers)
WORKDAY_TARGETS = [
    {
        "company": "Givaudan",
        "default_location": "Kemptthal",
        "api_url": "https://givaudan.wd3.myworkdayjobs.com/wday/cxs/givaudan/Givaudan_Careers/jobs",
        "site_url": "https://givaudan.wd3.myworkdayjobs.com/en-US/Givaudan_Careers",
        "search_terms": ["Chemistry", "Analytical", "Scientist", "Kemptthal"],
    },
    {
        "company": "Lonza",
        "default_location": "Basel / Stein",
        "api_url": "https://lonza.wd3.myworkdayjobs.com/wday/cxs/lonza/Lonza_Careers/jobs",
        "site_url": "https://lonza.wd3.myworkdayjobs.com/en-US/Lonza_Careers",
        "search_terms": ["Chemist", "Associate Scientist", "Analytical", "Organic"],
    },
    {
        "company": "Novartis",
        "default_location": "Basel / Stein",
        "api_url": "https://novartis.wd3.myworkdayjobs.com/wday/cxs/novartis/Novartis_Careers/jobs",
        "site_url": "https://novartis.wd3.myworkdayjobs.com/en-US/Novartis_Careers",
        "search_terms": ["Synthetic", "Organic Chemistry", "Scientific Associate", "Analytical"],
    },
    {
        "company": "Roche",
        "default_location": "Basel / Rotkreuz",
        "api_url": "https://roche.wd3.myworkdayjobs.com/wday/cxs/roche/roche-ext/jobs",
        "site_url": "https://roche.wd3.myworkdayjobs.com/en-US/roche-ext",
        "search_terms": ["Chemist", "Scientist Chemistry", "Analytical", "Small Molecules"],
    },
    {
        "company": "Takeda",
        "default_location": "Zürich (Glattpark)",
        "api_url": "https://takeda.wd3.myworkdayjobs.com/wday/cxs/takeda/External/jobs",
        "site_url": "https://takeda.wd3.myworkdayjobs.com/en-US/External",
        "search_terms": ["Zurich", "Neuchatel", "Quality", "Analytical", "Scientist"],
    },
]

# Curated Direct Career Pages (Cleantech, Schlieren Biotech, Local Chemical Industry)
DIRECT_CAREER_PAGES = [
    {"company": "Oxyle", "location": "Schlieren", "url": "https://oxyle.ch/careers/"},
    {"company": "Climeworks", "location": "Zürich Oerlikon", "url": "https://climeworks.com/careers"},
    {"company": "Synhelion", "location": "Zürich", "url": "https://synhelion.com/careers"},
    {"company": "SpiroChem", "location": "Basel", "url": "https://spirochem.com/careers.html"},
    {"company": "Philochem", "location": "Otelfingen", "url": "https://www.philochem.ch/careers/open-positions/"},
    {"company": "Dottikon ES", "location": "Dottikon", "url": "https://dottikon.com/en/careers/job-openings/"},
    {"company": "CellX Biosolutions", "location": "Schlieren", "url": "https://www.cellxbiosolutions.com/careers"},
    {"company": "Molecular Partners", "location": "Schlieren", "url": "https://www.molecularpartners.com/careers/"},
    {"company": "InSphero", "location": "Schlieren", "url": "https://insphero.com/company/careers/"},
    {"company": "Cutiss", "location": "Schlieren", "url": "https://cutiss.swiss/careers/"},
    {"company": "Celerion", "location": "Fehraltorf", "url": "https://www.celerion.com/careers"},
    {"company": "Halag Chemie", "location": "Aadorf / Winterthur", "url": "https://www.halagchemie.ch/ueber-uns/offene-stellen/"},
    {"company": "BÜCHI Labortechnik", "location": "Flawil / St. Gallen", "url": "https://www.buchi.com/en/jobs"},
    {"company": "Tecan", "location": "Männedorf", "url": "https://www.tecan.com/careers"},
    {"company": "Sika", "location": "Zürich", "url": "https://che.sika.com/de/karriere/offene-stellen.html"},
]

# Official ETH Spin-Off Directory URL & Target Departments
ETH_SPINOFF_TABLE_URL = (
    "https://entrepreneurship.ethz.ch/startup-stories/"
    "explore-startup-portraits-and-success-stories/uebersicht-eth-spin-offs.html"
)
ETH_TARGET_DEPTS = {"D-CHAB", "D-MATL", "D-BSSE", "D-BAUG", "D-USYS", "D-BIOL", "D-HEST", "D-EAPS"}

# Keywords for filtering direct career page links
POSITIVE_ROLE_KEYWORDS = re.compile(
    r"(chem|scien|research|r&d|analyt|synthe|labor|lab\b|process|formulat|"
    r"cataly|pfas|water|material|polymer|quality|qa\b|qc\b|regulatory|application|"
    r"consultant|engineer|wissenschaft|mitarbeiter|specialist|associate|intern)",
    re.IGNORECASE,
)
NEGATIVE_ROLE_KEYWORDS = re.compile(
    r"(accountant|finance|payroll|legal counsel|receptionist|chauffeur|"
    r"hr manager|recruiter|full stack|frontend|ios developer|android|lehrstelle|schnupper)",
    re.IGNORECASE,
)


# =====================================================================
# 2. STRUCTURED EVALUATION MODEL (GEMINI + HEURISTIC FALLBACK)
# =====================================================================

class JobEvaluation(BaseModel):
    is_relevant: bool = Field(description="True if role fits MSc Chemist with 3.5 yrs research/cleantech exp")
    match_score: int = Field(description="Score 1-10 for candidate profile fit")
    role_category: str = Field(description="One of: R&D Lab, Cleantech, Analytical, Process/Industry, Pharma QA/Reg, Consulting/App")
    degree_fit: str = Field(description="Short badge: 'Ideal for MSc+Exp', 'MSc/BSc', 'PhD or Equiv Exp', or 'Strict PhD Only'")
    language_req: str = Field(description="Short badge: 'English', 'EN + DE B1/B2 OK', or 'Fluent DE Required'")
    one_line_summary: str = Field(description="Concise 1-sentence reason why this job fits or what to watch out for")


def evaluate_job_heuristic(title: str, company: str, desc: str, source: str) -> JobEvaluation:
    """Zero-cost deterministic scorer used when GEMINI_API_KEY is not set or rate-limited."""
    text = f"{title} {company} {desc}".lower()

    if NEGATIVE_ROLE_KEYWORDS.search(title):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Other",
            degree_fit="N/A", language_req="N/A", one_line_summary="Non-scientific role filtered out."
        )

    score = 6
    category = "R&D Lab"

    # Boost core profile matches
    if any(k in text for k in ["organic", "synthe", "small molecule", "medicinal"]):
        score += 2
    if any(k in text for k in ["cleantech", "water", "pfas", "cataly", "environmental", "recycling", "sustainability"]):
        score += 2
        category = "Cleantech"
    if any(k in text for k in ["analytical", "hplc", "lc-ms", "gc-ms", "mass spec", "chromatography", "nmr"]):
        score += 1
        category = "Analytical"
    if any(k in text for k in ["associate scientist", "research associate", "wissenschaftliche", "scientific collaborator", "r&d chemist"]):
        score += 2
    if any(k in text for k in ["application specialist", "consultant", "technical sales", "product steward"]):
        category = "Consulting/App"
    if any(k in text for k in ["quality", "qa ", "gmp", "regulatory", "pharmacovigilance"]):
        category = "Pharma QA/Reg"

    # Degree check
    degree_fit = "Ideal for MSc+Exp"
    if "postdoc" in title.lower() or "professor" in title.lower():
        score -= 4
        degree_fit = "Strict PhD Only"
    elif "phd required" in text and "master" not in text and "equivalent" not in text:
        score -= 2
        degree_fit = "Strict PhD Only"
    elif "master" in text or "msc" in text or "m.sc" in text:
        score += 1
        degree_fit = "Ideal for MSc+Exp"

    # Language check
    de_words = len(re.findall(r"\b(und|oder|wir|für|mit|aufgaben|profil)\b", text))
    lang_req = "EN + DE B1/B2 OK" if de_words > 4 else "English"
    if any(k in text for k in ["verhandlungssicher", "muttersprache", "c1", "c2", "fluent german required"]):
        lang_req = "Fluent DE Required"
        score -= 1

    score = max(1, min(10, score))
    is_rel = score >= 6 and bool(POSITIVE_ROLE_KEYWORDS.search(f"{title} {desc[:400]}"))

    summary = f"{category} role at {company} ({source}); matches MSc Chemistry + R&D background."
    return JobEvaluation(
        is_relevant=is_rel,
        match_score=score,
        role_category=category,
        degree_fit=degree_fit,
        language_req=lang_req,
        one_line_summary=summary,
    )


def evaluate_job(client, title: str, company: str, location: str, desc: str, source: str) -> JobEvaluation:
    """Uses Gemini 2.5 Flash if configured, otherwise falls back cleanly to heuristic."""
    if not client:
        return evaluate_job_heuristic(title, company, desc, source)

    desc_clean = desc.strip() if desc else ""
    if len(desc_clean) < 30:
        desc_clean = f"Position: {title} at {company} in {location}."

    prompt = f"""
    Evaluate this Swiss job opening for the following candidate living in the Zurich area:
    - Education: Master's (MSc) in Organic Chemistry + 2 years of PhD research in Czech Republic + 6 months exchange at ETH Zurich.
    - Current Role: 1-year research internship at Oxyle (ETH cleantech spin-off in Schlieren, catalytic water treatment / PFAS destruction).
    - Total hands-on R&D experience: ~3.5 years.
    - Languages: Full English proficiency (C1/C2), B1-B2 German.
    - Target Sectors: R&D, Cleantech, Organic/Analytical/Process Chemistry, Pharma, Industry, Application Specialist, or Consulting.

    Job Title: {title}
    Company: {company}
    Location: {location}
    Source: {source}
    Description: {desc_clean[:5000]}
    """
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": JobEvaluation,
                    "temperature": 0.1,
                },
            )
            return JobEvaluation.model_validate_json(resp.text)
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "resource_exhausted" in err_msg:
                time.sleep(5 * (attempt + 1))
                continue
            return evaluate_job_heuristic(title, company, desc, source)
    return evaluate_job_heuristic(title, company, desc, source)


def rescore_database_jobs(conn: sqlite3.Connection, client, limit: Optional[int] = None) -> None:
    """Re-scores existing jobs stored in chem_jobs.db using Gemini 2.5 Flash."""
    if not client:
        print("[!] GEMINI_API_KEY is not set or google-genai is not available. Cannot rescore.")
        return

    cur = conn.cursor()
    query = "SELECT job_hash, title, company, location, url, source, summary FROM jobs"
    if limit:
        query += f" LIMIT {int(limit)}"
    cur.execute(query)
    rows = cur.fetchall()
    total = len(rows)

    print(f"[*] Re-scoring {total} existing jobs in chem_jobs.db using Gemini 2.5 Flash...")
    print("    (Pacing with a 4s interval to respect Google AI Studio free tier limits ~15 RPM)")

    updated = 0
    for i, (jhash, title, company, location, url, source, old_summary) in enumerate(rows, 1):
        print(f"  [{i}/{total}] Evaluating: {title[:38]} @ {company[:20]}...", flush=True)
        ev = evaluate_job(client, title, company, location, old_summary, source)
        cur.execute(
            """UPDATE jobs
               SET match_score = ?, is_relevant = ?, role_category = ?, degree_fit = ?, language_req = ?, summary = ?
               WHERE job_hash = ?""",
            (
                ev.match_score,
                1 if ev.is_relevant else 0,
                ev.role_category,
                ev.degree_fit,
                ev.language_req,
                ev.one_line_summary,
                jhash,
            ),
        )
        conn.commit()
        updated += 1
        if i < total:
            time.sleep(4.0)

    print(f"[+] Successfully rescored {updated} jobs in chem_jobs.db!")


# =====================================================================
# 3. DATABASE & SBB COMMUTE ENGINE
# =====================================================================

def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_hash TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            source TEXT,
            commute_mins INTEGER,
            commute_mode TEXT,
            match_score INTEGER,
            is_relevant INTEGER,
            role_category TEXT,
            degree_fit TEXT,
            language_req TEXT,
            summary TEXT,
            date_found TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS commute_cache (
            location TEXT PRIMARY KEY,
            minutes INTEGER,
            mode TEXT
        )
    """)
    conn.commit()
    return conn


def make_job_hash(company: str, title: str) -> str:
    norm_co = re.sub(r"[^a-z0-9]", "", str(company).lower())
    norm_ti = re.sub(r"[^a-z0-9]", "", str(title).lower())
    return hashlib.sha256(f"{norm_co}::{norm_ti}".encode("utf-8")).hexdigest()


def get_commute_info(conn: sqlite3.Connection, location_str: str) -> tuple[int, str]:
    """Returns (minutes, mode_label) from HOME_ORIGIN using overrides + SBB API."""
    if not location_str or pd.isna(location_str):
        return 35, "CH (Unspecified)"

    loc_lower = str(location_str).lower().strip()
    if loc_lower in {"switzerland", "schweiz", "suisse", "remote", "hybrid"}:
        return 30, "CH / Hybrid"

    # Clean city token (e.g. "Schlieren, Zurich, Switzerland" -> "schlieren")
    city_token = re.split(r"[,/|-]", loc_lower)[0].strip()
    city_token = re.sub(r"\b\d{4}\b", "", city_token).strip()

    # 1. Check fast driving/local overrides
    for town, mins in DRIVING_OVERRIDES.items():
        if town in loc_lower:
            mode = "SBB/Car" if mins <= 25 else "Car/SBB"
            return mins, mode

    # 2. Check SQLite cache
    cur = conn.cursor()
    cur.execute("SELECT minutes, mode FROM commute_cache WHERE location = ?", (city_token,))
    cached = cur.fetchone()
    if cached:
        return cached[0], cached[1]

    # 3. Query SBB transport.opendata.ch API for 08:00 arrival
    mins, mode = 999, "SBB"
    try:
        url = (
            f"http://transport.opendata.ch/v1/connections?"
            f"from={urllib.parse.quote(HOME_ORIGIN)}&"
            f"to={urllib.parse.quote(city_token)}&"
            f"time=08:00&isArrivalTime=1&limit=1"
        )
        r = requests.get(url, headers=HEADERS, timeout=6)
        if r.ok:
            conns = r.json().get("connections", [])
            if conns:
                dur = conns[0].get("duration", "00d01:30:00")
                days, hms = dur.split("d")
                hh, mm, _ = map(int, hms.split(":"))
                mins = int(days) * 1440 + hh * 60 + mm
                mode = "SBB Train"
    except Exception:
        mins, mode = 50, "Est."

    cur.execute("INSERT OR REPLACE INTO commute_cache VALUES (?, ?, ?)", (city_token, mins, mode))
    conn.commit()
    return mins, mode


# =====================================================================
# 4. MULTI-SOURCE SCRAPER MODULES
# =====================================================================

def fetch_jobspy_aggregators(hours_old: int = 72, sites: Optional[List[str]] = None) -> List[Dict]:
    """Scrapes aggregator job boards (defaults to Indeed Switzerland; LinkedIn requires proxies)."""
    if not HAS_JOBSPY:
        return []
    if sites is None:
        sites = ["indeed"]
    print(f"[1/6] Scanning {', '.join(sites).title()} (last {hours_old}h)...")
    collected = []
    for q in AGGREGATOR_QUERIES:
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=q,
                location="Zurich, Switzerland",
                distance=55,  # Covers Zurich, Zug, Schaffhausen, Aargau, Winterthur, Basel
                hours_old=hours_old,
                results_wanted=20,
                country_indeed="Switzerland",
                fetch_description=True,
                verbose=0,
            )
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    collected.append({
                        "title": str(row.get("title", "")).strip(),
                        "company": str(row.get("company", "Unknown")).strip(),
                        "location": str(row.get("location", "Zurich")).strip(),
                        "url": str(row.get("job_url_direct") or row.get("job_url", "")),
                        "description": str(row.get("description", "")),
                        "source": f"JobSpy ({row.get('site', 'Aggregator')})",
                    })
            time.sleep(1.0)
        except Exception as e:
            print(f"  [!] JobSpy warning on '{q}': {e}")
    print(f"  -> Retrieved {len(collected)} raw listings from aggregators.")
    return collected


def fetch_eawag_empa_psi() -> List[Dict]:
    """Scrapes federal research institutes: Eawag (Dübendorf), Empa (Dübendorf), and PSI (Villigen)."""
    print("[2/6] Scanning Eawag, Empa (Refline) & PSI Villigen...")
    results = []
    refline_targets = [
        ("Eawag", "Dübendorf", "https://apply.refline.ch/673277/search.html"),
        ("Empa", "Dübendorf", "https://apply.refline.ch/673276/search.html"),
    ]
    for inst, default_loc, url in refline_targets:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
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
    try:
        psi_url = "https://www.psi.ch/en/hr/job-opportunities"
        resp = requests.get(psi_url, headers=HEADERS, timeout=10)
        if resp.ok:
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                title = a.get_text(" ", strip=True)
                if "/hr/job-opportunities/" in href and len(title) > 10:
                    results.append({
                        "title": title,
                        "company": "Paul Scherrer Institute (PSI)",
                        "location": "Villigen",
                        "url": urllib.parse.urljoin(psi_url, href),
                        "description": f"PSI Villigen position: {title}",
                        "source": "PSI Career Portal",
                    })
    except Exception as e:
        print(f"  [!] PSI scrape warning: {e}")

    print(f"  -> Found {len(results)} listings across Eawag, Empa & PSI.")
    return results


def fetch_eth_spinoff_ecosystem(scan_spinoff_table: bool = True) -> List[Dict]:
    """
    Scans:
    1) Bio-Technopark Schlieren Job Board (https://www.bio-technopark.ch/en/jobs-englisch/)
    2) JoinUp ETH Entrepreneur Club Startup Portal (https://joinup.ch/)
    3) Official ETH Spin-Off Directory Table (https://entrepreneurship.ethz.ch/.../uebersicht-eth-spin-offs.html)
       filtering specifically for D-CHAB (Chemistry), D-MATL (Materials), D-BSSE, D-BAUG, D-USYS.
    """
    print("[3/6] Scanning ETH Spin-Off Directory, JoinUp.ch & Bio-Technopark Schlieren...")
    results = []

    # A. Bio-Technopark Schlieren-Zürich
    btp_url = "https://www.bio-technopark.ch/en/jobs-englisch/"
    try:
        r = requests.get(btp_url, headers=HEADERS, timeout=10)
        if r.ok:
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.find_all("a", href=True):
                text = a.get_text(" ", strip=True)
                href = a["href"]
                if POSITIVE_ROLE_KEYWORDS.search(text) and len(text) > 10:
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
            r = requests.get(ETH_SPINOFF_TABLE_URL, headers=HEADERS, timeout=12)
            if r.ok:
                soup = BeautifulSoup(r.text, "lxml")
                spinoffs_to_check = []
                for tr in soup.find_all("tr"):
                    tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                    if len(tds) >= 5:
                        name, _, year, _, dept = tds[0], tds[1], tds[2], tds[3], tds[4]
                        link_tag = tr.find("a", href=True)
                        if dept in ETH_TARGET_DEPTS and link_tag and link_tag["href"].startswith("http"):
                            spinoffs_to_check.append((name, dept, link_tag["href"]))

                # Probe the newest 25 chemistry/materials/env spin-offs for open career links
                for name, dept, base_url in spinoffs_to_check[:25]:
                    for suffix in ["/careers", "/jobs", "/career", ""]:
                        target_url = base_url.rstrip("/") + suffix
                        try:
                            sr = requests.get(target_url, headers=HEADERS, timeout=4)
                            if sr.ok and sr.status_code == 200:
                                ssoup = BeautifulSoup(sr.text, "lxml")
                                for a in ssoup.find_all("a", href=True):
                                    t = a.get_text(" ", strip=True)
                                    if 10 < len(t) < 95 and POSITIVE_ROLE_KEYWORDS.search(t) and not NEGATIVE_ROLE_KEYWORDS.search(t):
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


def fetch_workday_apis() -> List[Dict]:
    """Queries hidden Workday JSON endpoints directly for Givaudan, Lonza, Novartis, Roche, Takeda."""
    print("[4/6] Querying Workday Direct JSON APIs (Givaudan, Lonza, Novartis, Roche, Takeda)...")
    results = []
    wd_headers = {
        **HEADERS,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    for target in WORKDAY_TARGETS:
        for term in target["search_terms"]:
            payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": term}
            try:
                r = requests.post(target["api_url"], headers=wd_headers, json=payload, timeout=8)
                if r.ok:
                    data = r.json()
                    for post in data.get("jobPostings", []):
                        title = post.get("title", "")
                        loc = post.get("locationsText", target["default_location"])
                        ext_path = post.get("externalPath", "")
                        if not title or not ext_path:
                            continue
                        # Filter to Swiss locations
                        if any(k in loc.lower() for k in ["switzerland", "schweiz", "zurich", "zürich", "kemptthal", "basel", "stein", "schaffhausen", "rotkreuz", "visp"]):
                            job_url = f"{target['site_url'].rstrip('/')}{ext_path}"
                            results.append({
                                "title": title,
                                "company": target["company"],
                                "location": loc,
                                "url": job_url,
                                "description": f"{target['company']} role ({loc}): {title} - {post.get('bulletFields', '')}",
                                "source": "Workday Direct API",
                            })
            except Exception:
                continue
    print(f"  -> Retrieved {len(results)} Swiss listings from Workday APIs.")
    return results


def fetch_curated_career_pages() -> List[Dict]:
    """Polls the curated list of 15 local Cleantech/Biotech/Chemistry company career pages."""
    print("[5/6] Polling Curated Local Watchlist (Oxyle, Climeworks, Synhelion, SpiroChem, Philochem, Sika...)...")
    results = []
    for item in DIRECT_CAREER_PAGES:
        try:
            r = requests.get(item["url"], headers=HEADERS, timeout=8)
            if not r.ok:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.find_all("a", href=True):
                text = a.get_text(" ", strip=True)
                href = a["href"]
                if 8 < len(text) < 100 and POSITIVE_ROLE_KEYWORDS.search(text) and not NEGATIVE_ROLE_KEYWORDS.search(text):
                    # Skip generic nav links
                    if text.lower() in {"careers", "jobs", "open positions", "offene stellen", "read more", "apply now"}:
                        continue
                    results.append({
                        "title": text,
                        "company": item["company"],
                        "location": item["location"],
                        "url": urllib.parse.urljoin(item["url"], href),
                        "description": f"Direct career listing at {item['company']} ({item['location']}): {text}",
                        "source": "Curated Watchlist",
                    })
        except Exception:
            continue
    print(f"  -> Found {len(results)} candidate links on curated career pages.")
    return results


# =====================================================================
# 5. INTERACTIVE HTML DASHBOARD GENERATOR
# =====================================================================

def generate_html_dashboard(conn: sqlite3.Connection):
    """Generates a self-contained, modern HTML dashboard with instant filtering & local status memory."""
    df = pd.read_sql_query(
        """
        SELECT job_hash, title, company, location, url, source, commute_mins, commute_mode,
               match_score, role_category, degree_fit, language_req, summary, date_found
        FROM jobs
        WHERE is_relevant = 1 AND commute_mins <= ?
        ORDER BY date_found DESC, match_score DESC, commute_mins ASC
        """,
        conn,
        params=(MAX_COMMUTE_MINS + 5,),
    )

    rows_html = ""
    for _, r in df.iterrows():
        score = int(r["match_score"])
        badge_cls = "score-high" if score >= 8 else ("score-med" if score >= 7 else "score-low")
        commute_cls = "commute-fast" if r["commute_mins"] <= 25 else ("commute-mid" if r["commute_mins"] <= 45 else "commute-far")
        jid = r["job_hash"][:12]

        rows_html += f"""
        <tr data-id="{jid}" data-category="{r['role_category']}" data-score="{score}" data-commute="{r['commute_mins']}">
            <td><span class="badge {badge_cls}">{score}/10</span></td>
            <td>
                <a href="{r['url']}" target="_blank" rel="noopener" class="job-title">{r['title']}</a>
                <div class="job-summary">{r['summary']}</div>
            </td>
            <td><strong>{r['company']}</strong><br><small class="muted">{r['source']}</small></td>
            <td><span class="badge {commute_cls}">{r['location']} (~{r['commute_mins']}m {r['commute_mode']})</span></td>
            <td><span class="tag">{r['role_category']}</span></td>
            <td><span class="tag">{r['degree_fit']}</span><br><small>{r['language_req']}</small></td>
            <td>{r['date_found']}</td>
            <td>
                <button class="btn-action" onclick="toggleApplied('{jid}')">Applied</button>
                <button class="btn-hide" onclick="hideRow('{jid}')">✕</button>
            </td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Zurich Chemistry & Cleantech Job Radar</title>
<style>
    :root {{ --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --muted: #94a3b8; --accent: #38bdf8; --border: #334155; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 16px; }}
    h1 {{ margin: 0; font-size: 1.5rem; }}
    .controls {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; background: var(--card); padding: 14px; border-radius: 10px; border: 1px solid var(--border); }}
    input, select, button {{ background: #0f172a; color: var(--text); border: 1px solid var(--border); padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 10px; overflow: hidden; }}
    th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; }}
    th {{ background: #0f172a; color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    tr:hover {{ background: rgba(56, 189, 248, 0.06); }}
    tr.applied {{ background: rgba(34, 197, 94, 0.12) !important; }}
    .job-title {{ color: var(--accent); font-weight: 600; text-decoration: none; font-size: 1rem; }}
    .job-title:hover {{ text-decoration: underline; }}
    .job-summary {{ color: var(--muted); font-size: 0.84rem; margin-top: 4px; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 6px; font-weight: 600; font-size: 0.8rem; }}
    .score-high {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}
    .score-med {{ background: rgba(250, 204, 21, 0.2); color: #facc15; }}
    .score-low {{ background: rgba(148, 163, 184, 0.2); color: #cbd5e1; }}
    .commute-fast {{ background: rgba(34, 197, 94, 0.15); color: #86efac; }}
    .commute-mid {{ background: rgba(56, 189, 248, 0.15); color: #7dd3fc; }}
    .commute-far {{ background: rgba(249, 115, 22, 0.15); color: #fdba74; }}
    .tag {{ background: #334155; padding: 3px 7px; border-radius: 4px; font-size: 0.78rem; }}
    .muted {{ color: var(--muted); }}
    .btn-action {{ cursor: pointer; background: #1e3a8a; border-color: #1d4ed8; }}
    .btn-hide {{ cursor: pointer; color: #f87171; }}
</style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🧪 Zurich Chemistry & Cleantech Job Radar</h1>
            <small class="muted">Origin: {HOME_ORIGIN} (Max ~{MAX_COMMUTE_MINS}m) | Profile: MSc Organic Chemistry + 3.5y R&D (ETH / Oxyle) | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</small>
        </div>
        <div><strong>{len(df)}</strong> Matching Roles</div>
    </div>

    <div class="controls">
        <input type="text" id="searchInput" placeholder="Filter by title, company, location, PFAS, HPLC..." oninput="filterTable()" style="flex:1;">
        <select id="catFilter" onchange="filterTable()">
            <option value="">All Categories</option>
            <option value="R&D Lab">R&D Lab</option>
            <option value="Cleantech">Cleantech</option>
            <option value="Analytical">Analytical</option>
            <option value="Pharma QA/Reg">Pharma QA/Reg</option>
            <option value="Consulting/App">Consulting/App</option>
        </select>
        <select id="commuteFilter" onchange="filterTable()">
            <option value="999">All Commutes (<= {MAX_COMMUTE_MINS}m)</option>
            <option value="25"><= 25 mins (Zurich / Schlieren / Dübendorf / Winterthur)</option>
            <option value="45"><= 45 mins (+ Zug / Baden / Schaffhausen / Stein)</option>
        </select>
        <button onclick="resetHidden()">Restore Hidden Rows</button>
    </div>

    <table id="jobsTable">
        <thead>
            <tr>
                <th>Fit</th>
                <th>Role & Match Summary</th>
                <th>Company</th>
                <th>Commute from {HOME_ORIGIN}</th>
                <th>Category</th>
                <th>Degree & Language</th>
                <th>Found</th>
                <th>Track</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

<script>
    function loadState() {{
        const hidden = JSON.parse(localStorage.getItem('hiddenJobs') || '[]');
        const applied = JSON.parse(localStorage.getItem('appliedJobs') || '[]');
        document.querySelectorAll('#jobsTable tbody tr').forEach(tr => {{
            const id = tr.dataset.id;
            if (hidden.includes(id)) tr.style.display = 'none';
            if (applied.includes(id)) tr.classList.add('applied');
        }});
    }}
    function toggleApplied(id) {{
        let applied = JSON.parse(localStorage.getItem('appliedJobs') || '[]');
        const tr = document.querySelector(`tr[data-id="${{id}}"]`);
        if (applied.includes(id)) {{
            applied = applied.filter(x => x !== id);
            tr.classList.remove('applied');
        }} else {{
            applied.push(id);
            tr.classList.add('applied');
        }}
        localStorage.setItem('appliedJobs', JSON.stringify(applied));
    }}
    function hideRow(id) {{
        let hidden = JSON.parse(localStorage.getItem('hiddenJobs') || '[]');
        if (!hidden.includes(id)) hidden.push(id);
        localStorage.setItem('hiddenJobs', JSON.stringify(hidden));
        document.querySelector(`tr[data-id="${{id}}"]`).style.display = 'none';
    }}
    function resetHidden() {{
        localStorage.removeItem('hiddenJobs');
        location.reload();
    }}
    function filterTable() {{
        const q = document.getElementById('searchInput').value.toLowerCase();
        const cat = document.getElementById('catFilter').value;
        const maxC = parseInt(document.getElementById('commuteFilter').value);
        const hidden = JSON.parse(localStorage.getItem('hiddenJobs') || '[]');

        document.querySelectorAll('#jobsTable tbody tr').forEach(tr => {{
            if (hidden.includes(tr.dataset.id)) return;
            const text = tr.innerText.toLowerCase();
            const matchQ = text.includes(q);
            const matchCat = !cat || tr.dataset.category === cat;
            const matchC = parseInt(tr.dataset.commute) <= maxC;
            tr.style.display = (matchQ && matchCat && matchC) ? '' : 'none';
        }});
    }}
    loadState();
</script>
</body>
</html>"""

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n[DONE] Clean interactive dashboard written to: {REPORT_PATH}")


# =====================================================================
# 6. MAIN ORCHESTRATOR
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Zurich Chemistry & Cleantech Job Radar")
    parser.add_argument("--hours", type=int, default=72, help="Lookback hours for JobSpy (default: 72)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open HTML dashboard")
    parser.add_argument("--skip-spinoff-crawl", action="store_true", help="Skip deep crawl of ETH spin-off table")
    parser.add_argument("--skip-jobspy", action="store_true", help="Skip aggregator scraping (Indeed/LinkedIn/Google)")
    parser.add_argument(
        "--jobspy-sites",
        nargs="+",
        default=["indeed"],
        help="Aggregator sites to scan (default: indeed; options: indeed, linkedin, google). Note: LinkedIn requires residential proxies.",
    )
    parser.add_argument("--rescore", action="store_true", help="Re-score all existing jobs in chem_jobs.db using Gemini 2.5 Flash")
    parser.add_argument("--rescore-limit", type=int, default=None, help="Limit number of jobs to rescore (e.g. --rescore-limit 10)")
    args = parser.parse_args()

    conn = init_db()
    client = genai.Client(api_key=GEMINI_API_KEY) if (HAS_GENAI and GEMINI_API_KEY) else None
    if client:
        print("[INFO] Gemini 2.5 Flash semantic scoring ENABLED.")
    else:
        print("[INFO] Running with built-in Chemistry/Cleantech heuristic scorer (set GEMINI_API_KEY to enable LLM scoring).")

    if args.rescore:
        if not client:
            print("[ERROR] Cannot run --rescore: GEMINI_API_KEY is not set or google-genai is not installed.")
            return
        rescore_database_jobs(conn, client, limit=args.rescore_limit)
        generate_html_dashboard(conn)
        print(f"[+] Re-generated {REPORT_PATH}")
        if not args.no_browser:
            webbrowser.open(f"file://{REPORT_PATH}")
        return

    raw_jobs = []
    if not args.skip_jobspy:
        raw_jobs.extend(fetch_jobspy_aggregators(hours_old=args.hours, sites=args.jobspy_sites))
    else:
        print("[1/6] Skipping JobSpy aggregators (--skip-jobspy passed).")
    raw_jobs.extend(fetch_eawag_empa_psi())
    raw_jobs.extend(fetch_eth_spinoff_ecosystem(scan_spinoff_table=not args.skip_spinoff_crawl))
    raw_jobs.extend(fetch_workday_apis())
    raw_jobs.extend(fetch_curated_career_pages())

    print(f"[6/6] Deduplicating, checking SBB commutes from {HOME_ORIGIN}, and scoring {len(raw_jobs)} listings...")
    cur = conn.cursor()
    new_relevant_count = 0

    for item in raw_jobs:
        title = item.get("title", "").strip()
        company = item.get("company", "").strip()
        location = item.get("location", "Zurich").strip()
        url = item.get("url", "").strip()
        desc = item.get("description", "")
        source = item.get("source", "")

        if not title or not url:
            continue

        jhash = make_job_hash(company, title)
        cur.execute("SELECT 1 FROM jobs WHERE job_hash = ?", (jhash,))
        if cur.fetchone():
            continue

        commute_mins, commute_mode = get_commute_info(conn, location)
        if commute_mins > (MAX_COMMUTE_MINS + 5) and "basel" not in location.lower():
            continue

        ev = evaluate_job(client, title, company, location, desc, source)
        cur.execute(
            """INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                jhash, title, company, location, url, source,
                commute_mins, commute_mode, ev.match_score,
                1 if ev.is_relevant else 0, ev.role_category,
                ev.degree_fit, ev.language_req, ev.one_line_summary,
                datetime.now().strftime("%Y-%m-%d"),
            ),
        )
        conn.commit()
        if ev.is_relevant:
            new_relevant_count += 1

    print(f"  -> Added {new_relevant_count} new relevant positions within ~{MAX_COMMUTE_MINS}m of {HOME_ORIGIN}.")
    generate_html_dashboard(conn)

    if not args.no_browser:
        webbrowser.open(f"file://{REPORT_PATH}")


if __name__ == "__main__":
    main()