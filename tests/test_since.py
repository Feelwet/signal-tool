"""«På lista siden …» fra logs/categories.csv."""
from pathlib import Path
from signaltool import since as S

LOG = Path(__file__).resolve().parent.parent / "logs" / "categories.csv"


def _r(d, t="A", c="watch", p="10", pd=None):
    return {"date": d, "ticker": t, "category": c, "price": p, "price_date": pd or d}


def test_eiof_from_real_log():
    s = S.compute(S.load(LOG), "2026-10-25")["EIOF.OL"]
    assert s["since"] == "2026-10-08" and s["price"] == 17.0 and s["price_date"] == "2026-10-06" and s["days"] == 17
    assert S.line(s) == '<p class="since mut">På lista siden 08.10 · inn på 17,00 (sluttkurs 06.10) · Følg i 17 dager</p>'


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
    assert s["since"] == "2026-10-01" and s["days"] == 2 and "Hold i 2 dager" in S.line(s)


def test_cells_and_mobile():
    s = {"since": "2026-10-08", "price": 17.0, "price_date": "2026-10-06", "category": "watch", "days": 1}
    assert 'data-v="2026-10-08">08.10<' in S.cell(s) and "siden 08.10" in S.mobile(s) and "Følg i 1 dag" in S.line(s)
    assert S.line(None) == "" and S.mobile(None) == "" and "–" in S.cell(None)
