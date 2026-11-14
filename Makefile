.PHONY: run publish dashboard scrape test clean

# Run full discovery pipeline and automatically publish to GitHub Pages
run:
	.venv/bin/python zurich_chem_radar.py --skip-spinoff-crawl --publish

# Fast run without slow aggregators
fast:
	.venv/bin/python zurich_chem_radar.py --skip-spinoff-crawl --skip-jobspy --publish

# Regenerate dashboard/index from SQLite database and publish to GitHub Pages (no scraping)
publish:
	.venv/bin/python zurich_chem_radar.py --dashboard-only --publish --no-browser

# Regenerate dashboard locally without publishing
dashboard:
	.venv/bin/python zurich_chem_radar.py --dashboard-only

# Rescore all database jobs with Gemini and publish
rescore:
	.venv/bin/python zurich_chem_radar.py --rescore --publish

# Test sending email digest with top recent jobs
test-email:
	.venv/bin/python zurich_chem_radar.py --test-email

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
