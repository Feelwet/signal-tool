"""Skjemavalidering for flyt/noder.json og flyt/kanter.json. To lag sjekkes hver for seg."""
import copy
import json
from pathlib import Path

import pytest

from signaltool.flyt_schema import (
    FlytError,
    assert_valid,
    coverage,
    universe_tickers,
    validate,
)

FIX = Path(__file__).parent / "fixtures" / "flyt"


def _load():
    n = json.loads((FIX / "noder.json").read_text())
    k = json.loads((FIX / "kanter.json").read_text())
    s = json.loads((FIX / "scenarioer.json").read_text())
    return n, k, s


def test_fixture_valid_when_marked_fictive():
    n, k, s = _load()
    assert n["_fiktiv"] and k["_fiktiv"]
    assert not validate(n, k, s, allow_fictive=True)


def test_fixture_rejected_for_publish():
    n, k, s = _load()
    err = validate(n, k, s, allow_fictive=False)
    assert any("fiktive" in e for e in err)
    with pytest.raises(FlytError):
        assert_valid(n, k, s, allow_fictive=False)


def test_missing_kilde_url_fails_per_lag():
    n, k, s = _load()
    nodes = copy.deepcopy(n["noder"])
    raw = next(x for x in nodes if x["lag"] == "råvare" and x["status"] == "kilde")
    del raw["kilde_url"]
    err = validate({"noder": nodes, "_fiktiv": True}, k, s, allow_fictive=True)
    assert any("råvare" in e and "kilde_url" in e for e in err)

    nodes = copy.deepcopy(n["noder"])
    sel = next(x for x in nodes if x["lag"] == "selskap" and x["status"] == "kilde")
    del sel["kilde"]
    err = validate({"noder": nodes, "_fiktiv": True}, k, s, allow_fictive=True)
    assert any("selskap" in e and "kilde" in e for e in err)


def test_edge_missing_fields_fails():
    n, k, s = _load()
    edges = copy.deepcopy(k["kanter"])
    e0 = next(x for x in edges if x["status"] == "kilde")
    del e0["år"]
    del e0["enhet"]
    err = validate(n, {"kanter": edges, "_fiktiv": True}, s, allow_fictive=True)
    assert any("mangler kildefelt" in e for e in err)


def test_mangler_requires_grunn_not_url():
    n, k, s = _load()
    nodes = copy.deepcopy(n["noder"])
    miss = next(x for x in nodes if x["status"] == "mangler")
    miss["kilde_url"] = ""
    miss["grunn"] = "Mangler data for verdikjeden"
    assert not validate({"noder": nodes, "_fiktiv": True}, k, s, allow_fictive=True)
    miss["grunn"] = ""
    err = validate({"noder": nodes, "_fiktiv": True}, k, s, allow_fictive=True)
    assert any("grunn" in e for e in err)


def test_estimat_requires_metode():
    n, k, s = _load()
    nodes = copy.deepcopy(n["noder"])
    est = next(x for x in nodes if x["status"] == "estimat")
    est["metode"] = ""
    err = validate({"noder": nodes, "_fiktiv": True}, k, s, allow_fictive=True)
    assert any("metode" in e for e in err)


def test_coverage_from_universe_not_hardcoded():
    n, k, _ = _load()
    uni = universe_tickers(FIX / "list_members.csv")
    assert len(uni) == 8 and "NHY.OL" in uni and 61 not in (len(uni),)
    # uten godkjenning er alle kanter upubliserte
    cov0 = coverage(n, k, uni)
    assert cov0["n"] == 8
    assert cov0["råvare_n"] == 0 and cov0["selskap_n"] == 0
    assert cov0["statuslinje"] == "Råvaredata for 0 av 8 · Selskapsdata for 0 av 8"
    from signaltool.flyt_build import apply_godkjent
    k2 = {"kanter": apply_godkjent(k["kanter"], FIX / "godkjent.csv"), "_fiktiv": True}
    cov = coverage(n, k2, uni)
    assert cov["råvare_n"] == 1 and cov["selskap_n"] == 1
    assert cov["statuslinje"] == "Råvaredata for 1 av 8 · Selskapsdata for 1 av 8"
    assert "61" not in cov["statuslinje"]
    cov2 = coverage(n, k2, ["NHY.OL", "EQNR.OL"])
    assert cov2["statuslinje"] == "Råvaredata for 1 av 2 · Selskapsdata for 1 av 2"


def test_site_flyt_has_no_fictive_json():
    root = Path(__file__).resolve().parents[1] / "site" / "flyt"
    if not root.exists():
        return
    for p in root.glob("*.json"):
        raw = json.loads(p.read_text())
        assert not (isinstance(raw, dict) and raw.get("_fiktiv")), f"{p} er merket fiktiv"


def test_kontekst_status_is_valid_for_nodes_without_tall():
    from signaltool.flyt_schema import STATUS
    assert "kontekst" in STATUS
    n, k, s = _load()
    node = next(x for x in n["noder"] if x["status"] == "kontekst")
    assert node["id"] == "aluminium"
    assert node.get("verdi") in (None, "")
    assert not node.get("tall")
    assert not validate(n, k, s, allow_fictive=True)
    bad = copy.deepcopy(n)
    hit = next(x for x in bad["noder"] if x["id"] == "aluminium")
    hit["verdi"] = 100
    hit["enhet"] = "tonn"
    hit["år"] = 2024
    err = validate(bad, k, s, allow_fictive=True)
    assert any("kontekst" in e and "uten tall" in e for e in err)
