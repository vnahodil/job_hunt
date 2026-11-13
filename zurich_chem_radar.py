#!/usr/bin/env python3
"""
Zurich Chemistry & Cleantech Job Radar — CLI Entry Point

Tailored for: MSc Organic Chemistry + 2y PhD Research + 6m ETH + 1y Oxyle (Cleantech)
Commute origin: Glattbrugg / Zurich Area (<= 60 min transit or car)

Configuration lives in config/targets.yaml.
Business logic lives in the src/ package.
"""

import argparse
import webbrowser
from datetime import datetime

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

from src.config import cfg
from src.database import init_db, make_job_hash
from src.commute import get_commute_info
from src.evaluator import evaluate_job, rescore_database_jobs
from src.dashboard import generate_html_dashboard
from src.scrapers.jobspy_aggregator import fetch_jobspy_aggregators
from src.scrapers.institutes import fetch_eawag_empa_psi
from src.scrapers.eth_spinoffs import fetch_eth_spinoff_ecosystem
from src.scrapers.workday import fetch_workday_apis
from src.scrapers.career_pages import fetch_curated_career_pages
from src.scrapers.jobs_ch import fetch_jobs_ch
from src.scrapers.myscience import fetch_myscience_jobs
from src.scrapers.description_fetcher import fetch_job_description_body


def main():
    parser = argparse.ArgumentParser(description="Zurich Chemistry & Cleantech Job Radar")
    parser.add_argument("--hours", type=int, default=72, help="Lookback hours for JobSpy (default: 72)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open HTML dashboard")
    parser.add_argument("--skip-spinoff-crawl", action="store_true", help="Skip deep crawl of ETH spin-off table")
    parser.add_argument("--skip-jobspy", action="store_true", help="Skip aggregator scraping (Indeed/LinkedIn/Google)")
    parser.add_argument("--skip-jobs-ch", action="store_true", help="Skip jobs.ch REST API scan")
    parser.add_argument("--skip-myscience", action="store_true", help="Skip myScience.ch science portal scan")
    parser.add_argument(
        "--jobspy-sites",
        nargs="+",
        default=["indeed", "linkedin"],
        help="Aggregator sites to scan (default: indeed, linkedin; options: indeed, linkedin, google).",
    )
    parser.add_argument("--rescore", action="store_true", help="Re-score all existing jobs using Gemini 2.5 Flash")
    parser.add_argument("--rescore-limit", type=int, default=None, help="Limit number of jobs to rescore")
    args = parser.parse_args()

    conn = init_db()
    client = genai.Client(api_key=cfg.GEMINI_API_KEY) if (HAS_GENAI and cfg.GEMINI_API_KEY) else None
    if client:
        print("[INFO] Gemini Flash semantic scoring ENABLED (gemini-3.8-flash / 3.5-flash).")
    else:
        print("[INFO] Running with built-in Chemistry/Cleantech heuristic scorer (set GEMINI_API_KEY to enable LLM scoring).")

    # --rescore mode: re-evaluate existing DB rows via Gemini, then regenerate dashboard
    if args.rescore:
        if not client:
            print("[ERROR] Cannot run --rescore: GEMINI_API_KEY is not set or google-genai is not installed.")
            return
        rescore_database_jobs(conn, client, limit=args.rescore_limit)
        generate_html_dashboard(conn)
        print(f"[+] Re-generated {cfg.REPORT_PATH}")
        if not args.no_browser:
            webbrowser.open(f"file://{cfg.REPORT_PATH}")
        return

    # Normal scraping pipeline
    raw_jobs = []
    if not args.skip_jobspy:
        raw_jobs.extend(fetch_jobspy_aggregators(hours_old=args.hours, sites=args.jobspy_sites))
    else:
        print("[1/6] Skipping JobSpy aggregators (--skip-jobspy passed).")
    raw_jobs.extend(fetch_eawag_empa_psi())
    raw_jobs.extend(fetch_eth_spinoff_ecosystem(scan_spinoff_table=not args.skip_spinoff_crawl))
    if not args.skip_myscience:
        raw_jobs.extend(fetch_myscience_jobs())
    else:
        print("[*] Skipping myScience.ch (--skip-myscience passed).")
    raw_jobs.extend(fetch_workday_apis())
    raw_jobs.extend(fetch_curated_career_pages())
    if not args.skip_jobs_ch:
        raw_jobs.extend(fetch_jobs_ch())
    else:
        print("[*] Skipping jobs.ch API (--skip-jobs-ch passed).")

    print(f"[6/6] Deduplicating, checking SBB commutes from {cfg.HOME_ORIGIN}, and scoring {len(raw_jobs)} listings...")
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
        if commute_mins > (cfg.MAX_COMMUTE_MINS + 5) and "basel" not in location.lower():
            continue

        # Deep description fetching if text is brief
        if len(desc.strip()) < 80 and url:
            fetched_body = fetch_job_description_body(url)
            if fetched_body and len(fetched_body) > len(desc):
                desc = fetched_body

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

    print(f"  -> Added {new_relevant_count} new relevant positions within ~{cfg.MAX_COMMUTE_MINS}m of {cfg.HOME_ORIGIN}.")
    generate_html_dashboard(conn)

    if not args.no_browser:
        webbrowser.open(f"file://{cfg.REPORT_PATH}")


if __name__ == "__main__":
    main()
