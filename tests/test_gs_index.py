import csv

import pytest

from signaltool import gs_index as G

DAYS = ["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01"]
IDX = {"OSEBX.OL": {d: 100.0 for d in DAYS}}
EX = {"A.OL": "oslo", "B.OL": "oslo"}


def row(t, flags=""):
    return {"ticker": t, "category": "watch", "flags": flags}


def test_entry_day_after_listing_and_cost():
    # på lista fra logg 28.09 -> inn på sluttkurs 29.09 (første handelsdag etter); A stiger 10 % 29.09->30.09
    lists = {"2026-09-27": {}, "2026-09-28": {"A.OL": row("A.OL")}}
    yfp = {"A.OL": {"2026-09-28": 50.0, "2026-09-29": 100.0, "2026-09-30": 110.0, "2026-10-01": 110.0}}
    r = G.compute(lists, DAYS, {}, yfp, EX, IDX)
    assert [x["date"] for x in r] == DAYS
    assert r[0]["gs_index"] == 100
    assert r[1]["gs_index"] == pytest.approx(100 * (1 - 0.002))   # +100 % 28->29 telles ikke; inngangskostnad 0,2 % på 29.09
    assert r[1]["n_members"] == 1
    assert r[2]["gs_index"] == pytest.approx(100 * 0.998 * 1.10)


def test_exit_day_after_leaving_and_illiquid_cost():
    lists = {"2026-09-27": {"A.OL": row("A.OL", "illiquid")}, "2026-09-29": {}}
    yfp = {"A.OL": {"2026-09-28": 100.0, "2026-09-29": 110.0, "2026-09-30": 121.0, "2026-10-01": 50.0}}
    r = G.compute(lists, DAYS, {}, yfp, EX, IDX)
    # inn 28.09 (0,5 % trekkes i rad 2), +10 % 29.09, +10 % 30.09 (ute først på sluttkurs 30.09, kostnad 0,5 %), fallet 01.10 telles ikke
    assert r[1]["gs_index"] == pytest.approx(100 * 0.995 * 1.10)
    assert r[2]["gs_index"] == pytest.approx(100 * 0.995 * 1.10 * 1.10 * 0.995)
    assert r[3]["gs_index"] == pytest.approx(r[2]["gs_index"])


def test_missing_price_dropped_and_counted():
    lists = {"2026-09-27": {"A.OL": row("A.OL"), "B.OL": row("B.OL")}}
    yfp = {"A.OL": {d: 100.0 for d in DAYS}, "B.OL": {"2026-09-28": 100.0, "2026-09-30": 200.0}}
    r = G.compute(lists, DAYS, {}, yfp, EX, IDX)
    assert r[1]["n_no_price"] == 1          # B mangler 29.09: droppes, ikke oppfunnet
    assert r[1]["gs_index"] == pytest.approx(100 * (1 - 0.002))


def test_corrections_and_mixed_basis(tmp_path):
    cat = tmp_path / "c.csv"
    cat.write_text("date,ticker,category,price,price_date,benchmark,score,n_types,types,flags\n"
                   "2026-09-27,A.OL,watch,5.0,2026-09-25,,,,,\n2026-10-01,A.OL,watch,4.66,2026-09-29,,,,,\n"
                   "2026-09-27,X.L,watch,1,2026-09-25,,,,,\n2026-09-27,T.OL,tema,1,2026-09-25,,,,,\n")
    corr = tmp_path / "k.csv"
    corr.write_text("date,ticker,field,old,new,reason\n2026-10-01,A.OL,price,4.66,2.178,x\n2026-09-27,X.L,exclude,,1,x\n")
    rows = G.load_rows(cat, corr)
    assert {r["ticker"] for r in rows} == {"A.OL", "T.OL"}
    lp = G.logged_prices(rows)
    assert lp["A.OL"]["2026-09-29"] == (2.178, True) and lp["A.OL"]["2026-09-25"] == (5.0, False)
    assert set(G.lists_by_date(rows)["2026-09-27"]) == {"A.OL"}   # tema er ikke lista
    assert "2.178" not in cat.read_text()                         # categories.csv endres aldri


def test_benchmark_weighted_by_exchange():
    days = DAYS[:3]
    idx = {"OSEBX.OL": {"2026-09-28": 100, "2026-09-29": 110, "2026-09-30": 110},
           "^IXIC": {"2026-09-28": 100, "2026-09-29": 100, "2026-09-30": 100}}
    lists = {"2026-09-27": {"A.OL": row("A.OL"), "N": row("N"), "M": row("M")}}
    yfp = {t: {d: 1.0 for d in days} for t in ("A.OL", "N", "M")}
    r = G.compute(lists, days, {}, yfp, {"A.OL": "oslo", "N": "nasdaq", "M": "nasdaq"}, idx)
    assert r[1]["benchmark"] == pytest.approx(100 * (1 + 0.10 / 3))


def _write(p, n):
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=G.COLS)
        w.writeheader()
        for i in range(n):
            w.writerow({"date": f"2026-{i:04d}", "gs_index": 100 + i % 3, "benchmark": 100, "n_members": 50, "n_no_price": 2, "gs_ex_tech": 123.4567})


def test_hide_gate(tmp_path):
    p = tmp_path / "gs.csv"
    _write(p, 59)
    assert G.section_html(p) == ""
    _write(p, 60)
    h = G.section_html(p)
    assert "GS-indeksen" in h and G.FLAG_TEXT in h and "uten kurs" in h
    assert "123.4567" not in h and "123,4567" not in h and "%" not in h.replace("100%", "")   # ingen ex-TECH, ingen %-hero
