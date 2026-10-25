"""«★ Mine»: personlig liste i nettleseren – aldri i repoet, aldri i treffrater/tellere/kategorier."""
import json, re
from pathlib import Path
import pytest
from signaltool import mine, site, tickerlist as TL

SNAP = Path(__file__).resolve().parent.parent / "site" / "data.json"


def test_storage_key_and_param():
    assert mine.KEY == "signaltool.minliste" and mine.PARAM == "mine"
    assert "'{KEY}'" in mine.JS and "'{PARAM}'" in mine.JS and "liste=" not in mine.JS


def test_every_localstorage_call_is_wrapped():
    js = mine.JS
    calls = [m.start() for m in re.finditer(r"localStorage\.", js)]
    assert calls
    for i in calls:
        before = js[:i]
        assert before.rfind("try{") > before.rfind("}catch"), js[max(0, i - 60):i + 30]


def test_star_button_and_texts():
    b = mine.star("HAS")
    assert 'class="mstar"' in b and 'data-t="HAS"' in b and "☆" in b
    assert "min-width:44px" in mine.CSS and "height:44px" in mine.CSS
    assert "Lagt til i ★ Mine" in mine.JS
    assert mine.EMPTY == "Trykk ☆ på en ticker for å lagre den"
    assert "Del / flytt lista" in mine.tile() and "hidden" in mine.tile()


def test_import_validates_against_site_list():
    assert "filter(x=>T[x])" in mine.JS and "toUpperCase()" in mine.JS


def test_filter_row_mine_first_and_generic_empty():
    r = TL.filter_row({})
    first = re.search(r"<button[^>]*>(.*?)</button>", r).group(1)
    assert first.startswith("★ Mine (") and 'data-f="mine"' in r
    assert "Ingen tickere i '+NM[f]+' nå." in TL.JS and mine.EMPTY in TL.JS


def test_data_has_only_existing_fields():
    e = {"ticker": "ABC", "category": "watch", "stats": {"ret_1d": 0.012}, "cat_flags": {"crash": "kursfall"}}
    d = mine.data([e], lambda t: t)["ABC"]
    assert d == {"s": "ABC", "n": "", "c": "Følg", "d": 0.012, "f": ["kursfall"]}
    assert mine.data([{"ticker": "X", "stats": {}}], str)["X"]["d"] is None


@pytest.mark.skipif(not SNAP.exists(), reason="no snapshot available")
def test_build_wires_mine_without_touching_counts(tmp_path, monkeypatch):
    snap = json.loads(SNAP.read_text())
    before = json.dumps([(e["ticker"], e.get("category")) for e in snap["tickers"]])
    monkeypatch.setattr(site, "SITE", tmp_path / "site")
    site.build(snap)
    out = tmp_path / "site"
    idx, tl = (out / "index.html").read_text(), (out / "tickere.html").read_text()
    assert 'id="mine-tile"' in idx and "window.ST_T=" in idx
    assert tl.count('class="mstar"') == len(snap["tickers"])
    t = snap["tickers"][0]["ticker"]
    page = (out / "ticker" / f"{site.slug(t)}.html").read_text()
    assert f'class="mstar" data-t="{t}"' in page
    assert "minliste" not in (out / "data.json").read_text()
    assert json.dumps([(e["ticker"], e.get("category")) for e in snap["tickers"]]) == before
    assert not re.search("rob" + "ust", idx + tl, re.I)
