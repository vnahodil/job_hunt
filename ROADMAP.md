# Development Roadmap (`zurich_chem_radar`)

Use these milestones with the Antigravity agent in VS Code (`Cmd + L`).

## Milestone 1: Modularize Codebase & YAML Config ✅
- [x] Extract `WORKDAY_TARGETS`, `DIRECT_CAREER_PAGES`, `DRIVING_OVERRIDES`, and `AGGREGATOR_QUERIES` out of `zurich_chem_radar.py` into a clean `config/targets.yaml` file.
- [x] Split `zurich_chem_radar.py` into a clean package (`src/scrapers/`, `src/commute.py`, `src/evaluator.py`, `src/dashboard.py`) while keeping `zurich_chem_radar.py` as the CLI entry wrapper.

## Milestone 2: Scraper Reliability, Bug Fixes & Anti-Noise Filtering ✅
- [x] Fix Refline URLs for Eawag & Empa (`?form.buttons.listAll=1&target=overview`) to discover 40+ active institute roles.
- [x] Fix Indeed/JobSpy location parameter (`location="Zurich"`) to unblock Swiss aggregator discovery.
- [x] Add strict link hygiene in `career_pages.py`: reject marketing links, product pages (e.g. synthetic diesel), images, and generic navigation menus.
- [x] Purge historical phantom jobs from `chem_jobs.db` while preserving commute cache and legitimate roles.

## Milestone 3: Add Native `jobs.ch` REST API Scraper ✅
- [x] Implement `src/scrapers/jobs_ch.py` using `https://www.jobs.ch/api/v1/public/search` for rapid, zero-browser discovery across Swiss industry, CDMOs, and SMEs.
- [x] Add targeted search terms (`organic chemistry`, `chemist`, `analytical chemistry`, `laborant`, `cleantech`, `pfas`).
- [x] Wire `jobs.ch` into `zurich_chem_radar.py` orchestrator and `config/targets.yaml`.

## Milestone 4: Deep Description Fetching & Precision Gemini Scoring ✅
- [x] Add lightweight secondary pass that fetches clean job description text for newly discovered vacancy URLs.
- [x] Strip boilerplate (`<nav>`, `<footer>`, `<script>`) to pass full text to `evaluate_job()`.
- [x] Enforce degree fit (MSc + 3.5y research/cleantech exp vs. strict academic PhD postdocs) and language fit (EN / DE B1-B2 vs. C2).

## Milestone 5: 1-Click Tailored CV/Cover Letter Prompt in Dashboard ✅
- [x] Add "Copy Tailoring Prompt" button on each row in `dashboard.html` to generate an immediate LLM prompt with job title, company, summary, and candidate profile for fast application tailoring.

## Milestone 6: LinkedIn, myScience & Swiss Industry Expansion ✅
- [x] Re-enable LinkedIn in `jobspy_aggregator.py` with calibrated `location="Zurich, Switzerland"` and independent error shielding.
- [x] Add dedicated `src/scrapers/myscience.py` for direct research and university spin-off discovery across Switzerland.
- [x] Integrate high-priority CDMO & Chemical Workday APIs (**Arxada**, **Siegfried**).
- [x] Add curated direct career page integrations with advanced ATS support (**Gloor & Lang** via Starhunter, **Bachem** via SuccessFactors, **Carbogen Amcis**, **Chemspeed Technologies** via iCIMS).
- [x] Upgrade Gemini LLM evaluation model cascade (`gemini-3.8-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`) to prevent daily free-tier quota interruptions.

## Milestone 7: Direct Startup APIs, Life Science Work, SCS & Consulting Feeds ✅
- [x] Implement `src/scrapers/startup_apis.py` supporting Recruitee (**Climeworks**), Teamtailor (**Neustark**), Lever (**ANYbotics**), and Greenhouse (**Numab Therapeutics**).
- [x] Implement `src/scrapers/lifesciencework.py` for specialized Swiss biotech, pharma, and CDMO positions across Basel, Zurich, Zug, and surrounding cantons.
- [x] Implement `src/scrapers/scs.py` for Swiss Chemical Society (`scg.ch/jobs`) member directory and partner career pages (**Buchiglas Uster**).
- [x] Integrate **PwC Switzerland** Life Sciences & Sustainability Consulting via Workday CaaS API (`pwc.wd3.myworkdayjobs.com`).
- [x] Expand LinkedIn, Indeed, and `jobs.ch` queries with specialized consulting practices (**Capgemini Engineering**, **Deloitte Life Sciences**, **Life Sciences Consultant**, **Sustainability Consultant**) and staffing agencies (**nemensis**, **gi life sciences**, **kelly scientific**, **gloor lang**).

## Milestone 8: Daily Notification Delivery (Email Digest) ✅
- [x] Implement `src/notify.py` with multi-part MIME (rich HTML + fallback text) email digests.
- [x] Wire automatic email delivery via Gmail SMTP (`--notify` / `--test-email`) into `zurich_chem_radar.py` and `run_daily.sh`.
- [x] Filter for high-match positions (`match_score >= 7`) with direct dashboard link (`https://vnahodil.github.io/job_hunt/`).
- [x] Safe local `.env` credential management (`.gitignore` protected).

## Milestone 9: Full CV Matching, Envisioned Career Directions & Ingestion Guardrails ✅
- [x] Ingestion Guardrails: Block foreign positions (Boston, USA, UK, Germany) and senior executive / non-lab titles (Director, Head of, VP, Partner, Patent Attorney, Legal Counsel, PhD studentships) at the scraper level.
- [x] Candidate Profile as Free Text: Store complete CV (`config/candidate/cv.txt`) and envisioned career trajectories (`config/candidate/career_directions.txt`) as clean, easily editable plain text.
- [x] Upgraded Gemini Evaluator: Feed full CV + career tracks into Gemini prompt, extracting track alignment, CV skill overlap, seniority suitability, and calibrated 1-10 match score.
- [x] Database Sanitation: Purged 159 legacy heuristic phantom jobs (generic "role at..." summaries) and foreign/executive positions from `chem_jobs.db`.
- [x] Dashboard Quality Floor: Enforced strict quality floor (`match_score >= 6 AND is_relevant = 1`) and added Score Filter dropdown defaulting to Top Fits Only (7+).
- [x] Published: Re-rendered clean dashboard and deployed to GitHub Pages without triggering any emails.
