"""AnalBot 16.11: en ticker som mangler data i ombyggingen stopper hele ombyggingen og logges i dq_flags.
Hentehullet 16.11: yf.download i batch ga stille tomme kolonner (AKRBP.OL, OKTA, CRWD) -> enkeltvis nytt forsøk."""
import json

import pandas as pd
import pytest

from signaltool import gs_index as G


def _df(series: dict):
    idx = pd.to_datetime(["2026-11-09", "2026-11-10"])
    cols = pd.MultiIndex.from_tuples([("Close", t) for t in series])
    return pd.DataFrame({("Close", t): v for t, v in series.items()}, index=idx, columns=cols)


def test_batch_hole_is_refetched_one_by_one():
    calls = []

    def dl(tks, **kw):
        calls.append(list(tks))
        if len(tks) > 1:   # batch: OKTA kommer tom tilbake (stille feil)
            return _df({t: ([1.0, 1.1] if t != "OKTA" else [float("nan")] * 2) for t in tks})
        return _df({tks[0]: [2.0, 2.2]})
    out = G._yf(["CRWD", "OKTA"], "2026-09-20", pause=0, download=dl)
    assert out["OKTA"] == {"2026-11-09": 2.0, "2026-11-10": 2.2}
    assert calls[1:] == [["OKTA"]]


def test_still_missing_after_retries_is_absent():
    def dl(tks, **kw):
        return _df({t: ([1.0, 1.1] if t == "CRWD" else [float("nan")] * 2) for t in tks})
    out = G._yf(["CRWD", "OKTA"], "2026-09-20", retries=2, pause=0, download=dl)
    assert "OKTA" not in out and "CRWD" in out


def test_missing_check_stops_on_ticker_that_had_a_price_but_not_on_never_priced():
    rows = [{"ticker": "AKRBP.OL", "price": "350.0"}, {"ticker": "SFLN.OL", "price": ""}]
    idx = {k: {"2026-11-10": 1.0} for k in G.IDX.values()}
    stop, nosrc = G.missing_check(["AKRBP.OL", "SFLN.OL", "EQNR.OL"], {"EQNR.OL": {"x": 1}}, rows, idx)
    assert stop == ["AKRBP.OL"] and nosrc == ["SFLN.OL"]
    idx.pop("^IXIC")
    stop, _ = G.missing_check([], {}, rows, idx)
    assert stop == ["^IXIC"]


def test_build_stops_logs_dq_and_leaves_index_untouched(tmp_path, monkeypatch):
    cat = tmp_path / "categories.csv"
    cat.write_text("date,ticker,category,rangert,price,price_date\n"
                   "2026-11-09,AKRBP.OL,watch,1,350.0,2026-11-09\n2026-11-09,EQNR.OL,watch,1,250.0,2026-11-09\n")
    out = tmp_path / "gs_index.csv"
    out.write_bytes(b"date,gs_index\r\n2026-11-10,97.0250\r\n")
    before = out.read_bytes()
    dq = tmp_path / "dq_flags.jsonl"

    def fake(tks, start, **kw):
        return {t: {"2026-11-09": 1.0, "2026-11-10": 1.0} for t in tks if t != "AKRBP.OL"}
    monkeypatch.setattr(G, "_yf", fake)
    monkeypatch.setattr("signaltool.source_health.excluded", lambda: set())
    with pytest.raises(G.RebuildStopped):
        G.build(out_path=out, cat_path=cat, corr_path=None, dq_path=dq)
    assert out.read_bytes() == before
    fl = [json.loads(l) for l in dq.read_text().splitlines()]
    assert [(f["ticker"], f["type"]) for f in fl] == [("AKRBP.OL", "gs_rebuild_missing")]
    # samme dag igjen: ikke dobbeltlogget
    with pytest.raises(G.RebuildStopped):
        G.build(out_path=out, cat_path=cat, corr_path=None, dq_path=dq)
    assert len(dq.read_text().splitlines()) == 1


def test_run_reports_stop_in_status(monkeypatch):
    def boom(**kw):
        raise G.RebuildStopped("mangler data for OKTA")
    monkeypatch.setattr(G, "build", boom)
    st = {}
    G.run(st)
    assert st["GS-indeks (intern)"].startswith("STOPPET")
