"""Rule-based stock categories: «Kjøp» (kandidat), «Hold», «Watchlist».

IMPORTANT: our own backtests (reports/backtest.md) found NO proven edge in insider clusters or GDELT spikes.
These categories are therefore deliberately conservative, fully transparent rules - NOT a forecast, NOT personal
financial advice, and NOT proven to beat the market. A forward log (logs/categories.csv, committed to git) records every
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
          (benchmark: OSEBX for .OL, SPY = S&P 500 incl. dividends otherwise)
      (4) not stretched: 5d return < +10 %, 20d return < +25 %, close < 25 % above the 50-day average
      (5) no red flags: sharply rising short interest (Oslo: +0.3 pp in 7d or +0.75 pp in 30d), crash (>= 20 %
          peak-to-trough within 20 sessions), illiquid (median turnover < ~USD 1M/day) or penny stock (< ~USD 1),
          or volume/price-only signals; Oslo only (signaltool/oslo_flags.py): weak price (bottom 20 % 12-1 momentum OR bottom
          20 % proximity to the 52-week high among liquid Oslo stocks), negative EBIT, private placement in the last 60 trading days.
          Yellow flags (high volatility, December small loser) and info tags (active buyback) never block.
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
from .config import HISTORY, LOGS

log = logging.getLogger(__name__)
LOG_PATH = LOGS / "categories.csv"   # tracked in git; committed back by the nightly workflow
_OLD_LOG_PATH = HISTORY / "categories.csv"   # pre-2026-09-28 location (git-ignored, Actions cache only)
if not LOG_PATH.exists() and _OLD_LOG_PATH.exists():  # one-time migration from the old cache-only location
    import shutil as _sh
    _sh.copy2(_OLD_LOG_PATH, LOG_PATH)
LOG_COLS = ["date", "ticker", "category", "price", "price_date", "benchmark", "score", "n_types", "types", "flags"]

RULES = dict(min_types=2, fresh_days=7, stretch_5d=0.10, stretch_20d=0.25, stretch_sma=0.25, crash=-0.20,
             min_adv_usd=1_000_000, min_price_usd=1.0, short_7d=0.3, short_30d=0.75, theme_min=1.0,
             theme_market_z=1.0, hold_memory_days=30, min_track_n=30, track_spacing=60)
HORIZONS = (5, 20, 60)
# market-based theme confirmation that counts as an independent signal: physical oil spreads/futures curves only
# (prediction-market moves were considered but are too loosely linked to single stocks, e.g. elections -> SPY)
MARKET_COMPONENTS = ("physical_oil",)
# SPY = S&P 500 WITH dividends (auto_adjust) - the stocks are measured dividend-adjusted too (^GSPC is a price index).
# OSEBX is a total-return index.
BENCH_OSE, BENCH_US = "OSEBX.OL", "SPY"
BENCH_NAME = {BENCH_OSE: "OSEBX", BENCH_US: "S&P 500"}
# ETFs / index products never enter the forward log (they are not single stocks)
ETFS = {"SPY", "ITA", "BDRY", "FXI", "EWW", "REMX", "SMH", "FEZ", "EWZ", "EWG", "XLE", "JETS", "XRT", "GLD", "GDX", "XLK", "XLV", "XLF",
        "XLY", "XLC", "XLI", "XLP", "XLU", "XLRE", "XLB", "USO", "BNO", "UNG", "SLV", "EWT", "EWJ", "EWY", "INDA", "KWEB", "TLT", "IEF",
        "HYG", "LQD", "EFA", "EEM", "QQQ", "IWM", "DIA", "URA", "LIT", "TAN", "ICLN", "OIH", "XOP", "KRE", "XME", "COPX", "SOXX"}
# rough FX to USD for liquidity / penny checks (only thresholds; precision is not important)
FX_USD = {".OL": 0.095, ".L": 0.0127, ".DE": 1.1, ".PA": 1.1, ".AS": 1.1, ".MI": 1.1, ".HE": 1.1, ".ST": 0.095,
          ".CO": 0.147, ".TO": 0.73, ".AX": 0.65}
TYPE_NO = {"gov_contract": "offentlig kontrakt (DoD/USAspending)", "insider_cluster": "innsidekjøp-klynge (ledelse/styre)",
           "ose_contract": "kontraktsmelding (Newsweb)", "theme_market": "tema med markedsbekreftelse",
           "pead": "sterk kvartalsrapport (eksperimentell, svak evidens)",
           "tema_kat": "Tema-katalysator (eksperimentell – teller ikke mot Kjøp)"}
CAT_NO = {"kjop": "Kjøp", "hold": "Hold", "watch": "Watchlist"}
DISCLAIMER_NO = ("Kategoriene er regelbaserte og mekaniske – ikke personlig finansiell rådgivning, og ikke bevist å slå markedet "
                 "(våre egne tester fant ingen dokumentert meravkastning).")
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def benchmark_for(ticker: str) -> str:
    return BENCH_OSE if ticker.endswith(".OL") else BENCH_US


def is_equity(ticker: str) -> bool:
    return not ("=" in ticker or ticker.startswith("^"))


def loggable(ticker, quote_type: str | None = None) -> bool:
    """Forward log / track record: single stocks on US exchanges (no suffix) or Oslo Børs (.OL) only.
    ETFs, indices, futures/FX and other exchanges (e.g. BA.L - no matching benchmark) are left out."""
    t = str(ticker or "")
    if not t or not is_equity(t) or t.upper() in ETFS or (quote_type and quote_type.upper() not in ("EQUITY", "")):
        return False
    return t.endswith(".OL") or "." not in t


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
        # EXPERIMENTAL / weak evidence (strategy-research/RAPPORT_3): point-in-time S&P 500 incl. former members gives ~+0.4-0.8 pp
        # gross per 60 d for the site thresholds (t 0.7-1.9), ~0 net of 0.75 % costs. PEAD-S (vol above median) ~+1 pp gross, ~+0.25 net.
        ps = " · PEAD-S (vol. over median)" if dec.get("pead_s") else ""
        out["pead"] = {"date": _d(dec.get("last_earnings")), "detail": f"EPS-overraskelse {dec.get('eps_surprise'):+.0f} %, reaksjon {dec.get('earn_reaction', 0)*100:+.1f} % vs SPY{ps}"}
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
    warnings, info = {}, {}
    osl = e.get("oslo") if t.endswith(".OL") else None
    if osl:
        from .oslo_flags import FLAG_INFO
        for k, txt in (osl.get("flags") or {}).items():
            kind = FLAG_INFO.get(k, ("", "red"))[1]
            (flags if kind == "red" else warnings)[k] = txt
        info.update(osl.get("info") or {})
    elif t.endswith(".OL") and dec.get("weak_mom_oslo"):
        # fallback without the ranked universe: fixed bottom-quintile momentum cut-off (older snapshots / tests)
        flags["weak_px"] = f"svak kurs: 12-1-måneders momentum {dec.get('mom12_1', 0)*100:+.0f} % (laveste 20 % på Oslo Børs)"
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
        known = bool(osl and (osl.get("mom12_1") is not None or osl.get("hi52") is not None)) or dec.get("mom12_1") is not None
        mtxt = "–"
        if osl and osl.get("mom12_1") is not None:
            mtxt = f"12-1 {osl['mom12_1']*100:+.0f} %" + (f", {(osl['hi52']-1)*100:.0f} % fra 52-ukers topp" if osl.get("hi52") is not None else "")
        elif dec.get("mom12_1") is not None:
            mtxt = f"{dec['mom12_1']*100:+.0f} %"
        rules.append(("Oslo: ikke svak kurs (laveste 20 % på 12-1-momentum eller avstand til 52-ukers topp)", None if not known else "weak_px" not in flags,
                      flags.get("weak_px", mtxt)))
        eb = (osl or {}).get("ebit")
        rules.append(("Oslo: ikke negativt driftsresultat (siste årsregnskap; testet kun 2022–26)", None if not eb else "neg_ebit" not in flags,
                      flags.get("neg_ebit", "–" if not eb else f"EBIT {eb['fye'][:4]}: {eb['ebit']/1e6:,.0f} mill.".replace(",", " "))))
        rules.append(("Oslo: ingen rettet emisjon siste 60 handelsdager", None if osl is None else "placement" not in flags, flags.get("placement", "ok" if osl else "–")))
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
            "flags": list(flags.values()), "flag_keys": list(flags), "warnings": warnings, "info": info, "benchmark": bench}


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
    """One row per loggable ticker (single US / Oslo stocks) and run date; re-runs the same date replace the rows.
    `types` = independent signal types ("pead|gov_contract") plus the experimental "tema_kat" tag (never counted as a type for
    Kjøp; n_types excludes it), `flags` = red/yellow flag keys ("weak_px|high_vol")."""
    rows = [{"date": snap["date"], "ticker": e["ticker"], "category": e["category"],
             "price": (e.get("stats") or {}).get("close"), "price_date": (e.get("stats") or {}).get("last_date"),
             "benchmark": e.get("cat_benchmark"), "score": e.get("score"), "n_types": len(e.get("cat_types") or {}),
             "types": "|".join(sorted(list(e.get("cat_types") or {}) + (["tema_kat"] if (e.get("temakart") or {}).get("tema_kat") else []))),
             "flags": "|".join(list(e.get("cat_flag_keys") or []) + sorted(e.get("cat_warnings") or {}))}
            for e in snap.get("tickers", []) if e.get("category") and loggable(e["ticker"], (e.get("decision") or {}).get("quoteType"))]
    from .theme_maps import log_rows   # theme-map tickers outside the snapshot: category "tema" (not in Kjøp/Hold/Watchlist stats)
    rows += log_rows(snap)
    old = read_log(path)
    old = old[old["date"] != snap["date"]]  # one set of rows per day (re-runs replace)
    df = pd.concat([old, pd.DataFrame(rows, columns=LOG_COLS)], ignore_index=True) if rows else old
    df = df.reindex(columns=LOG_COLS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def _explode(logdf: pd.DataFrame, col: str) -> pd.DataFrame:
    """One row per (row, pipe-separated value in col) with the value in column 'key'."""
    if logdf.empty or col not in logdf.columns:
        return pd.DataFrame(columns=list(logdf.columns) + ["key"])
    d = logdf.assign(key=logdf[col].fillna("").astype(str).str.split("|")).explode("key")
    return d[d["key"] != ""]


def entries(logdf: pd.DataFrame, key: str = "category", spacing: int | None = None) -> pd.DataFrame:
    """Independent new entries per (ticker, key):
    * a streak = consecutive RUN DAYS in the log with the same (ticker, key); only the first day of a streak counts (a pause
      between runs never splits a streak, and one missing ticker-day starts a new one);
    * non-overlapping: at most one entry per (ticker, key) per `spacing` trading days (default 60 = the longest horizon)."""
    if logdf.empty:
        return logdf
    spacing = RULES["track_spacing"] if spacing is None else spacing
    d = logdf.copy()
    d["date"] = d["date"].astype(str)
    runs = sorted(d["date"].unique())
    prev = {x: (runs[i - 1] if i else None) for i, x in enumerate(runs)}
    present = set(zip(d["date"], d["ticker"], d[key]))
    out, last = [], {}
    for _, r in d.sort_values("date").iterrows():
        k = (r["ticker"], r[key])
        if (prev[r["date"]], r["ticker"], r[key]) in present:
            continue  # continuing streak
        dd = _d(r["date"])
        if k in last and np.busday_count(last[k], dd) < spacing:
            continue  # overlapping window with an earlier counted entry
        last[k] = dd
        out.append(r)
    return pd.DataFrame(out, columns=d.columns) if out else d.iloc[0:0]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95 % Wilson interval for a hit rate k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (float(c - h), float(c + h))


def mean_ci(x: pd.Series, groups: pd.Series, z: float = 1.96) -> tuple[float, float]:
    """95 % interval for the mean with standard errors clustered by entry week (entries in the same week are not independent)."""
    x = pd.Series(x, dtype=float).reset_index(drop=True)
    g = pd.Series(groups).reset_index(drop=True)
    n = len(x)
    if n < 2 or g.nunique() < 2:
        return (float("nan"), float("nan"))
    e = x - x.mean()
    se = float(np.sqrt((e.groupby(g).sum() ** 2).sum()) / n)
    return (float(x.mean() - z * se), float(x.mean() + z * se))


def _outcomes(ent: pd.DataFrame, closes: dict[str, pd.Series], h: int, status: dict) -> list[tuple]:
    """(entry_date, excess) for entries that reached h trading days. Entry = FIRST close AFTER the run date (the run uses
    closes up to the day before, so that close could not have been traded). Benchmark: SPY (US) / OSEBX (Oslo).
    A ticker that stopped trading inside the window keeps its last close (cash thereafter) and is listed as 'stopped';
    a ticker without any price series is listed as 'missing' (never silently dropped)."""
    out = []
    for _, r in ent.iterrows():
        t = r["ticker"]
        c, b = closes.get(t), closes.get(benchmark_for(t))
        if b is None or b.empty:
            continue
        b = b.dropna()
        if c is None or c.dropna().empty:
            status["missing"].add(t)
            continue
        c = c.dropna()
        run = pd.Timestamp(str(r["date"]))
        q0 = b.index.searchsorted(run, side="right")
        if q0 + h >= len(b):
            continue  # not matured yet
        p = c.index.searchsorted(run, side="right")
        stopped = c.index[-1] < b.index[-1] - pd.Timedelta(days=7)
        if p >= len(c):
            status["missing" if not stopped else "stopped"].add(t)
            continue
        q = b.index.searchsorted(c.index[p])
        if q + h >= len(b):
            continue
        end = b.index[q + h]
        if p + h < len(c) and c.index[p + h] <= end + pd.Timedelta(days=5):
            ce = c.iloc[p + h]
        elif stopped:
            ce = c.iloc[-1]
            status["stopped"].add(t)
        else:
            continue
        out.append((c.index[p], (ce / c.iloc[p] - 1) - (b.iloc[q + h] / b.iloc[q] - 1)))
    return out


def _perf(ent: pd.DataFrame, closes: dict, min_n: int, status: dict) -> dict:
    res = {"entries": int(len(ent))}
    for h in HORIZONS:
        o = _outcomes(ent, closes, h, status) if len(ent) else []
        x = pd.Series([v for _, v in o], dtype=float)
        r = {"n": int(len(x))}
        if len(x) >= min_n:
            wk = pd.Series([pd.Timestamp(d).strftime("%G-%V") for d, _ in o])
            k = int((x > 0).sum())
            r.update({"mean": float(x.mean()), "median": float(x.median()), "hit": k / len(x),
                      "hit_ci": wilson(k, len(x)), "mean_ci": mean_ci(x, wk), "weeks": int(wk.nunique())})
        res[f"h{h}"] = r
    return res


def track_record(logdf: pd.DataFrame, closes: dict[str, pd.Series], min_n: int | None = None) -> dict:
    """Excess return (stock - benchmark) after 5/20/60 trading days for independent new entries, per category, per signal
    type and per flag. Numbers are shown only from min_n (default 30) independent entries, with 95 % intervals."""
    min_n = min_n or RULES["min_track_n"]
    full = logdf
    if len(logdf):
        keep = logdf["ticker"].map(loggable)
        excluded = sorted(set(logdf.loc[~keep, "ticker"]))
        logdf = logdf[keep]
    else:
        excluded = []
    status = {"missing": set(), "stopped": set()}
    ent = entries(logdf)
    res = {"n_log_rows": int(len(full)), "n_days": int(full["date"].nunique()) if len(full) else 0,
           "first_date": str(full["date"].min()) if len(full) else None, "min_n": min_n, "spacing": RULES["track_spacing"],
           "benchmarks": {"us": "SPY (inkl. utbytte)", "oslo": "OSEBX"}, "excluded": excluded, "cats": {}, "types": {}, "flags": {}}
    for cat in CAT_NO:
        res["cats"][cat] = _perf(ent[ent["category"] == cat] if len(ent) else ent, closes, min_n, status)
    for col, dest in (("types", "types"), ("flags", "flags")):
        ex = _explode(logdf, col)
        if len(ex):
            ek = entries(ex, key="key")
            for k in sorted(ex["key"].unique()):
                res[dest][k] = _perf(ek[ek["key"] == k], closes, min_n, status)
    res["missing"] = sorted(status["missing"])
    res["stopped"] = sorted(status["stopped"])
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
                  "cat_types": c["types"], "cat_flags": c["flags"], "cat_flag_keys": c["flag_keys"],
                  "cat_warnings": c["warnings"], "cat_info": c["info"], "cat_benchmark": c["benchmark"]})
    logdf = append_log(snap, log_path)
    tr = track_record(logdf, {})
    matured = logdf[logdf["date"] <= (today - timedelta(days=7)).isoformat()] if len(logdf) else logdf
    if fetch and len(matured):
        try:
            start = (_d(matured["date"].min()) - timedelta(days=10)).isoformat()
            tick = {t for t in matured["ticker"] if loggable(t)} | {BENCH_OSE, BENCH_US}
            tr = track_record(logdf, _download_close(tick, start=start))
        except Exception as ex:
            log.warning("track record prices failed: %s", ex)
    counts = {k: sum(1 for e in snap.get("tickers", []) if e.get("category") == k) for k in CAT_NO}
    snap["categories_meta"] = {"rules": RULES, "bench_ret20": bench_ret20, "counts": counts}
    snap["track_record"] = tr
    return snap
