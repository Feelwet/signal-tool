"""Backtest: US crude/product stocks vs 5-year seasonal norm -> forward WTI / XLE returns.
Signal at the EIA report date (Wednesday after week end, we use week-end + 5 days as entry to avoid look-ahead).
Split: in-sample < 2015, out-of-sample >= 2015. HAC t-values (overlapping horizons)."""
from __future__ import annotations
import numpy as np, pandas as pd, yfinance as yf
from .price_rules import hac_t
from ..collectors.oil_nowcast import eia_weekly


def dev_series(s: pd.Series, years=5) -> pd.Series:
    out = {}
    for d in s.index:
        hist = []
        for y in range(1, years + 1):
            t = d - pd.DateOffset(years=y)
            w = s[(s.index >= t - pd.Timedelta(days=4)) & (s.index <= t + pd.Timedelta(days=4))]
            if len(w):
                hist.append(float(w.iloc[0]))
        if len(hist) == years:
            out[d] = s[d] / np.mean(hist) - 1
    return pd.Series(out)


def run():
    px = yf.download(["CL=F", "XLE", "SPY"], start="2001-01-01", auto_adjust=True, progress=False)["Close"]
    lines = ["| Serie | Signal | Mål | Horisont | Periode | N | Koeff. | HAC t | Treff (fall→opp) |", "|---|---|---|---|---|---|---|---|---|"]
    for sid in ["WCESTUS1", "WGTSTUS1", "WDISTUS1"]:
        s = eia_weekly(sid)
        dev = dev_series(s[s.index >= "1995-01-01"])
        for sig_name, sig in [("nivå vs 5-år", dev), ("4-ukers endring i avvik", dev.diff(4))]:
            for tgt in ["CL=F", "XLE"]:
                for h in [20, 60]:
                    rows = []
                    for d, v in sig.dropna().items():
                        e = d + pd.Timedelta(days=5)
                        p = px[tgt].dropna()
                        i = p.index.searchsorted(e)
                        if i + h >= len(p):
                            continue
                        r = p.iloc[i + h] / p.iloc[i] - 1
                        if tgt == "XLE":
                            b = px["SPY"].reindex(p.index).ffill()
                            r -= b.iloc[i + h] / b.iloc[i] - 1
                        rows.append((p.index[i], v, r))
                    df = pd.DataFrame(rows, columns=["d", "x", "y"]).set_index("d")
                    for per, sub in [("IS <2015", df[df.index < "2015-01-01"]), ("OOS ≥2015", df[df.index >= "2015-01-01"])]:
                        if len(sub) < 50:
                            continue
                        xc, yc = sub.x - sub.x.mean(), sub.y - sub.y.mean()
                        beta = float((xc * yc).sum() / (xc * xc).sum())
                        t = hac_t(xc * yc, h // 5 + 1)  # tests cov(x, y) = 0 with Newey-West errors
                        hit = ((sub.x < 0) == (sub.y > 0)).mean()
                        lines.append(f"| {sid} | {sig_name} | {tgt}{' vs SPY' if tgt=='XLE' else ''} | {h}d | {per} | {len(sub)} | {beta:.3f} | {t:.2f} | {hit:.0%} |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(run())
