"""Ferskhet for sluttkurser (AnalBot 28.10).

Funn 28.10: i hver morgenkjøring (≈07 norsk tid) manglet Yahoo-dagsbaren for forrige Oslo-handelsdag i det samlede
yfinance-kallet (range=2y), mens US-tickerne hadde forrige dag. Kveldskjøringer hadde riktig dag. I tillegg godtok
Oslo-universet (temakart-radene) en kurs-cache med siste bar inntil 5 kalenderdager gammel.

- expected_session(): siste børsdag (man–fre) der børsen har stengt, i børsens tidssone. Helligdager er ikke med; da blir
  en ticker bare forsøkt hentet på nytt, ingen verdi endres.
- repair_lagging(): tickere med siste bar eldre enn forventet hentes på nytt med eksplisitt start/slutt (period1/period2,
  ett samlet kall). Mangler baren fortsatt, brukes Yahoos egen sluttkurs fra chart-metadata (regularMarketPrice på
  regularMarketTime) bare når den datoen er en ferdig handelsdag. Ingen verdier diktes opp.
- tdays_old(): handelsdager (man–fre) fra siste kurs til kjøringsdatoen.
"""
from __future__ import annotations
import logging
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)
MAX_TD = 2          # AnalBot 28.10: avkastning skjules når siste kurs er mer enn 2 handelsdager gammel
# suffiks -> (tidssone, stengetid lokal tid; litt etter sluttauksjonen)
EXCH = {".OL": ("Europe/Oslo", dtime(16, 40)), ".L": ("Europe/London", dtime(16, 50)), "": ("America/New_York", dtime(16, 15))}


def exchange_of(ticker: str):
    t = str(ticker or "")
    if not t or "=" in t:
        return None                      # futures/FX: handles nesten døgnet rundt, ingen enkel «forventet dag»
    if t.startswith("^"):
        return EXCH[".OL"] if t.upper().startswith("^OSE") else EXCH[""]
    for suf in (".OL", ".L"):
        if t.endswith(suf):
            return EXCH[suf]
    return EXCH[""] if "." not in t or t.count(".") == 1 and len(t.split(".")[1]) == 1 else None   # BRK.B o.l. = US


def expected_session(ticker: str, now: datetime | None = None) -> date | None:
    ex = exchange_of(ticker)
    if not ex:
        return None
    tz = ZoneInfo(ex[0])
    now = (now or datetime.now(tz)).astimezone(tz)
    d = now.date() if now.time() >= ex[1] else now.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def tdays_old(last: str | date | None, run: str | date | None) -> int | None:
    """Handelsdager (man–fre) fra siste kurs til kjøringsdatoen; 0 = samme dag. None ved ukjent dato."""
    if not last or not run:
        return None
    try:
        a, b = date.fromisoformat(str(last)[:10]), date.fromisoformat(str(run)[:10])
    except ValueError:
        return None
    return int(np.busday_count(a, b)) if b >= a else 0


def is_stale(last, run, max_td: int = MAX_TD) -> bool:
    n = tdays_old(last, run)
    return n is not None and n > max_td


def _last(df) -> date | None:
    try:
        s = df["Close"].dropna()
        return pd.Timestamp(s.index[-1]).date() if len(s) else None
    except Exception:
        return None


def lagging(frames: dict, now: datetime | None = None) -> dict[str, tuple[date, date]]:
    """{ticker: (siste bar, forventet)} for tickere som ligger bak forventet handelsdag."""
    out = {}
    for t, df in (frames or {}).items():
        exp, last = expected_session(t, now), _last(df)
        if exp and last and last < exp:
            out[t] = (last, exp)
    return out


def _merge(df: pd.DataFrame, new: pd.DataFrame, after: date) -> pd.DataFrame:
    """Legg til rader fra `new` som er nyere enn `after` (bare kolonnene df har). Eksisterende rader endres ikke."""
    if new is None or not len(new):
        return df
    new = new.copy()
    new.index = pd.to_datetime(new.index)
    if getattr(new.index, "tz", None) is not None:
        new.index = new.index.tz_localize(None)
    new = new[[c for c in df.columns if c in new.columns]].dropna(subset=["Close"])
    new = new[[ts.date() > after for ts in new.index]]
    if not len(new):
        return df
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        new.index = new.index.tz_localize(idx.tz)
    return pd.concat([df, new.reindex(columns=df.columns)]).sort_index()


def _refetch(tickers: list[str], start: date, now: datetime) -> dict[str, pd.DataFrame]:
    from . import http as _http
    end = (now + timedelta(days=1)).date()
    d = _http.yf_download(sorted(tickers), start=start.isoformat(), end=end.isoformat(), progress=False, auto_adjust=True,
                          group_by="ticker", threads=True, tries=2)
    out = {}
    for t in tickers:
        try:
            out[t] = d[t] if len(tickers) > 1 or isinstance(d.columns, pd.MultiIndex) else d
        except KeyError:
            pass
    return out


def _meta_close(ticker: str):
    """(dato, sluttkurs) fra Yahoos chart-metadata (regularMarketTime/regularMarketPrice), eller None."""
    import yfinance as yf
    tk = yf.Ticker(ticker)
    tk.history(period="5d", auto_adjust=True)
    m = tk.history_metadata or {}
    ts, px, tz = m.get("regularMarketTime"), m.get("regularMarketPrice"), m.get("exchangeTimezoneName")
    if not ts or not px:
        return None
    if isinstance(ts, (int, float)):
        ts = pd.Timestamp(ts, unit="s", tz="UTC")
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return (ts.tz_convert(tz or "UTC").date(), float(px))


def repair_lagging(frames: dict, now: datetime | None = None, refetch=None, meta=None, max_meta: int = 80) -> dict:
    """Henter tickere som ligger bak forventet handelsdag på nytt (in place i `frames`). Returnerer
    {"lagging": n, "refetched": [...], "meta": [...], "still": {t: siste}}."""
    now = now or datetime.now(ZoneInfo("Europe/Oslo"))
    lag = lagging(frames, now)
    info = {"lagging": len(lag), "refetched": [], "meta": [], "still": {}}
    if not lag:
        return info
    log.info("freshness: %d tickere bak forventet dag: %s", len(lag), {t: (str(a), str(b)) for t, (a, b) in list(lag.items())[:20]})
    refetch = refetch or _refetch
    try:
        got = refetch(list(lag), min(a for a, _ in lag.values()) - timedelta(days=10), now)
    except Exception as ex:
        log.warning("freshness refetch: %s", ex); got = {}
    for t, (last, exp) in lag.items():
        if t in got:
            frames[t] = _merge(frames[t], got[t], last)
            if (_last(frames[t]) or last) > last:
                info["refetched"].append(t)
    meta = meta or _meta_close
    for t, (last, exp) in list(lagging({t: frames[t] for t in lag}, now).items())[:max_meta]:
        try:
            mc = meta(t)
        except Exception as ex:
            log.info("freshness meta %s: %s", t, ex); mc = None
        if mc and last < mc[0] <= exp:           # bare en ferdig handelsdag nyere enn siste bar
            df = frames[t]
            ts = pd.Timestamp(mc[0])
            if getattr(df.index, "tz", None) is not None:
                ts = ts.tz_localize(df.index.tz)
            row = pd.DataFrame({c: [mc[1] if c in ("Close", "Open", "High", "Low") else np.nan] for c in df.columns}, index=[ts])
            frames[t] = pd.concat([df, row]).sort_index()
            info["meta"].append(t)
    for t, (last, exp) in lagging({t: frames[t] for t in lag}, now).items():
        info["still"][t] = str(last)
    log.info("freshness: hentet på nytt %s, fra metadata %s, fortsatt bak %s", info["refetched"], info["meta"], info["still"])
    return info


def summary(info: dict) -> str:
    if not info or not info.get("lagging"):
        return ""
    return (f"; ferskhet: {info['lagging']} bak forventet dag, {len(info['refetched'])} hentet på nytt, "
            f"{len(info['meta'])} fra Yahoo-metadata, {len(info['still'])} fortsatt bak")
