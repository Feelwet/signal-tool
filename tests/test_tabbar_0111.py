from signaltool import tabbar as TB
from signaltool import site as S


def test_tabbar_tabs_and_more_sheet():
    h = TB.html("makro.html", "")
    for lab in ("Oversikt", "Tickere", "Oslo", "Signal-boka", "Mer"):
        assert f"<span>{lab}</span>" in h
    assert 'class="tb-t tb-more on"' in h                       # aktiv side under Mer lyser Mer-fanen
    for href in ("temaer.html", "sektorer.html", "makro.html", "kalender.html", "metode.html", "tickere.html?filter=flagg", "metode.html#treffrate", "kilder.html"):
        assert f'href="{href}"' in h
    assert 'aria-current=page' in TB.html("tickere.html", "../") and 'href="../tickere.html"' in TB.html("tickere.html", "../")


def test_ham_nav_pages_all_reachable_on_mobile():
    from signaltool import site_layout as L
    hrefs = {h for _, h, sub in L.NAV if h} | {h for _, h, sub in L.NAV if not h for h, _ in sub}
    reach = {h for h, _, _ in TB.TABS} | {h.split("?")[0].split("#")[0] for h, _ in TB.MORE}
    assert hrefs <= reach


def test_tabbar_css_and_page():
    c = TB.CSS
    assert "@media(max-width:768px)" in c and "56px + env(safe-area-inset-bottom" in c and "#1c2430" in c and "1px solid #3b4757" in c
    assert "72px + env(safe-area-inset-bottom" in c and ".side-toggle" in c and "height:48px" in c and "height:40px" in c and "height:32px" in c
    html = S.page("Oversikt", "<p>x</p>", 0, {"generated": "2026-11-01 21:19"})
    assert 'class="tabbar"' in html and 'id="more-sheet"' in html
