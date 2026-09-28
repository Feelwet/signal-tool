"""Market regime box: S&P 500 and OSEBX vs their 10-month average (Faber) + realised 1-month volatility.

Used ONLY to halve NEW position sizes in the example plan - not a sell signal. Research (strategy-research/RAPPORT.md 4.5):
Faber 10-month rule cut the worst drawdown for SPY 2007-2026 (−22 % vs −51 %) but returned less (8.4 % vs 11.0 %/yr);
for OSEBX 2016-2026 it did not even reduce the drawdown. Volatility targeting: Sharpe 0.81 vs 0.68 (1993-2016), 1.05 vs 1.00 (2017-2026).
"""
from __future__ import annotations
import logging, math
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)
INDEXES = {"^GSPC": "S&P 500", "OSEBX.OL": "OSEBX"}
VOL_LIMIT = 0.25   # annualised 1-month realised volatility


def assess(close: pd.Series) -> dict | None:
    c = pd.Series(close, dtype=float).dropna()
    if len(c) < 200:
        return None
    monthly = c.resample("ME").last()           # current month uses the latest close
    if len(monthly) < 10:
        return None
    sma10 = float(monthly.iloc[-10:].mean())
    last = float(c.iloc[-1])
    lr = np.log(c).diff().dropna()
    vol = float(lr.iloc[-21:].std() * math.sqrt(252))
    below, hivol = last < sma10, vol > VOL_LIMIT
    return {"last": round(last, 2), "sma10m": round(sma10, 2), "dist": round(last / sma10 - 1, 4), "vol1m": round(vol, 4),
            "below": bool(below), "high_vol": bool(hivol), "risk_off": bool(below or hivol), "asof": str(c.index[-1].date())}


def compute(closes: dict[str, pd.Series]) -> dict:
    out = {}
    for t, name in INDEXES.items():
        s = closes.get(t)
        a = assess(s) if s is not None else None
        if a:
            out[t] = {"name": name, **a}
    return out


def apply(snap: dict, fetch: bool = True) -> str:
    if not fetch:
        return "skipped"
    from .categories import _download_close
    try:
        r = compute(_download_close(list(INDEXES), period="2y"))
    except Exception as ex:
        log.warning("regime: %s", ex)
        return f"FAILED: {ex}"
    snap["regime"] = r
    return "ok (" + ", ".join(f"{v['name']}: {'under' if v['below'] else 'over'} 10-mnd snitt, vol {v['vol1m']*100:.0f} %" for v in r.values()) + ")"


def for_ticker(snap_or_regime: dict, ticker: str) -> dict | None:
    reg = snap_or_regime.get("regime", snap_or_regime) if isinstance(snap_or_regime, dict) else {}
    return (reg or {}).get("OSEBX.OL" if ticker.endswith(".OL") else "^GSPC")
