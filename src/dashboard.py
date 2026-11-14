"""Self-contained interactive HTML dashboard generator (zero-server, localStorage-based)."""

import sqlite3
from datetime import datetime

import pandas as pd

from src.config import cfg


def parse_summary_parts(summary: str) -> tuple[str, str, str]:
    """Extracts (track, fit, gaps) from structured critical evaluation summary."""
    if not summary:
        return ("", "", "")
    track = ""
    fit = ""
    gaps = ""
    parts = summary.split(" | ")
    for part in parts:
        part = part.strip()
        if "Track:" in part:
            track = part.replace("🎯 Track:", "").replace("Track:", "").strip()
        elif "Fit:" in part:
            fit = part.replace("✅ Fit:", "").replace("Fit:", "").strip()
        elif "Gaps:" in part:
            gaps = part.replace("⚠️ Gaps:", "").replace("Gaps:", "").strip()
        else:
            if not fit:
                fit = part
            else:
                gaps += (" " + part)
    return (track, fit, gaps)


def format_fit_gaps_html(fit: str, gaps: str) -> str:
    """Formats only Fit and Gaps into clean, styled rows for the Role & Match Summary column."""
    lines = []
    if fit:
        lines.append(f'<div class="sum-row"><span class="sum-tag sum-fit">✅ Fit</span> {fit}</div>')
    if gaps:
        lines.append(f'<div class="sum-row"><span class="sum-tag sum-gap">⚠️ Gaps</span> {gaps}</div>')
    return "".join(lines)


def format_found_date(raw_date: str) -> str:
    """Formats 'YYYY-MM-DD' into '14 November 2026'."""
    if not raw_date:
        return ""
    try:
        clean_date = str(raw_date).strip().split("T")[0]
        dt = datetime.strptime(clean_date, "%Y-%m-%d")
        return f"{dt.day} {dt.strftime('%B %Y')}"
    except Exception:
        return str(raw_date)


def generate_html_dashboard(conn: sqlite3.Connection) -> None:
    """Generates a self-contained, modern HTML dashboard with instant filtering & local status memory."""
    df = pd.read_sql_query(
        """
        SELECT job_hash, title, company, location, url, source, commute_mins, commute_mode,
               match_score, role_category, degree_fit, language_req, summary, date_found
        FROM jobs
        WHERE is_relevant = 1 AND match_score >= 6 AND commute_mins <= ?
        ORDER BY match_score DESC, date_found DESC, commute_mins ASC
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
        deg_safe = str(r["degree_fit"]).replace("'", "\\'").replace('"', '&quot;')
        date_safe = str(r["date_found"]).replace("'", "\\'").replace('"', '&quot;')

        track_text, fit_text, gap_text = parse_summary_parts(str(r["summary"]))
        fit_gaps_html = format_fit_gaps_html(fit_text, gap_text)
        track_safe = track_text.replace("'", "\\'").replace('"', '&quot;')

        cat_cell_html = f'<span class="tag cat-tag">{r["role_category"]}</span>'
        if track_text:
            cat_cell_html += f'<div class="cat-track"><span class="sum-tag sum-track">🎯 Track</span> {track_text}</div>'

        date_display = format_found_date(str(r["date_found"]))

        rows_html += f"""
        <tr data-id="{jid}" data-category="{r['role_category']}" data-track="{track_safe}" data-score="{score}" data-commute="{r['commute_mins']}" data-title="{title_safe}" data-company="{co_safe}" data-date="{date_safe}" data-degree="{deg_safe}">
            <td class="col-fit-cell"><span class="badge {badge_cls}">{score}/10</span></td>
            <td class="col-role-cell">
                <a href="{r['url']}" target="_blank" rel="noopener" class="job-title">{r['title']}</a>
                <div class="job-summary">{fit_gaps_html}</div>
            </td>
            <td class="col-co-cell"><strong>{r['company']}</strong><br><small class="muted">{r['source']}</small></td>
            <td class="col-commute-cell"><span class="badge {commute_cls}">{r['location']} (~{r['commute_mins']}m {r['commute_mode']})</span></td>
            <td class="col-cat-cell">{cat_cell_html}</td>
            <td class="col-degree-cell"><span class="tag">{r['degree_fit']}</span><br><small>{r['language_req']}</small></td>
            <td class="col-found-cell">{date_display}</td>
            <td class="col-action-cell">
                <button class="btn-action" onclick="toggleApplied('{jid}')">Applied</button>
                <button class="btn-prompt" onclick="copyPrompt(event, '{title_safe}', '{co_safe}', '{sum_safe}')">CV prompt</button>
                <button class="btn-hide btn-hide-toggle" onclick="hideRow('{jid}')">Hide</button>
            </td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
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
    th.col-fit {{ width: 55px; min-width: 55px; }}
    th.col-role {{ width: 38%; min-width: 340px; }}
    th.col-co {{ width: 12%; min-width: 120px; }}
    th.col-commute {{ width: 13%; min-width: 130px; }}
    th.col-cat {{ width: 15%; min-width: 145px; }}
    th.col-degree {{ width: 10%; min-width: 105px; }}
    th.col-found {{ width: 125px; min-width: 125px; }}
    th.col-action {{ width: 95px; min-width: 95px; }}
    td.col-action-cell {{ padding: 10px 8px; }}
    .col-found-cell {{ white-space: nowrap; font-size: 0.84rem; }}
    th.sortable {{ cursor: pointer; user-select: none; transition: background 0.15s, color 0.15s; white-space: nowrap; }}
    th.sortable:hover {{ background: #1e293b; color: var(--accent); }}
    .sort-icon {{ font-size: 0.72rem; margin-left: 4px; opacity: 0.45; display: inline-block; vertical-align: middle; }}
    th.asc .sort-icon, th.desc .sort-icon {{ opacity: 1; color: var(--accent); }}
    tr:hover {{ background: rgba(56, 189, 248, 0.06); }}
    tr.applied {{ background: rgba(34, 197, 94, 0.12) !important; }}
    .job-title {{ color: var(--accent); font-weight: 600; text-decoration: none; font-size: 0.98rem; }}
    .job-title:hover {{ text-decoration: underline; }}
    .job-summary {{ color: var(--muted); font-size: 0.82rem; margin-top: 5px; line-height: 1.42; }}
    .sum-row {{ margin-top: 4px; display: flex; align-items: baseline; gap: 6px; }}
    .sum-tag {{ font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; padding: 2px 6px; border-radius: 4px; white-space: nowrap; flex-shrink: 0; }}
    .sum-track {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }}
    .sum-fit {{ background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }}
    .sum-gap {{ background: rgba(248, 113, 113, 0.15); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3); }}
    .cat-tag {{ display: inline-block; margin-bottom: 4px; }}
    .cat-track {{ color: var(--muted); font-size: 0.78rem; line-height: 1.35; margin-top: 5px; }}
    .cat-track .sum-tag {{ font-size: 0.65rem; padding: 1px 5px; margin-right: 3px; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 6px; font-weight: 600; font-size: 0.8rem; }}
    .score-high {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}
    .score-med {{ background: rgba(250, 204, 21, 0.2); color: #facc15; }}
    .score-low {{ background: rgba(148, 163, 184, 0.2); color: #cbd5e1; }}
    .commute-fast {{ background: rgba(34, 197, 94, 0.15); color: #86efac; }}
    .commute-mid {{ background: rgba(56, 189, 248, 0.15); color: #7dd3fc; }}
    .commute-far {{ background: rgba(249, 115, 22, 0.15); color: #fdba74; }}
    .tag {{ background: #334155; padding: 3px 7px; border-radius: 4px; font-size: 0.78rem; }}
    .muted {{ color: var(--muted); }}
    .btn-action, .btn-prompt, .btn-hide {{
        display: block;
        width: 100%;
        box-sizing: border-box;
        text-align: center;
        font-size: 0.76rem;
        padding: 5px 4px;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 500;
        white-space: nowrap;
        border: 1px solid transparent;
        transition: background 0.15s, border-color 0.15s;
    }}
    .btn-action {{ background: #1e3a8a; border-color: #1d4ed8; color: #fff; margin-bottom: 4px; }}
    .btn-action:hover {{ background: #2563eb; }}
    tr.applied .btn-action {{ background: #15803d; border-color: #16a34a; color: #fff; }}
    tr.applied .btn-action:hover {{ background: #16a34a; }}
    .btn-prompt {{ background: #0284c7; border-color: #0369a1; color: #fff; margin-bottom: 4px; }}
    .btn-prompt:hover {{ background: #0ea5e9; }}
    .btn-hide {{ background: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.35); color: #f87171; margin-bottom: 0; }}
    .btn-hide:hover {{ background: rgba(239, 68, 68, 0.28); border-color: rgba(239, 68, 68, 0.5); }}
    .btn-unhide {{ background: rgba(14, 165, 233, 0.2) !important; border-color: #38bdf8 !important; color: #38bdf8 !important; margin-bottom: 0; }}
    .btn-unhide:hover {{ background: rgba(14, 165, 233, 0.35) !important; }}
    #toggleHiddenBtn {{ cursor: pointer; transition: all 0.2s; white-space: nowrap; }}
    #toggleHiddenBtn.active-hidden-view {{ background: rgba(239, 68, 68, 0.22); border-color: #f87171; color: #fecaca; font-weight: 600; }}
    tr.is-hidden-row {{ opacity: 0.92; border-left: 3px solid #f87171; }}
    .mobile-only-control {{ display: none; }}

    @media (max-width: 860px) {{
        body {{
            padding: 12px;
        }}
        .header {{
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
            padding-bottom: 12px;
        }}
        h1 {{
            font-size: 1.25rem;
            line-height: 1.3;
        }}
        .controls {{
            padding: 10px;
            gap: 8px;
        }}
        .controls input,
        .controls select,
        .controls button {{
            width: 100%;
            box-sizing: border-box;
            font-size: 16px; /* Prevents auto-zoom on iOS */
            padding: 10px 12px;
        }}
        .mobile-only-control {{
            display: block;
        }}

        /* Responsive Card Transformation */
        table, thead, tbody, th, td, tr {{
            display: block;
        }}
        thead {{
            display: none;
        }}
        tr {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 16px;
            padding: 16px;
            position: relative;
            box-sizing: border-box;
        }}
        tr.is-hidden-row {{
            border-left: 4px solid #f87171 !important;
        }}
        tr.applied {{
            border-left: 4px solid #22c55e !important;
        }}
        td {{
            padding: 3px 0;
            border: none;
        }}

        /* Fit badge top right */
        td.col-fit-cell {{
            position: absolute;
            top: 16px;
            right: 16px;
            padding: 0;
        }}
        td.col-fit-cell .badge {{
            font-size: 0.88rem;
            padding: 4px 10px;
        }}

        /* Role Title */
        td.col-role-cell {{
            padding-right: 65px;
            margin-bottom: 6px;
        }}
        .job-title {{
            font-size: 1.05rem;
            line-height: 1.35;
            display: inline-block;
            margin-bottom: 4px;
        }}
        .job-summary {{
            margin-top: 8px;
            font-size: 0.85rem;
        }}

        /* Company & Commute */
        td.col-co-cell {{
            margin-bottom: 4px;
            font-size: 0.92rem;
        }}
        td.col-commute-cell {{
            margin-bottom: 6px;
        }}
        td.col-commute-cell .badge {{
            font-size: 0.78rem;
            white-space: normal;
            line-height: 1.3;
        }}

        /* Category & Degree */
        td.col-cat-cell {{
            margin-bottom: 4px;
        }}
        td.col-degree-cell {{
            margin-bottom: 4px;
            font-size: 0.82rem;
        }}

        /* Found Date */
        td.col-found-cell {{
            font-size: 0.78rem;
            color: var(--muted);
            margin-top: 4px;
            margin-bottom: 8px;
        }}
        td.col-found-cell::before {{
            content: "Discovered: ";
            font-weight: 500;
            color: var(--muted);
        }}

        /* Action buttons: horizontal row on mobile */
        td.col-action-cell {{
            display: flex;
            gap: 8px;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
            width: 100%;
            box-sizing: border-box;
        }}
        td.col-action-cell .btn-action,
        td.col-action-cell .btn-prompt,
        td.col-action-cell .btn-hide {{
            flex: 1;
            margin: 0;
            padding: 9px 4px;
            font-size: 0.82rem;
            border-radius: 6px;
            text-align: center;
        }}
    }}
</style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🧪 Zurich Chemistry & Cleantech Job Radar</h1>
            <small class="muted">Origin: {cfg.HOME_ORIGIN} (Max ~{cfg.MAX_COMMUTE_MINS}m) | Profile: MSc Chemistry (Honors) + R&D (ETH Zürich / Oxyle / UCT Prague) | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</small>
        </div>
        <div id="roleCountDisplay"><strong>{len(df)}</strong> Matching Roles</div>
    </div>

    <div class="controls">
        <input type="text" id="searchInput" placeholder="Filter by title, company, location, PFAS, HPLC, Peptides..." oninput="filterTable()" style="flex:1;">
        <select id="scoreFilter" onchange="filterTable()">
            <option value="0" selected>All Verified Roles (6+ / 10)</option>
            <option value="7">Top Fits Only (7+ / 10)</option>
            <option value="8">Strong Matches (8+ / 10)</option>
            <option value="9">Dream Roles (9-10 / 10)</option>
        </select>
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
        <select id="mobileSort" class="mobile-only-control" onchange="onMobileSortChange()">
            <option value="0-desc" selected>Sort: Fit (Highest)</option>
            <option value="0-asc">Sort: Fit (Lowest)</option>
            <option value="6-desc">Sort: Date (Newest)</option>
            <option value="6-asc">Sort: Date (Oldest)</option>
            <option value="3-asc">Sort: Commute (Shortest)</option>
            <option value="1-asc">Sort: Title (A-Z)</option>
            <option value="2-asc">Sort: Company (A-Z)</option>
        </select>
        <button id="toggleHiddenBtn" onclick="toggleShowHidden()">Show Hidden (0)</button>
    </div>

    <table id="jobsTable">
        <thead>
            <tr>
                <th class="sortable col-fit desc" onclick="sortTable(0)">Fit <span class="sort-icon">▼</span></th>
                <th class="sortable col-role" onclick="sortTable(1)">Role & Match Summary <span class="sort-icon">↕</span></th>
                <th class="sortable col-co" onclick="sortTable(2)">Company <span class="sort-icon">↕</span></th>
                <th class="sortable col-commute" onclick="sortTable(3)">Commute <span class="sort-icon">↕</span></th>
                <th class="sortable col-cat" onclick="sortTable(4)">Category & Track <span class="sort-icon">↕</span></th>
                <th class="sortable col-degree" onclick="sortTable(5)">Degree & Language <span class="sort-icon">↕</span></th>
                <th class="sortable col-found" onclick="sortTable(6)">Found <span class="sort-icon">↕</span></th>
                <th class="sortable col-action" onclick="sortTable(7)">Status <span class="sort-icon">↕</span></th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

<script>
    let showHiddenOnly = false;

    function getHiddenJobs() {{
        return JSON.parse(localStorage.getItem('hiddenJobs') || '[]');
    }}

    function updateHiddenCount() {{
        const hidden = getHiddenJobs();
        const btn = document.getElementById('toggleHiddenBtn');
        if (!btn) return;
        if (showHiddenOnly) {{
            btn.classList.add('active-hidden-view');
            btn.innerText = `← View Active Roles (${{hidden.length}} hidden)`;
        }} else {{
            btn.classList.remove('active-hidden-view');
            btn.innerText = `Show Hidden (${{hidden.length}})`;
        }}
    }}

    function toggleShowHidden() {{
        showHiddenOnly = !showHiddenOnly;
        updateHiddenCount();
        filterTable();
    }}

    function loadState() {{
        const applied = JSON.parse(localStorage.getItem('appliedJobs') || '[]');
        document.querySelectorAll('#jobsTable tbody tr').forEach(tr => {{
            const id = tr.dataset.id;
            if (applied.includes(id)) tr.classList.add('applied');
        }});
        updateHiddenCount();
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
        let hidden = getHiddenJobs();
        if (!hidden.includes(id)) hidden.push(id);
        localStorage.setItem('hiddenJobs', JSON.stringify(hidden));
        updateHiddenCount();
        filterTable();
    }}
    function unhideRow(id) {{
        let hidden = getHiddenJobs();
        hidden = hidden.filter(x => x !== id);
        localStorage.setItem('hiddenJobs', JSON.stringify(hidden));
        updateHiddenCount();
        filterTable();
    }}
    function copyPrompt(e, title, company, summary) {{
        const prompt = `I am applying for the position of "${{title}}" at "${{company}}".

Candidate Profile:
- Education: Master’s in Chemistry (Honors) & Bachelor’s in Drug Synthesis & Production (Honors), UCT Prague
- Academic Research: 6 months Visiting Researcher & TA at ETH Zürich (Bode Group: peptide/GLP-1 synthesis, SPPS, HPLC, LCMS, MALDI, NMR) + 2 years PhD Researcher at UCT Prague (organic synthesis, development & commercialization of HPLC stationary phases Astra® DM with industry partners)
- Industry R&D: R&D Innovation Intern at an ETH cleantech spin-off (water treatment, ion-exchange resins, batch & column experiments, COD, photometry, ISE)
- Hands-on Lab & Analytical Skills: Synthetic organic chemistry, reaction design & retrosynthesis, SPPS peptide synthesis, asymmetric organocatalysis, HPLC / RP-HPLC, LCMS, MALDI, NMR, UV/Vis, IR, RT-PCR, GLP & HSE
- Software: ChemDraw, SciFinder, Reaxys, MNova, Excel
- Languages: English (fluent C1), German (conversational B1), Czech (Native)

Role Context & Critical Match Assessment:
${{summary}}

Please generate:
1. Three tailored, high-impact bullet points for my CV emphasizing my specific relevant lab experience for this role and strategically addressing the identified career gaps.
2. A compelling 3-point explanation of why my ETH Zurich research, UCT Prague synthesis/HPLC experience, and cleantech startup background makes me an ideal fit while bridging any gaps.
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
        const minS = parseInt(document.getElementById('scoreFilter').value || '0');
        const hidden = getHiddenJobs();

        let visibleCount = 0;
        document.querySelectorAll('#jobsTable tbody tr').forEach(tr => {{
            const id = tr.dataset.id;
            const isHidden = hidden.includes(id);

            if (showHiddenOnly) {{
                if (!isHidden) {{
                    tr.style.display = 'none';
                    return;
                }}
                tr.classList.add('is-hidden-row');
                const btn = tr.querySelector('.btn-hide-toggle');
                if (btn) {{
                    btn.innerText = 'Unhide';
                    btn.className = 'btn-hide btn-unhide btn-hide-toggle';
                    btn.onclick = () => unhideRow(id);
                }}
            }} else {{
                if (isHidden) {{
                    tr.style.display = 'none';
                    return;
                }}
                tr.classList.remove('is-hidden-row');
                const btn = tr.querySelector('.btn-hide-toggle');
                if (btn) {{
                    btn.innerText = 'Hide';
                    btn.className = 'btn-hide btn-hide-toggle';
                    btn.onclick = () => hideRow(id);
                }}
            }}

            const text = tr.innerText.toLowerCase();
            const matchQ = text.includes(q);
            const matchCat = !cat || tr.dataset.category === cat;
            const matchC = parseInt(tr.dataset.commute) <= maxC;
            const matchS = parseInt(tr.dataset.score) >= minS;
            const isVisible = (matchQ && matchCat && matchC && matchS);
            tr.style.display = isVisible ? '' : 'none';
            if (isVisible) visibleCount++;
        }});

        const countDisplay = document.getElementById('roleCountDisplay');
        if (countDisplay) {{
            countDisplay.innerHTML = showHiddenOnly
                ? `<strong>${{visibleCount}}</strong> Hidden Roles`
                : `<strong>${{visibleCount}}</strong> Matching Roles`;
        }}
    }}

    let currentSortCol = 0;
    let currentSortDir = 'desc';

    function getCellValue(tr, idx) {{
        switch (idx) {{
            case 0: return parseInt(tr.dataset.score || '0', 10);
            case 1: return (tr.dataset.title || '').toLowerCase();
            case 2: return (tr.dataset.company || '').toLowerCase();
            case 3: return parseInt(tr.dataset.commute || '999', 10);
            case 4: return ((tr.dataset.category || '') + ' ' + (tr.dataset.track || '')).toLowerCase();
            case 5: return (tr.dataset.degree || tr.children[5]?.innerText || '').toLowerCase();
            case 6: return tr.dataset.date || '';
            case 7: return tr.classList.contains('applied') ? 1 : 0;
            default: return tr.children[idx]?.innerText.trim().toLowerCase() || '';
        }}
    }}

    function onMobileSortChange() {{
        const val = document.getElementById('mobileSort').value;
        const [colStr, dir] = val.split('-');
        sortTable(parseInt(colStr, 10), dir);
    }}

    function sortTable(colIndex, forcedDir = null) {{
        const table = document.getElementById('jobsTable');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const headers = table.querySelectorAll('thead th');

        if (forcedDir) {{
            currentSortCol = colIndex;
            currentSortDir = forcedDir;
        }} else if (currentSortCol === colIndex) {{
            currentSortDir = (currentSortDir === 'asc') ? 'desc' : 'asc';
        }} else {{
            currentSortCol = colIndex;
            // Fit (0), Found (6), Track (7) default to descending; others default to ascending
            currentSortDir = (colIndex === 0 || colIndex === 6 || colIndex === 7) ? 'desc' : 'asc';
        }}

        // Sync mobile sort dropdown if present
        const mobileSort = document.getElementById('mobileSort');
        if (mobileSort) {{
            const key = `${{colIndex}}-${{currentSortDir}}`;
            for (let opt of mobileSort.options) {{
                if (opt.value === key) {{
                    mobileSort.value = key;
                    break;
                }}
            }}
        }}

        headers.forEach((th, idx) => {{
            th.classList.remove('asc', 'desc');
            const icon = th.querySelector('.sort-icon');
            if (icon) {{
                if (idx === colIndex) {{
                    th.classList.add(currentSortDir);
                    icon.textContent = currentSortDir === 'asc' ? '▲' : '▼';
                }} else {{
                    icon.textContent = '↕';
                }}
            }}
        }});

        rows.sort((a, b) => {{
            const valA = getCellValue(a, colIndex);
            const valB = getCellValue(b, colIndex);

            let comp = 0;
            if (typeof valA === 'number' && typeof valB === 'number') {{
                comp = valA - valB;
            }} else {{
                comp = String(valA).localeCompare(String(valB));
            }}
            if (comp !== 0) return currentSortDir === 'asc' ? comp : -comp;

            // Tie-breakers: Fit sorts secondary by Date (newest first); Date sorts secondary by Fit (highest first)
            if (colIndex === 0) {{
                const dateA = a.dataset.date || '';
                const dateB = b.dataset.date || '';
                return dateB.localeCompare(dateA);
            }}
            if (colIndex === 6) {{
                const fitA = parseInt(a.dataset.score || '0', 10);
                const fitB = parseInt(b.dataset.score || '0', 10);
                return fitB - fitA;
            }}
            return 0;
        }});

        rows.forEach(r => tbody.appendChild(r));
    }}
    loadState();
    filterTable();
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
