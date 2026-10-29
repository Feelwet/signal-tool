"""Prices & volumes via yfinance (free, unofficial Yahoo Finance endpoints; no key)."""
from __future__ import annotations
from .. import http as _http
import logging
import numpy as np
import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def _split_short(d, tickers: list[str]) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """(>30 sessions, 1-30 sessions). Short series = new listings (e.g. OUTLT.OL, listed 24.09.2026)."""
    out, short = {}, {}
    for t in tickers:
        try:
            df = d[t].dropna(subset=["Close"])
        except KeyError:
            continue
        if len(df) > 30:
            out[t] = df
        elif len(df):
            short[t] = df
    return out, short


LAST_FRESH: dict = {}


def download(tickers: list[str], period="2y", short: dict | None = None) -> dict[str, pd.DataFrame]:
    """Series with > 30 sessions. Pass a dict as `short` to also receive the 1-30-session series (not cleaned, no stats)."""
    d = _http.yf_download(tickers, period=period, progress=False, auto_adjust=True, group_by="ticker", threads=True)
    out, sh = _split_short(d, tickers)
    try:   # AnalBot 28.10: morgenkjøringen manglet forrige Oslo-handelsdag -> hent etternølere på nytt (freshness.py)
        from .. import freshness
        both = {**out, **sh}
        LAST_FRESH.clear(); LAST_FRESH.update(freshness.repair_lagging(both))
        out = {t: both[t] for t in out}
        sh = {t: both[t] for t in sh}
    except Exception as ex:
        log.warning("freshness repair failed: %s", ex)
    if short is not None:
        short.update(sh)
    from ..data_quality import clean_universe   # repair spike-and-revert bars before any stats (data_quality.py)
    out, _ = clean_universe(out, "Kurser (tema- og kandidataksjer)")
    return out


def short_stats(df: pd.DataFrame) -> dict:
    """Only the last close and its date for a too-short history: the forward log gets an entry price; every anomaly/rule
    input stays NaN, so the category logic sees exactly what it saw before (missing data)."""
    c = df["Close"]
    nan = np.nan
    return {"last_date": str(c.index[-1].date()), "close": float(c.iloc[-1]), "ret_1d": nan, "ret_5d": nan, "ret_20d": nan,
            "ret5_z": nan, "vol5_z": nan, "vol1_z": nan, "vol_ratio_5d": nan, "sma50": nan, "maxdd20": nan, "adv20": nan,
            "vol_1d": _vol1(df)}


def _vol1(df: pd.DataFrame) -> float:
    """Rått volum for siste bar (0 = ingen handel). NaN når volumet mangler (f.eks. sluttkurs fra chart-metadata)."""
    try:
        v = df["Volume"].iloc[-1]
        return float(v) if v == v else np.nan
    except Exception:
        return np.nan


def ticker_stats(df: pd.DataFrame) -> dict:
    """Return/volume anomaly stats for one ticker, vs its own history."""
    c, v = df["Close"], df["Volume"].replace(0, np.nan)
    r1 = c.pct_change()
    r5 = c.pct_change(5)
    out = {"last_date": str(c.index[-1].date()), "close": float(c.iloc[-1]),
           "ret_1d": float(r1.iloc[-1]), "ret_5d": float(r5.iloc[-1]), "ret_20d": float(c.pct_change(20).iloc[-1])}
    hist5 = r5.iloc[-260:-5].dropna()
    out["ret5_z"] = float((r5.iloc[-1] - hist5.mean()) / hist5.std()) if len(hist5) > 50 and hist5.std() > 0 else np.nan
    if v.notna().sum() > 70:
        lv = np.log(v.dropna())
        base = lv.iloc[-66:-6]  # 60 sessions ending a week ago
        recent = lv.iloc[-5:].mean()
        out["vol5_z"] = float((recent - base.mean()) / base.std()) if base.std() > 0 else np.nan
        out["vol1_z"] = float((lv.iloc[-1] - base.mean()) / base.std()) if base.std() > 0 else np.nan
        out["vol_ratio_5d"] = float(np.exp(recent - base.mean()))
    else:
        out["vol5_z"] = out["vol1_z"] = out["vol_ratio_5d"] = np.nan
    # inputs for the rule-based categories (signaltool/categories.py)
    out["sma50"] = float(c.iloc[-50:].mean()) if len(c) >= 50 else np.nan
    last20 = c.iloc[-20:]
    out["maxdd20"] = float((last20 / last20.cummax() - 1).min()) if len(last20) >= 5 else np.nan  # worst peak-to-trough, 20 sessions
    dv = (c * df["Volume"]).iloc[-20:]
    out["adv20"] = float(dv.median()) if dv.notna().sum() >= 10 else np.nan  # median daily turnover, local currency
    out["vol_1d"] = _vol1(df)   # plan 29.10: «Ingen handel» bare når dagens volum er 0 (rowfresh.py)
    return out


def collect(tickers: list[str]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], str]:
    try:
        short: dict = {}
        data = download(tickers, short=short)
    except Exception as e:
        return pd.DataFrame(), {}, f"FAILED: {e}"
    stats = {t: ticker_stats(df) for t, df in data.items()}
    stats.update({t: short_stats(df) for t, df in short.items() if t not in stats})
    missing = sorted(set(tickers) - set(data) - set(short))
    from ..freshness import summary
    msg = f"ok ({len(data)}/{len(tickers)} tickers)" + (f"; missing {missing}" if missing else "") + summary(LAST_FRESH)
    return pd.DataFrame(stats).T, data, msg


def earnings_calendar(tickers: list[str], days_ahead=21) -> tuple[list[dict], str]:
    """Upcoming earnings dates from Yahoo (yfinance Ticker.calendar). Skips ETFs/futures/FX."""
    import datetime as dt
    out, fails = [], 0
    today = dt.date.today(); horizon = today + dt.timedelta(days=days_ahead)
    for t in tickers:
        if "=" in t or t.startswith("^"):
            continue
        try:
            cal = yf.Ticker(t).calendar or {}
            ds = cal.get("Earnings Date") or []
            for d in ds[:1]:
                if isinstance(d, dt.datetime):
                    d = d.date()
                if today <= d <= horizon:
                    out.append({"date": d.isoformat(), "ticker": t, "eps_est": cal.get("Earnings Average")})
        except Exception:
            fails += 1
    return sorted(out, key=lambda x: x["date"]), f"ok ({len(out)} reports within {days_ahead}d; {fails} lookups failed)"
