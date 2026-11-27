"""Runde 6 (27.11): landetall etter AnalBot — selskapsnoder, ikke to hopp via råvare."""
from __future__ import annotations

import csv
import hashlib
import http.server
import json
import threading
from pathlib import Path

import pytest

from signaltool.flyt_page import LINK_CSS, prepare_preview, write
from signaltool.flyt_schema import (
    oversikt_varer_og_land,
    selskap_count_label,
    selskaper_paa_land,
    tickers_on_node,
)

ROOT = Path(__file__).resolve().parents[1]
FLYT = ROOT / "flyt"
JS = ROOT / "signaltool" / "flyt_static" / "flyt.js"
SHOTS = Path("/workspace/flyt-shots-2711")
MD5 = {
    "noder.json": "02ab5d48a26842392130afcecb7c72ba",
    "kanter.json": "9f6280057d24f7b869aee39eadd528a2",
    "scenarios.json": "bc2a39146e088416e362a8c46cf16f97",
}


def _load_official():
    noder = json.loads((FLYT / "noder.json").read_text(encoding="utf-8"))
    kanter = json.loads((FLYT / "kanter.json").read_text(encoding="utf-8"))
    if isinstance(noder, dict):
        noder = noder["noder"]
    if isinstance(kanter, dict):
        kanter = kanter["kanter"]
    return noder, kanter


def _N(i, typ, navn, **kw):
    n = {"id": i, "type": typ, "navn": navn, "lag": kw.pop("lag", "selskap"), "status": "kilde", "ticker": kw.pop("ticker", "")}
    n.update(kw)
    return n


def _E(fra, til, *, lag, publisert=True):
    return {"fra": fra, "til": til, "lag": lag, "publisert": publisert, "status": "kilde"}


def r6_fixture():
    """Direkte selskap-kant, via eget verk, og en råvare-vei som ikke skal telles."""
    noder = [
        _N("ticker:AAA.OL", "ticker", "Alfa", ticker="AAA.OL"),
        _N("ticker:BBB.OL", "ticker", "Beta", ticker="BBB.OL"),
        _N("ticker:CCC.OL", "ticker", "Gamma", ticker="CCC.OL"),
        _N("anlegg:verk-b", "anlegg", "Verk B"),
        _N("vare:mat", "vare", "Materiale", lag="råvare"),
        _N("land:DIR", "land", "Direkte-landet"),
        _N("land:VERK", "land", "Verk-landet"),
        _N("land:RAA", "land", "Råvare-landet", lag="råvare"),
        _N("land:TO", "land", "To-landet"),
        _N("ticker:DDD.OL", "ticker", "Delta", ticker="DDD.OL"),
    ]
    kanter = [
        # direkte: AAA --lag:selskap--> Direkte-landet
        _E("ticker:AAA.OL", "land:DIR", lag="selskap"),
        # via eget verk: BBB --selskap--> verk-b --selskap--> Verk-landet
        _E("ticker:BBB.OL", "anlegg:verk-b", lag="selskap"),
        _E("anlegg:verk-b", "land:VERK", lag="selskap"),
        # råvare-vei (skal ikke telles): CCC --selskap--> vare --råvare--> Råvare-landet
        _E("ticker:CCC.OL", "vare:mat", lag="selskap"),
        _E("vare:mat", "land:RAA", lag="råvare"),
        # To-landet: to selskaper (direkte AAA + DDD)
        _E("ticker:AAA.OL", "land:TO", lag="selskap"),
        _E("ticker:DDD.OL", "land:TO", lag="selskap"),
    ]
    return noder, kanter


def test_md5_unchanged():
    for fn, digest in MD5.items():
        got = hashlib.md5((FLYT / fn).read_bytes()).hexdigest()
        assert got == digest, (fn, got)


def test_selskaper_direkte_via_verk_ikke_via_raavare():
    noder, kanter = r6_fixture()
    assert selskaper_paa_land(noder, kanter, "land:DIR") == ["ticker:AAA.OL"]
    assert selskaper_paa_land(noder, kanter, "land:VERK") == ["ticker:BBB.OL"]
    assert selskaper_paa_land(noder, kanter, "land:RAA") == []
    # gammel 2-hopp-regel ville telt råvare-veien
    assert "CCC.OL" in tickers_on_node(noder, kanter, "land:RAA")
    assert selskaper_paa_land(noder, kanter, "land:TO") == ["ticker:AAA.OL", "ticker:DDD.OL"]


def test_offisiell_nhy_qatar_via_qatalum_og_eu_direkte():
    noder, kanter = _load_official()
    qa = selskaper_paa_land(noder, kanter, "land:QA")
    assert qa == ["ticker:NHY.OL"]
    eu = selskaper_paa_land(noder, kanter, "land:EU")
    assert eu == ["ticker:NHY.OL"]
    # Tyskland bare råvare-vei via andre land — teller ikke
    assert selskaper_paa_land(noder, kanter, "land:DE") == []


def test_entall_flertall_selskap():
    assert selskap_count_label(1) == "1 selskap"
    assert selskap_count_label(0) == "0 selskaper"
    assert selskap_count_label(2) == "2 selskaper"
    assert selskap_count_label(19) == "19 selskaper"
    src = JS.read_text(encoding="utf-8")
    fn = src.split("function selskapCountLabel", 1)[1].split("function ", 1)[0]
    assert "1 selskap" in fn
    assert "selskaper" in fn
    # vare-teksten er uendret
    tk = src.split("function tickerCountLabel", 1)[1].split("function ", 1)[0]
    assert "1 ticker" in tk and "tickere" in tk


def test_sortering_topp_6_etter_nytt_tall():
    noder, kanter = r6_fixture()
    ov = oversikt_varer_og_land(noder, kanter)
    vis = ov["land_synlige"]
    counts = [ov["counts"][n["id"]] for n in vis]
    assert counts == sorted(counts, reverse=True)
    # To-landet (2) foran land med 1
    assert vis[0]["id"] == "land:TO"
    assert ov["counts"]["land:TO"] == 2
    vis_ids = {n["id"] for n in vis}
    assert "land:DIR" in vis_ids and "land:VERK" in vis_ids
    assert "land:RAA" not in vis_ids
    andre_ids = {n["id"] for n in ov["andre"]}
    assert "land:RAA" in andre_ids
    # råvare-noder bruker fortsatt ticker-telling
    assert ov["counts"]["vare:mat"] == len(set(tickers_on_node(noder, kanter, "vare:mat")))


def test_statuslinje_kode_uendret_k_ge_1():
    src = JS.read_text(encoding="utf-8")
    fn = src.split("function updateStatus()", 1)[1].split("function fillSearch", 1)[0]
    assert "k >= 1" in fn or "k>=1" in fn
    from signaltool.flyt_page import body_html
    h0 = body_html(meta={"coverage": {"beregnet": True, "k": 0, "n": 60, "statuslinje": "Råvaredata for 0 av 60 · Selskapsdata for 0 av 60"}})
    assert 'id="flyt-status" hidden' in h0
    h1 = body_html(meta={"coverage": {"beregnet": True, "k": 1, "n": 8, "statuslinje": "Råvaredata for 1 av 8 · Selskapsdata for 1 av 8"}})
    assert "Råvaredata for 1 av 8" in h1 and 'id="flyt-status" hidden' not in h1


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
    dest = tmp_path_factory.mktemp("flyt-r6-off")
    prepare_preview(dest, fixture=False)
    httpd, url = _server(dest)
    yield dest, url
    httpd.shutdown()


@pytest.fixture(scope="module")
def r6_preview(tmp_path_factory):
    dest = tmp_path_factory.mktemp("flyt-r6-fx")
    noder, kanter = r6_fixture()
    _preview_from(dest, noder, kanter)
    httpd, url = _server(dest)
    yield dest, url, noder, kanter
    httpd.shutdown()


def test_js_and_python_same_counts_official_and_fixture(official_preview, r6_preview):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    def js_counts(page):
        page.wait_for_function("() => window.__flyt && window.__flyt.selskaperOn")
        return page.evaluate(
            """() => {
              const lands = (window.__flyt && window.noder)
                ? null
                : null;
              const noder = window.__flyt ? undefined : undefined;
              // noder er modul-privat; les etiketter + kall selskaperOn via kjente id-er
              return true;
            }"""
        )

    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()

        # offisielle data
        _, url = official_preview
        noder, kanter = _load_official()
        ov = oversikt_varer_og_land(noder, kanter)
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_function("() => window.__flyt && typeof window.__flyt.selskaperOn === 'function'")
        land_ids = [n["id"] for n in noder if n.get("type") == "land"]
        js = page.evaluate(
            """(ids) => {
              const out = {};
              for (const id of ids) out[id] = window.__flyt.selskaperOn(id).map((x) => x.id).sort();
              return out;
            }""",
            land_ids,
        )
        for lid in land_ids:
            py = selskaper_paa_land(noder, kanter, lid)
            assert js.get(lid, []) == py, (lid, js.get(lid), py)
        # etiketter i oversikten
        texts = page.evaluate("() => [...document.querySelectorAll('.flyt-lab')].map((e) => e.innerText.replace(/\\s+/g,' '))")
        for n in ov["land_synlige"]:
            lab = selskap_count_label(ov["counts"][n["id"]])
            assert any(n["navn"] in t and lab in t for t in texts), (n, texts)
        # runde 7: vareetiketter viser bare navnet, uten ticker-telling
        vare_texts = [t for t in texts if t.startswith("Råaluminium") or t.startswith("Bauksitt") or t.startswith("Alumina") or t.startswith("Halvfabrikata")]
        assert vare_texts, texts
        assert all("ticker" not in t.lower() for t in vare_texts), vare_texts
        assert all("1 tickere" not in t for t in texts)
        # Qatar-panel
        page.locator('.flyt-lab').filter(has_text="Qatar").first.click()
        page.wait_for_timeout(300)
        panel = page.inner_text("#flyt-panel")
        assert "1 selskap" in panel
        assert "NHY.OL" in panel

        # fiktiv fixture der råvare-vei skiller gammel og ny regel
        _, furl, fnoder, fkanter = r6_preview
        fov = oversikt_varer_og_land(fnoder, fkanter)
        page.goto(f"{furl}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_function("() => window.__flyt && typeof window.__flyt.selskaperOn === 'function'")
        fids = [n["id"] for n in fnoder if n.get("type") == "land"]
        fjs = page.evaluate(
            """(ids) => {
              const out = {};
              for (const id of ids) out[id] = window.__flyt.selskaperOn(id).map((x) => x.id).sort();
              return out;
            }""",
            fids,
        )
        for lid in fids:
            assert fjs.get(lid, []) == selskaper_paa_land(fnoder, fkanter, lid), lid
        ftexts = page.evaluate("() => [...document.querySelectorAll('.flyt-lab')].map((e) => e.innerText.replace(/\\s+/g,' '))")
        assert any("To-landet" in t and "2 selskaper" in t for t in ftexts), ftexts
        assert any("Direkte-landet" in t and "1 selskap" in t for t in ftexts), ftexts
        assert any("Verk-landet" in t and "1 selskap" in t for t in ftexts), ftexts
        assert not any("Råvare-landet" in t and "selskap" in t for t in ftexts if not t.startswith("+")), ftexts
        # topp-rekkefølge: To-landet først (2 selskaper)
        order = [t for t in ftexts if "landet" in t and "selskaper" in t or "selskap" in t]
        assert any(t.startswith("To-landet") for t in order)
        vis_names = [n["navn"] for n in fov["land_synlige"]]
        assert vis_names[0] == "To-landet"

        browser.close()
