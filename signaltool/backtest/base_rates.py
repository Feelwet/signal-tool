"""Historical base rates per signal type / category ("Historisk treffrate"), computed ONLY from data already cached
by the earlier backtests (no new downloads). Output: data/base_rates.json, used by the site.

For every signal: number of cases, share that beat the benchmark, median and mean excess return at 20 / 60 trading
days, period. Entry = close the day after the event (DoD: 2 days, as in categories_check). Excess = stock - benchmark
(SPY / S&P 500 for US, OSEBX for Oslo). Gross of costs. Survivorship bias in the US price universe (today's members).
EXCEPTION - PEAD: point-in-time S&P 500 membership incl. former members (event table built by strategy-research/round3,
us_build.py), excess vs the equal-weighted point-in-time universe, shown gross AND net of 0.75 % US round-trip cost.
Run: python -m signaltool.backtest.base_rates          (everything)
     python -m signaltool.backtest.base_rates pead     (only the PEAD rows; the rest of data/base_rates.json is kept)
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd
from ..config import CACHE, DATA
from ..categories import RULES
from . import universe, insider, oslo_events
from .categories_check import DOD_CACHE, dedupe, evaluate as cc_evaluate
from .price_rules import hac_t

OUT = DATA / "base_rates.json"
RESEARCH = Path(os.environ.get("SIGNAL_RESEARCH", "/workspace/strategy-research"))
PIT_EVENTS = RESEARCH / "round3" / "data" / "events_us.pkl"
COST_US = 0.0075   # round trip for a Norwegian retail client (0.5-1.0 %, Nordnet price list; RAPPORT.md ch. 5)
SPLIT = "2016-01-01"


def stats(x20: pd.Series, x60: pd.Series, dates: pd.Series, **meta) -> dict:
    a, b = pd.Series(x20, dtype=float).dropna(), pd.Series(x60, dtype=float).dropna()
    d = pd.to_datetime(pd.Series(dates)).dropna()
    r = {"n": int(max(len(a), len(b))), "period": f"{d.min():%Y-%m}–{d.max():%Y-%m}" if len(d) else ""}
    for h, s in ((20, a), (60, b)):
        r[f"n{h}"] = int(len(s))
        if len(s) >= 5:
            r[f"hit{h}"] = float((s > 0).mean()); r[f"med{h}"] = float(s.median()); r[f"mean{h}"] = float(s.mean())
    r.update(meta)
    return r


def _fwd_x(C: pd.DataFrame, bench: str, h: int, lag: int = 1) -> pd.DataFrame:
    F = C.shift(-(lag + h)) / C.shift(-lag) - 1
    return F.sub(F[bench], axis=0)


def _pit_stats(X: pd.DataFrame, note: str) -> dict:
    r = stats(X["x20"], X["x60"], X["date"], bench="likevektet S&P 500 (punkt-i-tid)", note=note)
    r["cost"] = COST_US
    for h in (20, 60):
        if r.get(f"mean{h}") is not None:
            r[f"net{h}"] = r[f"mean{h}"] - COST_US
    for per, sel in (("is", X["date"] < SPLIT), ("oos", X["date"] >= SPLIT)):
        Y = X[sel].dropna(subset=["x60"])
        if len(Y) >= 20:
            q = Y.groupby("qtr")["x60"].mean()
            r[f"mean60_{per}"], r[f"t60_{per}"], r[f"n60_{per}"] = float(Y["x60"].mean()), hac_t(q, 1), int(len(Y))
    r["pit"] = True
    return r


def pead() -> dict:
    """Point-in-time PEAD base rates (site thresholds and PEAD-S). Falls back to today's members (labelled) if the
    point-in-time event table is missing."""
    if PIT_EVENTS.exists():
        E = pd.read_pickle(PIT_EVENTS)
        R = E[E["pit"]].copy()
        site = (R["surprise"] >= 15) & (R["ear_spy"] >= 0.04)
        hv = R["q_vol"] > 0.5
        base = ("Punkt-i-tid S&P 500 inkl. 146 tidligere medlemmer (rapportdata mangler fortsatt for oppkjøpte/konkursrammede). "
                "Meravkastning mot likevektet punkt-i-tid-univers, inngang sluttkurs dagen etter reaksjonsdagen. "
                f"Netto = minus {COST_US*100:.2f} % tur-retur. t = HAC på kvartalssnitt. Kilde: strategy-research/RAPPORT_3.")
        return {"pead": _pit_stats(R[site], "EKSPERIMENTELL / svak evidens. Sidens terskler: EPS-overraskelse ≥ 15 % og reaksjon ≥ +4 % mot SPY. " + base),
                "pead_s": _pit_stats(R[site & hv], "EKSPERIMENTELL. PEAD-S = sidens terskler OG 1-års daglig volatilitet over median blant "
                                                   "S&P 500-aksjene dagen før reaksjonsdagen. " + base)}
    E = pd.read_pickle(universe.DIR / "pead_events.pkl")
    live = E[(E["surprise"] >= 15) & (E["ear"] >= 0.04)]
    r = stats(live["x20"], live["x60"], live["date"], bench="SPY",
              note="ADVARSEL: punkt-i-tid-tabellen mangler – dagens S&P 500-medlemmer (overlevelsesskjevhet, overvurderer effekten). Brutto.")
    return {"pead": r}


def us_events():
    p = insider.load_purchases()
    cl, _ = insider.find_events(p)
    dod = pd.read_csv(DOD_CACHE, parse_dates=["date"])
    dod = dedupe(dod) if not dod.empty else dod
    px = pd.read_csv(insider.DIR / "prices.csv.gz", index_col=0, parse_dates=True)
    spy = px["SPY"].dropna()
    ra = cc_evaluate(cl, px, spy)
    rb = cc_evaluate(dod, px, spy)
    return ra, rb


def us_unusual_volume(data: dict) -> dict:
    C = pd.DataFrame({t: d["Close"] for t, d in data.items()}).sort_index().ffill(limit=3)
    V = pd.DataFrame({t: d["Volume"] for t, d in data.items()}).reindex(C.index).replace(0, np.nan)
    return _unusual(C, V, "SPY", exclude=set(universe.SECTOR_ETF.values()) | {"SPY"}, adv_min=1e6)


def _unusual(C, V, bench, exclude, adv_min, fx=1.0):
    lv = np.log(V)
    base = lv.shift(6).rolling(60, min_periods=50)
    z = (lv.rolling(5).mean() - base.mean()) / base.std()
    adv = (C * V).rolling(20, min_periods=10).median() * fx
    X20, X60 = _fwd_x(C, bench, 20), _fwd_x(C, bench, 60)
    rows = []
    for t in C.columns:
        if t in exclude:
            continue
        zt = z[t]
        hit = (zt > 1.5) & (zt.shift(1) <= 1.5) & (adv[t] >= adv_min)
        last = None
        for d in zt.index[hit.fillna(False).values]:
            if last is not None and (d - last).days < 30:
                continue
            last = d
            rows.append((d, X20.at[d, t], X60.at[d, t]))
    R = pd.DataFrame(rows, columns=["date", "x20", "x60"])
    return R


def baseline(C, V, bench, exclude, adv_min, fx=1.0) -> pd.DataFrame:
    """Every liquid stock on every 21st trading day - what a 'random' pick did (the yardstick for the rows above)."""
    adv = (C * V).rolling(20, min_periods=10).median() * fx
    X20, X60 = _fwd_x(C, bench, 20), _fwd_x(C, bench, 60)
    rows = []
    for d in C.index[260::21]:
        ok = [t for t in C.columns if t not in exclude and adv.at[d, t] >= adv_min]
        for t in ok:
            rows.append((d, X20.at[d, t], X60.at[d, t]))
    return pd.DataFrame(rows, columns=["date", "x20", "x60"])


def oslo() -> tuple[dict, dict, dict, dict]:
    C, adv = oslo_events._prices()
    X20, X60 = _fwd_x(C, "OSEBX.OL", 20), _fwd_x(C, "OSEBX.OL", 60)

    def run(ev):
        rows = []
        for r in ev.itertuples():
            if r.ticker not in C.columns:
                continue
            i = C.index.searchsorted(r.date)
            if i >= len(C) - 3:
                continue
            d = C.index[i]
            if not (adv.at[d, r.ticker] >= oslo_events.MIN_ADV_NOK):
                continue
            rows.append((d, X20.at[d, r.ticker], X60.at[d, r.ticker]))
        return pd.DataFrame(rows, columns=["date", "x20", "x60"])
    ce = oslo_events.contract_events()
    con = run(ce[ce["group"] == "Kontraktsmelding (alle)"])
    ie = oslo_events.insider_events()
    ins = run(ie[ie["group"] == "Innsidekjøp (alle)"])
    V = pd.DataFrame({t: d["Volume"] for t, d in universe.oslo().items()}).reindex(C.index).replace(0, np.nan)
    uv = _unusual(C, V, "OSEBX.OL", exclude={"OSEBX.OL"}, adv_min=oslo_events.MIN_ADV_NOK)
    bl = baseline(C, V, "OSEBX.OL", {"OSEBX.OL"}, oslo_events.MIN_ADV_NOK)
    note = "Oslo Børs, likvide aksjer (dagens noterte selskaper). Inngang sluttkurs dagen etter meldingen."
    return (stats(con.x20, con.x60, con.date, bench="OSEBX", note=note + " Titler med kontrakt/ordre/rammeavtale, uten rettssaker/aksjetildelinger."),
            stats(ins.x20, ins.x60, ins.date, bench="OSEBX", note=note + " Retning lest fra meldingsteksten (2021–)."),
            stats(uv.x20, uv.x60, uv.date, bench="OSEBX", note="Volum-z (5 d mot 60 d) krysser 1,5, 30 d karantene, likvide Oslo-aksjer."),
            stats(bl.x20, bl.x60, bl.date, bench="OSEBX", note="Sammenligningsgrunnlag: alle likvide Oslo-aksjer hver 21. handelsdag."))


def build(only: str | None = None) -> dict:
    if only == "pead":
        out = json.loads(OUT.read_text()) if OUT.exists() else {}
        out.pop("pead_s", None)
        out.update(pead())
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
        return out
    out = {"_meta": {"what": "Meravkastning mot indeks (brutto, før kurtasje) fra inngang dagen etter hendelsen. "
                             "«Slo indeksen» = andel tilfeller med positiv meravkastning. Overlappende hendelser og overlevelsesskjevhet (USA) – "
                             "tallene er grunnlag for forventninger, ikke garantier."}}
    out.update(pead())
    ra, rb = us_events()
    out["insider_cluster"] = stats(ra.x20, ra.x60, ra.date, bench="SPY", note="≥ 3 ledere/styremedlemmer kjøper innen 30 d (SEC Form 4, 2022–2025).")
    out["gov_contract"] = stats(rb.x20, rb.x60, rb.date, bench="SPY", note="DoD/USAspending-kontrakter ≥ $100M (2022–), inngang 2 dager etter tildelingsdato.")
    both = pd.concat([ra, rb], ignore_index=True)
    k, h = both[both["kjop_rules"]], both[both["hold_like"]]
    out["rule_kjop"] = stats(k.x20, k.x60, k.date, bench="SPY", note="Innsideklynger og DoD-kontrakter der Kjøp-kursreglene også var oppfylt (kursbekreftelse, ikke strukket, ingen krasj). "
                             "Hele Kjøp-regelen (≥ 2 uavhengige typer) hadde bare 2 historiske tilfeller – for få.")
    out["rule_hold"] = stats(h.x20, h.x60, h.date, bench="SPY", note="Samme hendelser, men med kursbekreftelse og strukket kurs («Hold-lignende»).")
    usd, _ = universe.us()
    uv = us_unusual_volume(usd)
    out["unusual_volume"] = stats(uv.x20, uv.x60, uv.date, bench="SPY", note="Volum-z (5 d mot 60 d) krysser 1,5, 30 d karantene, likvide S&P 500-aksjer.")
    C = pd.DataFrame({t: d["Close"] for t, d in usd.items()}).sort_index().ffill(limit=3)
    V = pd.DataFrame({t: d["Volume"] for t, d in usd.items()}).reindex(C.index)
    bl = baseline(C, V, "SPY", set(universe.SECTOR_ETF.values()) | {"SPY"}, 1e6)
    out["baseline_us"] = stats(bl.x20, bl.x60, bl.date, bench="SPY", note="Sammenligningsgrunnlag: alle likvide S&P 500-aksjer hver 21. handelsdag.")
    out["ose_contract"], out["ose_insider_buy"], out["unusual_volume_ose"], out["baseline_ose"] = oslo()
    out["theme_market"] = {"n": 0, "note": "Ingen historikk: tema-score med markedsbekreftelse (olje/prediksjonsmarked) kan ikke rekonstrueres bakover med dataene vi har."}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    r = build(sys.argv[1] if len(sys.argv) > 1 else None)
    for k, v in r.items():
        if k.startswith("_"):
            continue
        print(k, {x: (round(y, 4) if isinstance(y, float) else y) for x, y in v.items() if x != "note"})
