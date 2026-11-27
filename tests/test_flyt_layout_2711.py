"""Headless målkrav for flyt.html ved 390 og 1280, med fiktiv fixture lokalt."""
from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest

from signaltool.flyt_page import prepare_preview

def _launch(p):
    import os
    from pathlib import Path
    chrome = os.environ.get("FLY_CHROME") or "/usr/bin/google-chrome"
    try:
        return p.chromium.launch()
    except Exception:
        if Path(chrome).exists():
            return p.chromium.launch(executable_path=chrome, headless=True)
        raise

SHOTS = Path("/workspace/flyt-shots-2711")

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402


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
    dest = tmp_path_factory.mktemp("flyt-preview")
    prepare_preview(dest, fixture=True)
    httpd, url = _server(dest)
    yield dest, url
    httpd.shutdown()


def _check(page, width, height, url, shot_name):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{url}/flyt.html?fokus=NHY.OL", wait_until="networkidle")
    page.wait_for_selector("#flyt-top")
    page.wait_for_timeout(300)
    # ingen hscroll
    scroll = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, bw: document.body.scrollWidth})")
    assert scroll["sw"] <= scroll["cw"] + 1, scroll
    assert scroll["bw"] <= scroll["cw"] + 1, scroll
    top = page.locator("#flyt-top").bounding_box()
    scene = page.locator("#flyt-scene").bounding_box()
    assert top and scene
    assert top["y"] >= 0 and top["y"] + top["height"] <= height
    if width == 390:
        assert top["y"] + top["height"] < height  # topprad over bretten
        visible_scene = min(scene["y"] + scene["height"], height) - scene["y"]
        assert visible_scene >= 300, visible_scene
        assert abs(scene["width"] - 390) <= 1 or scene["width"] <= 390
        assert abs(scene["height"] - 420) <= 2
    if width == 1280:
        assert abs(scene["width"] - 840) <= 2, scene
        assert abs(scene["height"] - 600) <= 2, scene
        panel = page.locator("#flyt-panel")
        if panel.is_visible():
            box = panel.bounding_box()
            if box:
                assert abs(box["width"] - 400) <= 2 or box["width"] <= 400
    # trykkflater minst 44
    sels = ["#flyt-kart", "#flyt-liste", "#flyt-hvis", "#flyt-zoom-in", "#flyt-zoom-out", "#flyt-reset", "#flyt-q"]
    for sel in sels:
        box = page.locator(sel).bounding_box()
        assert box, sel
        assert box["height"] >= 44 - 0.5, (sel, box)
        assert box["width"] >= 44 - 0.5, (sel, box)
    # etiketter minst 13 px
    fonts = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('.flyt-lab .n').forEach(el => {
        const s = getComputedStyle(el);
        out.push(parseFloat(s.fontSize));
      });
      return out;
    }""")
    assert fonts, "ingen etiketter"
    assert all(f >= 13 - 0.1 for f in fonts), fonts
    # tilbakestill: lukk detaljpanelet så det ikke dekker knappene
    page.evaluate("() => { const p=document.getElementById('flyt-panel'); if(p) p.hidden=true; }")
    page.wait_for_timeout(100)
    page.locator("#flyt-zoom-in").click()
    page.locator("#flyt-reset").click()
    page.wait_for_timeout(200)
    # URL-fokus beholdes, visningen er tilbake
    assert "fokus=NHY.OL" in page.url
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / shot_name), full_page=False)


def test_layout_390_and_1280(preview):
    dest, url = preview
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        _check(page, 390, 844, url, "flyt_390.png")
        _check(page, 1280, 800, url, "flyt_1280.png")
        # oversikt uten fokus
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_timeout(300)
        page.screenshot(path=str(SHOTS / "flyt_1280_oversikt.png"), full_page=False)
        status = page.inner_text("#flyt-status")
        assert status == "Råvaredata for 1 av 8 · Selskapsdata for 1 av 8"
        browser.close()
