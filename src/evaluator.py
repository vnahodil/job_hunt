"""Gemini Flash semantic evaluator + zero-cost heuristic fallback."""

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

def evaluate_job_heuristic(title: str, company: str, desc: str, source: str, location: str = "") -> JobEvaluation:
    """Zero-cost deterministic scorer used when GEMINI_API_KEY is not set or rate-limited."""
    text = f"{title} {company} {desc or ''}".lower()
    t_clean = (title or "").strip()
    loc_clean = (location or "").strip()
    d_clean = (desc or "").strip()
    t_lower = t_clean.lower()

    # 0. Foreign locations (Boston, USA, etc.) - check title and location ONLY
    if cfg.FOREIGN_LOCATIONS_REGEX.search(t_clean) or cfg.FOREIGN_LOCATIONS_REGEX.search(loc_clean):
        return JobEvaluation(
            is_relevant=False, match_score=1, role_category="Other",
            degree_fit="Foreign Location", language_req="N/A",
            track_alignment="Disqualified: Outside Switzerland",
            fit_strengths="None",
            career_gaps="Position is located outside Switzerland.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: None | ⚠️ Gaps: Position located outside Switzerland.",
            scorer="heuristic",
        )

    # 1. Hard exclusions: Negative keywords (executive, legal, IT, logistics, sales, trades)
    if cfg.NEGATIVE_ROLE_KEYWORDS.search(t_clean):
        return JobEvaluation(
            is_relevant=False, match_score=1, role_category="Other",
            degree_fit="Disqualified Title", language_req="N/A",
            track_alignment="Disqualified: Non-target track",
            fit_strengths="None",
            career_gaps="Executive, legal, patent, IT, logistics, or non-target title.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: None | ⚠️ Gaps: Disqualified non-scientific or executive title.",
            scorer="heuristic",
        )

    # 2. Hard exclusions: Academic Postdocs, Professorships, Apprenticeships, IT/Hardware
    if any(k in t_lower for k in ["postdoc", "postdoctoral", "professorship", "professor"]):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Academic",
            degree_fit="Academic Postdoc/Prof", language_req="N/A",
            track_alignment="Disqualified: Academic Postdoc",
            fit_strengths="Academic research overlap.",
            career_gaps="Demands completed PhD for academic research/teaching track.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: Academic research | ⚠️ Gaps: Postdoctoral position requires completed PhD.",
            scorer="heuristic",
        )
    if any(k in t_lower for k in ["lehrstelle", "schnupper", "laborant efz", "lernende"]):
        return JobEvaluation(
            is_relevant=False, match_score=1, role_category="Other",
            degree_fit="Apprenticeship EFZ", language_req="N/A",
            track_alignment="Disqualified: Vocational Apprenticeship",
            fit_strengths="Under-leveled for MSc Chemist.",
            career_gaps="Apprenticeship / vocational position.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: Under-leveled | ⚠️ Gaps: Apprenticeship / vocational training.",
            scorer="heuristic",
        )
    if any(k in t_lower for k in ["electrical engineer", "mechanical engineer", "software engineer", "frontend", "full stack"]):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Other",
            degree_fit="N/A", language_req="N/A",
            track_alignment="Disqualified: Non-chemical Engineering",
            fit_strengths="None",
            career_gaps="Requires hardware or software engineering degree.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: None | ⚠️ Gaps: Non-chemical engineering field.",
            scorer="heuristic",
        )

    # 3. Master thesis & Bachelor thesis exclusions
    if any(k in t_lower for k in ["master thesis", "masterarbeit", "master’s thesis", "bachelor thesis", "bachelorarbeit"]):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Academic",
            degree_fit="Student Thesis", language_req="N/A",
            track_alignment="Disqualified: Student Thesis",
            fit_strengths="Already graduated with MSc in Chemistry.",
            career_gaps="Student thesis project (candidate seeks professional employment).",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: Already graduated | ⚠️ Gaps: Student thesis project.",
            scorer="heuristic",
        )

    # 4. Academic PhD / Doctoral studentship exclusions
    if any(k in t_lower for k in ["phd position", "doctoral position", "phd student", "doktorand", "doctoral student", "phd in "]):
        return JobEvaluation(
            is_relevant=False, match_score=3, role_category="Academic",
            degree_fit="PhD Student", language_req="N/A",
            track_alignment="Disqualified: Academic PhD Studentship",
            fit_strengths="Synthesis / analytical background.",
            career_gaps="Candidate completed 2y PhD research and seeks professional R&D/industry roles.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: Synthesis research | ⚠️ Gaps: Academic PhD studentship.",
            scorer="heuristic",
        )

    # 5. Non-chemical biology / ecology / fieldwork exclusions
    if any(k in t_lower for k in ["ecology", "ökologie", "zoology", "biodiversity", "fish", "wildlife", "limnology", "stream", "alpine lake"]):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Other",
            degree_fit="N/A", language_req="N/A",
            track_alignment="Disqualified: Non-chemical Fieldwork",
            fit_strengths="None",
            career_gaps="Ecology/wildlife biology degree required.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: None | ⚠️ Gaps: Non-chemical ecology/wildlife fieldwork.",
            scorer="heuristic",
        )

    # 6. University Praktikum / student internships (non-industry)
    is_internship = any(k in t_lower for k in ["internship", "intern", "praktikum", "praktikant"])
    is_industry_internship = is_internship and any(
        k in text for k in ["roche", "lonza", "syngenta", "givaudan", "novartis", "industry", "lc-ms", "bioanalytics", "synthetic"]
    )
    if is_internship and not is_industry_internship:
        return JobEvaluation(
            is_relevant=False, match_score=3, role_category="Other",
            degree_fit="Student Praktikum", language_req="N/A",
            track_alignment="Disqualified: Undergraduate Internship",
            fit_strengths="Under-leveled.",
            career_gaps="Designed for enrolled undergraduate students.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: Under-leveled | ⚠️ Gaps: University student internship.",
            scorer="heuristic",
        )

    # 7. Core science / laboratory domain requirement:
    # If the title or text does not contain explicit chemical/science/cleantech terms, immediate disqualification!
    CHEM_SCIENCE_REGEX = re.compile(
        r"(chem|scien|labor|synthe|analyt|chromat|hplc|mass spec|lc-ms|gc-ms|nmr|spectro|"
        r"cleantech|water treat|ion exchange|pfas|peptid|resin|polym|pharma|biotech|formulat|"
        r"cdmo|qc\b|qa\b|gmp|process dev|method dev|regulatory affair|application specialist)",
        re.I,
    )
    if not CHEM_SCIENCE_REGEX.search(t_clean) and not CHEM_SCIENCE_REGEX.search(d_clean[:1000]):
        return JobEvaluation(
            is_relevant=False, match_score=1, role_category="Other",
            degree_fit="Non-scientific", language_req="N/A",
            track_alignment="Disqualified: Non-scientific field",
            fit_strengths="None",
            career_gaps="No chemistry, cleantech, or life sciences technical domain found.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: None | ⚠️ Gaps: Non-scientific domain.",
            scorer="heuristic",
        )

    # 8. Deterministic scoring for verified chemistry / cleantech roles
    score = 4
    category = "R&D Lab"
    track = "Track 2: Synthetic Organic & Process Chemistry"

    # Identify primary track and category
    if any(k in text for k in ["cleantech", "water treat", "pfas", "recycling", "environmental technology", "sorbent"]):
        category = "Cleantech"
        track = "Track 1: Cleantech & Environmental R&D"
        score += 2
    elif any(k in text for k in ["analytical", "hplc", "lc-ms", "gc-ms", "mass spec", "chromatography", "nmr", "method development"]):
        category = "Analytical"
        track = "Track 3: Analytical Chemistry & Method Development"
        score += 2
    elif any(k in text for k in ["organic", "synthe", "peptide", "small molecule", "medicinal", "spps"]):
        category = "R&D Lab"
        track = "Track 2: Synthetic Organic & Process Chemistry"
        score += 2
    elif any(k in text for k in ["application specialist", "technical sales", "product steward", "life science consultant"]):
        category = "Consulting/App"
        track = "Track 4: Life Sciences & Sustainability Consulting"
        score += 1
    elif any(k in text for k in ["quality assurance", "qa ", "qc ", "gmp", "regulatory affairs"]):
        category = "Pharma QA/Reg"
        track = "Track 5: Pharma QA & Regulatory Affairs"
        score += 1

    # BOOST: Entry-level, Early Career, Associate Scientist, Graduate / Trainee Programs
    is_early_career = any(k in t_lower for k in [
        "associate scientist", "research associate", "junior", "entry level", "entry-level",
        "trainee", "graduate program", "graduate", "rotational", "fellowship", "wissenschaftliche",
        "scientific collaborator", "r&d chemist", "lab specialist", "laboratory specialist"
    ])
    if is_early_career:
        score += 1
        degree_fit = "Ideal for MSc+Exp"
    elif is_industry_internship:
        score = max(score, 6)
        degree_fit = "Industry Trainee/Intern"
    else:
        degree_fit = "MSc/BSc Suitable"

    # Strict PhD penalty
    if "phd required" in text and "master" not in text and "equivalent" not in text:
        score -= 2
        degree_fit = "Strict PhD Only"

    # Language check
    de_words = len(re.findall(r"\b(und|oder|wir|für|mit|aufgaben|profil)\b", text))
    lang_req = "EN + DE B1/B2 OK" if de_words > 4 else "English (C1)"
    if any(k in text for k in ["verhandlungssicher", "muttersprache", "c1", "c2", "fluent german required"]):
        lang_req = "Fluent DE Required (C1/C2)"
        score -= 1

    # Heuristic score is strictly capped at 6 (or 7 for top match). Never 8, 9, 10!
    score = max(1, min(7, score))
    is_rel = (score >= 6)

    fit_str = f"Relevant {category} duties matching MSc Chemistry and lab toolkit."
    gap_str = "Heuristic fallback evaluation - requires Gemini LLM audit."
    summary = f"🎯 Track: {track} | ✅ Fit: {fit_str} | ⚠️ Gaps: {gap_str}"

    return JobEvaluation(
        is_relevant=is_rel,
        match_score=score,
        role_category=category,
        degree_fit=degree_fit,
        language_req=lang_req,
        track_alignment=track,
        fit_strengths=fit_str,
        career_gaps=gap_str,
        one_line_summary=summary,
        scorer="heuristic",
    )


# ---------------------------------------------------------------------------
# Gemini Flash evaluator (with automatic fallback cascade)
# ---------------------------------------------------------------------------

_DAILY_QUOTA_EXHAUSTED = False

def evaluate_job(client, title: str, company: str, location: str, desc: str, source: str) -> JobEvaluation:
    """Uses Gemini Flash (with automatic cascade and CV/Career matching) for critical job evaluation."""
    global _DAILY_QUOTA_EXHAUSTED
    if _DAILY_QUOTA_EXHAUSTED:
        return evaluate_job_heuristic(title, company, desc, source)

    # Fast guardrail: check foreign locations or hard negative keywords
    t_clean = title.strip()
    loc_clean = (location or "").strip()
    d_clean = (desc or "").strip()
    if cfg.FOREIGN_LOCATIONS_REGEX.search(t_clean) or cfg.FOREIGN_LOCATIONS_REGEX.search(loc_clean):
        return JobEvaluation(
            is_relevant=False, match_score=1, role_category="Other",
            degree_fit="Foreign Location", language_req="N/A",
            track_alignment="Disqualified: Outside Switzerland",
            fit_strengths="None",
            career_gaps="Position is located outside Switzerland.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: None | ⚠️ Gaps: Position located outside Switzerland.",
            scorer="gemini",
        )
    if cfg.NEGATIVE_ROLE_KEYWORDS.search(t_clean):
        return JobEvaluation(
            is_relevant=False, match_score=2, role_category="Other",
            degree_fit="Disqualified Title", language_req="N/A",
            track_alignment="Disqualified: Non-target track",
            fit_strengths="None",
            career_gaps="Executive, legal, patent, IT, logistics, or non-target title.",
            one_line_summary="🎯 Track: Disqualified | ✅ Fit: None | ⚠️ Gaps: Executive, legal, patent, or non-target title.",
            scorer="gemini",
        )

    if not client:
        return evaluate_job_heuristic(title, company, desc, source, location=location)

    desc_clean = d_clean if len(d_clean) >= 30 else f"Position: {title} at {company} in {location}."

    cv_text = cfg.get_candidate_cv()
    career_directions_text = cfg.get_candidate_career_directions()

    prompt = f"""
You are an uncompromising, senior Swiss life sciences career auditor and hiring manager.
Your task is to critically evaluate a job opening against the candidate's exact verified CV and envisioned career tracks.
Be skeptical and rigorous: do NOT flatter or produce polite, generic confirmations. Call out misalignments, domain differences, and scale gaps plainly.

=== CANDIDATE FULL VERIFIED CV ===
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

=== CRITICAL EVALUATION RULES ===

1. RIGOROUS CALIBRATION & SCORING:
   - 9-10 (Exceptional / Dream Fit): Near-perfect alignment with Track 1 (Cleantech/Water R&D), Track 2 (Synthetic Organic / Peptides / CDMO), or Track 3 (Analytical HPLC/MS). Candidate's hands-on lab experience (ETH GLP-1 peptide synthesis, UCT Prague HPLC stationary phase commercialization, Oxyle ion-exchange water treatment) directly covers 80%+ of core duties. Gaps are minor/negligible. Level fits MSc + ~3.5y research experience.
   - 7-8 (Strong Target Match): Strong scientific fit in target CDMO, pharma development, or cleantech. Solid overlap with organic synthesis, chromatography, or water remediation. Has bridgeable gaps (e.g. learning commercial GMP protocols vs academic benchtop, or learning specific matrix preparation).
   - 6 (Viable Baseline): Relevant scientific role (e.g. broad analytical QC, sustainability consulting, entry QA, general lab specialist). Viable and within commute, but deviates slightly from primary tracks or has moderate experience gaps.
   - 4-5 (Poor Fit / Misaligned): Scientifically adjacent but fundamentally misaligned (e.g. heavy biological cell culture, clinical trials, formulation of industrial lubricants/waxes, pure routine administrative documentation). Significant skill gaps.
   - 1-3 (Disqualified / Dealbreakers): Exclude immediately (is_relevant=false). Executive leadership (Director, Head of, VP), legal/patent, academic degrees (PhD student / Doktorand, Master thesis, apprentice EFZ), foreign location (outside Switzerland), or requiring native/C2 German.

2. SPECIFIC INSTRUCTIONS FOR OUTPUT FIELDS:
   - track_alignment: Identify precisely which of Envisioned Tracks 1-5 this advances (e.g. "Track 2: Synthetic Organic & Process Chemistry (Peptides/CDMO)"). If tangential or misaligned, state clearly (e.g. "Tangential: industrial formulation of cleaning products; does not advance core synthetic or cleantech tracks").
   - fit_strengths: Name the EXACT verified techniques and experiences from her CV that match the job duties (e.g. "Direct overlap with ETH Bode group SPPS peptide synthesis, RP-HPLC purification, and LCMS structural elucidation"). Be specific; avoid generic praise.
   - career_gaps: Honestly identify what the candidate lacks. Probe for:
     * Scale & Compliance: Academic / startup benchtop scale vs. commercial industrial GMP plant scale (filter dryers, reactors, validation).
     * Domain Mismatch: Synthetic/analytical chemistry vs. mammalian cell biology, pharmacology, or formulation.
     * Level / Credentials: Demands completed PhD with post-PhD industrial leadership vs. candidate's MSc + 3.5y research experience.
     * Language: Demands German C1/C2 vs. candidate's conversational B1.
     (If gaps are minimal, state: "Minimal gaps: day-to-day duties align directly with candidate's lab toolkit.")
   - one_line_summary: Combine the three dimensions in this exact format:
     "🎯 Track: <track_alignment> | ✅ Fit: <fit_strengths> | ⚠️ Gaps: <career_gaps>"
"""

    models_to_try = [
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.8-flash",
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
                ev = JobEvaluation.model_validate_json(resp.text)
                ev.scorer = "gemini"
                # Enforce structured summary format
                if "🎯 Track:" not in ev.one_line_summary or "✅ Fit:" not in ev.one_line_summary or "⚠️ Gaps:" not in ev.one_line_summary:
                    ev.one_line_summary = f"🎯 Track: {ev.track_alignment} | ✅ Fit: {ev.fit_strengths} | ⚠️ Gaps: {ev.career_gaps}"
                return ev
            except Exception as e:
                err_msg = str(e).lower()
                if "per day limit exceeded" in err_msg:
                    print("  [WARN] Gemini daily free tier quota exceeded. Fast-falling back to heuristic for remainder of run.")
                    _DAILY_QUOTA_EXHAUSTED = True
                    return evaluate_job_heuristic(title, company, desc, source)
                if "429" in err_msg or "resource_exhausted" in err_msg:
                    time.sleep(2 * (attempt + 1))
                    continue
                # For network/timeout, 503, or unavailable, continue to next model in cascade
                continue

    print(f"  [WARN] LLM evaluation failed for '{title[:30]}', using updated heuristic fallback.")
    return evaluate_job_heuristic(title, company, desc, source)


# ---------------------------------------------------------------------------
# Batch re-scorer for existing DB rows
# ---------------------------------------------------------------------------

def rescore_database_jobs(conn: sqlite3.Connection, client, limit: Optional[int] = None) -> None:
    """Re-scores existing jobs stored in chem_jobs.db using the enhanced critical evaluation system."""
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

    print(f"[*] Re-scoring {total} jobs in chem_jobs.db using critical Gemini Flash evaluation...")
    print("    (Fast-path for disqualified titles; paced at 1.5s intervals for active positions)")

    updated = 0
    for i, (jhash, title, company, location, url, source, old_summary) in enumerate(rows, 1):
        t_clean = (title or "").strip()
        loc_clean = (location or "").strip()
        d_clean = (old_summary or "").strip()
        is_fast_disqualified = (
            bool(cfg.FOREIGN_LOCATIONS_REGEX.search(t_clean))
            or bool(cfg.FOREIGN_LOCATIONS_REGEX.search(loc_clean))
            or bool(cfg.NEGATIVE_ROLE_KEYWORDS.search(t_clean))
        )

        desc_to_eval = d_clean
        if not is_fast_disqualified and url and len(d_clean) < 150:
            body = fetch_job_description_body(url, timeout=2.5)
            if body and len(body) > len(desc_to_eval):
                desc_to_eval = body

        ev = evaluate_job(client, title, company, location, desc_to_eval, source)
        cur.execute(
            """UPDATE jobs
               SET match_score = ?, is_relevant = ?, role_category = ?, degree_fit = ?,
                   language_req = ?, summary = ?, scorer = ?
               WHERE job_hash = ?""",
            (
                ev.match_score,
                1 if ev.is_relevant else 0,
                ev.role_category,
                ev.degree_fit,
                ev.language_req,
                ev.one_line_summary,
                ev.scorer,
                jhash,
            ),
        )
        conn.commit()
        updated += 1
        print(f"  [{i}/{total}] {title[:35]} @ {company[:18]} -> {ev.match_score}/10 ({ev.role_category}) [{ev.scorer}]", flush=True)
        if not is_fast_disqualified and i < total:
            time.sleep(1.5)

    print(f"[+] Successfully rescored {updated} jobs in chem_jobs.db!")


def rescore_heuristic_fallbacks(conn: sqlite3.Connection, client) -> int:
    """
    Finds any jobs evaluated with heuristic fallback (scorer = 'heuristic' or legacy summary)
    and re-evaluates them using Gemini to ensure 100% critical audit coverage.
    """
    if not client:
        print("[!] No Gemini client available to rescore heuristic fallbacks.")
        return 0

    cur = conn.cursor()
    cur.execute("""
        SELECT job_hash, title, company, location, url, source, summary, match_score
        FROM jobs
        WHERE scorer = 'heuristic'
           OR summary LIKE '%matching MSc Chemistry, hands-on lab toolkit%'
           OR summary LIKE '%Heuristic fallback evaluation%'
        ORDER BY match_score DESC
    """)
    rows = cur.fetchall()
    if not rows:
        print("[*] No heuristic fallback jobs to rescore. All jobs are Gemini-verified!")
        return 0

    print(f"[*] Found {len(rows)} heuristic fallback jobs. Re-evaluating via Gemini Flash...")
    rescored = 0
    for jhash, title, company, location, url, source, old_summary, old_score in rows:
        desc_to_eval = (old_summary or "").strip()
        if url and len(desc_to_eval) < 150:
            body = fetch_job_description_body(url, timeout=2.5)
            if body and len(body) > len(desc_to_eval):
                desc_to_eval = body

        ev = evaluate_job(client, title, company, location, desc_to_eval, source)
        if ev.scorer == "gemini":
            cur.execute("""
                UPDATE jobs
                SET match_score = ?, is_relevant = ?, role_category = ?, degree_fit = ?,
                    language_req = ?, summary = ?, scorer = 'gemini'
                WHERE job_hash = ?
            """, (
                ev.match_score,
                1 if ev.is_relevant else 0,
                ev.role_category,
                ev.degree_fit,
                ev.language_req,
                ev.one_line_summary,
                jhash,
            ))
            conn.commit()
            rescored += 1
            print(f"  [Rescored Gemini] {title[:35]} @ {company[:18]} -> was {old_score}/10, now {ev.match_score}/10 ({ev.role_category})")
        else:
            # If Gemini still failed, update row with clean conservative heuristic
            cur.execute("""
                UPDATE jobs
                SET match_score = ?, is_relevant = ?, role_category = ?, degree_fit = ?,
                    language_req = ?, summary = ?, scorer = 'heuristic'
                WHERE job_hash = ?
            """, (
                ev.match_score,
                1 if ev.is_relevant else 0,
                ev.role_category,
                ev.degree_fit,
                ev.language_req,
                ev.one_line_summary,
                jhash,
            ))
            conn.commit()
            print(f"  [Kept Heuristic] {title[:35]} @ {company[:18]} -> calibrated heuristic {old_score}/10 -> {ev.match_score}/10")
        time.sleep(1.0)

    print(f"[+] Re-scored {rescored}/{len(rows)} heuristic fallback jobs via Gemini!")
    return rescored
