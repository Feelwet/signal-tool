"""OFAC 'Recent Actions' (US Treasury sanctions) scraped from the public listing page (no key).
The SDN list itself is downloadable as CSV from sanctionslistservice.ofac.treas.gov."""
from __future__ import annotations
import html, re
import pandas as pd
from .. import http

URL = "https://ofac.treasury.gov/recent-actions"
ROW = re.compile(r'<a href="(/recent-actions/\d{8}[^"]*)"[^>]*>([^<]+)</a></div></div><div><div[^>]*>\s*([A-Z][a-z]+ \d{1,2}, \d{4})')


def parse(page_html: str) -> list[dict]:
    return [{"url": "https://ofac.treasury.gov" + u, "title": html.unescape(t).strip(),
             "date": pd.to_datetime(d, format="%B %d, %Y")} for u, t, d in ROW.findall(page_html)]


def collect(pages=12) -> tuple[pd.DataFrame, str]:
    rows = []
    try:
        for p in range(pages):
            rows += parse(http.get(URL, params={"page": p} if p else None, cache_hours=6).text)
    except Exception as e:
        if not rows:
            return pd.DataFrame(), f"FAILED: {e}"
    df = pd.DataFrame(rows).drop_duplicates("url")
    parts = df["title"].str.lower().str.split(";")
    df["designations"] = parts.map(lambda ps: any("designation" in x and "removal" not in x for x in ps))
    df["relief"] = parts.map(lambda ps: any(("removal" in x) or ("expiration" in x) for x in ps))
    return df, f"ok ({len(df)} actions since {df['date'].min().date()})"
