# Development Roadmap (`zurich_chem_radar`)

Use these milestones with the Antigravity agent in VS Code (`Cmd + L`).

## Milestone 1: Modularize Codebase & YAML Config
- [ ] Extract `WORKDAY_TARGETS`, `DIRECT_CAREER_PAGES`, `DRIVING_OVERRIDES`, and `AGGREGATOR_QUERIES` out of `zurich_chem_radar.py` into a clean `config/targets.yaml` file.
- [ ] Split `zurich_chem_radar.py` into a clean package (`src/scrapers/`, `src/commute.py`, `src/evaluator.py`, `src/dashboard.py`) while keeping `zurich_chem_radar.py` as the CLI entry wrapper.

## Milestone 2: Deep Description Fetching for Direct/Refline Links
- [ ] Currently, `fetch_eawag_empa_psi()` and `fetch_curated_career_pages()` score roles primarily on anchor text + company metadata.
- [ ] Add a lightweight secondary pass that fetches the full HTML body of newly discovered (unseen) direct job URLs, strips boilerplate (`<nav>`, `<footer>`, `<script>`), and passes the clean job description text to `evaluate_job()` for much higher precision on degree and German requirements.

## Milestone 3: Add `jobs.ch`, `eth-gethired.ch`, and `joinup.ch` Scrapers
- [ ] Use Antigravity's `/browser` subagent or `Playwright` / JSON state extraction to add a scraper module for:
  1. `https://www.jobs.ch/en/vacancies/?term=chemistry` (last 24h filter)
  2. `https://eth-gethired.ch/en/jobs/`
  3. `https://joinup.ch/` (ETH Entrepreneur Club startup board)

## Milestone 4: Daily Notification Delivery (Telegram / Email Digest)
- [ ] Add an optional notifier module (`src/notify.py`) triggered when `--notify` is passed.
- [ ] Send a daily summary of *only newly discovered roles from the current run* with `match_score >= 7` via a Telegram Bot webhook (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`) or Gmail SMTP.

## Milestone 5: 1-Click Cover Letter & CV Bullet Generator in Dashboard
- [ ] Add a button on each row in `dashboard.html` ("Copy Tailoring Prompt") that copies a pre-formatted prompt containing the job title, company, and summary to the clipboard so she can generate tailored CV bullet points immediately.