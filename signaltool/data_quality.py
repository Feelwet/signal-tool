"""Price data-quality filter (applied before signals, flags and backtest statistics).

Two known problems in free Yahoo data, especially for Oslo Børs:
  * spike-and-revert bars: one close jumps > 25 % and the next close is back within 5 % of the close before the jump
    (a bad print, not a real move). Repair: the bad close is set to NaN and forward-filled (High/Low on that bar too),
    so returns, momentum, 52-week highs and forward returns are not distorted.
  * stale runs: >= 5 identical closes in a row while volume > 0 (price not updated although the stock traded).
    These are only FLAGGED (listed on the site), not changed - we cannot know the true price.

A spike on the very last bar cannot be detected (the next day is unknown). All functions are pure (no network).
The module keeps a per-run summary (REPORT) that the pipeline writes to snap["data_quality"].
"""
from __future__ import annotations
import logging
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)
SPIKE = 0.25        # |1-day return| above this ...
REVERT = 0.05       # ... and the next close within 5 % of the close before the jump
STALE_N = 5         # identical closes in a row (with volume > 0)
STALE_WINDOW = 260  # stale runs are only flagged if they end within the last ~year of bars
REPORT: dict[str, dict] = {}


def spike_mask(close: pd.Series, spike: float = SPIKE, revert: float = REVERT) -> pd.Series:
    """True on bars whose close jumped > spike and reverted (within revert of the previous close) the next bar."""
    c = pd.Series(close, dtype=float)
    valid = c.dropna()
    out = pd.Series(False, index=c.index)
    if len(valid) < 3:
        return out
    r = valid.pct_change(fill_method=None)
    nxt = valid.shift(-1) / valid.shift(1) - 1      # next close vs close before the jump
    m = (r.abs() > spike) & (nxt.abs() <= revert) & valid.shift(-1).notna()
    out.loc[m[m].index] = True
    return out


def stale_runs(close: pd.Series, volume: pd.Series | None, n: int = STALE_N) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    """Runs of >= n identical consecutive closes where volume > 0 on the repeated days: [(start, end, length)]."""
    c = pd.Series(close, dtype=float).dropna()
    if len(c) < n:
        return []
    v = pd.Series(volume, dtype=float).reindex(c.index) if volume is not None else pd.Series(1.0, index=c.index)
    rep = (c.diff() == 0) & (v.fillna(0) > 0)
    grp = (~rep).cumsum()
    out = []
    for _, g in rep[rep].groupby(grp[rep]):
        length = len(g) + 1                          # the first close of the run is not a "repeat"
        if length >= n:
            start = c.index[c.index.get_loc(g.index[0]) - 1]
            out.append((start, g.index[-1], int(length)))
    return out


def clean_frame(df: pd.DataFrame, spike: float = SPIKE, revert: float = REVERT) -> tuple[pd.DataFrame, dict]:
    """Repair spike-and-revert bars in an OHLCV frame (copy). Returns (clean df, info)."""
    if df is None or len(df) == 0 or "Close" not in df:
        return df, {"spikes": [], "stale": []}
    m = spike_mask(df["Close"], spike, revert)
    out = df
    if m.any():
        out = df.copy()
        for col in ("Close", "High", "Low", "Open"):
            if col in out:
                s = out[col].astype(float)
                s[m] = np.nan
                out[col] = s.ffill()
    runs = stale_runs(out["Close"], out["Volume"] if "Volume" in out else None)
    if len(out.index):
        cutoff = out.index[max(0, len(out.index) - STALE_WINDOW)]
        runs = [r for r in runs if r[1] >= cutoff]
    return out, {"spikes": [str(pd.Timestamp(d).date()) for d in m[m].index], "stale": [(str(a.date()), str(b.date()), k) for a, b, k in runs]}


def clean_universe(data: dict[str, pd.DataFrame], source: str | None = None) -> tuple[dict[str, pd.DataFrame], dict]:
    """Clean every ticker; returns (cleaned dict, summary). If `source` is given the summary is stored in REPORT[source]."""
    out, spikes, stale = {}, {}, {}
    for t, df in (data or {}).items():
        try:
            c, info = clean_frame(df)
        except Exception as ex:   # never let the filter break a run
            log.warning("data quality %s: %s", t, ex)
            c, info = df, {"spikes": [], "stale": []}
        out[t] = c
        if info["spikes"]:
            spikes[t] = info["spikes"]
        if info["stale"]:
            stale[t] = info["stale"]
    summ = {"n_tickers": len(out), "n_spikes": int(sum(len(v) for v in spikes.values())), "spike_tickers": spikes,
            "stale_tickers": stale, "n_stale": len(stale)}
    if source:
        note(source, spikes, stale, list(out))
    return out, summ


def note(source: str, spikes: dict, stale: dict, tickers) -> None:
    """Merge results into REPORT[source] (keyed by ticker, so cleaning the same universe twice never double-counts)."""
    r = REPORT.setdefault(source, {"tickers": set(), "spike_tickers": {}, "stale_tickers": {}})
    r["tickers"].update(tickers)
    r["spike_tickers"].update(spikes)
    r["stale_tickers"].update(stale)
    for t in tickers:          # a re-clean without findings clears older findings for that ticker
        if t not in spikes:
            r["spike_tickers"].pop(t, None)
        if t not in stale:
            r["stale_tickers"].pop(t, None)
    r["n_tickers"] = len(r["tickers"])
    r["n_spikes"] = int(sum(len(v) for v in r["spike_tickers"].values()))
    r["n_stale"] = len(r["stale_tickers"])


def clean_close(close: pd.Series) -> tuple[pd.Series, list[str]]:
    """Close-only variant: repaired series + spike dates."""
    m = spike_mask(close)
    if not m.any():
        return close, []
    s = pd.Series(close, dtype=float).copy()
    s[m] = np.nan
    return s.ffill(), [str(pd.Timestamp(d).date()) for d in m[m].index]


def clean_close_wide(C: pd.DataFrame, source: str | None = None) -> pd.DataFrame:
    """Wide Close frame (columns = tickers): repair spikes column by column."""
    if C is None or len(C) == 0:
        return C
    C = C.copy()
    spikes = {}
    for t in C.columns:
        s, sp = clean_close(C[t].dropna())
        if sp:
            C[t] = s.reindex(C.index)   # keep the original NaN pattern (non-trading days)
            spikes[t] = sp
    if source:
        note(source, spikes, {}, list(C.columns))
    return C


def summary(asof: str | None = None) -> dict:
    """Snapshot-ready summary of all cleaned sources in this run (small: at most 30 examples per list)."""
    src = {}
    recent = (pd.Timestamp(asof) if asof else pd.Timestamp.today()) - pd.Timedelta(days=365)
    for k, v in REPORT.items():
        n_recent = sum(1 for ds in v["spike_tickers"].values() for d in ds if pd.Timestamp(d) >= recent)
        src[k] = {"n_tickers": v["n_tickers"], "n_spikes": v["n_spikes"], "n_spikes_12m": int(n_recent), "n_stale": v["n_stale"],
                  "spikes": sorted(((t, d) for t, ds in v["spike_tickers"].items() for d in ds), key=lambda x: x[1], reverse=True)[:30],
                  "stale": sorted(((t, r[0][0], r[0][1], r[0][2]) for t, r in ((t, sorted(rs, key=lambda x: x[1], reverse=True)) for t, rs in v["stale_tickers"].items())),
                                  key=lambda x: x[2], reverse=True)[:30]}
    return {"asof": asof, "rules": {"spike": SPIKE, "revert": REVERT, "stale_n": STALE_N, "stale_window": STALE_WINDOW}, "sources": src,
            "n_spikes": int(sum(v["n_spikes"] for v in src.values())), "n_spikes_12m": int(sum(v["n_spikes_12m"] for v in src.values())),
            "n_stale": int(sum(v["n_stale"] for v in src.values()))}


def reset() -> None:
    REPORT.clear()
