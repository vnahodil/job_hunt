# 🧪 Zurich Chemistry & Cleantech Job Radar

Automated daily job discovery, SBB/car commute calculator, and LLM profile-fit evaluator tailored for an **MSc Organic Chemist with academic PhD + ETH + Swiss Cleantech (Oxyle) R&D experience** commuting from **Glattbrugg / Zurich**.

## Features
- **Multi-Tier Ingestion:**
  1. **Broad Aggregators:** Scrapes Indeed Switzerland, LinkedIn, and Google Jobs concurrently via `JobSpy`.
  2. **Swiss Federal Institutes:** Scrapes **Eawag** (Dübendorf), **Empa** (Dübendorf), and **PSI** (Villigen) via Refline & PSI portals.
  3. **Official ETH Spin-Off Ecosystem:** Scrapes **Bio-Technopark Schlieren** and crawls the official **ETH Spin-off Directory** filtered by Chemistry (`D-CHAB`), Materials (`D-MATL`), Biosystems (`D-BSSE`), and Environmental/Civil (`D-BAUG`, `D-USYS`) departments.
  4. **Direct Workday JSON APIs:** Queries Roche, Novartis, Lonza, Givaudan (Kemptthal), and Takeda (Glattpark) without a headless browser.
  5. **Curated Local Watchlist:** Monitors 15+ local targets (Oxyle, Climeworks, Synhelion, SpiroChem, Philochem Otelfingen, Dottikon ES, CellX, Sika, Halag, Celerion, etc.).
- **Smart Commute Engine:** Combines a fast driving override table (for Zurich North/East/West industrial parks) with the live **SBB OpenData API** (`transport.opendata.ch`) for an `08:00` arrival from Glattbrugg.
- **Dual-Mode Scoring:** Uses **Gemini 2.5 Flash** (`google-genai` Structured Outputs) when `GEMINI_API_KEY` is provided, or falls back automatically to a deterministic Chemistry/Cleantech heuristic scorer.
- **Zero-Server HTML Dashboard:** Generates `dashboard.html` with live search, category/commute filters, and persistent `Applied` / `Dismiss` buttons stored in `localStorage`.

---

## Quick Start

### 1. Setup Environment
```bash
make setup
cp .env.example .env
# Optional: Add your free Google AI Studio key to .env