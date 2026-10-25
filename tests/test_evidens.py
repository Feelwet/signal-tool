import json
from signaltool import evidens as V


def _snap(nk=0):
    return {"regime": {"OSEBX.OL": {"below": False, "high_vol": False, "risk_off": False}},
            "oslo_flags_meta": {"asof": "2026-10-23", "newsweb_ok": True},
            "oslo_universe_flags": [{"ticker": "A.OL", "flags": {"weak_px": "svak", "high_vol": "vol"}, "asof": "2026-10-23", "ebit_known": True},
                                    {"ticker": "B.OL", "flags": {}, "asof": "2026-10-23", "ebit_known": False},
                                    {"ticker": "C.OL", "flags": {"neg_ebit": "x"}, "asof": "2026-10-23", "ebit_known": True}],
            "tickers": [{"ticker": "X", "category": "kjop"}] * nk, "briefing": {"focus": [{"title": "T1", "link": "tema/a"}]}}


def test_levels_from_file(tmp_path):
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"svak_momentum_12_1": {"evidens": "eksperimentell", "n": 7.9, "effekt_60d": -0.0326, "t_is": -1.47, "t_oos": -3.23},
                             "negativ_ebit_ttm": {"evidens": "ikke_testet"}}))
    r = V.load_red(p)
    assert r["weak_px"][0] == "eksp" and "ikke bestått testkravet: t −1,5 før 2018" in r["weak_px"][1].lower()
    assert r["neg_ebit"][0] == "litteratur"
    assert r["placement"][0] == "litteratur" and "ikke satt" in r["placement"][1]


def test_badge_first_and_no_robust():
    s = _snap()
    h = V.red_page(s) + V.red_top5(s) + V.summary_html(s) + V.focus_html(s)
    assert "robust" not in h.lower()
    assert "Røde flagg Oslo · verdt å undersøke" in h and "Se alle (2)" in h
    assert "negativ EBIT er bare kjent for 2 av 3" in h
    assert V.focus_html(s).count('<li class="evrow"><span class="evb') == 1


def test_summary_zero_kjop():
    L = V.summary(_snap())
    assert len(L) == 4 and L[2] == "Ingen kjøp-kandidater i dag, det er normalt." and "2 av 3" in L[1]
    assert "1 kjøp-kandidat" in V.summary(_snap(1))[2]


def test_mapping_single_place():
    assert all(k in V.evidens for k in V.RED_FLAGS + ["pead", "theme", "gdelt", "unusual_volume"])
    assert V.level("unknown") == "oppm"


def test_sort_and_fold():
    s = _snap()
    s["oslo_universe_flags"] = [{"ticker": f"T{i:02d}.OL", "flags": {"neg_ebit": "x"}, "asof": "d"} for i in range(20)] + [
        {"ticker": "Z.OL", "flags": {"high_vol": "v"}, "asof": "d"}, {"ticker": "Y.OL", "flags": {"weak_px": "w"}, "asof": "d"},
        {"ticker": "X.OL", "flags": {"placement": "p", "neg_ebit": "e"}, "asof": "d"}]
    assert [r["ticker"] for r in V.red_rows(s)[:4]] == ["Y.OL", "Z.OL", "X.OL", "T00.OL"]
    h = V.red_page(s)
    assert "2+ flagg (0)" in h and "1 flagg (3), ingen målt underavkastning" in h and "Bare negativ EBIT (20), ikke testet" in h and "1 flagg + EBIT" in h and "Sortert etter" not in h


def test_two_plus_text():
    t = V.evidens["two_plus"][1]
    assert "−6,9 %" in t and "t −3,7" in t and "Ikke bestått testkravet: t −0,8 i 2014–18" in t and "robust" not in t.lower()


def test_ebit_not_counted():
    r = {"flags": {"weak_px": "w", "high_vol": "v", "placement": "p", "neg_ebit": "e"}}
    assert V.ntest(r) == 3 and V.nlabel(r) == "3 flagg + EBIT" and V.nlabel({"flags": {"neg_ebit": "e"}}) == "bare EBIT"
