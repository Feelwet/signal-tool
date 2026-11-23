"""UxBot 17.11: filtre (risiko, sektor, børs) og kontrast på Tickere."""
from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

import pytest

from signaltool import site as S
from signaltool import site_risk as RK
from signaltool import tickerlist as TL


def _rel_lum(hx: str) -> float:
    h = hx.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def f(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a: str, b: str) -> float:
    l1, l2 = _rel_lum(a), _rel_lum(b)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def test_gics_translation_and_unknown_sector():
    assert TL.sektor_label("") == "Ukjent sektor"
    assert TL.sektor_label(None) == "Ukjent sektor"
    assert TL.sektor_label("  ") == "Ukjent sektor"
    assert TL.sektor_label("Widgets") == "Ukjent sektor"
    assert TL.sektor_label("Energy") == "Energi"
    assert TL.sektor_label("Information Technology") == "Teknologi"
    assert TL.sektor_label("Technology") == "Teknologi"
    assert TL.sektor_label("Financials") == "Finans"
    assert TL.sektor_label("Financial Services") == "Finans"
    assert TL.sektor_label("Health Care") == "Helse"
    assert TL.sektor_label("Healthcare") == "Helse"
    assert TL.sektor_label("Consumer Discretionary") == "Syklisk forbruk"
    assert TL.sektor_label("Consumer Staples") == "Defensivt forbruk"
    assert TL.sektor_label("Materials") == "Råvarer"
    assert TL.sektor_label("Basic Materials") == "Råvarer"
    assert TL.sektor_of({"decision": {}}) == "Ukjent sektor"
    assert TL.sektor_of({"decision": {"sector": ""}}) == "Ukjent sektor"
    assert TL.sektor_slug({"decision": {"sector": "Energy"}}) == "energi"
    assert TL.sektor_slug({"decision": {}}) == "ukjent-sektor"
    assert set(TL.SEKTOR_NAV[:-1]) == {
        "Energi", "Råvarer", "Industri", "Syklisk forbruk", "Defensivt forbruk",
        "Helse", "Finans", "Teknologi", "Kommunikasjon", "Forsyning", "Eiendom",
    }


def test_bors_from_suffix_only_never_csv():
    assert TL.bors_of("EQNR.OL") == "Oslo"
    assert TL.bors_of("AAPL") == "USA"
    assert TL.bors_of("BRK.B") == "USA"
    assert TL.bors_of("MOG.A") == "USA"
    assert TL.bors_of("RHM.DE") == "Tyskland"
    assert TL.bors_of("RHM.DE", "US") == "Tyskland"  # market-argument ignoreres
    assert TL.bors_of("NKT.CO") == "Danmark"
    assert TL.bors_of("MAERSK-B.CO") == "Danmark"
    assert TL.bors_of("BA.L") == "Storbritannia"
    assert TL.bors_of("SAAB-B.ST") == "Sverige"
    assert TL.bors_of("7203.T") == "Japan"
    assert TL.bors_of("2330.TWO") == "Taiwan"
    assert TL.bors_of("2330.TW") == "Taiwan"
    assert TL.bors_of("FOO.XX") == "Ukjent børs"
    assert TL.bors_of("AAA.ST", "Oslo") == "Sverige"  # aldri CSV/market som overstyrer suffiks


def _row(**kw):
    base = dict(ticker="X", name="X Inc", risiko="hoy", sektor="energi", bors="oslo", flag=False, ny=False, mine=False)
    base.update(kw)
    return base


def test_filter_or_in_group_and_across_groups():
    rows = [
        _row(ticker="A", risiko="hoy", sektor="energi", bors="oslo"),
        _row(ticker="B", risiko="hoy", sektor="teknologi", bors="usa"),
        _row(ticker="C", risiko="lav", sektor="energi", bors="oslo"),
        _row(ticker="D", risiko="middels", sektor="energi", bors="usa", flag=True),
        _row(ticker="E", risiko="hoy", sektor="ukjent-sektor", bors="oslo", mine=True, ny=True),
    ]
    # ELLER i risiko
    got = [r["ticker"] for r in rows if TL.matches(r, {"risiko": ["hoy", "middels"], "sektor": [], "bors": [], "annet": [], "q": ""})]
    assert got == ["A", "B", "D", "E"]
    # OG på tvers: hoy + energi + oslo
    got = [r["ticker"] for r in rows if TL.matches(r, {"risiko": ["hoy"], "sektor": ["energi"], "bors": ["oslo"], "annet": [], "q": ""})]
    assert got == ["A"]
    # sektor=energi & bors=oslo
    got = [r["ticker"] for r in rows if TL.matches(r, {"risiko": [], "sektor": ["energi"], "bors": ["oslo"], "annet": [], "q": ""})]
    assert got == ["A", "C"]
    # søk kombineres med alt
    got = [r["ticker"] for r in rows if TL.matches(r, {"risiko": ["hoy"], "sektor": [], "bors": [], "annet": [], "q": "a"})]
    assert got == ["A"]
    # mine / flagg / ny
    assert [r["ticker"] for r in rows if TL.matches(r, {"risiko": [], "sektor": [], "bors": [], "annet": ["mine"], "q": ""})] == ["E"]
    assert [r["ticker"] for r in rows if TL.matches(r, {"risiko": [], "sektor": [], "bors": [], "annet": ["flagg"], "q": ""})] == ["D"]
    empty = {"risiko": [], "sektor": [], "bors": [], "annet": [], "q": ""}
    assert TL.facet_count(rows, empty, "risiko", "hoy") == 3
    assert TL.facet_count(rows, {"risiko": [], "sektor": ["energi"], "bors": ["oslo"], "annet": [], "q": ""}, "risiko", "hoy") == 1
    assert TL.facet_count(rows, empty, "sektor", "ukjent-sektor") == 1


def test_ticker_row_has_data_sektor_bors_and_unknown():
    e = {
        "ticker": "EQNR.OL", "name": "Equinor", "points": {}, "score": 1.0,
        "stats": {"close": 10, "ret_5d": 0.01, "ret_20d": 0.02},
        "decision": {"sector": "Energy"},
        "_risk": {"level": "Høy", "market": "Oslo", "in_universe": 1},
        "_flag": {"ticker": "EQNR.OL", "flags": {"weak_px": "x"}},
        "_ret": {"new": False},
    }
    h = S.ticker_row(e)
    assert 'data-sektor="energi"' in h and 'data-bors="oslo"' in h
    assert 'data-flag="1"' in h and 'data-ny="0"' in h and 'data-risk="1"' in h
    assert 'data-cat="Høy"' in h
    e2 = {**e, "ticker": "ZZZ", "decision": {}, "_risk": {"level": "Lav", "in_universe": 1}, "_flag": None, "_ret": {"new": True}}
    h2 = S.ticker_row(e2)
    assert 'data-sektor="ukjent-sektor"' in h2
    assert 'data-bors="usa"' in h2
    assert 'data-flag="0"' in h2 and 'data-ny="1"' in h2 and 'data-risk="1"' in h2
    e3 = {**e, "ticker": "RHM.DE", "decision": {"sector": "Industrials"}, "_risk": {"level": "Høy", "market": "US", "in_universe": 0}}
    h3 = S.ticker_row(e3)
    assert 'data-bors="tyskland"' in h3
    assert 'data-sektor="industri"' in h3
    assert 'data-cat=""' in h3 and 'data-risk="0"' in h3
    assert "Ingen risikonivå" in h3


def test_css_contrast_tokens():
    assert "--bg:#0b0f14" in S.CSS and "--line:#3a4350" in S.CSS
    assert "--card:#161b22" in S.CSS and "--mut:#9ea9b5" in S.CSS and "--ink:#e6edf3" in S.CSS
    assert "tr:hover td,tr:focus-within td{background:#1f2733}" in S.CSS
    assert "tr:focus-visible{outline:2px solid var(--acc);outline-offset:-2px}" in S.CSS
    assert "#tf-table th{background:#1f2733;color:#c9d1d9}" in TL.CSS
    assert "border:1px solid #6b7787" in TL.CSS
    assert "background:rgba(108,182,255,.18)" in TL.CSS
    assert "content:\"✓ \"" in TL.CSS or "content:\"✓ \";" in TL.CSS
    assert ".tf-opt.is-on .tf-opt-lab::before" not in TL.CSS
    assert ".tf-mine[aria-pressed=true]::before{content:\"✓ \";}" in TL.CSS
    assert ".tf-slukk{flex:none;width:44px;height:44px" in TL.CSS
    assert ".tf-apply{height:48px;min-height:48px" in TL.CSS
    assert ".tf-empty{" in TL.CSS and "min-height:48px" in TL.CSS
    assert ".tf-empty-reset,.tf-sheet-reset" in TL.CSS and "min-height:44px" in TL.CSS[TL.CSS.find(".tf-empty-reset"):TL.CSS.find(".tf-empty-reset")+400]
    assert contrast("#e6edf3", "#161b22") >= 7
    assert contrast("#9ea9b5", "#161b22") >= 4.5
    assert contrast("#6b7787", "#161b22") >= 3
    assert contrast("#6cb6ff", "#161b22") >= 3
    assert contrast("#c9d1d9", "#1f2733") >= 4.5


def test_risk_badge_neutral_no_color_variant():
    assert "rk-farger" not in RK.CSS
    assert "var(--up)" not in RK.CSS and "var(--down)" not in RK.CSS and "var(--warn)" not in RK.CSS
    html = S.page("Tickere", "<p>x</p>", 0, {"generated": "2026-11-17 12:00"})
    assert "rk-farger" not in html
    assert re.search(r"\.rk-lav,\.rk-middels,\.rk-hoy,\.rk-na\{[^}]*color:var\(--ink", RK.CSS)
    assert "trygg" not in RK.CSS.lower() and "sikker" not in RK.CSS.lower()
    assert "trygg" not in RK.chip({"level": "Lav"}).lower()
    assert "sikker" not in RK.chip({"level": "Lav"}).lower()


def test_filter_row_url_localstorage_and_sheet():
    h = TL.filter_row({"tickers": [
        {"ticker": "EQNR.OL", "decision": {"sector": "Energy"}, "_risk": {"level": "Høy", "market": "Oslo", "in_universe": 1}, "_ret": {"new": True}},
        {"ticker": "AAPL", "decision": {}, "_risk": {"level": "Lav", "market": "US", "in_universe": 1}},
    ], "date": "2026-11-17"})
    assert 'id="tf-fbtn"' in h and "Filter (0)" in h
    assert 'id="tf-sheet"' in h and 'id="tf-slukk"' in h and 'aria-label="Lukk"' in h
    assert "Vis 2 tickere" in h and "Nullstill" in h
    assert 'data-g="risiko"' in h and 'data-g="sektor"' in h and 'data-g="bors"' in h and 'data-g="annet"' in h
    assert "Energi (1)" in h and "Ukjent sektor (1)" in h
    assert "Høy (1)" in h and "Lav (1)" in h
    assert "Ingen risikonivå" not in h and "Middels (" not in h
    assert "Oslo (1)" in h and "USA (1)" in h
    assert "Danmark" not in h and "Sverige" not in h and "Storbritannia" not in h
    assert "Japan" not in h and "Taiwan" not in h and "Ukjent børs" not in h and "Tyskland" not in h
    assert "Råvarer" not in h
    assert 'data-total="2"' in h
    assert "signaltool.tickere-filter" in h
    assert "searchParams" in TL.JS and "'risiko'" in TL.JS and "join(',')" in TL.JS
    assert "localStorage" in TL.JS and "Escape" in TL.JS
    assert "Viser 2 av 2" in h
    assert 'id="tf-mine"' in h and "Annet ▾" in h


def test_filter_js_not_duplicated_in_row():
    # JS ligger i TL.JS og settes inn én gang av site.build (etter fold_tables).
    assert "function setSheet" not in TL.filter_row({"tickers": []})
    assert "function setSheet" in TL.JS
    src = open(__import__("signaltool.site", fromlist=["x"]).__file__).read()
    assert src.count("+ TL.JS") == 1


def _fixture(tmp_path: Path) -> Path:
    rows = [
        ("AAPL", "Apple", "hoy", "teknologi", "usa", "0", "0", "Høy"),
        ("MSFT", "Microsoft", "hoy", "teknologi", "usa", "0", "0", "Høy"),
        ("EQNR.OL", "Equinor", "hoy", "energi", "oslo", "1", "0", "Høy"),
        ("VAR.OL", "Vår Energi", "middels", "energi", "oslo", "0", "0", "Middels"),
        ("DNB.OL", "DNB Bank", "lav", "finans", "oslo", "0", "1", "Lav"),
        ("JPM", "JPMorgan", "middels", "finans", "usa", "0", "0", "Middels"),
        ("RHM.DE", "Rheinmetall", "", "industri", "tyskland", "0", "0", ""),
        ("ZZZ", "Ukjent AS", "lav", "ukjent-sektor", "usa", "0", "0", "Lav"),
        ("TSM", "TSMC", "", "teknologi", "usa", "0", "0", ""),
        ("YETI", "YETI", "", "syklisk-forbruk", "usa", "0", "0", ""),
    ]
    tr = "".join(
        f'<tr class="rowlink" data-t="{t}" data-cat="{cat}" data-sektor="{sec}" data-bors="{bors}" data-flag="{flag}" data-ny="{ny}" data-risk="{"1" if cat else "0"}">'
        f'<td><span class="nm">{name}</span></td></tr>'
        for t, name, risk, sec, bors, flag, ny, cat in rows
    )
    body = TL.filter_row({"tickers": [
        {"ticker": t, "name": n, "decision": {"sector": {
            "teknologi": "Technology", "energi": "Energy", "finans": "Financial Services",
            "industri": "Industrials", "ukjent-sektor": "", "syklisk-forbruk": "Consumer Discretionary",
        }[sec]}, "_risk": {"level": cat, "market": {"usa": "US", "oslo": "Oslo", "tyskland": "US"}[bors],
                            "in_universe": 0 if bors == "tyskland" or t in ("TSM", "YETI") else 1},
         "_flag": {"x": 1} if flag == "1" else None, "_ret": {"new": ny == "1"}}
        for t, n, risk, sec, bors, flag, ny, cat in rows
    ], "date": "2026-11-17", "_risk_asof": __import__("datetime").date(2026, 11, 13),
       "_risk_today": __import__("datetime").date(2026, 11, 17)})
    html = (
        "<!doctype html><html lang='no'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<style>:root{--bg:#0b0f14;--card:#161b22;--ink:#e6edf3;--mut:#9ea9b5;--acc:#6cb6ff;--line:#3a4350}"
        "body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 sans-serif}"
        + TL.CSS +
        "</style></head><body class='pg-tickere'>"
        + body +
        f"<div id='tf-table'><div class='card'><table>{tr}</table></div></div>"
        + TL.empties() + TL.JS +
        "</body></html>"
    )
    f = tmp_path / "tickere-filter.html"
    f.write_text(html)
    return f


@pytest.mark.skipif(not (shutil.which("google-chrome") or shutil.which("chromium")), reason="ingen headless Chrome")
def test_headless_filter_logic_sizes_and_counts(tmp_path):
    pw = pytest.importorskip("playwright.sync_api")
    f = _fixture(tmp_path)
    with pw.sync_playwright() as p:
        b = p.chromium.launch(channel="chrome" if shutil.which("google-chrome") else None)
        # 390: knappe- og lukkmål, ingen hscroll, filterkombinasjoner
        pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto(f.as_uri())
        m390 = pg.evaluate("""()=>{
          const q=document.getElementById('tf-q'), btn=document.getElementById('tf-fbtn');
          const qb=q.getBoundingClientRect(), bb=btn.getBoundingClientRect();
          const de=document.documentElement;
          return {qh:qb.height, qw:qb.width, bh:bb.height, bw:bb.width,
                  sw:de.scrollWidth, cw:de.clientWidth, topH:document.querySelector('.tf-top').getBoundingClientRect().height};
        }""")
        assert m390["qh"] == 44 and m390["bh"] == 44 and m390["bw"] >= 44, m390
        assert m390["topH"] == 44, m390
        assert m390["sw"] <= m390["cw"] + 1, m390

        pg.click("#tf-fbtn")
        sheet = pg.evaluate("""()=>{
          const s=document.getElementById('tf-sheet'), x=document.getElementById('tf-slukk'), a=document.getElementById('tf-apply');
          const sb=s.getBoundingClientRect(), xb=x.getBoundingClientRect(), ab=a.getBoundingClientRect();
          const opt=[...s.querySelectorAll('.tf-opt')][0].getBoundingClientRect();
          return {open:!s.hidden, xw:xb.width, xh:xb.height, ah:ab.height, oh:opt.height, lab:x.getAttribute('aria-label')};
        }""")
        assert sheet["open"] and sheet["xw"] == 44 and sheet["xh"] == 44 and sheet["ah"] == 48 and sheet["oh"] == 44
        assert sheet["lab"] == "Lukk"
        pg.keyboard.press("Escape")
        assert pg.evaluate("()=>document.getElementById('tf-sheet').hidden")
        assert pg.evaluate("()=>document.activeElement && document.activeElement.id==='tf-fbtn'")

        def visible():
            return pg.evaluate("()=>[...document.querySelectorAll('#tf-table tr.rowlink')].filter(r=>!r.hidden).map(r=>r.dataset.t)")

        # risiko=hoy
        pg.click("#tf-fbtn")
        pg.locator('.tf-sheet .tf-opt[data-g="risiko"][data-k="hoy"] input').click()
        pg.click("#tf-apply")
        v = visible()
        assert set(v) == {"AAPL", "MSFT", "EQNR.OL"}, v
        assert "risiko=hoy" in pg.evaluate("()=>location.search")
        count = pg.evaluate("()=>document.getElementById('tf-count').textContent")
        assert "Viser 3 av 10" in count
        assert "3 uten risikonivå utelatt" in count
        assert "Risiko per 13.11" in count
        assert pg.evaluate("()=>!document.getElementById('tf-risk-note').hidden")
        assert "Risikonivå er rangert innen hver børs." in pg.evaluate("()=>document.getElementById('tf-risk-note').textContent")

        # nullstill, så sektor=energi & bors=oslo
        pg.click("#tf-fbtn")
        pg.click("#tf-sheet-reset")
        pg.click("#tf-fbtn")
        pg.locator('.tf-sheet .tf-opt[data-g="sektor"][data-k="energi"] input').click()
        pg.locator('.tf-sheet .tf-opt[data-g="bors"][data-k="oslo"] input').click()
        n_btn = pg.locator("#tf-apply").inner_text()
        pg.click("#tf-apply")
        v = visible()
        assert set(v) == {"EQNR.OL", "VAR.OL"}, v
        assert "Vis 2 tickere" in n_btn
        search = pg.evaluate("()=>location.search")
        assert "sektor=energi" in search and "bors=oslo" in search

        # risiko=hoy,middels & bors=usa
        pg.click("#tf-fbtn")
        pg.click("#tf-sheet-reset")
        pg.click("#tf-fbtn")
        pg.locator('.tf-sheet .tf-opt[data-g="risiko"][data-k="hoy"] input').click()
        pg.locator('.tf-sheet .tf-opt[data-g="risiko"][data-k="middels"] input').click()
        pg.locator('.tf-sheet .tf-opt[data-g="bors"][data-k="usa"] input').click()
        pg.click("#tf-apply")
        v = visible()
        assert set(v) == {"AAPL", "MSFT", "JPM"}, v

        # risiko=hoy & børs=oslo: ingen forbehold (børs avgrenset til én)
        pg.click("#tf-fbtn")
        pg.click("#tf-sheet-reset")
        pg.click("#tf-fbtn")
        pg.locator('.tf-sheet .tf-opt[data-g="risiko"][data-k="hoy"] input').click()
        pg.locator('.tf-sheet .tf-opt[data-g="bors"][data-k="oslo"] input').click()
        pg.click("#tf-apply")
        v = visible()
        assert set(v) == {"EQNR.OL"}, v
        assert pg.evaluate("()=>document.getElementById('tf-risk-note').hidden")
        count = pg.evaluate("()=>document.getElementById('tf-count').textContent")
        assert "uten risikonivå utelatt" not in count
        assert "Risiko per 13.11" in count

        pg.close()

        # 1280: søk 280, nedtrekk 44, ingen hscroll
        pg = b.new_page(viewport={"width": 1280, "height": 800})
        pg.goto(f.as_uri())
        m1280 = pg.evaluate("""()=>{
          const q=document.getElementById('tf-q'), dd=[...document.querySelectorAll('.tf-dd-btn')];
          const qb=q.getBoundingClientRect();
          const de=document.documentElement;
          return {qw:qb.width, qh:qb.height, ddh:dd.map(b=>b.getBoundingClientRect().height),
                  ddw:dd.map(b=>b.getBoundingClientRect().width),
                  sw:de.scrollWidth, cw:de.clientWidth,
                  fbtn:getComputedStyle(document.getElementById('tf-fbtn')).display,
                  mine:getComputedStyle(document.getElementById('tf-mine')).display};
        }""")
        assert m1280["qw"] == 280 and m1280["qh"] == 44, m1280
        assert m1280["ddh"] and all(h == 44 for h in m1280["ddh"]), m1280
        assert m1280["sw"] <= m1280["cw"] + 1, m1280
        assert m1280["fbtn"] == "none" and m1280["mine"] != "none"
        pg.locator('.tf-dd[data-g="risiko"] .tf-dd-btn').click()
        list_m = pg.evaluate("""()=>{
          const l=document.querySelector('.tf-dd[data-g="risiko"] .tf-dd-list');
          const r=l.getBoundingClientRect();
          const o=l.querySelector('.tf-opt').getBoundingClientRect();
          return {h:r.height, w:r.width, oh:o.height, hidden:l.hidden};
        }""")
        assert list_m["h"] <= 320 and list_m["w"] <= 320 and list_m["oh"] == 44 and not list_m["hidden"]
        pg.close()
        b.close()


def test_risk_filter_hidden_when_older_than_8_days():
    from datetime import date
    snap_old = {"tickers": [
        {"ticker": "EQNR.OL", "decision": {"sector": "Energy"},
         "_risk": {"level": "Høy", "market": "Oslo", "in_universe": 1}},
    ], "date": "2026-11-17", "_risk_asof": date(2026, 11, 1), "_risk_today": date(2026, 11, 17)}
    h = TL.filter_row(snap_old)
    assert 'data-risk-open="0"' in h
    assert "Risiko per 01.11" in h
    assert 'data-g="risiko"' in h  # i DOM, skjult med CSS/JS
    snap_ok = {**snap_old, "_risk_asof": date(2026, 11, 13)}
    h2 = TL.filter_row(snap_ok)
    assert 'data-risk-open="1"' in h2
    assert "Risiko per 13.11" in h2
    assert TL.risk_filter_open(date(2026, 11, 9), date(2026, 11, 17)) is True
    assert TL.risk_filter_open(date(2026, 11, 8), date(2026, 11, 17)) is False  # 9 dager


def test_shown_level_in_universe_and_market_matches_suffix():
    from signaltool.bors import bors_of
    from signaltool import risk
    cases = [
        ("EQNR.OL", {"level": "Høy", "market": "Oslo", "in_universe": 1}, "Høy", "Oslo"),
        ("AAPL", {"level": "Lav", "market": "US", "in_universe": 1}, "Lav", "USA"),
        ("BRK.B", {"level": "Lav", "market": "US", "in_universe": 1}, "Lav", "USA"),
        ("TSM", {"level": "Middels", "market": "US", "in_universe": 0}, None, "USA"),
        ("YETI", {"level": "Høy", "market": "US", "in_universe": 0}, None, "USA"),
        ("RHM.DE", {"level": "Høy", "market": "US", "in_universe": 0}, None, "Tyskland"),
        ("RHM.DE", {"level": "Høy", "market": "US", "in_universe": 1}, None, "Tyskland"),
        ("NKT.CO", {"level": "Høy", "market": "US", "in_universe": 0}, None, "Danmark"),
        ("BA.L", {"level": "Lav", "market": "US", "in_universe": 0}, None, "Storbritannia"),
        ("ZZZ", None, None, "USA"),
        ("FOO.XX", {"level": "Høy", "market": "US", "in_universe": 1}, None, "Ukjent børs"),
    ]
    for tkr, rec, exp, bors in cases:
        assert bors_of(tkr) == bors, tkr
        assert RK.shown_level(rec, tkr) == exp, tkr
        e = {
            "ticker": tkr, "name": tkr, "points": {}, "score": 1.0,
            "stats": {"close": 10, "ret_5d": 0.01, "ret_20d": 0.02},
            "decision": {}, "_risk": rec, "_ret": {"new": False},
        }
        h = S.ticker_row(e)
        assert f'data-bors="{TL._slug(bors)}"' in h, (tkr, h)
        if exp:
            assert f'data-cat="{exp}"' in h and 'data-risk="1"' in h
            assert f">{exp}</span>" in h
            mk = rec["market"]
            assert (mk == "Oslo" and bors == "Oslo") or (mk == "US" and bors == "USA")
            assert risk.market(tkr) in ("US", "Oslo")
        else:
            assert 'data-risk="0"' in h and 'data-cat=""' in h
            assert "Ingen risikonivå" in h


def test_page_levels_from_csv_have_in_universe_and_matching_market():
    """Hver ticker som får nivå på siden har in_universe=1, og market samsvarer med suffiks-børsen."""
    from signaltool.bors import bors_of
    from signaltool.risk import read_log
    rows = read_log()   # erstattet=1 filtrert bort
    if not rows:
        return
    last = {}
    for r in rows:
        tkr = (r.get("ticker") or "").strip()
        if tkr and (tkr not in last or r["date"] >= last[tkr]["date"]):
            last[tkr] = r
    shown = 0
    for tkr, r in last.items():
        rec = {
            "level": r.get("level"),
            "market": r.get("market"),
            "in_universe": int(r.get("in_universe") or 0),
            "date": r.get("date"),
        }
        lv = RK.shown_level(rec, tkr)
        e = {
            "ticker": tkr, "name": tkr, "points": {}, "score": 1.0,
            "stats": {"close": 10, "ret_5d": 0.0, "ret_20d": 0.0},
            "decision": {}, "_risk": rec,
        }
        h = S.ticker_row(e)
        if lv:
            shown += 1
            assert rec["in_universe"] == 1, tkr
            b = bors_of(tkr)
            mk = rec["market"]
            assert (mk == "Oslo" and b == "Oslo") or (mk == "US" and b == "USA"), (tkr, mk, b)
            assert f'data-cat="{lv}"' in h and 'data-risk="1"' in h
        else:
            assert 'data-risk="0"' in h and "Ingen risikonivå" in h
    assert shown > 0


def test_risk_market_never_us_for_foreign_suffix():
    from signaltool import risk
    assert risk.market("AAPL") == "US"
    assert risk.market("BRK.B") == "US"
    assert risk.market("MOG.A") == "US"
    assert risk.market("EQNR.OL") == "Oslo"
    assert risk.market("RHM.DE") == "Tyskland"
    assert risk.market("HLAG.DE") == "Tyskland"
    assert risk.market("NKT.CO") == "Danmark"
    assert risk.market("MAERSK-B.CO") == "Danmark"
    assert risk.market("BA.L") == "Storbritannia"
    assert risk.market("SAAB-B.ST") == "Sverige"
    assert risk.market("7203.T") == "Japan"
    assert risk.market("2330.TWO") == "Taiwan"
    assert risk.market("FOO.XX") == "Ukjent børs"
    assert risk.market("RHM.DE") != "US"
    assert risk.market("NKT.CO") != "US"


@pytest.mark.skipif(not (shutil.which("google-chrome") or shutil.which("chromium")), reason="ingen headless Chrome")
def test_sheet_stays_open_after_one_click(tmp_path):
    """JS lastes én gang; ett klikk åpner arket og det blir stående åpent (regresjon a4f0a39)."""
    pw = pytest.importorskip("playwright.sync_api")
    f = _fixture(tmp_path)
    html = f.read_text()
    assert html.count("function setSheet") == 1
    with pw.sync_playwright() as p:
        b = p.chromium.launch(channel="chrome" if shutil.which("google-chrome") else None)
        pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto(f.as_uri())
        n = pg.evaluate("()=>[...document.scripts].filter(s=> (s.textContent||'').includes('function setSheet')).length")
        assert n == 1, n
        assert pg.evaluate("()=>document.getElementById('tf-sheet').hidden")
        pg.click("#tf-fbtn")
        pg.wait_for_timeout(80)
        assert pg.evaluate("()=>!document.getElementById('tf-sheet').hidden")
        pg.wait_for_timeout(200)
        assert pg.evaluate("()=>!document.getElementById('tf-sheet').hidden")
        pg.close()
        b.close()


def _listed_snap():
    """Fire synlige rader, én av dem ikke rangert (ALPE.OL), to uten risikonivå."""
    return {
        "date": "2026-11-17",
        "_risk_asof": date(2026, 11, 13),
        "_risk_today": date(2026, 11, 17),
        "tickers": [
            {"ticker": "EQNR.OL", "name": "Equinor", "points": {}, "score": 1.0,
             "stats": {"close": 10, "ret_5d": 0.01, "ret_20d": 0.02},
             "decision": {"sector": "Energy"},
             "_risk": {"level": "Høy", "market": "Oslo", "in_universe": 1}},
            {"ticker": "AAPL", "name": "Apple", "points": {}, "score": 1.0,
             "stats": {"close": 10, "ret_5d": 0.01, "ret_20d": 0.02},
             "decision": {"sector": "Technology"},
             "_risk": {"level": "Lav", "market": "US", "in_universe": 1}},
            {"ticker": "RHM.DE", "name": "Rheinmetall", "points": {}, "score": 1.0,
             "stats": {"close": 10, "ret_5d": 0.01, "ret_20d": 0.02},
             "decision": {"sector": "Industrials"},
             "_risk": {"level": "Høy", "market": "US", "in_universe": 0}},
            {"ticker": "ALPE.OL", "name": "Alpine", "points": {}, "score": 0.0,
             "stats": {"close": 10}, "decision": {}, "unranked": True, "_risk": None},
        ],
    }


def _listed_page(snap: dict) -> str:
    ranked = [e for e in snap["tickers"] if not e.get("unranked")]
    unr = [e for e in snap["tickers"] if e.get("unranked")]
    tables = ('<div class="card"><div class="tw"><table>'
              + "".join(S.ticker_row(e) for e in ranked) + "</table></div>")
    if unr:
        tables += ('<div class="ur-head"><b>Ikke rangert</b></div>'
                   + '<div class="tw"><table class="ur-tab">'
                   + "".join(S.ticker_row(e) for e in unr) + "</table></div>")
    tables += "</div>"
    return (
        "<!doctype html><html lang='no'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<style>:root{--bg:#0b0f14;--card:#161b22;--ink:#e6edf3;--mut:#9ea9b5;--acc:#6cb6ff;--line:#3a4350}"
        "body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 sans-serif}"
        + TL.CSS +
        "</style></head><body class='pg-tickere'>"
        + TL.tickere_intro(snap) + TL.filter_row(snap)
        + f"<div id='tf-table'>{tables}</div>"
        + TL.empties() + TL.JS +
        "</body></html>"
    )


def _facet_counts(html: str, group: str) -> dict[str, int]:
    m = re.search(rf'<section class="tf-sec" data-g="{group}">(.*?)</section>', html, re.S)
    assert m, group
    out = {}
    for mm in re.finditer(
        rf'data-g="{group}" data-k="([^"]+)"[^>]*>\s*<input[^>]*>\s*<span class="tf-opt-lab">([^<]+) \((\d+)\)</span>',
        m.group(1),
    ):
        out[mm.group(1)] = int(mm.group(3))
    return out


def _assert_totals_match(html: str, n_rows: int | None = None):
    if n_rows is None:
        n_rows = len(re.findall(r'<tr class="rowlink"', html))
    total = int(re.search(r'data-total="(\d+)"', html).group(1))
    vis = re.search(r'id="tf-count"[^>]*>Viser (\d+) av (\d+)', html)
    assert vis, html[html.find("tf-count"):html.find("tf-count")+200]
    n, tot = int(vis.group(1)), int(vis.group(2))
    risiko = _facet_counts(html, "risiko")
    sektor = _facet_counts(html, "sektor")
    bors = _facet_counts(html, "bors")
    assert "ingen" in risiko and "Ingen risikonivå" in html
    assert "ukjent-sektor" in sektor
    assert n_rows == total == n == tot == sum(risiko.values()) == sum(sektor.values()) == sum(bors.values()), {
        "rows": n_rows, "data-total": total, "viser": (n, tot),
        "risiko": risiko, "risiko_sum": sum(risiko.values()),
        "sektor_sum": sum(sektor.values()), "bors": bors, "bors_sum": sum(bors.values()),
    }
    return {"rows": n_rows, "total": total, "risiko": risiko, "sektor": sektor, "bors": bors}


def test_intro_and_listed_count_include_unranked():
    snap = _listed_snap()
    assert TL.listed_count(snap) == 4
    assert "4 kandidat-tickere" in TL.tickere_intro(snap)
    src = Path("signaltool/site.py").read_text()
    assert "TL.tickere_intro" in src
    meta = [TL.row_meta(e) for e in snap["tickers"]]
    assert sum(1 for r in meta if r["bors"] == "oslo") == 2  # EQNR + ALPE.OL


def test_static_html_row_count_equals_total_and_facet_sums():
    snap = _listed_snap()
    html = _listed_page(snap)
    got = _assert_totals_match(html, 4)
    assert got["bors"]["oslo"] == 2
    assert got["risiko"]["ingen"] == 2
    assert got["sektor"]["ukjent-sektor"] == 1
    assert "Viser 4 av 4" in html
    assert 'data-total="4"' in html


@pytest.mark.skipif(not (shutil.which("google-chrome") or shutil.which("chromium")), reason="ingen headless Chrome")
def test_headless_totals_nullstill_target_and_no_check_on_options(tmp_path):
    """Etter JS: radtall = total i teksten = fasettsum. Nullstill ≥ 44 px. Ingen ✓ i avkrysningsrader."""
    pw = pytest.importorskip("playwright.sync_api")
    snap = _listed_snap()
    html = _listed_page(snap)
    _assert_totals_match(html, 4)
    f = tmp_path / "tickere-total.html"
    f.write_text(html)
    with pw.sync_playwright() as p:
        b = p.chromium.launch(channel="chrome" if shutil.which("google-chrome") else None)
        pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto(f.as_uri())
        after = pg.evaluate(r"""()=>{
          const rows=[...document.querySelectorAll('#tf-table tr.rowlink')];
          const count=(document.getElementById('tf-count')||{}).textContent||'';
          const total=parseInt((document.getElementById('tf-wrap')||{}).getAttribute('data-total')||'0',10);
          const facets={};
          document.querySelectorAll('.tf-sheet .tf-sec').forEach(sec=>{
            const g=sec.getAttribute('data-g');
            facets[g]={};
            sec.querySelectorAll('.tf-opt').forEach(lab=>{
              const k=lab.getAttribute('data-k');
              const t=(lab.querySelector('.tf-opt-lab')||{}).textContent||'';
              const m=t.match(/[(](\d+)[)] *$/);
              facets[g][k]=m?parseInt(m[1],10):null;
            });
          });
          const m=count.match(/Viser (\d+) av (\d+)/);
          return {nRows:rows.length, total, count, viser:m?[parseInt(m[1],10),parseInt(m[2],10)]:null, facets,
                  intro:(document.querySelector('.pintro')||{}).textContent||''};
        }""")
        n = after["nRows"]
        assert n == after["total"] == after["viser"][0] == after["viser"][1] == 4, after
        assert after["intro"].startswith("4 kandidat-tickere")
        for g in ("risiko", "sektor", "bors"):
            assert sum(after["facets"][g].values()) == n, (g, after["facets"][g])
        assert after["facets"]["bors"]["oslo"] == 2
        assert after["facets"]["risiko"]["ingen"] == 2
        assert "ukjent-sektor" in after["facets"]["sektor"]

        pg.click("#tf-fbtn")
        # huk av Lav, sjekk at raden ikke har ✓
        pg.locator('.tf-sheet .tf-opt[data-g="risiko"][data-k="lav"] input').click()
        mark = pg.evaluate("""()=>{
          const lab=document.querySelector('.tf-sheet .tf-opt[data-g="risiko"][data-k="lav"]');
          const span=lab.querySelector('.tf-opt-lab');
          const before=getComputedStyle(span, '::before').content;
          return {text:span.textContent, before, hasChk:!!lab.querySelector('input[type=checkbox]'),
                  on:lab.classList.contains('is-on')};
        }""")
        assert mark["hasChk"] and mark["on"]
        assert "✓" not in mark["text"]
        assert mark["before"] in ("none", "normal", '""', "''") or not mark["before"] or mark["before"] == "none"

        rst = pg.evaluate("""()=>{
          const b=document.getElementById('tf-sheet-reset');
          const r=b.getBoundingClientRect();
          const cs=getComputedStyle(b);
          return {h:r.height, w:r.width, fs:cs.fontSize, bg:cs.backgroundColor, color:cs.color};
        }""")
        assert rst["h"] >= 44, rst
        assert rst["fs"] == "14px", rst

        pg.click("#tf-apply")
        # tom tilstand via søk som ikke treffer
        pg.fill("#tf-q", "zzzz-ingen-treff")
        empty = pg.evaluate("""()=>{
          const e=document.getElementById('tf-empty');
          const b=document.getElementById('tf-empty-reset');
          const r=b.getBoundingClientRect();
          const cs=getComputedStyle(b);
          return {shown:!e.hidden, h:r.height, w:r.width, fs:cs.fontSize, text:b.textContent};
        }""")
        assert empty["shown"] and empty["text"] == "Nullstill"
        assert empty["h"] >= 44, empty
        assert empty["fs"] == "14px", empty
        pg.close()
        b.close()



def test_unfiltered_zero_facet_options_omitted():
    """UxBot 23.11: børs/sektor/risiko med 0 rader i ufiltrert liste vises ikke. Annet beholder 0 (★ Mine)."""
    h = TL.filter_row({"tickers": [
        {"ticker": "EQNR.OL", "decision": {"sector": "Energy"}, "_risk": {"level": "Høy", "market": "Oslo", "in_universe": 1}},
        {"ticker": "AAPL", "decision": {}, "_risk": {"level": "Lav", "market": "US", "in_universe": 1}},
    ], "date": "2026-11-17"})
    risiko = _facet_counts(h, "risiko")
    sektor = _facet_counts(h, "sektor")
    bors = _facet_counts(h, "bors")
    annet = _facet_counts(h, "annet")
    assert risiko == {"hoy": 1, "lav": 1}
    assert set(sektor) == {"energi", "ukjent-sektor"} and all(n > 0 for n in sektor.values())
    assert bors == {"oslo": 1, "usa": 1}
    assert "mine" in annet and annet["mine"] == 0
    assert all(n > 0 for n in (*risiko.values(), *sektor.values(), *bors.values()))


@pytest.mark.skipif(not (shutil.which("google-chrome") or shutil.which("chromium")), reason="ingen headless Chrome")
def test_headless_zero_from_other_filters_is_dimmed_not_hidden(tmp_path):
    """0-treff som skyldes andre aktive filtre skal bare tones ned, ikke skjules."""
    pw = pytest.importorskip("playwright.sync_api")
    snap = _listed_snap()
    html = _listed_page(snap)
    # ufiltrert: ingen middels (utelatt), men lav/hoy/ingen, usa/oslo/tyskland, teknologi finnes
    risiko = _facet_counts(html, "risiko")
    assert "middels" not in risiko and risiko["lav"] == 1
    f = tmp_path / "tickere-dim.html"
    f.write_text(html)
    with pw.sync_playwright() as p:
        b = p.chromium.launch(channel="chrome" if shutil.which("google-chrome") else None)
        pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto(f.as_uri())
        pg.click("#tf-fbtn")
        pg.locator('.tf-sheet .tf-opt[data-g="bors"][data-k="oslo"] input').click()
        got = pg.evaluate("""()=>{
          const pick=(g,k)=>{
            const lab=document.querySelector(`.tf-sheet .tf-opt[data-g="${g}"][data-k="${k}"]`);
            if(!lab) return null;
            const cs=getComputedStyle(lab);
            return {present:true, zero:lab.classList.contains('is-zero'),
                    text:(lab.querySelector('.tf-opt-lab')||{}).textContent||'',
                    opacity:cs.opacity};
          };
          return {
            lav: pick('risiko','lav'),
            hoy: pick('risiko','hoy'),
            ingen: pick('risiko','ingen'),
            middels: pick('risiko','middels'),
            teknologi: pick('sektor','teknologi'),
            energi: pick('sektor','energi'),
            usa: pick('bors','usa'),
            danmark: pick('bors','danmark'),
          };
        }""")
        pg.close()
        b.close()
    # Lav og Teknologi blir 0 fordi Oslo-filteret ikke treffer AAPL; skal vises, nedtonet
    assert got["lav"] and got["lav"]["zero"] and "(0)" in got["lav"]["text"]
    assert float(got["lav"]["opacity"]) < 1
    assert got["teknologi"] and got["teknologi"]["zero"] and "(0)" in got["teknologi"]["text"]
    assert float(got["teknologi"]["opacity"]) < 1
    # Høy og Energi treffer EQNR.OL, ikke nedtonet
    assert got["hoy"] and not got["hoy"]["zero"] and "(1)" in got["hoy"]["text"]
    assert got["energi"] and not got["energi"]["zero"] and "(1)" in got["energi"]["text"]
    # USA finnes fortsatt (facet erstatter børs-valget); Danmark var 0 ufiltrert og skal ikke finnes
    assert got["usa"] and not got["usa"]["zero"]
    assert got["middels"] is None
    assert got["danmark"] is None
