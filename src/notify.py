"""
Email Notification Service for Zurich Chemistry & Cleantech Job Radar.

Sends a daily morning HTML digest of newly discovered high-match positions
(match_score >= 7) via Gmail SMTP to configured recipients.
"""

import smtplib
import sqlite3
from datetime import datetime
from email.message import EmailMessage
from typing import Dict, List, Optional

from src.config import cfg


def _build_html_body(jobs: List[Dict], date_str: str) -> str:
    """Builds a beautiful, responsive HTML email body."""
    cards_html = ""
    for j in jobs:
        score = int(j.get("match_score", 0))
        score_bg = "#15803d" if score >= 9 else ("#16a34a" if score >= 8 else "#ca8a04")
        commute_mins = j.get("commute_mins", 0)
        commute_mode = j.get("commute_mode", "transit")
        title = j.get("title", "")
        company = j.get("company", "")
        location = j.get("location", "")
        url = j.get("url", "#")
        summary = j.get("summary", "")
        category = j.get("role_category", "R&D")
        degree = j.get("degree_fit", "MSc / PhD")

        cards_html += f"""
        <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div style="flex: 1;">
                    <a href="{url}" target="_blank" style="color: #0284c7; font-size: 16px; font-weight: bold; text-decoration: none;">
                        {title}
                    </a>
                    <div style="color: #334155; font-size: 14px; margin-top: 2px;">
                        <strong>{company}</strong> &bull; <span style="color: #64748b;">{location} (~{commute_mins}m {commute_mode})</span>
                    </div>
                </div>
                <div style="background-color: {score_bg}; color: #ffffff; font-weight: bold; font-size: 13px; padding: 4px 8px; border-radius: 6px; white-space: nowrap; margin-left: 12px;">
                    {score}/10
                </div>
            </div>
            <div style="margin: 8px 0;">
                <span style="background-color: #f1f5f9; color: #475569; font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 500;">{category}</span>
                <span style="background-color: #f1f5f9; color: #475569; font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 500; margin-left: 4px;">{degree}</span>
            </div>
            <div style="color: #475569; font-size: 13px; line-height: 1.4; font-style: italic; background-color: #f8fafc; padding: 8px 10px; border-radius: 4px; border-left: 3px solid #0284c7;">
                &ldquo;{summary}&rdquo;
            </div>
            <div style="margin-top: 10px; text-align: right;">
                <a href="{url}" target="_blank" style="color: #0284c7; font-size: 12px; font-weight: 600; text-decoration: none;">
                    View Vacancy &rarr;
                </a>
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; color: #1e293b;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 24px; color: #ffffff;">
            <div style="font-size: 20px; font-weight: bold; margin-bottom: 4px;">
                🧪 Zurich Chemistry & Cleantech Job Radar
            </div>
            <div style="color: #94a3b8; font-size: 13px;">
                Daily Digest &bull; {date_str} &bull; Origin: {cfg.HOME_ORIGIN} (&le; {cfg.MAX_COMMUTE_MINS}m)
            </div>
        </div>

        <!-- Hero text -->
        <div style="padding: 20px 24px 10px 24px; background-color: #ffffff;">
            <p style="margin: 0; font-size: 15px; color: #334155; line-height: 1.5;">
                Good morning! <strong>{len(jobs)} high-match roles (&ge; {cfg.MIN_NOTIFY_SCORE}/10)</strong> were discovered today matching her organic chemistry & cleantech profile:
            </p>
        </div>

        <!-- Job Cards -->
        <div style="padding: 10px 24px 20px 24px;">
            {cards_html}
        </div>

        <!-- CTA Button -->
        <div style="padding: 0 24px 28px 24px; text-align: center;">
            <a href="{cfg.DASHBOARD_URL}" target="_blank" style="display: inline-block; background-color: #0284c7; color: #ffffff; font-weight: 600; font-size: 14px; padding: 12px 24px; border-radius: 8px; text-decoration: none; box-shadow: 0 2px 4px rgba(2,132,199,0.3);">
                Open Full Interactive Radar (300+ Roles & CV Prompts) &rarr;
            </a>
            <div style="margin-top: 10px; font-size: 12px; color: #94a3b8;">
                Includes commute filters, live search, and 1-click tailored cover letter prompts.
            </div>
        </div>

        <!-- Footer -->
        <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 24px; text-align: center; color: #94a3b8; font-size: 11px;">
            Profile: MSc Organic Chemistry + ETH Zurich & Oxyle R&D (Glattbrugg) &bull; Automated via macOS launchd
        </div>
    </div>
</body>
</html>"""
    return html


def _build_text_body(jobs: List[Dict], date_str: str) -> str:
    """Builds a fallback plain-text email body."""
    lines = [
        f"🧪 Zurich Chemistry & Cleantech Job Radar - Daily Digest ({date_str})",
        f"Origin: {cfg.HOME_ORIGIN} (Max ~{cfg.MAX_COMMUTE_MINS}m)",
        "",
        f"Good morning! {len(jobs)} high-match roles (>= {cfg.MIN_NOTIFY_SCORE}/10) were discovered today:",
        "-" * 50,
    ]
    for j in jobs:
        score = j.get("match_score", 0)
        title = j.get("title", "")
        company = j.get("company", "")
        location = j.get("location", "")
        mins = j.get("commute_mins", 0)
        mode = j.get("commute_mode", "transit")
        url = j.get("url", "")
        summary = j.get("summary", "")
        category = j.get("role_category", "R&D")

        lines.append(f"\n• [{score}/10] {title} @ {company}")
        lines.append(f"  Location: {location} (~{mins}m {mode}) | Category: {category}")
        lines.append(f"  Match: \"{summary}\"")
        lines.append(f"  Link: {url}")

    lines.append("\n" + "-" * 50)
    lines.append(f"Open Full Interactive Radar: {cfg.DASHBOARD_URL}")
    return "\n".join(lines)


def fetch_today_top_jobs(conn: sqlite3.Connection, min_score: int = None, date_str: str = None) -> List[Dict]:
    """Fetches high-match jobs added on date_str (default: today)."""
    if min_score is None:
        min_score = cfg.MIN_NOTIFY_SCORE
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    cur = conn.cursor()
    cur.execute(
        """
        SELECT title, company, location, url, commute_mins, commute_mode,
               match_score, role_category, degree_fit, summary
        FROM jobs
        WHERE date_found = ? AND match_score >= ? AND is_relevant = 1
        ORDER BY match_score DESC, commute_mins ASC
        """,
        (date_str, min_score),
    )
    rows = cur.fetchall()
    return [
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
        for r in rows
    ]


def send_daily_email_digest(
    jobs: Optional[List[Dict]] = None,
    conn: Optional[sqlite3.Connection] = None,
    force: bool = False,
) -> bool:
    """
    Sends the daily email summary.
    If jobs is None, queries SQLite for today's new high-scoring jobs.
    Returns True if sent or skipped normally, False if an error occurred.
    """
    if not cfg.NOTIFY_ENABLED and not force:
        print("[notify] Email notifications are disabled in configuration.")
        return True

    today_str = datetime.now().strftime("%Y-%m-%d")

    if jobs is None:
        if conn is None:
            conn = sqlite3.connect(cfg.DB_PATH)
        jobs = fetch_today_top_jobs(conn, min_score=cfg.MIN_NOTIFY_SCORE, date_str=today_str)

    if not jobs:
        print(f"[notify] No new roles with match_score >= {cfg.MIN_NOTIFY_SCORE} found today ({today_str}). Skipping email.")
        return True

    if not cfg.SMTP_USER or not cfg.SMTP_PASS:
        print("\n[notify WARNING] Email credentials not configured:")
        print("  -> Set SMTP_USER and SMTP_PASS in .env or environment to enable email delivery.")
        print(f"  -> Generated digest ready with {len(jobs)} high-fit roles.")
        return False

    recipients = cfg.NOTIFY_RECIPIENTS or [cfg.SMTP_USER]

    # Build Email Message
    msg = EmailMessage()
    msg["Subject"] = f"🧪 [Zurich Chem Radar] {len(jobs)} Top Roles Discovered Today ({today_str})"
    msg["From"] = f"Zurich Chem Radar <{cfg.SMTP_USER}>"
    msg["To"] = ", ".join(recipients)

    text_content = _build_text_body(jobs, today_str)
    html_content = _build_html_body(jobs, today_str)

    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype="html")

    try:
        print(f"[notify] Connecting to {cfg.SMTP_HOST}:{cfg.SMTP_PORT} as {cfg.SMTP_USER}...")
        if cfg.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(cfg.SMTP_USER, cfg.SMTP_PASS)
        server.send_message(msg)
        server.quit()
        print(f"[notify SUCCESS] Sent daily digest ({len(jobs)} roles) to {', '.join(recipients)}!")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"\n[notify ERROR] Gmail SMTP Authentication failed: {e}")
        print("Tip: If using Gmail with 2-Factor Authentication, you must use a 16-character 'App Password'.")
        print("Generate one here: https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        print(f"[notify ERROR] Failed to send email: {e}")
        return False
