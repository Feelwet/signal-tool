"""AnalBot 11.11: papirbøkene, GS-indeksen, learn_raw og siste kurs i Siden-avkastningen bruker bare LUKKEDE barer
(stengetid + 30 min i børsens tidssone). Ventende fill til neste kjøring; ingen retting bakover; intradag-fills logget."""
import csv
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from signaltool import closedbars as CB, portfolio as P, portfolio_books as B

OSLO = ZoneInfo("Europe/Oslo")
R2 = B.BOOKS["hoy_risiko_v1"]


def at(y, m, d, h, mi):
    return dt.datetime(y, m, d, h, mi, tzinfo=OSLO)


def tk(t, close, d, cat="watch"):
    return {"ticker": t, "category": cat, "score": 1.0, "cat_flags": {}, "cat_types": {}, "decision": {"sector": "Energy"},
            "stats": {"close": close, "last_date": d, "ret_20d": 0.05}}


def rows(p):
    return list(csv.DictReader(p.open())) if p.exists() else []


HIST = {"SCANA.OL": {"2026-11-09": 1.40, "2026-11-10": 1.44, "2026-11-11": 1.47}}


def test_closedbars_rule_and_unknown_exchange():
    assert not CB.ok("SCANA.OL", "2026-11-11", at(2026, 11, 11, 16, 54)) and CB.ok("SCANA.OL", "2026-11-11", at(2026, 11, 11, 16, 55))
    assert CB.ok("RHM.DE", "2026-11-11", at(2026, 11, 11, 18, 0)) and not CB.ok("RHM.DE", "2026-11-11", at(2026, 11, 11, 17, 59))
    assert not CB.ok("X.ZZ", "2026-11-01", at(2026, 11, 11, 23, 0))
    assert CB.last(HIST["SCANA.OL"], "SCANA.OL", at(2026, 11, 11, 13, 0)) == (1.44, "2026-11-10")
    assert CB.last(HIST["SCANA.OL"], "SCANA.OL", at(2026, 11, 11, 17, 0)) == (1.47, "2026-11-11")


def test_closed_view_replaces_intraday_bar_and_flags_wait():
    snap = {"date": "2026-11-11", "generated": "2026-11-11 13:00", "tickers": [tk("SCANA.OL", 1.46, "2026-11-11"), tk("VRT", 180.0, "2026-11-10")]}
    v = P.closed_view(snap, now=at(2026, 11, 11, 13, 0), hist=lambda ts: {t: HIST.get(t, {}) for t in ts})
    assert v["SCANA.OL"] == (1.44, "2026-11-10", True)     # intradag 1,46 brukes aldri
    assert v["VRT"] == (180.0, "2026-11-10", False)         # US 10.11 lukket


def _go(tmp, day, close, d, now, picks=None, R=R2, name="t"):
    snap = {"date": day, "generated": now.strftime("%Y-%m-%d %H:%M"), "tickers": [tk("SCANA.OL", close, d)]}
    closed = P.closed_view(snap, now=now, hist=lambda ts: {t: HIST.get(t, {}) for t in ts})
    return P.step(snap, 10.0, {"osebx": 1.0, "spx": 1.0}, tmp / f"{name}.csv", tmp / f"{name}_n.csv", rules=R,
                  picks=picks if picks is not None else [], cols=B.B_COLS, annotate=B.annotator({}), closed=closed)


def test_pending_fill_waits_while_exchange_open_then_fills_at_close(tmp_path):
    # ordre 10.11 på signalets bar (10.11, intradag): fill krever en LUKKET bar etter 10.11
    _go(tmp_path, "2026-11-10", 1.43, "2026-11-10", at(2026, 11, 10, 13, 0), picks=[tk("SCANA.OL", 1.43, "2026-11-10")])
    o = [r for r in rows(tmp_path / "t.csv") if r["event"] == "order"]
    assert len(o) == 1 and o[0]["price_date"] == "2026-11-10"
    # 11.11 kl. 13: børsen åpen (intradag 1,46) -> VENTENDE, ingen fill, ingen kansellering
    s = _go(tmp_path, "2026-11-11", 1.46, "2026-11-11", at(2026, 11, 11, 13, 0))
    assert len(s["pending"]) == 1 and not [r for r in rows(tmp_path / "t.csv") if r["event"] in ("fill", "cancel")]
    # neste kjøring 12.11 kl. 13: 11.11 er lukket -> fylles til sluttkursen 11.11 (1,47), aldri intradag
    _go(tmp_path, "2026-11-12", 1.55, "2026-11-12", at(2026, 11, 12, 13, 0))
    f = [r for r in rows(tmp_path / "t.csv") if r["event"] == "fill"]
    assert len(f) == 1 and float(f[0]["price"]) == 1.47 and f[0]["price_date"] == "2026-11-11"


def test_waiting_order_never_cancelled_by_expiry(tmp_path, monkeypatch):
    tp = tmp_path / "t.csv"
    P._append(tp, B.B_COLS, [{"rules_version": R2["version"], "event": "order", "order_id": "2026-11-10-0092", "run_date": "2026-11-10",
                             "signal_date": "2026-11-10", "ticker": "SCANA.OL", "side": "buy", "reason": "x", "price_date": "2026-11-10",
                             "currency": "NOK"}])
    monkeypatch.setitem(HIST, "SCANA.OL", {"2026-11-09": 1.40, "2026-11-10": 1.44})     # ingen lukket bar etter 10.11 ennå
    for i, day in enumerate(("2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16")):
        s = _go(tmp_path, day, 1.46, day, at(2026, 11, 11 + i, 13, 0))
        assert len(s["pending"]) == 1 and not [r for r in rows(tp) if r["event"] in ("fill", "cancel")]   # > order_expiry_runs (5)


def test_nav_uses_last_closed_bar(tmp_path, monkeypatch):
    monkeypatch.setitem(HIST, "SCANA.OL", {"2026-11-10": 1.44, "2026-11-11": 1.47, "2026-11-12": 1.50})
    _go(tmp_path, "2026-11-10", 1.43, "2026-11-10", at(2026, 11, 10, 13, 0), picks=[tk("SCANA.OL", 1.43, "2026-11-10")])
    _go(tmp_path, "2026-11-11", 1.46, "2026-11-11", at(2026, 11, 11, 13, 0))          # venter
    _go(tmp_path, "2026-11-12", 9.99, "2026-11-12", at(2026, 11, 12, 13, 0))          # fylt 1,47 (11.11); intradag 9,99 ignoreres
    n0 = rows(tmp_path / "t_n.csv")[-1]
    _go(tmp_path, "2026-11-13", 7.77, "2026-11-13", at(2026, 11, 13, 13, 0))          # verdsatt til lukket 12.11 = 1,50
    sh = float([r for r in rows(tmp_path / "t.csv") if r["event"] == "fill"][0]["shares"])
    n1 = rows(tmp_path / "t_n.csv")[-1]
    assert abs(float(n1["nav"]) - float(n0["nav"]) - sh * (1.50 - 1.47)) < 0.05
    c = [r for r in rows(tmp_path / "portfolio_closes.csv") if r["date"] == "2026-11-13"]
    assert c and c[0]["close"] == "1.5" and c[0]["price_date"] == "2026-11-12"


def test_books_2_and_3_get_same_closed_view():
    src = Path("signaltool/portfolio_books.py").read_text()
    assert "closed=closed)   # samme lukkede barer som bok 1" in src and src.count("P.step(") == 1   # én løkke for bok 2 og 3
    p = Path("signaltool/portfolio.py").read_text()
    assert "step(snap, usd, bench, px_extra=px_extra, fx=fx, closed=closed)" in p
    assert "portfolio_books.run(snap, status, usd, bench, px_extra=px_extra, fx=fx, closed=closed)" in p


def test_off_list_closes_only_closed_bars():
    out = P.fetch_closes(["SCANA.OL"], now=at(2026, 11, 11, 13, 0), hist=lambda ts: HIST)
    assert out == {"SCANA.OL": (1.44, "2026-11-10")}


def test_learn_raw_drops_intraday_bar(tmp_path, monkeypatch):
    from signaltool import learnloop as L
    cat = tmp_path / "c.csv"
    cat.write_text("date,ticker,category,price,price_date,flags\n2026-11-10,A.OL,watch,1,2026-11-10,\n")
    monkeypatch.setattr(L, "CAT_LOG", cat)
    for n in ("RAW", "EXITS", "DQ"):
        monkeypatch.setattr(L, n, tmp_path / f"{n}.csv")
    days = [(dt.date(2026, 7, 14) + dt.timedelta(days=i)).isoformat() for i in range(120)]   # siste 10.11 (lukket)
    ser = {d: 100.0 + i for i, d in enumerate(days)}
    ser["2099-01-02"] = 999.0                                             # «dagens» bar som ikke er lukket
    monkeypatch.setattr(L, "_closes", lambda ts, period="1y": {t: dict(ser) for t in ts})
    snap = {"date": "2026-11-11", "tickers": [{"ticker": "A.OL", "score": 1.0, "points": {"x": 1}}]}
    L.record(snap, snap["tickers"], "2026-11-11")
    r = list(csv.DictReader((tmp_path / "RAW.csv").open()))[0]
    assert r["close_date"] == days[-1] and float(r["close"]) == ser[days[-1]] and "999" not in r["close"]
    assert abs(float(r["r5"]) - (ser[days[-1]] / ser[days[-6]] - 1)) < 1e-6
    assert "Historiske rader (før 11.11) er ikke rettet bakover" in Path("signaltool/learnloop.py").read_text()


def test_site_return_uses_last_closed_bar():
    from signaltool.site import _last_closed, _gen_time
    gen = _gen_time({"generated": "2026-11-10 14:29"})            # snapshot hentet 14:29 Oslo: .OL-baren 10.11 var intradag
    e = {"ticker": "SCANA.OL", "stats": {"close": 1.46, "last_date": "2026-11-10"}}
    assert _last_closed(e, {"SCANA.OL": [("2026-11-09", 1.40), ("2026-11-10", 1.44)]}, gen) == (1.44, "2026-11-10")   # Yahoo-sluttkursen
    e2 = {"ticker": "VRT", "stats": {"close": 180.0, "last_date": "2026-11-09"}}
    assert _last_closed(e2, {}, gen) == (180.0, "2026-11-09")     # US 09.11 var lukket da snapshotet ble hentet
    assert _last_closed(e2, {}, None) == (None, None)            # ukjent hentetid: aldri snapshotets kurs
    assert "_last_closed(e, _px if _ys else None, _gen)" in Path("signaltool/site.py").read_text()


def test_gs_index_drops_intraday_logged_prices():
    from signaltool import gs_index as G
    times = {"A.OL": [("2026-11-06", 98.4, "2026-11-06T12:58:00+00:00", "2026-11-06"),
                      ("2026-11-06", 99.5, "2026-11-08T11:57:00+00:00", "2026-11-08")]}
    rs = [{"date": "2026-11-06", "ticker": "A.OL", "price": "98.4", "price_date": "2026-11-06"},
          {"date": "2026-11-08", "ticker": "A.OL", "price": "99.5", "price_date": "2026-11-06"},
          {"date": "2026-11-09", "ticker": "A.OL", "price": "100", "price_date": "2026-11-09"},          # ukjent loggtid
          {"date": "2026-11-09", "ticker": "B.OL", "price": "5", "price_date": "2026-11-09", "_corrected": True}]
    out = G.closed_logged(rs, times)
    assert [r["price"] for r in out] == ["", "99.5", "", "5"]
    assert G.logged_prices(out)["A.OL"] == {"2026-11-06": (99.5, False)}
    src = Path("signaltool/gs_index.py").read_text()
    assert "CB.series(v, k) for k, v in _yf(list(IDX.values())" in src and "rows = closed_logged(rows)" in src


def test_intraday_fills_log():
    from signaltool.close_valid import is_close
    p = Path("logs/intraday_fills.csv")
    rs = list(csv.DictReader(p.open()))
    assert rs and set(rs[0]) == {"book", "order_id", "ticker", "side", "fill_date", "fill_time", "basis", "fill_price", "close", "diff_pct", "diff_nok"}
    assert all(not is_close(r["ticker"], r["fill_date"], r["fill_time"]) for r in rs)        # bare fylt før stengetid + 30
    assert {r["book"] for r in rs} <= {"rules_v1", "hoy_risiko_v1", "kontroll_tilfeldig_v1"}
    for r in rs:
        if r["close"]:
            assert abs(float(r["diff_pct"]) - (float(r["fill_price"]) / float(r["close"]) - 1)) < 1e-5
    # ikke rettet bakover: handelsloggen inneholder fortsatt intradagkursen
    tr = {(x["order_id"], x["event"]): x for x in csv.DictReader(Path("logs/portfolio_kontroll_tilfeldig_v1_trades.csv").open())}
    k = [r for r in rs if r["book"] == "kontroll_tilfeldig_v1"]
    assert k and all(tr[(r["order_id"], "fill")]["price"] == r["fill_price"] for r in k)
    assert "intraday_fills" not in Path("signaltool/site.py").read_text()                     # vises ikke på siden


def test_snapshot_bar_fetched_intraday_is_not_closed_even_later():
    """Snapshot hentet 10.11 14:29 (Oslo åpen): baren 10.11 er intradag selv om kjøringen/verdsettelsen skjer senere."""
    snap = {"date": "2026-11-10", "generated": "2026-11-10 14:29", "tickers": [tk("SCANA.OL", 1.43, "2026-11-10")]}
    v = P.closed_view(snap, now=at(2026, 11, 10, 18, 0), hist=lambda ts: {"SCANA.OL": {"2026-11-09": 1.40, "2026-11-10": 1.44}})
    assert v["SCANA.OL"] == (1.44, "2026-11-10", True)       # Yahoo-sluttkursen, ikke snapshotets intradag 1,43
    assert P.closed_view({"tickers": [tk("VRT", 1.0, "2026-11-09")]}, now=at(2026, 11, 10, 18, 0), hist=lambda ts: {})["VRT"][0] is None
