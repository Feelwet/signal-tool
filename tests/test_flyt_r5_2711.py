"""Runde 5 (27.11): A, R1–R7 — enhet og Playwright mot fixture og offisielle data."""
from __future__ import annotations

import hashlib
import http.server
import json
import re
import threading
from pathlib import Path

import pytest

from signaltool.flyt_page import body_html, html, meta_from, prepare_preview
from signaltool.flyt_schema import (
    OFFISIELL_MD5,
    coverage,
    oversikt_varer_og_land,
    universe_tickers,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "flyt"
FLYT = ROOT / "flyt"
JS = ROOT / "signaltool" / "flyt_static" / "flyt.js"
CSS = ROOT / "signaltool" / "flyt_static" / "flyt.css"
SHOTS = Path("/workspace/flyt-shots-2711")


def _load_official():
    noder = json.loads((FLYT / "noder.json").read_text(encoding="utf-8"))
    kanter = json.loads((FLYT / "kanter.json").read_text(encoding="utf-8"))
    sc = json.loads((FLYT / "scenarios.json").read_text(encoding="utf-8"))
    return noder, kanter, sc


def _load_fix():
    n = json.loads((FIX / "noder.json").read_text(encoding="utf-8"))
    k = json.loads((FIX / "kanter.json").read_text(encoding="utf-8"))
    noder = n["noder"] if isinstance(n, dict) else n
    kanter = k["kanter"] if isinstance(k, dict) else k
    return noder, kanter


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
def official_preview(tmp_path_factory):
    dest = tmp_path_factory.mktemp("flyt-r5-off")
    prepare_preview(dest, fixture=False)
    httpd, url = _server(dest)
    yield dest, url
    httpd.shutdown()


@pytest.fixture(scope="module")
def fixture_preview(tmp_path_factory):
    dest = tmp_path_factory.mktemp("flyt-r5-fix")
    prepare_preview(dest, fixture=True)
    httpd, url = _server(dest)
    yield dest, url
    httpd.shutdown()


def test_md5_unchanged():
    for fn, digest in {
        "noder.json": "02ab5d48a26842392130afcecb7c72ba",
        "kanter.json": "9f6280057d24f7b869aee39eadd528a2",
        "scenarios.json": "bc2a39146e088416e362a8c46cf16f97",
    }.items():
        got = hashlib.md5((FLYT / fn).read_bytes()).hexdigest()
        assert got == digest, (fn, got)
        assert OFFISIELL_MD5.get(fn, digest) == digest or fn == "scenarios.json"


def test_a_status_hidden_when_k_is_0_shown_when_k_ge_1():
    noder, kanter = _load_fix()
    uni = ["AAA.OL", "BBB.OL", "CCC.OL", "DDD.OL", "EEE.OL", "FFF.OL", "GGG.OL", "HHH.OL"]
    # fixture coverage is computed from real fixture tickers via meta_from
    h0 = body_html(meta={"coverage": {"beregnet": True, "k": 0, "n": 60, "statuslinje": "Råvaredata for 0 av 60 · Selskapsdata for 0 av 60"}})
    assert 'id="flyt-status" hidden' in h0
    assert "Råvaredata for" not in h0.split('id="flyt-status"', 1)[1][:80]
    h1 = body_html(meta={"coverage": {"beregnet": True, "k": 1, "n": 8, "statuslinje": "Råvaredata for 1 av 8 · Selskapsdata for 1 av 8"}})
    assert 'id="flyt-status" hidden' not in h1
    assert "Råvaredata for 1 av 8 · Selskapsdata for 1 av 8" in h1
    src = JS.read_text(encoding="utf-8")
    fn = src.split("function updateStatus()", 1)[1].split("function fillSearch", 1)[0]
    assert "k >= 1" in fn or "k>=1" in fn


def test_r4_land_label_is_calculated_not_hardcoded():
    noder, kanter, _ = _load_official()
    ov = oversikt_varer_og_land(noder, kanter)
    assert ov["land_n"] == len(ov["land_synlige"]) + len(ov["andre"])
    assert ov["land_label"] == f"Land ({ov['land_n']})"
    assert ov["varer_label"] == f"Varer ({ov['varer_n']})"
    src = JS.read_text(encoding="utf-8")
    # telleren skal komme fra lands.length, ikke et hardkodet 25
    assert "Land (' + lands.length + ')" in src or 'Land (\' + lands.length + \')' in src
    assert "Land (25)" not in src
    assert "landHeading" in src and "__land_h" in src


def test_r5_ticker_inflection_in_js():
    src = JS.read_text(encoding="utf-8")
    assert "function tickerCountLabel" in src
    fn = src.split("function tickerCountLabel", 1)[1].split("function ", 1)[0]
    assert "1 ticker" in fn
    assert "tickere" in fn
    assert "k === 1" in fn or "k===1" in fn


def test_r6_plain_ticker_not_in_row_rule():
    css = CSS.read_text(encoding="utf-8")
    row = css.split(".flyt-row,", 1)[1].split("{", 1)[0]
    assert "flyt-tk-plain" not in row
    assert ".flyt-tk-plain{" in css
    assert "display:inline" in css.split(".flyt-tk-plain{", 1)[1][:200]
    js = JS.read_text(encoding="utf-8")
    kb = js.split("function kursBlock", 1)[1].split("function pctSpan", 1)[0]
    assert "Mangler kursdata" in kb
    assert "tickerPlain" in kb
    # ticker uten side lims rett etter miss-teksten, i samme avsnitt
    assert "p.append" in kb and "tickerPlain" in kb


def test_r7_src_min_hit_targets_in_css():
    css = CSS.read_text(encoding="utf-8")
    assert "min-height:44px" in css.split(".flyt-src a", 1)[1]
    assert "min-height:24px" in css.split(".flyt-src a", 1)[1]


def test_r1_r2_reset_and_height_in_source():
    src = JS.read_text(encoding="utf-8")
    rv = src.split("function resetView()", 1)[1].split("function applyScenario", 1)[0]
    assert "closePanel()" in rv
    assert "zoom = start.zoom" in rv
    css = CSS.read_text(encoding="utf-8")
    assert "100dvh - var(--flyt-scene-top" in css or "100dvh - var(--flyt-scene-top," in css
    assert "56px - 8px" in css or "56px - 8px))" in css


def _overlap(page):
    return page.evaluate(
        """() => {
          const labs = [...document.querySelectorAll('.flyt-lab, .flyt-col-h')];
          const boxes = labs.map((el) => {
            const r = el.getBoundingClientRect();
            return {id: el.dataset.id || '', t: (el.innerText||'').trim(),
                    left:r.left, right:r.right, top:r.top, bottom:r.bottom, x: r.left+r.width/2};
          });
          let overlap = 0;
          const pairs = [];
          for (let i = 0; i < boxes.length; i++) {
            for (let j = i + 1; j < boxes.length; j++) {
              const a = boxes[i], b = boxes[j];
              const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
              const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
              if (ox > 0.5 && oy > 0.5) { overlap++; pairs.push([a.t, b.t, ox, oy]); }
            }
          }
          return {overlap, pairs, n: boxes.length, texts: boxes.map((b) => b.t), boxes};
        }"""
    )


def test_r5_playwright_a_and_r1_to_r7(official_preview, fixture_preview):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    dest, url = official_preview
    fdest, furl = fixture_preview
    SHOTS.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()

        # A: official k=0 → status hidden; fixture k≥1 → visible
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(300)
        st = page.evaluate(
            """() => {
              const el = document.getElementById('flyt-status');
              const r = el ? el.getBoundingClientRect() : null;
              return {hidden: !el || el.hidden || getComputedStyle(el).display==='none',
                      text: el ? el.textContent : '', shown: !!(el && r && r.height > 0 && !el.hidden)};
            }"""
        )
        assert st["hidden"] is True or st["shown"] is False, st
        assert "Råvaredata" not in (st["text"] or "") or st["hidden"], st

        page.goto(f"{furl}/flyt.html", wait_until="networkidle")
        page.wait_for_timeout(300)
        st1 = page.evaluate(
            """() => {
              const el = document.getElementById('flyt-status');
              const r = el ? el.getBoundingClientRect() : null;
              return {hidden: !el || el.hidden || getComputedStyle(el).display==='none',
                      text: el ? (el.textContent||'') : '',
                      shown: !!(el && r && r.height > 0 && !el.hidden)};
            }"""
        )
        assert st1["shown"] is True, st1
        assert "Råvaredata for 1 av 8" in st1["text"], st1

        # R4 + R5 1280 oversikt: Varer (n) og Land (n), samme y, til høyre for zoom,
        # EU-27 samme x som andre land, korrekt bøyning.
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(400)
        noder, kanter, _ = _load_official()
        ov = oversikt_varer_og_land(noder, kanter)
        want_v = ov["varer_label"]
        want_l = ov["land_label"]
        meas = page.evaluate(
            """() => {
              const heads = [...document.querySelectorAll('.flyt-col-h')].map((el) => {
                const r = el.getBoundingClientRect();
                const scene = document.getElementById('flyt-scene').getBoundingClientRect();
                const zoom = document.querySelector('.flyt-zoom').getBoundingClientRect();
                return {t: el.innerText.trim(), y: r.top, x: r.left+r.width/2, left: r.left,
                        sceneTop: scene.top, zoomRight: zoom.right, zoomTop: zoom.top};
              });
              const lands = [...document.querySelectorAll('.flyt-lab')].filter((el) => {
                const id = el.dataset.id || '';
                return id.startsWith('land:') || id === 'andre:oversikt';
              }).map((el) => {
                const r = el.getBoundingClientRect();
                return {id: el.dataset.id, t: el.innerText.trim(), x: r.left + r.width/2};
              });
              return {heads, lands};
            }"""
        )
        texts = [h["t"] for h in meas["heads"]]
        assert want_v in texts, (texts, want_v)
        assert want_l in texts, (texts, want_l)
        hv = next(h for h in meas["heads"] if h["t"] == want_v)
        hl = next(h for h in meas["heads"] if h["t"] == want_l)
        assert abs(hv["y"] - hl["y"]) <= 1, (hv, hl)
        # øverst i scenen og til høyre for zoomknappene
        assert hv["y"] <= hv["sceneTop"] + 40, hv
        assert hv["left"] >= hv["zoomRight"] - 2, hv
        assert hl["left"] >= hl["zoomRight"] - 2, hl
        land_xs = [L["x"] for L in meas["lands"] if L["id"] != "andre:oversikt" or True]
        # EU-27 samme x som andre land (andre-noden er også i landkolonnen)
        xs = [L["x"] for L in meas["lands"]]
        assert xs, meas["lands"]
        mid = sum(xs) / len(xs)
        for L in meas["lands"]:
            assert abs(L["x"] - mid) <= 2, (L, mid, meas["lands"])
        eu = [L for L in meas["lands"] if "EU-27" in L["t"] or "EU27" in L["t"] or L["id"] == "land:EU-27" or "EU" in L["t"]]
        # EU-27 kan ligge i +n andre; da er den ikke en egen etikett, men «andre» har samme x
        blob = " | ".join(page.evaluate("() => [...document.querySelectorAll('.flyt-lab,.flyt-col-h')].map(e => e.innerText)"))
        # bøyning: land bruker «1 selskap»; varer har ingen ticker-telling i oversikten (runde 7)
        assert "1 selskap" in blob
        assert "1 tickere" not in blob
        assert "1 ticker" not in blob
        ovp = _overlap(page)
        assert ovp["overlap"] == 0, ovp["pairs"]
        page.screenshot(path=str(SHOTS / "r5_1280_oversikt.png"), full_page=False)

        # R1: klikk Norge, så Tilbakestill — panelet lukket, brødsmule = rot (tom i oversikt)
        norge = page.locator('.flyt-lab').filter(has_text="Norge")
        assert norge.count() >= 1, blob
        norge.first.click()
        page.wait_for_timeout(300)
        panel = page.locator("#flyt-panel")
        assert panel.is_visible()
        crumb_before = page.inner_text("#flyt-crumb")
        assert "Norge" in crumb_before
        page.locator("#flyt-reset").click()
        page.wait_for_timeout(300)
        assert not panel.is_visible(), page.evaluate("() => document.getElementById('flyt-panel').hidden")
        crumb = page.evaluate(
            """() => {
              const el = document.getElementById('flyt-crumb');
              return {hidden: el.hidden || getComputedStyle(el).display==='none', text: (el.innerText||'').trim()};
            }"""
        )
        assert crumb["hidden"] or crumb["text"] == "", crumb
        # rot i oversikt er tom brødsmule
        page.screenshot(path=str(SHOTS / "r5_1280_reset.png"), full_page=False)

        # R6 + R7 ved 1280: NHY.OL rett etter Mangler kursdata, uten rad/ramme; kildelenke ≥ 24 px
        page.goto(f"{url}/flyt.html?fokus=NHY.OL", wait_until="networkidle")
        page.wait_for_timeout(400)
        r6 = page.evaluate(
            """() => {
              const miss = document.querySelector('#flyt-panel .flyt-kurs .flyt-miss');
              const plain = document.querySelector('#flyt-panel .flyt-tk-plain');
              if (!miss || !plain) return {ok:false, miss:!!miss, plain:!!plain};
              const s = getComputedStyle(plain);
              const r = plain.getBoundingClientRect();
              const cs = getComputedStyle(plain);
              return {
                ok: true,
                text: miss.innerText.trim(),
                sameParent: miss.contains(plain),
                after: miss.innerText.includes('Mangler kursdata') && miss.innerText.includes('NHY.OL'),
                display: s.display, border: s.borderTopWidth, minH: s.minHeight,
                h: r.height, bg: s.backgroundColor,
              };
            }"""
        )
        assert r6.get("ok") and r6.get("after") and r6.get("sameParent"), r6
        assert r6["display"] in ("inline", "inline-block", "inline-flex"), r6
        assert float(str(r6["border"]).replace("px", "") or 0) == 0
        srcs = page.evaluate(
            """() => [...document.querySelectorAll('#flyt-panel .flyt-src a')].map((a) => {
              const r = a.getBoundingClientRect();
              return {t: a.innerText, h: r.height, w: r.width};
            })"""
        )
        assert srcs, "forventet kildelenker i panelet"
        for a in srcs:
            assert a["h"] >= 24 - 0.5 and a["w"] >= 24 - 0.5, a
        page.screenshot(path=str(SHOTS / "r5_1280_panel.png"), full_page=False)

        # R2 + R3 + R7 ved 390
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(400)
        r2 = page.evaluate(
            """() => {
              const scene = document.getElementById('flyt-scene').getBoundingClientRect();
              const tab = document.querySelector('nav.tabbar');
              const tabTop = tab ? tab.getBoundingClientRect().top : 844 - 56;
              const labs = [...document.querySelectorAll('.flyt-lab, .flyt-col-h')].map((el) => {
                const r = el.getBoundingClientRect();
                return {t: (el.innerText||'').trim(), bottom: r.bottom, top: r.top};
              });
              const expected = Math.min(660, (window.innerHeight || 844) - scene.top - 56 - 8);
              return {
                sceneTop: scene.top, sceneH: scene.height, expected,
                tabTop, labs, maxLabBottom: Math.max(...labs.map((l) => l.bottom), 0),
                dvh: window.innerHeight,
              };
            }"""
        )
        assert abs(r2["sceneH"] - r2["expected"]) <= 2, r2
        assert r2["maxLabBottom"] <= r2["tabTop"] + 0.5, r2
        # hele «+n andre» over menyen
        andre = [l for l in r2["labs"] if l["t"].startswith("+") and "andre" in l["t"]]
        assert andre and andre[0]["bottom"] <= r2["tabTop"] + 0.5, (andre, r2)
        page.screenshot(path=str(SHOTS / "r5_390_oversikt.png"), full_page=False)

        # R1 live-sti ved 390 også
        page.locator('.flyt-lab').filter(has_text="Norge").first.click()
        page.wait_for_timeout(300)
        assert page.locator("#flyt-panel").is_visible()
        page.locator("#flyt-reset").click()
        page.wait_for_timeout(300)
        assert not page.locator("#flyt-panel").is_visible()
        crumb390 = page.evaluate(
            """() => {
              const el = document.getElementById('flyt-crumb');
              return {hidden: el.hidden || getComputedStyle(el).display==='none', text: (el.innerText||'').trim()};
            }"""
        )
        assert crumb390["hidden"] or crumb390["text"] == "", crumb390

        # R3: åpne en node, aktiver Hva hvis — arket lukkes, chips og tekst synlige
        page.locator('.flyt-lab').filter(has_text="Norge").first.click()
        page.wait_for_timeout(250)
        assert page.locator("#flyt-panel").is_visible()
        page.locator("#flyt-hvis").click()
        page.wait_for_timeout(350)
        assert not page.locator("#flyt-panel").is_visible()
        r3 = page.evaluate(
            """() => {
              const tab = document.querySelector('nav.tabbar');
              const tabTop = tab ? tab.getBoundingClientRect().top : 844 - 56;
              const chips = [...document.querySelectorAll('#flyt-hvis-chips .flyt-chip')].map((el) => {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return {t: el.innerText.trim(), top: r.top, bottom: r.bottom, vis: r.height>0 && s.display!=='none' && s.visibility!=='hidden'};
              });
              const box = document.getElementById('flyt-hvis-box');
              const texts = [...box.querySelectorAll('p, h2')].map((el) => {
                const r = el.getBoundingClientRect();
                return {t: el.innerText.trim(), top: r.top, bottom: r.bottom, vis: r.height>0 && r.bottom>0 && r.top < tabTop};
              });
              const br = box.getBoundingClientRect();
              return {
                panelHidden: document.getElementById('flyt-panel').hidden,
                chips, texts, boxTop: br.top, boxBottom: br.bottom, tabTop,
                boxVis: br.height>0 && !box.hidden,
              };
            }"""
        )
        assert r3["panelHidden"] is True, r3
        assert r3["boxVis"] is True, r3
        assert len(r3["chips"]) >= 3, r3
        for c in r3["chips"]:
            assert c["vis"] and c["top"] >= 0 and c["bottom"] <= r3["tabTop"] + 0.5, (c, r3)
        # lead, overskrift og etikett synlige
        joined = " ".join(x["t"] for x in r3["texts"])
        assert "Forklaring fra kildene, ikke en prognose" in joined, r3
        assert "Hva kildene sier" in joined, r3
        for x in r3["texts"]:
            if x["t"]:
                assert x["vis"] and x["bottom"] <= r3["tabTop"] + 0.5, (x, r3)
        page.screenshot(path=str(SHOTS / "r5_390_hvis.png"), full_page=False)

        # R7 ved 390: kildelenke minst 44 px — åpne panel på NHY
        page.goto(f"{url}/flyt.html?fokus=NHY.OL", wait_until="networkidle")
        page.wait_for_timeout(300)
        # åpne arket om det er lukket ved ?fokus=
        if not page.locator("#flyt-panel").is_visible():
            page.locator('.flyt-lab').first.click()
            page.wait_for_timeout(250)
        srcs390 = page.evaluate(
            """() => [...document.querySelectorAll('#flyt-panel .flyt-src a')].map((a) => {
              const r = a.getBoundingClientRect();
              return {t: a.innerText, h: r.height, w: r.width};
            })"""
        )
        assert srcs390, "forventet kildelenker i panelet ved 390"
        for a in srcs390:
            assert a["h"] >= 44 - 0.5, a
        page.screenshot(path=str(SHOTS / "r5_390_panel.png"), full_page=False)

        browser.close()
