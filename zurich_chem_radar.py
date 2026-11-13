#!/usr/bin/env python3
"""
Zurich Chemistry & Cleantech Job Radar — CLI Entry Point

Tailored for: MSc Organic Chemistry + 2y PhD Research + 6m ETH + 1y Oxyle (Cleantech)
Commute origin: Glattbrugg / Zurich Area (<= 60 min transit or car)

Configuration lives in config/targets.yaml.
Business logic lives in the src/ package.
"""

import argparse
import os
import subprocess
import webbrowser
from datetime import datetime

try:
    from google import genai
    from google.genai import types
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
from src.scrapers.lifesciencework import fetch_lifesciencework_jobs
from src.scrapers.startup_apis import fetch_startup_api_jobs
from src.scrapers.scs import fetch_scs_jobs
from src.scrapers.description_fetcher import fetch_job_description_body
from src.notify import send_daily_email_digest


def publish_to_github(commit_msg: str = None) -> bool:
    """Stages updated dashboard/index files and commits & pushes to GitHub Pages."""
    if not commit_msg:
        commit_msg = f"Update dashboard ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    try:
        files_to_add = [
            str(cfg.REPORT_PATH),
            str(cfg.INDEX_PATH),
            str(cfg.DOCS_INDEX_PATH),
            str(cfg.PROJECT_ROOT / ".nojekyll"),
            str(cfg.DOCS_DIR / ".nojekyll"),
            str(cfg.PROJECT_ROOT / ".gitignore"),
            str(cfg.DB_PATH),
            str(cfg.PROJECT_ROOT / "src"),
            str(cfg.PROJECT_ROOT / "config"),
            str(cfg.PROJECT_ROOT / "zurich_chem_radar.py"),
            str(cfg.PROJECT_ROOT / "ROADMAP.md"),
            str(cfg.PROJECT_ROOT / "README.md"),
        ]
        existing = [f for f in files_to_add if os.path.exists(f)]
        subprocess.run(["git", "add"] + existing, check=True, cwd=str(cfg.PROJECT_ROOT))

        diff_res = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(cfg.PROJECT_ROOT))
        if diff_res.returncode == 0:
            print("[publish] No changes to commit (everything up-to-date).")
            return True

        subprocess.run(["git", "commit", "-m", commit_msg], check=True, cwd=str(cfg.PROJECT_ROOT))
        subprocess.run(["git", "push", "origin", "main"], check=True, cwd=str(cfg.PROJECT_ROOT))
        print("[publish] Successfully pushed updated dashboard to GitHub Pages!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[publish ERROR] Git command failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Zurich Chemistry & Cleantech Job Radar")
    parser.add_argument("--hours", type=int, default=72, help="Lookback hours for JobSpy (default: 72)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open HTML dashboard")
    parser.add_argument("--skip-spinoff-crawl", action="store_true", help="Skip deep crawl of ETH spin-off table")
    parser.add_argument("--skip-jobspy", action="store_true", help="Skip aggregator scraping (Indeed/LinkedIn/Google)")
    parser.add_argument("--skip-jobs-ch", action="store_true", help="Skip jobs.ch REST API scan")
    parser.add_argument("--skip-myscience", action="store_true", help="Skip myScience.ch science portal scan")
    parser.add_argument("--skip-lifesciencework", action="store_true", help="Skip Life Science Work portal scan")
    parser.add_argument("--skip-startup-apis", action="store_true", help="Skip direct startup JSON APIs scan")
    parser.add_argument("--skip-scs", action="store_true", help="Skip Swiss Chemical Society portal scan")
    parser.add_argument(
        "--jobspy-sites",
        nargs="+",
        default=["indeed", "linkedin"],
        help="Aggregator sites to scan (default: indeed, linkedin; options: indeed, linkedin, google).",
    )
    parser.add_argument("--rescore", action="store_true", help="Re-score all existing jobs using Gemini 2.5 Flash")
    parser.add_argument("--rescore-limit", type=int, default=None, help="Limit number of jobs to rescore")
    parser.add_argument("--dashboard-only", action="store_true", help="Re-generate dashboard and index.html from DB without scraping")
    parser.add_argument("--publish", action="store_true", help="Auto-commit and push updated dashboard/index to GitHub Pages")
    parser.add_argument("--notify", action="store_true", help="Send daily email digest to configured recipients")
    parser.add_argument("--test-email", action="store_true", help="Send a test email with recent top jobs and exit")
    args = parser.parse_args()

    conn = init_db()
    client = (
        genai.Client(
            api_key=cfg.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=15000),
        )
        if (HAS_GENAI and cfg.GEMINI_API_KEY)
        else None
    )
    if client:
        print("[INFO] Gemini Flash semantic scoring ENABLED (gemini-3.8-flash / 3.5-flash).")
    else:
        print("[INFO] Running with built-in Chemistry/Cleantech heuristic scorer (set GEMINI_API_KEY to enable LLM scoring).")

    # --test-email mode: test email connectivity with top high-match jobs
    if args.test_email:
        print("[*] Preparing test email digest with top high-match jobs...")
        cur = conn.cursor()
        cur.execute(
            """
            SELECT title, company, location, url, commute_mins, commute_mode,
                   match_score, role_category, degree_fit, summary
            FROM jobs
            WHERE match_score >= 8 AND is_relevant = 1
            ORDER BY match_score DESC, commute_mins ASC
            LIMIT 4
            """
        )
        sample_jobs = [
            {
                "title": r[0],
                "company": r[1],
                "location": r[2],
                "url": r[3],
                "commute_mins": r[4],
                "commute_mode": r[5],
                "match_score": r[6],
                "role_category": r[7],
                "degree_fit": r[8],
                "summary": r[9],
            }
            for r in cur.fetchall()
        ]
        send_daily_email_digest(jobs=sample_jobs, conn=conn, force=True)
        return

    # --dashboard-only mode: re-render HTML files from DB without scraping
    if args.dashboard_only:
        generate_html_dashboard(conn)
        if args.publish:
            publish_to_github()
        if not args.no_browser:
            webbrowser.open(f"file://{cfg.REPORT_PATH}")
        return

    # --rescore mode: re-evaluate existing DB rows via Gemini, then regenerate dashboard
    if args.rescore:
        if not client:
            print("[ERROR] Cannot run --rescore: GEMINI_API_KEY is not set or google-genai is not installed.")
            return
        rescore_database_jobs(conn, client, limit=args.rescore_limit)
        generate_html_dashboard(conn)
        if args.publish:
            publish_to_github()
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
    if not args.skip_startup_apis:
        raw_jobs.extend(fetch_startup_api_jobs())
    else:
        print("[*] Skipping direct startup JSON APIs (--skip-startup-apis passed).")
    if not args.skip_lifesciencework:
        raw_jobs.extend(fetch_lifesciencework_jobs())
    else:
        print("[*] Skipping Life Science Work portal (--skip-lifesciencework passed).")
    if not args.skip_scs:
        raw_jobs.extend(fetch_scs_jobs())
    else:
        print("[*] Skipping Swiss Chemical Society (--skip-scs passed).")
    raw_jobs.extend(fetch_curated_career_pages())
    if not args.skip_jobs_ch:
        raw_jobs.extend(fetch_jobs_ch())
    else:
        print("[*] Skipping jobs.ch API (--skip-jobs-ch passed).")

    print(f"[*] Filtering {len(raw_jobs)} listings: checking database for duplicates and SBB commute limit...")
    cur = conn.cursor()

    already_seen_count = 0
    commute_exceeded_count = 0
    to_evaluate = []

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
            already_seen_count += 1
            continue

        commute_mins, commute_mode = get_commute_info(conn, location)
        if commute_mins > (cfg.MAX_COMMUTE_MINS + 5) and "basel" not in location.lower():
            commute_exceeded_count += 1
            continue

        to_evaluate.append({
            "item": item,
            "jhash": jhash,
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "desc": desc,
            "source": source,
            "commute_mins": commute_mins,
            "commute_mode": commute_mode,
        })

    print(f"  -> {already_seen_count} already in database (skipped)")
    print(f"  -> {commute_exceeded_count} exceed ~{cfg.MAX_COMMUTE_MINS}m commute limit (skipped)")
    print(f"  -> {len(to_evaluate)} brand new candidates to evaluate with Gemini...")

    new_relevant_count = 0
    for idx, cand in enumerate(to_evaluate, 1):
        title = cand["title"]
        company = cand["company"]
        location = cand["location"]
        url = cand["url"]
        desc = cand["desc"]
        source = cand["source"]
        jhash = cand["jhash"]
        commute_mins = cand["commute_mins"]
        commute_mode = cand["commute_mode"]

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
        print(f"     [{idx}/{len(to_evaluate)}] {title[:38]} @ {company[:20]} -> {ev.match_score}/10 ({ev.role_category})")

    print(f"  -> Added {new_relevant_count} new relevant positions within ~{cfg.MAX_COMMUTE_MINS}m of {cfg.HOME_ORIGIN}.")
    generate_html_dashboard(conn)

    if args.publish:
        publish_to_github()

    if args.notify or cfg.NOTIFY_ENABLED:
        send_daily_email_digest(conn=conn)

    if not args.no_browser:
        webbrowser.open(f"file://{cfg.REPORT_PATH}")


if __name__ == "__main__":
    main()
