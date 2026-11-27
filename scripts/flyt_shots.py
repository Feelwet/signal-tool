#!/usr/bin/env python3
"""Lokal headless sjekk av flyt.html ved 390 og 1280 med fiktiv fixture. Lagrer /workspace/flyt-shots-2711/."""
from __future__ import annotations

import http.server
import shutil
import sys
import tempfile
import threading
from pathlib import Path

SHOTS = Path("/workspace/flyt-shots-2711")


def main() -> int:
    from playwright.sync_api import sync_playwright
    from signaltool.flyt_page import prepare_preview

    dest = Path(tempfile.mkdtemp(prefix="flyt-shots-"))
    try:
        prepare_preview(dest, fixture=True)
        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(dest), **k)
            def log_message(self, *a, **k):
                pass
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{httpd.server_address[1]}"
        SHOTS.mkdir(parents=True, exist_ok=True)
        fails = []
        with sync_playwright() as p:
            chrome = "/usr/bin/google-chrome"
            try:
                browser = p.chromium.launch()
            except Exception:
                browser = p.chromium.launch(executable_path=chrome, headless=True)
            page = browser.new_page()
            for width, height, name, q in (
                (390, 844, "flyt_390.png", "?fokus=NHY.OL"),
                (1280, 800, "flyt_1280.png", "?fokus=NHY.OL"),
                (1280, 800, "flyt_1280_oversikt.png", ""),
            ):
                page.set_viewport_size({"width": width, "height": height})
                page.goto(f"{url}/flyt.html{q}", wait_until="networkidle")
                page.wait_for_timeout(400)
                sw = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
                if sw > 1:
                    fails.append(f"{name}: hscroll {sw}px")
                if width == 390:
                    scene = page.locator("#flyt-scene").bounding_box()
                    top = page.locator("#flyt-top").bounding_box()
                    vis = min(scene["y"] + scene["height"], height) - scene["y"]
                    if vis < 300:
                        fails.append(f"{name}: bare {vis:.0f} px av scenen over bretten")
                    if top["y"] >= height:
                        fails.append(f"{name}: topprad under bretten")
                page.screenshot(path=str(SHOTS / name), full_page=False)
                print(f"skrev {SHOTS / name}")
            browser.close()
        httpd.shutdown()
    finally:
        shutil.rmtree(dest, ignore_errors=True)
    if fails:
        print("FEIL:", *fails, sep="\n- ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
