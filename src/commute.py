"""SBB commute estimation engine with driving overrides and SQLite cache."""

import re
import sqlite3
import urllib.parse

import requests
import pandas as pd

from src.config import cfg


def get_commute_info(conn: sqlite3.Connection, location_str: str) -> tuple[int, str]:
    """Returns (minutes, mode_label) from HOME_ORIGIN using overrides + SBB API."""
    if not location_str or pd.isna(location_str):
        return 35, "CH (Unspecified)"

    loc_lower = str(location_str).lower().strip()
    if loc_lower in {"switzerland", "schweiz", "suisse", "remote", "hybrid"}:
        return 30, "CH / Hybrid"

    # Clean city token (e.g. "Schlieren, Zurich, Switzerland" -> "schlieren")
    city_token = re.split(r"[,/|-]", loc_lower)[0].strip()
    city_token = re.sub(r"\b\d{4}\b", "", city_token).strip()

    # 1. Check fast driving/local overrides
    for town, mins in cfg.DRIVING_OVERRIDES.items():
        if town in loc_lower:
            mode = "SBB/Car" if mins <= 25 else "Car/SBB"
            return mins, mode

    # 2. Check SQLite cache
    cur = conn.cursor()
    cur.execute("SELECT minutes, mode FROM commute_cache WHERE location = ?", (city_token,))
    cached = cur.fetchone()
    if cached:
        return cached[0], cached[1]

    # 3. Query SBB transport.opendata.ch API for 08:00 arrival
    mins, mode = 999, "SBB"
    try:
        url = (
            f"http://transport.opendata.ch/v1/connections?"
            f"from={urllib.parse.quote(cfg.HOME_ORIGIN)}&"
            f"to={urllib.parse.quote(city_token)}&"
            f"time=08:00&isArrivalTime=1&limit=1"
        )
        r = requests.get(url, headers=cfg.HEADERS, timeout=6)
        if r.ok:
            conns = r.json().get("connections", [])
            if conns:
                dur = conns[0].get("duration", "00d01:30:00")
                days, hms = dur.split("d")
                hh, mm, _ = map(int, hms.split(":"))
                mins = int(days) * 1440 + hh * 60 + mm
                mode = "SBB Train"
    except Exception:
        mins, mode = 50, "Est."

    cur.execute("INSERT OR REPLACE INTO commute_cache VALUES (?, ?, ?)", (city_token, mins, mode))
    conn.commit()
    return mins, mode
