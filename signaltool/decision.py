"""Decision support per candidate ticker: what is already priced in, risk, invalidation levels, event risk, valuation.

All numbers come from free Yahoo Finance endpoints via yfinance (unofficial; valuation/analyst fields can be stale or
missing - shown as '–' then). Nothing here is a recommendation; it is context for a human decision.
"""
from __future__ import annotations
from . import http as _http
import logging, math, os, random, time
from datetime import date
import numpy as np
import pandas as pd
import yfinance as yf
from .categories import benchmark_for, is_equity, BENCH_US
from .config import CACHE
from .themes import THEME_BY_KEY

log = logging.getLogger(__name__)
SPDR = {"Information Technology": "XLK", "Health Care": "XLV", "Financials": "XLF", "Consumer Discretionary": "XLY",
        "Communication Services": "XLC", "Industrials": "XLI", "Consumer Staples": "XLP", "Energy": "XLE",
        "Utilities": "XLU", "Real Estate": "XLRE", "Materials": "XLB"}
YF_SECTOR = {"Technology": "XLK", "Healthcare": "XLV", "Financial Services": "XLF", "Consumer Cyclical": "XLY",
             "Communication Services": "XLC", "Industrials": "XLI", "Consumer Defensive": "XLP", "Energy": "XLE",
             "Utilities": "XLU", "Real Estate": "XLRE", "Basic Materials": "XLB"}
INFO_KEYS = ["trailingPE", "forwardPE", "enterpriseToEbitda", "priceToBook", "marketCap", "dividendYield", "recommendationKey",
             "numberOfAnalystOpinions", "targetMeanPrice", "currency", "sector", "shortPercentOfFloat", "beta", "quoteType",
             # Nøkkeltall-seksjonen (nokkeltall.py): faktiske tall siste 12 mnd fra samme Yahoo-kall
             "trailingEps", "totalRevenue", "financialCurrency", "bookValue", "sharesOutstanding",
             "trailingAnnualDividendRate", "trailingAnnualDividendYield", "priceToSalesTrailing12Months",
             "operatingMargins", "isEarningsDateEstimate"]
PEAD_SURPRISE = 15.0   # EPS surprise % ~ 80th percentile of S&P 500 reports 2016-2026 (backtest/pead.py)
PEAD_REACTION = 0.04   # reaction-day return minus SPY (dividend-adjusted) ~ 80th percentile
PEAD_MAX_AGE = 45      # calendar days the signal stays active (same limit in collectors/pead_scan.py)
PEAD_BENCH = "SPY"     # same reference in the live signal, the scanner and the backtest
# fallback only (when the ranked Oslo universe in oslo_flags.py is unavailable): median 20th percentile of 12-1 momentum 2018-2026
OSLO_WEAK_MOM = -0.106
VOL_MEDIAN_CACHE = CACHE / "universe" / "sp500_vol_median.json"


def sp500_median_vol(fetch: bool = True, max_age_days: int = 7) -> pd.Series | None:
    """Daily median of 1-year daily-return volatility (std of daily returns, 252 sessions) across current S&P 500 members -
    the PEAD-S threshold (strategy-research/RAPPORT_3: it varies 1.3-3.6 %/day historically, so it is computed, not hard-coded).
    Sources in order: cached series (<= 7 days old), the backtest price cache (if fresh), else one 14-month batch download."""
    import json
    from .backtest import universe
    today = pd.Timestamp(date.today())
    if VOL_MEDIAN_CACHE.exists():
        try:
            j = json.loads(VOL_MEDIAN_CACHE.read_text())
            s = pd.Series(j["median"], index=pd.to_datetime(j["dates"]))
            if (today - s.index[-1]).days <= max_age_days:
                return s
        except Exception:
            pass
    C = None
    p = universe.DIR / "us.pkl"
    if p.exists():
        try:
            d = pd.read_pickle(p)
            last = max(v.index[-1] for v in d.values())
            if (today - last).days <= max_age_days:
                etf = set(universe.SECTOR_ETF.values()) | {"SPY"}
                C = pd.DataFrame({t: v["Close"].iloc[-400:] for t, v in d.items() if t not in etf}).sort_index()
        except Exception as ex:
            log.info("us.pkl: %s", ex)
    if C is None and fetch:
        try:
            tick = universe.sp500_members()["Symbol"].astype(str).tolist()
            raw = _http.yf_download(tick, period="14mo", progress=False, auto_adjust=True, threads=True)["Close"]
            C = raw.sort_index()
        except Exception as ex:
            log.warning("S&P 500 vol median download failed: %s", ex)
    if C is None or C.empty:
        return None
    vol = C.pct_change(fill_method=None).rolling(252, min_periods=200).std()
    med = vol.median(axis=1).dropna().iloc[-120:]
    if med.empty:
        return None
    VOL_MEDIAN_CACHE.write_text(json.dumps({"dates": [str(x.date()) for x in med.index], "median": [float(x) for x in med]}))
    return med


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
    out["sma20"] = _f(c.iloc[-20:].mean(), 3) if len(c) >= 20 else None
    out["hi20"] = _f(c.iloc[-21:-1].max(), 3) if len(c) >= 21 else None  # highest close of the 20 sessions before today
    out["stop_atr"] = _f(c.iloc[-1] - 2 * atr, 3) if atr == atr else None
    out["mom12_1"] = _f(c.iloc[-22] / c.iloc[-253] - 1) if len(c) > 253 else None
    out["close"] = _f(c.iloc[-1], 3)
    return out


def _q_run(q, rows):
    """Nyeste sammenhengende kvartalsrekke (eldst først) uten hull: ingen NaN og 60–120 dager mellom kvartalene."""
    row = next((r for r in rows if r in q.index), None)
    if row is None:
        return []
    v = q.loc[row].sort_index(ascending=False)
    out, prev = [], None
    for d, x in v.items():
        if x != x:
            break
        if prev is not None and not 60 <= (prev - d).days <= 120:
            break
        out.append([str(d.date()), float(x)])
        prev = d
    return out[::-1]


def quarterly(tk: yf.Ticker) -> dict:
    """EBIT siste 12 mnd (sum av fire siste kvartaler, aldri avledet) + kvartalsrekker for omsetning og EPS (sparklines)."""
    try:
        q = tk.quarterly_income_stmt
    except Exception:
        q = None
    if q is None or q.empty:
        return {"ebit_ttm": None, "rev_q": [], "eps_q": []}
    return {"ebit_ttm": ebit_ttm(tk, q), "rev_q": _q_run(q, ("Total Revenue", "Operating Revenue")),
            "eps_q": _q_run(q, ("Diluted EPS", "Basic EPS"))}


def ebit_ttm(tk: yf.Ticker, q=None):
    """EBIT siste 12 mnd = sum av Yahoos fire siste kvartaler (rad EBIT, ellers Operating Income). Mangler ett kvartal: None."""
    try:
        q = tk.quarterly_income_stmt if q is None else q
        if q is None or q.empty:
            return None
        row = next((r for r in ("EBIT", "Operating Income") if r in q.index), None)
        if row is None:
            return None
        v = q.loc[row].sort_index(ascending=False).iloc[:4]
        if len(v) < 4 or v.isna().any():
            return None
        return float(v.sum())
    except Exception:
        return None


def _next_earnings(tk: yf.Ticker):
    try:
        cal = tk.calendar or {}
        ds = cal.get("Earnings Date") or []
        ds = [d.date() if hasattr(d, "date") and not isinstance(d, date) else d for d in ds]
        fut = sorted(d for d in ds if d >= date.today())
        return fut[0].isoformat() if fut else None
    except Exception:
        return None


def pead_info(tk: yf.Ticker, close: pd.Series, bench: pd.Series | None, vol_median: pd.Series | None = None) -> dict:
    """Latest reported quarter: EPS surprise (Yahoo) + reaction-day excess return vs SPY; flags the PEAD condition (<= 45 days)
    and the experimental PEAD-S variant (1-year daily volatility the day before the reaction day above the S&P 500 median)."""
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
    pead = bool(sur >= PEAD_SURPRISE and ear >= PEAD_REACTION and age <= PEAD_MAX_AGE)
    out = {"last_earnings": str(idx[p].date()), "eps_surprise": _f(sur, 1), "earn_reaction": _f(ear), "pead": pead, "pead_age_days": age}
    out.update(pead_s_check(close, p, vol_median, pead))
    return out


def pead_s_check(close: pd.Series, p: int, vol_median: pd.Series | None, pead: bool) -> dict:
    """PEAD-S: PEAD AND the stock's 1-year daily volatility (known the day before the reaction day) above the S&P 500 median."""
    if p < 1:
        return {}
    v = close.pct_change(fill_method=None).rolling(252, min_periods=200).std()
    sv = v.iloc[p - 1]
    out = {"vol1y_d": _f(sv, 5)}
    if vol_median is not None and len(vol_median) and sv == sv:
        m = vol_median[vol_median.index <= close.index[p - 1]]
        med = float(m.iloc[-1]) if len(m) else float(vol_median.iloc[0])
        out.update({"vol1y_median_d": _f(med, 5), "pead_s": bool(pead and sv > med)})
    return out


def revisions(tk: yf.Ticker) -> dict:
    """Analyst EPS-estimate trend for the current fiscal year (Yahoo, free; current snapshot only - no history to backtest)."""
    out = {}
    try:
        tr = tk.eps_trend
        if tr is not None and "0y" in tr.index:
            r = tr.loc["0y"]
            for lab, col in (("rev30", "30daysAgo"), ("rev90", "90daysAgo")):
                if r.get(col) and r.get("current") is not None and abs(float(r[col])) > 1e-9:
                    out[f"eps_{lab}"] = _f(float(r["current"]) / abs(float(r[col])) - (1 if float(r[col]) > 0 else -1))
    except Exception:
        pass
    try:
        rv = tk.eps_revisions
        if rv is not None and "0y" in rv.index:
            out["eps_up30"] = _f(rv.loc["0y"].get("upLast30days"), 0)
            out["eps_down30"] = _f(rv.loc["0y"].get("downLast30days"), 0)
    except Exception:
        pass
    return out


_RUN = {"fail": False}     # kildefeil gjelder hele kjøringen (alle apply-kall i samme prosess)
RATE_S = float(os.environ.get("YF_RATE_S", "1.0"))                 # ≤ 1 forespørsel/s mot Yahoo (+ jitter)
RETRY_BASE_S = float(os.environ.get("YF_RETRY_BASE_S", "60"))      # 60, 120, 240, 480, 960 s ...
RETRY_WINDOW_S = float(os.environ.get("YF_RETRY_WINDOW_MIN", "45")) * 60
_LAST = [0.0]


def _pace() -> None:
    gap = RATE_S * random.uniform(1.0, 1.5) - (time.monotonic() - _LAST[0])
    if gap > 0:
        time.sleep(gap)
    _LAST[0] = time.monotonic()


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
    def _one(t):
        tk = yf.Ticker(t)
        inf = tk.info or {}
        if not any(inf.get(k) is not None for k in ("sector", "marketCap", "trailingPE", "quoteType")):
            raise RuntimeError("tom info")
        _pace(); infos[t] = {k: inf.get(k) for k in INFO_KEYS}
        infos[t]["info_date"] = date.today().isoformat()
        infos[t].update(quarterly(tk)); _pace()
        infos[t]["next_earnings"] = _next_earnings(tk); _pace()
        infos[t].update(revisions(tk))
        if t not in sector_of and YF_SECTOR.get(inf.get("sector")) and not t.endswith(".OL"):
            sector_of[t] = YF_SECTOR[inf["sector"]]
    todo = [t for t in tickers[:max_info] if is_equity(t)]
    wait = RETRY_BASE_S
    while True:
        failed = []
        for t in todo:
            _pace()
            try:
                _one(t)
            except Exception as ex:
                infos.pop(t, None)
                failed.append(t)
                log.info("info %s: %s", t, ex)
        # AnalBot 25.10: eksponentiell backoff innen et vindu (standard 45 min per kjøring) før > 50 %-vakten slår til
        left = _RUN.setdefault("deadline", time.monotonic() + RETRY_WINDOW_S) - time.monotonic()
        if not failed or _RUN["fail"] or left <= 0:
            break
        nap = min(wait, left) * random.uniform(0.85, 1.15)
        log.warning("Yahoo-fundamentaldata: %d/%d feilet, nytt forsøk om %.0f s (%.0f s igjen av vinduet)", len(failed), len(todo), nap, left)
        time.sleep(max(0.0, nap))
        todo, wait = failed, wait * 2
    refs = sorted(set(sector_of.values()) | {BENCH_US, "OSEBX.OL"})
    vol_med = None
    try:
        vol_med = sp500_median_vol()
    except Exception as ex:
        log.info("vol median: %s", ex)
    d = _http.yf_download(sorted(set(tickers) | set(refs)), period="2y", progress=False, auto_adjust=True, group_by="ticker", threads=True)
    out = {}
    retry: dict[str, pd.Series] = {}
    def ser(t):
        try:
            s = d[t]["Close"].dropna()
            if len(s):
                return s
        except Exception:
            pass
        if t in refs:  # Yahoo mister av og til enkeltserier i store nedlastinger – prøv igjen alene
            if t not in retry:
                try:
                    r = _http.yf_download(t, period="2y", progress=False, auto_adjust=True)["Close"]
                    retry[t] = (r.iloc[:, 0] if isinstance(r, pd.DataFrame) else r).dropna()
                except Exception:
                    retry[t] = pd.Series(dtype=float)
            return retry[t] if len(retry[t]) else None
        return None
    from .data_quality import clean_frame, note as dq_note
    for t in tickers:
        try:
            df = d[t][["Close", "High", "Low"]].dropna(subset=["Close"])
        except Exception:
            continue
        df, dqi = clean_frame(df)          # spike-and-revert repair (data_quality.py)
        dq_note("Beslutningsdata (kurshistorikk per ticker)", {t: dqi["spikes"]} if dqi["spikes"] else {}, {}, [t])
        if len(df) < 60:
            continue
        m = price_metrics(df, ser(benchmark_for(t)), ser(sector_of[t]) if t in sector_of else None)
        m["sector_etf"] = sector_of.get(t)
        inf = infos.get(t, {})
        txt_keys = ("recommendationKey", "currency", "sector", "next_earnings", "quoteType", "financialCurrency", "info_date")
        # tekst, ja/nei og kvartalsrekker beholdes som de er; bare tall går gjennom _f
        m.update({k: (v if k in txt_keys or isinstance(v, (bool, list)) else _f(v)) for k, v in inf.items()})
        if inf.get("targetMeanPrice") and m.get("close"):
            m["target_upside"] = _f(inf["targetMeanPrice"] / m["close"] - 1)
        if m.get("next_earnings"):
            m["days_to_earnings"] = (date.fromisoformat(m["next_earnings"]) - date.today()).days
        if is_equity(t) and not t.endswith(".OL") and "." not in t:
            try:
                m.update(pead_info(yf.Ticker(t), df["Close"], ser(PEAD_BENCH), vol_med))
            except Exception as ex:
                log.info("pead %s: %s", t, ex)
        m["weak_mom_oslo"] = bool(t.endswith(".OL") and m.get("mom12_1") is not None and m["mom12_1"] <= OSLO_WEAK_MOM)
        out[t] = m
    return out


FUND_KEYS = tuple(INFO_KEYS) + ("next_earnings", "info_date")
FALLBACK_MAX_TD = 5        # AnalBot 25.10: gjenbruk høyst 5 handelsdager gammel dekning/fundamentaldata


def _has_fund(m) -> bool:
    return bool(m) and any(m.get(k) is not None for k in ("sector", "marketCap", "trailingPE", "numberOfAnalystOpinions"))


def fallback(snap: dict, dec: dict, today: str | None = None, path=None) -> dict:
    """Yahoo-vakt (AnalBot 25.10): feiler fundamentaldata for > 50 % av aksjetickerne i kjøringen, er det kildefeil for hele
    kjøringen. Da gjenbrukes siste vellykkede fundamentaldata per ticker (høyst 5 handelsdager gamle) og e["fund_fallback"]
    = dato; eldre -> vanlig 4/7-regel. Uten kildefeil lagres dagens vellykkede som siste gode (data/cache, følger actions/cache)."""
    import json
    today = today or date.today().isoformat()
    path = path or (CACHE / "fund_lastgood.json")
    try:
        good = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        good = {}
    eq = [e for e in snap.get("tickers", []) if is_equity(e["ticker"])]
    failed = [e for e in eq if not _has_fund(dec.get(e["ticker"]))]
    if eq and len(failed) / len(eq) > 0.5:
        _RUN["fail"] = True
    used = []
    if _RUN["fail"]:
        for e in failed:
            g = good.get(e["ticker"])
            if not g or int(np.busday_count(g["date"], today)) > FALLBACK_MAX_TD:
                continue
            m = dec.setdefault(e["ticker"], dict(e.get("decision") or {}))
            for k, v in g["fund"].items():
                if m.get(k) is None:
                    m[k] = v
            m["fund_fallback"] = g["date"]
            used.append(e["ticker"])
    else:
        for e in eq:
            m = dec.get(e["ticker"])
            if _has_fund(m):
                good[e["ticker"]] = {"date": today, "fund": {k: m.get(k) for k in FUND_KEYS if m.get(k) is not None}}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(good, ensure_ascii=False, default=str))
        except OSError as ex:
            log.warning("lastgood: %s", ex)
    return {"attempted": len(eq), "failed": len(failed), "source_fail": _RUN["fail"], "used": used}


def fb_date(e: dict):
    return (e.get("decision") or {}).get("fund_fallback")


def fb_text(e: dict) -> str:
    d = fb_date(e)
    return f"Fundamentaldata fra {d[8:10]}.{d[5:7]} (Yahoo feilet i dag)" if d else ""


def apply(snap: dict) -> dict:
    try:
        dec = compute(snap)
    except Exception as ex:
        log.warning("decision data failed: %s", ex)
        dec = {}
    try:
        snap.setdefault("_fund_fb", []).append(fallback(snap, dec))
    except Exception as ex:
        log.warning("yahoo fallback: %s", ex)
    for e in snap.get("tickers", []):
        if e["ticker"] in dec:
            e["decision"] = dec[e["ticker"]]
    return snap
