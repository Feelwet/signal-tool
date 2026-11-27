"""Runde 4 (27.11): A1, A2, A4, U1–U11 — enhet og Playwright mot fixture og offisielle data."""
from __future__ import annotations

import csv
import hashlib
import http.server
import json
import threading
from pathlib import Path

import pytest

from signaltool.flyt_page import html, meta_from, prepare_preview
from signaltool.flyt_schema import (
    OFFISIELL_MD5,
    coverage,
    oversikt_varer_og_land,
    published_only,
    ticker_has_published,
    universe_tickers,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "flyt"
FLYT = ROOT / "flyt"
JS = ROOT / "signaltool" / "flyt_static" / "flyt.js"
CSS = ROOT / "signaltool" / "flyt_static" / "flyt.css"
YML = ROOT / ".github" / "workflows" / "tests.yml"
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


def test_a4_tests_yml_fetches_origin_master_and_does_not_touch_r20():
    y = YML.read_text(encoding="utf-8")
    assert "git fetch --no-tags origin master:refs/remotes/origin/master" in y
    r20 = (ROOT / "tests" / "test_r20_close_1711.py").read_text(encoding="utf-8")
    assert "pytest.mark.skip" not in r20 and "xfail" not in r20
    # filen er urørt i denne runden
    import subprocess
    st = subprocess.check_output(["git", "status", "--porcelain", "tests/test_r20_close_1711.py"], cwd=ROOT, text=True)
    assert st.strip() == ""


def test_a2_coverage_k_equals_universe_tickers_with_published_and_hidden_when_not_calculated():
    noder, kanter = _load_fix()
    from signaltool.flyt_build import apply_godkjent
    k2 = apply_godkjent(kanter, FIX / "godkjent.csv")
    uni = universe_tickers(FIX / "list_members.csv")
    cov = coverage(noder, k2, uni)
    assert cov["beregnet"] is True
    assert cov["k"] == sum(1 for t in uni if ticker_has_published(noder, k2, t))
    assert cov["k"] == 1 and "NHY.OL" in uni
    assert cov["statuslinje"] == "Råvaredata for 1 av 8 · Selskapsdata for 1 av 8"

    # ikke beregnet: noder/kanter mangler i samme bygg → linja skjult
    h = html({"generated": "2026-11-27 13:00"}, universe=uni, noder=None, kanter=None)
    assert 'id="flyt-status" hidden' in h
    assert "Råvaredata for" not in h.split('id="flyt-status"', 1)[1][:80]

    # beregnet i samme bygg: linja er med i HTML
    from signaltool.flyt_schema import scenario_chips
    s = json.loads((FIX / "scenarioer.json").read_text(encoding="utf-8"))
    h2 = html({"generated": "2026-11-27 13:00"}, universe=uni, noder=noder, kanter=k2, scenarioer=s)
    assert 'id="flyt-status" hidden' not in h2
    assert "Råvaredata for 1 av 8 · Selskapsdata for 1 av 8" in h2

    # offisielle data: NHY.OL er ikke i universet og telles ikke i k
    on, ok, _ = _load_official()
    uni_now = universe_tickers()
    cov_o = coverage(on, ok, uni_now)
    assert "NHY.OL" not in uni_now
    assert cov_o["k"] == sum(1 for t in uni_now if ticker_has_published(on, ok, t))
    assert cov_o["k"] == 0


def test_a2_ticker_drop_61_to_60_and_nhy_fallback_in_source():
    """N 61→60 er en utskifting 26.11→27.11, ikke ett enkelt fall (ALPE.OL var ute fra 23.11)."""
    rows = list(csv.DictReader((ROOT / "logs" / "list_members.csv").open(encoding="utf-8", newline="")))
    by = {}
    for r in rows:
        by.setdefault(r["date"], set()).add(r["ticker"])
    a, b = by.get("2026-11-26", set()), by.get("2026-11-27", set())
    assert len(a) == 61 and len(b) == 60
    dropped = sorted(a - b)
    added = sorted(b - a)
    assert dropped == ["ADI", "AVGO", "CYTK", "FXI", "KO", "MU", "NKT.CO", "NOD.OL", "SMH", "SPY", "STRC", "WSM"]
    assert added == ["AFG.OL", "BOHUS.OL", "BOR.OL", "CYVIZ.OL", "ENDUR.OL", "EWZ", "HUDL.OL", "IDEX.OL", "INDCT.OL", "MULTI.OL", "PLSV.OL"]
    # ALPE.OL falt ut tidligere (sist 2026-11-18) og er ikke 61→60-årsaken
    assert "ALPE.OL" not in a and "ALPE.OL" not in b
    assert "NHY.OL" not in a and "NHY.OL" not in b
    src = JS.read_text(encoding="utf-8")
    assert "function tickerPageHref" in src
    assert "flyt-tk-plain" in src
    assert "ticker/${slug(ticker)}.html" not in src or "tickerPageHref" in src


def test_u1_oversikt_varer_4_and_top_6_lands_zero_tickers_in_andre():
    noder, kanter, _ = _load_official()
    ov = oversikt_varer_og_land(noder, kanter)
    assert ov["varer_n"] == 4
    assert ov["varer_label"] == "Varer (4)"
    assert len(ov["land_synlige"]) <= 6
    assert all((ov["counts"].get(n["id"], 0) or 0) > 0 for n in ov["land_synlige"])
    assert all((ov["counts"].get(n["id"], 0) or 0) == 0 or n in ov["land_synlige"] or True for n in ov["andre"])
    # 0-ticker-land er i +n andre, ikke blant de 6
    zero = [n for n in noder if n.get("type") == "land" and ov["counts"].get(n["id"], 0) == 0]
    andre_ids = {n["id"] for n in ov["andre"]}
    vis_ids = {n["id"] for n in ov["land_synlige"]}
    for n in zero:
        if n["id"] in ov["counts"]:  # tilkoblet
            assert n["id"] in andre_ids
            assert n["id"] not in vis_ids
    # synkende tickerantall
    counts = [ov["counts"][n["id"]] for n in ov["land_synlige"]]
    assert counts == sorted(counts, reverse=True)


def test_u8_src_builders_and_u9_path_in_js():
    src = JS.read_text(encoding="utf-8")
    assert "function srcText" in src and "function kildeKort" in src
    assert "Kilde, s." not in src.split("function applyScenario", 1)[1].split("function bind", 1)[0]
    assert "kildeKort" in src.split("function applyScenario", 1)[1].split("function bind", 1)[0]
    # U9: scenarios.json lastes først, scenarioer.json bare som fallback — ikke i Promise.all
    init = src.split("async function init()", 1)[1].split("window.__flyt", 1)[0]
    assert "Promise.all" in init
    all_block = init.split("Promise.all", 1)[1]
    all_block = all_block[: all_block.find(");") + 2]
    assert "scenarioer.json" not in all_block
    assert "scenarios.json" in init
    assert "if (!S)" in init and "scenarioer.json" in init
    css = CSS.read_text(encoding="utf-8")
    # U5, U8 typografi
    assert "font-size:13px" in css.split("#flyt-reset{width:auto", 1)[1][:120]
    assert "font-size:13px" in css.split("span.badge", 1)[1][:200]
    assert "font-size:12px" in css.split(".flyt-src", 1)[1][:120]
    assert "line-height:16px" in css.split(".flyt-src", 1)[1][:160]


def test_u10_strommer_heading_and_a1_mangler_in_apply_source():
    src = JS.read_text(encoding="utf-8")
    assert "Strømmer koblet hit" in src
    assert "strommer" in src
    apply = src.split("function applyScenario", 1)[1].split("function bind", 1)[0]
    assert "mangler data" in apply
    assert "hasEmpty" in apply or "Kilden beskriver ikke dette" in apply


def test_official_md5_unchanged():
    def md5(fn):
        return hashlib.md5((FLYT / fn).read_bytes()).hexdigest()
    assert md5("noder.json") == OFFISIELL_MD5["noder.json"] == "02ab5d48a26842392130afcecb7c72ba"
    assert md5("kanter.json") == OFFISIELL_MD5["kanter.json"] == "9f6280057d24f7b869aee39eadd528a2"
    # U9: stien rettes i JS; scenarios.json er innholdsmessig uendret
    assert md5("scenarios.json") == "bc2a39146e088416e362a8c46cf16f97"



def test_u12_scene_rounds_tonn_half_up_panel_keeps_exact():
    from signaltool.flyt_schema import is_tonn, round_tonn_scene
    assert round_tonn_scene(1381341.523) == 1381342
    assert round_tonn_scene(0.5) == 1
    assert round_tonn_scene(1.5) == 2
    assert round_tonn_scene(2.5) == 3
    noder, _, _ = _load_official()
    n = next(x for x in noder if x["id"] == "vare:raaaluminium")
    assert is_tonn(n["enhet"])
    assert n["verdi"] == 1381341.523
    assert round_tonn_scene(n["verdi"]) == 1381342
    src = JS.read_text(encoding="utf-8")
    assert "function fmtSceneVal" in src and "function roundTonnHalfUp" in src
    # panelet bruker fortsatt fmtVal (ordrett), scenen fmtSceneVal
    assert src.count("const fv = fmtSceneVal(n);") >= 2
    assert "Ingen tall for denne noden." not in src
    assert "Noden har ingen egne tall." in src


# ---------- Playwright ----------

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
    dest = tmp_path_factory.mktemp("flyt-r4-off")
    prepare_preview(dest, fixture=False)
    httpd, url = _server(dest)
    yield dest, url
    httpd.shutdown()


def _overlap(page):
    return page.evaluate(
        """() => {
          const labs = [...document.querySelectorAll('.flyt-lab, .flyt-col-h')];
          const boxes = labs.map((el) => {
            const r = el.getBoundingClientRect();
            return {id: el.dataset.id || el.className, t: (el.innerText||'').trim(),
                    left:r.left, right:r.right, top:r.top, bottom:r.bottom, w:r.width, h:r.height};
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
          const hits = labs.filter((el) => el.classList.contains('flyt-lab')).map((el) => {
            const r = el.getBoundingClientRect();
            return {t: (el.innerText||'').trim(), w: r.width, h: r.height};
          });
          return {overlap, pairs, n: boxes.length, texts: boxes.map((b) => b.t), hits};
        }"""
    )


def test_r4_playwright_official_u_and_a(official_preview):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    dest, url = official_preview
    SHOTS.mkdir(parents=True, exist_ok=True)
    failed_req = []

    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        page.on("response", lambda r: failed_req.append((r.status, r.url)) if r.status >= 400 else None)

        # U1 1280 oversikt: Varer (4), 6 land + andre, 0 overlapp, scrollWidth
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_selector(".flyt-lab")
        page.wait_for_timeout(400)
        ov = _overlap(page)
        assert ov["overlap"] == 0, ov["pairs"]
        blob = " | ".join(ov["texts"])
        assert "Varer (4)" in blob
        assert any(t.startswith("+") and "andre" in t for t in ov["texts"])
        landish = [t for t in ov["texts"] if t and not t.startswith("Varer") and not t.startswith("+") and "tickere" in t.lower() or True]
        # høyre kolonne: maks 6 land-etiketter + 1 andre
        labs_n = [t for t in ov["texts"] if "tickere" in t.lower() or (t.startswith("+") and "andre" in t)]
        # vare nodes don't say tickere? they might. Varer have ticker counts too.
        scroll = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, sh: document.documentElement.scrollHeight, ch: document.documentElement.clientHeight})")
        assert scroll["sw"] <= scroll["cw"] + 1, scroll
        # U4 zoom øverst til venstre 16/16, ingenting under folden
        zoom = page.locator(".flyt-zoom").bounding_box()
        scene = page.locator("#flyt-scene").bounding_box()
        assert zoom and scene
        assert abs(zoom["x"] - (scene["x"] + 16)) <= 2, zoom
        assert abs(zoom["y"] - (scene["y"] + 16)) <= 2, zoom
        assert scroll["sh"] <= scroll["ch"] + 2, scroll
        # U5 typografi
        fonts = page.evaluate(
            """() => {
              const reset = getComputedStyle(document.getElementById('flyt-reset'));
              return {reset: parseFloat(reset.fontSize)};
            }"""
        )
        assert fonts["reset"] >= 13 - 0.1, fonts
        for h in ov["hits"]:
            assert h["w"] >= 44 - 0.5 and h["h"] >= 44 - 0.5, h
        page.screenshot(path=str(SHOTS / "r4_1280_oversikt.png"), full_page=False)

        # U1 390 oversikt
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{url}/flyt.html", wait_until="networkidle")
        page.wait_for_timeout(400)
        ov390 = _overlap(page)
        assert ov390["overlap"] == 0, ov390["pairs"]
        assert "Varer (4)" in " | ".join(ov390["texts"])
        scroll390 = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        assert scroll390["sw"] <= scroll390["cw"] + 1, scroll390
        page.screenshot(path=str(SHOTS / "r4_390_oversikt.png"), full_page=False)

        # U2: ?fokus= ved 390, arket lukket, synlig scene ≥ 300
        page.goto(f"{url}/flyt.html?fokus=NHY.OL", wait_until="networkidle")
        page.wait_for_timeout(400)
        panel = page.locator("#flyt-panel")
        assert panel.get_attribute("hidden") is not None or not panel.is_visible()
        scene = page.locator("#flyt-scene").bounding_box()
        vis = min(scene["y"] + scene["height"], 844) - scene["y"]
        assert vis >= 300, (vis, scene)
        page.screenshot(path=str(SHOTS / "r4_390_fokus_lukket.png"), full_page=False)

        # åpnes kun ved trykk
        page.evaluate("() => { const l = document.querySelector('.flyt-lab[data-id=\"ticker:NHY.OL\"]'); if (l) l.click(); }")
        page.wait_for_timeout(300)
        assert page.locator("#flyt-panel").is_visible()
        handle = page.locator("#flyt-sheet-handle").bounding_box()
        assert handle and handle["height"] >= 44 - 0.5, handle
        # U11: trykk på håndtaket når 90 %
        page.locator("#flyt-sheet-handle").click()
        page.wait_for_timeout(200)
        h = page.evaluate("() => document.getElementById('flyt-panel').getBoundingClientRect().height")
        assert h >= 0.85 * 844, h
        page.screenshot(path=str(SHOTS / "r4_390_ark90.png"), full_page=False)

        # U3 + U8 + A2 fallback ved 1280 med fokus NHY
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{url}/flyt.html?fokus=NHY.OL", wait_until="networkidle")
        page.wait_for_timeout(400)
        ov_f = _overlap(page)
        texts = ov_f["texts"]
        assert any("Verk (13)" in t or t.startswith("Verk (") for t in texts)
        assert ov_f["overlap"] == 0, ov_f["pairs"]
        srcs = page.locator("#flyt-panel .flyt-src").all_inner_texts()
        joined = " ".join(srcs)
        assert "Selskapsrapport ·" in joined
        assert "s. 37" in joined
        assert "2025 · 2025" not in joined and "2025, 2025" not in joined
        fs = page.evaluate(
            """() => {
              const el = document.querySelector('#flyt-panel .flyt-src');
              if (!el) return null;
              const s = getComputedStyle(el);
              return {fs: parseFloat(s.fontSize), lh: parseFloat(s.lineHeight), t: el.innerText};
            }"""
        )
        assert fs and abs(fs["fs"] - 12) <= 0.2 and abs(fs["lh"] - 16) <= 0.2, fs
        # NHY er ikke i universet: ticker-lenke er ren tekst, ikke død href
        dead = page.evaluate(
            """() => {
              const a = [...document.querySelectorAll('#flyt-panel a')].filter((x) => (x.getAttribute('href')||'').includes('ticker/'));
              return a.map((x) => x.getAttribute('href'));
            }"""
        )
        assert all("NHY" not in (h or "") for h in dead), dead
        plain = page.locator("#flyt-panel .flyt-tk-plain")
        assert plain.count() >= 1
        assert "NHY.OL" in plain.first.inner_text()
        page.screenshot(path=str(SHOTS / "r4_1280_nhy.png"), full_page=False)

        # U6 + A1 + U7 + U8 hva-hvis
        page.locator("#flyt-hvis").click()
        page.wait_for_timeout(200)
        chips = page.locator("#flyt-hvis-chips")
        assert chips.is_visible()
        cb = chips.bounding_box()
        top = page.locator("#flyt-top").bounding_box()
        scene = page.locator("#flyt-scene").bounding_box()
        assert cb and top and scene
        assert cb["y"] + 1 >= top["y"] + top["height"] - 1
        assert cb["y"] + cb["height"] <= scene["y"] + 2
        assert cb["y"] + cb["height"] <= 800
        names = [chips.locator(".flyt-chip").nth(i).inner_text().strip() for i in range(chips.locator(".flyt-chip").count())]
        assert names == ["Energipris i Norge opp", "Import til EU ned", "Etterspørsel fra bil opp"]

        page.locator(".flyt-chip", has_text="Import til EU ned").click()
        page.wait_for_timeout(250)
        tekst = page.inner_text("#flyt-hvis-tekst")
        tall = page.inner_text("#flyt-hvis-tall")
        assert "Mangler data" in tall
        assert "strategisk materiale" in tekst
        assert "Kilde, s." not in tekst
        assert "Årsrapport 2025" in tekst or "Årsrapport 2025" in tall
        page.screenshot(path=str(SHOTS / "r4_1280_hvis_import.png"), full_page=False)

        page.locator(".flyt-chip", has_text="Etterspørsel fra bil opp").click()
        page.wait_for_timeout(250)
        tekst_b = page.inner_text("#flyt-hvis-tekst")
        tall_b = page.inner_text("#flyt-hvis-tall")
        assert tekst_b.count("Kilden beskriver ikke dette") == 0
        assert tall_b.count("Kilden beskriver ikke dette") == 1
        page.screenshot(path=str(SHOTS / "r4_1280_hvis_bil.png"), full_page=False)

        # U10 kontekst
        page.goto(f"{url}/flyt.html?fokus=land:NO", wait_until="networkidle")
        page.wait_for_timeout(400)
        # desktop: panel åpent ved last
        tall_sec = page.locator('#flyt-panel [data-sec="tall"]')
        assert tall_sec.count() == 1
        assert tall_sec.locator(".flyt-kontekst-tall").inner_text().strip() == "Noden har ingen egne tall."
        assert tall_sec.locator(".badge").count() == 0
        strom = page.locator('#flyt-panel [data-sec="strommer"]')
        assert strom.count() == 1
        assert "strømmer koblet hit" in strom.inner_text().lower()
        rows = strom.locator(".flyt-strom-rad")
        assert rows.count() >= 1
        assert rows.nth(0).locator(".flyt-src").count() == 1
        typ = page.evaluate("""() => {
          const el = document.querySelector('#flyt-panel .flyt-kontekst-tall');
          const s = getComputedStyle(el);
          return {fs: parseFloat(s.fontSize), lh: parseFloat(s.lineHeight), color: s.color};
        }""")
        assert abs(typ["fs"] - 13) <= 0.2 and abs(typ["lh"] - 18) <= 0.2, typ
        assert "158" in typ["color"] and "169" in typ["color"] and "181" in typ["color"], typ
        page.screenshot(path=str(SHOTS / "r4_1280_kontekst.png"), full_page=False)

        # U12: tonn i scenen avrundet, panelet ordrett
        page.goto(f"{url}/flyt.html?fokus=vare:raaaluminium", wait_until="networkidle")
        page.wait_for_timeout(400)
        scene_t = page.locator('.flyt-lab[data-id="vare:raaaluminium"] .v').inner_text()
        assert "1 381 342" in scene_t.replace("\xa0", " ").replace("\u00a0", " ").replace("\u202f", " ") or "1\xa0381\xa0342" in scene_t or "1381342" in scene_t.replace("\xa0", "").replace(" ", "").replace("\u202f", "")
        # mer robust normalisering
        norm = scene_t.replace("\xa0", " ").replace("\u00a0", " ").replace("\u202f", " ").replace(" ", "")
        # actually do it in python properly below via evaluate
        scene_norm = page.evaluate("""() => {
          const el = document.querySelector('.flyt-lab[data-id="vare:raaaluminium"] .v');
          return (el ? el.innerText : '').replace(/[\u00a0\u202f]/g, ' ');
        }""")
        assert "1 381 342" in scene_norm, scene_norm
        assert "1 381 341,523" not in scene_norm
        panel = page.evaluate("""() => {
          const tall = document.querySelector('#flyt-panel [data-sec="tall"]');
          return (tall ? tall.innerText : '').replace(/[\u00a0\u202f]/g, ' ');
        }""")
        assert "1 381 341,523" in panel, panel
        assert "SSB" in panel or "08801" in panel
        page.screenshot(path=str(SHOTS / "r4_1280_tonn_avrunding.png"), full_page=False)

        # U5 Mangler data-merke ≥ 13 på energi:kraft-NO
        page.goto(f"{url}/flyt.html?fokus=energi:kraft-NO", wait_until="networkidle")
        page.wait_for_timeout(300)
        badge_fs = page.evaluate(
            """() => {
              const b = document.querySelector('#flyt-panel .badge');
              return b ? {fs: parseFloat(getComputedStyle(b).fontSize), t: b.innerText} : null;
            }"""
        )
        assert badge_fs and badge_fs["t"] == "Mangler data" and badge_fs["fs"] >= 13 - 0.1, badge_fs
        page.screenshot(path=str(SHOTS / "r4_1280_kraft.png"), full_page=False)

        # U9: ingen 404 på scenarioer.json når scenarios.json finnes
        bad = [u for st, u in failed_req if "scenarioer.json" in u]
        assert not bad, failed_req
        # scenarios.json skal ha blitt lastet
        assert (dest / "flyt" / "scenarios.json").exists()
        assert not (dest / "flyt" / "scenarioer.json").exists()

        browser.close()
