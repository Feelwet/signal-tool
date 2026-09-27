"""Post-earnings-announcement drift (PEAD) on today's S&P 500 members (yfinance earnings dates with EPS surprise).

Event = earnings announcement. Reaction day d0 = announcement day if before the open (time < 09:30 ET), else next trading
day. Information is fully public at the close of d0; ENTRY at close of d0+1 (one day later, conservative), exit after
20/60 trading days. Excess = stock - SPY. Groups: EPS-surprise quintile and announcement-reaction (d-1 -> d0 excess
return) quintile, ranked within each calendar year. Split in-sample 2006-2015 / out-of-sample 2016-2026.
Costs 0.2 % round trip subtracted from long legs. HAC t-values on quarterly-bucket means.
Biases: survivorship (today's members), yfinance surprise data quality (restatements, missing estimates).
"""
from __future__ import annotations
import logging, time
import numpy as np
import pandas as pd
import yfinance as yf
from . import universe
from .price_rules import hac_t

log = logging.getLogger(__name__)
EV = universe.DIR / "earnings_events.pkl"


def events(tickers) -> pd.DataFrame:
    if EV.exists():
        return pd.read_pickle(EV)
    rows = []
    for i, t in enumerate(tickers):
        try:
            d = yf.Ticker(t).get_earnings_dates(limit=100)
        except Exception as e:
            log.info("%s: %s", t, e)
            continue
        if d is None or d.empty:
            continue
        d = d.dropna(subset=["Surprise(%)"]).reset_index()
        d["ticker"] = t
        rows.append(d.rename(columns={"Earnings Date": "ts", "Surprise(%)": "surprise"})[["ticker", "ts", "surprise", "EPS Estimate", "Reported EPS"]])
        time.sleep(0.2)
    df = pd.concat(rows, ignore_index=True)
    df.to_pickle(EV)
    return df


def run() -> tuple[str, pd.DataFrame]:
    data, members = universe.us()
    tick = [t for t in members["Symbol"] if t in data]
    ev = events(tick)
    C = pd.DataFrame({t: data[t]["Close"] for t in tick + ["SPY"] if t in data}).sort_index()
    spy = C["SPY"]
    idx = C.index
    rows = []
    for r in ev.itertuples():
        if r.ticker not in C:
            continue
        ts = pd.Timestamp(r.ts)
        local = ts.tz_convert("America/New_York") if ts.tzinfo else ts
        day = pd.Timestamp(local.date())
        p = idx.searchsorted(day)
        if local.hour + local.minute / 60 >= 9.5:
            p += 1 if (p < len(idx) and idx[p] == day) else 0
        if p < 1 or p + 62 >= len(idx):
            continue
        c = C[r.ticker]
        if np.isnan(c.iloc[p]) or np.isnan(c.iloc[p - 1]):
            continue
        ear = (c.iloc[p] / c.iloc[p - 1] - 1) - (spy.iloc[p] / spy.iloc[p - 1] - 1)
        e = p + 1
        row = {"ticker": r.ticker, "date": idx[p], "surprise": r.surprise, "ear": ear}
        for h in (20, 60):
            row[f"x{h}"] = (c.iloc[e + h] / c.iloc[e] - 1) - (spy.iloc[e + h] / spy.iloc[e] - 1)
        rows.append(row)
    E = pd.DataFrame(rows).dropna(subset=["x20"])
    E = E[E["date"] >= "2006-01-01"].drop_duplicates(["ticker", "date"])
    E["year"] = E["date"].dt.year
    E["sq"] = E.groupby("year")["surprise"].rank(pct=True)
    E["eq"] = E.groupby("year")["ear"].rank(pct=True)
    E["qtr"] = E["date"].dt.to_period("Q")
    E.to_pickle(universe.DIR / "pead_events.pkl")
    out = []
    groups = {"Overraskelse topp 20 %": E["sq"] >= 0.8, "Overraskelse bunn 20 %": E["sq"] <= 0.2,
              "Kursreaksjon topp 20 %": E["eq"] >= 0.8, "Kursreaksjon bunn 20 %": E["eq"] <= 0.2,
              "Topp overraskelse OG topp reaksjon": (E["sq"] >= 0.8) & (E["eq"] >= 0.8), "Alle": E["sq"] >= 0}
    for per, m in (("in-sample", E["date"] < "2016-01-01"), ("out-of-sample", E["date"] >= "2016-01-01")):
        for g, gm in groups.items():
            S = E[m & gm]
            for h in (20, 60):
                q = S.groupby("qtr")[f"x{h}"].mean()
                out.append({"period": per, "group": g, "h": h, "n": len(S), "mean": S[f"x{h}"].mean(),
                            "median": S[f"x{h}"].median(), "net": S[f"x{h}"].mean() - 0.002, "t": hac_t(q - 0.002, 1),
                            "from": str(S["date"].min().date()) if len(S) else "", "to": str(S["date"].max().date()) if len(S) else ""})
    R = pd.DataFrame(out)
    L = ["## Drift etter kvartalsrapport (PEAD) – USA",
         f"_Kode: signaltool/backtest/pead.py. {len(E):,} rapporter fra {E['ticker'].nunique()} av dagens S&P 500-selskaper (yfinance), 2006–. "
         "Inngang = sluttkurs dagen ETTER reaksjonsdagen (all info offentlig). Meravkastning mot SPY; netto = minus 0,2 % kostnad; t = HAC på kvartalssnitt._", "",
         "| Gruppe | Horisont | Periode | Antall | Snitt (median) | Netto (t) |", "|---|---|---|---|---|---|"]
    for _, r in R.iterrows():
        L.append(f"| {r['group']} | {r['h']} d | {r['period']} {r['from'][:4]}–{r['to'][:4]} | {r['n']} | {r['mean']*100:+.2f} % ({r['median']*100:+.2f} %) | {r['net']*100:+.2f} % ({r['t']:.1f}) |")
    return "\n".join(L), R
