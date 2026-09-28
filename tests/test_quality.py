"""Data-quality filter, random-data control, robustness (fast-run log merge, stale sources, site sections, site check)."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from signaltool import data_quality as dq, null_control as N, categories as C, http, site_quality as Q, sitecheck

DAYS = pd.bdate_range("2025-01-01", periods=40)


def frame(close, vol=None):
    close = pd.Series(close, index=DAYS[:len(close)], dtype=float)
    return pd.DataFrame({"Close": close, "High": close * 1.01, "Low": close * 0.99,
                         "Volume": pd.Series(vol if vol is not None else [1000] * len(close), index=close.index)})


# ---------------------------------------------------------------- data quality
def test_spike_and_revert_is_repaired():
    c = [100, 101, 102, 150, 101.5, 103, 104]          # +47 % then back within 0.5 % of 102
    df, info = dq.clean_frame(frame(c))
    assert info["spikes"] == [str(DAYS[3].date())]
    assert df["Close"].iloc[3] == 102 and df["High"].iloc[3] == pytest.approx(102 * 1.01)
    assert df["Close"].pct_change().abs().max() < 0.05


def test_downward_spike_and_real_jump():
    assert dq.spike_mask(pd.Series([50, 50, 20, 49.5, 50.0])).tolist() == [False, False, True, False, False]
    # a real re-rating (jump that stays) and a jump that only partly reverts are kept
    assert not dq.spike_mask(pd.Series([100, 100, 140, 141, 142.0])).any()
    assert not dq.spike_mask(pd.Series([100, 100, 140, 120, 121.0])).any()
    # the last bar cannot be judged
    assert not dq.spike_mask(pd.Series([100, 100, 100, 160.0])).any()


def test_stale_runs_need_volume_and_length():
    c = [10, 11, 12, 12, 12, 12, 12, 13, 14]            # five identical closes
    assert dq.stale_runs(pd.Series(c, index=DAYS[:9]), pd.Series([5] * 9, index=DAYS[:9]))[0][2] == 5
    assert dq.stale_runs(pd.Series(c, index=DAYS[:9]), pd.Series([0] * 9, index=DAYS[:9])) == []   # no trading -> fine
    c4 = [10, 11, 12, 12, 12, 12, 13, 14, 15]           # only four
    assert dq.stale_runs(pd.Series(c4, index=DAYS[:9]), pd.Series([5] * 9, index=DAYS[:9])) == []


def test_clean_universe_summary_merges_without_double_count():
    dq.reset()
    data = {"A.OL": frame([100, 101, 102, 150, 101.5, 103, 104]), "B.OL": frame([10, 11, 12, 12, 12, 12, 12, 13])}
    for _ in range(2):   # the same universe cleaned twice in one run (oslo flags + theme maps)
        out, s = dq.clean_universe(data, "Oslo")
    assert s["n_spikes"] == 1 and s["n_stale"] == 1 and out["A.OL"]["Close"].iloc[3] == 102
    sm = dq.summary(str(DAYS[-1].date()))
    assert sm["n_spikes"] == 1 and sm["n_stale"] == 1 and sm["sources"]["Oslo"]["n_tickers"] == 2
    assert sm["sources"]["Oslo"]["spikes"][0][0] == "A.OL"
    json.dumps(sm)   # snapshot-safe
    dq.reset()


def test_clean_close_wide_keeps_gaps():
    W = pd.DataFrame({"X": [100, np.nan, 101, 180, 100.5, 102], "Y": [1, 2, 3, 4, 5, 6.0]}, index=DAYS[:6])
    out = dq.clean_close_wide(W)
    assert out["X"].iloc[3] == 101 and np.isnan(out["X"].iloc[1]) and out["Y"].equals(W["Y"])


# ---------------------------------------------------------------- retry
def test_retry_call_retries_errors_and_empty_results():
    calls = []
    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("boom")
        return [] if len(calls) == 2 else [1]
    assert http.retry_call(flaky, wait=0, ok=lambda r: len(r) > 0) == [1] and len(calls) == 3
    with pytest.raises(ValueError):
        http.retry_call(lambda: (_ for _ in ()).throw(ValueError("x")), tries=2, wait=0)


# ---------------------------------------------------------------- random-data control
def test_compare_percentile_and_p():
    null = np.arange(100) / 100.0              # 0.00 .. 0.99
    r = N.compare(0.95, null)
    assert r["percentile"] == 96 and r["p"] == pytest.approx(6 / 101)
    assert N.compare(0.02, null, higher_is_better=False)["p"] == pytest.approx(4 / 101)
    assert N.compare(float("nan"), null)["real"] is None


def _panel(effect, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for d in pd.bdate_range("2015-01-01", periods=60, freq="21B"):
        for i in range(50):
            weak = i < 10
            rows.append({"date": d, "ticker": f"T{i}", "weak": weak, "x60": rng.normal(effect if weak else 0.0, 0.05)})
    return pd.DataFrame(rows)


def test_oslo_weak_null_detects_real_effect_only():
    strong = N.oslo_weak(n_draws=200, panel=_panel(-0.05))["weak_px"]
    assert strong["n"] == 600 and strong["mean"]["p"] < 0.01 and strong["mean"]["percentile"] < 1
    none = N.oslo_weak(n_draws=200, panel=_panel(0.0))["weak_px"]
    assert none["mean"]["p"] > 0.05


def test_stratified_null_is_reproducible_and_matches_counts():
    P = _panel(0.0)
    S = P[P["weak"]]
    a = N.stratified_null(P, S, "x60", "date", n_draws=20, seed=7)
    b = N.stratified_null(P, S, "x60", "date", n_draws=20, seed=7)
    assert np.allclose(a[0], b[0]) and np.allclose(a[1], b[1])


def test_forward_log_null():
    days = pd.bdate_range("2026-01-01", periods=140)
    closes = {C.BENCH_US: pd.Series(100.0, index=days)}
    rows = []
    for k in range(12):
        winner, loser = f"W{k}", f"L{k}"
        closes[winner] = pd.Series([100 * 1.004 ** i for i in range(140)], index=days)
        closes[loser] = pd.Series([100 * 0.998 ** i for i in range(140)], index=days)
        d = days[k * 5].date().isoformat()
        rows += [{"date": d, "ticker": winner, "category": "kjop"}, {"date": d, "ticker": loser, "category": "watch"}]
    log = pd.DataFrame(rows).reindex(columns=C.LOG_COLS)
    r = N.forward(log, closes, min_n=10, h=20, n_draws=100)
    assert r["cats"]["kjop"]["n"] == 12 and r["cats"]["kjop"]["percentile"] > 90
    assert r["cats"]["watch"]["percentile"] < 10 and r["cats"]["hold"]["n"] == 0
    assert "real" not in N.forward(log, closes, min_n=50)["cats"]["kjop"]   # too few -> no numbers


def test_kontroll_file_committed_and_renders():
    K = N.load()
    assert {"pead_s", "weak_px"} <= set(K) and K["pead_s"]["mean"]["n_draws"] >= 200
    html = Q.kontroll_html({"track_record": {}})
    assert 'id="kontroll"' in html and "PEAD-S" in html and "Svak kurs" in html and "Fremoverloggen" in html


# ---------------------------------------------------------------- robustness
def test_fast_run_never_overwrites_full_rows(tmp_path):
    p = tmp_path / "categories.csv"
    tk = lambda t: {"ticker": t, "category": "watch", "score": 1, "stats": {"close": 10, "last_date": "2026-09-25"}, "cat_benchmark": C.BENCH_OSE, "cat_types": {}}
    C.append_log({"date": "2026-09-28", "tickers": [tk(f"T{i}.OL") for i in range(10)]}, p)
    C.append_log({"date": "2026-09-28", "fast": True, "tickers": [tk("T1.OL"), tk("NEW.OL")]}, p)
    df = C.read_log(p)
    assert len(df) == 11 and "NEW.OL" in set(df["ticker"])          # merged, nothing lost
    C.append_log({"date": "2026-09-28", "tickers": [tk("T1.OL")]}, p)   # a full re-run replaces the day
    assert len(C.read_log(p)) == 1


def test_mark_stale_marks_failed_sources(tmp_path):
    from signaltool import pipeline
    p = tmp_path / "last.json"
    pipeline.mark_stale({"A": "ok (1)", "B": "ok"}, "2026-09-27", p)
    st = {"A": "ok (2)", "B": "FAILED: timeout"}
    last = pipeline.mark_stale(st, "2026-09-28", p)
    assert st["B"] == "FAILED: timeout – ikke oppdatert (siste: 2026-09-27)" and last["A"] == "2026-09-28"
    st2 = {"C": "FAILED: x"}
    pipeline.mark_stale(st2, "2026-09-28", p)
    assert "siste: ukjent" in st2["C"]


def test_safe_source_never_raises():
    from signaltool import pipeline
    st = {}
    def boom():
        raise RuntimeError("nede")
    assert pipeline._safe(st, "X", boom, "default") == "default" and st["X"].startswith("FAILED: RuntimeError")
    assert pipeline._safe(st, "Y", lambda: ([1], "ok (1)"), None) == [1] and st["Y"] == "ok (1)"
    assert pipeline._safe(st, "Z", lambda: ("a", "b", "ok"), None) == ("a", "b")


def test_failing_section_shows_stale_card(tmp_path, monkeypatch):
    monkeypatch.setattr(Q, "SECTION_OK", tmp_path / "ok.json")
    assert Q.section("S", lambda: "<p>x</p>", snap={"date": "2026-09-27"}) == "<p>x</p>"
    out = Q.section("S", lambda: 1 / 0, snap={"date": "2026-09-28"})
    assert "ikke oppdatert" in out and "2026-09-27" in out and "S" in Q.FAILED_SECTIONS
    assert "ikke oppdatert (siste: 2026-09-26)" in Q.source_note({"status": {"Newsweb": "FAILED: x"}, "source_last_ok": {"Newsweb": "2026-09-26"}}, "Newsweb")


SNAP = Path(__file__).resolve().parent.parent / "site" / "data.json"


@pytest.mark.skipif(not SNAP.exists(), reason="no snapshot available")
def test_build_survives_broken_section_and_passes_check(tmp_path, monkeypatch):
    from signaltool import site, site_extra as X
    snap = json.loads(SNAP.read_text())
    snap["data_quality"] = {"asof": "2026-09-28", "rules": {"spike": .25, "revert": .05, "stale_n": 5, "stale_window": 260},
                            "sources": {"Oslo": {"n_tickers": 2, "n_spikes": 1, "n_spikes_12m": 1, "n_stale": 1,
                                                 "spikes": [["A.OL", "2026-01-02"]], "stale": [["B.OL", "2026-09-01", "2026-09-07", 5]]}},
                            "n_spikes": 1, "n_spikes_12m": 1, "n_stale": 1}
    monkeypatch.setattr(site, "SITE", tmp_path / "site")
    monkeypatch.setattr(Q, "SECTION_OK", tmp_path / "ok.json")
    monkeypatch.setattr(X, "focus_html", lambda s: 1 / 0)          # a broken section must not break the build
    site.build(snap)
    out = tmp_path / "site"
    idx = (out / "index.html").read_text()
    assert "ikke oppdatert" in idx and "Datakvalitet i dag" in idx
    k = (out / "kilder.html").read_text()
    assert 'id="datakvalitet"' in k and "A.OL 2026-01-02" in k and "B.OL (5 dager" in k and 'id="kontroll"' in k
    assert sitecheck.check(out) == []
    (out / "kilder.html").write_text("<html></html>")
    assert any("datakvalitet" in p for p in sitecheck.check(out))
    (out / "index.html").unlink()
    assert sitecheck.check(out) == [f"{out / 'index.html'} mangler"]


def test_oslo_universe_list_available_without_backtest_cache():
    from signaltool import oslo_flags as O
    t = O.universe_tickers()      # CI has no data/cache/universe -> the committed list must be enough
    assert len(t) >= 200 and "OSEBX.OL" in t and all(x.endswith(".OL") for x in t)
