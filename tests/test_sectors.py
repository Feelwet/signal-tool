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


def test_every_column_has_info_text():
    fund = {"asof": "2026-10-24", "source": "t", "data": {}}
    for k in S.SECTORS:
        for key, _, _ in S.rules_for(k):
            assert S.INFO.get(key) and S.INFO[key][1]
        h = S.sector_html(k, fund)
        assert h.count('class="info"') == len(S.rules_for(k)) + 2
        assert 'role="tooltip"' in h and "aria-describedby" in h


def test_calendar_json_embedded_and_valid():
    import json, re
    from signaltool import calendar_view as CV
    cal = [{"date": "2026-10-28", "time": "20:00", "source": "Federal Reserve", "title": "FOMC", "kind": "sentralbank"},
           {"date": "2026-11-05", "time": "", "source": "Selskap (estimert)", "title": "Q3", "kind": "resultat", "ticker": "SUBC.OL"},
           {"date": "2026-10-29", "time": "08:00", "source": "SSB", "title": "KPI </script>", "kind": "makro"}]
    h = CV.calendar_html(cal, "<table></table>")
    m = re.search(r'<script type="application/json" id="cal-data">(.*?)</script>', h, re.S)
    ev = json.loads(m.group(1))
    assert [e["type"] for e in ev] == ["sentralbank", "resultat", "makro"]
    assert ev[1]["follow"] and ev[1]["est"] and "OSL%3ASUBC" in ev[1]["tv"]
    assert 'aria-label="Forrige måned"' in h and 'aria-label="Neste måned"' in h and "<table></table>" in h


def test_calendar_log_merge_and_coverage(tmp_path):
    from datetime import date, timedelta
    from signaltool import calendar_view as CV
    p = tmp_path / "cal.json"
    past = (date.today() - timedelta(days=3)).isoformat()
    CV.merge_log([{"date": past, "time": "", "source": "X", "title": "gammel", "kind": "makro"}], p)
    out = CV.merge_log([{"date": date.today().isoformat(), "time": "", "source": "Y", "title": "ny", "kind": "makro"}], p)
    assert [e["title"] for e in out] == ["gammel", "ny"]
    h = CV.calendar_html(out, "")
    assert "Data rekker til " + date.today().isoformat() in h and "past" in h


def test_fold_tables():
    from signaltool import site
    rows = "".join(f"<tr><td>{i}</td></tr>" for i in range(20))
    h = site.fold_tables("<table><tr><th>h</th></tr>" + rows + "</table>")
    assert h.count('class="xscroll"') == 2 and "Vis alle (20 rader)" in h and "<details" in h


def test_source_state_and_log(tmp_path):
    import json
    from signaltool import site_extra as X, pipeline as P
    st = {"a": "ok (5)", "b": "FAILED: 403 Client Error", "c": "not automated (x)", "d": "fx ok; press rss ok (5)", "e": "partial: 403"}
    assert [X.source_state(v) for v in st.values()] == ["ok", "fail", "skip", "ok", "fail"]
    p = tmp_path / "s.jsonl"
    P.append_source_status(st, p)
    rows = [json.loads(l) for l in p.read_text().splitlines()]
    assert len(rows) == 5 and rows[1]["code"] == "403" and rows[0]["state"] == "ok"
