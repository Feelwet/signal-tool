"""Historical sanity check of the Kjøp-kandidat rules (signaltool/categories.py) on past events.

What CAN be tested with data we have:
  A) US insider-purchase clusters (SEC data sets 2022-2025, officers/directors, same events as reports/backtest.md)
  B) Large US DoD contract awards (USAspending, >= $100M new awards 2022-2026, mapped to listed contractors)
  C) Both within 30 days for the same ticker (= the '>= 2 independent signal types' rule)
For every event the price-based rules are evaluated with data up to the event day: close > 50-day average,
20-day return > S&P 500 (SPY), not stretched, no >= 20 % crash in 20 sessions, price >= $1.
NOT testable historically: Oslo Newsweb contracts, theme/oil confirmation, short interest (US), liquidity (no volume
in the price cache). Entry = close of the first trading day after the event (as in reports/backtest.md).
"""
from __future__ import annotations
import logging
from datetime import date
import numpy as np
import pandas as pd
from .. import http
from ..config import CACHE, REPORTS
from ..categories import RULES
from ..themes import NAME_TO_TICKER
from .common import fwd_returns, summarize, fmt
from . import insider

log = logging.getLogger(__name__)
API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
DOD_CACHE = CACHE / "insider_ds" / "dod_awards_hist.csv"


def dod_awards(start_year=2022, min_amount=100_000_000) -> pd.DataFrame:
    if DOD_CACHE.exists():
        return pd.read_csv(DOD_CACHE, parse_dates=["date"])
    rows = []
    today = date.today()
    for y in range(start_year, today.year + 1):
        for q, (m1, m2, d2) in enumerate([(1, 3, 31), (4, 6, 30), (7, 9, 30), (10, 12, 31)], 1):
            if date(y, m1, 1) > today:
                break
            for page in range(1, 6):
                body = {"filters": {"award_type_codes": ["A", "B", "C", "D"],
                                    "agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}],
                                    "time_period": [{"start_date": f"{y}-{m1:02d}-01", "end_date": f"{y}-{m2:02d}-{d2}", "date_type": "new_awards_only"}],
                                    "award_amounts": [{"lower_bound": min_amount}]},
                        "fields": ["Award ID", "Recipient Name", "Award Amount", "Start Date", "Base Obligation Date"],
                        "sort": "Award Amount", "order": "desc", "limit": 100, "page": page}
                try:
                    j = http.get_json(API, method="POST", json_body=body, timeout=120)
                except Exception as e:
                    log.warning("usaspending %s q%s p%s: %s", y, q, page, e)
                    break
                rows += j.get("results", [])
                if not j.get("page_metadata", {}).get("hasNext"):
                    break
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    up = df["Recipient Name"].fillna("").str.upper()
    df["ticker"] = up.map(lambda n: next((v for k, v in NAME_TO_TICKER.items() if v and k in n), None))
    df["date"] = pd.to_datetime(df["Base Obligation Date"].fillna(df["Start Date"]), errors="coerce")
    df = df.dropna(subset=["ticker", "date"])
    df = df[df["ticker"].str.fullmatch(r"[A-Z]{1,5}", na=False)]  # US listings only (SPY benchmark)
    df = df.rename(columns={"Award Amount": "amount"})[["ticker", "date", "amount", "Recipient Name"]]
    df.to_csv(DOD_CACHE, index=False)
    return df


def dedupe(ev: pd.DataFrame, cooldown=30) -> pd.DataFrame:
    out = []
    for t, g in ev.sort_values("date").groupby("ticker"):
        last = None
        for _, r in g.iterrows():
            if last is None or (r["date"] - last).days >= cooldown:
                out.append(r); last = r["date"]
    return pd.DataFrame(out)


def rule_state(c: pd.Series, spy: pd.Series, d) -> dict | None:
    c = c.dropna()
    p = c.index.searchsorted(pd.Timestamp(d), side="right") - 1  # last close known on the event day
    if p < 50:
        return None
    w = c.iloc[: p + 1]
    close, sma = w.iloc[-1], w.iloc[-50:].mean()
    r5, r20 = close / w.iloc[-6] - 1, close / w.iloc[-21] - 1
    sp = spy.dropna()
    q = sp.index.searchsorted(w.index[-1], side="right") - 1
    if q < 21:
        return None
    b20 = sp.iloc[q] / sp.iloc[q - 20] - 1
    l20 = w.iloc[-20:]
    dd = (l20 / l20.cummax() - 1).min()
    price_ok = close > sma and r20 > b20
    stretched = r5 >= RULES["stretch_5d"] or r20 >= RULES["stretch_20d"] or close / sma - 1 >= RULES["stretch_sma"]
    flags = dd <= RULES["crash"] or close < RULES["min_price_usd"]
    return {"price_ok": price_ok, "stretched": stretched, "flags": flags,
            "kjop_rules": price_ok and not stretched and not flags, "hold_like": price_ok and stretched and not flags}


def evaluate(events: pd.DataFrame, px: pd.DataFrame, spy: pd.Series) -> pd.DataFrame:
    rows = []
    for _, e in events.iterrows():
        if e["ticker"] not in px.columns:
            continue
        c = px[e["ticker"]].dropna()
        st = rule_state(c, spy, e["date"])
        if st is None:
            continue
        fr, fs = fwd_returns(c, [e["date"]], (20, 60), entry_lag=2), fwd_returns(spy, [e["date"]], (20, 60), entry_lag=2)
        if fr.empty or fs.empty:
            continue
        rows.append({"ticker": e["ticker"], "date": e["date"], **st,
                     "x20": fr["r20"].iloc[0] - fs["r20"].iloc[0], "x60": fr["r60"].iloc[0] - fs["r60"].iloc[0]})
    return pd.DataFrame(rows)


def table(name: str, r: pd.DataFrame) -> list[str]:
    L = [f"### {name}", "| Gruppe | 20 handelsdager (meravkastning vs SPY) | 60 handelsdager |", "|---|---|---|"]
    if r.empty:
        return L + ["| (ingen hendelser med kursdata) | | |", ""]
    groups = [("Alle hendelser", r), ("Oppfyller kurs-/flaggreglene for Kjøp (kursbekreftelse, ikke strukket, ingen krasj/penny)", r[r["kjop_rules"]]),
              ("«Hold-lignende» (kursbekreftelse, men strukket)", r[r["hold_like"]]),
              ("Oppfyller IKKE kursbekreftelse / har flagg", r[~r["kjop_rules"] & ~r["hold_like"]])]
    for g, d in groups:
        L.append(f"| {g} | {fmt(summarize(d['x20']))} | {fmt(summarize(d['x60']))} |")
    return L + [""]


def run() -> str:
    p = insider.load_purchases()
    cl, _ = insider.find_events(p)
    cl = cl.rename(columns={"date": "date"})
    dod = dod_awards()
    dod_ev = dedupe(dod) if not dod.empty else dod
    tick = sorted(set(cl["ticker"]) | set(dod_ev.get("ticker", [])) | {"SPY"})
    px = insider.prices(tick)
    spy = px["SPY"].dropna()
    ra = evaluate(cl, px, spy)
    rb = evaluate(dod_ev, px, spy) if not dod_ev.empty else pd.DataFrame()
    both = []
    if not dod_ev.empty and not cl.empty:
        for _, e in dod_ev.iterrows():
            m = cl[(cl["ticker"] == e["ticker"]) & ((cl["date"] - e["date"]).abs().dt.days <= 30)]
            if len(m):
                both.append({"ticker": e["ticker"], "date": max(e["date"], m["date"].max())})
    rc = evaluate(pd.DataFrame(both), px, spy) if both else pd.DataFrame()
    L = ["## Historisk sjekk av Kjøp-kandidat-reglene",
         f"_Beregnet {date.today().isoformat()} fra nedlastede data (signaltool/backtest/categories_check.py). Ingen tall er satt inn manuelt._", "",
         "Reglenes kursdel (kurs over 50-dagers snitt, 20d-avkastning bedre enn SPY, ikke strukket, ikke ≥ 20 % krasj, kurs ≥ $1) er brukt på "
         "historiske hendelser med data kjent på hendelsesdagen. Inngang = sluttkurs første handelsdag etter hendelsen. Meravkastning = aksje − SPY.", "",
         f"Hendelser: A) {len(cl)} innsidekjøp-klynger (SEC 2022–2025, ledelse/styre), med kursdata: {len(ra)}. "
         f"B) {len(dod_ev)} store DoD-kontrakter (USAspending ≥ $100M, 2022–, koblet til børsnoterte leverandører, 30 d karantene), med kursdata: {len(rb)}. "
         f"C) begge innen 30 dager for samme ticker («≥ 2 uavhengige signaltyper»): {len(both)}, med kursdata: {len(rc)}.", ""]
    L += table("A) Innsidekjøp-klynger", ra) + table("B) Store DoD-kontrakter", rb) + table("C) Kontrakt + innsideklynge (to uavhengige typer)", rc)
    L += ["**Forbehold:** Newsweb-kontrakter, tema/olje-bekreftelse, shortdata og likviditet finnes ikke historisk her og er ikke testet. "
          "USAspending-dato (obligasjonsdato) er ikke alltid samme dag som offentlig kunngjøring. Overlevelsesskjevhet (avnoterte aksjer mangler), "
          "ingen kurtasje/spread, overlappende hendelser, og flere grupper sammenlignet (multippel testing). "
          "t-verdier under ca. 2 betyr at forskjellen ikke kan skilles fra tilfeldigheter."]
    txt = "\n".join(L)
    out = REPORTS / "backtest_categories.md"
    old = out.read_text() if out.exists() else ""
    keep = old[old.index("\n## Tolkning"):] if "\n## Tolkning" in old else ""  # hand-written interpretation is kept
    out.write_text(txt + "\n" + keep)
    return txt
