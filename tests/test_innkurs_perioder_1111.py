"""AnalBot 11.11: innkurspunktet og avkastningen i Siden-raden følger listeperiodene (gjeldende periode)."""
import csv
import datetime as dt
from pathlib import Path

from signaltool import since as SN, ov_changes as C, pricechart as PC, close_valid as CV
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
        # «start» for innkursen = Inn-kjøringens price_date (siste sluttkurs før/på Inn-datoen): aldri eldre. Er den verdien
        # ikke en sluttkurs (logget før stengetid + 30 min): neste gyldige sluttkurs (close_valid.entry).
        assert s["since"] == inn and (s["price_date"], s["price"]) == CV.entry(CV.load(), t, row["price_date"][:10])
        assert s["price_date"] is None or s["price_date"] >= row["price_date"][:10]
        if s["price_date"]:
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
    s = SN.from_period(rows, "A", SN.current_inn(per, "A"), "2026-11-07", times=CV.from_rows(rows))
    assert s["since"] == "2026-11-07" and s["price"] == 12.0                    # innkurs fra gjeldende periode
    ep = tmp_path / "entry.csv"
    ep.write_text("date,ticker,category,price,price_date\n2026-11-05,ETF,watch,50,2026-11-04\n2026-11-07,ETF,watch,55,2026-11-06\n")
    from signaltool.since import SIDE_START
    assert SIDE_START <= "2026-11-05"
    per2 = C.periods(C.by_date(p, ep, None))
    assert per2["ETF"] == [["2026-11-05", None]] and C.gaps(p, ep, None) == {"ETF": ["2026-11-06"]}   # «data mangler» holder perioden
    rows2 = rows + [{"date": "2026-11-05", "ticker": "ETF", "category": "watch", "price": "50", "price_date": "2026-11-04"},
                    {"date": "2026-11-07", "ticker": "ETF", "category": "watch", "price": "55", "price_date": "2026-11-06"}]
    s2 = SN.from_period(rows2, "ETF", SN.current_inn(per2, "ETF"), "2026-11-07", times=CV.from_rows(rows2))
    assert s2["since"] == "2026-11-05" and s2["price"] == 50.0 and s2["price_date"] == "2026-11-04"


def test_period_from_log_start_uses_first_log_date_entry(tmp_path):
    rows = [{"date": "2026-09-27", "ticker": "K", "category": "watch", "price": "300", "price_date": "2026-09-25", "flags": ""},
            {"date": "2026-09-28", "ticker": "K", "category": "watch", "price": "305", "price_date": "2026-09-26", "flags": ""}]
    s = SN.from_period(rows, "K", "2026-09-27", "2026-09-28", times=CV.from_rows(rows))
    assert (s["since"], s["price"], s["price_date"]) == ("2026-09-27", 300.0, "2026-09-25")


def test_site_prep_uses_periods_and_other_users_unchanged():
    src = Path("signaltool/site.py").read_text()
    assert "SN.from_period(_rows, e[\"ticker\"], inn, _today or None)" in src
    # papirbøkene, GS-indeks, læringsløkka og innkurs-sideloggen bruker ikke Siden-raden/listeperiodene
    for f in ("portfolio.py", "portfolio_books.py", "portfolio_page.py", "gs_index.py", "learnloop.py", "categories.py", "results.py"):
        t = Path("signaltool", f).read_text()
        assert "from_period" not in t and "current_inn" not in t and "_since" not in t, f


def _t(rows):
    """[(date, ticker, price_date, price, logged_at)] -> tidsoppslag som i logs/price_log_times.csv."""
    import io
    buf = io.StringIO("date,ticker,price_date,price,logged_at,basis\n" + "".join(f"{a},{b},{c},{d},{e},run_start\n" for a, b, c, d, e in rows))
    p = Path(__import__("tempfile").mkdtemp()) / "t.csv"
    p.write_text(buf.getvalue())
    return CV.load(p)


def test_price_logged_before_close_is_not_a_close_odl_like():
    """ODL.OL: 98,40 logget 06.11 13:58 Oslo (før 16:25 + 30) er ikke sluttkurs; 99,50 logget 08.11 for price_date 06.11 vinner."""
    t = _t([("2026-11-06", "ODL.OL", "2026-11-06", "98.4", "2026-11-06T12:58:37+00:00"),
            ("2026-11-08", "ODL.OL", "2026-11-06", "99.5", "2026-11-08T11:57:24+00:00")])
    assert not CV.is_close("ODL.OL", "2026-11-06", "2026-11-06T12:58:37+00:00")
    assert CV.is_close("ODL.OL", "2026-11-06", "2026-11-06T15:55:00+00:00")            # 16:55 Oslo = 16:25 + 30
    assert not CV.is_close("ODL.OL", "2026-11-06", "2026-11-06T15:54:00+00:00")
    assert CV.entry(t, "ODL.OL", "2026-11-06") == ("2026-11-06", 99.5)
    rows = [{"date": "2026-11-06", "ticker": "ODL.OL", "category": "watch", "price": "98.4", "price_date": "2026-11-06", "flags": ""}]
    s = SN.from_period(rows, "ODL.OL", "2026-11-06", "2026-11-08", times=t)
    assert (s["price_date"], s["price"]) == ("2026-11-06", 99.5)


def test_two_after_close_values_last_wins_and_exchange_timezone():
    t = _t([("2026-11-06", "VRT", "2026-11-05", "180.0", "2026-11-05T21:31:00+00:00"),    # 16:31 New York (før 16:30? nei: 16:31 ≥ 16:30)
            ("2026-11-07", "VRT", "2026-11-05", "181.5", "2026-11-07T08:00:00+00:00"),
            ("2026-11-06", "VRT", "2026-11-05", "175.0", "2026-11-05T21:00:00+00:00")])     # 16:00 NY: før stengetid + 30
    assert CV.entry(t, "VRT", "2026-11-05") == ("2026-11-05", 181.5)                         # siste gyldige vinner
    assert not CV.is_close("VRT", "2026-11-05", "2026-11-05T21:29:00+00:00") and CV.is_close("VRT", "2026-11-05", "2026-11-05T21:30:00+00:00")


def test_no_close_for_price_date_falls_back_to_next_valid_close():
    t = _t([("2026-11-05", "A.OL", "2026-11-05", "10", "2026-11-05T10:00:00+00:00"),        # intradag, aldri bekreftet
            ("2026-11-07", "A.OL", "2026-11-06", "11", "2026-11-07T10:00:00+00:00"),
            ("2026-11-07", "A.OL", "2026-11-09", "99", "2026-11-09T10:00:00+00:00")])       # 09.11 intradag: ikke gyldig
    assert CV.entry(t, "A.OL", "2026-11-05") == ("2026-11-06", 11.0)                         # neste gyldige sluttkurs
    assert CV.entry(t, "A.OL", "2026-11-09") == (None, None)                                 # ingen gyldig -> ingen innkurs
    assert CV.entry(t, "MAERSK-B.CO", "2026-11-05") == (None, None)
    u = _t([("2026-11-06", "X.CO", "2026-11-05", "5", "2026-11-09T10:00:00+00:00")])
    assert CV.entry(u, "X.CO", "2026-11-05") == (None, None)                                 # ukjent børs: aldri sluttkurs


def test_pipeline_logs_run_start_times_and_workflow_commits_file(tmp_path):
    cat = tmp_path / "c.csv"
    cat.write_text("date,ticker,category,price,price_date,flags\n2026-11-12,ODL.OL,watch,100,2026-11-11,\n2026-11-11,ODL.OL,watch,99,2026-11-10,\n")
    ent = tmp_path / "e.csv"
    ent.write_text("date,ticker,category,price,price_date\n2026-11-12,SPY,watch,600,2026-11-11\n")
    out = tmp_path / "t.csv"
    n = CV.append_run({"date": "2026-11-12", "generated": "2026-11-12 06:17"}, out, cat, ent)
    rows = list(csv.DictReader(out.open()))
    assert n == 2 and {r["ticker"] for r in rows} == {"ODL.OL", "SPY"}
    assert all(r["logged_at"] == "2026-11-12T06:17:00+01:00" and r["basis"] == "run_start" for r in rows)
    assert CV.append_run({"date": "2026-11-12", "generated": "2026-11-12 06:17"}, out, cat, ent) == 0       # idempotent
    assert "logs/price_log_times.csv" in Path(".github/workflows/nightly.yml").read_text()
    assert "CV.append_run(snap)" in Path("signaltool/pipeline.py").read_text()
    real = list(csv.DictReader(CV.TIMES.open()))
    assert real and {r["basis"] for r in real} <= {"run_start", "commit"}
