"""Physical-oil market signals from free futures prices (yfinance): 3-2-1 crack spread, Brent–WTI spread,
and futures-curve shape (front vs ~3rd contract; backwardation = tight prompt supply)."""
from __future__ import annotations
from .. import http as _http
from datetime import date
import pandas as pd
import yfinance as yf
from ..anomaly import robust_z

MONTH_CODES = "FGHJKMNQUVXZ"


def _contract(root: str, y: int, m: int, exch="NYM") -> str:
    return f"{root}{MONTH_CODES[m-1]}{str(y)[-2:]}.{exch}"


def curve(root: str, n=5) -> pd.Series:
    t = date.today()
    syms = []
    for k in range(1, n + 2):
        m = (t.month - 1 + k) % 12 + 1
        y = t.year + (t.month - 1 + k) // 12
        syms.append(_contract(root, y, m))
    d = _http.yf_download(syms, period="5d", progress=False, auto_adjust=True)["Close"]
    last = d.ffill().iloc[-1].dropna()
    return last.reindex([s for s in syms if s in last.index])


def collect() -> tuple[dict, str]:
    try:
        d = _http.yf_download(["CL=F", "BZ=F", "RB=F", "HO=F"], period="2y", progress=False, auto_adjust=True)["Close"].ffill().dropna()
    except Exception as e:
        return {}, f"FAILED: {e}"
    crack = (2 * d["RB=F"] * 42 + d["HO=F"] * 42 - 3 * d["CL=F"]) / 3
    bw = d["BZ=F"] - d["CL=F"]
    out = {}
    for name, s, label in (("crack_321", crack, "3-2-1 crack spread (USD/fat) – raffinerimargin"),
                           ("brent_wti", bw, "Brent–WTI (USD/fat) – sjøbåren vs. amerikansk olje")):
        z, info = robust_z(s, recent_n=3, baseline_n=250, min_baseline=100)
        out[name] = {"label": label, "last": round(float(s.iloc[-1]), 2), "z": None if pd.isna(z) else round(z, 2),
                     "chg_5d": round(float(s.iloc[-1] - s.iloc[-6]), 2), "spark": [round(float(x), 2) for x in s.iloc[-60:]]}
    for root, nm in (("BZ", "Brent"), ("CL", "WTI")):
        try:
            c = curve(root)
            if len(c) >= 3:
                out[f"{root.lower()}_curve"] = {"label": f"{nm} terminkurve: 1. vs 3. kontrakt (USD/fat, + = backwardation)",
                                                "last": round(float(c.iloc[0] - c.iloc[2]), 2), "z": None,
                                                "contracts": {k: round(float(v), 2) for k, v in c.items()}}
        except Exception:
            pass
    return out, f"ok ({', '.join(out)})"
