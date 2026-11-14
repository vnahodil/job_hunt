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
from src.dashboard import parse_summary_parts


def _build_html_body(
    display_jobs: List[Dict],
    new_today_count: int,
    overall_active_count: int,
    date_str: str,
    is_test: bool = False,
) -> str:
    """Builds a beautiful, responsive HTML email body with highlights + total count."""
    cards_html = ""
    for j in display_jobs:
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

        track_text, fit_text, gap_text = parse_summary_parts(summary)

        if fit_text or gap_text:
            analysis_html = ""
            if track_text:
                analysis_html += f"""
                <div style="font-size: 11px; color: #0284c7; font-weight: 600; margin-bottom: 6px;">
                    🎯 Track: {track_text}
                </div>
                """
            if fit_text:
                analysis_html += f"""
                <div style="background-color: #f0fdf4; border-left: 3px solid #22c55e; padding: 6px 10px; margin-bottom: 5px; border-radius: 4px; color: #166534; font-size: 12px; line-height: 1.4;">
                    <strong>✅ Fit:</strong> {fit_text}
                </div>
                """
            if gap_text:
                analysis_html += f"""
                <div style="background-color: #fef2f2; border-left: 3px solid #ef4444; padding: 6px 10px; border-radius: 4px; color: #991b1b; font-size: 12px; line-height: 1.4;">
                    <strong>⚠️ Gaps:</strong> {gap_text}
                </div>
                """
        else:
            analysis_html = f"""
            <div style="color: #475569; font-size: 13px; line-height: 1.4; background-color: #f8fafc; padding: 8px 10px; border-radius: 4px; border-left: 3px solid #0284c7;">
                {summary}
            </div>
            """

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
            {analysis_html}
            <div style="margin-top: 10px; text-align: right;">
                <a href="{url}" target="_blank" style="color: #0284c7; font-size: 12px; font-weight: 600; text-decoration: none;">
                    View Vacancy &rarr;
                </a>
            </div>
        </div>
        """

    # Banner for extra jobs if new_today_count > len(display_jobs)
    overflow_count = max(0, new_today_count - len(display_jobs))
    role_word_today = "role" if new_today_count == 1 else "roles"
    pos_word_overflow = "position" if overflow_count == 1 else "positions"
    was_were = "was" if new_today_count == 1 else "were"

    overflow_banner = ""
    if overflow_count > 0:
        overflow_banner = f"""
        <div style="background-color: #f0fdf4; border: 1px dashed #86efac; border-radius: 8px; padding: 14px; text-align: center; margin-bottom: 20px;">
            <div style="color: #166534; font-weight: 600; font-size: 14px;">
                ✨ + {overflow_count} more new matching {pos_word_overflow} discovered today!
            </div>
            <div style="color: #15803d; font-size: 12px; margin-top: 4px;">
                All {new_today_count} new discoveries and {overall_active_count} total verified radar roles are ready in your dashboard.
            </div>
        </div>
        """

    # Customize hero text
    if is_test:
        hero_text = (
            f"This is a test preview showing the <strong>top {len(display_jobs)} high-match highlights</strong> "
            f"currently in your radar (out of <strong>{overall_active_count} active matching roles</strong>):"
        )
    elif overflow_count > 0:
        hero_text = (
            f"Good morning! <strong>{new_today_count} high-match {role_word_today} (&ge; {cfg.MIN_NOTIFY_SCORE}/10)</strong> "
            f"were discovered today. Here are today's <strong>Top {len(display_jobs)} highlights</strong> based on profile fit and commute:"
        )
    else:
        hero_text = (
            f"Good morning! <strong>{new_today_count} new high-match {role_word_today} (&ge; {cfg.MIN_NOTIFY_SCORE}/10)</strong> "
            f"{was_were} discovered today matching your organic chemistry & cleantech profile:"
        )

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
                {hero_text}
            </p>
        </div>

        <!-- Job Cards -->
        <div style="padding: 10px 24px 10px 24px;">
            {cards_html}
            {overflow_banner}
        </div>

        <!-- CTA Button -->
        <div style="padding: 0 24px 28px 24px; text-align: center;">
            <a href="{cfg.DASHBOARD_URL}" target="_blank" style="display: inline-block; background-color: #0284c7; color: #ffffff; font-weight: 600; font-size: 14px; padding: 12px 24px; border-radius: 8px; text-decoration: none; box-shadow: 0 2px 4px rgba(2,132,199,0.3);">
                Open Interactive Radar ({overall_active_count} Active Roles) &rarr;
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


def _build_text_body(
    display_jobs: List[Dict],
    new_today_count: int,
    overall_active_count: int,
    date_str: str,
    is_test: bool = False,
) -> str:
    """Builds a fallback plain-text email body."""
    overflow_count = max(0, new_today_count - len(display_jobs))
    role_word_today = "role" if new_today_count == 1 else "roles"
    pos_word_overflow = "position" if overflow_count == 1 else "positions"
    was_were = "was" if new_today_count == 1 else "were"

    lines = [
        f"🧪 Zurich Chemistry & Cleantech Job Radar - Daily Digest ({date_str})",
        f"Origin: {cfg.HOME_ORIGIN} (Max ~{cfg.MAX_COMMUTE_MINS}m)",
        "",
    ]
    if is_test:
        lines.append(f"This is a test preview showing Top {len(display_jobs)} highlights (out of {overall_active_count} active matching roles):")
    elif overflow_count > 0:
        lines.append(f"Good morning! {new_today_count} high-match {role_word_today} (>= {cfg.MIN_NOTIFY_SCORE}/10) were discovered today.")
        lines.append(f"Here are today's Top {len(display_jobs)} highlights:")
    else:
        lines.append(f"Good morning! {new_today_count} new high-match {role_word_today} (>= {cfg.MIN_NOTIFY_SCORE}/10) {was_were} discovered today:")

    lines.append("-" * 50)

    for j in display_jobs:
        score = j.get("match_score", 0)
        title = j.get("title", "")
        company = j.get("company", "")
        location = j.get("location", "")
        mins = j.get("commute_mins", 0)
        mode = j.get("commute_mode", "transit")
        url = j.get("url", "")
        summary = j.get("summary", "")
        category = j.get("role_category", "R&D")

        track_text, fit_text, gap_text = parse_summary_parts(summary)

        lines.append(f"\n• [{score}/10] {title} @ {company}")
        lines.append(f"  Location: {location} (~{mins}m {mode}) | Category: {category}")
        if track_text:
            lines.append(f"  Track: {track_text}")
        if fit_text:
            lines.append(f"  Fit: {fit_text}")
        if gap_text:
            lines.append(f"  Gaps: {gap_text}")
        if not (fit_text or gap_text):
            lines.append(f"  Match: \"{summary}\"")
        lines.append(f"  Link: {url}")

    if overflow_count > 0:
        lines.append(f"\n✨ + {overflow_count} more new matching {pos_word_overflow} waiting in the dashboard!")

    lines.append("\n" + "-" * 50)
    lines.append(f"Open Full Interactive Radar ({overall_active_count} Active Roles): {cfg.DASHBOARD_URL}")
    return "\n".join(lines)


def fetch_today_top_jobs(conn: sqlite3.Connection, min_score: int = None, date_str: str = None) -> List[Dict]:
    """Fetches high-match jobs added on date_str (default: today) within commute threshold."""
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
        WHERE date_found = ? AND match_score >= ? AND is_relevant = 1 AND commute_mins <= ?
        ORDER BY match_score DESC, commute_mins ASC
        """,
        (date_str, min_score, cfg.MAX_COMMUTE_MINS + 5),
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


def fetch_overall_active_count(conn: sqlite3.Connection) -> int:
    """Returns the total number of verified roles matching active dashboard criteria."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT count(*) FROM jobs
        WHERE is_relevant = 1 AND match_score >= 6 AND commute_mins <= ?
        """,
        (cfg.MAX_COMMUTE_MINS + 5,),
    )
    row = cur.fetchone()
    return row[0] if row else 0


def send_daily_email_digest(
    jobs: Optional[List[Dict]] = None,
    conn: Optional[sqlite3.Connection] = None,
    force: bool = False,
    total_count: Optional[int] = None,
    overall_count: Optional[int] = None,
    is_test: bool = False,
) -> bool:
    """
    Sends the daily email summary.
    If jobs is None, queries SQLite for today's new high-scoring jobs within commute cap.
    Previews top N jobs in email (cfg.MAX_EMAIL_JOBS) while reporting total count.
    Returns True if sent or skipped normally, False if an error occurred.
    """
    if not cfg.NOTIFY_ENABLED and not force:
        print("[notify] Email notifications are disabled in configuration.")
        return True

    today_str = datetime.now().strftime("%Y-%m-%d")

    if conn is None:
        conn = sqlite3.connect(cfg.DB_PATH)

    if jobs is None:
        jobs = fetch_today_top_jobs(conn, min_score=cfg.MIN_NOTIFY_SCORE, date_str=today_str)

    if not jobs:
        print(f"[notify] No new roles with match_score >= {cfg.MIN_NOTIFY_SCORE} to notify. Skipping email.")
        return True

    if total_count is None:
        total_count = len(jobs)

    if overall_count is None:
        overall_count = fetch_overall_active_count(conn)

    max_display = getattr(cfg, "MAX_EMAIL_JOBS", 6)
    display_jobs = jobs[:max_display]

    if not cfg.SMTP_USER or not cfg.SMTP_PASS:
        print("\n[notify WARNING] Email credentials not configured:")
        print("  -> Set SMTP_USER and SMTP_PASS in .env or environment to enable email delivery.")
        print(f"  -> Generated digest ready with {total_count} high-fit roles ({len(display_jobs)} previewed).")
        return False

    recipients = cfg.NOTIFY_RECIPIENTS or [cfg.SMTP_USER]

    # Build Email Message with dynamic subject
    role_word = "Role" if total_count == 1 else "Roles"
    if is_test:
        subject = f"🧪 [TEST PREVIEW] Zurich Chem Radar ({len(display_jobs)} Highlights of {overall_count} Active Roles)"
    elif total_count > len(display_jobs):
        subject = f"🧪 [Zurich Chem Radar] {total_count} New {role_word} Discovered Today • Top {len(display_jobs)} Highlights ({today_str})"
    else:
        subject = f"🧪 [Zurich Chem Radar] {total_count} New {role_word} Discovered Today ({today_str})"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Zurich Chem Radar <{cfg.SMTP_USER}>"
    msg["To"] = ", ".join(recipients)

    text_content = _build_text_body(display_jobs, total_count, overall_count, today_str, is_test=is_test)
    html_content = _build_html_body(display_jobs, total_count, overall_count, today_str, is_test=is_test)

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
        print(f"[notify SUCCESS] Sent daily digest ({len(display_jobs)} highlights of {total_count} new roles, {overall_count} active in radar) to {', '.join(recipients)}!")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"\n[notify ERROR] Gmail SMTP Authentication failed: {e}")
        print("Tip: If using Gmail with 2-Factor Authentication, you must use a 16-character 'App Password'.")
        print("Generate one here: https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        print(f"[notify ERROR] Failed to send email: {e}")
        return False
