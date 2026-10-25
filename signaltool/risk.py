"""Risikonivå Høy/Middels/Lav (AnalBots test, reports/natt/risiko.md – BESTÅTT).

Kompositten regnes likt som signaltool/backtest/risk_levels.py, per marked og per uke:
  vol = 60-dagers std av daglig avkastning (|r| > 50 % fjernet) · sqrt(252)
  dd  = største fall fra topp siste 252 dager
  liq = median omsetning (kurs · volum) siste 60 dager
  comp = (rank(vol) + rank(-dd) + rank(-liq)) / 3, prosentrang innen markedets univers den uka.
Krav: ≥ 252 kursdager, handlet siste 5 dager, alle tre mål finnes; Oslo også kurs ≥ 1,0.
Univers: US = S&P 500 (risk_universe_us.txt), Oslo = oslo_universe.txt. Tickere utenfor universet rangeres mot universet.
Grenser (fryst på IS): US Lav < 0,407 ≤ Middels < 0,596 ≤ Høy; Oslo Lav < 0,387 ≤ Middels < 0,609 ≤ Høy.
Nivået sier ingenting om avkastning. Resultat lagres i data/cache/risk_levels.json og logs/risk_levels.csv (privat)."""
from __future__ import annotations

import csv, json, logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CACHE, LOGS

log = logging.getLogger(__name__)
TH = {"US": (0.407, 0.596), "Oslo": (0.387, 0.609)}
LEVELS = ("Lav", "Middels", "Høy")
ETF_X = {"SPY", "OSEBX.OL", "XLK", "XLV", "XLF", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB"}
CPATH = CACHE / "risk_levels.json"
LPATH = LOGS / "risk_levels.csv"
HERE = Path(__file__).parent


def market(t: str) -> str:
    return "Oslo" if t.endswith(".OL") else "US"


def universe(mk: str) -> list[str]:
    f = HERE / ("oslo_universe.txt" if mk == "Oslo" else "risk_universe_us.txt")
    return sorted({l.strip() for l in f.read_text().splitlines() if l.strip() and not l.startswith("#")} - ETF_X)


def level(comp: float | None, mk: str) -> str | None:
    if comp is None or comp != comp:
        return None
    a, b = TH[mk]
    return "Lav" if comp < a else "Middels" if comp < b else "Høy"


def _download(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    from . import http
    from .data_quality import clean_universe
    out = {}
    for i in range(0, len(tickers), 100):
        ch = tickers[i:i + 100]
        try:
            d = http.yf_download(ch, period="3y", progress=False, auto_adjust=True, group_by="ticker", threads=True)
        except Exception as ex:
            log.warning("risk download: %s", ex)
            continue
        for t in ch:
            try:
                df = d[t][["Close", "Volume", "High", "Low"]].dropna(subset=["Close"])
            except KeyError:
                continue
            if len(df):
                df.index = pd.to_datetime(df.index).tz_localize(None)
                out[t] = df
    out = clean_universe(out)[0]
    C = pd.DataFrame({t: v["Close"] for t, v in out.items()}).sort_index()
    V = pd.DataFrame({t: v["Volume"] for t, v in out.items()}).reindex(C.index)
    return C, V


def _metrics(C: pd.DataFrame, V: pd.DataFrame):
    R = C.pct_change(fill_method=None)
    R = R.mask(R.abs() > 0.5)
    vol = R.rolling(60, min_periods=50).std() * np.sqrt(252)
    Cc = (1 + R.fillna(0)).cumprod().where(C.notna())
    dd = (Cc / Cc.rolling(252, min_periods=240).max() - 1).rolling(252, min_periods=240).min()
    liq = (C * V).rolling(60, min_periods=50).median()
    return vol, dd, liq


def week_date(idx: pd.DatetimeIndex, today: date) -> pd.Timestamp:
    """Siste handelsdag i siste fullførte uke (lør/søn: inneværende uke er fullført)."""
    wk = idx.to_series().groupby(idx.to_period("W")).max()
    cur = pd.Timestamp(today).to_period("W")
    if today.weekday() < 5:
        wk = wk[wk.index < cur]
    return pd.Timestamp(wk.iloc[-1])


def compute_market(mk: str, extra: list[str], today: date) -> tuple[dict, str]:
    uni = universe(mk)
    ext = sorted(set(extra) - set(uni) - ETF_X)
    C, V = _download(uni + ext)
    d = week_date(C.index, today)
    vol, dd, liq = _metrics(C, V)
    hist = C.notna().cumsum()
    recent = C.notna().rolling(5).sum() > 0
    ok = (hist.loc[d] >= 252) & recent.loc[d] & vol.loc[d].notna() & dd.loc[d].notna() & liq.loc[d].notna()
    if mk == "Oslo":
        ok &= C.loc[d] >= 1.0
    ok = ok[ok].index
    base = [t for t in ok if t in uni]
    df = pd.DataFrame({"vol": vol.loc[d, base], "ndd": -dd.loc[d, base], "nliq": -liq.loc[d, base]})
    comp = (df["vol"].rank(pct=True) + df["ndd"].rank(pct=True) + df["nliq"].rank(pct=True)) / 3
    out = {t: float(comp[t]) for t in base}
    for t in ext:                 # utenfor universet: prosentrang i (univers ∪ {t})
        if t not in ok:
            continue
        x = {"vol": vol.loc[d, t], "ndd": -dd.loc[d, t], "nliq": -liq.loc[d, t]}
        r = [(pd.concat([df[k], pd.Series({t: x[k]})]).rank(pct=True))[t] for k in x]
        out[t] = float(np.mean(r))
    log.info("risk %s %s: %d i universet, %d utenfor", mk, d.date(), len(base), len(out) - len(base))
    return out, str(d.date())


def refresh(tickers: list[str], today: date | None = None, force: bool = False) -> dict:
    """{ticker: {"level","comp","market","date","in_universe"}}; regnes på nytt én gang per uke (cache), ellers fra cache."""
    today = today or date.today()
    cache = json.loads(CPATH.read_text()) if CPATH.exists() else {}
    need = set(tickers) - set(cache.get("levels", {}))
    stale = cache.get("for_week") != str(pd.Timestamp(today).to_period("W")) or cache.get("weekday_lt5") != (today.weekday() < 5)
    if not force and cache and not stale and not need:
        return cache["levels"]
    levels, dates = {}, {}
    for mk in ("US", "Oslo"):
        ex = [t for t in tickers if market(t) == mk]
        try:
            comp, d = compute_market(mk, ex, today)
        except Exception as e:
            log.warning("risk %s failed: %s", mk, e)
            continue
        uni = set(universe(mk))
        for t, c in comp.items():
            if t in uni or t in ex:
                levels[t] = {"level": level(c, mk), "comp": round(c, 4), "market": mk, "date": d, "in_universe": t in uni}
        dates[mk] = d
    if not levels:
        return cache.get("levels", {})
    CPATH.parent.mkdir(parents=True, exist_ok=True)
    CPATH.write_text(json.dumps({"for_week": str(pd.Timestamp(today).to_period("W")), "weekday_lt5": today.weekday() < 5,
                                 "dates": dates, "levels": levels}))
    _log(levels)
    return levels


def _log(levels: dict) -> None:
    have = set()
    if LPATH.exists():
        with LPATH.open() as f:
            have = {(r["date"], r["ticker"]) for r in csv.DictReader(f)}
    new = [(v["date"], t, v["market"], v["comp"], v["level"], int(v["in_universe"])) for t, v in sorted(levels.items()) if (v["date"], t) not in have]
    if not new:
        return
    head = not LPATH.exists()
    with LPATH.open("a", newline="") as f:
        w = csv.writer(f)
        if head:
            w.writerow(["date", "ticker", "market", "comp", "level", "in_universe"])
        w.writerows(new)
