"""Forhåndsregistrert poengtest (AnalBot, låst 29.10.2026). IKKE juster parametere.

Spesifikasjon (låst før data ble sett):
  univers   alle rader med poengsum (score), US og Oslo, samme historikk som regeltest_2026-10.md (rules_full.py)
  mål       avkastning 20 handelsdager fram fra neste sluttkurs minus indeks (OSEBX for .OL, loggens benchmark for US)
  per dato  Spearman rang-IC og topp-desil minus bunn-desil
  t         klynget per dato (snitt per dato, i.i.d.-t over datoer; aldri HAC-lag > n/4)
  perm      1000 permutasjoner, score stokkes innen dato, seed 42
  IS/OOS    første 60 % av datoene = IS, resten OOS (som regeltest)
  PASS      OOS IC t > 2 OG IS IC samme fortegn OG topp−bunn > 0 i begge halvdeler; dom på samlet (US+Oslo)
  survivorship alltid FLAG

Kjøring: PYTHONPATH=. python -m signaltool.backtest.poengtest
Skriptet sjekker først om historiske poengsummer kan rekonstrueres. Kan de ikke det, stopper det (ingen tall diktes).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "logs" / "categories.csv"
H, IS_FRAC, NPERM, SEED = 20, 0.60, 1000, 42
REGELTEST_START = {"US": "2022-01-01", "Oslo": "2019-01-01"}   # historikken i regeltest_2026-10.md

# Komponenter i score (pipeline.py: e["score"] = sum(points)) og om de finnes punkt-i-tid bakover
COMPONENTS = {
    "insider_cluster": "SEC Form 4 2022–2025: ja (rules_full)",
    "federal_award / dod_contract": "USAspending ≥ $100M: delvis (live bruker ≥ $25M + daglig DoD-liste)",
    "ose_contracts": "Newsweb-titler 2019–: ja",
    "ose_insider_notices": "Newsweb: delvis (retning ukjent)",
    "congress_buys": "House PTR: delvis, FLAG (ticker-hull 45–52 %)",
    "pead": "yfinance-rapporter: ja (US)",
    "unusual_volume / price_move": "kurs/volum: ja for S&P 500, ellers mangler volum",
    "reddit_mentions": "NEI: data/history/reddit.csv dekker bare 2026-08-31–2026-09-28",
    "theme_attention (0,75 × temascore)": "NEI: ingen historiske temascorer (logs/theme_score.csv fra 25.10.2026)",
    "utvalg (topp 60 med score > 0)": "NEI: ikke-valgte tickere har ingen logget score",
}


def ic_day(g: pd.DataFrame) -> float:
    return g["score"].rank().corr(g["fwd"].rank()) if len(g) >= 10 else np.nan


def tb_day(g: pd.DataFrame) -> float:
    if len(g) < 10:
        return np.nan
    q = g["score"].rank(pct=True, method="first")
    return g.loc[q > 0.9, "fwd"].mean() - g.loc[q <= 0.1, "fwd"].mean()


def tstat(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 else np.nan


def run_test(panel: pd.DataFrame) -> dict:
    """panel: date, ticker, score, fwd (20d meravkastning). Kalles bare når historikken finnes."""
    dates = np.sort(panel["date"].unique())
    cut = dates[int(len(dates) * IS_FRAC)]
    ic = panel.groupby("date").apply(ic_day)
    tb = panel.groupby("date").apply(tb_day)
    out = {"n_dates": len(dates), "n_obs": len(panel),
           "ic_is": ic[ic.index < cut].mean(), "t_is": tstat(ic[ic.index < cut]),
           "ic_oos": ic[ic.index >= cut].mean(), "t_oos": tstat(ic[ic.index >= cut])}
    half = dates[len(dates) // 2]
    out["tb_h1"], out["tb_h2"] = tb[tb.index < half].mean(), tb[tb.index >= half].mean()
    rng = np.random.default_rng(SEED)
    obs, null = ic.mean(), []
    for _ in range(NPERM):
        p = panel.copy()
        p["score"] = p.groupby("date")["score"].transform(lambda s: rng.permutation(s.values))
        null.append(p.groupby("date").apply(ic_day).mean())
    out["perm_p"] = float((np.sum(np.abs(null) >= abs(obs)) + 1) / (NPERM + 1))
    out["pass"] = bool(out["t_oos"] > 2 and np.sign(out["ic_is"]) == np.sign(out["ic_oos"]) and out["tb_h1"] > 0 and out["tb_h2"] > 0)
    return out


def coverage() -> pd.DataFrame:
    d = pd.read_csv(LOG)
    d = d[d["score"].notna()].copy()
    d["mkt"] = np.where(d["ticker"].str.endswith(".OL"), "Oslo", "US")
    rows = []
    for m, g in list(d.groupby("mkt")) + [("Samlet", d)]:
        pdates = np.sort(g["price_date"].dropna().unique())          # handelsdager sett i loggen
        complete = [x for i, x in enumerate(pdates) if len(pdates) - 1 - i >= H + 1]   # neste sluttkurs + 20
        rows.append({"marked": m, "første logg": g["date"].min(), "siste logg": g["date"].max(),
                     "rader m/score": len(g), "kursdatoer": len(pdates),
                     "datoer med full 20d": len(complete)})
    return pd.DataFrame(rows)


def main() -> int:
    print("Komponenter i score og punkt-i-tid-historikk:")
    for k, v in COMPONENTS.items():
        print(f"  {k}: {v}")
    d = pd.read_csv(LOG)
    first = d.loc[d["score"].notna(), "date"].min()
    print(f"\nTidligste loggede score: {first} (logs/categories.csv). Regeltest-historikk starter {REGELTEST_START}.")
    print(coverage().to_string(index=False))
    if first > min(REGELTEST_START.values()):
        print("\nSTOPP: historiske poengsummer kan ikke rekonstrueres for regeltest-perioden "
              "(temascore, Reddit og topp-60-utvalget finnes ikke punkt-i-tid). Testen kjøres ikke. Ingen tall beregnet.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
