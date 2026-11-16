"""AnalBot 16.11: GS-indeksen skal bruke én kurstype (justert sluttkurs) for nivå og avkastning."""
import json
from pathlib import Path

import pandas as pd
import pytest

from signaltool import gs_index as G

ROOT = Path(__file__).resolve().parents[1]


def test_price_type_is_adj_close():
    assert G.PRICE_TYPE == "adj_close"


def test_price_kind_god_dividend():
    # 02.10: logg 15,9 = ujustert Close; Yahoo Adj Close 14,0724 (utbytte 2,00 ekskl. 16.10)
    assert G.price_kind(15.9, close=15.9, adj=14.0724) == "close"
    # 15.10: logg 15,4 = justert (Close var 17,4)
    assert G.price_kind(15.4, close=17.4, adj=15.4) == "adj_close"
    # etter ekskl.: Close og Adj Close er like
    assert G.price_kind(15.2, close=15.2, adj=15.2) == "both"
    assert G.price_kind(15.9, close=15.7, adj=13.8954) is None  # intradag 05.10


def test_logged_unadjusted_dropped_adj_kept():
    logp = {"GOD.OL": {"2026-10-14": (17.4, False), "2026-10-15": (15.4, False), "2026-10-16": (15.2, False)}}
    close_px = {"GOD.OL": {"2026-10-14": 17.4, "2026-10-15": 17.4, "2026-10-16": 15.2}}
    adj_px = {"GOD.OL": {"2026-10-14": 15.4, "2026-10-15": 15.4, "2026-10-16": 15.2}}
    kept, rej = G.logged_prices_of_type(logp, close_px, adj_px)
    assert set(kept["GOD.OL"]) == {"2026-10-15", "2026-10-16"}
    assert {x["date"] for x in rej} == {"2026-10-14"}
    assert rej[0]["price_type"] == "close"


def test_check_price_types_stops_and_logs_dq(tmp_path):
    dq = tmp_path / "dq.jsonl"
    with pytest.raises(G.RebuildStopped, match="ulik kurstype"):
        G.check_price_types("adj_close", {"close"}, dq, date="2026-11-16")
    fl = [json.loads(l) for l in dq.read_text().splitlines()]
    assert len(fl) == 1
    assert fl[0]["type"] == "gs_price_type_mismatch"
    assert fl[0]["level_type"] == "adj_close"
    assert "close" in fl[0]["return_types"]
    # samme nøkkel logges ikke to ganger
    with pytest.raises(G.RebuildStopped):
        G.check_price_types("adj_close", {"close"}, dq, date="2026-11-16")
    assert len(dq.read_text().splitlines()) == 1


def test_check_price_types_allows_same_and_both():
    G.check_price_types("adj_close", {"adj_close"})
    G.check_price_types("adj_close", {"adj_close", "both"})
    G.check_price_types("adj_close", {"both"})


def test_record_price_type_once(tmp_path):
    dq = tmp_path / "dq.jsonl"
    G.record_price_type(dq)
    G.record_price_type(dq)
    fl = [json.loads(l) for l in dq.read_text().splitlines()]
    assert len(fl) == 1
    assert fl[0]["type"] == "gs_price_type" and fl[0]["price_type"] == "adj_close"


def test_filtered_log_does_not_treat_dividend_as_loss():
    lists = {"2026-10-13": {"GOD.OL": {"ticker": "GOD.OL", "category": "watch", "flags": ""}}}
    days = ["2026-10-14", "2026-10-15"]
    exch = {"GOD.OL": "oslo"}
    idx = {"OSEBX.OL": {d: 100.0 for d in days}}
    yfp = {"GOD.OL": {"2026-10-14": 15.4, "2026-10-15": 15.4}}
    mixed = {"GOD.OL": {"2026-10-14": (17.4, False), "2026-10-15": (15.4, False)}}
    close_px = {"GOD.OL": {"2026-10-14": 17.4, "2026-10-15": 17.4}}
    kept, _ = G.logged_prices_of_type(mixed, close_px, yfp)
    r_bad = G.compute(lists, days, mixed, yfp, exch, idx)
    r_ok = G.compute(lists, days, kept, yfp, exch, idx)
    # dag 1: inngang 100, kostnad 0,2 % trekkes i rad 2. Ujustert 17,4 → justert 15,4 er et falskt 11,5 % tap.
    assert r_ok[1]["gs_index"] == pytest.approx(100 * (1 - 0.002))
    assert r_bad[1]["gs_index"] == pytest.approx(100 * (15.4 / 17.4) * (1 - 0.002))


def _df(series, fields=("Close",)):
    idx = pd.to_datetime(["2026-10-02", "2026-10-15"])
    cols = pd.MultiIndex.from_tuples([(f, t) for f in fields for t in series])
    data = {}
    for t, vals in series.items():
        for f, arr in vals.items():
            data[(f, t)] = arr
    return pd.DataFrame(data, index=idx, columns=cols)


def test_yf_default_is_auto_adjust_true():
    calls = []

    def dl(tks, **kw):
        calls.append(kw.get("auto_adjust"))
        return _df({t: {"Close": [1.0, 1.1]} for t in tks})

    out = G._yf(["CRWD"], "2026-09-20", pause=0, download=dl)
    assert calls == [True]
    assert out["CRWD"]["2026-10-02"] == 1.0


def test_yf_unadj_out_returns_adj_close():
    def dl(tks, **kw):
        assert kw.get("auto_adjust") is False
        return _df({t: {"Close": [15.9, 17.4], "Adj Close": [14.0724, 15.4]} for t in tks},
                   fields=("Close", "Adj Close"))

    unadj = {}
    out = G._yf(["GOD.OL"], "2026-09-20", pause=0, download=dl, unadj_out=unadj)
    assert out["GOD.OL"]["2026-10-02"] == pytest.approx(14.0724)
    assert unadj["GOD.OL"]["2026-10-02"] == pytest.approx(15.9)
    assert out["GOD.OL"]["2026-10-15"] == pytest.approx(15.4)


def test_build_stops_on_mixed_types_and_leaves_index(tmp_path, monkeypatch):
    cat = tmp_path / "categories.csv"
    cat.write_text("date,ticker,category,rangert,price,price_date\n"
                   "2026-11-09,EQNR.OL,watch,1,250.0,2026-11-09\n")
    out = tmp_path / "gs_index.csv"
    out.write_bytes(b"date,gs_index\r\n2026-11-10,97.0250\r\n")
    before = out.read_bytes()
    dq = tmp_path / "dq_flags.jsonl"

    def fake(tks, start, **kw):
        ser = {t: {"2026-11-09": 1.0, "2026-11-10": 1.0} for t in tks}
        if kw.get("unadj_out") is not None:
            kw["unadj_out"].update(ser)
        return ser

    monkeypatch.setattr(G, "_yf", fake)
    monkeypatch.setattr("signaltool.source_health.excluded", lambda: set())
    monkeypatch.setattr(G, "closed_logged", lambda rows, times=None: rows)
    monkeypatch.setattr(G, "logged_prices_of_type", lambda logp, *a, **k: (logp, []))
    monkeypatch.setattr(G, "price_kind", lambda *a, **k: "close")
    with pytest.raises(G.RebuildStopped, match="ulik kurstype"):
        G.build(out_path=out, cat_path=cat, corr_path=None, dq_path=dq)
    assert out.read_bytes() == before
    fl = [json.loads(l) for l in dq.read_text().splitlines()]
    assert any(f["type"] == "gs_price_type_mismatch" for f in fl)
