"""AnalBot 27.11: siste bar på siden = close_date i learn_raw for samme kjøring, uten hardkodede antall.

Fanger JACK-scenariet der to kall gir ulik siste bar (første 25.11, senere 26.11), og det motsatte
der siden ville vist 26.11 (ufiltrert siste bar) og learn_raw 25.11 (kun lukkede barer).
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from signaltool import learnloop as L
from signaltool import shared_closes as SC
from signaltool.site import _last_closed, _gen_time

import pytest
from signaltool import freshness as FR


@pytest.fixture(autouse=True)
def _ingen_skriving_til_price_source(monkeypatch, tmp_path):
    """Tester skal ikke røre logs/price_source.csv."""
    monkeypatch.setattr(FR, "write_price_source", lambda *a, **k: 0)
    monkeypatch.setattr(SC.FR, "write_price_source", lambda *a, **k: 0)


OSLO = ZoneInfo("Europe/Oslo")


def at(y, m, d, h, mi):
    return dt.datetime(y, m, d, h, mi, tzinfo=OSLO)


def _frame(last: str, close: float = 6.25, n: int = 70, extra: dict | None = None) -> pd.DataFrame:
    days = [str(d.date()) for d in pd.bdate_range(end=last, periods=n)]
    px = {d: close for d in days}
    if extra:
        # ekstra barer (nyere dato enn `last`, eller overstyrte kurs)
        px.update({str(k)[:10]: float(v) for k, v in extra.items()})
        days = sorted(px)
    idx = pd.to_datetime(days)
    return pd.DataFrame({"Close": [px[str(d.date())] for d in idx], "Volume": [10_000] * len(idx)}, index=idx)


def _snap(tickers: dict[str, dict], day="2026-11-27", generated="2026-11-27 02:07"):
    return {
        "date": day,
        "generated": generated,
        "tickers": [
            {"ticker": t, "score": 1.0, "points": {"x": 1.0},
             "stats": {"close": v["close"], "last_date": v["last_date"],
                       "ret_5d": 0.0, "ret_20d": 0.0}}
            for t, v in tickers.items()
        ],
    }


def _record(tmp_path, monkeypatch, snap, frames, now):
    for n in ("RAW", "EXITS", "DQ"):
        monkeypatch.setattr(L, n, tmp_path / f"{n}.csv")
    monkeypatch.setattr(L, "CAT_LOG", tmp_path / "c.csv")
    L.record(snap, snap["tickers"], snap["date"], frames=frames, now=now)
    return list(csv.DictReader((tmp_path / "RAW.csv").open()))


def _site_last(e, gen, frames=None):
    px = SC.as_pairs(frames) if frames is not None else {}
    return _last_closed(e, px or None, gen)


def test_siste_bar_lik_close_date_uten_hardkodet_antall(tmp_path, monkeypatch):
    """For hver ticker i kjøringen er sidens siste bar lik learn_raw.close_date. Antall er ikke hardkodet."""
    now = at(2026, 11, 27, 2, 20)
    # flere tickere, ulike siste lukkede dager — listen er ikke et fasit-antall
    specs = {
        "JACK.OL": ("2026-11-26", 6.26),
        "EQNR.OL": ("2026-11-26", 240.0),
        "KOG.OL": ("2026-11-25", 300.0),
        "DNB.OL": ("2026-11-26", 270.0),
        "NEL.OL": ("2026-11-24", 2.50),
    }
    frames = {t: _frame(last, close) for t, (last, close) in specs.items()}
    snap = _snap({t: {"last_date": "1900-01-01", "close": 0.0} for t in specs})  # bevisst feil før prepare
    SC.prepare(snap, frames, now=now, refetch=lambda *a, **k: {}, meta=lambda *a, **k: None)
    raw = _record(tmp_path, monkeypatch, snap, frames, now)
    gen = _gen_time(snap)
    by = {r["ticker"]: r for r in raw}
    checked = 0
    for e in snap["tickers"]:
        t = e["ticker"]
        side_d = str((e.get("stats") or {}).get("last_date") or "")[:10]
        kurs, dato = _site_last(e, gen, frames)
        learn = by[t]
        assert side_d == learn["close_date"] == str(dato)[:10], (t, side_d, learn["close_date"], dato)
        assert abs(float(e["stats"]["close"]) - float(learn["close"])) < 1e-6
        assert abs(float(kurs) - float(learn["close"])) < 1e-6
        checked += 1
    assert checked == len(by) == len(snap["tickers"])
    assert checked > 1


def test_jack_to_kall_ulik_siste_bar_endres_til_felles(tmp_path, monkeypatch):
    """Første kall slutter 25.11; et senere kall ville gitt 26.11. Felles repair gir samme bar for side og learn_raw.

    learnloop._closes skal ikke kalles når rammer er gitt.
    """
    now = at(2026, 11, 27, 2, 20)  # fredag; 26.11 er lukket, expected_session = 26.11
    first = _frame("2026-11-25", 6.25)
    later = _frame("2026-11-26", 6.26)
    assert str(first.index[-1].date()) == "2026-11-25"
    assert str(later.index[-1].date()) == "2026-11-26"

    calls = []

    def _closes(tickers, period="2y"):
        calls.append(list(tickers))
        return {"JACK.OL": {str(k.date()): float(v) for k, v in later["Close"].items()}}

    monkeypatch.setattr(L, "_closes", _closes)

    def refetch(tickers, start, now):
        return {t: later.copy() for t in tickers if t == "JACK.OL"}

    frames = {"JACK.OL": first.copy()}
    snap = _snap({"JACK.OL": {"last_date": "2026-11-25", "close": 6.25}})
    # før repair: siden (stats) 25.11, et senere _closes ville gitt 26.11
    assert snap["tickers"][0]["stats"]["last_date"] == "2026-11-25"

    SC.prepare(snap, frames, now=now, refetch=refetch, meta=lambda *a, **k: None)
    raw = _record(tmp_path, monkeypatch, snap, frames, now)

    assert calls == [], "learnloop skal ikke laste ned selv når rammer finnes"
    st = snap["tickers"][0]["stats"]
    row = raw[0]
    gen = _gen_time(snap)
    kurs, dato = _site_last(snap["tickers"][0], gen, frames)
    assert st["last_date"] == row["close_date"] == "2026-11-26" == str(dato)[:10]
    assert abs(float(st["close"]) - 6.26) < 1e-9
    assert abs(float(row["close"]) - 6.26) < 1e-9
    assert abs(float(kurs) - 6.26) < 1e-9
    assert st.get("shared_closed") is True


def test_motsatt_side_26_learn_25_rettes_til_lukket_bar(tmp_path, monkeypatch):
    """Motsatt JACK-tilfelle: ticker_stats ville tatt 26.11 (siste bar, ikke lukket);
    learn_raw med closedbars ville tatt 25.11. Felles serie gir 25.11 for begge."""
    now = at(2026, 11, 26, 15, 0)  # torsdag før stengetid: 26.11 er ikke lukket
    # ramme med uåpnet 26.11-bar oppå lukket 25.11
    base = _frame("2026-11-25", 6.25, extra={"2026-11-26": 6.26})
    assert str(base.index[-1].date()) == "2026-11-26"
    from signaltool.collectors.markets import ticker_stats
    raw_stats = ticker_stats(base)
    assert raw_stats["last_date"] == "2026-11-26"  # slik siden ville vist uten closedbars-filter

    frames = {"JACK.OL": base.copy()}
    snap = _snap({"JACK.OL": {"last_date": "2026-11-26", "close": 6.26}},
                 day="2026-11-26", generated="2026-11-26 15:00")
    closes_calls = []
    monkeypatch.setattr(L, "_closes", lambda *a, **k: closes_calls.append(a) or {})

    SC.prepare(snap, frames, now=now, refetch=lambda *a, **k: {}, meta=lambda *a, **k: None)
    raw = _record(tmp_path, monkeypatch, snap, frames, now)

    assert closes_calls == []
    st = snap["tickers"][0]["stats"]
    row = raw[0]
    gen = _gen_time(snap)
    kurs, dato = _site_last(snap["tickers"][0], gen, frames)
    assert st["last_date"] == row["close_date"] == "2026-11-25" == str(dato)[:10]
    assert abs(float(st["close"]) - 6.25) < 1e-9
    assert abs(float(row["close"]) - 6.25) < 1e-9
    assert abs(float(kurs) - 6.25) < 1e-9
    # 26.11-baren er borte fra den felles serien
    assert str(frames["JACK.OL"].index[-1].date()) == "2026-11-25"


def test_learnloop_laster_ikke_ned_nar_rammer_finnes(tmp_path, monkeypatch):
    now = at(2026, 11, 27, 2, 20)
    frames = {"EQNR.OL": _frame("2026-11-26", 240.0)}
    snap = _snap({"EQNR.OL": {"last_date": "2026-11-26", "close": 240.0}})
    calls = []
    monkeypatch.setattr(L, "_closes", lambda *a, **k: calls.append(a) or {})
    SC.prepare(snap, frames, now=now, refetch=lambda *a, **k: {}, meta=lambda *a, **k: None)
    # en ticker som mangler i rammene skal heller ikke utløse nedlasting
    snap["tickers"].append({"ticker": "MISSING.OL", "score": 1.0, "points": {"x": 1.0},
                            "stats": {"close": 1.0, "last_date": "2026-11-26"}})
    _record(tmp_path, monkeypatch, snap, frames, now)
    assert calls == []


def test_pipeline_kjører_repair_før_learnloop_og_merger_extra():
    src = Path("signaltool/pipeline.py").read_text()
    assert "mdata.update(ed)" in src
    assert "all_frames=True" in src
    assert "shared_closes" in src
    i_prep = src.index("SC.prepare")
    i_rec = src.index("n = learnloop.record")
    assert i_prep < i_rec
    # site.build ligger i cli etter pipeline.run, som returnerer snap med oppdatert stats
    cli = Path("signaltool/cli.py").read_text()
    assert "site.build(snap)" in cli
    assert "SC.prepare" not in Path("signaltool/learnloop.py").read_text()
