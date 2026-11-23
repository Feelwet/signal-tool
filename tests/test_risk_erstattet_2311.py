"""AnalBot 23.11: erstattet=1 i risk_levels.csv filtreres bort; én rad per ticker, marked og ISO-uke."""
from __future__ import annotations

from signaltool import risk


def test_one_row_per_ticker_market_isoweek_after_filter():
    """Sjekker hele fila, uten hardkodet antall. Feiler hvis et nytt ukes-duplikat ikke er merket."""
    rows = risk.read_log()
    seen = {}
    for r in rows:
        t, mk, d = (r.get("ticker") or "").strip(), (r.get("market") or "").strip(), (r.get("date") or "").strip()
        if not (t and mk and d):
            continue
        key = (t, mk, risk.iso_week(d))
        assert key not in seen, f"to aktive rader i samme uke: {key} ({seen[key]} og {d})"
        seen[key] = d


def test_replaced_rows_are_kept_and_dominated():
    """erstattet=1 slettes ikke, og hver merket rad har en senere aktiv rad i samme uke og marked."""
    all_rows = risk.read_log(include_replaced=True)
    active = {(r["ticker"], r["market"], risk.iso_week(r["date"])): r["date"]
              for r in risk.read_log()}
    n_rep = 0
    for r in all_rows:
        if not risk.replaced(r):
            continue
        n_rep += 1
        key = (r["ticker"], r["market"], risk.iso_week(r["date"]))
        assert key in active, f"erstattet rad uten aktiv etterfølger: {r['ticker']} {r['date']}"
        assert r["date"] < active[key]
    assert len(all_rows) >= len(risk.read_log())
    if n_rep:
        assert len(all_rows) > len(risk.read_log())


def test_log_marks_older_same_week_and_keeps_row(tmp_path, monkeypatch):
    p = tmp_path / "risk_levels.csv"
    monkeypatch.setattr(risk, "LPATH", p)
    risk._log({"FOO.OL": {"date": "2026-11-19", "market": "Oslo", "comp": 0.5,
                          "level": "Middels", "in_universe": 1}})
    risk._log({"FOO.OL": {"date": "2026-11-20", "market": "Oslo", "comp": 0.6,
                          "level": "Høy", "in_universe": 1}})
    all_rows = risk.read_log(p, include_replaced=True)
    assert len(all_rows) == 2
    by_date = {r["date"]: r for r in all_rows}
    assert by_date["2026-11-19"]["erstattet"] == "1"
    assert by_date["2026-11-19"]["level"] == "Middels"
    assert by_date["2026-11-20"]["erstattet"] == "0"
    assert by_date["2026-11-20"]["level"] == "Høy"
    active = risk.read_log(p)
    assert len(active) == 1 and active[0]["date"] == "2026-11-20"
    # samme (date, ticker) skrives ikke på nytt
    risk._log({"FOO.OL": {"date": "2026-11-20", "market": "Oslo", "comp": 0.9,
                          "level": "Lav", "in_universe": 1}})
    assert len(risk.read_log(p, include_replaced=True)) == 2
    assert risk.read_log(p)[0]["level"] == "Høy"


def test_log_marks_new_row_when_older_than_existing_same_week(tmp_path, monkeypatch):
    p = tmp_path / "risk_levels.csv"
    monkeypatch.setattr(risk, "LPATH", p)
    risk._log({"FOO.OL": {"date": "2026-11-20", "market": "Oslo", "comp": 0.6,
                          "level": "Høy", "in_universe": 1}})
    risk._log({"FOO.OL": {"date": "2026-11-19", "market": "Oslo", "comp": 0.5,
                          "level": "Middels", "in_universe": 1}})
    all_rows = risk.read_log(p, include_replaced=True)
    assert len(all_rows) == 2
    by_date = {r["date"]: r for r in all_rows}
    assert by_date["2026-11-19"]["erstattet"] == "1"
    assert by_date["2026-11-20"]["erstattet"] == "0"
    active = risk.read_log(p)
    assert [r["date"] for r in active] == ["2026-11-20"]


def test_log_does_not_mark_other_weeks_or_markets(tmp_path, monkeypatch):
    p = tmp_path / "risk_levels.csv"
    monkeypatch.setattr(risk, "LPATH", p)
    risk._log({"FOO.OL": {"date": "2026-11-13", "market": "Oslo", "comp": 0.4,
                          "level": "Lav", "in_universe": 1}})
    risk._log({
        "FOO.OL": {"date": "2026-11-20", "market": "Oslo", "comp": 0.6, "level": "Høy", "in_universe": 1},
        "AAPL": {"date": "2026-11-20", "market": "US", "comp": 0.5, "level": "Middels", "in_universe": 1},
    })
    rows = risk.read_log(p, include_replaced=True)
    assert len(rows) == 3
    assert all(r["erstattet"] == "0" for r in rows)
    assert len(risk.read_log(p)) == 3
