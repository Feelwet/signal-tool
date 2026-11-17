"""UxBot 17.11: filtre (risiko, sektor, børs) og kontrast på Tickere."""
from __future__ import annotations

import re
import shutil
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
    assert ".tf-slukk{flex:none;width:44px;height:44px" in TL.CSS
    assert ".tf-apply{height:48px;min-height:48px" in TL.CSS
    assert ".tf-empty{" in TL.CSS and "min-height:48px" in TL.CSS
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
    assert "Oslo (1)" in h and "USA (1)" in h
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
    import csv
    from collections import defaultdict
    from pathlib import Path as P
    from signaltool.bors import bors_of
    from signaltool.config import LOGS
    path = LOGS / "risk_levels.csv"
    if not path.exists():
        return
    last = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
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

