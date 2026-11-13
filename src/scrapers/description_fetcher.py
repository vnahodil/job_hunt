"""Lightweight secondary pass to fetch clean job description text from direct vacancy URLs."""

import re
import requests
from bs4 import BeautifulSoup

from src.config import cfg


def fetch_job_description_body(url: str, timeout: int = 6) -> str:
    """
    Fetches clean text body from a job detail URL.
    Strips boilerplate (<nav>, <footer>, <header>, <script>, <style>).
    """
    if not url or not url.startswith("http"):
        return ""

    try:
        r = requests.get(url, headers=cfg.HEADERS, timeout=timeout)
        if not r.ok:
            return ""

        soup = BeautifulSoup(r.text, "lxml")

        # Decompose unwanted elements
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()

        # Prioritize job body container if present
        target_container = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"(job[-_]?desc|vacancy|posting|content|detail|offer)", re.I))
            or soup.body
        )

        if target_container:
            text = " ".join(target_container.stripped_strings)
            # Return up to 6000 characters (sufficient for full job duties + requirements)
            return text[:6000]

        return " ".join(soup.stripped_strings)[:6000]
    except Exception:
        return ""
