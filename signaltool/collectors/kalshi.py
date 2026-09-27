"""Kalshi public market data (no key needed for reads). Returned HTTP 429 from this box on every
attempt; kept for normal connections."""
from __future__ import annotations
import pandas as pd
from .. import http
from ..themes import match_themes

API = "https://api.elections.kalshi.com/trade-api/v2/events"


def collect() -> tuple[pd.DataFrame, str]:
    try:
        j = http.get_json(API, params={"limit": 200, "status": "open", "with_nested_markets": "true"}, retries=2)
    except Exception as e:
        return pd.DataFrame(), f"FAILED: {e}"
    rows = []
    for ev in j.get("events", []):
        for m in ev.get("markets", []) or []:
            rows.append({"event": ev.get("title"), "question": m.get("title"), "p_yes": (m.get("last_price") or 0) / 100,
                         "prev": (m.get("previous_price") or 0) / 100, "volume_24h": m.get("volume_24h"),
                         "url": f"https://kalshi.com/markets/{ev.get('event_ticker', '').lower()}",
                         "themes": "|".join(match_themes((m.get("title") or "") + " " + (ev.get("title") or "")))})
    return pd.DataFrame(rows), f"ok ({len(rows)} markets)"
