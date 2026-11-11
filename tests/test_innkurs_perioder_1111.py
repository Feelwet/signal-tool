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
        # «start» for innkursen = Inn-kjøringens price_date (siste sluttkurs før/på Inn-datoen): aldri eldre. Kursen fra Yahoo.
        assert s["since"] == inn and s["price_date"] == row["price_date"][:10] and s["price"] is None and s["src"] == "yahoo"
        SN.yahoo_entry(s, t, ser, dt.datetime(2026, 12, 1, tzinfo=dt.timezone.utc))
        assert s["price"] == 100.0 or s["entry_state"] == SN.MISSING
        if s["price"]:
            assert PC.entry_point(ser, C.ticker_periods(t), SN.dot_date(s)) == s["price_date"]
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
    assert s["since"] == "2026-11-07" and s["price_date"] == rows[-2]["price_date"]   # innkursdato fra gjeldende periode
    ep = tmp_path / "entry.csv"
    ep.write_text("date,ticker,category,price,price_date\n2026-11-05,ETF,watch,50,2026-11-04\n2026-11-07,ETF,watch,55,2026-11-06\n")
    from signaltool.since import SIDE_START
    assert SIDE_START <= "2026-11-05"
    per2 = C.periods(C.by_date(p, ep, None))
    assert per2["ETF"] == [["2026-11-05", None]] and C.gaps(p, ep, None) == {"ETF": ["2026-11-06"]}   # «data mangler» holder perioden
    rows2 = rows + [{"date": "2026-11-05", "ticker": "ETF", "category": "watch", "price": "50", "price_date": "2026-11-04"},
                    {"date": "2026-11-07", "ticker": "ETF", "category": "watch", "price": "55", "price_date": "2026-11-06"}]
    s2 = SN.from_period(rows2, "ETF", SN.current_inn(per2, "ETF"), "2026-11-07")
    assert s2["since"] == "2026-11-05" and s2["price_date"] == "2026-11-04"


def test_period_from_log_start_uses_first_log_date_entry(tmp_path):
    rows = [{"date": "2026-09-27", "ticker": "K", "category": "watch", "price": "300", "price_date": "2026-09-25", "flags": ""},
            {"date": "2026-09-28", "ticker": "K", "category": "watch", "price": "305", "price_date": "2026-09-26", "flags": ""}]
    s = SN.from_period(rows, "K", "2026-09-27", "2026-09-28")
    assert (s["since"], s["price_date"]) == ("2026-09-27", "2026-09-25")


def test_site_prep_uses_periods_and_other_users_unchanged():
    src = Path("signaltool/site.py").read_text()
    assert "SN.from_period(_rows, e[\"ticker\"], inn, _today or None)" in src
    # papirbøkene, GS-indeks, læringsløkka og innkurs-sideloggen bruker ikke Siden-raden/listeperiodene
    for f in ("portfolio.py", "portfolio_books.py", "portfolio_page.py", "gs_index.py", "learnloop.py", "categories.py", "results.py"):
        t = Path("signaltool", f).read_text()
        assert "from_period" not in t and "current_inn" not in t and "_since" not in t, f


UTC = dt.timezone.utc


def _at(y, mo, d, h, mi, tz="Europe/Oslo"):
    from zoneinfo import ZoneInfo
    return dt.datetime(y, mo, d, h, mi, tzinfo=ZoneInfo(tz))


def test_entry_is_yahoo_daily_close_never_logged_value():
    """ODL.OL: logget 98,40 (intradag 06.11) brukes ikke; Yahoos sluttkurs 06.11 = 99,50 er innkursen."""
    ser = [("2026-11-05", 97.0), ("2026-11-06", 99.5), ("2026-11-09", 101.0)]
    rows = [{"date": "2026-11-06", "ticker": "ODL.OL", "category": "watch", "price": "98.4", "price_date": "2026-11-06", "flags": ""}]
    s = SN.yahoo_entry(SN.from_period(rows, "ODL.OL", "2026-11-06", "2026-11-09"), "ODL.OL", ser, _at(2026, 11, 9, 12, 0))
    assert (s["price_date"], s["price"], s["entry_state"]) == ("2026-11-06", 99.5, None)
    assert SN.dot_date(s) == "2026-11-06"


def test_wait_until_close_plus_30_in_exchange_timezone():
    ser = [("2026-11-10", 80.0), ("2026-11-11", 83.7)]   # 11.11-baren finnes intradag
    s = {"price_date": "2026-11-11", "src": "yahoo"}
    assert SN.yahoo_entry(dict(s), "HAFNI.OL", ser, _at(2026, 11, 11, 16, 54))["entry_state"] == SN.WAIT    # 16:25 + 30
    assert SN.yahoo_entry(dict(s), "HAFNI.OL", ser, _at(2026, 11, 11, 16, 55))["price"] == 83.7
    w = SN.yahoo_entry(dict(s), "HAFNI.OL", ser, _at(2026, 11, 11, 12, 0))
    assert w["price"] is None and SN.dot_date(w) is None and SN.no_entry_text(None, w) == SN.NEW_T
    assert SN.yahoo_entry(dict(s), "MAERSK-B.CO", ser, _at(2026, 11, 11, 17, 29))["entry_state"] == SN.WAIT  # 17:00 + 30 København
    assert SN.yahoo_entry(dict(s), "MAERSK-B.CO", ser, _at(2026, 11, 11, 17, 30))["price"] == 83.7
    assert SN.yahoo_entry(dict(s), "RHM.DE", ser, _at(2026, 11, 11, 17, 59))["entry_state"] == SN.WAIT       # 17:30 + 30 Xetra
    assert SN.yahoo_entry(dict(s), "RHM.DE", ser, _at(2026, 11, 11, 18, 0))["price"] == 83.7
    assert SN.yahoo_entry(dict(s), "VRT", ser, _at(2026, 11, 11, 22, 29))["entry_state"] == SN.WAIT          # 16:00 ET + 30
    assert SN.yahoo_entry(dict(s), "VRT", ser, _at(2026, 11, 11, 22, 30))["price"] == 83.7


def test_missing_only_when_history_lacks_date_or_unknown_exchange():
    ser = [("2026-11-05", 10.0), ("2026-11-09", 11.0)]
    s = SN.yahoo_entry({"price_date": "2026-11-06", "src": "yahoo"}, "A.OL", ser, _at(2026, 11, 11, 12, 0))
    assert s["entry_state"] == SN.MISSING and s["price"] is None and SN.no_entry_text(None, s) == SN.NO_ENTRY
    assert SN.yahoo_entry({"price_date": "2026-11-05", "src": "yahoo"}, "X.ZZ", ser, _at(2026, 11, 11, 23, 0))["entry_state"] == SN.MISSING
    assert SN.yahoo_entry({"price_date": "2026-11-05", "src": "yahoo"}, "A.OL", ser, _at(2026, 11, 11, 12, 0))["price"] == 10.0


def test_display_no_entry_and_wait_in_table_ticker_page_and_sorting():
    none = {"since": "2026-11-10", "price": None, "price_date": "2026-11-10", "entry_state": SN.MISSING, "src": "yahoo"}
    wait = {"since": "2026-11-11", "price": None, "price_date": "2026-11-11", "entry_state": SN.WAIT, "src": "yahoo"}
    for s, txt in ((none, SN.NO_ENTRY), (wait, SN.NEW_T)):
        c = SN.ret_cell(None, s)
        assert 'data-v=""' in c and f'<span class="rtx">{txt}</span><span class="rex">–</span>' in c   # grå tekst + grå «–» mot indeks
        assert "%" not in c
    assert 'data-new="1"' in SN.ret_cell(None, wait) and 'data-new="1"' not in SN.ret_cell(None, none)
    assert ".rtx{font-size:13px;line-height:18px;font-weight:400;color:#94a3b8" in SN.CSS
    assert "#tf-table td.ret-c .rtx{white-space:normal;display:block;max-width:96px;margin-left:auto;text-align:right" in SN.CSS
    # tom data-v sorteres alltid nederst, begge retninger
    assert "if(!x&&!y)return 0;if(!x)return 1;if(!y)return -1;const c=num?(+x)-(+y):x.localeCompare(y);return asc?c:-c" in SN.JS
    ln = SN.line_rk(none, "", None)
    assert f"&nbsp;·&nbsp;{SN.NO_ENTRY}</span></p>" in ln and "ⓘ" not in ln.split(SN.NO_ENTRY)[1]   # ingen ekstra forklaring
    assert SN.NEW_T in SN.line_rk(wait, "", None)
    assert SN.dot_date(none) is None and SN.dot_date(wait) is None


def test_close_table_has_copenhagen_and_xetra_with_official_links():
    from signaltool import displayprices as DP
    assert DP.exchange_close("MAERSK-B.CO") == ("Europe/Copenhagen", 17, 0)
    assert DP.exchange_close("RHM.DE") == ("Europe/Berlin", 17, 30)
    assert DP.exchange_close("X.ZZ") is None
    src = Path("signaltool/displayprices.py").read_text().split("CLOSE = {")[0]
    assert "https://www.nasdaqomxnordic.com/tradinghours" in src
    assert "https://www.cashmarket.deutsche-boerse.com/cash-en/trading/trading-calendar-and-trading-hours" in src


def test_co_de_dst():
    """Europa bytter samtidig (28.03.2027 / 25.10.2026): 17:00 + 30 København = 17:30 Oslo; Xetra 17:30 + 30 = 18:00 Oslo."""
    from signaltool.laering_fwd import day_closed
    for d, z in (("2026-10-23", "sommer"), ("2026-10-26", "vinter"), ("2027-03-26", "vinter"), ("2027-03-29", "sommer")):
        y, m, dd = map(int, d.split("-"))
        assert not day_closed(d, "MAERSK-B.CO", _at(y, m, dd, 17, 29)) and day_closed(d, "MAERSK-B.CO", _at(y, m, dd, 17, 30)), (d, z)
        assert not day_closed(d, "RHM.DE", _at(y, m, dd, 17, 59)) and day_closed(d, "RHM.DE", _at(y, m, dd, 18, 0)), (d, z)
        # i UTC flytter grensen seg med sommertid
    assert day_closed("2026-10-23", "RHM.DE", dt.datetime(2026, 10, 23, 16, 0, tzinfo=UTC))       # CEST: 18:00 = 16:00 UTC
    assert not day_closed("2026-10-26", "RHM.DE", dt.datetime(2026, 10, 26, 16, 59, tzinfo=UTC))  # CET: 18:00 = 17:00 UTC
    assert day_closed("2026-10-26", "RHM.DE", dt.datetime(2026, 10, 26, 17, 0, tzinfo=UTC))


def test_site_fills_entry_from_yahoo_and_skips_logged_checks():
    src = Path("signaltool/site.py").read_text()
    assert "SN.yahoo_entry(sin[t], t, _px.get(t))" in src
    assert src.count('.get("src") != "yahoo"') == 2                                              # _factor_fix og _entry_check
    assert "SN.dot_date(" in src and 'PC.html(e["ticker"], e.get("_px"), (s or {}).get("price_date")' not in src
    assert "close_valid" not in Path("signaltool/since.py").read_text()                          # loggen styrer ikke innkurs


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
    assert CV.append_run({"date": "2026-11-12", "generated": "2026-11-12 06:17"}, out, cat, ent) == 0
    assert "logs/price_log_times.csv" in Path(".github/workflows/nightly.yml").read_text()
    t = CV.load()
    assert CV.intraday(t, "ODL.OL") and all(x[2] != 99.5 for x in CV.intraday(t, "ODL.OL"))          # 98,40 06.11 var intradag


def test_nightly_extra_run_after_european_close():
    import yaml
    d = yaml.safe_load(Path(".github/workflows/nightly.yml").read_text())
    crons = [c["cron"] for c in d[True]["schedule"]]
    assert crons == ["17 5 * * *", "15 17 * * *"] and d["concurrency"]["cancel-in-progress"] is False


def test_price_hold_tech_ol_shows_dash_kurs_under_kontroll():
    s = SN.yahoo_entry({"since": "2026-11-09", "price_date": "2026-11-09", "src": "yahoo"}, "TECH.OL",
                       [("2026-11-09", 1.57)], _at(2026, 11, 11, 12, 0))
    assert s["price"] == 1.57
    SN.price_hold(s, "TECH.OL")
    assert s["price"] is None and s["entry_state"] == SN.HOLD and SN.dot_date(s) is None
    c = SN.ret_cell(None, s)
    assert 'data-v=""' in c and '<span class="rv rna">–</span><span class="rex rhold">kurs under kontroll</span>' in c
    assert SN.NO_ENTRY not in c and SN.NEW_T not in c and "%" not in c
    ln = SN.line_rk(s, "", None)
    assert "&nbsp;·&nbsp;–&nbsp;kurs under kontroll" in ln and "inn " not in ln and SN.NO_ENTRY not in ln
    assert SN.price_hold({"since": "x", "price": 5.0}, "VRT")["price"] == 5.0                      # andre urørt
    assert "SN.price_hold(sin[t], t)" in Path("signaltool/site.py").read_text()


def test_wait_has_no_info_button_on_ticker_page():
    wait = {"since": "2026-11-11", "price": None, "price_date": "2026-11-11", "entry_state": SN.WAIT, "src": "yahoo"}
    ln = SN.line_rk(wait, "", None)
    assert SN.NEW_T in ln and "ⓘ" not in ln and 'class="ri' not in ln
