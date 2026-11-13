"""SQLite database initialization and job hashing utilities."""

import re
import hashlib
import sqlite3

from src.config import cfg


def init_db() -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure tables exist."""
    conn = sqlite3.connect(cfg.DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_hash TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            source TEXT,
            commute_mins INTEGER,
            commute_mode TEXT,
            match_score INTEGER,
            is_relevant INTEGER,
            role_category TEXT,
            degree_fit TEXT,
            language_req TEXT,
            summary TEXT,
            date_found TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS commute_cache (
            location TEXT PRIMARY KEY,
            minutes INTEGER,
            mode TEXT
        )
    """)
    conn.commit()
    return conn


def make_job_hash(company: str, title: str) -> str:
    """Deterministic hash for deduplication (company + title)."""
    norm_co = re.sub(r"[^a-z0-9]", "", str(company).lower())
    norm_ti = re.sub(r"[^a-z0-9]", "", str(title).lower())
    return hashlib.sha256(f"{norm_co}::{norm_ti}".encode("utf-8")).hexdigest()
