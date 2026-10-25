from signaltool import learnloop as LL


def e(t, s, n):
    return {"ticker": t, "score": s, "points": {f"k{i}": 1.0 for i in range(n)}}


def test_tiebreak_order():
    c = [e("ZZZ", 1.0, 1), e("AAA", 1.0, 1), e("BBB", 1.0, 3), e("OLD", 1.0, 1), e("TOP", 2.0, 1)]
    r = [x["ticker"] for x in LL.rank_candidates(c, {"OLD"})]
    assert r == ["TOP", "OLD", "BBB", "AAA", "ZZZ"]


def test_exit_reason_tie(tmp_path, monkeypatch):
    log = tmp_path / "categories.csv"
    log.write_text("date,ticker,category,price,price_date\n2026-10-24,X,watch,1,2026-10-23\n")
    for k, v in {"CAT_LOG": log, "RAW": tmp_path / "r.csv", "EXITS": tmp_path / "e.csv", "DQ": tmp_path / "d.jsonl"}.items():
        monkeypatch.setattr(LL, k, v)
    monkeypatch.setattr(LL, "_closes", lambda *a, **k: {})
    ranked = [e(f"T{i:02d}", 1.0, 1) for i in range(60)] + [dict(e("X", 1.0, 1), stats={"close": 1})]
    for x in ranked[:60]:
        x["stats"] = {"close": 1}
    LL.record({"date": "2026-10-25", "tickers": ranked[:60]}, ranked)
    txt = (tmp_path / "e.csv").read_text()
    assert "lik score, kutt 60" in txt and ",1,1," in txt and "T59:ny:1" in txt and txt.startswith(",".join(LL.EXIT_COLS[:9]))


def test_tie_step():
    a, b = e("AAA", 1.0, 1), e("BBB", 1.0, 1)
    assert LL.tie_step(b, a, {"AAA", "BBB"}) == "3"
    assert LL.tie_step(b, a, {"AAA"}) == "1"
    assert LL.tie_step(e("BBB", 1.0, 1), e("CCC", 1.0, 2), set()) == "2"


def test_raw_append_only_with_run_id(tmp_path, monkeypatch):
    log = tmp_path / "categories.csv"
    log.write_text("date,ticker,category,price,price_date\n2026-10-24,T00,watch,1,2026-10-23\n")
    raw = tmp_path / "r.csv"
    raw.write_text("date,ticker,rank,score,types,close,close_date,index,r5,i5,r20,i20,r60,i60\n2026-10-25,OLD,1,2,a,1,,,,,,,,\n")
    for k, v in {"CAT_LOG": log, "RAW": raw, "EXITS": tmp_path / "e.csv", "DQ": tmp_path / "d.jsonl"}.items():
        monkeypatch.setattr(LL, k, v)
    monkeypatch.setattr(LL, "_closes", lambda *a, **k: {})
    snap = {"date": "2026-10-25", "tickers": [dict(e("T01", 1.0, 1), stats={"close": 1})]}
    ranked = snap["tickers"] + [dict(e("T00", 0.5, 1), stats={"close": 1})]
    monkeypatch.setenv("GITHUB_RUN_ID", "111"); monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    LL.record(snap, ranked)
    monkeypatch.setenv("GITHUB_RUN_ID", "222"); monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    LL.record(snap, ranked)
    import csv
    R = list(csv.DictReader(raw.open()))
    assert [(r["ticker"], r["run_id"], r["is_canonical"]) for r in R] == [("OLD", "", "true"), ("T01", "111", "false"), ("T01", "222", "true")]
    assert R[0]["score"] == "2"
    X = list(csv.DictReader((tmp_path / "e.csv").open()))
    assert [(x["ticker"], x["run_id"], x["is_canonical"]) for x in X] == [("T00", "111", "false"), ("T00", "222", "true")]


def test_logmerge_keeps_all_runs():
    from signaltool.logmerge import merge
    h = "date,ticker,run_id\n"
    assert merge(h + "d,A,2\n", h + "d,A,1\n", "x.csv") == h + "d,A,1\nd,A,2\n"


def test_congress_row():
    from signaltool import site_congress as C
    assert C.amount("$15,001 - $50,000") == "$15–50k" and C.amount("$15,001") == "–" and C.amount("$500,001 - $1,000,000") == "$500k–1M"
    p = C.parts({"member": "Cleo Fields (LA06)", "type": "P", "trans_date": "10/01/2026", "filing_date": "2026-10-22", "amount": "$1,001 - $15,000", "asset": "NVIDIA"})
    assert (p["name"], p["state"], p["type"], p["amount"], p["trade"], p["filed"], p["owner"]) == ("Cleo Fields", "LA", "Kjøp", "$1–15k", "01.10", "22.10", "–")
    snap = {"congress": [{"ticker": "X", "member": f"M{i} (CA01)", "type": "S", "trans_date": f"10/{i+1:02d}/2026", "url": f"u{i}"} for i in range(7)]}
    h = C.html(C.rows_for(snap, "X"))
    assert h.count("<li>") == 7 and "Vis alle (7)" in h and C.SRC in h and "parti" not in h.lower()


def test_coverage_cut_and_sources(monkeypatch):
    from signaltool import pipeline, decision as dec, site_sources as SS
    monkeypatch.setattr(dec, "apply", lambda snap: None)
    full = {"close": 1, "sma50": 1}
    dfull = {"sector": "x", "marketCap": 1, "trailingPE": 1}
    pos = [{"ticker": f"T{i:02d}", "score": 1.0, "stats": dict(full), "decision": dict(dfull)} for i in range(62)]
    pos[3] = {"ticker": "NPRO.OL", "score": 1.0, "stats": {}, "decision": {}}
    snap, st = {"tickers": pos[:60]}, {}
    pipeline._coverage_cut(snap, pos, st)
    t = [e["ticker"] for e in snap["tickers"]]
    assert t[-1] == "NPRO.OL" and snap["tickers"][-1]["unranked"] and "T60" in t and "T61" not in t and len(t) == 61
    status = {"Prices (yfinance)": "ok", "SEC EDGAR Form 4": "FAILED listing: 403", "US House PTR (congress trades)": "ok",
              "GDELT DOC 2.0 API": "FAILED 429", "SEC EDGAR 8-K full-text": "partial: 403", "GDELT 1.0 daily events": "ok", "News RSS": "ok",
              "Oslo Børs Newsweb": "ok", "Finanstilsynet short register": "ok"}
    us = SS.line({"ticker": "HAS", "themes": ["x"], "stats": {"close": 1}}, status)
    assert "mangler: GDELT DOC, SEC 8-K, SEC Form 4" in us and "src-bad" in us
    no = SS.line({"ticker": "VAR.OL", "themes": [], "stats": {"close": 1}}, status)
    assert "alle kilder ok" in no and "Form 4" not in no


def test_completed_periods(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text("date,ticker,types,is_canonical\n2026-01-02,A,pead,true\n2026-01-05,A,pead,true\n2026-04-30,B,x,true\n2026-05-01,C,x,false\n")
    assert LL.completed_periods(p) == (1, 1)


def test_sector_chip():
    from signaltool import site_sector as SC
    assert "Sektor: –" in SC.chip({"ticker": "ZZZ", "decision": {}})
    h = SC.chip({"ticker": "VAR.OL", "decision": {"sector": "Energy"}})
    assert "sektorer.html#energi" in h and "Sektor: Energi" in h
    assert "<a" not in SC.chip({"ticker": "HAS", "decision": {"sector": "Consumer Cyclical"}})
