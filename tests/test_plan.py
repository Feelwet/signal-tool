from signaltool import plan as P


def _e(**kw):
    e = {"ticker": "XYZ", "category": "hold", "cat_types": {"insider_cluster": "SEC Form 4"}, "points": {"insider_cluster": 1.0},
         "themes": [], "stats": {"ret_5d": 0.02, "ret_20d": 0.12, "adv20": 5e7},
         "decision": {"close": 100.0, "atr14": 2.0, "sma50": 90.0, "sma20": 96.0, "stop_atr": 96.0, "hi20": 104.0, "hi52": 120.0,
                      "vol60": 0.3, "next_earnings": "2026-11-01", "days_to_earnings": 30, "rel_bench_20d": 0.05}}
    e.update(kw)
    return e


def test_levels_hold_waits_for_pullback_and_stop_below_entry():
    lv = P.levels(_e())
    assert lv["entry_how"].startswith("vent") and abs(lv["entry"] - 96.0) < 1e-9
    assert lv["stop"] < lv["entry_lo"]
    assert abs(lv["stop"] - 92.0) < 1e-9          # entry - 2xATR (92) is stricter than the 50d average (90)
    assert abs(lv["target_rr"] - (96 + 2 * 4)) < 1e-9
    assert abs(lv["size"] - min(P.MAX_POSITION, 0.01 / (4 / 96))) < 1e-9


def test_levels_size_capped_and_halved():
    e = _e(category="kjop", stats={"ret_5d": 0.0, "ret_20d": 0.02, "adv20": 1e6})
    e["decision"].update(sma50=99.5, stop_atr=96.0, vol60=0.8)
    lv = P.levels(e)
    assert lv["entry"] == 100.0 and abs(lv["stop"] - 96.0) < 1e-9   # 50d avg (99.5) is inside the entry zone -> 2xATR
    assert abs(lv["size"] - P.MAX_POSITION / 4) < 1e-9 and len(lv["size_reasons"]) == 2


def test_levels_missing_inputs():
    assert P.levels({"ticker": "X", "decision": {}}) == {}


def test_thesis_uses_real_levels():
    th = P.thesis(_e())
    assert "innsidekjøp-klynge" in th["tese"]
    assert "104.00" in th["bekreftes"]
    assert "2026-11-01" in th["avkreftes"] and "92.00" in th["avkreftes"]


def test_signal_keys_include_category_and_baseline():
    ks = P.signal_keys(_e(ticker="ABC.OL", points={"unusual_volume": 1.0}, cat_types={}, category="watch",
                          insider_oslo={"counts": {"kjøp": 2}}))
    assert ks == ["unusual_volume_ose", "ose_insider_buy", "baseline_ose"]
