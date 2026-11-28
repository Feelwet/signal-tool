"""Runde 1 (28.11): AnalBot FLAG 1–5, SPEC-tillegg og UxBot 13:08."""
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from signaltool.config import ROOT
from signaltool.flyt_schema import round_tonn_scene, scene_tonn_tekst
from signaltool.flyt_utkast import SELSKAP_VARER, yoy_merke

UTKAST = ROOT / "flyt" / "utkast_2811"
JS = ROOT / "signaltool" / "flyt_static" / "flyt.js"
CSS = ROOT / "signaltool" / "flyt_static" / "flyt.css"
PDFS = Path("/workspace/flyt-alle-2811/pdfs")


def _kanter():
    return json.loads((UTKAST / "kanter.json").read_text(encoding="utf-8"))


def _land_kanter():
    return [e for e in _kanter() if e["lag"] == "råvare" and str(e["til"]).startswith("land:")]


def _js_fn(src: str, name: str) -> str:
    i = src.index(f"function {name}(")
    j = src.index("{", i)
    depth = 0
    for k in range(j, len(src)):
        c = src[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
    raise AssertionError(name)


def _js_prelude(names: list[str]) -> str:
    src = JS.read_text(encoding="utf-8")
    consts = [
        re.search(r"^const LAG_SRC = .*$", src, re.M).group(0),
        re.search(r"^const TONN = .*$", src, re.M).group(0),
    ]
    return "\n".join(consts + [_js_fn(src, n) for n in names])


def _node(js: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node mangler")
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# ---------- FLAG 1 ----------

def test_flag1_yoy_merker_174_av_345_og_upublisert():
    land = _land_kanter()
    assert len(land) == 345
    merket = [e for e in land if e.get("yoy_merke")]
    assert len(merket) == 174  # AnalBot 13:10 teller 174 av 345
    for e in land:
        assert e["publisert"] is False
        # uavhengig regel: ny i 2025 (2024 mangler/0) eller |Δ| >= 40 %
        v24 = e.get("verdi_2024")
        if v24 in (None, 0, 0.0):
            assert e["yoy_merke"] == "ny_i_2025", e["id"]
        else:
            pct = abs(e["verdi"] - v24) / v24 * 100
            assert (e["yoy_merke"] == "yoy_ge_40") == (pct >= 40 - 1e-9), e["id"]
    # egen logglinje før/etter per treff
    rows = list(csv.DictReader((UTKAST / "yoy_logg.csv").open(encoding="utf-8")))
    assert len(rows) == 174
    assert {r["kant_id"] for r in rows} == {e["id"] for e in merket}
    for r in rows:
        assert r["etter_2025_tonn"] != ""
        assert r["publisert_for"] == "False" and r["publisert_etter"] == "False"
        if r["merke"] == "yoy_ge_40":
            assert r["for_2024_tonn"] != "" and r["yoy_pct"] != ""
    man = json.loads((UTKAST / "manifest.json").read_text(encoding="utf-8"))
    assert man["n_yoy_merket"] == 174 and man["n_publisert_true"] == 0


def test_flag1_regel_enhet():
    assert yoy_merke(1000, None)["yoy_merke"] == "ny_i_2025"
    assert yoy_merke(1000, 0)["yoy_merke"] == "ny_i_2025"
    assert yoy_merke(1400, 1000)["yoy_merke"] == "yoy_ge_40"
    assert yoy_merke(600, 1000)["yoy_merke"] == "yoy_ge_40"
    assert yoy_merke(1399, 1000)["yoy_merke"] == ""


# ---------- FLAG 2 ----------

def test_flag2_verdi_lagres_med_desimaler():
    trade = [e for e in _kanter() if e["lag"] == "råvare"]
    assert trade and all(isinstance(e["verdi"], float) for e in trade)
    assert any(e["verdi"] != int(e["verdi"]) for e in trade)
    for e in trade:
        assert e["verdi"] == e["råverdi"] / 1000.0


def test_flag2_scene_hele_tonn_og_under_1_tonn_python():
    assert scene_tonn_tekst(0.11) == "under 1 tonn"
    assert scene_tonn_tekst(0.958) == "under 1 tonn"
    assert scene_tonn_tekst(1.0) == "1 tonn"
    assert scene_tonn_tekst(1.5) == "2 tonn"
    assert scene_tonn_tekst(2.4999) == "2 tonn"
    assert round_tonn_scene(2.5) == 3
    assert scene_tonn_tekst(147304.0) == "147\u00a0304 tonn"


def test_flag2_scene_js_lik_python():
    pre = _js_prelude(["yearOf", "isTonn", "roundTonnHalfUp", "fmtSceneVal"])
    vals = [0.11, 0.958, 0.5, 1.0, 1.5, 2.4999, 2.5, 147304.0]
    js = pre + f"\nconsole.log(JSON.stringify({json.dumps(vals)}.map(v => fmtSceneVal({{verdi: v, enhet: 'tonn', ar: '2025'}}))));"
    out = _node(js)
    assert out[:3] == ["under 1 tonn 2025"] * 3
    assert out[3] == "1 tonn 2025" and out[4] == "2 tonn 2025" and out[5] == "2 tonn 2025" and out[6] == "3 tonn 2025"
    assert out[7].replace("\u00a0", " ") == "147 304 tonn 2025"


# ---------- FLAG 3 / 4 ----------

def _sel(ticker):
    return [e for e in _kanter() if e["lag"] == "selskap" and e["fra"] == f"ticker:{ticker}"]


def _pdf_sentence(pdf: Path, page: int, x: int, w: int, h: int) -> str:
    out = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), "-layout", "-x", str(x), "-y", "0",
                          "-W", str(w), "-H", str(h), str(pdf), "-"], capture_output=True, text=True)
    return re.sub(r"\s+", " ", out.stdout)


def test_flag3_eqnr_naturgass_har_egen_setning_med_side():
    ed = {e["til"]: e for e in _sel("EQNR.OL")}
    assert set(ed) == {"vare:raaolje", "vare:naturgass"}
    g = ed["vare:naturgass"]
    assert g["side"] == "12" and "naturgass" in g["sitat"] and g["sitat"].endswith(".")
    assert g["publisert"] is False
    pdf = PDFS / "EQNR_2025_NO.pdf"
    if pdf.exists() and shutil.which("pdftotext"):
        txt = _pdf_sentence(pdf, 12, 0, 400, 596)
        assert g["sitat"] in txt
        assert ed["vare:raaolje"]["sitat"] in txt


def test_flag4_mowi_kun_varer_med_hel_setning():
    ed = {e["til"]: e for e in _sel("MOWI.OL")}
    assert set(ed) == {"vare:laks_fersk_hel", "vare:laks_fersk_filet", "vare:laks_fryst_filet"}
    assert "vare:laks_fryst_hel" not in ed
    assert ed["vare:laks_fersk_hel"]["side"] == "21" and "Fresh whole salmon" in ed["vare:laks_fersk_hel"]["sitat"]
    for k in ("vare:laks_fersk_filet", "vare:laks_fryst_filet"):
        assert ed[k]["side"] == "242"
        assert "fillets" in ed[k]["sitat"] and "fresh and frozen" in ed[k]["sitat"]
    assert all(e["publisert"] is False for e in ed.values())
    pdf = PDFS / "MOWI_2025.pdf"
    if pdf.exists() and shutil.which("pdftotext"):
        assert ed["vare:laks_fersk_hel"]["sitat"] in _pdf_sentence(pdf, 21, 295, 300, 842)
        assert ed["vare:laks_fersk_filet"]["sitat"] in _pdf_sentence(pdf, 242, 295, 300, 842)
    assert set(SELSKAP_VARER["MOWI.OL"]["varer"]) == set(ed)


# ---------- FLAG 5 ----------

def test_flag5_kildelinje_kun_norsk_rapportering():
    ssb = [e for e in _kanter() if "SSB" in e["kilde"]]
    assert ssb and all("kun norsk rapportering" in e["kilde"] for e in ssb)
    assert all("kun norsk rapportering" in e["metode"] for e in ssb)
    pre = _js_prelude(["yearOf", "srcText"])
    js = pre + "\nconsole.log(JSON.stringify([srcText({lag:'råvare', kilde:'SSB tabell 08801', ar:'2025', hs_kode:'7601'}), srcText({lag:'råvare', kilde:'SSB tabell 08801 (kun norsk rapportering)', ar:'2025'}), srcText({lag:'selskap', kilde:'Hydro integrert årsrapport 2025', side:'37'})]));"
    out = _node(js)
    assert out[0].endswith("kun norsk rapportering") and out[0].count("kun norsk rapportering") == 1
    assert out[1].count("kun norsk rapportering") == 1
    assert "kun norsk" not in out[2]


# ---------- SPEC-tillegg ----------

def test_mangler_data_overalt():
    src = JS.read_text(encoding="utf-8")
    assert "Ingen tickere koblet hit" not in src
    assert "Ingen publiserte koblinger" not in src
    assert src.count("'Mangler data'") >= 6


def test_halvfabrikata_kun_7604_7608():
    lines = [ln for ln in (ROOT / "flyt" / "hs_map.csv").read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")]
    rows = list(csv.DictReader(lines))
    hf = {r["hs_kode"].strip() for r in rows if r["vare_id"].strip() == "vare:halvfabrikata"}
    assert hf == {"7604", "7605", "7606", "7607", "7608"}


def test_avvik_to_rader_44px_og_metodelinje():
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    from tests.test_flyt_r1_ui_2811 import _launch
    pre = _js_prelude(["yearOf", "isTonn", "srcText", "srcLine", "fmtVal", "avvikInfo", "appendAvvik"])
    html = f"<!doctype html><html><head><style>{CSS.read_text(encoding='utf-8')}</style></head><body><div id='c' style='width:360px'></div></body></html>"
    with sync_playwright() as p:
        b = _launch(p)
        page = b.new_page(viewport={"width": 390, "height": 800})
        page.set_content(html)
        page.add_script_tag(content=pre + """
          window.__t = () => {
            const c = document.getElementById('c');
            const lite = {verdi: 100, enhet: 'tonn', ar: '2025', reporter_land: 'NO', metode: 'm', partner: {verdi: 115, reporter_land: 'DE'}};
            const stor = {verdi: 100, enhet: 'tonn', ar: '2025', reporter_land: 'NO', kilde: 'SSB tabell 08801', metode: 'Speilstatistikk: rapportør NO, partner DE.', partner: {verdi: 130, reporter_land: 'DE'}};
            const none = avvikInfo(lite);
            const info = avvikInfo(stor);
            appendAvvik(c, stor, {lag: 'råvare'}, info);
            const rows = [...c.querySelectorAll('.flyt-avvik-rad')].map(r => ({h: r.getBoundingClientRect().height, t: r.innerText}));
            const m = c.querySelector('.flyt-metode');
            const st = getComputedStyle(m);
            return {none, pct: info.pct, rows, mt: m.innerText, fs: st.fontSize, lh: st.lineHeight};
          };""")
        r = page.evaluate("window.__t()")
        b.close()
    assert r["none"] is None
    assert abs(r["pct"] - 30) < 1e-9
    assert len(r["rows"]) == 2 and all(abs(x["h"] - 44) < 0.5 for x in r["rows"])
    assert "Rapportør (NO)" in r["rows"][0]["t"] and "Partner (DE)" in r["rows"][1]["t"]
    assert r["mt"].startswith("Metode: Speilstatistikk")
    assert r["fs"] == "13px" and r["lh"] == "18px"


# ---------- UI: Liste-rad, Selskaper-overskrift, hovedmeny ----------

def _serve(root):
    from tests.test_flyt_r1_ui_2811 import _server
    return _server(root)


@pytest.fixture(scope="module")
def official_site(tmp_path_factory):
    from signaltool.flyt_page import prepare_preview
    from signaltool.site import page as site_page
    dest = tmp_path_factory.mktemp("flyt-r1-flag")
    prepare_preview(dest, fixture=False)
    (dest / "index.html").write_text(site_page("Oversikt", "<h1>Oversikt</h1><p>Start</p>"), encoding="utf-8")
    httpd, url = _serve(dest)
    yield dest, url
    httpd.shutdown()


def test_selskaper_overskrift_alltid_synlig_1280_og_liste_uten_status(official_site):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    from tests.test_flyt_r1_ui_2811 import _launch
    _, url = official_site
    with sync_playwright() as p:
        b = _launch(p)
        page = b.new_page(viewport={"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(300)
        h = page.evaluate("""() => [...document.querySelectorAll('.flyt-col-h')].map(e => {
            const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
            return {t: e.innerText.trim(), vis: s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0 && r.width > 0 && r.height > 0 && r.top >= 0 && r.bottom <= innerHeight};})""")
        sel = [x for x in h if x["t"].startswith("Selskaper (")]
        assert sel and sel[0]["vis"], h
        n_rows = page.evaluate("document.querySelectorAll('.flyt-lab.selskap-rad').length")
        assert n_rows == 1 and sel[0]["t"] == "Selskaper (1)"
        # Liste: ingen aggregert status i raden
        page.locator("#flyt-liste").click()
        page.wait_for_selector("#flyt-list .flyt-list-rad")
        rows = page.evaluate("""() => [...document.querySelectorAll('.flyt-list-rad')].map(r => ({
            cls: [...r.children].map(c => c.className), t: r.innerText}))""")
        b.close()
    assert rows
    for r in rows:
        assert set(r["cls"]) <= {"tk", "nm", "miss-lab"}, r
        assert not re.search(r"\b\d+ (kanter|koblinger|selskaper|land|varer)\b|publisert|status", r["t"], re.I), r


@pytest.mark.parametrize("width", [390, 1280])
def test_flyt_naas_fra_hovedmenyen(official_site, width):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    from tests.test_flyt_r1_ui_2811 import _launch
    _, url = official_site
    with sync_playwright() as p:
        b = _launch(p)
        page = b.new_page(viewport={"width": width, "height": 800})
        page.goto(f"{url}/index.html", wait_until="domcontentloaded")
        if width >= 700:
            link = page.locator("aside.side nav a[href='flyt.html']")
        else:
            page.locator("#tb-more").click()
            link = page.locator("#more-sheet a[href='flyt.html']")
        link.wait_for(state="visible")
        box = link.bounding_box()
        assert box and box["width"] > 0 and box["height"] > 0
        assert box["x"] >= 0 and box["x"] + box["width"] <= width
        link.click()
        page.wait_for_url(re.compile(r"/flyt\.html"))
        page.wait_for_selector(".flyt-lab")
        b.close()
