"""Lightweight secondary pass to fetch clean job description text from direct vacancy URLs."""

import json
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

        # Check for Phenom People embedded JSON (e.g. Givaudan)
        if "phApp.ddo" in r.text:
            matches = re.findall(r"phApp\.ddo\s*=\s*({.*?});\s*phApp", r.text, re.DOTALL)
            if matches:
                try:
                    data = json.loads(matches[0])
                    job_desc = data.get("jobDetail", {}).get("data", {}).get("job", {}).get("description", "")
                    if job_desc:
                        desc_soup = BeautifulSoup(job_desc, "html.parser")
                        clean = " ".join(desc_soup.stripped_strings)
                        if len(clean) > 100:
                            return clean[:6000]
                except Exception:
                    pass

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
