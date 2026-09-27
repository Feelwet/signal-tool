"""Tests for the overnight additions: decision metrics, PEAD signal type, Oslo weak-momentum flag, Newsweb insider
classifier, briefing (focus / changes / alerts), scenarios, oil seasonal deviation, EIA parser, site rendering."""
import json
from datetime import date, timedelta
import numpy as np
import pandas as pd
from signaltool import categories as C, briefing, scenarios, site_extra as X
from signaltool.decision import price_metrics
from signaltool.collectors.newsweb_insider import classify
from signaltool.collectors.oil_nowcast import seasonal_dev
from tests.test_categories import cand, ctx, snap, two_ctx, TWO, FRESH, TODAY


def test_price_metrics_basic():
    idx = pd.bdate_range("2024-01-01", periods=300)
    c = pd.Series(np.linspace(100, 160, 300), index=idx)
    df = pd.DataFrame({"Close": c, "High": c * 1.01, "Low": c * 0.99})
    bench = pd.Series(np.linspace(100, 110, 300), index=idx)
    m = price_metrics(df, bench, None)
    assert abs(m["ret_20d"] - (160 / c.iloc[-21] - 1)) < 1e-3
    assert m["rel_bench_20d"] > 0 and m["pct_from_hi52"] == 0 and m["maxdd1y"] == 0
    assert m["stop_atr"] < m["close"] and m["sma50"] < m["close"]
    assert m["mom12_1"] is not None


def test_pead_counts_as_signal_type():
    e = cand(points={"dod_contract": 1.5}, dates={"gov_contract": FRESH})
    e["decision"] = {"pead": True, "last_earnings": FRESH, "eps_surprise": 22.0, "earn_reaction": 0.06}
    r = C.classify(e, ctx())
    assert "pead" in r["types"] and r["category"] == "kjop", r["reason"]


def test_oslo_weak_momentum_is_red_flag():
    e = cand("ABC.OL", points={"ose_contracts": 1.5}, dates={"ose_contract": FRESH})
    e["decision"] = {"weak_mom_oslo": True, "mom12_1": -0.3, "pead": False}
    r = C.classify(e, ctx())
    assert r["category"] == "watch" and any("momentum" in f for f in r["flags"])
    assert any(x[0].startswith("Oslo: ikke svak") and x[1] is False for x in r["rules"])
    # US tickers are never flagged
    e2 = cand(points=TWO, dates={"gov_contract": FRESH}); e2["decision"] = {"weak_mom_oslo": False, "mom12_1": -0.5}
    assert C.classify(e2, two_ctx())["category"] == "kjop"


def test_insider_classifier():
    assert classify("Ståle Rodahl, Chair of the Board, has on 26 August 2026 purchased 200,000 shares at an average price of NOK 8.34 per share.")["kind"] == "kjøp"
    k = classify("Jane Doe, CFO, has sold 37,556 shares in Instabank ASA at a price of NOK 4.97 per share.")
    assert k["kind"] == "salg" and k["shares"] == 37556
    assert classify("Følgende primærinnsidere har blitt allokert aksjer i forbindelse med lønnssubstitutt")["kind"] == "annet"
    assert classify("Grant of share options to management")["kind"] == "annet"
    assert classify("Please see the attachment for details.")["kind"] == "ukjent"
    assert classify("X sold 200,000 shares. The shares had been acquired in the private placement.")["kind"] == "salg"
    v = classify("CEO has purchased 71 450 shares at an average price of NOK 13.986 per share.")
    assert v["kind"] == "kjøp" and abs(v["value_nok"] - 71450 * 13.986) < 1


def test_seasonal_dev():
    idx = pd.date_range("2019-01-04", "2026-09-18", freq="W-FRI")
    s = pd.Series(100.0, index=idx); s.iloc[-1] = 90.0
    d = seasonal_dev(s)
    assert d["avg5y"] == 100.0 and abs(d["dev_pct"] + 0.10) < 1e-9 and d["chg_w"] == -10.0


def _snap(date_, tickers, themes=None, **kw):
    return {"date": date_, "tickers": tickers, "themes": themes or [], **kw}


def test_briefing_changes_and_focus(tmp_path):
    prev = _snap("2026-09-26", [{"ticker": "AAA", "category": "watch"}, {"ticker": "BBB", "category": "hold"}],
                 [{"key": "k", "name": "Tema", "score": 0.5}])
    (tmp_path / "2026-09-26.json").write_text(json.dumps(prev))
    cur = _snap("2026-09-27", [{"ticker": "AAA", "category": "kjop", "cat_reason": "to signaler", "decision": {"stop_atr": 9.0, "close": 10.0}},
                               {"ticker": "CCC", "category": "hold", "cat_reason": "strukket", "decision": {"days_to_earnings": 3, "next_earnings": "2026-09-30"}}],
                [{"key": "k", "name": "Tema", "score": 2.6, "components": {"a": {"score": 3.0, "label": "GDELT"}}}],
                chokepoints={"chokepoint6": {"name": "Hormuzstredet", "last_date": "2026-09-20", "alle": {"last7": 3.0, "yoy": -0.96, "z90": -1.0, "vs90": -0.1}},
                             "chokepoint4": {"name": "Bab el-Mandeb", "last_date": "2026-09-20", "alle": {"last7": 20.0, "yoy": -0.1, "z90": -3.0, "vs90": -0.3}},
                             "chokepoint2": {"name": "Panamakanalen", "last_date": "2026-09-20", "alle": {"last7": 30.0, "yoy": 0.0, "z90": -3.0, "vs90": -0.05}}})
    briefing.apply(cur, tmp_path)
    b = cur["briefing"]
    kinds = {c["kind"] for c in b["changes"]["items"]}
    assert b["changes"]["prev_date"] == "2026-09-26" and {"opp", "ny", "ut", "tema"} <= kinds
    assert b["focus"][0]["title"].startswith("Kjøp-kandidat: AAA") and "9.00" in b["focus"][0]["why"]
    lv = {a["title"].split(":")[0]: a["level"] for a in b["alerts"]}
    assert lv.get("Hormuzstredet") == "info" and lv.get("Bab el-Mandeb") == "alert" and "Panamakanalen" not in lv  # persistent / new drop / small dip
    assert any("kvartalsrapport" in a["title"] for a in b["alerts"])
    assert 3 <= len(b["focus"]) <= 5


def test_briefing_first_run(tmp_path):
    cur = _snap("2026-09-27", [])
    briefing.apply(cur, tmp_path)
    assert cur["briefing"]["changes"]["prev_date"] is None and "Første" in cur["briefing"]["changes"]["note"]


def test_scenarios_and_render():
    t = {"key": "mideast_energy", "name": "Midtøsten", "score": 2.5, "escalation": "opp", "deescalation": "ned",
         "tickers": [{"ticker": "BZ=F", "ret_20d": 0.08, "ret_5d": 0.02}], "polymarket": []}
    s = {"chokepoints": {"chokepoint6": {"name": "Hormuzstredet", "last_date": "2026-09-20", "alle": {"last7": 3.0, "yoy": -0.96, "z90": -2.5}}},
         "oil_nowcast": {"WCESTUS1": {"label": "Råolje", "dev_pct": -0.08, "last": 400, "week": 38}}}
    sc = scenarios.scenario(t, s)
    assert sc["base"] and sc["lean"] == "bull" and sc["n_bull"] >= 3
    h = X.scenario_html(t, s)
    assert "Bull" in h and "Hormuzstredet" in h and "heller mot" in h


def test_decision_html_and_verdict():
    e = {"ticker": "XYZ", "stats": {"adv20": 5e6}, "decision": {"close": 100.0, "sma50": 95.0, "stop_atr": 92.0, "pct_from_hi52": -0.01,
                                                             "rel_bench_60d": 0.25, "forwardPE": 55.0, "trailingPE": 70.0, "days_to_earnings": 5, "next_earnings": "2026-10-02"}}
    h = X.decision_html(e)
    assert "Allerede priset inn?" in h and "Ugyldiggjøring" in h and "92.00" in h and "priset inn" in h and "hendelsesrisiko" in h
    assert "Ingen kurs" in X.decision_html({"ticker": "Q"})


def test_focus_dedupes_same_ticker():
    from signaltool import briefing
    snap = {"tickers": [{"ticker": "DELL", "category": "hold", "cat_reason": "x"}], "themes": []}
    chg = {"items": [{"kind": "ny", "ticker": "DELL", "text": "DELL er ny på listen som Hold", "level": "info"}]}
    out = briefing.focus(snap, chg, [])
    assert sum(1 for i in out if i["link"] == "ticker/DELL") == 1


def test_insider_singular_share_not_holding():
    from signaltool.collectors.newsweb_insider import classify
    c = classify("On 22 September 2026, Kona BidCo AS acquired 1 share in Zalaris ASA at a price of NOK 100 per share through market purchase. "
                 "Following this Kona BidCo AS owns a total of 19,413,705 shares in the Company.")
    assert c["kind"] == "kjøp" and c["shares"] == 1 and c["value_nok"] == 100


def test_contract_filter_excludes_legal_and_share_awards():
    from signaltool.collectors.newsweb import NOT_CONTRACT
    assert NOT_CONTRACT.search("nordic mining asa: legal proceedings initiated by epc contractor")
    assert NOT_CONTRACT.search("subsea 7 s.a. announces details of share related awards")
    assert not NOT_CONTRACT.search("scana asa: scana company secures contract for e-house module")
