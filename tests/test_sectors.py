from datetime import date
from signaltool import sectors as S

GOOD = {"rev_cagr3": 0.15, "fcf": 1e9, "roic": 0.2, "shares_cagr3": 0.0, "net_debt_ebitda": 1.0}
BANK = {"roe": 0.14, "cost_income": 0.40, "shares_cagr3": 0.0}


def test_clear_when_all_rules_hold():
    assert S.evaluate(GOOD)["status"] == "CLEAR"
    assert S.evaluate({**GOOD, "net_debt_ebitda": -1.5})["status"] == "CLEAR"


def test_fail_beats_missing_and_counts():
    r = S.evaluate({**GOOD, "roic": 0.05, "fcf": None})
    assert r["status"] == "FAIL" and r["failed"] == ["roic"] and r["missing"] == ["fcf"]
    r = S.evaluate({**GOOD, "fcf": None})
    assert r["status"] == "MISSING" and r["missing"] == ["fcf"]
    assert len(S.evaluate({})["missing"]) == 5


def test_bank_missing_cet1_and_loan_loss_is_not_clear():
    r = S.evaluate(BANK, bank=True)
    assert r["status"] == "MISSING"
    assert set(r["missing"]) == {"cet1", "loan_loss"} and not r["failed"]
    full = {**BANK, "loan_loss": 0.001, "cet1": 0.18, "cet1_req": 0.16}
    assert S.evaluate(full, bank=True)["status"] == "CLEAR"
    assert S.evaluate({**full, "cost_income": 0.6}, bank=True)["status"] == "FAIL"
    assert "growth" not in S.evaluate(full, bank=True)["checks"]


def test_stale():
    assert S.is_stale("2026-01-01", date(2026, 10, 24)) and not S.is_stale("2026-10-01", date(2026, 10, 24))


def test_pages_render():
    fund = {"asof": "2026-10-24", "source": "test", "data": {"FRO.OL": {**GOOD, "name": "Frontline"}, "DNB.OL": BANK}}
    assert S.counts("shipping", fund)["CLEAR"] == 1
    assert S.counts("bank", fund)["CLEAR"] == 0
    for k in S.SECTORS:
        h = S.sector_html(k, fund)
        assert "Målbare drivere" in h and "ikke investeringsråd" in h and "Kjøp<" not in h and "Feilet" not in h
        assert "ikke bakovertestet" in h.lower() and "Frosset 24.10" in h
    b = S.sector_html("bank", fund)
    assert "ROE &gt;10 %" in b and "ROIC" not in b.split("<table")[2] and "kvartalsrapport" in b
    i = S.index_html(fund)
    assert "sektor_shipping.html" in i and "FLAG: n&lt;5" in i


def test_tv_url_builder():
    assert S.tv_url("FRO.OL") == "https://www.tradingview.com/chart/?symbol=OSL%3AFRO"
    assert S.tv_symbol("NORBT.OL") == "OSL:NORBT"
    assert S.tv_url("BRK-B") is None and S.tv_url("AAPL") is None and S.tv_url("") is None
    assert S.tv_url("SUBC.OL").endswith("OSL%3ASUBC")
    link = S.tv_ticker("FRO.OL")
    assert 'target="_blank"' in link and 'rel="noopener"' in link and "↗" in link and "FRO.OL" in link
    assert S.tv_ticker("AAPL") == "<b>AAPL</b>" and S.tv_ext("AAPL") == ""
