"""PWA 01.11: manifest, ikoner, SW (network-first for HTML/data, build-versjonert cache), iOS-meta, installer-lenke, ferskhet i appen."""
import json
import struct
import pytest
import signaltool.pwa as P
import signaltool.mstrip as M
from datetime import date, datetime, timezone


def test_manifest_spec():
    m = P.manifest()
    assert m["name"] == "Signal-tool" and m["short_name"] == "Signal" and m["display"] == "standalone"
    assert m["start_url"] == m["scope"] == "/signal-tool/" and m["background_color"] == "#111821" and m["theme_color"] == "#1c2430"
    sizes = {(i["sizes"], i["purpose"]) for i in m["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= sizes


def test_icon_png_sizes():   # uten Pillow: les IHDR
    for fn, px, _ in P.ICONS:
        b = (P.ICON_DIR / fn).read_bytes()
        assert b[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", b[16:24]) == (px, px)


def test_icons_sizes_and_colors():
    Image = pytest.importorskip("PIL.Image")
    for fn, px, mask in P.ICONS:
        im = Image.open(P.ICON_DIR / fn).convert("RGB")
        assert im.size == (px, px)
        assert im.getpixel((1, 1)) == (0x11, 0x18, 0x21)
        if mask:   # G innenfor midterste 60 %
            blue = [(x, y) for x in range(0, px, 2) for y in range(0, px, 2) if im.getpixel((x, y))[2] > 200]
            lo, hi = px * 0.2, px * 0.8
            assert blue and all(lo <= x <= hi and lo <= y <= hi for x, y in blue)


def test_sw_network_first_and_versioned(tmp_path):
    P.write(tmp_path, "abc123")
    sw = (tmp_path / "sw.js").read_text()
    assert "st-abc123" in sw and "caches.delete" in sw and "cache:'no-store'" in sw and 'data-offline="1"' in sw
    assert json.loads((tmp_path / "manifest.webmanifest").read_text())["short_name"] == "Signal"
    assert all((tmp_path / "icons" / fn).exists() for fn, _, _ in P.ICONS)


def test_head_and_js():
    h = P.head("../")
    for x in ('rel="manifest" href="../manifest.webmanifest"', 'apple-touch-icon', 'name="theme-color" content="#1c2430"',
              'apple-mobile-web-app-capable', 'apple-mobile-web-app-title" content="Signal"', 'black-translucent'):
        assert x in h
    j = P.js("../")
    assert "register('../sw.js',{scope:'../'})" in j and "register('sw.js',{scope:'./'})" in P.js("") and "Frakoblet, viser data fra {dato}" in j and "beforeinstallprompt" in j and "prompt()" in j
    assert "Del → Legg til på Hjem-skjerm" in P.install_html() and "hidden" in P.install_html()
    assert "env(safe-area-inset-top" in P.CSS and "#fdba74" in P.CSS and "13px" in P.CSS and "#94a3b8" in P.CSS


def test_strip_has_price_date_for_client_freshness():
    s = {"dates": ["2026-10-27", "2026-10-28"], "close": [50.0, 51.0]}
    h = M.field(M.FIELDS[0], {"BZ=F": s}, datetime(2026, 10, 29, 6, 0, tzinfo=timezone.utc))
    assert 'data-d="2026-10-28"' in h
