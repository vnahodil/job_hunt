"""Gemini 2.5 Flash semantic evaluator + zero-cost heuristic fallback."""

import re
import time
import sqlite3
from typing import Optional

from src.config import cfg
from src.models import JobEvaluation
from src.scrapers.description_fetcher import fetch_job_description_body


# ---------------------------------------------------------------------------
# Heuristic (deterministic, zero-API-key) fallback scorer
# ---------------------------------------------------------------------------

def evaluate_job_heuristic(title: str, company: str, desc: str, source: str) -> JobEvaluation:
    """Zero-cost deterministic scorer used when GEMINI_API_KEY is not set or rate-limited."""
    text = f"{title} {company} {desc}".lower()
    t_lower = title.lower()

    # 0. Foreign locations (Boston, USA, etc.)
    if cfg.FOREIGN_LOCATIONS_REGEX.search(title) or cfg.FOREIGN_LOCATIONS_REGEX.search(desc[:500]):
        return JobEvaluation(
            is_relevant=False, match_score=1, role_category="Other",
            degree_fit="Foreign Location", language_req="N/A",
            one_line_summary="Position located outside Switzerland.",
        )

    # 1. Hard exclusions: Academic Postdocs, Professorships, Apprenticeships, IT/Hardware
    if any(k in t_lower for k in ["postdoc", "postdoctoral", "professorship", "professor"]):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Academic",
            degree_fit="Academic Postdoc/Prof", language_req="N/A",
            one_line_summary="Academic postdoc / professorship excluded.",
        )
    if any(k in t_lower for k in ["lehrstelle", "schnupper", "laborant efz", "lernende"]):
        return JobEvaluation(
            is_relevant=False, match_score=1, role_category="Other",
            degree_fit="Apprenticeship EFZ", language_req="N/A",
            one_line_summary="Apprenticeship / vocational position excluded.",
        )
    if any(k in t_lower for k in ["electrical engineer", "mechanical engineer", "software engineer", "frontend", "full stack"]):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Other",
            degree_fit="N/A", language_req="N/A",
            one_line_summary="Non-chemical engineering position excluded.",
        )

    # 2. Master thesis & Bachelor thesis exclusions
    if any(k in t_lower for k in ["master thesis", "masterarbeit", "master’s thesis", "bachelor thesis", "bachelorarbeit"]):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Academic",
            degree_fit="Student Thesis", language_req="N/A",
            one_line_summary="Student thesis project excluded (candidate already has MSc + 3.5y R&D).",
        )

    # 3. Academic PhD / Doctoral studentship exclusions
    if any(k in t_lower for k in ["phd position", "doctoral position", "phd student", "doktorand", "doctoral student", "phd in "]):
        return JobEvaluation(
            is_relevant=False, match_score=3, role_category="Academic",
            degree_fit="PhD Student", language_req="N/A",
            one_line_summary="Academic PhD / Doctoral student position excluded (candidate seeking professional R&D/industry roles).",
        )

    # 4. Non-chemical biology / ecology / fieldwork exclusions
    if any(k in t_lower for k in ["ecology", "ökologie", "zoology", "biodiversity", "fish", "wildlife", "limnology", "stream", "alpine lake"]):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Other",
            degree_fit="N/A", language_req="N/A",
            one_line_summary="Non-chemical ecology/wildlife fieldwork excluded.",
        )

    # 5. University Praktikum / student internships (non-industry)
    is_internship = any(k in t_lower for k in ["internship", "intern", "praktikum", "praktikant"])
    is_industry_internship = is_internship and any(
        k in text for k in ["roche", "lonza", "syngenta", "givaudan", "novartis", "industry", "lc-ms", "bioanalytics", "synthetic"]
    )
    if is_internship and not is_industry_internship:
        return JobEvaluation(
            is_relevant=False, match_score=3, role_category="Other",
            degree_fit="Student Praktikum", language_req="N/A",
            one_line_summary="University / student internship under-leveled for candidate with MSc + 3.5y R&D.",
        )

    if cfg.NEGATIVE_ROLE_KEYWORDS.search(title):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Other",
            degree_fit="N/A", language_req="N/A", one_line_summary="Non-scientific role filtered out.",
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

    # BOOST: Entry-level, Early Career, Associate Scientist, Graduate / Trainee Programs
    is_early_career = any(k in t_lower for k in [
        "associate scientist", "research associate", "junior", "entry level", "entry-level",
        "trainee", "graduate program", "graduate", "rotational", "fellowship", "wissenschaftliche",
        "scientific collaborator", "r&d chemist", "lab specialist", "laboratory specialist"
    ])
    if is_early_career:
        score += 2
        degree_fit = "Early Career / MSc"
    elif is_industry_internship:
        score = max(score, 7)
        degree_fit = "Industry Trainee/Intern"
    else:
        degree_fit = "Ideal for MSc+Exp"

    if any(k in text for k in ["application specialist", "consultant", "technical sales", "product steward"]):
        category = "Consulting/App"
    if any(k in text for k in ["quality", "qa ", "gmp", "regulatory", "pharmacovigilance"]):
        category = "Pharma QA/Reg"

    # Degree check
    if "phd required" in text and "master" not in text and "equivalent" not in text:
        score -= 2
        degree_fit = "Strict PhD Only"
    elif "master" in text or "msc" in text or "m.sc" in text:
        score += 1

    # Language check
    de_words = len(re.findall(r"\b(und|oder|wir|für|mit|aufgaben|profil)\b", text))
    lang_req = "EN + DE B1/B2 OK" if de_words > 4 else "English"
    if any(k in text for k in ["verhandlungssicher", "muttersprache", "c1", "c2", "fluent german required"]):
        lang_req = "Fluent DE Required"
        score -= 1

    score = max(1, min(10, score))
    is_rel = score >= 6 and bool(cfg.POSITIVE_ROLE_KEYWORDS.search(f"{title} {desc[:400]}"))

    summary = f"{category} role at {company} ({source}); matches MSc Chemistry + R&D background."
    return JobEvaluation(
        is_relevant=is_rel,
        match_score=score,
        role_category=category,
        degree_fit=degree_fit,
        language_req=lang_req,
        one_line_summary=summary,
    )


# ---------------------------------------------------------------------------
# Gemini 3.8 Flash evaluator (with automatic fallback to 3.5 Flash)
# ---------------------------------------------------------------------------

def evaluate_job(client, title: str, company: str, location: str, desc: str, source: str) -> JobEvaluation:
    """Uses Gemini 3.8 Flash (falling back to 3.5 Flash or heuristic) with Full CV & Career Tracks."""
    # Fast guardrail: check foreign locations or hard negative keywords
    t_clean = title.strip()
    d_clean = (desc or "").strip()
    if cfg.FOREIGN_LOCATIONS_REGEX.search(t_clean) or cfg.FOREIGN_LOCATIONS_REGEX.search(d_clean[:600]):
        return JobEvaluation(
            is_relevant=False, match_score=1, role_category="Other",
            degree_fit="Foreign Location", language_req="N/A",
            one_line_summary="Position located outside Switzerland.",
        )
    if cfg.NEGATIVE_ROLE_KEYWORDS.search(t_clean):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Other",
            degree_fit="Disqualified Title", language_req="N/A",
            one_line_summary="Executive, legal, patent, or non-target role excluded.",
        )

    if not client:
        return evaluate_job_heuristic(title, company, desc, source)

    desc_clean = d_clean if len(d_clean) >= 30 else f"Position: {title} at {company} in {location}."

    cv_text = cfg.get_candidate_cv()
    career_directions_text = cfg.get_candidate_career_directions()

    prompt = f"""
    You are an expert Swiss life sciences career advisor evaluating a job opening for this candidate.

    === CANDIDATE FULL CV ===
    {cv_text}

    === ENVISIONED CAREER DIRECTIONS & TARGET TRACKS ===
    {career_directions_text}

    === JOB VACANCY TO EVALUATE ===
    Job Title: {title}
    Company: {company}
    Location: {location}
    Source: {source}
    Description:
    {desc_clean[:5500]}

    === EVALUATION GUIDELINES ===
    1. EXCLUDE & REJECT (is_relevant=false, match_score 1-3):
       - Executive & Senior Leadership: Director, Senior Director, Head of Department, VP, Chief (demands completed PhD + 5+ years post-PhD corporate management).
       - Legal, Patent & Non-Lab Fields: Patent Attorney, Patent Agent, Legal Counsel, Actuarial, Finance, Tax.
       - Academic Degrees & Trainees: Academic PhD positions (Doktorand), Master / Bachelor thesis projects, Vocational Apprenticeships (Lehrstelle EFZ), Student Praktikum.
       - Foreign Locations: Positions located outside Switzerland (e.g. Boston, USA, Germany, UK).
       - Languages: Roles explicitly demanding native/C2 German for legal/contract negotiations.

    2. FAVOR & BOOST (is_relevant=true, match_score 8-10):
       - Directly aligns with one of her 5 Envisioned Career Tracks (especially Track 1 Cleantech/Environmental R&D, Track 2 Synthetic Chemistry, Track 3 Analytical HPLC/MS, Track 4 Sustainability Consulting).
       - Matches hands-on skills in her CV: Organic synthesis, reaction scouting, catalysis, water treatment / PFAS destruction, HPLC, LC-MS, GC-MS, NMR, process scale-up.
       - Entry-level to early-career level (~0 to 4 years post-MSc effective experience): Associate Scientist, Research Associate, Chemist, R&D Specialist, Application Specialist, Industry Graduate Programs.
       - Working language English (C1/C2) or conversational lab German (B1-B2).

    3. OUTPUT REQUIREMENTS:
       - role_category: One of ['R&D Lab', 'Cleantech', 'Analytical', 'Pharma QA/Reg', 'Consulting/App', 'Process/Industry'].
       - degree_fit: e.g. "MSc / PhD Ideal", "BSc/MSc Suitable", "Overqualified (PhD Req)", "Non-chemical".
       - language_req: e.g. "English (C1)", "German (B1-B2)", "German (C1/C2 - Reject)".
       - one_line_summary: A concise statement highlighting specific CV overlap (e.g. "Direct fit for her 1y Oxyle catalytic water treatment & HPLC-MS PFAS experience.") or the specific reason for disqualification.
    """

    models_to_try = [
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]
    for attempt in range(2):
        for model_name in models_to_try:
            try:
                resp = client.models.generate_content(
                    model=model_name,
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
                    time.sleep(3 * (attempt + 1))
                    continue
                # For network/timeout, 503, or unavailable, continue to next model in cascade
                continue

    print(f"  [WARN] LLM evaluation failed for '{title[:30]}', using updated heuristic fallback.")
    return evaluate_job_heuristic(title, company, desc, source)


# ---------------------------------------------------------------------------
# Batch re-scorer for existing DB rows
# ---------------------------------------------------------------------------

def rescore_database_jobs(conn: sqlite3.Connection, client, limit: Optional[int] = None) -> None:
    """Re-scores existing jobs stored in chem_jobs.db using Gemini 3.8 / 3.5 Flash."""
    if not client:
        print("[!] GEMINI_API_KEY is not set or google-genai is not available. Cannot rescore.")
        return

    cur = conn.cursor()
    query = """
        SELECT job_hash, title, company, location, url, source, summary 
        FROM jobs 
        ORDER BY is_relevant DESC, match_score DESC
    """
    if limit:
        query += f" LIMIT {int(limit)}"
    cur.execute(query)
    rows = cur.fetchall()
    total = len(rows)

    print(f"[*] Re-scoring {total} jobs in chem_jobs.db using Gemini (gemini-3.8-flash / 3.5-flash)...")
    print("    (Paced at 4s intervals for Google AI Studio free tier limits ~15 RPM)")

    updated = 0
    for i, (jhash, title, company, location, url, source, old_summary) in enumerate(rows, 1):
        print(f"  [{i}/{total}] Evaluating: {title[:38]} @ {company[:20]}...", flush=True)

        desc_to_eval = old_summary
        if url:
            body = fetch_job_description_body(url, timeout=3)
            if body and len(body) > 60:
                desc_to_eval = body

        ev = evaluate_job(client, title, company, location, desc_to_eval, source)
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
