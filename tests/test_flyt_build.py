"""CSV → noder.json / kanter.json. Fiktiv fixture skal ikke publiseres i site/flyt/."""
import json
from pathlib import Path

import pytest

from signaltool.flyt_build import convert, maybe_convert
from signaltool.flyt_schema import validate

FIX = Path(__file__).parent / "fixtures" / "flyt"


def test_convert_csv_to_two_files(tmp_path):
    dest = tmp_path / "flyt"
    info = convert(FIX / "csv", dest)
    assert (dest / "noder.json").exists() and (dest / "kanter.json").exists()
    n = json.loads((dest / "noder.json").read_text())
    k = json.loads((dest / "kanter.json").read_text())
    s = json.loads((dest / "scenarioer.json").read_text())
    assert not n.get("_fiktiv")
    assert any(x["id"] == "NHY.OL" for x in n["noder"])
    assert any(x["fra"] == "NHY.OL" for x in k["kanter"])
    assert all(x.get("publisert") is False for x in k["kanter"])
    assert {x["id"] for x in s["scenarioer"]} == {"energi_opp", "import_eu_ned", "bil_opp"}
    assert not validate(n, k, s, allow_fictive=False)
    assert info["noder"]


def test_maybe_convert_skips_when_missing(tmp_path):
    assert maybe_convert(tmp_path / "ingen", tmp_path / "out") is False
    assert not (tmp_path / "out" / "noder.json").exists()


def test_convert_rejects_row_without_source(tmp_path):
    src = tmp_path / "csv"
    src.mkdir()
    (src / "nodes.csv").write_text("id,lag,navn,hva_det_er,status,kilde,kilde_url,år,enhet\n"
                                   "X,selskap,X,selskap,kilde,, ,2024,tonn\n", encoding="utf-8")
    (src / "edges.csv").write_text("fra,til,lag,verdi,enhet,år,kilde,kilde_url,status\n", encoding="utf-8")
    with pytest.raises(Exception):
        convert(src, tmp_path / "out")
