"""UxBot 23.11: varsellinje under header.top når snapshotet er mer enn 36 timer gammelt."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from signaltool import site as S

OSLO = ZoneInfo("Europe/Oslo")
GEN = "2026-11-18 00:57"
ISO = "2026-11-18T00:57:00+01:00"
TEXT = "Dataene er ikke oppdatert siden 18.11 kl. 00:57."
TITLES = (
    "Oversikt", "Trender", "Temaer", "Tickere", "Makro", "Kalender",
    "Oslo Børs", "Sektorer", "Metode", "Om siden", "Signal-boka", "Nyheter",
    "EQNR.OL",
)


def _page(title="Tickere", generated=GEN, body="<p>x</p>"):
    return S.page(title, body, 0, {"generated": generated} if generated is not None else None)


def test_timestamp_and_text_from_same_source():
    dt = S.gen_dt(GEN)
    assert dt is not None and dt.tzinfo is not None
    assert S.gen_iso(GEN) == dt.isoformat() == ISO
    assert S.gen_short(GEN) == dt.strftime("%d.%m %H:%M") == "18.11 00:57"
    html = _page()
    assert f'data-generated="{ISO}"' in html
    assert "Oppdatert 18.11 kl. 00:57" in html
    assert TEXT in html
    # én kilde: ISO på body, Oppdatert-tekst, varseltekst og data-hent kommer av samme generated-felt
    assert 'data-hent="18.11 kl. 00:57"' in html
    assert html.count("18.11 kl. 00:57") == 3
    assert 'id="stale-line"' in html and " hidden" in html[html.find('id="stale-line"'):html.find('id="stale-line"') + 80]


def test_banner_in_template_on_all_pages():
    src = Path("signaltool/site.py").read_text()
    assert 'id="stale-line"' in src and "data-generated" in src
    assert "Date.now()-ts>36*60*60*1000" in src
    for title in TITLES:
        html = _page(title)
        assert 'id="stale-line" class="stale-line" hidden' in html, title
        assert f'data-generated="{ISO}"' in html, title
        assert TEXT in html, title
        # uten JS er linja skjult (hidden i markup)
        i = html.find('id="stale-line"')
        tag = html[html.rfind("<", 0, i):html.find(">", i) + 1]
        assert "hidden" in tag
    # uten generated: linja finnes likevel, men uten tekst og uten tidsstempel
    html = S.page("Tickere", "<p>x</p>", 0, None)
    assert 'id="stale-line" class="stale-line" hidden' in html
    assert " data-generated=" not in html and "data-generated='" not in html
    assert "Dataene er ikke oppdatert siden" not in html


def test_banner_css_spec():
    css = S.CSS
    assert ".stale-line{" in css
    block = css[css.find(".stale-line{"):css.find("}", css.find(".stale-line{")) + 1]
    assert "height:44px" in block and "min-height:44px" in block and "max-height:44px" in block
    assert "background:#1f2733" in block
    assert "border-left:3px solid var(--warn)" in block
    assert "font-size:13px" in block and "line-height:18px" in block
    assert "color:#e6edf3" in block
    assert ".stale-line[hidden]{display:none!important}" in css


def _clock_page(tmp_path: Path, now: datetime) -> dict:
    pw = pytest.importorskip("playwright.sync_api")
    html = _page()
    f = tmp_path / "stale.html"
    # style.css finnes ikke ved file://, så CSS fra S.CSS må inn i siden
    if "<link rel=\"stylesheet\"" in html:
        html = html.replace(
            html[html.find("<link rel=\"stylesheet\""):html.find(">", html.find("<link rel=\"stylesheet\"")) + 1],
            f"<style>{S.CSS}</style>",
            1,
        )
    f.write_text(html)
    epoch_ms = int(now.timestamp() * 1000)
    with pw.sync_playwright() as p:
        b = p.chromium.launch(channel="chrome" if shutil.which("google-chrome") else None)
        pg = b.new_page()
        pg.add_init_script(f"Date.now=()=>{epoch_ms};")
        pg.goto(f.as_uri())
        got = pg.evaluate("""()=>{
          const el=document.getElementById('stale-line');
          const r=el.getBoundingClientRect();
          return {hidden:el.hidden, text:el.textContent, iso:document.body.getAttribute('data-generated'),
                  h:r.height, w:r.width, display:getComputedStyle(el).display,
                  bg:getComputedStyle(el).backgroundColor, fs:getComputedStyle(el).fontSize,
                  lh:getComputedStyle(el).lineHeight, color:getComputedStyle(el).color};
        }""")
        pg.close()
        b.close()
    return got


@pytest.mark.skipif(not (shutil.which("google-chrome") or shutil.which("chromium")), reason="ingen headless Chrome")
def test_headless_shown_at_37h_hidden_at_35h(tmp_path):
    start = S.gen_dt(GEN)
    hidden = _clock_page(tmp_path, start + timedelta(hours=35))
    assert hidden["iso"] == ISO
    assert hidden["hidden"] is True or hidden["display"] == "none"
    assert hidden["h"] == 0
    shown = _clock_page(tmp_path / "t37" if False else tmp_path, start + timedelta(hours=37))
    # same tmp file is overwritten; write again inside helper — call with 37h
    shown = _clock_page(tmp_path, start + timedelta(hours=37))
    assert shown["hidden"] is False
    assert shown["display"] != "none"
    assert shown["text"] == TEXT
    assert shown["h"] == 44 or shown["h"] >= 44  # måles nøyaktig under
    assert abs(shown["h"] - 44) < 0.5, shown


@pytest.mark.skipif(not (shutil.which("google-chrome") or shutil.which("chromium")), reason="ingen headless Chrome")
def test_headless_height_44_at_390_and_1280(tmp_path):
    pw = pytest.importorskip("playwright.sync_api")
    html = _page()
    if "<link rel=\"stylesheet\"" in html:
        html = html.replace(
            html[html.find("<link rel=\"stylesheet\""):html.find(">", html.find("<link rel=\"stylesheet\"")) + 1],
            f"<style>{S.CSS}</style>",
            1,
        )
    f = tmp_path / "stale-h.html"
    f.write_text(html)
    start = S.gen_dt(GEN)
    epoch_ms = int((start + timedelta(hours=37)).timestamp() * 1000)
    heights = {}
    with pw.sync_playwright() as p:
        b = p.chromium.launch(channel="chrome" if shutil.which("google-chrome") else None)
        for w in (390, 1280):
            pg = b.new_page(viewport={"width": w, "height": 844 if w == 390 else 800})
            pg.add_init_script(f"Date.now=()=>{epoch_ms};")
            pg.goto(f.as_uri())
            heights[w] = pg.evaluate("""()=>{
              const el=document.getElementById('stale-line');
              const r=el.getBoundingClientRect();
              const cs=getComputedStyle(el);
              return {hidden:el.hidden, h:r.height, w:r.width, fs:cs.fontSize, lh:cs.lineHeight,
                      bg:cs.backgroundColor, color:cs.color, bl:cs.borderLeftWidth};
            }""")
            pg.close()
        b.close()
    for w, g in heights.items():
        assert g["hidden"] is False, (w, g)
        assert abs(g["h"] - 44) < 0.5, (w, g)
        assert g["fs"] == "13px" and g["lh"] == "18px"
        assert g["bl"] == "3px"
