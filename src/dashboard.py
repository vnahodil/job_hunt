"""Self-contained interactive HTML dashboard generator (zero-server, localStorage-based)."""

import sqlite3
from datetime import datetime

import pandas as pd

from src.config import cfg


def generate_html_dashboard(conn: sqlite3.Connection) -> None:
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
        params=(cfg.MAX_COMMUTE_MINS + 5,),
    )

    rows_html = ""
    for _, r in df.iterrows():
        score = int(r["match_score"])
        badge_cls = "score-high" if score >= 8 else ("score-med" if score >= 7 else "score-low")
        commute_cls = "commute-fast" if r["commute_mins"] <= 25 else ("commute-mid" if r["commute_mins"] <= 45 else "commute-far")
        jid = r["job_hash"][:12]

        title_safe = str(r["title"]).replace("'", "\\'").replace('"', '&quot;')
        co_safe = str(r["company"]).replace("'", "\\'").replace('"', '&quot;')
        sum_safe = str(r["summary"]).replace("'", "\\'").replace('"', '&quot;')

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
                <button class="btn-prompt" onclick="copyPrompt(event, '{title_safe}', '{co_safe}', '{sum_safe}')">Tailor CV</button>
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
    .btn-action {{ cursor: pointer; background: #1e3a8a; border-color: #1d4ed8; font-size: 0.8rem; padding: 4px 8px; }}
    .btn-prompt {{ cursor: pointer; background: #0284c7; border-color: #0369a1; color: #fff; margin-top: 4px; display: block; width: 100%; font-size: 0.78rem; padding: 4px 6px; border-radius: 4px; }}
    .btn-prompt:hover {{ background: #0369a1; }}
    .btn-hide {{ cursor: pointer; color: #f87171; margin-top: 4px; font-size: 0.78rem; }}
</style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🧪 Zurich Chemistry & Cleantech Job Radar</h1>
            <small class="muted">Origin: {cfg.HOME_ORIGIN} (Max ~{cfg.MAX_COMMUTE_MINS}m) | Profile: MSc Organic Chemistry + 3.5y R&D (ETH / Oxyle) | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</small>
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
            <option value="999">All Commutes (<= {cfg.MAX_COMMUTE_MINS}m)</option>
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
                <th>Commute from {cfg.HOME_ORIGIN}</th>
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
    function copyPrompt(e, title, company, summary) {{
        const prompt = `I am applying for the position of "${{title}}" at "${{company}}".

Candidate Profile:
- Education: Master of Science (MSc) in Organic Chemistry
- Academic Research: 2 years PhD research in synthetic organic chemistry + 6 months visiting researcher at ETH Zurich
- Industry Cleantech R&D: 1-year research internship at Oxyle (ETH cleantech spin-off in Schlieren, catalytic water treatment / PFAS destruction)
- Hands-on Lab Skills: Organic synthesis, reaction optimization, catalytic degradation, analytical chemistry (HPLC, LC-MS, GC-MS, NMR), lab automation, process scale-up
- Languages: English (fluent C1/C2), German (B1-B2 conversational lab German)

Role Context / Match Summary:
${{summary}}

Please generate:
1. Three tailored, high-impact bullet points for my CV emphasizing my specific relevant lab experience for this role.
2. A compelling 3-point explanation of why my ETH Zurich research + Oxyle cleantech experience makes me an ideal fit.
3. A polished, professional 3-paragraph cover letter in English matching this company.`;

        navigator.clipboard.writeText(prompt).then(() => {{
            const btn = e.target;
            const orig = btn.innerText;
            btn.innerText = 'Copied!';
            btn.style.background = '#16a34a';
            setTimeout(() => {{
                btn.innerText = orig;
                btn.style.background = '';
            }}, 2000);
        }});
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

    # Write to dashboard.html, index.html (root), and docs/index.html (GitHub Pages)
    cfg.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    target_paths = [cfg.REPORT_PATH, cfg.INDEX_PATH, cfg.DOCS_INDEX_PATH]

    for p in target_paths:
        with open(p, "w", encoding="utf-8") as f:
            f.write(html)

    # Ensure .nojekyll exists so GitHub Pages serves raw assets and doesn't run Jekyll
    for nojekyll_dir in [cfg.PROJECT_ROOT, cfg.DOCS_DIR]:
        nj = nojekyll_dir / ".nojekyll"
        if not nj.exists():
            nj.touch()

    print(f"\n[DONE] Clean interactive dashboard written to:")
    for p in target_paths:
        print(f"  -> {p}")
