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
    assert "lik score, kutt 60" in (tmp_path / "e.csv").read_text()
