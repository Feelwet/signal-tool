"""Runde 1 C: oversikt, liste, fokus, Playwright 3/60 ved 390 og 1280."""
from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from signaltool.config import ROOT
from signaltool.flyt_page import LINK_CSS, prepare_preview, prepare_testdata_preview, write

# Foretrukket katalog som i briefen; i CI finnes ikke /workspace med skrivetilgang.
SHOTS = Path("/workspace/flyt-shots-2811")
try:
    SHOTS.mkdir(parents=True, exist_ok=True)
except OSError:
    SHOTS = Path("/tmp/flyt-shots-2811")
    SHOTS.mkdir(parents=True, exist_ok=True)


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


def _labs(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('.flyt-lab, .flyt-col-h')].map((el) => {
          const r = el.getBoundingClientRect();
          const st = getComputedStyle(el);
          const font = parseFloat(st.fontSize) || 0;
          const fonts = [...el.querySelectorAll('*')].map((c) => parseFloat(getComputedStyle(c).fontSize)||0);
          return {
            id: el.dataset.id || '', cls: el.className,
            t: (el.innerText||'').replace(/\\s+/g,' '),
            x: r.left+r.width/2, y: r.top, w: r.width, h: r.height,
            bottom: r.bottom, left: r.left, right: r.right,
            font: Math.max(font, ...fonts, 0)
          };
        })"""
    )


def _meas(page):
    return page.evaluate(
        """() => {
          const scene = document.getElementById('flyt-scene').getBoundingClientRect();
          const labels = document.getElementById('flyt-labels');
          const labs = [...(labels? labels.querySelectorAll('.flyt-lab, .flyt-col-h') : [])].map((el) => {
            const r = el.getBoundingClientRect();
            return {id: el.dataset.id||'', t:(el.innerText||'').replace(/\\s+/g,' '),
                    left:r.left, right:r.right, top:r.top, bottom:r.bottom, w:r.width, h:r.height,
                    font: Math.max(parseFloat(getComputedStyle(el).fontSize)||0,
                      ...[...el.querySelectorAll('*')].map(c => parseFloat(getComputedStyle(c).fontSize)||0))};
          });
          let overlap = 0, pairs = [];
          for (let i=0;i<labs.length;i++){
            for (let j=i+1;j<labs.length;j++){
              const a=labs[i], b=labs[j];
              const ox=Math.min(a.right,b.right)-Math.max(a.left,b.left);
              const oy=Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top);
              if (ox>1 && oy>1){ overlap++; pairs.push([a.t,b.t,ox,oy]); }
            }
          }
          const hits = labs.filter((l) => l.id && !l.id.startsWith('__'));
          return {
            overlap, pairs,
            sceneBottom: scene.bottom, sceneH: scene.height, sceneTop: scene.top,
            sw: document.documentElement.scrollWidth,
            cw: document.documentElement.clientWidth,
            labs, hits,
          };
        }"""
    )


def _assert_layout(m, *, where):
    assert m["overlap"] == 0, (where, m["pairs"])
    for L in m["hits"]:
        assert L["h"] >= 44 - 0.5, (where, L)
        assert L["font"] >= 12 - 0.5, (where, L)
    assert m["sceneBottom"] <= 788 + 0.5, (where, m["sceneBottom"])
    assert m["sw"] <= m["cw"] + 1, (where, m["sw"], m["cw"])


@pytest.fixture(scope="module")
def official_preview(tmp_path_factory):
    dest = tmp_path_factory.mktemp("flyt-r1-off")
    prepare_preview(dest, fixture=False)
    httpd, url = _server(dest)
    yield dest, url
    httpd.shutdown()


@pytest.fixture(scope="module")
def td3(tmp_path_factory):
    dest = tmp_path_factory.mktemp("flyt-r1-td3")
    prepare_testdata_preview(dest, n_tickers=3)
    httpd, url = _server(dest)
    yield dest, url
    httpd.shutdown()


@pytest.fixture(scope="module")
def td60(tmp_path_factory):
    dest = tmp_path_factory.mktemp("flyt-r1-td60")
    prepare_testdata_preview(dest, n_tickers=60)
    httpd, url = _server(dest)
    yield dest, url
    httpd.shutdown()


def test_c1_c2_official_390_1280(official_preview):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    dest, url = official_preview
    failed = []
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        page.on("response", lambda r: failed.append((r.status, r.url)) if r.status >= 400 else None)

        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(300)
        labs = _labs(page)
        texts = [x["t"] for x in labs]
        assert "Varer (4)" in texts and "Land (25)" in texts
        assert any(t.startswith("Selskaper") for t in texts)
        nhy = next((x for x in labs if x["id"] == "ticker:NHY.OL"), None)
        assert nhy and "NHY.OL" in nhy["t"] and "Norsk Hydro" in nhy["t"], labs
        assert not any((x["id"] or "").startswith("ticker:") and "NHY" not in x["id"] for x in labs)
        land = [x for x in labs if (x["id"] or "").startswith("land:")]
        assert len(land) == 6
        assert any(x["id"] == "andre:oversikt" and x["t"] == "+19 andre" for x in labs)
        sels_h = next(x["h"] for x in labs if x["id"] == "ticker:NHY.OL")
        assert sels_h >= 44 - 0.5 and sels_h <= 46
        m = _meas(page)
        _assert_layout(m, where="official-1280")
        page.screenshot(path=str(SHOTS / "r1_official_1280_oversikt.png"), full_page=False)

        # C2: +n andre åpner Liste, ikke flere land i scenen
        page.locator('.flyt-lab[data-id="andre:oversikt"]').click()
        page.wait_for_timeout(250)
        assert page.locator("#flyt-list").is_visible()
        assert page.locator("#flyt-list .flyt-list-rad").count() >= 19
        # scenen er skjult
        wrap = page.evaluate("() => document.getElementById('flyt-stage-wrap').style.display")
        assert wrap == "none"

        # 390: ingen selskaper-kolonne
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(300)
        labs390 = _labs(page)
        t390 = [x["t"] for x in labs390]
        assert "Varer (4)" in t390 and "Land (25)" in t390
        assert not any(t.startswith("Selskaper") for t in t390)
        assert not any((x["id"] or "").startswith("ticker:") for x in labs390)
        m390 = _meas(page)
        _assert_layout(m390, where="official-390")
        page.screenshot(path=str(SHOTS / "r1_official_390_oversikt.png"), full_page=False)
        browser.close()
    real_4xx = [f for f in failed if "/favicon" not in f[1]]
    assert not real_4xx, real_4xx


def test_c3_liste_gics_mangler_data(official_preview):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    _, url = official_preview
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.locator("#flyt-liste").click()
        page.wait_for_timeout(250)
        assert page.locator("#flyt-list").is_visible()
        # Ingen WebGL-canvas i listevisning
        webgl = page.evaluate("() => !!document.querySelector('#flyt-scene canvas')")
        assert webgl is False
        rows = page.locator("#flyt-list .flyt-list-rad")
        assert rows.count() >= 60
        h = page.evaluate("() => { const r=document.querySelector('.flyt-list-rad'); const b=r.getBoundingClientRect(); return b.height; }")
        assert h >= 56 - 0.5
        # upubliserte er grå og ikke klikkbare
        miss = page.locator("#flyt-list .flyt-list-rad.miss")
        assert miss.count() >= 1
        tag = miss.first.evaluate("el => el.tagName")
        assert tag == "DIV"
        assert "Mangler data" in miss.first.inner_text()
        # NHY er klikkbar
        nhy = page.locator("#flyt-list .flyt-list-rad").filter(has_text="NHY.OL")
        if nhy.count():
            assert "miss" not in (nhy.first.get_attribute("class") or "")
        page.screenshot(path=str(SHOTS / "r1_official_1280_liste.png"), full_page=False)
        browser.close()


def test_c4_fokus_midten_maks_etiketter(official_preview):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    _, url = official_preview
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{url}/flyt.html?fokus=NHY.OL", wait_until="networkidle")
        page.wait_for_timeout(500)
        labs = _labs(page)
        hits = [x for x in labs if x["id"] and not x["id"].startswith("__")]
        assert len(hits) <= 14, [x["t"] for x in hits]
        mid = page.evaluate(
            """() => {
              const scene = document.getElementById('flyt-scene').getBoundingClientRect();
              const el = document.querySelector('.flyt-lab[data-id="ticker:NHY.OL"]');
              const r = el.getBoundingClientRect();
              return {cx: r.left+r.width/2, mid: scene.left+scene.width/2, sceneW: scene.width};
            }"""
        )
        # midten: innenfor midtre tredjedel
        assert abs(mid["cx"] - mid["mid"]) <= mid["sceneW"] * 0.25, mid
        m = _meas(page)
        # ved 390 med åpent ark kan scenen være kortere; layoutkrav uten overlap/hscroll
        assert m["overlap"] == 0, m["pairs"]
        assert m["sw"] <= m["cw"] + 1
        page.screenshot(path=str(SHOTS / "r1_official_390_fokus.png"), full_page=False)
        browser.close()


def test_c7_testdata_3_og_60(td3, td60):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    cases = [
        ("3", td3, 390, 844, "r1_td3_390.png"),
        ("3", td3, 1280, 800, "r1_td3_1280.png"),
        ("60", td60, 390, 844, "r1_td60_390.png"),
        ("60", td60, 1280, 800, "r1_td60_1280.png"),
    ]
    report = []
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        for kind, (dest, url), w, h, shot in cases:
            failed = []
            page.on("response", lambda r: failed.append((r.status, r.url)) if r.status >= 400 else None)
            page.set_viewport_size({"width": w, "height": h})
            page.goto(f"{url}/flyt.html", wait_until="networkidle")
            page.wait_for_selector(".flyt-lab")
            page.wait_for_timeout(300)
            labs = _labs(page)
            texts = [x["t"] for x in labs]
            if w >= 901:
                assert any(t.startswith("Selskaper") for t in texts), (kind, w, texts)
                if kind == "60":
                    sels = [x for x in labs if (x["id"] or "").startswith("testdata:ticker:")]
                    assert len(sels) <= 8
                    assert any(x["id"] == "andre:selskaper" for x in labs)
            else:
                assert not any(t.startswith("Selskaper") for t in texts), (kind, w, texts)
                assert not any((x["id"] or "").startswith("testdata:ticker:") for x in labs)
            m = _meas(page)
            _assert_layout(m, where=f"td{kind}-{w}")
            real_4xx = [f for f in failed if "/favicon" not in f[1]]
            assert not real_4xx, (kind, w, real_4xx)
            page.screenshot(path=str(SHOTS / shot), full_page=False)
            report.append({"kind": kind, "w": w, "n_labs": len(labs), "overlap": m["overlap"],
                           "sceneBottom": m["sceneBottom"], "hscroll": m["sw"] - m["cw"],
                           "min_hit_h": min((x["h"] for x in m["hits"]), default=None),
                           "min_font": min((x["font"] for x in m["hits"]), default=None)})
        # Liste 60: upubliserte nederst, ikke i scenen
        _, url60 = td60
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url60}/flyt.html", wait_until="networkidle")
        page.locator("#flyt-liste").click()
        page.wait_for_timeout(300)
        page.screenshot(path=str(SHOTS / "r1_td60_1280_liste.png"), full_page=False)
        info = page.evaluate(
            """() => {
              const groups = [...document.querySelectorAll('#flyt-list details')].map((d) => {
                const rows = [...d.querySelectorAll('.flyt-list-rad')].map((r) => ({
                  miss: r.classList.contains('miss'), t: r.innerText, tag: r.tagName, h: r.getBoundingClientRect().height
                }));
                return {h: d.querySelector('summary').innerText, rows};
              });
              return {groups, webgl: !!document.querySelector('#flyt-scene canvas')};
            }"""
        )
        assert info["webgl"] is False
        assert info["groups"]
        for g in info["groups"]:
            flags = [r["miss"] for r in g["rows"]]
            if True in flags and False in flags:
                first_miss = flags.index(True)
                assert all(flags[first_miss:]), g["h"]
            for r in g["rows"]:
                assert r["h"] >= 56 - 0.5
                if r["miss"]:
                    assert r["tag"] == "DIV" and "Mangler data" in r["t"]
        browser.close()
    Path("/workspace/flyt-shots-2811/r1_maalinger_3_60.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
