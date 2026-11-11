"""AnalBot 11.11: innkurspunktet og avkastningen i Siden-raden følger listeperiodene (gjeldende periode)."""
import csv
import datetime as dt
from pathlib import Path

from signaltool import since as SN, ov_changes as C, pricechart as PC
from tests.test_ov_changes_1111 import _write


def _bdays(a="2026-09-01", b="2026-11-30"):
    d, out = dt.date.fromisoformat(a), []
    while d <= dt.date.fromisoformat(b):
        if d.weekday() < 5:
            out.append((d.isoformat(), 100.0))
        d += dt.timedelta(days=1)
    return out


def test_dot_equals_entry_price_date_for_all_tickers_on_list():
    rows, per = SN.load(), C.periods(C.by_date())
    today = max(r["date"] for r in rows)
    cur = [t for t in per if SN.current_inn(per, t)]
    assert len(cur) == len(C.by_date()[max(C.by_date())])
    ser = _bdays()
    n = 0
    for t in cur:
        inn = SN.current_inn(per, t)
        s = SN.from_period(rows, t, inn, today)
        row = next(r for r in rows if r["ticker"] == t and r["date"] == inn)
        # «start» for innkursen = Inn-kjøringens price_date (siste sluttkurs før/på Inn-datoen): aldri eldre
        assert s["since"] == inn and s["price_date"] == row["price_date"][:10] and s["price_date"] <= inn
        assert s["price"] == float(row["price"])
        assert PC.entry_point(ser, C.ticker_periods(t), s["price_date"]) == s["price_date"]
        n += 1
    assert n == len(cur) and n > 0


def test_unlogged_gap_breaks_and_data_missing_gap_holds(tmp_path):
    p = _write(tmp_path, [("2026-11-05", "A"), ("2026-11-05", "B"), ("2026-11-06", "B"), ("2026-11-07", "A"), ("2026-11-07", "B")])
    rows = list(csv.DictReader(p.open()))
    for r in rows:
        r["price"] = {"2026-11-05": "10", "2026-11-06": "11", "2026-11-07": "12"}[r["date"]]
    per = C.periods(C.by_date(p, None, None))
    assert per["A"] == [["2026-11-05", "2026-11-06"], ["2026-11-07", None]]      # ulogget hull 06.11 = Ut + Inn
    s = SN.from_period(rows, "A", SN.current_inn(per, "A"), "2026-11-07")
    assert s["since"] == "2026-11-07" and s["price"] == 12.0                    # innkurs fra gjeldende periode
    ep = tmp_path / "entry.csv"
    ep.write_text("date,ticker,category,price,price_date\n2026-11-05,ETF,watch,50,2026-11-04\n2026-11-07,ETF,watch,55,2026-11-06\n")
    from signaltool.since import SIDE_START
    assert SIDE_START <= "2026-11-05"
    per2 = C.periods(C.by_date(p, ep, None))
    assert per2["ETF"] == [["2026-11-05", None]] and C.gaps(p, ep, None) == {"ETF": ["2026-11-06"]}   # «data mangler» holder perioden
    rows2 = rows + [{"date": "2026-11-05", "ticker": "ETF", "category": "watch", "price": "50", "price_date": "2026-11-04"},
                    {"date": "2026-11-07", "ticker": "ETF", "category": "watch", "price": "55", "price_date": "2026-11-06"}]
    s2 = SN.from_period(rows2, "ETF", SN.current_inn(per2, "ETF"), "2026-11-07")
    assert s2["since"] == "2026-11-05" and s2["price"] == 50.0 and s2["price_date"] == "2026-11-04"


def test_period_from_log_start_uses_first_log_date_entry(tmp_path):
    rows = [{"date": "2026-09-27", "ticker": "K", "category": "watch", "price": "300", "price_date": "2026-09-25", "flags": ""},
            {"date": "2026-09-28", "ticker": "K", "category": "watch", "price": "305", "price_date": "2026-09-26", "flags": ""}]
    s = SN.from_period(rows, "K", "2026-09-27", "2026-09-28")
    assert (s["since"], s["price"], s["price_date"]) == ("2026-09-27", 300.0, "2026-09-25")


def test_site_prep_uses_periods_and_other_users_unchanged():
    src = Path("signaltool/site.py").read_text()
    assert "SN.from_period(_rows, e[\"ticker\"], inn, _today or None)" in src
    # papirbøkene, GS-indeks, læringsløkka og innkurs-sideloggen bruker ikke Siden-raden/listeperiodene
    for f in ("portfolio.py", "portfolio_books.py", "portfolio_page.py", "gs_index.py", "learnloop.py", "categories.py", "results.py"):
        t = Path("signaltool", f).read_text()
        assert "from_period" not in t and "current_inn" not in t and "_since" not in t, f
