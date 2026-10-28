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
    assert 'data-v="2026-10-08"' in S.cell(s) and 'data-sort="2026-10-08">siden 08.10<' in S.cell(s)
    assert "siden 08.10" in S.mobile(s) and "· 1 dag" in S.line(s)
    assert S.line(None) == "" and S.mobile(None) == "" and "–" in S.cell(None) and 'data-sort=""' in S.cell(None)


def test_dato_sort_js_uxbot():
    """UxBot 27.10: ISO data-sort, første klikk nyeste (▼), URL ?sort=dato_*, tomme nederst, poeng-tiebreak."""
    js, css = S.JS, S.CSS
    assert "data-sort" in S.cell({"since": "2026-10-08"}) and "dataset.sort" in js
    assert "dato_desc" in js and "dato_asc" in js and "history.replaceState" in js
    assert "descending" in js and "ascending" in js
    assert "score(b)-score(a)" in js
    assert "if(!x)return 1;if(!y)return -1" in js
    assert 'font-size:12px' in css and 'content:" ▼"' in css and 'content:" ▲"' in css


def test_return():
    s = {"since": "2026-10-08", "price": 17.0, "price_date": "2026-10-06", "category": "watch", "days": 17, "list_days": 17, "illiquid": True}
    idx = {"OSEBX.OL": {"2026-10-06": 100.0, "2026-10-23": 101.0}}
    r = S.ret(s, 17.8, "2026-10-23", idx, "EIOF.OL")
    assert S.pct(r["r"]) == "+4,7 %" and S.pp(r["ex"]) == "+3,7 pp" and "vs OSEBX +3,7 pp" in S.ret_inner(r) and r["illiquid"]
    assert "+4,7 %" in S.line(s, "", r) and "⚠" in S.ret_cell(r) and "rup" in S.ret_cell(r)
    assert S.ret(dict(s, list_days=0), 17.8, "2026-10-23", idx, "EIOF.OL")["r"] > 0
    assert S.ret(s, None, None, idx, "EIOF.OL") is None and S.ret_cell(None).count("–") == 1
    assert '<span class="rex">–</span>' in S.ret_inner(S.ret(s, 17.8, "2026-10-23", {}, "EIOF.OL"))
    assert S.bench_for("EIOF.OL")[1] == "OSEBX"


def test_nokkeltall_missing_and_etf():
    from signaltool import nokkeltall as N
    e = {"ticker": "IBM", "decision": {"close": 250.0, "currency": "USD", "sharesOutstanding": 9.6e8, "trailingEps": -1.0, "info_date": "2026-10-25"}}
    n = N.compute(e)
    v = {f["key"]: f["value"] for f in n["fields"]}
    assert len(n["fields"]) == 10 and v["mcap"] == "240 mrd. USD" and v["pe"] == "Negativ" and v["rev"] is None
    h = N.html(n)
    assert "Tallet mangler hos kilden." in h and "Ikke tilgjengelig" not in h and "oppdatert 25.10" in h
    etf = N.compute({"ticker": "SPY", "decision": {"quoteType": "ETF"}})
    assert {f["key"] for f in etf["fields"]} == {"mcap", "rev", "dps", "yld", "next"}


def test_sparkline_needs_4_consecutive_quarters_and_ebit_never_derived():
    import pandas as pd
    from signaltool import nokkeltall as N, decision as D
    cols = pd.to_datetime(["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30"])
    q = pd.DataFrame([[10, 9, 8, 7, 6], [1.0, 0.9, float("nan"), 0.7, 0.6], [2, 2, 2, float("nan"), 2]],
                     index=["Total Revenue", "Diluted EPS", "EBIT"], columns=cols)
    assert len(D._q_run(q, ("Total Revenue",))) == 5 and len(D._q_run(q, ("Diluted EPS",))) == 2
    assert D.ebit_ttm(None, q) is None          # ett kvartal mangler -> ingen EBIT
    e = {"ticker": "X", "decision": {"close": 10.0, "currency": "USD", "totalRevenue": 34.0, "operatingMargins": 0.2,
                                     "rev_q": D._q_run(q, ("Total Revenue",)), "eps_q": D._q_run(q, ("Diluted EPS",))}}
    n = N.compute(e); f = {x["key"]: x for x in n["fields"]}
    assert f["ebit"]["value"] is None and "quarters" in f["rev"] and "quarters" not in f["eps"]
    assert "siste 5 kv." in N.html(n)


def test_decision_keeps_lists_bools_and_text():
    import inspect
    from signaltool import decision as D
    src = inspect.getsource(D)
    assert '"info_date"' in src and "isinstance(v, (bool, list))" in src
