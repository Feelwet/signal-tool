"""Felles lukket kurstabell for siden og learn_raw (AnalBot 27.11).

Én repair kjøres før både learnloop.record og site.build. Repairen godtar bare barer som er
lukket (stengetid + 30 min). Etter repair oppdateres snapshot-stats fra den samme lukkede
serien; learnloop og siden leser derfra og laster ikke ned kursene på nytt.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from . import closedbars as CB
from . import freshness as FR

log = logging.getLogger(__name__)

STAT_KEYS = [
    "close", "ret_1d", "ret_5d", "ret_20d", "ret5_z", "vol5_z", "vol_ratio_5d",
    "sma50", "maxdd20", "adv20", "vol_1d",
]


def _f(x):
    try:
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else round(x, 4)
    except (TypeError, ValueError):
        return None


def _now(now=None):
    if now is not None:
        return now
    return datetime.now(ZoneInfo("Europe/Oslo"))


def last_bar_date(df) -> str | None:
    try:
        s = df["Close"].dropna()
        return str(pd.Timestamp(s.index[-1]).date()) if len(s) else None
    except Exception:
        return None


def closed_frame(df: pd.DataFrame, ticker: str, now=None) -> pd.DataFrame:
    """Behold bare rader der handelsdagen er lukket (stengetid + 30 min) ved `now`."""
    now = _now(now)
    if df is None or not len(df):
        return df if df is not None else pd.DataFrame()
    keep = []
    for ts in df.index:
        d = str(pd.Timestamp(ts).date())
        if CB.ok(ticker, d, now):
            keep.append(ts)
    return df.loc[keep] if keep else df.iloc[0:0]


def closed_frames(frames: dict, now=None) -> dict:
    now = _now(now)
    out = {}
    for t, df in (frames or {}).items():
        cf = closed_frame(df, t, now)
        if cf is not None and len(cf):
            out[t] = cf
    return out


def is_lagging(ticker: str, df, now=None) -> bool:
    """True når siste *lukkede* bar er eldre enn forventet handelsdag."""
    now = _now(now)
    exp = FR.expected_session(ticker, now)
    last = last_bar_date(closed_frame(df, ticker, now))
    return bool(exp and last and last < exp.isoformat())


def stats_from_frame(df: pd.DataFrame) -> dict:
    from .collectors.markets import short_stats, ticker_stats
    try:
        n = int(df["Close"].dropna().shape[0])
    except Exception:
        n = 0
    return ticker_stats(df) if n > 30 else short_stats(df)


def as_pairs(frames: dict | None) -> dict:
    """{ticker: [(dato, close), ...]} som site/pricechart forventer, fra de felles rammene."""
    out = {}
    for t, df in (frames or {}).items():
        if df is None or not len(df):
            continue
        try:
            s = df["Close"].dropna()
        except Exception:
            continue
        out[str(t)] = [(str(pd.Timestamp(k).date()), float(v)) for k, v in s.items()]
    return out


def index_closes(frames: dict | None) -> dict:
    """{ticker: {dato: close}} for indekser i de felles rammene."""
    out = {}
    for t, df in (frames or {}).items():
        if df is None or not len(df):
            continue
        try:
            s = df["Close"].dropna()
        except Exception:
            continue
        out[str(t)] = {str(pd.Timestamp(k).date()): float(v) for k, v in s.items()}
    return out


def update_snap_stats(snap: dict, frames: dict) -> int:
    """Skriv snapshot-stats fra den felles lukkede serien. Returnerer antall oppdaterte tickere."""
    n = 0
    for e in snap.get("tickers") or []:
        t = e.get("ticker")
        df = (frames or {}).get(t)
        if df is None or not len(df):
            continue
        st = stats_from_frame(df)
        cur = e.setdefault("stats", {})
        for k in STAT_KEYS:
            if k in st:
                cur[k] = _f(st.get(k))
        if st.get("last_date"):
            cur["last_date"] = str(st["last_date"])[:10]
        cur["shared_closed"] = True
        n += 1
    snap["shared_closes"] = True
    return n


def _rewrite_price_source(snap: dict) -> None:
    """Oppdater dagens rader i price_source.csv til den felles lukkede serien. Historiske rader røres ikke."""
    day = str(snap.get("date") or "")
    if not day:
        return
    rows = []
    for e in snap.get("tickers") or []:
        st = e.get("stats") or {}
        if st.get("last_date") and st.get("close") is not None:
            rows.append({
                "ticker": e["ticker"],
                "price_date": str(st["last_date"])[:10],
                "close": st["close"],
                "source": FR.source_of(e["ticker"]),
            })
    if rows:
        FR.write_price_source(day, rows)


def prepare(snap: dict, frames: dict, now=None, refetch=None, meta=None) -> dict:
    """Én felles repair (bare lukkede barer) og oppdaterte snap-stats. Muterer `frames` og `snap`.

    Repair (refetch/meta) kjøres når siste lukkede bar er eldre enn expected_session. Etterpå
    beholdes bare lukkede barer, og e['stats'] skrives fra den serien. Returnerer de lukkede rammene.
    """
    now = _now(now)
    frames = frames if frames is not None else {}
    # Repair bare etternølere: last_date (lukket) < expected_session
    lag = {t: df for t, df in list(frames.items()) if is_lagging(t, df, now)}
    if lag:
        info = FR.repair_lagging(frames, now=now, refetch=refetch, meta=meta)
        log.info("shared_closes: repair lagging=%s refetched=%s meta=%s still=%s",
                 info.get("lagging"), info.get("refetched"), info.get("meta"), info.get("still"))
    # Godta bare lukkede barer (også barer repairen eventuelt la inn)
    closed = closed_frames(frames, now)
    frames.clear()
    frames.update(closed)
    n = update_snap_stats(snap, frames)
    try:
        _rewrite_price_source(snap)
    except Exception as ex:
        log.warning("shared_closes price_source: %s", ex)
    log.info("shared_closes: %d tickere med felles lukket serie", n)
    return frames
