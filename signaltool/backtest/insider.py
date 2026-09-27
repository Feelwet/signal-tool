"""Backtest: US insider open-market purchase clusters (SEC Form 3/4/5 quarterly data sets) vs SPY.

Only officers/directors count (10%-owner funds excluded). Cluster event: >= 3 distinct insiders file open-market purchases (code P) in the same issuer within 30
calendar days, combined value >= $100k; event date = filing date that completes the cluster (the
information date). Cooldown 90 days per ticker. Comparison group: 'single' purchases (exactly one insider
buying in the window, value >= $25k), random sample. Entry at the close of the first trading day AFTER
the filing date. Excess return = stock return - SPY return over the same days.
"""
from __future__ import annotations
import io, logging, zipfile
import numpy as np
import pandas as pd
import yfinance as yf
from .. import http
from ..config import CACHE
from .common import fwd_returns, summarize, fmt

log = logging.getLogger(__name__)
QUARTERS = [f"{y}q{q}" for y in range(2022, 2026) for q in range(1, 5)]
URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{}_form345.zip"
DIR = CACHE / "insider_ds"
DIR.mkdir(parents=True, exist_ok=True)


def load_purchases() -> pd.DataFrame:
    out = DIR / "purchases_od.csv.gz"
    if out.exists():
        return pd.read_csv(out, parse_dates=["filing_date"])
    frames = []
    for q in QUARTERS:
        r = http.get(URL.format(q), timeout=180)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        sub = pd.read_csv(z.open("SUBMISSION.tsv"), sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERTRADINGSYMBOL"])
        tr = pd.read_csv(z.open("NONDERIV_TRANS.tsv"), sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "TRANS_CODE", "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
        ow = pd.read_csv(z.open("REPORTINGOWNER.tsv"), sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"]).drop_duplicates("ACCESSION_NUMBER")
        # officers/directors only: excludes funds / 10% owners whose affiliated entities would fake 'clusters'
        ow = ow[ow["RPTOWNER_RELATIONSHIP"].fillna("").str.contains("Director|Officer", case=False)]
        tr = tr[(tr["TRANS_CODE"] == "P") & (tr["TRANS_ACQUIRED_DISP_CD"] == "A")]
        tr["value"] = pd.to_numeric(tr["TRANS_SHARES"], errors="coerce") * pd.to_numeric(tr["TRANS_PRICEPERSHARE"], errors="coerce")
        tr = tr.groupby("ACCESSION_NUMBER", as_index=False)["value"].sum()
        df = tr.merge(sub[sub["DOCUMENT_TYPE"].isin(["4", "4/A"])], on="ACCESSION_NUMBER").merge(ow, on="ACCESSION_NUMBER")
        df["filing_date"] = pd.to_datetime(df["FILING_DATE"], format="%d-%b-%Y", errors="coerce")
        frames.append(df[["filing_date", "ISSUERTRADINGSYMBOL", "RPTOWNERCIK", "value"]])
        log.info("%s: %d purchase filings", q, len(df))
    p = pd.concat(frames).rename(columns={"ISSUERTRADINGSYMBOL": "ticker", "RPTOWNERCIK": "owner"})
    p["ticker"] = p["ticker"].str.upper().str.strip()
    p = p[p["ticker"].str.fullmatch(r"[A-Z]{1,5}", na=False) & (p["value"] > 0)]
    p.to_csv(out, index=False)
    return p


def find_events(p: pd.DataFrame, min_insiders=3, window=30, min_value=100_000, cooldown=90):
    clusters, singles = [], []
    for t, g in p.sort_values("filing_date").groupby("ticker"):
        last_ev = None
        dates = g["filing_date"].values
        for i in range(len(g)):
            d = g["filing_date"].iloc[i]
            w = g[(g["filing_date"] > d - pd.Timedelta(days=window)) & (g["filing_date"] <= d)]
            n = w["owner"].nunique()
            if last_ev is not None and (d - last_ev).days < cooldown:
                continue
            if n >= min_insiders and w["value"].sum() >= min_value:
                clusters.append({"ticker": t, "date": d, "n": n, "value": w["value"].sum()}); last_ev = d
            elif n == 1 and g["value"].iloc[i] >= 25_000:
                around = g[(g["filing_date"] > d - pd.Timedelta(days=window)) & (g["filing_date"] <= d + pd.Timedelta(days=window))]
                if around["owner"].nunique() == 1:
                    singles.append({"ticker": t, "date": d, "n": 1, "value": g["value"].iloc[i]}); last_ev = d
    return pd.DataFrame(clusters), pd.DataFrame(singles)


def prices(tickers, start="2021-12-01"):
    cp = DIR / "prices.csv.gz"
    have = pd.read_csv(cp, index_col=0, parse_dates=True) if cp.exists() else pd.DataFrame()
    need = [t for t in tickers if t not in have.columns]
    for i in range(0, len(need), 150):
        chunk = need[i:i + 150]
        try:
            d = yf.download(chunk, start=start, progress=False, auto_adjust=True, threads=True)["Close"]
            if isinstance(d, pd.Series):
                d = d.to_frame(chunk[0])
            have = pd.concat([have, d.reindex(columns=chunk)], axis=1)
        except Exception as e:
            log.warning("price chunk failed: %s", e)
    have = have.loc[:, ~have.columns.duplicated()]
    have.index = pd.to_datetime(have.index)
    have = have.sort_index()
    have.to_csv(cp)
    return have


def evaluate(events: pd.DataFrame, px: pd.DataFrame, spy: pd.Series, horizons=(5, 20, 60)):
    rows = []
    for _, e in events.iterrows():
        if e["ticker"] not in px.columns:
            continue
        c = px[e["ticker"]].dropna()
        if c.empty:
            continue
        pos = c.index.searchsorted(e["date"])
        if pos >= len(c) or c.iloc[min(pos, len(c) - 1)] < 1.0:   # skip sub-$1 stocks
            continue
        fr = fwd_returns(c, [e["date"]], horizons, entry_lag=2)   # day after filing (filings often after close)
        fs = fwd_returns(spy, [e["date"]], horizons, entry_lag=2)
        if fr.empty or fs.empty:
            continue
        r = {"ticker": e["ticker"], "date": e["date"], "n": e["n"]}
        for h in horizons:
            r[f"x{h}"] = fr[f"r{h}"].iloc[0] - fs[f"r{h}"].iloc[0]
            r[f"r{h}"] = fr[f"r{h}"].iloc[0]
        rows.append(r)
    return pd.DataFrame(rows)


def run() -> str:
    p = load_purchases()
    cl, si = find_events(p)
    si_s = si.sample(min(len(si), 700), random_state=42) if len(si) else si
    tick = sorted(set(cl["ticker"]) | set(si_s["ticker"]) | {"SPY"})
    px = prices(tick)
    spy = px["SPY"].dropna() if "SPY" in px.columns else pd.Series(dtype=float)
    if spy.empty:  # benchmark must never be silently missing
        spy = yf.download("SPY", start="2021-12-01", progress=False, auto_adjust=True)["Close"].squeeze().dropna()
        px["SPY"] = spy
        px.to_csv(DIR / "prices.csv.gz")
    rc, rs = evaluate(cl, px, spy), evaluate(si_s, px, spy)
    rc.to_csv(DIR / "cluster_results.csv", index=False)
    L = ["## Innsidekjøp-klynger (USA, SEC Form 4) – historisk test",
         f"Data: SEC Insider Transactions Data Sets {QUARTERS[0]}–{QUARTERS[-1]}; {len(p):,} kjøpsmeldinger (kode P). "
         f"Klynger funnet: {len(cl)}, med kursdata: {len(rc)}. Enkeltkjøp (sammenligning, tilfeldig utvalg): {len(si_s)}, med kursdata: {len(rs)}.",
         "Inngang: sluttkurs første handelsdag etter innleveringsdato. Meravkastning = aksje − SPY. Aksjer under $1 utelatt.", ""]
    L.append("| Horisont | Klynger (≥3 innsidere) meravkastning | Enkeltkjøp meravkastning |")
    L.append("|---|---|---|")
    for h in (5, 20, 60):
        L.append(f"| {h} handelsdager | {fmt(summarize(rc.get(f'x{h}', pd.Series(dtype=float))))} | {fmt(summarize(rs.get(f'x{h}', pd.Series(dtype=float))))} |")
    if len(rc):
        rc["year"] = pd.to_datetime(rc["date"]).dt.year
        L.append("\nPer år (klynger, 20d meravkastning): " + "; ".join(f"{y}: {fmt(summarize(g['x20']))}" for y, g in rc.groupby("year")))
        L.append(f"\nWinsorisert (1/99 %) snitt 20d, klynger: {rc['x20'].clip(rc['x20'].quantile(.01), rc['x20'].quantile(.99)).mean()*100:+.2f}%")
    L += ["", "**Forbehold:** Overlevelsesskjevhet (yfinance mangler mange avnoterte aksjer – trolig skjevhet oppover), "
          "ingen handelskostnader/spread (viktig for småselskaper), overlappende hendelser gir for optimistiske t-verdier, "
          "ticker-endringer kan gi feil kobling. Snitt drives ofte av få ekstreme småselskaper – se median."]
    return "\n".join(L)
