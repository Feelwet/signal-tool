from __future__ import annotations
import numpy as np
import pandas as pd


def fwd_returns(close: pd.Series, event_dates, horizons=(5, 20, 60), entry_lag=1):
    """Return DataFrame of forward returns. Entry = close `entry_lag` trading days after the event date
    (event on a non-trading day -> next trading day counts as day 0)."""
    close = close.dropna()
    idx = close.index
    out = []
    for d in event_dates:
        pos = idx.searchsorted(pd.Timestamp(d))
        e = pos + entry_lag - 1 if entry_lag > 0 else pos
        if pos >= len(idx) or e >= len(idx):
            continue
        row = {"event": pd.Timestamp(d), "entry_date": idx[e]}
        for h in horizons:
            row[f"r{h}"] = close.iloc[e + h] / close.iloc[e] - 1 if e + h < len(idx) else np.nan
        row["r_prior5"] = close.iloc[e] / close.iloc[e - 5] - 1 if e >= 5 else np.nan
        out.append(row)
    return pd.DataFrame(out)


def summarize(x: pd.Series) -> dict:
    x = pd.Series(x).dropna()
    n = len(x)
    if n < 2:
        return {"n": n}
    t = x.mean() / (x.std(ddof=1) / np.sqrt(n)) if x.std() > 0 else np.nan
    return {"n": n, "mean": x.mean(), "median": x.median(), "hit": (x > 0).mean(), "t": t}


def fmt(s: dict) -> str:
    if s.get("n", 0) < 2:
        return f"n={s.get('n', 0)}"
    return f"n={s['n']}, snitt {s['mean']*100:+.2f}%, median {s['median']*100:+.2f}%, andel positive {s['hit']*100:.0f}%, t={s['t']:.2f}"
