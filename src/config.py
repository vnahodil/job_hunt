"""
Loads all configuration from config/targets.yaml and environment variables.

Usage:
    from src.config import cfg
    print(cfg.HOME_ORIGIN)
    print(cfg.DRIVING_OVERRIDES)
    print(cfg.WORKDAY_TARGETS)
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Any

import yaml


# ---------------------------------------------------------------------------
# Locate the project root (parent of src/) and config/targets.yaml
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "targets.yaml"


def _load_env_file() -> None:
    """Reads key=value pairs from .env in project root if it exists, without overwriting existing env vars."""
    env_file = _PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v


def _load_yaml() -> dict:
    """Read and parse the YAML config file."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {_CONFIG_PATH}\n"
            "Create config/targets.yaml (see ROADMAP.md)."
        )
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class Config:
    """Immutable runtime configuration populated from YAML + env vars."""

    def __init__(self) -> None:
        _load_env_file()
        raw = _load_yaml()

        # --- Commute ---
        commute = raw.get("commute_settings", {})
        self.HOME_ORIGIN: str = os.getenv("JOB_ORIGIN", commute.get("home_origin", "Glattbrugg"))
        self.MAX_COMMUTE_MINS: int = int(os.getenv("MAX_COMMUTE_MINS", commute.get("max_commute_mins", 60)))
        self.DRIVING_OVERRIDES: Dict[str, int] = commute.get("driving_overrides", {})

        # --- Gemini ---
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

        # --- Paths ---
        self.PROJECT_ROOT: Path = _PROJECT_ROOT
        self.DB_PATH: str = str(_PROJECT_ROOT / "chem_jobs.db")
        self.REPORT_PATH: str = str(_PROJECT_ROOT / "dashboard.html")
        self.INDEX_PATH: str = str(_PROJECT_ROOT / "index.html")
        self.DOCS_DIR: Path = _PROJECT_ROOT / "docs"
        self.DOCS_INDEX_PATH: str = str(self.DOCS_DIR / "index.html")

        # --- HTTP ---
        self.HEADERS: Dict[str, str] = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,de-CH;q=0.8,de;q=0.7",
        }

        # --- Email Notifications ---
        notify = raw.get("notifications", {})
        self.NOTIFY_ENABLED: bool = bool(notify.get("enabled", True))
        self.MIN_NOTIFY_SCORE: int = int(os.getenv("MIN_NOTIFY_SCORE", notify.get("min_score", 7)))
        self.MAX_EMAIL_JOBS: int = int(os.getenv("MAX_EMAIL_JOBS", notify.get("max_email_jobs", 6)))
        self.SMTP_HOST: str = os.getenv("SMTP_HOST", notify.get("smtp_host", "smtp.gmail.com"))
        self.SMTP_PORT: int = int(os.getenv("SMTP_PORT", notify.get("smtp_port", 587)))
        self.SMTP_USER: str = os.getenv("SMTP_USER", notify.get("smtp_user", ""))
        self.SMTP_PASS: str = os.getenv("SMTP_PASS", "")
        env_recipients = [r.strip() for r in os.getenv("NOTIFY_RECIPIENTS", "").split(",") if r.strip()]
        self.NOTIFY_RECIPIENTS: List[str] = env_recipients or notify.get("recipients", [])
        self.DASHBOARD_URL: str = os.getenv(
            "DASHBOARD_URL",
            notify.get("dashboard_url", "https://vnahodil.github.io/job_hunt/"),
        )

        # --- Aggregator ---
        self.AGGREGATOR_QUERIES: List[str] = raw.get("aggregator_queries", [])
        self.JOBS_CH_QUERIES: List[str] = raw.get("jobs_ch_queries", [])
        self.MYSCIENCE_QUERIES: List[str] = raw.get("myscience_queries", [])

        # --- Workday ---
        self.WORKDAY_TARGETS: List[Dict[str, Any]] = raw.get("workday_targets", [])

        # --- Direct Startup APIs ---
        self.STARTUP_API_TARGETS: List[Dict[str, Any]] = raw.get("startup_api_targets", [])

        # --- Institutes & Hubs ---
        hubs = raw.get("institutes_and_hubs", {})
        self.ETH_SPINOFF_TABLE_URL: str = hubs.get(
            "eth_spinoff_directory_url",
            "https://entrepreneurship.ethz.ch/startup-stories/"
            "explore-startup-portraits-and-success-stories/uebersicht-eth-spin-offs.html",
        )
        self.ETH_TARGET_DEPTS: set = set(hubs.get("eth_target_departments", []))
        self.INSTITUTE_PORTALS: List[Dict[str, str]] = hubs.get("portals", [])

        # --- Direct Career Pages ---
        self.DIRECT_CAREER_PAGES: List[Dict[str, str]] = raw.get("direct_career_pages", [])

        # --- Keyword Filters ---
        filters = raw.get("filters", {})
        self.POSITIVE_ROLE_KEYWORDS = re.compile(
            filters.get(
                "positive_regex",
                r"(chem|scien|research|r&d|analyt|synthe|labor|lab\b|process|formulat|"
                r"cataly|pfas|water|material|polymer|quality|qa\b|qc\b|regulatory|application|"
                r"consultant|engineer|wissenschaft|mitarbeiter|specialist|associate|intern)",
            ),
            re.IGNORECASE,
        )
        self.NEGATIVE_ROLE_KEYWORDS = re.compile(
            filters.get(
                "negative_regex",
                r"(accountant|finance|payroll|legal counsel|receptionist|chauffeur|"
                r"hr manager|recruiter|full stack|frontend|ios developer|android|lehrstelle|schnupper)",
            ),
            re.IGNORECASE,
        )


# ---------------------------------------------------------------------------
# Module-level singleton — import as `from src.config import cfg`
# ---------------------------------------------------------------------------
cfg = Config()
