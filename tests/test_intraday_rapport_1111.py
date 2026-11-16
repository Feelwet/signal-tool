"""AnalBot 11.11: bokrapportens linje om intradag-fills og forberedt «med/uten» (skjult til 30 lukkede handler)."""
import csv
from pathlib import Path

from signaltool import intraday_fills as I
from signaltool import portfolio as P
from signaltool import portfolio_books as PB

LOG = Path(__file__).resolve().parents[1] / "logs" / "intraday_fills.csv"


def _w(path, cols, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def test_line_from_real_log_not_hardcoded():
    rows = list(csv.DictReader(LOG.open()))
    st = I.stats(LOG)
    assert st["samlet"]["n"] == len(rows) == 32          # rommet 11.11: SCANA.OL nr. 32
    d = [abs(float(r["diff_pct"])) for r in rows if r["diff_pct"]]
    assert abs(st["samlet"]["mean_abs_pct"] - sum(d) / len(d)) < 1e-12
    assert sum(st[b]["n"] for b in st if b != "samlet") == len(rows)
    d = [abs(float(r["diff_pct"])) for r in rows if r["diff_pct"]]
    assert I.line(st["samlet"]) == f"{len(rows)} fills før 11.11 på intradag-kurs, snitt absolutt avvik " + f"{sum(d) / len(d) * 100:.1f} %".replace(".", ",")
    ls = I.report_lines(LOG)
    assert ls[-1].startswith(f"Samlet: {len(rows)} fills før 11.11") and any(x.startswith("Høy risiko:") for x in ls)


def test_line_follows_file(tmp_path):
    p = tmp_path / "f.csv"
    _w(p, I.COLS, [{"book": "hoy_risiko_v1", "order_id": "a", "diff_pct": "0.02"}, {"book": "hoy_risiko_v1", "order_id": "b", "diff_pct": "-0.04"},
                   {"book": "kontroll_tilfeldig_v1", "order_id": "c", "diff_pct": ""}])
    st = I.stats(p)
    assert I.line(st["hoy_risiko_v1"]) == "2 fills før 11.11 på intradag-kurs, snitt absolutt avvik 3,0 %"
    assert I.line(st["kontroll_tilfeldig_v1"]).endswith("snitt absolutt avvik –")
    assert st["samlet"]["n"] == 3


def _fill(oid, t, side, d, px, sh, pnl=""):
    v = px * sh
    return {"rules_version": "hoy_risiko_v1", "event": "fill", "order_id": oid, "run_date": d, "signal_date": d, "ticker": t, "side": side,
            "price_date": d, "price": px, "currency": "NOK", "fx": 1, "shares": sh, "nok_value": v, "cost_nok": 0, "pnl_nok": pnl}


def _book(tmp_path, n_closed):
    tp, _ = PB.paths("hoy_risiko_v1", tmp_path)
    rows = []
    for i in range(n_closed):
        rows += [_fill(f"b{i}", f"T{i}.OL", "buy", "2026-10-01", 100, 10), _fill(f"s{i}", f"T{i}.OL", "sell", "2026-10-20", 110 if i else 50, 10, 100 if i else -500)]
    _w(tp, P.T_COLS, rows)
    lf = tmp_path / "intra.csv"
    _w(lf, I.COLS, [{"book": "hoy_risiko_v1", "order_id": "b0", "diff_pct": "0.01"}])
    return lf


def test_with_without_hidden_before_30(tmp_path):
    lf = _book(tmp_path, 29)
    assert I.with_without("hoy_risiko_v1", tmp_path, lf) is None


def test_with_without_visible_at_30_drops_whole_round_trip(tmp_path):
    lf = _book(tmp_path, 30)
    r = I.with_without("hoy_risiko_v1", tmp_path, lf)
    start = PB.BOOKS["hoy_risiko_v1"]["start_nok"]
    assert r["med"]["closed"] == 30 and r["uten"]["closed"] == 29
    assert abs(r["med"]["nav_est"] - (start + 29 * 100 - 500)) < 1e-6
    assert abs(r["uten"]["nav_est"] - (start + 29 * 100)) < 1e-6
    assert r["line"].startswith("Avkastning med intradag-fills ")


def test_drop_open_position_with_intraday_buy():
    tr = [_fill("b1", "A.OL", "buy", "2026-10-01", 10, 1), _fill("b2", "B.OL", "buy", "2026-10-01", 10, 1)]
    assert [r["order_id"] for r in I._drop_intraday(tr, {"b1"})] == ["b2"]


def test_scana_row_32_waits_for_closed_bar_then_fills(tmp_path):
    import datetime as dt
    from zoneinfo import ZoneInfo
    rows = list(csv.DictReader(LOG.open()))
    sc = [r for r in rows if r["ticker"] == "SCANA.OL" and r["fill_date"] == "2026-11-11"]
    assert len(sc) == 1 and sc[0]["fill_price"] == "1.425" and sc[0]["fill_time"] == "2026-11-11T12:44:44+00:00"   # 13:44 Oslo
    p = tmp_path / "f.csv"
    base = [dict(r, close="", diff_pct="", diff_nok="") if r is sc[0] else r for r in rows]   # nr. 32 som den ble ført 11.11: uten sluttkurs
    _w(p, list(rows[0]), base)
    rows = list(csv.DictReader(p.open()))
    logs = tmp_path / "logs"
    logs.mkdir()
    tp = PB.paths("kontroll_tilfeldig_v1", logs)[0]
    _w(tp, P.T_COLS, [{"event": "fill", "order_id": sc[0]["order_id"], "ticker": "SCANA.OL", "side": "buy", "shares": 1000, "fx": 1}])
    hist = lambda ts: {"SCANA.OL": {"2026-11-10": 1.45, "2026-11-11": 1.40}}
    o = ZoneInfo("Europe/Oslo")
    open_ = dt.datetime(2026, 11, 11, 16, 40, tzinfo=o)       # Oslo stenger 16:25 -> gyldig fra 16:55
    assert I.fill_closes(p, hist, open_, logs) == 0
    assert [r for r in csv.DictReader(p.open()) if r["ticker"] == "SCANA.OL"][-1]["close"] == ""
    after = dt.datetime(2026, 11, 11, 18, 15, tzinfo=o)
    assert I.fill_closes(p, hist, after, logs) == 1
    r = [r for r in csv.DictReader(p.open()) if r["ticker"] == "SCANA.OL"][-1]
    assert r["close"] == "1.4" and abs(float(r["diff_pct"]) - (1.425 / 1.4 - 1)) < 1e-6 and float(r["diff_nok"]) == 25.0
    other = [x for x in csv.DictReader(p.open()) if x["ticker"] != "SCANA.OL" or x["fill_date"] != "2026-11-11"]
    assert other == [x for x in rows if x["ticker"] != "SCANA.OL" or x["fill_date"] != "2026-11-11"]   # resten urørt
    assert I.fill_closes(p, hist, after, logs) == 0


def test_pipeline_runs_fill_closes_and_workflow_commits_log():
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]
    assert "IF.fill_closes()" in (root / "signaltool" / "pipeline.py").read_text()
    assert "logs/intraday_fills.csv" in (root / ".github" / "workflows" / "nightly.yml").read_text()
