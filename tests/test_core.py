import math
from datetime import date
import numpy as np
import pandas as pd
import pytest

from signaltool import anomaly
from signaltool.themes import THEMES, match_themes, all_watch_tickers
from signaltool.collectors import congress, ofac, sec, macro, calendar_cb
from signaltool.backtest.common import fwd_returns, summarize


def test_robust_z_detects_spike():
    s = pd.Series([10, 11, 9, 10, 12, 10, 9, 11, 10, 10, 11, 9, 10, 10, 11, 30.0])
    z, info = anomaly.robust_z(s, recent_n=1, baseline_n=15, min_baseline=10)
    assert z > 5 and info["n_baseline"] == 15


def test_robust_z_short_series_is_nan():
    z, _ = anomaly.robust_z(pd.Series([1, 2, 3]), recent_n=1, baseline_n=60)
    assert math.isnan(z)


def test_weighted_positive_score_ignores_negative_and_nan():
    comp = {"a": {"score": 3.0, "weight": 1}, "b": {"score": -2.0, "weight": 1}, "c": {"score": float("nan"), "weight": 5}}
    assert anomaly.weighted_positive_score(comp) == pytest.approx(1.5)


def test_themes_complete():
    keys = [t.key for t in THEMES]
    assert len(keys) == len(set(keys)) >= 10
    for t in THEMES:
        assert t.reasoning and t.keywords and t.all_tickers and t.escalation and t.risks
    assert "KOG.OL" in all_watch_tickers() and "EQNR.OL" in all_watch_tickers()


def test_match_themes():
    assert "mideast_energy" in match_themes("Iran threatens to close Strait of Hormuz")
    assert "shipping_chokepoints" in match_themes("Houthi attack on container ship in Red Sea")
    assert match_themes("Local bakery wins award") == []


def test_parse_ptr_text():
    txt = """
                      Netflix, Inc. - Common Stock (NFLX)    P              08/12/2026 09/01/2026        $1,001 - $15,000
                      [ST]
                      F      S     : New


                      Howmet Aerospace Inc. Common           S (partial)    08/11/2026 09/01/2026        $1,001 - $15,000
                      Stock (HWM) [ST]
"""
    rows = congress.parse_ptr_text(txt)
    assert [(r["ticker"], r["type"]) for r in rows] == [("NFLX", "P"), ("HWM", "S")]
    assert rows[0]["asset_type"] == "ST" and rows[0]["amount"].startswith("$1,001")


def test_ofac_parse():
    html = ('<div><div class="x"><a href="/recent-actions/20260917" hreflang="en">Iran-related Designations; Belarus-related Designations Removals</a>'
            '</div></div><div><div class="y">September 17, 2026 - ')
    rows = ofac.parse(html)
    assert rows[0]["date"] == pd.Timestamp("2026-09-17") and "Iran" in rows[0]["title"]


def test_parse_form4():
    xml = b"""<ownershipDocument><issuer><issuerCik>1</issuerCik><issuerName>ACME</issuerName><issuerTradingSymbol>acme</issuerTradingSymbol></issuer>
    <reportingOwner><reportingOwnerId><rptOwnerName>Doe John</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>1</isDirector></reportingOwnerRelationship></reportingOwner>
    <nonDerivativeTable><nonDerivativeTransaction><transactionDate><value>2026-09-20</value></transactionDate>
    <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
    <transactionAmounts><transactionShares><value>1000</value></transactionShares><transactionPricePerShare><value>12.5</value></transactionPricePerShare>
    <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts></nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>"""
    tx = sec.parse_form4(xml)
    assert tx[0]["ticker"] == "ACME" and tx[0]["code"] == "P" and tx[0]["shares"] * tx[0]["price"] == 12500
    df = pd.DataFrame([dict(tx[0], owner="A", url="u", file_date="2026-09-21"), dict(tx[0], owner="B", url="u", file_date="2026-09-22")])
    cl = sec.insider_buy_clusters(df, min_insiders=2, min_value=10_000)
    assert bool(cl.iloc[0]["cluster"]) and cl.iloc[0]["n_insiders"] == 2


def test_period_parsing():
    assert macro._period_to_ts("2026M08") == pd.Timestamp(2026, 8, 1)
    assert macro._period_to_ts("2026 AUG") == pd.Timestamp(2026, 8, 1)
    assert macro._period_to_ts("2026U38").year == 2026


def test_jsonstat2_series():
    j = {"id": ["A", "Tid"], "size": [1, 3], "value": [1.0, 2.0, 3.0],
         "dimension": {"A": {"category": {"index": {"x": 0}}}, "Tid": {"category": {"index": {"2026M01": 0, "2026M02": 1, "2026M03": 2}}}}}
    s = macro.jsonstat2_series(j)
    assert list(s.values) == [1.0, 2.0, 3.0]


def test_ics_parse_timezones():
    ics = "BEGIN:VEVENT\nDTSTART;VALUE=DATE-TIME:20260930T123000Z\nSUMMARY:GDP\nEND:VEVENT\nBEGIN:VEVENT\nDTSTART;TZID=US-Eastern:20261002T083000\nSUMMARY:Employment Situation\nEND:VEVENT"
    ev = macro._parse_ics(ics, "X")
    assert ev[0]["time"] == "14:30" and ev[1]["time"] == "14:30"  # both 08:30 ET -> 14:30 Oslo (CEST)


def test_fomc_ecb_parse():
    fed = '<a id="1">2026 FOMC Meetings</a><div class="fomc-meeting__month x"><strong>October</strong></div><div class="fomc-meeting__date y">27-28</div>'
    assert calendar_cb.fomc(fed)[0]["date"] == "2026-10-28"
    ecb = "<dt> \n29/10/2026\n</dt>\n<dd>        \nGoverning Council of the ECB: monetary policy meeting in Frankfurt (Day 2), followed by press conference<br>"
    assert calendar_cb.ecb(ecb)[0]["date"] == "2026-10-29"


def test_fwd_returns_no_lookahead():
    idx = pd.bdate_range("2026-01-01", periods=30)
    close = pd.Series(np.arange(100, 130, dtype=float), index=idx)
    fr = fwd_returns(close, [idx[5]], horizons=(5,), entry_lag=1)
    assert fr["entry_date"].iloc[0] == idx[5]
    assert fr["r5"].iloc[0] == pytest.approx(110 / 105 - 1)
    s = summarize(pd.Series([0.01, 0.02, -0.01]))
    assert s["n"] == 3 and 0 < s["hit"] < 1
