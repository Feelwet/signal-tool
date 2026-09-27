"""Decision support per candidate ticker: what is already priced in, risk, invalidation levels, event risk, valuation.

All numbers come from free Yahoo Finance endpoints via yfinance (unofficial; valuation/analyst fields can be stale or
missing - shown as '–' then). Nothing here is a recommendation; it is context for a human decision.
"""
from __future__ import annotations
import logging, math
from datetime import date
import numpy as np
import pandas as pd
import yfinance as yf
from .categories import benchmark_for, is_equity
from .themes import THEME_BY_KEY

log = logging.getLogger(__name__)
SPDR = {"Information Technology": "XLK", "Health Care": "XLV", "Financials": "XLF", "Consumer Discretionary": "XLY",
        "Communication Services": "XLC", "Industrials": "XLI", "Consumer Staples": "XLP", "Energy": "XLE",
        "Utilities": "XLU", "Real Estate": "XLRE", "Materials": "XLB"}
YF_SECTOR = {"Technology": "XLK", "Healthcare": "XLV", "Financial Services": "XLF", "Consumer Cyclical": "XLY",
             "Communication Services": "XLC", "Industrials": "XLI", "Consumer Defensive": "XLP", "Energy": "XLE",
             "Utilities": "XLU", "Real Estate": "XLRE", "Basic Materials": "XLB"}
INFO_KEYS = ["trailingPE", "forwardPE", "enterpriseToEbitda", "priceToBook", "marketCap", "dividendYield", "recommendationKey",
             "numberOfAnalystOpinions", "targetMeanPrice", "currency", "sector", "shortPercentOfFloat", "beta"]
PEAD_SURPRISE = 15.0   # EPS surprise % ~ 80th percentile of S&P 500 reports 2016-2026 (backtest/pead.py)
PEAD_REACTION = 0.04   # reaction-day return minus SPY ~ 80th percentile
PEAD_MAX_AGE = 45      # calendar days the signal stays active (drift measured over the following 60 trading days)
OSLO_WEAK_MOM = -0.106  # median 20th percentile of 12-1 month momentum among liquid Oslo stocks 2018-2026 (backtest/price_rules)


def _f(x, nd=4):
    try:
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else round(x, nd)
    except (TypeError, ValueError):
        return None


def price_metrics(df: pd.DataFrame, bench: pd.Series | None, sector: pd.Series | None) -> dict:
    c = df["Close"].dropna()
    h, l = df["High"].reindex(c.index), df["Low"].reindex(c.index)
    out = {}
    for n in (5, 20, 60):
        out[f"ret_{n}d"] = _f(c.iloc[-1] / c.iloc[-1 - n] - 1) if len(c) > n else None
        for lab, ref in (("bench", bench), ("sector", sector)):
            if ref is not None and len(ref.dropna()) > n:
                r = ref.dropna()
                out[f"rel_{lab}_{n}d"] = _f(out[f"ret_{n}d"] - (r.iloc[-1] / r.iloc[-1 - n] - 1)) if out[f"ret_{n}d"] is not None else None
    y = c.iloc[-252:]
    out["hi52"], out["lo52"] = _f(y.max(), 2), _f(y.min(), 2)
    out["pct_from_hi52"] = _f(c.iloc[-1] / y.max() - 1)
    lr = np.log(c).diff().dropna()
    out["vol60"] = _f(lr.iloc[-60:].std() * math.sqrt(252))
    out["maxdd1y"] = _f((y / y.cummax() - 1).min())
    if bench is not None:
        b = np.log(bench.dropna()).diff().dropna()
        j = pd.concat([lr, b], axis=1, join="inner").iloc[-252:]
        if len(j) > 100 and j.iloc[:, 1].var() > 0:
            out["beta1y"] = _f(j.cov().iloc[0, 1] / j.iloc[:, 1].var(), 2)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    out["atr14"] = _f(atr, 3)
    out["atr_pct"] = _f(atr / c.iloc[-1])
    sma50 = c.iloc[-50:].mean() if len(c) >= 50 else None
    out["sma50"] = _f(sma50, 3)
    out["stop_atr"] = _f(c.iloc[-1] - 2 * atr, 3) if atr == atr else None
    out["mom12_1"] = _f(c.iloc[-22] / c.iloc[-253] - 1) if len(c) > 253 else None
    out["close"] = _f(c.iloc[-1], 3)
    return out


def _next_earnings(tk: yf.Ticker):
    try:
        cal = tk.calendar or {}
        ds = cal.get("Earnings Date") or []
        ds = [d.date() if hasattr(d, "date") and not isinstance(d, date) else d for d in ds]
        fut = sorted(d for d in ds if d >= date.today())
        return fut[0].isoformat() if fut else None
    except Exception:
        return None


def pead_info(tk: yf.Ticker, close: pd.Series, bench: pd.Series | None) -> dict:
    """Latest reported quarter: EPS surprise (Yahoo) + reaction-day excess return; flags the PEAD condition."""
    try:
        d = tk.get_earnings_dates(limit=8)
    except Exception:
        return {}
    if d is None or d.empty or bench is None:
        return {}
    d = d.dropna(subset=["Surprise(%)"])
    if d.empty:
        return {}
    ts = d.index.max()
    local = ts.tz_convert("America/New_York") if ts.tzinfo else ts
    day = pd.Timestamp(local.date())
    idx = close.index
    p = idx.searchsorted(day)
    if local.hour + local.minute / 60 >= 9.5 and p < len(idx) and idx[p] == day:
        p += 1
    if p < 1 or p >= len(idx):
        return {"last_earnings": str(day.date()), "eps_surprise": _f(d.loc[ts, "Surprise(%)"], 1)}
    b = bench.reindex(idx).ffill()
    ear = (close.iloc[p] / close.iloc[p - 1] - 1) - (b.iloc[p] / b.iloc[p - 1] - 1)
    sur = float(d.loc[ts, "Surprise(%)"])
    age = (date.today() - idx[p].date()).days
    return {"last_earnings": str(idx[p].date()), "eps_surprise": _f(sur, 1), "earn_reaction": _f(ear),
            "pead": bool(sur >= PEAD_SURPRISE and ear >= PEAD_REACTION and age <= PEAD_MAX_AGE), "pead_age_days": age}


def compute(snap: dict, max_info=80) -> dict:
    tickers = [e["ticker"] for e in snap.get("tickers", [])]
    if not tickers:
        return {}
    sector_of = {}
    for e in snap["tickers"]:
        for k in e.get("themes", []):
            th = THEME_BY_KEY.get(k)
            if th and th.sector_etf and th.sector_etf != "SPY":
                sector_of.setdefault(e["ticker"], th.sector_etf)
    infos = {}
    for t in tickers[:max_info]:
        if not is_equity(t):
            continue
        try:
            tk = yf.Ticker(t)
            inf = tk.info or {}
            infos[t] = {k: inf.get(k) for k in INFO_KEYS}
            infos[t]["next_earnings"] = _next_earnings(tk)
            if t not in sector_of and YF_SECTOR.get(inf.get("sector")) and not t.endswith(".OL"):
                sector_of[t] = YF_SECTOR[inf["sector"]]
        except Exception as ex:
            log.info("info %s: %s", t, ex)
    refs = sorted(set(sector_of.values()) | {"^GSPC", "OSEBX.OL"})
    d = yf.download(sorted(set(tickers) | set(refs)), period="2y", progress=False, auto_adjust=True, group_by="ticker", threads=True)
    out = {}
    def ser(t):
        try:
            s = d[t]["Close"].dropna()
            return s if len(s) else None
        except Exception:
            return None
    for t in tickers:
        try:
            df = d[t][["Close", "High", "Low"]].dropna(subset=["Close"])
        except Exception:
            continue
        if len(df) < 60:
            continue
        m = price_metrics(df, ser(benchmark_for(t)), ser(sector_of[t]) if t in sector_of else None)
        m["sector_etf"] = sector_of.get(t)
        inf = infos.get(t, {})
        txt_keys = ("recommendationKey", "currency", "sector", "next_earnings")
        m.update({k: (v if k in txt_keys else _f(v)) for k, v in inf.items()})
        if inf.get("targetMeanPrice") and m.get("close"):
            m["target_upside"] = _f(inf["targetMeanPrice"] / m["close"] - 1)
        if m.get("next_earnings"):
            m["days_to_earnings"] = (date.fromisoformat(m["next_earnings"]) - date.today()).days
        if is_equity(t) and not t.endswith(".OL") and "." not in t:
            try:
                m.update(pead_info(yf.Ticker(t), df["Close"], ser("^GSPC")))
            except Exception as ex:
                log.info("pead %s: %s", t, ex)
        m["weak_mom_oslo"] = bool(t.endswith(".OL") and m.get("mom12_1") is not None and m["mom12_1"] <= OSLO_WEAK_MOM)
        out[t] = m
    return out


def apply(snap: dict) -> dict:
    try:
        dec = compute(snap)
    except Exception as ex:
        log.warning("decision data failed: %s", ex)
        dec = {}
    for e in snap.get("tickers", []):
        if e["ticker"] in dec:
            e["decision"] = dec[e["ticker"]]
    return snap
