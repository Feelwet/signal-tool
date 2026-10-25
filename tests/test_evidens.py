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
    assert "Negativ EBIT er bare kjent for 2 av 3" in h
    assert V.focus_html(s).count('<li class="evrow"><span class="evb') == 1


def test_summary_zero_kjop():
    L = V.summary(_snap())
    assert len(L) == 4 and L[2] == "Ingen kjøp-kandidater i dag, det er normalt." and "2 av 3" in L[1]
    assert "1 kjøp-kandidat" in V.summary(_snap(1))[2]


def test_mapping_single_place():
    assert all(k in V.evidens for k in V.RED_FLAGS + ["pead", "theme", "gdelt", "unusual_volume"])
    assert V.level("unknown") == "oppm"
