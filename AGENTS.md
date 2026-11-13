# Project: Zurich Chemistry & Cleantech Job Radar

## Overview
`zurich_chem_radar` is an automated daily job discovery, commute calculation, and semantic scoring pipeline written in Python. It finds relevant R&D, Chemistry, Cleantech, Pharma, and Consulting roles within a **60-minute commute of Glattbrugg / Zurich**, deduplicates them in SQLite (`chem_jobs.db`), scores them via Gemini 2.5 Flash (or a deterministic fallback), and renders a zero-dependency interactive HTML tracker (`dashboard.html`).

Core entry point: @zurich_chem_radar.py
Development backlog: @[Roadmap](ROADMAP.md)

---

## Candidate Profile Context (Ground Truth for Scoring & Filtering)
Every scraper filter, keyword regex, and LLM prompt MUST align with this exact candidate profile:
- **Education:** MSc in Organic Chemistry + 2 years of PhD research (Czech Republic) + 6 months visiting researcher at ETH Zurich.
- **Current Experience:** 1-year R&D internship at **Oxyle** (ETH cleantech spin-off in Schlieren; catalytic water treatment / PFAS destruction).
- **Effective Experience Level:** ~3.5 years of hands-on academic + startup R&D experience.
- **Target Titles:** Associate Scientist, Senior Research Associate, R&D Chemist, Organic/Synthetic Chemist, Analytical Chemist (HPLC, LC-MS, GC-MS, NMR), Process Development Chemist, Cleantech R&D Engineer, Scientific Collaborator (*Wissenschaftliche/r Mitarbeiter/in*), Application Specialist, Product Stewardship, Pharma QA/Operations, Life Science Consultant.
- **Qualification Nuance:**
  - **INCLUDE:** Roles requiring BSc/MSc + experience, OR roles stating *"PhD or equivalent industrial/research experience"*.
  - **EXCLUDE:** Academic Postdoc positions, Professorships, apprenticeships (*Lehrstelle Laborant EFZ*), or senior director roles demanding a completed PhD + 5+ years of post-PhD industry leadership.
- **Languages:** Full English proficiency (C1/C2) and B1–B2 German (conversational lab German, reading/writing basic documentation). Exclude roles explicitly requiring native/C2 German for legal/regulatory negotiations.
- **Commute Constraint:** Base is **Glattbrugg (8152 Opfikon) / Zurich North**. Maximum door-to-door commute is **60 minutes** via public transit (SBB API `transport.opendata.ch` for 08:00 arrival) OR car (`DRIVING_OVERRIDES` for industrial parks like Kemptthal, Fehraltorf, Otelfingen, Schlieren, Dübendorf, Winterthur, Schaffhausen, Stein AG, Dottikon). Basel SBB roles (~60 min IC train) are included if hybrid or near the station.

---

## Antigravity Agent Workflow Guidelines
1. **Environment Execution:** Always run Python commands inside `.venv/bin/python` or via `make` targets.
2. **Using Subagents:**
   - When adding a new scraper for a JavaScript-rendered Swiss job board (e.g., `eth-gethired.ch`, `joinup.ch`, `jobs.ch`, or company career pages), use the **browser subagent (`/browser`)** to inspect the DOM or network XHR requests before writing `BeautifulSoup` or JSON-API code.
   - When modifying the HTML template in `generate_html_dashboard()`, verify layout and `localStorage` filtering in `/browser`.
3. **Database Safety:** Never delete `chem_jobs.db` during refactoring unless explicitly asked—it holds historical seen-job hashes (`seen_jobs` / `jobs`) and the SBB commute cache (`commute_cache`). Use `ALTER TABLE` migrations if adding columns.