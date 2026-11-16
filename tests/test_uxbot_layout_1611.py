"""UxBot 16.11 (bindende): Tickere-rad som <a>, Bekreftede koblinger-grid og radhøyde, 390-rekkefølge,
faner 200 px, produsentvisning 50/50, komp-path 44 px. AnalBot+UxBot: dato/år i eget element utenfor ellipsis."""
from __future__ import annotations

import re
from datetime import date

from signaltool import kjede as K
from signaltool import site as S
from signaltool import ux390 as U

PAGE = date(2026, 11, 11)
AVAIL = {"LMT", "RTX", "KOG.OL"}


def section():
    return K.section_html("KOG.OL", available=AVAIL, page_date=PAGE)


def test_tickere_row_is_anchor_star_outside():
    h = S.ticker_row({"ticker": "KOG.OL", "name": "Kongsberg Gruppen ASA", "score": 2.1,
                      "points": {}, "stats": {"close": 1}, "_risk": {"level": "Lav"}})
    a = re.search(r'<a class="row-a" href="([^"]+)">(.*?)</a>', h)
    assert a and a.group(1).endswith("ticker/KOG_OL.html") and "Kongsberg Gruppen ASA" in a.group(2)
    assert "mstar" not in a.group(0)
    assert '<td class="mcol">' in h and 'class="mstar"' in h
    assert a.start() < h.find('class="mstar"')
    assert '<tr class="rowlink" tabindex="0"' not in h  # ett tabstopp: selve <a class="row-a">
    mob = U.CSS.split("@media(max-width:599px){", 1)[1].split("}@media(min-width:600px)", 1)[0]
    assert "a.row-a{position:absolute;top:0;left:0;bottom:0;right:44px;z-index:1" in mob
    assert "td.mcol .mstar{width:44px;height:44px;min-width:44px;min-height:44px" in mob
    assert "a.row-a:focus-visible{outline:2px solid #60a5fa" in mob
    # den gamle navnelenke-strekken skal ikke brukes (overflow:hidden klippet den live)
    assert ".tn .nm a::after" not in U.CSS


def test_kjede_grid_fr_units_no_fixed_column_widths():
    s = section()
    assert "grid-template-columns:minmax(0,9fr) minmax(0,10fr) minmax(0,9fr)" in s
    assert "gap:24px" in s
    assert "360px 400px 360px" not in s
    assert ".kjede-mid{width:400px}" not in s
    assert ".kjede-col{width:360px}" not in s
    assert 'class="kjede-col kjede-sup"' in s
    assert 'class="kjede-col kjede-cus"' in s
    # 390: selskap, leverandører, kunder (grid-area, ikke nth-of-type som byttet kolonnene)
    assert 'grid-template-areas:"mid" "sup" "cus"' in s
    assert ".kjede-col:nth-of-type" not in s


def test_simple_row_role_and_date_flex_date_never_in_ellipsis():
    s = section()
    css = s[s.find("<style>"):s.find("</style>")]
    assert ".kjede-meta{display:flex;align-items:baseline;min-width:0;margin:0}" in css
    assert (".kjede-role{flex:1 1 auto;min-width:0;overflow:hidden;"
            "text-overflow:ellipsis;white-space:nowrap;font-size:12px;line-height:16px") in css
    assert (".kjede-date{flex:none;white-space:nowrap;margin-left:8px;"
            "overflow:visible;font-size:12px;line-height:16px;color:#94a3b8}") in css
    assert ".kjede-row{box-sizing:border-box;min-height:64px;max-height:96px" in css
    assert ".kjede-row:has(.kjede-more){max-height:140px}" in css
    assert ".kjede-name{" in css and "text-overflow:ellipsis;white-space:nowrap" in css
    arts = re.findall(r'<article class="kjede-row[^"]*"[^>]*>.*?</article>', s, re.S)
    simple = [a for a in arts if "Alle kontrakter" not in a]
    assert simple
    for a in simple:
        if 'class="kjede-meta"' not in a:
            continue
        meta = re.search(r'<div class="kjede-meta">(.*?)</div>\s*(?:<div class="kjede-src|$)', a, re.S)
        assert meta, a[:200]
        inner = meta.group(1)
        role = re.search(r'<div class="kjede-role">.*?</div>', inner, re.S)
        dato = re.search(r'<span class="kjede-date">[^<]+</span>', inner)
        assert role and "kjede-date" not in role.group(0)
        # dato/år ligger i eget søskenelement utenfor rolle-ellipsis
        assert dato and dato.start() >= role.end()
    # kilder ≥ 24 mnd viser år i datoelementet (ikke kuttet); 10.12.2024 blir år 10.12.2026
    s_year = K.section_html("KOG.OL", available=AVAIL, page_date=date(2026, 12, 10))
    assert re.search(r'<span class="kjede-date">2024</span>', s_year)
    marand = next(a for a in re.findall(r'<article class="kjede-row[^"]*"[^>]*>.*?</article>', s_year, re.S)
                  if 'kjede-name">Marand Precision Engineering<' in a)
    assert '<span class="kjede-date">2024</span>' in marand
    assert 'kjede-date">10.12.2024' not in marand
    # rader med «Alle kontrakter (n)» kan gå til 140
    more = next(a for a in arts if "Alle kontrakter (4)" in a)
    assert "max-height:140px" in css


def test_tabs_200px_after_50_percent_and_left_aligned():
    s = section()
    i50 = s.find("flex:1 1 50%")
    i200 = s.rfind("flex:0 0 200px;width:200px")
    assert 0 <= i50 < i200  # 200 px-regelen kommer etter 50/50, ellers vinner 50/50 ved 1280
    assert "justify-content:flex-start" in s


def test_producer_view_50_50_at_1280_customers_first_when_stacked():
    s = section()
    one = '.komp-prod-grid{display:grid;grid-template-columns:minmax(0,1fr);grid-template-areas:"cus" "card"'
    mq = "@media(min-width:1024px){"
    two = '.komp-prod-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);grid-template-areas:"cus card";gap:24px}'
    assert one in s and mq in s and two in s
    # 1-kolonne-regelen må stå før 1024-regelen, ellers vinner den ved 1280 (live-avvik i 18c3289)
    assert s.find(one) < s.find(mq) < s.find(two, s.find(mq))
    assert "komp-prod-view" in s
    assert "komp-prod-cus" in s
    assert "komp-prod-card" in s
    # i DOM: kunder først, deretter produsentkort (390 stablet = samme rekkefølge)
    i_cus = s.find('class="komp-prod-cus"')
    i_card = s.find('class="komp-prod-card"')
    assert 0 < i_cus < i_card
    # tomtilstand uendret
    assert "Ingen kunder navngitt i offentlige kilder" in s
    assert "Kunder av Norsk Hydro ASA (7)" in s


def test_komp_path_390_one_line_ellipsis_on_last_norwegian_names():
    s = section()
    assert "komp-crumb-mid" in s and "komp-crumb-last" in s
    assert "@media(max-width:599px)" in s
    assert ".komp-path{flex-wrap:nowrap;align-items:center;height:44px;min-height:44px;max-height:44px;overflow:hidden" in s
    assert ".komp-crumb,.komp-crumb-sep,.komp-crumb-mid{flex:none;white-space:nowrap}" in s
    assert ".komp-crumb-last{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" in s
    # norske visningsnavn i brikker og data-path (brødsmule)
    for no, en in (("Stål", "Steel"), ("Kobber", "Copper"), ("Aluminium", "Aluminium"), ("Jern", "Jern")):
        assert f">{no}<" in s
        if no != en:
            assert f'data-path="KOG.OL|{en}|' not in s
            assert f'data-path="KOG.OL|{no}|' in s


def test_tabs_390_nowrap_14_20_still_44px():
    s = section()
    mob = s.split("@media(max-width:599px){", 1)[1]
    assert ".kjede-tab{white-space:nowrap;font-size:14px;line-height:20px;height:44px;min-height:44px}" in mob
