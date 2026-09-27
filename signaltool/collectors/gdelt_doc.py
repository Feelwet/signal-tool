"""GDELT DOC 2.0 API (free, no key; max 1 request / 5 s). Keyword news-volume timelines.

From this box the API returned HTTP 429 on every call (likely a shared/flagged IP), so the tool
falls back to the GDELT daily event files. Kept here because it works from normal connections.
"""
from __future__ import annotations
import logging
import pandas as pd
from .. import http

log = logging.getLogger(__name__)
API = "https://api.gdeltproject.org/api/v2/doc/doc"


def timeline(query: str, mode="timelinevolraw", timespan="3m") -> pd.Series:
    j = http.get_json(API, params={"query": query, "mode": mode, "timespan": timespan, "format": "json"},
                      retries=1, timeout=40)
    data = j["timeline"][0]["data"]
    s = pd.Series({pd.Timestamp(x["date"][:8]): x["value"] for x in data})
    return s.groupby(level=0).sum()


def collect(queries: dict[str, str]) -> tuple[dict, str]:
    """queries: theme_key -> GDELT query string. Stops at the first failure to stay polite."""
    out = {}
    for k, q in queries.items():
        try:
            out[k] = timeline(q)
        except Exception as e:
            return out, f"FAILED after {len(out)} queries: {e}"
    return out, f"ok ({len(out)} queries)"
