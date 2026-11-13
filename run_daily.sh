#!/bin/zsh
set -e

# Load user environment variables (GEMINI_API_KEY, PATH, Git credentials)
if [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc" >/dev/null 2>&1 || true
fi

PROJECT_DIR="/Users/vnahodil/dev/job_hunt"
cd "$PROJECT_DIR"

echo "==========================================" >> "$PROJECT_DIR/radar.log"
echo "Radar run started at: $(date)" >> "$PROJECT_DIR/radar.log"
echo "==========================================" >> "$PROJECT_DIR/radar.log"

# Run radar pipeline and auto-publish to GitHub Pages
"$PROJECT_DIR/.venv/bin/python" zurich_chem_radar.py \
    --skip-spinoff-crawl \
    --publish \
    --notify \
    --no-browser >> "$PROJECT_DIR/radar.log" 2>&1

echo "Radar run completed successfully at: $(date)" >> "$PROJECT_DIR/radar.log"
