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
    """Uses Gemini 3.8 Flash (falling back to 3.5 Flash or heuristic)."""
    if not client:
        return evaluate_job_heuristic(title, company, desc, source)

    desc_clean = desc.strip() if desc else ""
    if len(desc_clean) < 30:
        desc_clean = f"Position: {title} at {company} in {location}."

    prompt = f"""
    Evaluate this Swiss job opening for the following candidate living in the Zurich area:
    - Education: Master's (MSc) in Organic Chemistry + 2 years of PhD research in Czech Republic + 6 months exchange at ETH Zurich.
    - Current Experience: 1-year research internship at Oxyle (ETH cleantech spin-off in Schlieren, catalytic water treatment / PFAS destruction).
    - Total hands-on R&D experience: ~3.5 years.
    - Target Career Level: Entry-level & early-career professional positions, associate scientist roles, and industry graduate/trainee programs.
    - Languages: Full English proficiency (C1/C2), B1-B2 German (conversational lab German).
    - Target Roles: Associate Scientist, Senior Research Associate, R&D Chemist, Organic/Synthetic Chemist, Analytical Chemist (HPLC, LC-MS, GC-MS, NMR), Process Development Chemist, Cleantech R&D Engineer, Scientific Collaborator (Wissenschaftliche/r Mitarbeiter/in), Application Specialist, Product Stewardship, Pharma QA/Operations, Life Science Consultant.

    STRICT FILTERING & SCORING RULES:
    1. EXCLUDE & HEAVILY PENALIZE (is_relevant=false, match_score 1-3):
       - Master thesis / Bachelor thesis projects (she already holds an MSc)
       - Academic PhD positions / Doctoral studentships (she already completed MSc + 2y PhD, not seeking a 4-year academic doctorate)
       - Student Praktikum / University student internships aimed at enrolled students (e.g. Eawag lake ecology internship)
       - Academic Postdoc positions (Postdoctoral Fellow / Postdoc) or University Professorships
       - Apprenticeships (Lehrstelle, Laborant EFZ)
       - Pure non-chemical engineering (mechanical, electrical, software/IT roles)
       - Non-chemical biology/fieldwork (ecology, zoology, biodiversity, fish ecology)
       - Senior Director / Executive leadership demanding completed PhD + 5+ years post-PhD industry management
       - Roles explicitly demanding native/C2 German for legal/contract negotiations
    2. FAVOR & BOOST (is_relevant=true, match_score 8-10):
       - Entry-level and early-career professional roles: Associate Scientist, Research Associate, Chemist, R&D Specialist
       - Industry graduate programs, rotational programs, and corporate trainee programs
       - High-value industry R&D internships (e.g. Roche 12-month LC-MS Bioanalytics internship, Syngenta chemistry research internship) designed as industry career entry points
       - Roles matching her hands-on skills: Organic synthesis, reaction scouting, catalysis, analytical chemistry (HPLC, LC-MS, NMR), water treatment / PFAS / cleantech R&D
       - Roles requiring BSc/MSc + experience, OR roles stating "PhD or equivalent industrial/research experience"
       - Working language English or German B1-B2 acceptable.

    Job Title: {title}
    Company: {company}
    Location: {location}
    Source: {source}
    Description: {desc_clean[:5000]}
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
                    time.sleep(4 * (attempt + 1))
                    continue
                if "503" in err_msg or "unavailable" in err_msg or "not_found" in err_msg:
                    # Model spike or unavailable -> continue to next model in cascade
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
