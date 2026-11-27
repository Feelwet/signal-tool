"""AnalBot 27.11: publisert er false som standard og settes bare fra flyt/godkjent.csv."""
import csv
import json
from pathlib import Path

import pytest

from signaltool.flyt_build import apply_godkjent, apply_godkjent_file, convert
from signaltool.flyt_schema import FlytError, coverage, ticker_has_published, universe_tickers, validate

FIX = Path(__file__).parent / "fixtures" / "flyt"


def _load():
    n = json.loads((FIX / "noder.json").read_text())
    k = json.loads((FIX / "kanter.json").read_text())
    return n, k


def test_fixture_edges_default_unpublished():
    _, k = _load()
    assert k["kanter"] and all(e.get("publisert") is False for e in k["kanter"])


def test_convert_never_sets_publisert_true(tmp_path):
    dest = tmp_path / "flyt"
    # selv om kilden har en kolonne publisert=true, skal konverteringen tvinge false
    src = tmp_path / "csv"
    src.mkdir()
    # kopier fixture-csv og injiser kolonnen
    import shutil
    shutil.copytree(FIX / "csv", src, dirs_exist_ok=True)
    edges = list(csv.DictReader((src / "edges.csv").open(encoding="utf-8", newline="")))
    fields = list(edges[0].keys()) + (["publisert"] if "publisert" not in edges[0] else [])
    with (src / "edges.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in edges:
            r = dict(r)
            r["publisert"] = "true"
            w.writerow(r)
    info = convert(src, dest)
    assert info["kanter"] and all(e.get("publisert") is False for e in info["kanter"])
    k = json.loads((dest / "kanter.json").read_text())
    assert all(e.get("publisert") is False for e in k["kanter"])


def test_apply_godkjent_sets_only_matching_rows():
    n, k = _load()
    out = apply_godkjent(k["kanter"], FIX / "godkjent.csv")
    pub = [e for e in out if e["publisert"] is True]
    unpub = [e for e in out if e["publisert"] is False]
    expect = sum(1 for r in __import__("csv").DictReader((FIX / "godkjent.csv").open(encoding="utf-8", newline="")))
    assert len(pub) == expect and unpub
    orig = {(e["fra"], e["til"], e.get("lag")): e.get("status") for e in k["kanter"]}
    assert all(e.get("status") == orig[(e["fra"], e["til"], e.get("lag"))] for e in pub)
    assert all(e.get("godkjent_dato") == "2026-11-27" for e in pub)
    assert all(e.get("kontroll") == "fiktiv-testkontroll" for e in pub)
    assert all("godkjent_dato" not in e for e in unpub)
    # original uendret
    assert all(e.get("publisert") is False for e in k["kanter"])


def test_incomplete_godkjent_row_is_rejected(tmp_path):
    _, k = _load()
    p = tmp_path / "godkjent.csv"
    p.write_text("kant-id,lag,dato,kontroll\nNHY.OL>eu,råvare,2026-11-27,\n", encoding="utf-8")
    with pytest.raises(FlytError, match="dato og kontroll"):
        apply_godkjent(k["kanter"], p)
    p.write_text("kant-id,lag,dato,kontroll\nUKJENT>X,råvare,2026-11-27,x\n", encoding="utf-8")
    with pytest.raises(FlytError, match="ukjent kant"):
        apply_godkjent(k["kanter"], p)


def test_coverage_and_missing_chain_use_only_published():
    n, k = _load()
    uni = universe_tickers(FIX / "list_members.csv")
    assert coverage(n, k, uni)["statuslinje"] == "Råvaredata for 0 av 8 · Selskapsdata for 0 av 8"
    assert ticker_has_published(n, k, "NHY.OL") is False
    out = apply_godkjent(k["kanter"], FIX / "godkjent.csv")
    k2 = {"kanter": out}
    assert coverage(n, k2, uni)["statuslinje"] == "Råvaredata for 1 av 8 · Selskapsdata for 1 av 8"
    assert ticker_has_published(n, k2, "NHY.OL") is True
    assert ticker_has_published(n, k2, "EQNR.OL") is False
    assert ticker_has_published(n, k2, "KOG.OL") is False


def test_apply_godkjent_file_roundtrip(tmp_path):
    dest = tmp_path / "flyt"
    convert(FIX / "csv", dest)
    assert all(e["publisert"] is False for e in json.loads((dest / "kanter.json").read_text())["kanter"])
    n = apply_godkjent_file(dest, FIX / "godkjent.csv")
    expect = sum(1 for r in __import__("csv").DictReader((FIX / "godkjent.csv").open(encoding="utf-8", newline="")))
    assert n == expect
    k = json.loads((dest / "kanter.json").read_text())
    assert sum(1 for e in k["kanter"] if e["publisert"] is True) == expect
    # å fjerne fila og kjøre apply på tomt utvalg: ny fil uten rader setter alt til false
    empty = tmp_path / "empty.csv"
    empty.write_text("kant-id,lag,dato,kontroll\n", encoding="utf-8")
    n2 = apply_godkjent_file(dest, empty)
    assert n2 == 0
    k = json.loads((dest / "kanter.json").read_text())
    assert all(e["publisert"] is False for e in k["kanter"])
