"""AnalBot 16.11: GS bruker kursens eget tidspunkt (is_close_own); papirbøker beholder is_close (loggetid).
Kjedevakt: startkurs dag t == sluttkurs dag t-1, ellers RebuildStopped / gs_chain_break."""
import json

import pytest

from signaltool import close_valid as CV
from signaltool import gs_index as G


def test_is_close_still_uses_log_time_for_books():
    """Relogg neste morgen av en intradagkurs: is_close (loggetid) er True – bøker/Siden uendret."""
    assert not CV.is_close("SCATC.OL", "2026-11-05", "2026-11-05T13:14:26+00:00")
    assert CV.is_close("SCATC.OL", "2026-11-05", "2026-11-06T12:58:37+00:00")


def test_is_close_own_uses_first_seen_not_relog():
    times = {"SCATC.OL": [
        ("2026-11-05", 88.3, "2026-11-05T13:14:26+00:00", "2026-11-05"),
        ("2026-11-05", 88.3, "2026-11-06T12:58:37+00:00", "2026-11-06"),
    ]}
    assert CV.first_seen(times, "SCATC.OL", "2026-11-05", 88.3) == "2026-11-05T13:14:26+00:00"
    assert not CV.is_close_own("SCATC.OL", "2026-11-05", 88.3, times)
    # ekte sluttkurs først logget neste morgen: godtas
    later = {"A.OL": [("2026-11-06", 99.5, "2026-11-08T11:57:00+00:00", "2026-11-08")]}
    assert CV.is_close_own("A.OL", "2026-11-06", 99.5, later)


def test_gs_closed_logged_drops_stale_relog_of_intraday():
    times = {"A.OL": [
        ("2026-11-06", 98.4, "2026-11-06T12:58:00+00:00", "2026-11-06"),
        ("2026-11-06", 98.4, "2026-11-08T11:57:00+00:00", "2026-11-08"),  # samme intradag-tall relogget
        ("2026-11-06", 99.5, "2026-11-08T11:57:00+00:00", "2026-11-08"),
    ]}
    rs = [
        {"date": "2026-11-06", "ticker": "A.OL", "price": "98.4", "price_date": "2026-11-06"},
        {"date": "2026-11-08", "ticker": "A.OL", "price": "98.4", "price_date": "2026-11-06"},
        {"date": "2026-11-08", "ticker": "A.OL", "price": "99.5", "price_date": "2026-11-06"},
    ]
    out = G.closed_logged(rs, times)
    assert [r["price"] for r in out] == ["", "", "99.5"]


def test_chain_break_stops_and_logs_dq(tmp_path):
    days = ["2026-10-01", "2026-10-02", "2026-10-03"]
    lists = {"2026-09-30": {"A.OL": {"ticker": "A.OL", "category": "watch", "flags": ""}}}
    # par 01->02 bruker logg 10 og 11; par 02->03 bruker yahoo 10.5 og 11 (start 02 ≠ slutt 11)
    logp = {"A.OL": {"2026-10-01": (10.0, False), "2026-10-02": (11.0, False)}}
    yfp = {"A.OL": {"2026-10-01": 10.0, "2026-10-02": 10.5, "2026-10-03": 11.0}}
    exch = {"A.OL": "oslo"}
    idx = {"OSEBX.OL": {d: 100.0 for d in days}}
    dq = tmp_path / "dq.jsonl"
    with pytest.raises(G.RebuildStopped, match="brudd i GS-kjeden"):
        G.check_chain_prices(lists, days, logp, yfp, exch, idx, dq_path=dq)
    fl = [json.loads(l) for l in dq.read_text().splitlines()]
    assert fl and fl[0]["type"] == "gs_chain_break" and fl[0]["ticker"] == "A.OL"
    assert fl[0]["date"] == "2026-10-02"


def test_chain_ok_when_same_series():
    days = ["2026-10-01", "2026-10-02", "2026-10-03"]
    lists = {"2026-09-30": {"A.OL": {"ticker": "A.OL", "category": "watch", "flags": ""}}}
    yfp = {"A.OL": {"2026-10-01": 10.0, "2026-10-02": 10.5, "2026-10-03": 11.0}}
    G.check_chain_prices(lists, days, {}, yfp, {"A.OL": "oslo"}, {"OSEBX.OL": {d: 100.0 for d in days}})
