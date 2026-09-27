"""Rule-based stock categories: «Kjøp» (kandidat), «Hold», «Watchlist».

IMPORTANT: our own backtests (reports/backtest.md) found NO proven edge in insider clusters or GDELT spikes.
These categories are therefore deliberately conservative, fully transparent rules - NOT a forecast, NOT personal
financial advice, and NOT proven to beat the market. A forward log (data/history/categories.csv) records every
day's categories and prices so the real hit rate can be measured over time ("Treffsikkerhet").

Rules (all thresholds in RULES):
  Kjøp-kandidat  = ALL of
      (1) >= 2 INDEPENDENT signal types from higher-reliability sources:
            gov_contract    US DoD daily contract announcement or USAspending award (official; DoD+USAspending = one type)
            insider_cluster SEC Form 4 open-market purchases by >= 2 insiders (>= $50k) incl. officers/directors (not only 10 % funds)
            ose_contract    Oslo Børs Newsweb contract/order announcement (exchange filing)
            theme_market    ticker is a named winner of a theme with score >= 1.0 AND a market-based theme component
                            (physical oil spreads/futures curves) with z >= 1.0
         (volume, price moves, Reddit, congress trades and Newsweb insider notices of unknown direction do NOT count)
      (2) at least one of those signals is fresh (<= 7 calendar days old)
      (3) price confirmation: close > 50-day average AND 20-day return > benchmark 20-day return
          (benchmark: OSEBX for .OL, S&P 500 otherwise)
      (4) not stretched: 5d return < +10 %, 20d return < +25 %, close < 25 % above the 50-day average
      (5) no red flags: sharply rising short interest (Oslo: +0.3 pp in 7d or +0.75 pp in 30d), crash (>= 20 %
          peak-to-trough within 20 sessions), illiquid (median turnover < ~USD 1M/day) or penny stock (< ~USD 1),
          or volume/price-only signals
  Hold           = >= 1 higher-reliability signal type, price confirmation holds, no red flags, but the entry is late:
                   stretched (rule 4 fails) OR no signal fresher than 7 days OR it was a Kjøp-kandidat within the last
                   30 days without a new trigger ("if you own it, the signals still support it; don't chase").
                   A single fresh, un-stretched signal is NOT Hold but Watchlist (single source = unconfirmed).
  Watchlist      = everything else with attention/anomalies (single source, volume-only, theme-only, falling price,
                   red flags, missing price data)
"""
from __future__ import annotations
import logging, re
from datetime import date, datetime, timedelta
import numpy as np
import pandas as pd
from .config import HISTORY

log = logging.getLogger(__name__)
LOG_PATH = HISTORY / "categories.csv"
LOG_COLS = ["date", "ticker", "category", "price", "price_date", "benchmark", "score", "n_types"]

RULES = dict(min_types=2, fresh_days=7, stretch_5d=0.10, stretch_20d=0.25, stretch_sma=0.25, crash=-0.20,
             min_adv_usd=1_000_000, min_price_usd=1.0, short_7d=0.3, short_30d=0.75, theme_min=1.0,
             theme_market_z=1.0, hold_memory_days=30, min_track_n=10)
HORIZONS = (5, 20, 60)
# market-based theme confirmation that counts as an independent signal: physical oil spreads/futures curves only
# (prediction-market moves were considered but are too loosely linked to single stocks, e.g. elections -> SPY)
MARKET_COMPONENTS = ("physical_oil",)
BENCH_OSE, BENCH_US = "OSEBX.OL", "^GSPC"
BENCH_NAME = {BENCH_OSE: "OSEBX", BENCH_US: "S&P 500"}
# rough FX to USD for liquidity / penny checks (only thresholds; precision is not important)
FX_USD = {".OL": 0.095, ".L": 0.0127, ".DE": 1.1, ".PA": 1.1, ".AS": 1.1, ".MI": 1.1, ".HE": 1.1, ".ST": 0.095,
          ".CO": 0.147, ".TO": 0.73, ".AX": 0.65}
TYPE_NO = {"gov_contract": "offentlig kontrakt (DoD/USAspending)", "insider_cluster": "innsidekjøp-klynge (ledelse/styre)",
           "ose_contract": "kontraktsmelding (Newsweb)", "theme_market": "tema med markedsbekreftelse",
           "pead": "sterk kvartalsrapport (overraskelse + kursreaksjon)"}
CAT_NO = {"kjop": "Kjøp", "hold": "Hold", "watch": "Watchlist"}
DISCLAIMER_NO = ("Kategoriene er regelbaserte og mekaniske – ikke personlig finansiell rådgivning, og ikke bevist å slå markedet "
                 "(våre egne tester fant ingen dokumentert meravkastning).")
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def benchmark_for(ticker: str) -> str:
    return BENCH_OSE if ticker.endswith(".OL") else BENCH_US


def is_equity(ticker: str) -> bool:
    return not ("=" in ticker or ticker.startswith("^"))


def fx_usd(ticker: str) -> float:
    for suf, f in FX_USD.items():
        if ticker.endswith(suf):
            return f
    return 1.0


def _d(x) -> date | None:
    """Parse the various date formats found in the snapshot."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    s = str(x)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),\s+(\d{4})", s)  # "Contracts for Sept. 23, 2026"
    if m and m.group(1).lower() in _MONTHS:
        return date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
    return None


def build_context(snap: dict, bench_ret20: dict | None = None, prev_kjop: dict | None = None) -> dict:
    today = _d(snap.get("date")) or date.today()
    ctx = {"today": today, "bench_ret20": bench_ret20 or {}, "prev_kjop": prev_kjop or {},
           "themes": {t["key"]: t for t in snap.get("themes", [])}, "shorts": {}, "insider": {}, "dates": {}}
    for r in snap.get("shorts", []) or []:
        if r.get("ticker"):
            ctx["shorts"][r["ticker"]] = r
    for r in snap.get("insider_clusters", []) or []:
        if r.get("ticker"):
            ctx["insider"][str(r["ticker"]).upper()] = r
    dates = ctx["dates"]
    for r in snap.get("dod_awards", []) or []:
        if r.get("ticker"):
            dates.setdefault(("gov_contract", r["ticker"]), []).append(_d(r.get("day")))
    for r in snap.get("awards", []) or []:
        if r.get("ticker"):
            dates.setdefault(("gov_contract", r["ticker"]), []).append(_d(r.get("Start Date")))
    for r in snap.get("newsweb_contracts", []) or []:
        dates.setdefault(("ose_contract", f"{r.get('issuer')}.OL"), []).append(_d(r.get("published")))
    for t, r in ctx["insider"].items():
        dates.setdefault(("insider_cluster", t), []).append(_d(r.get("last_date")))
    return ctx


def _officer_director(roles: str) -> bool:
    return bool(re.search(r"director|officer|chief|ceo|cfo|coo|president|vp\b|vice", roles or "", re.I))


def signal_types(e: dict, ctx: dict) -> dict:
    """Higher-reliability, independent signal types present for this ticker -> {type: {"date", "detail"}}."""
    t, pts, out = e["ticker"], e.get("points", {}), {}

    def newest(kind):
        ds = [d for d in ctx["dates"].get((kind, t), []) + [_d((e.get("signal_dates") or {}).get(kind))] if d]
        return max(ds) if ds else None
    if pts.get("dod_contract", 0) > 0 or pts.get("federal_award", 0) > 0:
        out["gov_contract"] = {"date": newest("gov_contract"), "detail": "DoD/USAspending"}
    if pts.get("insider_cluster", 0) > 0:
        r = ctx["insider"].get(t.upper(), {})
        roles = r.get("roles") or " ".join(x.get("text", "") for x in e.get("evidence", []) if "Form 4" in x.get("text", ""))
        if _officer_director(roles):
            out["insider_cluster"] = {"date": newest("insider_cluster"), "detail": roles[:80]}
    dec = e.get("decision") or {}
    if dec.get("pead"):
        # validated out-of-sample 2016-2026 (reports/backtest_natt.md): top EPS surprise + top reaction -> +1.9 pp / 60 d vs other reports
        out["pead"] = {"date": _d(dec.get("last_earnings")), "detail": f"EPS-overraskelse {dec.get('eps_surprise'):+.0f} %, reaksjon {dec.get('earn_reaction', 0)*100:+.1f} % vs S&P 500"}
    if pts.get("ose_contracts", 0) > 0:
        out["ose_contract"] = {"date": newest("ose_contract"), "detail": "Newsweb"}
    for k in e.get("themes", []):
        th = ctx["themes"].get(k)
        if not th or (th.get("score") or 0) < RULES["theme_min"]:
            continue
        comps = th.get("components", {})
        mk = [c for c in MARKET_COMPONENTS if (comps.get(c, {}).get("score") or 0) >= RULES["theme_market_z"]]
        if mk:
            out["theme_market"] = {"date": ctx["today"], "detail": f"{th['name']} (score {th['score']:.2f}; " +
                                   ", ".join({'physical_oil': 'fysisk olje', 'prediction_mkts': 'prediksjonsmarked'}[c] + f" z={comps[c]['score']:.1f}" for c in mk) + ")"}
            break
    return out


def classify(e: dict, ctx: dict) -> dict:
    t, st, R = e["ticker"], e.get("stats") or {}, RULES
    types = signal_types(e, ctx)
    n = len(types)
    close, sma, r5, r20 = st.get("close"), st.get("sma50"), st.get("ret_5d"), st.get("ret_20d")
    bench = benchmark_for(t)
    b20 = ctx["bench_ret20"].get(bench)
    above = None if close is None or sma is None else close > sma
    rel20 = None if r20 is None or b20 is None else r20 - b20
    beats = None if rel20 is None else rel20 > 0
    price_ok = bool(above) and bool(beats)
    fresh_dates = [v["date"] for v in types.values() if v["date"]]
    newest = max(fresh_dates) if fresh_dates else None
    fresh = newest is not None and (ctx["today"] - newest).days <= R["fresh_days"]
    stale = newest is not None and not fresh  # unknown dates are neither fresh nor stale
    dist = None if close is None or not sma else close / sma - 1
    stretched = any([r5 is not None and r5 >= R["stretch_5d"], r20 is not None and r20 >= R["stretch_20d"],
                     dist is not None and dist >= R["stretch_sma"]])
    # red flags
    flags = {}
    sh = ctx["shorts"].get(t)
    if sh and ((sh.get("chg_7d") or 0) >= R["short_7d"] or (sh.get("chg_30d") or 0) >= R["short_30d"]):
        flags["short"] = f"økende short ({sh.get('short_pct', 0):.2f} %, +{max(sh.get('chg_7d') or 0, 0):.2f} pp 7d)"
    dd = st.get("maxdd20")
    if dd is not None and dd <= R["crash"]:
        flags["crash"] = f"kursfall {dd*100:.0f} % siste 20 handelsdager"
    if is_equity(t) and close is not None:
        f = fx_usd(t)
        adv = st.get("adv20")
        if adv is not None and adv * f < R["min_adv_usd"]:
            flags["illiquid"] = f"lav likviditet (~${adv*f/1e6:.2f}M/dag)"
        if close * f < R["min_price_usd"]:
            flags["penny"] = "pennyaksje"
    dec = e.get("decision") or {}
    if dec.get("weak_mom_oslo"):
        # Oslo only: bottom-quintile 12-1 month momentum underperformed OSEBX out-of-sample (reports/backtest_natt.md)
        flags["weak_mom"] = f"svak 12-1-måneders momentum ({dec.get('mom12_1', 0)*100:+.0f} %, laveste 20 % på Oslo Børs)"
    pos = {k for k, v in e.get("points", {}).items() if v > 0}
    if pos and pos <= {"unusual_volume", "price_move"}:
        flags["volume_only"] = "bare volum/kurs-signal"
    no_flags = not flags

    rules = [
        ("≥ 2 uavhengige signaltyper fra kilder med høyere pålitelighet", n >= R["min_types"],
         ", ".join(TYPE_NO[k] for k in types) or "ingen"),
        (f"Minst ett av dem ferskere enn {R['fresh_days']} dager", fresh if types else False, f"nyeste {newest}" if newest else "–"),
        ("Kurs over 50-dagers glidende snitt", above,
         "mangler kursdata" if above is None else f"{close:.2f} vs {sma:.2f}"),
        (f"20-dagers avkastning bedre enn {BENCH_NAME[bench]}", beats,
         "mangler data" if rel20 is None else f"{r20*100:+.1f} % vs {b20*100:+.1f} %"),
        ("Ikke strukket (5d < +10 %, 20d < +25 %, < 25 % over 50d-snitt)", None if r5 is None else not stretched,
         "–" if r5 is None else f"5d {r5*100:+.1f} %, 20d {(r20 or 0)*100:+.1f} %" + (f", {dist*100:+.0f} % vs 50d" if dist is not None else "")),
        ("Ingen kraftig økende shortposisjoner", "short" not in flags, flags.get("short", "ok")),
        ("Ikke nylig krasj (≥ 20 % fall på 20 dager)", None if dd is None else "crash" not in flags, flags.get("crash", "ok" if dd is not None else "–")),
        ("Tilstrekkelig likviditet, ikke pennyaksje", "illiquid" not in flags and "penny" not in flags,
         "; ".join(flags[k] for k in ("illiquid", "penny") if k in flags) or "ok"),
        ("Ikke bare volum-/kurssignal", "volume_only" not in flags, "ok" if "volume_only" not in flags else "bare volum/kurs"),
    ]
    if t.endswith(".OL"):
        rules.append(("Oslo: ikke svak 12-1-måneders momentum (laveste 20 %)", None if dec.get("mom12_1") is None else "weak_mom" not in flags,
                      flags.get("weak_mom", "–" if dec.get("mom12_1") is None else f"{dec['mom12_1']*100:+.0f} %")))
    prev = ctx["prev_kjop"].get(t)
    prev_recent = prev is not None and (ctx["today"] - prev).days <= R["hold_memory_days"] and prev < ctx["today"]
    names = " + ".join(TYPE_NO[k] for k in types)
    bn = BENCH_NAME[bench]
    if n >= R["min_types"] and fresh and price_ok and no_flags and not stretched:
        cat = "kjop"
        reason = f"{names}; kurs over 50-dagers snitt og sterkere enn {bn} siste 20 d; ingen røde flagg."
    elif price_ok and no_flags and n >= 1 and (stretched or stale or prev_recent):
        cat = "hold"
        if stretched:
            reason = f"{names} og positiv trend, men kursen har allerede steget (5d {r5*100:+.0f} %, 20d {r20*100:+.0f} %" + (f", {dist*100:+.0f} % over 50d-snitt" if dist is not None else "") + ") – ikke jag."
        elif stale:
            reason = f"{names} og positiv trend, men ingen ny utløser siste {R['fresh_days']} dager (nyeste {newest})."
        else:
            reason = f"Var Kjøp-kandidat {prev}; trend og {names} holder fortsatt, ingen ny utløser."
    else:
        cat = "watch"
        why = []
        if flags:
            why.append("rødt flagg: " + ", ".join(flags.values()))
        if n == 0:
            kinds = sorted(pos - {"theme_attention"})
            why.append("bare tema-oppmerksomhet" if pos == {"theme_attention"} else
                       "ingen signaler fra kilder med høyere pålitelighet" + (" (bare " + ", ".join(kinds) + ")" if kinds else ""))
        elif n == 1:
            why.append(f"bare én uavhengig kildetype ({names})")
        if above is None:
            why.append("mangler kursdata")
        elif not above:
            why.append("kurs under 50-dagers snitt")
        elif beats is False:
            why.append(f"svakere enn {bn} siste 20 d")
        if not why and n >= 2 and not fresh:
            why.append("signalene er ikke ferske")
        reason = "Mangler bekreftelse: " + "; ".join(why[:3]) + "."
    return {"category": cat, "reason": reason, "rules": rules, "types": {k: v["detail"] for k, v in types.items()},
            "flags": list(flags.values()), "benchmark": bench}


# ---------------------------------------------------------------- forward log + track record
def read_log(path=LOG_PATH) -> pd.DataFrame:
    if path.exists():
        try:
            return pd.read_csv(path, dtype={"ticker": str})
        except Exception as ex:  # never let a damaged log break the run
            log.warning("categories log unreadable: %s", ex)
    return pd.DataFrame(columns=LOG_COLS)


def previous_kjop(logdf: pd.DataFrame, before: date) -> dict:
    if logdf.empty:
        return {}
    k = logdf[(logdf["category"] == "kjop") & (logdf["date"] < before.isoformat())]
    return {t: _d(d) for t, d in k.groupby("ticker")["date"].max().items()}


def append_log(snap: dict, path=LOG_PATH) -> pd.DataFrame:
    rows = [{"date": snap["date"], "ticker": e["ticker"], "category": e["category"],
             "price": (e.get("stats") or {}).get("close"), "price_date": (e.get("stats") or {}).get("last_date"),
             "benchmark": e.get("cat_benchmark"), "score": e.get("score"), "n_types": len(e.get("cat_types") or {})}
            for e in snap.get("tickers", []) if e.get("category")]
    old = read_log(path)
    old = old[old["date"] != snap["date"]]  # one set of rows per day (re-runs replace)
    df = pd.concat([old, pd.DataFrame(rows, columns=LOG_COLS)], ignore_index=True) if rows else old
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def entries(logdf: pd.DataFrame, gap_days=5) -> pd.DataFrame:
    """First day of each (ticker, category) streak - avoids counting the same call every day."""
    if logdf.empty:
        return logdf
    out = []
    for t, g in logdf.dropna(subset=["price"]).sort_values("date").groupby("ticker"):
        prev_cat, prev_d = None, None
        for _, r in g.iterrows():
            d = _d(r["date"])
            if r["category"] != prev_cat or prev_d is None or (d - prev_d).days > gap_days:
                out.append(r)
            prev_cat, prev_d = r["category"], d
    return pd.DataFrame(out)


def track_record(logdf: pd.DataFrame, closes: dict[str, pd.Series], min_n: int | None = None) -> dict:
    """Excess return (stock - benchmark) after 5/20/60 trading days for each category's new entries."""
    min_n = min_n or RULES["min_track_n"]
    ent = entries(logdf)
    res = {"n_log_rows": int(len(logdf)), "n_days": int(logdf["date"].nunique()) if len(logdf) else 0,
           "first_date": str(logdf["date"].min()) if len(logdf) else None, "min_n": min_n, "cats": {}}
    for cat in CAT_NO:
        e = ent[ent["category"] == cat] if len(ent) else ent
        res["cats"][cat] = {"entries": int(len(e))}
        for h in HORIZONS:
            xs = []
            for _, r in e.iterrows():
                c, b = closes.get(r["ticker"]), closes.get(r.get("benchmark") or benchmark_for(r["ticker"]))
                if c is None or b is None or c.empty or b.empty:
                    continue
                c, b = c.dropna(), b.dropna()
                p = c.index.searchsorted(pd.Timestamp(str(r.get("price_date") or r["date"])))
                if p >= len(c) or p + h >= len(c):
                    continue
                q = b.index.searchsorted(c.index[p])
                if q + h >= len(b):
                    continue
                xs.append((c.iloc[p + h] / c.iloc[p] - 1) - (b.iloc[q + h] / b.iloc[q] - 1))
            x = pd.Series(xs, dtype=float)
            res["cats"][cat][f"h{h}"] = ({"n": int(len(x)), "mean": float(x.mean()), "median": float(x.median()), "hit": float((x > 0).mean())}
                                        if len(x) >= min_n else {"n": int(len(x))})
    return res


# ---------------------------------------------------------------- orchestration (network)
def _download_close(tickers, **kw) -> dict[str, pd.Series]:
    import yfinance as yf
    tickers = sorted(set(tickers))
    if not tickers:
        return {}
    d = yf.download(tickers, progress=False, auto_adjust=True, group_by="ticker", threads=True, **kw)
    out = {}
    for t in tickers:
        try:
            s = (d[t]["Close"] if len(tickers) > 1 else d["Close"]).squeeze().dropna()
            if len(s):
                s.index = pd.to_datetime(s.index).tz_localize(None)
                out[t] = s
        except Exception:
            pass
    return out


def apply(snap: dict, log_path=LOG_PATH, fetch=True) -> dict:
    """Categorise every ticker in the snapshot, append to the forward log and compute the track record."""
    bench_ret20 = {}
    if fetch:
        try:
            bc = _download_close([BENCH_OSE, BENCH_US], period="6mo")
            bench_ret20 = {k: float(v.iloc[-1] / v.iloc[-21] - 1) for k, v in bc.items() if len(v) > 21}
        except Exception as ex:
            log.warning("benchmark download failed: %s", ex)
    logdf = read_log(log_path)
    today = _d(snap["date"]) or date.today()
    ctx = build_context(snap, bench_ret20, previous_kjop(logdf, today))
    for e in snap.get("tickers", []):
        c = classify(e, ctx)
        e.update({"category": c["category"], "cat_reason": c["reason"], "cat_rules": c["rules"],
                  "cat_types": c["types"], "cat_flags": c["flags"], "cat_benchmark": c["benchmark"]})
    logdf = append_log(snap, log_path)
    tr = track_record(logdf, {})
    matured = logdf[logdf["date"] <= (today - timedelta(days=7)).isoformat()] if len(logdf) else logdf
    if fetch and len(matured):
        try:
            start = (_d(matured["date"].min()) - timedelta(days=10)).isoformat()
            tick = set(matured["ticker"]) | {BENCH_OSE, BENCH_US}
            tr = track_record(logdf, _download_close(tick, start=start))
        except Exception as ex:
            log.warning("track record prices failed: %s", ex)
    counts = {k: sum(1 for e in snap.get("tickers", []) if e.get("category") == k) for k in CAT_NO}
    snap["categories_meta"] = {"rules": RULES, "bench_ret20": bench_ret20, "counts": counts}
    snap["track_record"] = tr
    return snap
