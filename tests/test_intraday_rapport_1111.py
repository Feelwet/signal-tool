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
    assert st["samlet"]["n"] == len(rows) == 31
    d = [abs(float(r["diff_pct"])) for r in rows]
    assert abs(st["samlet"]["mean_abs_pct"] - sum(d) / len(d)) < 1e-12
    assert sum(st[b]["n"] for b in st if b != "samlet") == 31
    assert I.line(st["samlet"]) == f"31 fills før 11.11 på intradag-kurs, snitt absolutt avvik " + f"{sum(d) / len(d) * 100:.1f} %".replace(".", ",")
    ls = I.report_lines(LOG)
    assert ls[-1].startswith("Samlet: 31 fills før 11.11") and any(x.startswith("Høy risiko:") for x in ls)


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
