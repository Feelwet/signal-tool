"""Research-driven changes (strategy-research RAPPORT 1-3): forward-log fixes, Oslo red flags, PEAD-S, regime, portfolio rules."""
from datetime import date, timedelta
import numpy as np
import pandas as pd
import pytest
from signaltool import categories as C, oslo_flags as O, plan as P, regime, site, site_extra as X
from signaltool.decision import pead_s_check
from tests.test_categories import cand, ctx, snap, two_ctx, TWO, FRESH, TODAY

DAYS = pd.bdate_range("2026-01-01", periods=200)


def _row(t, cat="watch", types=None, flags=None, close=100.0):
    return {"ticker": t, "category": cat, "score": 1, "stats": {"close": close, "last_date": "x"}, "cat_benchmark": C.benchmark_for(t),
            "cat_types": {k: "" for k in (types or [])}, "cat_flag_keys": flags or [], "cat_warnings": {}}


# ---------------------------------------------------------------- A: forward log
def test_log_types_flags_and_only_single_us_oslo_stocks(tmp_path):
    p = tmp_path / "c.csv"
    s = {"date": "2026-09-28", "tickers": [_row("AAA", types=["pead", "gov_contract"], flags=["short"]), _row("SPY"), _row("BA.L"), _row("EQNR.OL", flags=["weak_px"])]}
    df = C.append_log(s, p)
    assert list(df.columns) == C.LOG_COLS and set(df["ticker"]) == {"AAA", "EQNR.OL"}
    r = df.set_index("ticker")
    assert r.at["AAA", "types"] == "gov_contract|pead" and r.at["AAA", "flags"] == "short" and r.at["EQNR.OL", "flags"] == "weak_px"
    assert not C.loggable("FEZ") and not C.loggable("^GSPC") and not C.loggable("CL=F") and C.loggable("BRK-B") and C.loggable("NVDA", "EQUITY")
    assert not C.loggable("XYZ", "ETF")


def test_us_benchmark_is_dividend_adjusted_spy():
    assert C.benchmark_for("AAPL") == "SPY" == C.BENCH_US and C.benchmark_for("EQNR.OL") == "OSEBX.OL"


def _log(rows):
    return pd.DataFrame([{**{c: None for c in C.LOG_COLS}, **r} for r in rows])


def test_entry_is_first_close_after_run_date():
    run = DAYS[10]
    px = pd.Series(100.0, index=DAYS); px[DAYS > run] = 110.0            # gap the day after the run
    closes = {"AAA": px, "SPY": pd.Series(100.0, index=DAYS)}
    lg = _log([{"date": str(run.date()), "ticker": "AAA", "category": "kjop", "price": 100.0, "price_date": str(DAYS[9].date()), "benchmark": "^GSPC"}])
    tr = C.track_record(lg, closes, min_n=1)
    assert abs(tr["cats"]["kjop"]["h5"]["mean"]) < 1e-12                  # the +10 % gap is NOT captured


def test_entries_pause_between_runs_is_one_entry_and_windows_do_not_overlap():
    runs = list(DAYS[0:5]) + list(DAYS[20:25])                           # 2-week pause in the RUNS, ticker always Kjøp
    lg = _log([{"date": str(d.date()), "ticker": "AAA", "category": "kjop", "price": 1.0} for d in runs])
    assert len(C.entries(lg)) == 1
    # leaves the category and returns 10 trading days later -> still inside the 60-day window -> not a new independent entry
    rows = [{"date": str(d.date()), "ticker": "AAA", "category": "kjop" if not (5 <= i < 8) else "watch", "price": 1.0} for i, d in enumerate(DAYS[:15])]
    e = C.entries(_log(rows))
    assert len(e[e["category"] == "kjop"]) == 1 and len(e[e["category"] == "watch"]) == 1
    # returns after >= 60 trading days -> counted again
    rows = [{"date": str(DAYS[0].date()), "ticker": "AAA", "category": "kjop", "price": 1.0},
            {"date": str(DAYS[1].date()), "ticker": "AAA", "category": "watch", "price": 1.0},
            {"date": str(DAYS[70].date()), "ticker": "AAA", "category": "kjop", "price": 1.0}]
    assert len(C.entries(_log(rows)).query("category == 'kjop'")) == 2


def test_missing_and_stopped_tickers_are_reported_not_dropped():
    closes = {"SPY": pd.Series(100.0, index=DAYS), "DEAD": pd.Series(np.linspace(100, 50, 30), index=DAYS[:30])}
    lg = _log([{"date": str(DAYS[5].date()), "ticker": t, "category": "watch", "price": 10.0} for t in ("DEAD", "GONE")])
    tr = C.track_record(lg, closes, min_n=1)
    assert tr["missing"] == ["GONE"] and tr["stopped"] == ["DEAD"]
    assert tr["cats"]["watch"]["h60"]["n"] == 1 and tr["cats"]["watch"]["h60"]["mean"] < -0.3   # last close used (cash thereafter)


def test_min_n_30_confidence_intervals_and_per_type():
    assert C.RULES["min_track_n"] == 30
    closes = {"SPY": pd.Series(100.0, index=DAYS)}
    rows = []
    for i in range(12):
        t = f"T{i}"
        closes[t] = pd.Series([100 * (1.002 if i % 3 else 0.999) ** k for k in range(len(DAYS))], index=DAYS)
        rows.append({"date": str(DAYS[i].date()), "ticker": t, "category": "watch", "price": 100.0, "types": "pead" if i < 6 else "", "flags": "weak_px" if i >= 6 else ""})
    tr = C.track_record(_log(rows), closes, min_n=5)
    h = tr["cats"]["watch"]["h20"]
    assert h["n"] == 12 and h["hit_ci"][0] < h["hit"] < h["hit_ci"][1] and h["mean_ci"][0] < h["mean"] < h["mean_ci"][1]
    assert tr["types"]["pead"]["entries"] == 6 and tr["flags"]["weak_px"]["entries"] == 6
    assert "mean" not in C.track_record(_log(rows), closes)["cats"]["watch"]["h20"]     # default 30 -> hidden
    lo, hi = C.wilson(15, 30)
    assert 0.31 < lo < 0.34 and 0.66 < hi < 0.69


# ---------------------------------------------------------------- C: Oslo flags
def _universe(n=30, days=300):
    idx = pd.bdate_range("2025-06-01", periods=days)
    rng = np.random.default_rng(1)
    out = {}
    for i in range(n):
        drift = 0.001 * (i - n / 2) / n * 4
        vol = 0.01 if i != n - 1 else 0.05
        c = 50 * np.exp(np.cumsum(drift + vol * rng.standard_normal(days)))
        out[f"S{i}.OL"] = pd.DataFrame({"Close": c, "High": c * 1.005, "Volume": 1e6}, index=idx)
    return out


def test_oslo_price_flags_ranked_in_liquid_universe():
    meta, m = O.price_ranks(_universe())
    assert meta["n_liquid"] == 30 and meta["mom_q20"] is not None
    weakest = m["mom12_1"].idxmin()
    f = O.price_flags(weakest, m, meta, date(2026, 9, 28))
    assert "weak_px" in f["flags"] and "momentum" in f["flags"]["weak_px"]
    assert "high_vol" in O.price_flags("S29.OL", m, meta, date(2026, 9, 28))["flags"]
    strongest = m["hi52"].idxmax()
    assert "weak_px" not in O.price_flags(strongest, m, meta, date(2026, 9, 28))["flags"]
    assert O.in_december_window(date(2026, 12, 3)) and O.in_december_window(date(2027, 1, 20)) and not O.in_december_window(date(2027, 1, 21))


def test_newsweb_placement_and_buyback():
    today = date(2026, 9, 28)
    nw = pd.DataFrame([
        {"published": "2026-08-10T06:00:00Z", "issuer": "AAA", "title": "AAA ASA: Successful private placement", "category": "INSIDE INFORMATION", "url": "u1"},
        {"published": "2026-08-11T06:00:00Z", "issuer": "BBB", "title": "Mandatory notification of trade - private placement", "category": "MANAGERS", "url": "u2"},
        {"published": "2026-03-01T06:00:00Z", "issuer": "CCC", "title": "Rettet emisjon gjennomført", "category": "INSIDE INFORMATION", "url": "u3"},
        {"published": "2026-09-20T06:00:00Z", "issuer": "DDD", "title": "Share buyback", "category": "ACQUISITION OR DISPOSAL OF AN ISSUER'S OWN SHARES", "url": "u4"},
        {"published": "2026-07-01T06:00:00Z", "issuer": "EEE", "title": "Share buyback", "category": "ACQUISITION OR DISPOSAL OF AN ISSUER'S OWN SHARES", "url": "u5"}])
    ev = O.newsweb_events(nw, today)
    assert ev["AAA.OL"]["placement"]["date"] == "2026-08-10"
    assert "BBB.OL" not in ev and "CCC.OL" not in ev           # trade notification / older than 60 trading days
    assert ev["DDD.OL"]["buyback"]["url"] == "u4" and "EEE.OL" not in ev


def test_ebit_from_statement():
    fin = pd.DataFrame({pd.Timestamp("2025-12-31"): [-5e6, -4e6], pd.Timestamp("2024-12-31"): [1e6, 1e6]}, index=["EBIT", "Operating Income"])
    assert O.ebit_from_statement(fin) == {"fye": "2025-12-31", "ebit": -5e6, "item": "EBIT"}
    assert O.ebit_from_statement(None) is None


def _oslo_kjop(**oslo):
    s = snap(newsweb_contracts=[{"issuer": "ABC", "published": FRESH}],
             themes=[{"key": "t", "name": "Olje", "score": 1.5, "components": {"physical_oil": {"score": 3.0}}}])
    e = cand("ABC.OL", points={"ose_contracts": 1.5, "theme_attention": 1.0}, themes=["t"], stats={"adv20": 50e6})
    e["oslo"] = {"mom12_1": 0.1, "hi52": 0.95, "flags": {}, "ebit": {"fye": "2025-12-31", "ebit": 1e8}, **oslo}
    return C.classify(e, ctx(s))


def test_oslo_red_flags_block_kjop_yellow_and_info_do_not():
    assert _oslo_kjop()["category"] == "kjop"
    for k in ("weak_px", "neg_ebit", "placement"):
        r = _oslo_kjop(flags={k: f"{k} tekst"})
        assert r["category"] == "watch" and k in r["flag_keys"], k
    r = _oslo_kjop(flags={"weak_px": "svak kurs: 12-1-momentum -40 %"})
    assert any(x[0].startswith("Oslo: ikke svak kurs") and x[1] is False for x in r["rules"])
    r = _oslo_kjop(flags={"high_vol": "høy vol"}, info={"buyback": "aktivt tilbakekjøp"})
    assert r["category"] == "kjop" and "high_vol" in r["warnings"] and "buyback" in r["info"]


def test_flags_html_shows_evidence_level():
    e = {"ticker": "ABC.OL", "cat_flag_keys": ["weak_px"], "cat_flags": ["svak kurs: x"], "cat_warnings": {"high_vol": "høy"}, "cat_info": {"buyback": "tilbakekjøp"},
         "oslo": {"buyback": {"date": "2026-09-20", "title": "Share buyback", "url": "u"}}}
    h = X.flags_html(e)
    assert "evidens: sterk" in h and "Aktivt tilbakekjøp" in h and "−3,7 %" in h and "gult flagg" in h


# ---------------------------------------------------------------- B: PEAD-S
def test_pead_s_uses_vol_median_day_before():
    idx = pd.bdate_range("2025-01-01", periods=320)
    rng = np.random.default_rng(0)
    c = pd.Series(100 * np.exp(np.cumsum(0.03 * rng.standard_normal(320))), index=idx)
    med = pd.Series(0.015, index=idx[-100:])
    r = pead_s_check(c, 310, med, True)
    assert r["pead_s"] is True and r["vol1y_d"] > 0.015
    assert pead_s_check(c, 310, pd.Series(0.2, index=idx[-100:]), True)["pead_s"] is False
    assert pead_s_check(c, 310, med, False)["pead_s"] is False


def test_pead_is_labelled_experimental():
    e = cand(points={"dod_contract": 1.5}, dates={"gov_contract": FRESH})
    e["decision"] = {"pead": True, "pead_s": True, "last_earnings": FRESH, "eps_surprise": 22.0, "earn_reaction": 0.06}
    r = C.classify(e, ctx())
    assert "eksperimentell" in C.TYPE_NO["pead"] and "PEAD-S" in r["types"]["pead"] and "SPY" in r["types"]["pead"]


def test_pead_base_rates_point_in_time_net():
    from signaltool.backtest import base_rates as B
    if not B.PIT_EVENTS.exists():
        pytest.skip("point-in-time event table not available")
    r = B.pead()
    assert r["pead"]["pit"] and abs(r["pead"]["net60"] - (r["pead"]["mean60"] - 0.0075)) < 1e-12
    assert abs(r["pead"]["mean60_is"] - 0.0076) < 5e-4 and abs(r["pead_s"]["mean60_oos"] - 0.0103) < 5e-4   # RAPPORT_3 F3 / F4


# ---------------------------------------------------------------- D: regime, sizing, confirmation level
def test_regime_below_10m_average_is_risk_off():
    idx = pd.bdate_range("2024-09-01", periods=520)
    up = pd.Series(np.linspace(100, 200, 520), index=idx)
    a = regime.assess(up)
    assert not a["below"] and not a["risk_off"]
    down = up.copy(); down.iloc[-30:] = np.linspace(180, 120, 30)
    b = regime.assess(down)
    assert b["below"] and b["risk_off"]


def _plan_e(**kw):
    e = {"ticker": "XYZ", "category": "kjop", "cat_types": {"insider_cluster": "x"}, "points": {}, "themes": [], "stats": {"ret_5d": 0.0, "ret_20d": 0.02, "adv20": 5e7},
         "decision": {"close": 100.0, "atr14": 2.0, "sma50": 99.5, "sma20": 98.0, "stop_atr": 90.0, "vol60": 0.3}}
    e.update(kw)
    return e


def test_position_cap_5pct_and_halvings():
    assert P.MAX_POSITION == 0.05
    base = P.levels(_plan_e())["size"]
    assert base <= 0.05 + 1e-12
    assert abs(P.levels(_plan_e(cat_warnings={"high_vol": "x"}))["size"] - base / 2) < 1e-12
    lv = P.levels(_plan_e(_regime={"name": "S&P 500", "below": True, "high_vol": False, "risk_off": True, "vol1m": 0.1}))
    assert abs(lv["size"] - base / 2) < 1e-12 and any("markedsregime" in r for r in lv["size_reasons"])
    assert "ASK" in P.net_note({"ticker": "AAPL"}) and "37.84" in P.net_note({"ticker": "AAPL"})


def test_far_confirmation_level_is_hidden_hhh():
    # HHH 2026-09-28: close 68.43, 52-week high 89.85 (+31 %) - must never be the confirmation level
    e = _plan_e(category="hold", decision={"close": 68.43, "atr14": 2.15, "sma50": 65.3, "sma20": 63.43, "hi20": None, "hi52": 89.85, "rel_bench_20d": 0.052})
    th = P.thesis(e)
    assert "89.85" not in th["bekreftes"] and "63.43" in th["bekreftes"]
    e["decision"]["hi20"] = 85.0                      # a far 20-day high after a crash is hidden too
    assert "85.00" not in P.thesis(e)["bekreftes"]
    assert P.near_level(104, 100) and not P.near_level(124, 100) and not P.near_level(95, 100)


# ---------------------------------------------------------------- site
def test_site_sections():
    h = X.dropped_html()
    assert "Testet og droppet" in h and "Minervini" in h and "Dual Momentum" in h and "ikke noe robust kjøpssignal" in h
    assert "Ærlig status" in X.honesty_html() and "maks 5 %" in X.portfolio_rules_html().replace("Maks", "maks")
    tr = C.track_record(_log([{"date": "2026-09-28", "ticker": "AAA", "category": "watch", "price": 1.0, "types": "pead"}]), {})
    t = site.track_html({"track_record": tr})
    assert "vises fra 30" in t and "Per signaltype" in t
    r = X.regime_html({"regime": {"^GSPC": {"name": "S&P 500", "last": 1, "sma10m": 2, "dist": -0.5, "vol1m": 0.3, "below": True, "high_vol": True, "risk_off": True, "asof": "x"}}})
    assert "halver nye posisjoner" in r and "Ikke et salgssignal" in r
