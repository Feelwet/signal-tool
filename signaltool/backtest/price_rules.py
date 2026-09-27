"""Validation of the PRICE parts of the category rules and of momentum / relative-strength signals.

Question: do the conditions we use (close > 50d average, 20d return > benchmark, "not stretched", no crash) or classic
momentum (12-1 months) / sector-relative strength predict the next 20/60 trading days' return vs the benchmark?

Method: every 21 trading days (formation date t), for every liquid stock (median turnover >= ~USD 1M/day, price >= ~USD 1)
compute the features with data up to t; entry at close t+1, exit t+1+h. Excess = stock - benchmark (SPY / OSEBX).
Per formation date we take the equal-weighted mean of each group minus the universe mean ("spread"); the time series of
spreads gives mean and a HAC (Newey-West) t-value. Split: in-sample (older half) vs out-of-sample (newer half).
Costs: a signal that selects stocks has to trade them: round trip 0.20 % (US) / 0.40 % (Oslo) is subtracted from the
group-vs-benchmark return ("netto"). Multiple testing: ~30 tests -> Bonferroni |t| >= 3.1 required for "robust".
Bias: US universe = TODAY's S&P 500 members (survivorship bias, flatters everything that 'survived'; affects all groups).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from ..config import REPORTS
from . import universe

COST = {"US": 0.002, "OSLO": 0.004}
MIN_ADV_USD = 1e6


def hac_t(x: pd.Series, lags: int) -> float:
    x = pd.Series(x).dropna()
    n = len(x)
    if n < 10:
        return np.nan
    e = x - x.mean()
    s = (e ** 2).sum() / n
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        s += 2 * w * (e[L:].values * e[:-L].values).sum() / n
    return float(x.mean() / np.sqrt(s / n)) if s > 0 else np.nan


def features(data: dict, bench: str, fx: float, sector_of: dict | None = None):
    C = pd.DataFrame({t: d["Close"] for t, d in data.items()}).sort_index()
    V = pd.DataFrame({t: d["Volume"] for t, d in data.items()}).reindex(C.index)
    C = C.ffill(limit=3)
    b = C[bench]
    feats = {
        "above50": C > C.rolling(50, min_periods=45).mean(),
        "r5": C / C.shift(5) - 1, "r20": C / C.shift(20) - 1,
        "dist50": C / C.rolling(50, min_periods=45).mean() - 1,
        "mom12_1": C.shift(21) / C.shift(252) - 1,
        "maxdd20": (C / C.rolling(20).max() - 1).rolling(20).min(),
        "adv": (C * V).rolling(20, min_periods=10).median() * fx,
        "px": C * fx,
    }
    feats["rel20"] = feats["r20"].sub(b / b.shift(20) - 1, axis=0)
    if sector_of:
        r60 = C / C.shift(60) - 1
        rel = pd.DataFrame(index=C.index)
        for t, etf in sector_of.items():
            if t in C and etf in C:
                rel[t] = r60[t] - r60[etf]
        feats["secrel60"] = rel
    fwd = {h: (C.shift(-(1 + h)) / C.shift(-1) - 1).sub(b.shift(-(1 + h)) / b.shift(-1) - 1, axis=0) for h in (20, 60)}
    return C, feats, fwd


def run_market(name: str, data: dict, bench: str, fx: float, split: str, sector_of=None, exclude=()) -> tuple[list[dict], pd.DataFrame]:
    C, F, fwd = features(data, bench, fx, sector_of)
    dates = C.index[260::21]
    dates = dates[dates <= C.index[-62]]
    cols = [c for c in C.columns if c != bench and c not in exclude]
    recs = []
    for t in dates:
        row = pd.DataFrame({k: v.loc[t].reindex(cols) for k, v in F.items()})
        row["f20"], row["f60"] = fwd[20].loc[t].reindex(cols), fwd[60].loc[t].reindex(cols)
        row = row[(row["adv"] >= MIN_ADV_USD) & (row["px"] >= 1.0)].dropna(subset=["f20", "r20", "above50"])
        if len(row) < 20:
            continue
        row["date"] = t
        recs.append(row)
    P = pd.concat(recs)
    P["above50"] = P["above50"].astype(bool)
    P["price_ok"] = P["above50"] & (P["rel20"] > 0)
    P["stretched"] = (P["r5"] >= 0.10) | (P["r20"] >= 0.25) | (P["dist50"] >= 0.25)
    P["crash"] = P["maxdd20"] <= -0.20
    P["kjop_price"] = P["price_ok"] & ~P["stretched"] & ~P["crash"]
    P["hold_like"] = P["price_ok"] & P["stretched"] & ~P["crash"]
    P["fail"] = ~P["price_ok"]
    q = P.groupby("date")["mom12_1"].rank(pct=True)
    P["mom_top"], P["mom_bot"] = q >= 0.8, q <= 0.2
    groups = ["price_ok", "kjop_price", "hold_like", "fail", "crash", "mom_top", "mom_bot"]
    if "secrel60" in P:
        qs = P.groupby("date")["secrel60"].rank(pct=True)
        P["secrel_top"], P["secrel_bot"] = qs >= 0.8, qs <= 0.2
        groups += ["secrel_top", "secrel_bot"]
    out = []
    for per, mask in (("in-sample", P["date"] < split), ("out-of-sample", P["date"] >= split)):
        S = P[mask]
        for g in groups:
            for h in (20, 60):
                by = S.groupby("date")
                uni = by[f"f{h}"].mean()
                grp = S[S[g]].groupby("date")[f"f{h}"].mean()
                spread = (grp - uni.reindex(grp.index)).dropna()
                gross = grp.dropna()
                lags = 0 if h == 20 else 3
                out.append({"market": name, "period": per, "group": g, "h": h, "n_dates": len(spread),
                            "avg_n": float(S[S[g]].groupby("date").size().mean()) if len(gross) else 0,
                            "spread": spread.mean(), "t_spread": hac_t(spread, lags),
                            "net_vs_bench": gross.mean() - COST[name], "t_net": hac_t(gross - COST[name], lags),
                            "hit": float((spread > 0).mean()) if len(spread) else np.nan,
                            "from": str(S["date"].min().date()), "to": str(S["date"].max().date())})
    return out, P


LABEL = {"price_ok": "Kursbekreftelse (over 50d-snitt og 20d > indeks)", "kjop_price": "Kjøp-kursregler (kursbekr. + ikke strukket + ingen krasj)",
         "hold_like": "Kursbekr. men strukket («Hold»)", "fail": "Uten kursbekreftelse", "crash": "Krasj ≥ 20 % siste 20 d",
         "mom_top": "Momentum 12-1 mnd, topp 20 %", "mom_bot": "Momentum 12-1 mnd, bunn 20 %",
         "secrel_top": "Sektorrelativ styrke 60 d, topp 20 %", "secrel_bot": "Sektorrelativ styrke 60 d, bunn 20 %"}


def run() -> str:
    usd, members = universe.us()
    sector_of = {r.Symbol: universe.SECTOR_ETF.get(r._3) for r in members.itertuples() if universe.SECTOR_ETF.get(r._3)}
    res_us, _ = run_market("US", usd, "SPY", 1.0, "2016-01-01", sector_of, exclude=set(universe.SECTOR_ETF.values()))
    osl = universe.oslo()
    res_os, _ = run_market("OSLO", osl, "OSEBX.OL", 0.095, "2018-07-01")
    R = pd.DataFrame(res_us + res_os)
    R.to_csv(universe.DIR / "price_rules_results.csv", index=False)
    L = ["## Kursregler, momentum og sektorrelativ styrke – stor test med ut-av-utvalg-sjekk",
         f"_Kode: signaltool/backtest/price_rules.py. USA: dagens S&P 500 ({len(usd)} tickere m/ data, 2006–) – overlevelsesskjevhet. "
         f"Oslo: {len(osl)} tickere fra Newsweb med yfinance-data (2011–). Formasjon hver 21. handelsdag, kun likvide aksjer (≥ ~$1M/dag, kurs ≥ ~$1)._",
         "", "«Spread» = gruppens snitt minus snittet av alle aksjer samme dato (brutto). «Netto vs indeks» = gruppens meravkastning mot SPY/OSEBX "
         "etter handelskostnad (0,2 % USA / 0,4 % Oslo tur-retur). t = HAC t-verdi. Robust krever |t| ≥ 3,1 (Bonferroni for ~30 tester) OG samme fortegn i begge perioder.", ""]
    for mk in ("US", "OSLO"):
        L += [f"### {'USA' if mk == 'US' else 'Oslo Børs'}", "| Gruppe | Horisont | Periode | Snitt antall aksjer | Spread vs alle (t) | Netto vs indeks (t) | Andel datoer spread > 0 |", "|---|---|---|---|---|---|---|"]
        for _, r in R[R["market"] == mk].iterrows():
            L.append(f"| {LABEL[r['group']]} | {r['h']} d | {r['period']} {r['from'][:4]}–{r['to'][:4]} | {r['avg_n']:.0f} | "
                     f"{r['spread']*100:+.2f} % ({r['t_spread']:.1f}) | {r['net_vs_bench']*100:+.2f} % ({r['t_net']:.1f}) | {r['hit']*100:.0f} % |")
        L.append("")
    return "\n".join(L), R
