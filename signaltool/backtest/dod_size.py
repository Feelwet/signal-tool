"""Backtest: DoD/USAspending award size relative to the contractor's market cap -> excess return vs SPY.
Market cap at award date ~ close x current shares outstanding (Yahoo) - approximate (buybacks/issuance ignored).
Awards >= $100M 2022- (cache from categories_check), 30-day cooldown per ticker, entry 2 trading days after the
award date (USAspending action date is not always the public announcement date)."""
from __future__ import annotations
import numpy as np, pandas as pd, yfinance as yf
from .categories_check import DOD_CACHE, dedupe
from .price_rules import hac_t


def run() -> str:
    d = pd.read_csv(DOD_CACHE, parse_dates=["date"])
    tick = sorted(d["ticker"].dropna().unique())
    shares = {}
    for t in tick:
        try:
            shares[t] = yf.Ticker(t).info.get("sharesOutstanding")
        except Exception:
            pass
    px = yf.download(tick + ["SPY"], start="2021-06-01", auto_adjust=True, progress=False)["Close"]
    ev = dedupe(d.dropna(subset=["ticker"]))
    rows = []
    for e in ev.itertuples():
        if e.ticker not in px or not shares.get(e.ticker):
            continue
        c = px[e.ticker].dropna()
        i = c.index.searchsorted(e.date)
        if i + 62 >= len(c) or i < 1:
            continue
        mcap = c.iloc[i - 1] * shares[e.ticker]
        s = px["SPY"].reindex(c.index).ffill()
        ent = i + 2
        r = {"ticker": e.ticker, "date": e.date, "rel": e.amount / mcap}
        for h in (20, 60):
            r[f"x{h}"] = (c.iloc[ent + h] / c.iloc[ent] - 1) - (s.iloc[ent + h] / s.iloc[ent] - 1)
        rows.append(r)
    R = pd.DataFrame(rows)
    R["m"] = R["date"].dt.to_period("M")
    L = ["## DoD-kontraktens størrelse i forhold til markedsverdi → meravkastning vs SPY",
         f"_{len(R)} kontrakter ≥ $100M (USAspending 2022–, 30 d karantene per selskap). Markedsverdi ≈ kurs × dagens aksjeantall (tilnærming). "
         "Inngang 2 handelsdager etter kontraktsdato. Ingen kostnader trukket (≈0,2 % tur-retur). t = Newey-West på månedssnitt._", "",
         "| Gruppe | N | 20 d snitt (t) | 60 d snitt (t) | Andel > 0 (60 d) |", "|---|---|---|---|---|"]
    for lab, m in (("Kontrakt ≥ 1 % av markedsverdi", R["rel"] >= 0.01), ("0,25–1 %", (R["rel"] >= 0.0025) & (R["rel"] < 0.01)),
                   ("< 0,25 %", R["rel"] < 0.0025), ("Alle", R["rel"] >= 0)):
        g = R[m]
        if len(g) < 5:
            L.append(f"| {lab} | {len(g)} | – | – | – |"); continue
        t20 = hac_t(g.groupby("m")["x20"].mean(), 1); t60 = hac_t(g.groupby("m")["x60"].mean(), 2)
        L.append(f"| {lab} | {len(g)} | {g['x20'].mean()*100:+.2f} % ({t20:.1f}) | {g['x60'].mean()*100:+.2f} % ({t60:.1f}) | {(g['x60'] > 0).mean():.0%} |")
    big = R[R["rel"] >= 0.01].sort_values("rel", ascending=False).head(8)
    L.append("")
    L.append("Største relative kontrakter: " + ", ".join(f"{r.ticker} {r.date:%Y-%m} ({r.rel*100:.1f} %)" for r in big.itertuples()))
    return "\n".join(L)


if __name__ == "__main__":
    print(run())
