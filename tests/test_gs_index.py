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
    assert set(G.lists_by_date(rows)["2026-09-27"]) == {"A.OL", "T.OL"}   # tema er med (AnalBot 26.10)
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
            w.writerow({"date": f"2026-{i:04d}", "gs_index": 100 + i % 3, "benchmark": 100, "n_members": 50, "n_no_price": 2, "n_invalid": 0, "flag": "", "gs_with_tech": 123.4567})


def test_hide_gate(tmp_path):
    p = tmp_path / "gs.csv"
    _write(p, 59)
    assert G.section_html(p) == ""
    _write(p, 60)
    h = G.section_html(p)
    assert "GS-indeksen" in h and G.FLAG_TEXT in h and "uten kurs" in h
    assert "123.4567" not in h and "123,4567" not in h and "%" not in h.replace("100%", "")   # ingen ex-TECH, ingen %-hero


def test_rangert_filter_and_flag_days():
    rows = [{"date": "2026-09-27", "ticker": "A.OL", "category": "watch"},
            {"date": "2026-09-28", "ticker": "A.OL", "category": "watch", "rangert": "1"},
            {"date": "2026-09-28", "ticker": "B.OL", "category": "watch", "rangert": "0"}]
    lists = G.lists_by_date(rows)
    assert set(lists["2026-09-28"]) == {"A.OL"}            # rangert=0 («Ikke rangert») er ikke med
    assert G.unflagged_dates(rows) == {"2026-09-28"}
    yfp = {"A.OL": {d: 100.0 for d in DAYS}}
    r = G.compute(lists, DAYS, {}, yfp, EX, IDX, known=G.unflagged_dates(rows))
    assert [x["flag"] for x in r] == ["FLAG", "", "", ""]   # 28.09 bruker lista fra 27.09 (uten rangert-felt)


def test_invalid_jump_excluded_not_a_loss():
    lists = {"2026-09-27": {"A.OL": row("A.OL"), "B.OL": row("B.OL")}}
    yfp = {"A.OL": {"2026-09-28": 5.50, "2026-09-29": 2.178, "2026-09-30": 2.178, "2026-10-01": 2.178},
           "B.OL": {"2026-09-28": 100.0, "2026-09-29": 110.0, "2026-09-30": 110.0, "2026-10-01": 110.0}}
    inv = []
    r = G.compute(lists, DAYS, {}, yfp, EX, IDX, invalid_log=inv)
    assert r[1]["n_invalid"] == 1 and inv[0]["ticker"] == "A.OL" and inv[0]["date"] == "2026-09-29"
    assert 109 < r[1]["gs_index"] < 110   # bare B (+10 %) teller; A sitt −60 % er ikke et tap
    r2 = G.compute(lists, DAYS, {}, yfp, EX, IDX, splits=frozenset({("A.OL", "2026-09-29")}))
    assert r2[1]["n_invalid"] == 0


def test_otc_on_us_side(tmp_path, monkeypatch):
    import json
    c = tmp_path / "ex.json"
    c.write_text(json.dumps({"NOKBF": "PNK"}))
    import signaltool.since as S
    monkeypatch.setattr(S, "bench_for", lambda t: None)
    assert G._exch(["NOKBF"], c) == {"NOKBF": "nyse"}


def test_append_log_writes_rangert(tmp_path):
    from signaltool import categories as C
    p = tmp_path / "c.csv"
    old = "date,ticker,category,price,price_date,benchmark,score,n_types,types,flags\n2026-09-27,A.OL,watch,1.0,2026-09-25,OSEBX.OL,1.0,0,,\n"
    p.write_text(old)
    snap = {"date": "2026-10-27", "tickers": [{"ticker": "B.OL", "category": "watch"}, {"ticker": "C.OL", "category": "watch", "unranked": True}]}
    df = C.append_log(snap, p)
    assert "rangert" in df.columns
    got = {r["ticker"]: r["rangert"] for _, r in df.iterrows()}
    assert got.get("B.OL") == 1 and got.get("C.OL") == 0
    assert str(df[df.ticker == "A.OL"]["rangert"].iloc[0]) == "nan"   # gamle rader skrives ikke om


def test_logmerge_new_column():
    from signaltool.logmerge import merge
    theirs = "date,ticker,x\n2026-10-01,A,1\n2026-10-02,A,2\n"
    ours = "date,ticker,x,rangert\n2026-10-01,A,1,\n2026-10-27,B,3,1\n"
    assert merge(ours, theirs, "c.csv") == "date,ticker,x,rangert\n2026-10-01,A,1,\n2026-10-02,A,2,\n2026-10-27,B,3,1\n"


def test_append_log_rangert_integer_and_old_rows_untouched(tmp_path):
    from signaltool import categories as C
    p = tmp_path / "c.csv"
    old = ("date,ticker,category,price,price_date,benchmark,score,n_types,types,flags,rangert\n"
           "2026-09-27,A.OL,watch,1.0,2026-09-25,OSEBX.OL,1.0,0,,,\n"
           "2026-10-26,A.OL,watch,1.0,2026-10-23,OSEBX.OL,1.0,0,,,1.0\n"
           "2026-10-26,Z.OL,watch,2.0,2026-10-23,OSEBX.OL,,0,,,0.0\n")
    p.write_text(old)
    snap = {"date": "2026-10-27", "tickers": [{"ticker": "B.OL", "category": "watch"}, {"ticker": "C.OL", "category": "watch", "unranked": True}]}
    C.append_log(snap, p)
    lines = p.read_text().splitlines()
    assert "\n".join(lines[:4]) + "\n" == old                     # eksisterende rader byte-for-byte uendret
    assert lines[4].endswith(",1") and lines[5].endswith(",0")    # nye rader: heltall, ikke 1.0/0.0
    assert not any(l.endswith((",1.0", ",0.0")) for l in lines[4:])


def test_rangert_reader_accepts_float_int_and_empty():
    from signaltool.categories import rangert_val
    assert [rangert_val(v) for v in ("1", "1.0", 1, 1.0, "0", "0.0", 0, "", None, float("nan"))] == [1, 1, 1, 1, 0, 0, 0, None, None, None]
    rows = [{"date": "2026-10-26", "ticker": "A.OL", "category": "watch", "rangert": "1.0"},
            {"date": "2026-10-26", "ticker": "X.OL", "category": "watch", "rangert": "0.0"},
            {"date": "2026-10-27", "ticker": "A.OL", "category": "watch", "rangert": "1"},
            {"date": "2026-10-27", "ticker": "X.OL", "category": "watch", "rangert": "0"},
            {"date": "2026-10-28", "ticker": "A.OL", "category": "watch", "rangert": ""}]
    lists = G.lists_by_date(rows)
    assert set(lists["2026-10-26"]) == {"A.OL"} and set(lists["2026-10-27"]) == {"A.OL"}   # begge dagene telles
    assert set(lists["2026-10-28"]) == {"A.OL"}                                             # tomt felt: med, men FLAG
    assert G.unflagged_dates(rows) == {"2026-10-26", "2026-10-27"}
