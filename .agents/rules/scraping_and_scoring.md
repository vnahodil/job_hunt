---
trigger: always_on
description: Architectural invariants, SDK rules, and anti-blocking constraints for zurich_chem_radar
---

# Mandatory Engineering Constraints

1. **Google GenAI SDK (`google-genai` only):**
   - Always use `from google import genai` and `client.models.generate_content(model="gemini-2.5-flash", ...)`.
   - NEVER import the deprecated `google.generativeai` package.
   - Always maintain `evaluate_job_heuristic()` as a zero-API-key fallback whenever `GEMINI_API_KEY` is unset or raises a quota/network error.

2. **JobSpy Installation & Rate-Limiting:**
   - `python-jobspy` must be installed from `git+https://github.com/speedyapply/JobSpy.git` (not PyPI) to retain 2026 LinkedIn/Indeed parser fixes.
   - To prevent residential IP blocks on LinkedIn, never set `results_wanted` above `35` per query or `hours_old` above `72` on automated daily runs.

3. **ETH Spin-Off & Swiss Portal URLs:**
   - Do NOT use `jobs.entrepreneurship.ethz.ch` (domain does not exist).
   - Official ETH spin-off discovery uses `https://entrepreneurship.ethz.ch/startup-stories/explore-startup-portraits-and-success-stories/uebersicht-eth-spin-offs.html` filtered by departments `D-CHAB`, `D-MATL`, `D-BSSE`, `D-BAUG`, `D-USYS`, `D-BIOL`, `D-HEST`, `D-EAPS`.
   - Federal institute jobs use Refline endpoints (`apply.refline.ch/673277` for Eawag, `apply.refline.ch/673276` for Empa) and `psi.ch/en/hr/job-opportunities` for PSI.

4. **SBB API Etiquette (`transport.opendata.ch`):**
   - Always check `DRIVING_OVERRIDES` first, then the SQLite `commute_cache` table, before making an HTTP GET to `http://transport.opendata.ch/v1/connections`.
   - Never make uncached SBB API calls inside tight loops without caching the normalized city name.

5. **Dashboard Self-Containment:**
   - `dashboard.html` must remain a single, zero-server HTML file using vanilla CSS/JS and `localStorage` (`appliedJobs`, `hiddenJobs`) so it can be opened directly via `file://`.