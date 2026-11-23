"""AnalBot 16.11: 28 intradag-fills omregnet til Yahoo-sluttkurs; TECH.OL 30.10 og 02.11 urørt;
intradag_fills er revisjonsspor; fill_recalc_close i portfolio_deviations; tellere uendret."""
import csv
import hashlib
from pathlib import Path

import pytest

from signaltool import portfolio_books as B
from signaltool import testbooks_page as TB
from signaltool.portfolio import _f, _read, state

ROOT = Path(__file__).resolve().parents[1]
DIFF = Path("/workspace/signal-tool-avvik/closevalid_books_diff_1611.csv")
# Diff-fila er privat (ligger på boksen, ikke i repoet); i CI hoppes de to testene som leser den over.
needs_diff = pytest.mark.skipif(not DIFF.exists(), reason="privat diff-fil, ikke i repoet (CI)")
SKIP = {("kontroll_tilfeldig_v1", "2026-10-29-0001"), ("kontroll_tilfeldig_v1", "2026-10-30-0018")}
INTRA_HASH = "37909c88e52cb349738f278344e0ebabf2ebd6cafd29faad8434127e6f13f431"


def _fills(book):
    tp, _ = B.paths(book)
    return [r for r in _read(tp) if r.get("event") == "fill"]


@needs_diff
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


@needs_diff
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


def _order_date(r: dict) -> str:
    """Datoen i ordre-id (YYYY-MM-DD-…), ellers signal_date/run_date."""
    oid = r.get("order_id") or ""
    if len(oid) >= 10 and oid[4] == "-" and oid[7] == "-":
        return oid[:10]
    return r.get("signal_date") or r.get("run_date") or ""


def _trade_path(book: str) -> Path:
    return ROOT / "logs/portfolio_trades.csv" if book == "rules_v1" else B.paths(book)[0]


def test_sell_shares_and_pnl_follow_buy_and_counts_unchanged():
    # AnalBot 23.11: tellesjekken gjelder bare ordre til og med 2026-11-16 (NCLH-fill 18.11 er utenfor).
    cutoff = "2026-11-16"
    for book, n_open, n_closed in (("hoy_risiko_v1", 20, 2), ("kontroll_tilfeldig_v1", 19, 13)):
        rows = _read(B.paths(book)[0])
        early = [r for r in rows if _order_date(r) <= cutoff]
        s = state(early)
        assert len(s["open"]) == n_open and len(s["closed"]) == n_closed, (book, len(s["open"]), len(s["closed"]))
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
    # AnalBot 23.11: åpne posisjoner = kjøp − salg, for hver bok, på hele loggen.
    for book in ("hoy_risiko_v1", "kontroll_tilfeldig_v1", "rules_v1"):
        rows = _read(_trade_path(book))
        buys = sum(1 for r in rows if r["event"] == "fill" and r["side"] == "buy")
        sells = sum(1 for r in rows if r["event"] == "fill" and r["side"] == "sell")
        s = state(rows)
        assert len(s["open"]) == buys - sells, (book, len(s["open"]), buys, sells)


def test_visible_book_card_counters_unchanged():
    """Invarianter (ikke hardkodet dato): kjøringer = unike NAV-datoer; universradene
    følger qualifies() (20d strengt > 0, ikke-tom score, ikke Tema); trukket univers
    == _last_universe for hver NAV-dato. 16.11 uten NAV teller ikke."""
    from signaltool.config import LOGS
    from signaltool.portfolio import _read, state
    from signaltool.testbooks_page import MIN_CLOSED

    def _f(v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    for book in ("hoy_risiko_v1", "kontroll_tilfeldig_v1"):
        d = TB.book_data(book)
        navs = _read(B.paths(book)[1])
        nav_dates = [r["date"] for r in navs]
        unique = list(dict.fromkeys(nav_dates))
        assert nav_dates == unique, f"{book}: duplikate NAV-datoer"
        assert d["dates"] == unique and len(d["dates"]) == len(unique)
        st = state(_read(B.paths(book)[0]))
        assert d["open"] == len(st["open"]) and d["closed"] == len(st["closed"])
        udate, un = TB._last_universe(book, LOGS)
        assert (d["universe_date"], d["universe_n"]) == (udate, un)
        # 16.11 er kandidat uten NAV og skal ikke bli siste univers
        assert d["universe_date"] in unique and d["universe_date"] != "2026-11-16"
        cands = [r for r in _read(LOGS / B.CANDS.name) if r.get("book_id") == book]
        trades = _read(B.paths(book)[0])
        for day in unique:
            cr = [r for r in cands if r.get("date") == day]
            if not cr:
                continue
            # Hvis denne NAV-datoen er den siste med kandidatrad, er det _last_universe
            later = [r for r in cands if r.get("date") in unique and r["date"] > day]
            if not later:
                assert (day, int(cr[-1]["universe_n"])) == (udate, un)
            tickers = [x for x in (cr[-1].get("tickers") or "").split("|") if x]
            # Hver trukket ticker: ingen Tema; ret_20d/score fra handelsloggen når de finnes
            why = [r for r in trades if (r.get("run_date") == day or r.get("signal_date") == day)
                   and r.get("ticker") in tickers]
            for r in why:
                cat = (r.get("category") or "").strip()
                assert cat.lower() != "tema", f"{book} {day} {r.get('ticker')}: Tema i trekket"
                sc = r.get("score")
                if sc not in (None, ""):
                    assert str(sc).strip() != ""
                r20 = _f(r.get("ret_20d"))
                if r20 is not None:
                    assert r20 > 0, f"{book} {day} {r.get('ticker')}: ret_20d={r20} ikke strengt > 0"
        html = TB.book_card(d, d["dates"])
        assert f'{d["closed"]} av {MIN_CLOSED}' in html
        assert f'lukkede · {d["open"]} åpne' in html
