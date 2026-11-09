from html import escape
from html.parser import HTMLParser
from signaltool import site, trender, overview as OV, site_intro as I

class Visible(HTMLParser):
    def __init__(self):
        super().__init__(); self.depth=0; self.text=[]
    def handle_starttag(self, tag, attrs):
        if tag=='details': self.depth+=1
    def handle_endtag(self, tag):
        if tag=='details': self.depth-=1
    def handle_data(self, text):
        if not self.depth: self.text.append(text)

def sample():
    return {'date':'2026-11-07','tickers':[{'ticker':'EXAMPLE','score':2.4}],
            'oslo_universe_flags':[{'ticker':'A.OL','flags':{'weak_px':'x','high_vol':'y'}},
                                    {'ticker':'B.OL','flags':{'neg_ebit':'z'}}],
            'oslo_flags_meta':{'asof':'2026-11-06'},
            'themes':[{'key':'example','name':'Example','score':3}], 'calendar':[]}

def test_overview_has_one_flag_summary_and_preserved_count_date_and_link():
    h=site.overview_html(sample())
    # UxBot 09.11: «Røde flagg Oslo» er nå også en inngang (lenke); fortsatt bare ett flaggsammendrag
    assert h.count('Røde flagg Oslo')==2 and h.count('Oslo-aksjer med 2+ flagg')==1   # AnalBot 09.11: flisen nevner utvalget
    assert '<a href="tickere.html?filter=flagg">Røde flagg Oslo</a>' in h
    assert '<div class="big">1</div>' in h and '<div class="sub">av 2 Oslo-aksjer med 2+ flagg</div>' in h
    assert 'data per 2026-11-06' in h and 'href="tickere.html?filter=flagg"' in h
    assert 'A.OL' not in h and 'B.OL' not in h
    assert 'Neste hendelse' not in h

def test_overview_order_compact_entries_and_untested_score():
    h=site.overview_html(sample())
    # UxBot 09.11: kandidattabellen før Marked og risiko (intro + kandidat 1 over bretten på 390)
    assert h.index('<h1>Oversikt</h1>') < h.index('class="ov-status"') < h.index(I.TEXTS['Oversikt']) < h.index('class="ov-go"') < h.index('class="card ov-candidates') < h.index('id="marked-risiko"') < h.index('class="ov-entries"') < h.index('aria-label="Nyheter"') < h.index('class="ov-low2"')
    assert 'Rangering, ikke testet' in h
    assert 'id="temascore"' not in h and 'class="ov-bar"' not in h
    assert 'href="temaer.html"' in h and 'href="trender.html"' in h

def test_trend_evidence_and_counterevidence_remain_visible_once():
    d=trender.load();h=trender.html(d);p=Visible();p.feed(h);visible=' '.join(p.text)
    for t in d['trends']:
        claims=t['latest']+[q for c in t['companies'] for q in (c['exposure'],c['limits'])]
        for c in claims:
            assert c['text'] in visible and h.count(escape(c['text'], quote=True))==1
        for chain in t['chain']:
            for k in ('material','component','industry','sector','published','period'):
                assert chain[k] in visible
        for c in t['background']: assert c['text'] not in visible
    assert 'Mangelstatus: Mangler data' in visible
    assert 'Rapportert vekst fra denne utviklingen: Mangler data' in visible
    assert 'Verdsettelse og kursutvikling mot indeks: Mangler data' in visible
    assert 'Inngangskurs er ikke registrert' in visible
    assert 'Tilknytning betyr ikke at selskapet vil tjene mer eller aksjen stige.' in visible
    assert 'Råvareavhengighet dokumenterer ikke økt fortjeneste hos selskapet.' not in h
    assert h.count('<summary>Les dokumentasjonen</summary>')==3

def test_no_nested_usage_frames_and_responsive_constraints_preserved():
    assert '.tr-chain>div{padding:0;background:none;border:0;border-radius:0;' in trender.CSS
    assert '@container(min-width:1000px)' in trender.CSS
    assert 'minmax(0,620fr) minmax(0,356fr)' in trender.CSS
    assert 'gap:24px' in trender.CSS and 'align-items:start' in trender.CSS
    assert 'min-height:44px' in trender.CSS and 'min-height:44px' in OV.CSS
    assert 'margin:0 0 32px' in OV.CSS and 'margin-bottom:24px' in OV.CSS


def test_source_links_have_real_44_by_44_hit_area():
    assert '.tr-page .tr-source a,.tr-page .tr-source-short a,.tr-company h4>a{display:inline-flex;align-items:center;min-width:44px;min-height:44px;' in trender.CSS
    h=trender.html()
    assert 'class="tr-source-short"' in h and '>Kilde</a>' in h
    for t in trender.load()['trends']:
        for c in t['chain']:
            assert c['published'] in h and c['period'] in h


def test_deploy_check_accepts_new_overview_and_requires_themescore_on_themes(tmp_path, monkeypatch):
    import json
    from signaltool import sitecheck as C, theme_maps as TM
    for filename, needles in C.REQUIRED.items():
        (tmp_path/filename).write_text(' '.join(needles))
    actual=site.page('Oversikt',site.overview_html(sample()),0,sample())
    (tmp_path/'index.html').write_text(actual)
    (tmp_path/'data.json').write_text(json.dumps({'date':'2026-11-07','themes':[{'key':'example'}]}))
    (tmp_path/'tema').mkdir()
    for m in TM.MAPS.values(): (tmp_path/'tema'/f"{m['file']}.html").write_text('example')
    (tmp_path/'ticker').mkdir();(tmp_path/'ticker'/'EXAMPLE.html').write_text('example')
    monkeypatch.setattr(C,'log_page_problems',lambda *a:[])
    assert 'Temascore' not in actual
    assert C.check(tmp_path)==[]
    (tmp_path/'temaer.html').write_text('Temaer')
    assert 'temaer.html: mangler «Temascore»' in C.check(tmp_path)
    (tmp_path/'temaer.html').write_text('Temaer Temascore')
    (tmp_path/'index.html').write_text(actual.replace('Marked og risiko',''))
    assert 'index.html: mangler «Marked og risiko»' in C.check(tmp_path)
