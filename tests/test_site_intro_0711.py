from html import escape
import pytest
from signaltool import site_intro as I, site_layout as L, trender, sectors, portfolio_page

@pytest.mark.parametrize("title", ["Makro", "Oslo", "Temaer"])
def test_visible_header_before_metadata_and_kpis(title):
    h=L.head(title, "gammel forklaring", [("1","Et mål","detalj","#")], meta='<p class="src">kilde</p>')
    assert h.index('</h1>') < h.index(I.html(title)) < h.index('class="src"') < h.index('class="kpis')
    assert 'gammel forklaring' not in h
    assert h.count(escape(I.TEXTS[title])) == 1
    assert '<details' not in h and 'role="tooltip"' not in h

def test_theme_quality_caution_is_visible_after_intro():
    h=I.html("Temaer")
    assert h.index('class="page-intro"') < h.index('class="page-intro-caution"')
    assert I.THEME_CAUTION in h and 'hidden' not in h
    assert 'font-size:14px;line-height:22px' in I.CSS

def test_intro_style():
    assert 'font-size:15px;line-height:23px;max-width:720px;margin:0 0 16px' in I.CSS
    assert I.CSS in L.CSS

def test_trender_intro_before_choices_and_no_new_certainty():
    h=trender.html()
    assert h.index('</h1>') < h.index(I.html("Trender")) < h.index('class="tr-tabs"')
    assert 'Tilknytning betyr ikke at selskapet vil tjene mer eller aksjen stige.' in h
    assert 'Eksponert for trenden (ikke testet for avkastning)' in h

def test_sector_intro_and_forward_caveat():
    h=sectors.index_html({"data":{}})
    assert h.index('</h1>') < h.index(I.html("Sektorer")) < h.index('class="scards"')
    assert 'Frosset 24.10' in h and 'ikke bakovertestet' in h

def test_portfolio_intro_not_matched_control_claim(tmp_path, monkeypatch):
    from signaltool import gs_index, testbooks_page
    monkeypatch.setattr(gs_index, 'section_html', lambda: '')
    monkeypatch.setattr(testbooks_page, 'section_html', lambda **kw: '')
    monkeypatch.setattr(testbooks_page, 'rules_html', lambda: '')
    h=portfolio_page.html({}, tmp_path/'trades.csv', tmp_path/'nav.csv')
    assert h.index('</h1>') < h.index(I.html("Signal-boka")) < h.index('class="card pf-status"')
    assert 'kontrollportefølje' not in I.TEXTS['Signal-boka']
    assert 'For få handler (n=0)' in h
