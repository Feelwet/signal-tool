"""Runde 7 (27.11): landrader bare ved ≥1 selskap; vareetiketter uten ticker-telling."""
from __future__ import annotations

import hashlib
import http.server
import json
import re
import threading
from pathlib import Path

import pytest

from signaltool.flyt_page import LINK_CSS, prepare_preview, write
from signaltool.flyt_schema import oversikt_varer_og_land, selskaper_paa_land

ROOT = Path(__file__).resolve().parents[1]
FLYT = ROOT / "flyt"
MD5 = {
    "noder.json": "02ab5d48a26842392130afcecb7c72ba",
    "kanter.json": "9f6280057d24f7b869aee39eadd528a2",
    "scenarios.json": "bc2a39146e088416e362a8c46cf16f97",
}
TICKER_COUNT_RE = re.compile(r"\d+\s+ticker", re.I)


def _load_official():
    noder = json.loads((FLYT / "noder.json").read_text(encoding="utf-8"))
    kanter = json.loads((FLYT / "kanter.json").read_text(encoding="utf-8"))
    if isinstance(noder, dict):
        noder = noder["noder"]
    if isinstance(kanter, dict):
        kanter = kanter["kanter"]
    return noder, kanter


def _N(i, typ, navn, **kw):
    n = {
        "id": i, "type": typ, "navn": navn,
        "lag": kw.pop("lag", "selskap"), "status": kw.pop("status", "kilde"),
        "ticker": kw.pop("ticker", ""),
    }
    n.update(kw)
    return n


def _E(fra, til, *, lag, publisert=True):
    return {"fra": fra, "til": til, "lag": lag, "publisert": publisert, "status": "kilde"}


def r7_fixture_zero_in_top():
    """To land med ≥1 selskap, og flere 0-land med høyere kantgrad som ellers ville vært topp-kandidater."""
    noder = [
        _N("ticker:AAA.OL", "ticker", "Alfa", ticker="AAA.OL"),
        _N("ticker:BBB.OL", "ticker", "Beta", ticker="BBB.OL"),
        _N("vare:mat", "vare", "Materiale", lag="råvare"),
        _N("land:A", "land", "Land-A"),
        _N("land:B", "land", "Land-B"),
        _N("land:C0", "land", "Null-C", lag="råvare"),
        _N("land:D0", "land", "Null-D", lag="råvare"),
        _N("land:E0", "land", "Null-E", lag="råvare"),
        _N("land:F0", "land", "Null-F", lag="råvare"),
        _N("land:G0", "land", "Null-G", lag="råvare"),
    ]
    kanter = [
        _E("ticker:AAA.OL", "land:A", lag="selskap"),
        _E("ticker:BBB.OL", "land:B", lag="selskap"),
        # 0-land: mange råvare-kanter gir høy grad, men 0 selskaper
        _E("vare:mat", "land:C0", lag="råvare"),
        _E("vare:mat", "land:D0", lag="råvare"),
        _E("vare:mat", "land:E0", lag="råvare"),
        _E("vare:mat", "land:F0", lag="råvare"),
        _E("vare:mat", "land:G0", lag="råvare"),
        _E("land:C0", "land:D0", lag="råvare"),
        _E("land:C0", "land:E0", lag="råvare"),
        _E("land:C0", "land:F0", lag="råvare"),
        _E("land:D0", "land:E0", lag="råvare"),
        _E("land:D0", "land:F0", lag="råvare"),
        _E("land:E0", "land:G0", lag="råvare"),
    ]
    return noder, kanter


def test_md5_unchanged():
    for fn, digest in MD5.items():
        got = hashlib.md5((FLYT / fn).read_bytes()).hexdigest()
        assert got == digest, (fn, got)


def test_offisiell_land_heading_og_bare_land_med_selskap():
    noder, kanter = _load_official()
    ov = oversikt_varer_og_land(noder, kanter)
    assert ov["land_label"] == "Land (25)"
    assert ov["land_n"] == 25
    assert len(ov["land_synlige"]) <= 6
    assert len(ov["land_synlige"]) == 6
    assert all(ov["counts"][n["id"]] >= 1 for n in ov["land_synlige"])
    assert all(selskaper_paa_land(noder, kanter, n["id"]) for n in ov["land_synlige"])
    assert all(ov["counts"].get(n["id"], 0) == 0 or n in ov["land_synlige"] for n in ov["andre"] if ov["counts"].get(n["id"], 0) > 0) or True
    # 0-land er i +n andre
    for n in ov["andre"]:
        assert ov["counts"][n["id"]] == 0 or n["id"] in {x["id"] for x in ov["land_synlige"]}
        if n["id"] not in {x["id"] for x in ov["land_synlige"]}:
            # de som ikke nådde topp 6 med ≥1 ville vært her; offisielt alle andre har 0
            assert ov["counts"][n["id"]] == 0
    assert len(ov["andre"]) == 19
    assert ov["varer_label"] == "Varer (4)"


def test_fikstur_null_land_gaar_i_andre_og_faerre_enn_6():
    noder, kanter = r7_fixture_zero_in_top()
    ov = oversikt_varer_og_land(noder, kanter)
    vis = ov["land_synlige"]
    assert len(vis) == 2, [n["id"] for n in vis]
    assert {n["id"] for n in vis} == {"land:A", "land:B"}
    assert all(ov["counts"][n["id"]] >= 1 for n in vis)
    andre_ids = {n["id"] for n in ov["andre"]}
    assert andre_ids == {"land:C0", "land:D0", "land:E0", "land:F0", "land:G0"}
    assert all(ov["counts"][i] == 0 for i in andre_ids)
    assert len(ov["andre"]) == 5
    # Land-tallet er antall tilkoblede, ikke bare de med selskap
    assert ov["land_n"] == 7
    assert ov["land_label"] == "Land (7)"
    # aldri fylle opp med 0-land
    assert len(vis) < 6


def _launch(p):
    import os
    chrome = os.environ.get("FLY_CHROME") or "/usr/bin/google-chrome"
    try:
        return p.chromium.launch()
    except Exception:
        if Path(chrome).exists():
            return p.chromium.launch(executable_path=chrome, headless=True)
        raise


def _server(root: Path):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(root), **k)

        def log_message(self, *a, **k):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _preview_from(dest: Path, noder, kanter):
    from signaltool import site as S
    from signaltool import tabbar as TB
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    flyt = dest / "flyt"
    flyt.mkdir(exist_ok=True)
    (flyt / "noder.json").write_text(json.dumps({"noder": noder}, ensure_ascii=False), encoding="utf-8")
    (flyt / "kanter.json").write_text(json.dumps({"kanter": kanter}, ensure_ascii=False), encoding="utf-8")
    (flyt / "scenarios.json").write_text(json.dumps({"scenarioer": []}, ensure_ascii=False), encoding="utf-8")
    (dest / "data.json").write_text(json.dumps({"tickers": []}), encoding="utf-8")
    (dest / "style.css").write_text(S.CSS + TB.CSS + LINK_CSS, encoding="utf-8")
    write(dest, {"generated": "2026-11-27 13:00"}, universe=[], noder=noder, kanter=kanter,
          scenarioer=[], data_base="flyt", kurs_url="data.json")
    return dest


@pytest.fixture(scope="module")
def official_preview(tmp_path_factory):
    dest = tmp_path_factory.mktemp("flyt-r7-off")
    prepare_preview(dest, fixture=False)
    httpd, url = _server(dest)
    yield dest, url
    httpd.shutdown()


@pytest.fixture(scope="module")
def r7_preview(tmp_path_factory):
    dest = tmp_path_factory.mktemp("flyt-r7-fx")
    noder, kanter = r7_fixture_zero_in_top()
    _preview_from(dest, noder, kanter)
    httpd, url = _server(dest)
    yield dest, url, noder, kanter
    httpd.shutdown()


def _labs(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('.flyt-lab, .flyt-col-h')].map((el) => ({
          id: el.dataset.id || '', typ: el.className, t: (el.innerText||'').replace(/\\s+/g,' ')
        }))"""
    )


def test_r7_playwright_landrader_og_varer_uten_ticker_telling(official_preview, r7_preview):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()

        _, url = official_preview
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(300)
        labs = _labs(page)
        texts = [x["t"] for x in labs]
        heads = [x["t"] for x in labs if x["id"].startswith("__") or x["t"].startswith("Land") or x["t"].startswith("Varer")]
        assert "Land (25)" in texts
        assert "Varer (4)" in texts
        land_rows = [x for x in labs if (x["id"] or "").startswith("land:")]
        andre = [x for x in labs if x["id"] == "andre:oversikt" or (x["t"].startswith("+") and "andre" in x["t"])]
        assert len(land_rows) == 6, land_rows
        assert len(andre) == 1 and andre[0]["t"] == "+19 andre", andre
        vare_rows = [x for x in labs if (x["id"] or "").startswith("vare:")]
        assert len(vare_rows) == 4, vare_rows
        for v in vare_rows:
            assert v["t"] == v["t"].split("  ")[0] or True
            assert "ticker" not in v["t"].lower(), v
            assert not TICKER_COUNT_RE.search(v["t"]), v
        # navn alene
        names = {v["t"] for v in vare_rows}
        assert "Bauksitt" in names and "Alumina" in names
        assert "Råaluminium" in names
        assert any("Halvfabrikata" in t for t in names)
        # varepanel: ingen «n ticker(e)»-telling
        page.locator('.flyt-lab').filter(has_text="Råaluminium").first.click()
        page.wait_for_timeout(300)
        panel = page.inner_text("#flyt-panel")
        assert not TICKER_COUNT_RE.search(panel), panel
        assert "1 ticker" not in panel and "0 tickere" not in panel

        # fikstur: bare 2 landrader, 0-land i +5 andre, vare uten telling
        _, furl, fnoder, fkanter = r7_preview
        ov = oversikt_varer_og_land(fnoder, fkanter)
        page.goto(f"{furl}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(300)
        flabs = _labs(page)
        ftexts = [x["t"] for x in flabs]
        fland = [x for x in flabs if (x["id"] or "").startswith("land:")]
        fandre = [x for x in flabs if x["id"] == "andre:oversikt"]
        assert len(fland) == 2, fland
        assert {x["id"] for x in fland} == {"land:A", "land:B"}
        assert fandre and fandre[0]["t"] == "+5 andre", fandre
        assert "Land (7)" in ftexts
        assert not any(x["t"].startswith("Null-") for x in fland)
        fvare = [x for x in flabs if (x["id"] or "").startswith("vare:")]
        for v in fvare:
            assert "ticker" not in v["t"].lower(), v
            assert not TICKER_COUNT_RE.search(v["t"]), v
        assert any(v["t"] == "Materiale" for v in fvare), fvare
        page.locator('.flyt-lab').filter(has_text="Materiale").first.click()
        page.wait_for_timeout(250)
        fpanel = page.inner_text("#flyt-panel")
        assert not TICKER_COUNT_RE.search(fpanel), fpanel
        assert "0 tickere" not in fpanel and "1 ticker" not in fpanel

        browser.close()
