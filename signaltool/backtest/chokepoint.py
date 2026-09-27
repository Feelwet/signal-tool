"""Chokepoint transit drops (IMF PortWatch, 2019-) vs tanker equities / Brent.

Event: 7-day average transits (tankers) at a chokepoint fall >= 2 robust-z below the previous 60 days, 20-day cooldown.
PortWatch is published with a lag of roughly a week, so ENTRY = close 7 calendar days after the event date (realistic).
Forward 20/60 trading-day returns of FRO, DHT, STNG (tankers), BZ=F (Brent) vs SPY, compared with all days (bootstrap p).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import yfinance as yf
from ..collectors import portwatch
from . import universe

INSTR = ["FRO", "DHT", "STNG", "BZ=F"]


def run() -> str:
    px = {}
    d = yf.download(INSTR + ["SPY"], start="2018-06-01", progress=False, auto_adjust=True)["Close"]
    d.index = pd.to_datetime(d.index).tz_localize(None)
    rng = np.random.default_rng(7)
    L = ["## Trafikkfall i sjøveis flaskehalser (IMF PortWatch) vs tankrederier og Brent",
         "_Kode: signaltool/backtest/chokepoint.py. Hendelse = 7-dagers snitt av tankskip-passeringer ≥ 2 robuste z under foregående 60 dager "
         "(20 d karantene). Inngang 7 kalenderdager etter hendelsen (PortWatch publiseres med ca. en ukes forsinkelse). Meravkastning mot SPY. "
         "p = andel av 2000 tilfeldige like store utvalg av dager med minst like stort snitt._", "",
         "| Flaskehals | Hendelser | Instrument | 20 d etter (snitt) | Alle dager 20 d | p | 60 d etter | Alle dager 60 d |", "|---|---|---|---|---|---|---|---|"]
    for pid in ("chokepoint6", "chokepoint4", "chokepoint1", "chokepoint2"):
        h = portwatch.history(pid, since="2019-01-01", cache_hours=24)
        s = h["n_tanker"].rolling(7).mean()
        base = s.shift(7).rolling(60, min_periods=45)
        med = base.median()
        mad = (s.shift(7) - med).abs().rolling(60, min_periods=45).median() * 1.4826
        z = (s - med) / mad.replace(0, np.nan)
        ev, last = [], None
        for t, v in z.items():
            if v <= -2 and (last is None or (t - last).days >= 20):
                ev.append(t); last = t
        for ins in INSTR:
            c, b = d[ins].dropna(), d["SPY"].dropna()
            idx = c.index.intersection(b.index)
            c, b = c[idx], b[idx]
            res = {}
            for hh in (20, 60):
                fx = (c.shift(-hh) / c - 1) - (b.shift(-hh) / b - 1)
                allv = fx.dropna()
                vals = []
                for t in ev:
                    p = idx.searchsorted(t + pd.Timedelta(days=7))
                    if p < len(idx) and not np.isnan(fx.iloc[p]):
                        vals.append(fx.iloc[p])
                m = np.mean(vals) if vals else np.nan
                pv = np.nan
                if len(vals) >= 3:
                    sims = [allv.sample(len(vals), random_state=int(rng.integers(1e9))).mean() for _ in range(2000)]
                    pv = np.mean([abs(x - allv.mean()) >= abs(m - allv.mean()) for x in sims])
                res[hh] = (len(vals), m, allv.mean(), pv)
            L.append(f"| {portwatch.CHOKE[pid]} | {res[20][0]} | {ins} | {res[20][1]*100:+.2f} % | {res[20][2]*100:+.2f} % | {res[20][3]:.2f} | "
                     f"{res[60][1]*100:+.2f} % | {res[60][2]*100:+.2f} % |")
    L += ["", "**Forbehold:** Svært få uavhengige hendelser (Rødehavskrisen 2023–24, Panama-tørken 2023, Hormuz 2025–26 dominerer); "
          "mange tester (4 flaskehalser × 4 instrumenter) → forvent noen lave p-verdier ved flaks. Ingen kostnader."]
    return "\n".join(L)
