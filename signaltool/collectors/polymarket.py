"""Polymarket public Gamma API (no key): live geopolitical event probabilities and their moves.
Prices are market-implied probabilities (0-1) of 'Yes'. Not available to trade from all
jurisdictions - used here purely as information."""
from __future__ import annotations
import json, re
import pandas as pd
from .. import http
from ..themes import match_themes

GAMMA = "https://gamma-api.polymarket.com/events"
# local races rarely move markets -> not matched to themes
LOCAL = re.compile(r"mayor|mayoral|governor|gubernatorial|city council|state senate|state house|assembly district|primary|sheriff|attorney general", re.I)
SPORTS = re.compile(r"\bwin on \d{4}-|\bvs\.?\s|\bFIFA\b|\bUEFA\b|\bNFL\b|\bNBA\b|\bNHL\b|\bMLB\b|Premier League|World Cup|"
                    r"Champions League|\bO/U\b|\bspread\b|\bgoals?\b|\bmatch\b|Grand Prix|\bseries\b|\bSuper Bowl\b|\bopen\b.*\btennis", re.I)


def _rows(events):
    for ev in events:
        for m in ev.get("markets", []):
            if m.get("closed") or not m.get("active", True):
                continue
            try:
                prices = json.loads(m.get("outcomePrices") or "[]")
                p_yes = float(prices[0]) if prices else None
            except Exception:
                p_yes = None
            q = m.get("question") or ""
            if SPORTS.search(q) or SPORTS.search(ev.get("title") or ""):
                continue
            local = bool(LOCAL.search(q))
            yield {"event": ev.get("title"), "question": q, "p_yes": p_yes,
                   "chg_1d": m.get("oneDayPriceChange"), "chg_1w": m.get("oneWeekPriceChange"),
                   "chg_1m": m.get("oneMonthPriceChange"),
                   "volume_24h": float(m.get("volume24hr") or 0), "volume": float(m.get("volumeNum") or m.get("volume") or 0),
                   "liquidity": float(m.get("liquidityNum") or 0), "end": m.get("endDate"),
                   "url": f"https://polymarket.com/event/{ev.get('slug')}",
                   "themes": "" if local else "|".join(match_themes(q + " " + (ev.get("title") or "")))}


def collect() -> tuple[pd.DataFrame, str]:
    evs = []
    try:
        for params in ({"tag_slug": "geopolitics"}, {"tag_slug": "world"}, {}, {"tag_slug": "politics"},
                       {"tag_slug": "economy"}):
            for off in (0, 100):
                evs += http.get_json(GAMMA, params={**params, "closed": "false", "limit": 100, "offset": off,
                                                    "order": "volume24hr", "ascending": "false"})
    except Exception as e:
        if not evs:
            return pd.DataFrame(), f"FAILED: {e}"
    df = pd.DataFrame(list(_rows(evs))).drop_duplicates("question")
    # markets resolving within 2 days swing to 0/1 mechanically -> exclude from move-based signals
    end = pd.to_datetime(df["end"], utc=True, errors="coerce")
    df["resolving_soon"] = end < pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2)
    for c in ("chg_1d", "chg_1w", "chg_1m"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, f"ok ({len(df)} open markets, {int((df['themes'] != '').sum())} matched to themes)"
