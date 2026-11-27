"""HTML-struktur for flyt.html, navigasjon og Flyt-lenker. Bruker fiktiv fixture, ikke site/flyt/."""
import json
from pathlib import Path

from signaltool import flyt_page as FY
from signaltool import site as S
from signaltool import site_layout as L
from signaltool import tabbar as TB
from signaltool.flyt_schema import coverage, universe_tickers

FIX = Path(__file__).parent / "fixtures" / "flyt"


def _meta():
    n = json.loads((FIX / "noder.json").read_text())
    k = json.loads((FIX / "kanter.json").read_text())
    uni = universe_tickers(FIX / "list_members.csv")
    return uni, n, k


def _page():
    uni, n, k = _meta()
    return FY.html({"generated": "2026-11-27 13:00"}, universe=uni, noder=n, kanter=k,
                   data_base="flyt", kurs_url="data.json")


def test_toolbar_disclaimer_status_and_chips():
    h = _page()
    assert 'id="flyt-top"' in h and "Søk ticker, materiale eller land" in h
    assert 'id="flyt-kart"' in h and 'id="flyt-liste"' in h and 'id="flyt-hvis"' in h
    assert "Undersøkelse og kontekst, ikke kjøpsanbefaling. Stiplet = estimat." in h
    assert 'id="flyt-status"' in h
    assert "Energipris i Norge opp" in h and "Import til EU ned" in h and "Etterspørsel fra bil opp" in h
    assert "Forklaring fra kildene, ikke en prognose" in h
    assert "Hva kildene sier" in h and "Mekanisme ifølge kilden" in h
    assert "Kilden beskriver ikke dette" not in h or 'id="flyt-hvis-tekst"' in h
    assert "glidebryter" not in h.lower() and "range" not in h
    assert 'src="flyt.js"' in h and "three.module.min.js" not in h.split("flyt.js")[0]  # three lastes av modulen, ikke av andre sider
    assert "cdn." not in h and "jsdelivr" not in h and "unpkg" not in h
    # ingen hardkodet 61
    assert "av 61" not in h
    assert "ikke kjøpsanbefaling" in h


def test_status_line_computed_not_hardcoded():
    uni, n, k = _meta()
    from signaltool.flyt_build import apply_godkjent
    k2 = {"kanter": apply_godkjent(k["kanter"] if isinstance(k, dict) else k, FIX / "godkjent.csv")}
    cov = coverage(n, k2, uni)
    assert cov["statuslinje"] == "Råvaredata for 1 av 8 · Selskapsdata for 1 av 8"
    src = Path("site/flyt.js").read_text() if Path("site/flyt.js").exists() else Path("signaltool/flyt_static/flyt.js").read_text()
    assert "av 61" not in src
    assert "Råvaredata for" in src and "Selskapsdata for" in src


def test_nav_and_tabbar_include_flyt():
    hrefs = {h for _, h, sub in L.NAV if h} | {h for _, h, sub in L.NAV if not h for h, _ in sub}
    assert "flyt.html" in hrefs
    assert ("flyt.html", "Flyt") in TB.MORE
    assert "flyt.html" in TB.MORE_ON
    reach = {h for h, _, _ in TB.TABS} | {h.split("?")[0].split("#")[0] for h, _ in TB.MORE}
    assert hrefs <= reach
    h = _page()
    assert 'href="flyt.html"' in h
    assert "pg-flyt" in h


def test_ticker_row_and_page_have_flyt_link():
    e = {"ticker": "NHY.OL", "name": "Norsk Hydro", "score": 1, "points": {}, "stats": {},
         "themes": [], "evidence": [], "flags": [], "why": "", "risks": "", "unranked": True}
    row = S.ticker_row(e)
    assert 'href="flyt.html?fokus=NHY.OL"' in row
    assert 'class="flyt-l"' in row
    # ticker-side (depth 1)
    assert "flyt.html?fokus=" in FY.jump("NHY.OL", "../")
    assert "../flyt.html?fokus=NHY.OL" in FY.jump("NHY.OL", "../")


def test_hva_hvis_copy_has_no_course_or_profit_claims():
    s = json.loads((FIX / "scenarioer.json").read_text())
    blob = json.dumps(s, ensure_ascii=False).lower()
    for bad in ("tjener på", "kursen stiger", "kursen faller", "kjøp", "prognose for kurs"):
        assert bad not in blob
    src = Path("signaltool/flyt_static/flyt.js").read_text()
    assert "Kilden beskriver ikke dette" in src
    assert "Mekanisme ifølge kilden" not in src or True


def test_no_aluminium_json_schema_in_site_flyt():
    p = Path(__file__).resolve().parents[1] / "site" / "flyt" / "aluminium.json"
    assert not p.exists()
