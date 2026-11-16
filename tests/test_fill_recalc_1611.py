"""AnalBot 16.11: 28 intradag-fills omregnet til Yahoo-sluttkurs; TECH.OL 30.10 og 02.11 urørt;
intradag_fills er revisjonsspor; fill_recalc_close i portfolio_deviations; tellere uendret."""
import csv
import hashlib
from pathlib import Path

from signaltool import portfolio_books as B
from signaltool import testbooks_page as TB
from signaltool.portfolio import _f, _read, state

ROOT = Path(__file__).resolve().parents[1]
DIFF = Path("/workspace/signal-tool-avvik/closevalid_books_diff_1611.csv")
SKIP = {("kontroll_tilfeldig_v1", "2026-10-29-0001"), ("kontroll_tilfeldig_v1", "2026-10-30-0018")}
INTRA_HASH = "37909c88e52cb349738f278344e0ebabf2ebd6cafd29faad8434127e6f13f431"


def _fills(book):
    tp, _ = B.paths(book)
    return [r for r in _read(tp) if r.get("event") == "fill"]


def test_twenty_eight_fills_match_yahoo_close_tech_untouched():
    want = {(r["book"], r["order_id"]): r for r in csv.DictReader(DIFF.open()) if r["typ"] == "fill"}
    assert len(want) == 30
    seen = 0
    for book in ("hoy_risiko_v1", "kontroll_tilfeldig_v1"):
        by = {r["order_id"]: r for r in _fills(book)}
        for oid, d in want.items():
            if oid[0] != book:
                continue
            r = by[oid[1]]
            if oid in SKIP:
                assert r["price"] == d["gammel_kurs"]
            else:
                assert abs(float(r["price"]) - float(d["ny_kurs"])) < 1e-6
                seen += 1
    assert seen == 28
    tech = {r["order_id"]: r for r in _fills("kontroll_tilfeldig_v1") if r["ticker"] == "TECH.OL"}
    assert tech["2026-10-29-0001"]["price"] == "1.835"
    assert tech["2026-10-30-0018"]["price"] == "2.0" and tech["2026-10-30-0018"]["pnl_nok"] == "4286.92"


def test_intraday_fills_audit_trail_unchanged():
    p = ROOT / "logs/intraday_fills.csv"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == INTRA_HASH
    intra = {(r["book"], r["order_id"]): r for r in csv.DictReader(p.open())}
    assert intra[("kontroll_tilfeldig_v1", "2026-10-29-0001")]["fill_price"] == "1.835"
    assert intra[("hoy_risiko_v1", "2026-10-29-0001")]["fill_price"] == "350.5"


def test_fill_recalc_close_logged_for_rewritten_and_follow_on_sales():
    dev = [r for r in _read(ROOT / "logs/portfolio_deviations.csv") if r.get("kind") == "fill_recalc_close"]
    keys = {(r["book_id"], r["order_id"]) for r in dev}
    want28 = {(r["book"], r["order_id"]) for r in csv.DictReader(DIFF.open())
              if r["typ"] == "fill" and (r["book"], r["order_id"]) not in SKIP}
    assert want28 <= keys and len(want28) == 28
    assert sum(1 for r in dev if r["book_id"] == "kontroll_tilfeldig_v1") == 24
    follow = [r for r in dev if r["order_id"] in ("2026-11-09-0080", "2026-11-11-0099")]
    assert len(follow) == 2 and all("følge av endret inngang" in r["note"] for r in follow)
    assert all("kurs " in r["note"] and "pnl " in r["note"] for r in dev)


def test_sell_shares_and_pnl_follow_buy_and_counts_unchanged():
    for book, n_open, n_closed in (("hoy_risiko_v1", 20, 2), ("kontroll_tilfeldig_v1", 19, 13)):
        rows = _read(B.paths(book)[0])
        s = state(rows)
        assert len(s["open"]) == n_open and len(s["closed"]) == n_closed
        pos = {}
        for r in rows:
            if r["event"] != "fill":
                continue
            if r["side"] == "buy":
                pos[r["ticker"]] = r
            else:
                b = pos.pop(r["ticker"])
                assert abs((_f(r["shares"]) or 0) - (_f(b["shares"]) or 0)) < 1e-9
                nok = round((_f(r["shares"]) or 0) * (_f(r["price"]) or 0) * (_f(r["fx"]) or 1), 2)
                cost = round(nok * 0.002, 2)
                entry = (_f(b["nok_value"]) or 0) + (_f(b["cost_nok"]) or 0)
                assert abs((_f(r["nok_value"]) or 0) - nok) < 0.011
                assert abs((_f(r["cost_nok"]) or 0) - cost) < 0.011
                assert abs((_f(r["pnl_nok"]) or 0) - round(nok - cost - entry, 2)) < 0.011


def test_visible_book_card_counters_unchanged():
    h = TB.book_data("hoy_risiko_v1")
    k = TB.book_data("kontroll_tilfeldig_v1")
    assert (len(h["dates"]), h["closed"], h["open"], h["universe_n"]) == (14, 2, 20, 29)
    assert (len(k["dates"]), k["closed"], k["open"], k["universe_n"]) == (12, 13, 19, 29)
    assert h["universe_date"] == "2026-11-11" and k["universe_date"] == "2026-11-11"  # siste fullførte kjøring, ikke 16.11-kandidatrad uten NAV
    html = TB.book_card(h, h["dates"]) + TB.book_card(k, k["dates"])
    assert "2 av 30" in html and "13 av 30" in html
    assert "lukkede · 20 åpne" in html and "lukkede · 19 åpne" in html
