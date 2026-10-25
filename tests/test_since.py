"""«På lista siden …» fra logs/categories.csv."""
from pathlib import Path
from signaltool import since as S

LOG = Path(__file__).resolve().parent.parent / "logs" / "categories.csv"


def _r(d, t="A", c="watch", p="10", pd=None):
    return {"date": d, "ticker": t, "category": c, "price": p, "price_date": pd or d}


def test_eiof_from_real_log():
    s = S.compute(S.load(LOG), "2026-10-25")["EIOF.OL"]
    assert s["since"] == "2026-10-08" and s["price"] == 17.0 and s["price_date"] == "2026-10-06" and s["days"] == 17
    assert S.line(s) == '<p class="since mut">Siden 08.10 · inn 17,00 (06.10) · 17 dager</p>'


def test_days_are_calendar_days_not_rows():
    rows = [_r("2026-10-01"), _r("2026-10-05"), _r("2026-10-10")]
    assert S.compute(rows, "2026-10-10")["A"]["days"] == 9


def test_comeback_uses_return_date_and_its_price():
    other = [_r(d, "B") for d in ("2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05")]
    rows = other + [_r("2026-10-01", p="5"), _r("2026-10-04", p="7", pd="2026-10-03"), _r("2026-10-05", p="8")]
    s = S.compute(rows, "2026-10-05")["A"]
    assert s["since"] == "2026-10-04" and s["price"] == 7.0 and s["price_date"] == "2026-10-03"


def test_single_missed_run_does_not_break():
    other = [_r(d, "B") for d in ("2026-10-01", "2026-10-02", "2026-10-03")]
    rows = other + [_r("2026-10-01"), _r("2026-10-03")]
    assert S.compute(rows, "2026-10-03")["A"]["since"] == "2026-10-01"


def test_category_days_from_current_category():
    rows = [_r("2026-10-01", c="watch"), _r("2026-10-02", c="hold"), _r("2026-10-03", c="hold")]
    s = S.compute(rows, "2026-10-04")["A"]
    assert s["since"] == "2026-10-01" and s["days"] == 2 and "2 dager" in S.line(s)


def test_cells_and_mobile():
    s = {"since": "2026-10-08", "price": 17.0, "price_date": "2026-10-06", "category": "watch", "days": 1}
    assert 'data-v="2026-10-08">08.10<' in S.cell(s) and "siden 08.10" in S.mobile(s) and "· 1 dag" in S.line(s)
    assert S.line(None) == "" and S.mobile(None) == "" and "–" in S.cell(None)


def test_return():
    s = {"since": "2026-10-08", "price": 17.0, "price_date": "2026-10-06", "category": "watch", "days": 17, "list_days": 17, "illiquid": True}
    idx = {"OSEBX.OL": {"2026-10-06": 100.0, "2026-10-23": 101.0}}
    r = S.ret(s, 17.8, "2026-10-23", idx, "EIOF.OL")
    assert S.pct(r["r"]) == "+4,7 %" and S.pct(r["ex"]) == "+3,7 %" and r["illiquid"]
    assert "+4,7 %" in S.line(s, "", r) and "⚠" in S.ret_cell(r) and "rup" in S.ret_cell(r)
    assert S.ret(dict(s, list_days=4), 17.8, "2026-10-23", idx, "EIOF.OL") is None
    assert S.ret(s, None, None, idx, "EIOF.OL") is None and S.ret_cell(None).count("–") == 1
    assert "mot" not in S.ret_inner(S.ret(s, 17.8, "2026-10-23", {}, "EIOF.OL"))
