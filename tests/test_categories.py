"""Rule-based Kjøp-kandidat / Hold / Watchlist categories."""
from datetime import date, timedelta
import pandas as pd
from signaltool import categories as C

TODAY = date(2026, 9, 27)
GOOD = {"close": 110.0, "sma50": 100.0, "ret_5d": 0.02, "ret_20d": 0.05, "maxdd20": -0.05, "adv20": 50e6}


def snap(**kw):
    s = {"date": TODAY.isoformat(), "themes": [], "shorts": [], "insider_clusters": [], "dod_awards": [], "awards": [], "newsweb_contracts": []}
    s.update(kw)
    return s


def ctx(s=None, prev=None, bench=0.01):
    return C.build_context(s or snap(), {C.BENCH_US: bench, C.BENCH_OSE: bench}, prev or {})


def cand(ticker="XYZ", points=None, stats=None, dates=None, themes=None):
    return {"ticker": ticker, "points": points or {}, "stats": {**GOOD, **(stats or {})}, "themes": themes or [],
            "evidence": [], "signal_dates": dates or {}}


FRESH = (TODAY - timedelta(days=2)).isoformat()
OLD = (TODAY - timedelta(days=12)).isoformat()
TWO = {"dod_contract": 1.5, "insider_cluster": 1.5}


def two_ctx():
    return ctx(snap(insider_clusters=[{"ticker": "XYZ", "roles": "Director; Chief Executive Officer", "last_date": FRESH}]))


def test_kjop_requires_all_rules():
    r = C.classify(cand(points=TWO, dates={"gov_contract": FRESH}), two_ctx())
    assert r["category"] == "kjop", r["reason"]
    assert set(r["types"]) == {"gov_contract", "insider_cluster"}
    assert all(x[1] for x in r["rules"] if not x[0].startswith("…eller"))  # topp/topp-raden er et alternativ, ikke et krav


def test_single_source_is_watchlist():
    r = C.classify(cand(points={"dod_contract": 2.0}, dates={"gov_contract": FRESH}), ctx())
    assert r["category"] == "watch" and "én uavhengig" in r["reason"]


def test_volume_only_is_red_flag():
    r = C.classify(cand(points={"unusual_volume": 2.0, "price_move": 1.0}), ctx())
    assert r["category"] == "watch" and "bare volum" in r["reason"]


def test_dod_and_usaspending_count_as_one_type():
    r = C.classify(cand(points={"dod_contract": 1.0, "federal_award": 1.0}, dates={"gov_contract": FRESH}), ctx())
    assert list(r["types"]) == ["gov_contract"] and r["category"] == "watch"


def test_ten_percent_owner_cluster_does_not_count():
    s = snap(insider_clusters=[{"ticker": "XYZ", "roles": "10% owner", "last_date": FRESH}])
    r = C.classify(cand(points=TWO, dates={"gov_contract": FRESH}), ctx(s))
    assert "insider_cluster" not in r["types"] and r["category"] == "watch"


def test_price_below_sma_or_weaker_than_benchmark_blocks_kjop():
    assert C.classify(cand(points=TWO, stats={"close": 95.0}, dates={"gov_contract": FRESH}), two_ctx())["category"] == "watch"
    r = C.classify(cand(points=TWO, stats={"ret_20d": 0.0}, dates={"gov_contract": FRESH}),
                   C.build_context(two_ctx_snap(), {C.BENCH_US: 0.03}, {}))
    assert r["category"] == "watch" and "svakere enn S&P 500" in r["reason"]


def two_ctx_snap():
    return snap(insider_clusters=[{"ticker": "XYZ", "roles": "Director", "last_date": FRESH}])


def test_stretched_is_hold():
    r = C.classify(cand(points=TWO, stats={"ret_5d": 0.15}, dates={"gov_contract": FRESH}), two_ctx())
    assert r["category"] == "hold" and "ikke jag" in r["reason"]


def test_stale_signals_are_hold_not_kjop():
    s = snap(insider_clusters=[{"ticker": "XYZ", "roles": "Director", "last_date": OLD}])
    r = C.classify(cand(points=TWO, dates={"gov_contract": OLD}), ctx(s))
    assert r["category"] == "hold" and "ingen ny utløser" in r["reason"]


def test_previous_kjop_without_new_trigger_is_hold():
    r = C.classify(cand(points={"dod_contract": 1.0}, dates={"gov_contract": OLD}), ctx(prev={"XYZ": TODAY - timedelta(days=5)}))
    assert r["category"] == "hold"


def test_red_flags_block_kjop_and_hold():
    for stats in ({"maxdd20": -0.3}, {"adv20": 10_000.0}, {"close": 0.5, "sma50": 0.4}):
        r = C.classify(cand(points=TWO, stats=stats, dates={"gov_contract": FRESH}), two_ctx())
        assert r["category"] == "watch" and "rødt flagg" in r["reason"], stats
    s = two_ctx_snap(); s["shorts"] = [{"ticker": "XYZ", "short_pct": 3.0, "chg_7d": 0.8, "chg_30d": 1.0}]
    assert C.classify(cand(points=TWO, dates={"gov_contract": FRESH}), ctx(s))["category"] == "watch"


def test_oslo_liquidity_uses_fx_and_osebx():
    s = snap(newsweb_contracts=[{"issuer": "ABC", "published": FRESH}],
             themes=[{"key": "t", "name": "Olje", "score": 1.5, "components": {"physical_oil": {"score": 3.0}}}])
    e = cand("ABC.OL", points={"ose_contracts": 1.5, "theme_attention": 1.0}, themes=["t"], stats={"adv20": 50e6})
    r = C.classify(e, ctx(s))
    assert r["benchmark"] == C.BENCH_OSE and set(r["types"]) == {"ose_contract", "theme_market"} and r["category"] == "kjop"
    e["stats"]["adv20"] = 5e6  # NOK 5M ~ USD 0.5M -> illiquid
    assert C.classify(e, ctx(s))["category"] == "watch"


def test_theme_without_oil_confirmation_does_not_count():
    s = snap(themes=[{"key": "t", "name": "Valg", "score": 2.0, "components": {"prediction_mkts": {"score": 3.0}}}])
    r = C.classify(cand(points={"theme_attention": 1.0}, themes=["t"]), ctx(s))
    assert r["types"] == {} and "tema-oppmerksomhet" in r["reason"]


def test_missing_prices_is_watchlist():
    e = cand(points=TWO, dates={"gov_contract": FRESH}); e["stats"] = {}
    assert C.classify(e, two_ctx())["category"] == "watch"


def test_log_and_track_record(tmp_path):
    p = tmp_path / "categories.csv"
    days = pd.bdate_range("2026-01-01", periods=120)
    closes = {"AAA": pd.Series([100 * 1.01 ** i for i in range(120)], index=days),
              C.BENCH_US: pd.Series([100.0] * 120, index=days)}
    for i in range(0, 30):  # 30 daily runs, AAA always Kjøp -> only ONE new entry
        s = {"date": days[i].date().isoformat(), "tickers": [{"ticker": "AAA", "category": "kjop", "score": 1,
             "stats": {"close": closes["AAA"].iloc[i], "last_date": days[i].date().isoformat()}, "cat_benchmark": C.BENCH_US, "cat_types": {}}]}
        df = C.append_log(s, p)
    C.append_log(s, p)  # re-run same day replaces, not duplicates
    df = C.read_log(p)
    assert len(df) == 30 and len(C.entries(df)) == 1
    tr = C.track_record(df, closes, min_n=1)
    assert tr["cats"]["kjop"]["h5"]["mean"] > 0.04 and tr["cats"]["hold"]["entries"] == 0
    assert "mean" not in C.track_record(df, closes)["cats"]["kjop"]["h5"]  # default min_n=10 -> not enough data


def test_parse_dates():
    assert C._d("Contracts for Sept. 23, 2026") == date(2026, 9, 23)
    assert C._d("2026-09-25T07:41:09.719Z") == date(2026, 9, 25)
    assert C._d(None) is None


# ---------------- PEAD topp/topp
TT = {"pead": True, "last_earnings": FRESH, "eps_surprise": 22.0, "earn_reaction": 0.06}


def _tt(stats=None, dec=None, points=None, dates=None):
    e = cand(points=points or {}, stats=stats, dates=dates)
    e["decision"] = {**TT, **(dec or {})}
    return e


def test_tt_alone_is_kjop_and_not_double_counted():
    r = C.classify(_tt(), ctx())
    assert r["category"] == "kjop" and r["via_tt"], r["reason"]
    assert list(r["types"]) == ["pead_tt"]          # samme rapport: aldri både pead og pead_tt
    assert "via Sterk rapport + reaksjon" in r["reason"]


def test_ordinary_pead_does_not_count_for_kjop():
    e = _tt(dec={"eps_surprise": 9.0}, points={"dod_contract": 1.5}, dates={"gov_contract": FRESH})
    r = C.classify(e, ctx())
    assert set(r["types"]) == {"pead", "gov_contract"} and r["category"] != "kjop"


def test_tt_exempt_from_stretch():
    hot = {"ret_5d": 0.12, "ret_20d": 0.30, "close": 130.0}
    assert C.classify(_tt(stats=hot), ctx())["category"] == "kjop"
    e = _tt(stats=hot, dec={"eps_surprise": 9.0}, points={"dod_contract": 1.5}, dates={"gov_contract": FRESH})
    assert C.classify(e, ctx())["category"] != "kjop"
    st = next(x for x in C.classify(_tt(stats=hot), ctx())["rules"] if x[0].startswith("Ikke strukket"))
    assert st[1] is True and "unntatt" in st[2]


def test_tt_still_needs_price_confirmation_fresh_and_no_flags():
    r = C.classify(_tt(stats={"close": 95.0}), ctx())
    assert r["category"] == "watch" and "kurs under 50-dagerssnittet" in r["reason"] and "én uavhengig" not in r["reason"]
    r = C.classify(_tt(stats={"ret_20d": -0.05}), ctx())
    assert r["category"] == "watch" and "svakere enn" in r["reason"]
    assert C.classify(_tt(dec={"last_earnings": OLD}), ctx())["category"] != "kjop"
    assert C.classify(_tt(stats={"maxdd20": -0.3}), ctx())["category"] == "watch"


def test_tt_display(tmp_path):
    from signaltool import site
    from signaltool.config import PEAD_TT_BADGE, PEAD_TT_CAVEAT
    e = _tt(); r = C.classify(e, ctx())
    e.update(category=r["category"], cat_reason=r["reason"], cat_rules=r["rules"], cat_types=r["types"], cat_via_tt=r["via_tt"])
    assert "· 1 type: sterk rapport" in site.cat_cell(e)
    h = site.cat_rules_html(e)
    assert "via Sterk rapport + reaksjon" in h and PEAD_TT_CAVEAT.replace("&", "&amp;") in h and "…eller ⚑ sterk rapport" in h
    assert PEAD_TT_BADGE.replace("&", "&amp;") in site.tt_row(e)
