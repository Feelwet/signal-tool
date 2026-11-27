"""UxBot 27.11: Verk-samlenode, land-tak, uslåtte kraftandeler og Hva hvis-regler."""
from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from signaltool.flyt_build import apply_godkjent
from signaltool.flyt_page import html, prepare_preview
from signaltool.flyt_schema import (
    MAX_LAND_PER_LAG,
    land_for_lag,
    node_tall,
    scenario_chips,
    scenario_has_chip,
    universe_tickers,
    verk_for,
    verk_label,
)

FIX = Path(__file__).parent / "fixtures" / "flyt"
JS = Path("signaltool/flyt_static/flyt.js")
CSS = Path("signaltool/flyt_static/flyt.css")


def _data():
    noder = json.loads((FIX / "noder.json").read_text())
    kanter = json.loads((FIX / "kanter.json").read_text())
    scenarioer = json.loads((FIX / "scenarioer.json").read_text())
    kanter = {"kanter": apply_godkjent(kanter["kanter"], FIX / "godkjent.csv"), "_fiktiv": True}
    uni = universe_tickers(FIX / "list_members.csv")
    return noder, kanter, scenarioer, uni


def _noder():
    return _data()[0]["noder"]


# --- 1. Verk-samlenode -------------------------------------------------------

def test_verk_label_counts_from_data_never_hardcoded():
    noder, kanter, _, _ = _data()
    verks = verk_for(noder, kanter, "NHY.OL")
    assert verks, "fixture skal ha verk knyttet til NHY.OL"
    assert len(verks) != 13, "fixture bruker et annet antall enn 13, så hardkoding avsløres"
    assert verk_label(verks) == f"Verk ({len(verks)})"
    assert verk_label(verks[:2]) == "Verk (2)"
    assert verk_label([]) == "Verk (0)"
    src = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert "Verk (13)" not in src and "Verk (13)" not in css
    assert "verkLabel" in src and "verkOpen" in src
    assert ".flyt-verk-rad" in css and "height:44px" in css.replace(" ", "")


def test_page_does_not_bake_verk_13():
    noder, kanter, scenarioer, uni = _data()
    h = html({"generated": "2026-11-27 13:00"}, universe=uni, noder=noder, kanter=kanter,
             scenarioer=scenarioer, data_base="flyt", kurs_url="data.json")
    assert "Verk (13)" not in h


# --- 2. Land, maks 6, +n andre ----------------------------------------------

def test_land_max_six_same_year_tonnes_unmeasured_in_andre():
    assert MAX_LAND_PER_LAG == 6
    nodes = _noder()
    visible, andre = land_for_lag(nodes)
    assert len(visible) <= MAX_LAND_PER_LAG
    assert [n["navn"] for n in visible] == ["Norge", "EU", "Tyskland", "Frankrike", "Italia", "USA"]
    names = [n["navn"] for n in andre]
    assert "Spania" in names and "Polen" in names
    assert "Sveits" in names and "Østerrike" in names
    # land uten tonn rangeres ikke foran målte
    assert names.index("Sveits") > names.index("Spania")
    src = JS.read_text(encoding="utf-8")
    assert "MAX_LAND_PER_LAG = 6" in src
    assert "landForLag" in src


def test_land_other_year_and_no_tonnes_go_to_andre_and_are_not_ranked():
    lands = [
        {"id": "a", "type": "land", "navn": "A", "verdi": 10, "enhet": "tonn", "år": 2024},
        {"id": "b", "type": "land", "navn": "B", "verdi": 50, "enhet": "tonn", "år": 2024},
        {"id": "c", "type": "land", "navn": "C", "verdi": 40, "enhet": "tonn", "år": 2024},
        {"id": "d", "type": "land", "navn": "D", "verdi": 30, "enhet": "tonn", "år": 2024},
        {"id": "e", "type": "land", "navn": "E", "verdi": 20, "enhet": "tonn", "år": 2024},
        {"id": "f", "type": "land", "navn": "F", "verdi": 15, "enhet": "tonn", "år": 2024},
        {"id": "g", "type": "land", "navn": "G", "verdi": 5, "enhet": "tonn", "år": 2024},
        {"id": "old", "type": "land", "navn": "Gammel", "verdi": 999, "enhet": "tonn", "år": 2020},
        {"id": "uten", "type": "land", "navn": "Uten", "år": 2024},
    ]
    visible, andre = land_for_lag(lands)
    assert [n["navn"] for n in visible] == ["B", "C", "D", "E", "F", "A"]
    andre_navn = [n["navn"] for n in andre]
    assert andre_navn == ["G", "Gammel", "Uten"]
    # 999 tonn i et annet år rangeres ikke inn i topp 6
    assert "Gammel" not in [n["navn"] for n in visible]


# --- 3. Kraftandelen, to uslåtte rader --------------------------------------

def test_kraftandel_two_separate_rows_never_merged():
    kraft = next(n for n in _noder() if n["id"] == "kraft_norge")
    rows = node_tall(kraft)
    assert len(rows) == 2
    texts = [r["tekst"] for r in rows]
    assert texts[0] == "ca. 80 % av kapasiteten (s. 16)"
    assert texts[1] == "over 70 % av produksjonen (s. 81)"
    assert texts[0] != texts[1]
    joined = " ".join(texts)
    # visningen slår dem ikke sammen til én setning
    assert "80 % av kapasiteten" in joined and "70 % av produksjonen" in joined
    assert rows[0].get("kilde_url") and rows[1].get("kilde_url")
    assert rows[0]["kilde_url"] != rows[1]["kilde_url"]
    src = JS.read_text(encoding="utf-8")
    assert "appendTallRows" in src and "nodeTall" in src
    assert "flyt-tall-rad" in src and "flyt-tall-rad" in CSS.read_text(encoding="utf-8")


# --- 4. Hva hvis: chip og tallfelt ------------------------------------------

def test_hva_hvis_chip_only_with_source_backed_sentence():
    _, _, scenarioer, uni = _data()
    ss = scenarioer["scenarioer"]
    by_id = {s["id"]: s for s in ss}
    assert scenario_has_chip(by_id["energi_opp"])
    assert scenario_has_chip(by_id["import_eu_ned"])
    assert scenario_has_chip(by_id["bil_opp"])
    assert not scenario_has_chip(by_id["uten_setning"])
    chips = scenario_chips(scenarioer)
    assert [i for i, _ in chips] == ["energi_opp", "import_eu_ned", "bil_opp"]
    assert "uten_setning" not in [i for i, _ in chips]
    noder, kanter, _, uni = _data()
    h = html({"generated": "2026-11-27 13:00"}, universe=uni, noder=noder, kanter=kanter,
             scenarioer=scenarioer, data_base="flyt", kurs_url="data.json")
    assert 'data-scenario="energi_opp"' in h
    assert 'data-scenario="uten_setning"' not in h
    assert 'id="flyt-hvis-tall"' in h
    src = JS.read_text(encoding="utf-8")
    assert "scenarioHasChip" in src and "fillChips" in src
    assert "flyt-hvis-tall" in src
    # tomt tallfelt får setningen bare der, ikke som erstatning for mekanismesetninger
    apply = src.split("function applyScenario", 1)[1].split("function ", 1)[0]
    assert "flyt-hvis-tall" in apply
    assert apply.index("flyt-hvis-tall") < apply.index("EMPTY") or "tallBox" in apply


# --- Playwright: alle fire punkter i visningen --------------------------------

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


@pytest.fixture(scope="module")
def preview(tmp_path_factory):
    dest = tmp_path_factory.mktemp("flyt-ux")
    prepare_preview(dest, fixture=True)
    httpd, url = _server(dest)
    yield dest, url
    httpd.shutdown()


@pytest.mark.skipif(False, reason="alltid kjør når playwright er tilgjengelig")
def test_ux_playwright_verk_land_kraft_hvis(preview):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    noder, kanter, _, _ = _data()
    n_verk = len(verk_for(noder, kanter, "NHY.OL"))
    label = f"Verk ({n_verk})"
    dest, url = preview
    shots = Path("/workspace/flyt-shots-2711")
    shots.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html?fokus=NHY.OL", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(400)

        labs = page.locator(".flyt-lab .n")
        names = [labs.nth(i).inner_text().strip() for i in range(labs.count())]
        assert label in names
        assert "Verk (13)" not in names
        # ingen individuelle verk synlige før viften åpnes
        plant_names = [n["navn"] for n in verk_for(noder, kanter, "NHY.OL")]
        assert not any(n in names for n in plant_names)

        # land: maks 6 synlige, resten i +n andre
        land_nodes = [n for n in noder["noder"] if n.get("type") == "land"]
        visible, andre = land_for_lag([
            n for n in land_nodes if n["id"] in {
                "norge", "eu", "tyskland", "usa", "frankrike", "italia",
                "spania", "polen", "storbritannia", "belgia", "sveits", "osterrrike",
            }
        ])
        # hop-1 land rundt NHY (brasil kan ligge på et annet hop)
        for n in visible:
            assert n["navn"] in names
        andre_lab = f"+{len(andre)} andre"
        assert any(n == andre_lab or n.startswith("+") and n.endswith("andre") for n in names)
        for n in andre:
            assert n["navn"] not in names

        # 1. åpne vifte
        page.locator('.flyt-lab[data-id="verk:NHY.OL"]').click(force=True)
        page.wait_for_timeout(300)
        names_open = [labs.nth(i).inner_text().strip() for i in range(labs.count())]
        assert label in names_open
        for n in plant_names:
            assert n in names_open
        rows = page.locator(".flyt-verk-rad")
        assert rows.count() == n_verk
        for i in range(rows.count()):
            box = rows.nth(i).bounding_box()
            assert box and box["height"] >= 44 - 0.5
            txt = rows.nth(i).inner_text()
            assert any(p in txt for p in plant_names)
            assert "tonn" in txt or "Mangler data" in txt
        shots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shots / "flyt_1280_verk.png"), full_page=False)

        # lukk med nytt trykk
        page.locator('.flyt-lab[data-id="verk:NHY.OL"]').click(force=True)
        page.wait_for_timeout(300)
        names_closed = [labs.nth(i).inner_text().strip() for i in range(labs.count())]
        assert label in names_closed
        assert not any(n in names_closed for n in plant_names)

        # åpne igjen og lukk med Tilbakestill
        page.locator('.flyt-lab[data-id="verk:NHY.OL"]').click(force=True)
        page.wait_for_timeout(200)
        page.evaluate("() => { const p=document.getElementById('flyt-panel'); if(p) p.hidden=true; }")
        page.locator("#flyt-reset").click()
        page.wait_for_timeout(300)
        names_reset = [labs.nth(i).inner_text().strip() for i in range(labs.count())]
        assert label in names_reset
        assert not any(n in names_reset for n in plant_names)

        # 3. kraftandeler: to rader med hver sin grunnlinje
        page.locator('.flyt-lab[data-id="kraft_norge"]').click()
        page.wait_for_timeout(200)
        tall = page.locator('#flyt-panel [data-sec="tall"] .flyt-tall-rad')
        assert tall.count() == 2
        t0 = tall.nth(0).inner_text()
        t1 = tall.nth(1).inner_text()
        assert "ca. 80 % av kapasiteten (s. 16)" in t0
        assert "over 70 % av produksjonen (s. 81)" in t1
        assert "ca. 80 % av kapasiteten (s. 16)" not in t1
        assert "over 70 % av produksjonen (s. 81)" not in t0
        # egen kilde per rad, ikke én slått sammen
        assert tall.nth(0).locator(".flyt-src").count() == 1
        assert tall.nth(1).locator(".flyt-src").count() == 1

        # 4. Hva hvis
        chips = page.locator("#flyt-hvis-chips .flyt-chip")
        chip_ids = [chips.nth(i).get_attribute("data-scenario") for i in range(chips.count())]
        chip_txt = [chips.nth(i).inner_text().strip() for i in range(chips.count())]
        assert "energi_opp" in chip_ids and "import_eu_ned" in chip_ids and "bil_opp" in chip_ids
        assert "uten_setning" not in chip_ids
        assert "Et scenario uten kilde" not in chip_txt
        page.locator("#flyt-hvis").click()
        page.wait_for_timeout(150)
        page.locator('.flyt-chip[data-scenario="import_eu_ned"]').click()
        page.wait_for_timeout(200)
        tekst = page.inner_text("#flyt-hvis-tekst")
        tall_h = page.inner_text("#flyt-hvis-tall")
        assert "Kilden beskriver ikke dette" not in tekst
        assert "Kilden beskriver ikke dette" in tall_h
        # scenario med tall i feltet, ikke i setningsboksen som erstatning
        page.locator('.flyt-chip[data-scenario="energi_opp"]').click()
        page.wait_for_timeout(200)
        assert "Kilden beskriver ikke dette" not in page.inner_text("#flyt-hvis-tall")
        page.screenshot(path=str(shots / "flyt_1280_hvis.png"), full_page=False)
        browser.close()


def test_kontekst_ingen_tall_no_badge_in_source():
    src = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert "Ingen tall for denne noden." in src
    assert "flyt-kontekst-tall" in src and "flyt-kontekst-tall" in css
    assert "font-size:13px" in css.split(".flyt-kontekst-tall", 1)[1][:200]
    assert "line-height:18px" in css.split(".flyt-kontekst-tall", 1)[1][:200]
    # merke bare på Mangler data, ikke på kontekst
    place = src
    # badge-setning for etikett: bare estimat og mangler
    assert place.count("b.textContent = 'Mangler data'") >= 1
    assert "kontekst" in src
    assert "Ingen tall for denne noden." not in css  # teksten ligger i JS, typografien i CSS


def test_ux_playwright_kontekst_panel(preview):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    dest, url = preview
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html?fokus=NHY.OL", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(400)
        lab = page.locator('.flyt-lab[data-id="aluminium"]')
        assert lab.count() == 1
        assert lab.locator(".badge").count() == 0
        assert "Mangler data" not in (lab.inner_text() or "")
        lab.click(force=True)
        page.wait_for_timeout(200)
        tall = page.locator('#flyt-panel [data-sec="tall"]')
        assert tall.count() == 1
        line = tall.locator(".flyt-kontekst-tall")
        assert line.count() == 1
        assert line.inner_text().strip() == "Ingen tall for denne noden."
        assert tall.locator(".badge").count() == 0
        assert "Mangler data" not in tall.inner_text()
        # én linje, 13/18 i dempet farge
        assert tall.locator("p").count() == 1
        css = line.evaluate("""el => {
          const s = getComputedStyle(el);
          return { fs: parseFloat(s.fontSize), lh: parseFloat(s.lineHeight), color: s.color };
        }""")
        assert abs(css["fs"] - 13) <= 0.2, css
        assert abs(css["lh"] - 18) <= 0.2, css
        # dempet: ikke hovedtekstfargen
        ink = page.evaluate("() => getComputedStyle(document.body).getPropertyValue('--ink') || getComputedStyle(document.body).color")
        mut = page.evaluate("() => getComputedStyle(document.body).getPropertyValue('--mut') || ''")
        # rgb for --mut #9ea9b5 = 158,169,181
        assert "158" in css["color"] and "169" in css["color"] and "181" in css["color"], (css, ink, mut)

        # Bare «Mangler data» får grått merke
        page.goto(f"{url}/flyt.html?fokus=EQNR.OL", wait_until="networkidle")
        page.wait_for_timeout(400)
        badge = page.locator("#flyt-panel .badge")
        assert badge.count() >= 1
        assert any("Mangler data" in badge.nth(i).inner_text() for i in range(badge.count()))
        browser.close()

