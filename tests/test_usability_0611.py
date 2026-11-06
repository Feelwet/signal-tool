from html.parser import HTMLParser
from signaltool import trender, usability, site, since


class HiddenText(HTMLParser):
    def __init__(self):
        super().__init__(); self.depth=0; self.visible=[]; self.hidden=[]
    def handle_starttag(self,tag,attrs):
        if tag=='details':self.depth+=1
    def handle_endtag(self,tag):
        if tag=='details':self.depth-=1
    def handle_data(self,text):
        (self.hidden if self.depth else self.visible).append(text)


def test_header_before_trend_jumps_and_companies():
    h=trender.html()
    assert h.index('<h1>Trender</h1>')<h.index('aria-label="Trender på siden"')
    assert h.index('class="tr-explanation"')<h.index('class="tr-company"')
    assert 'class="tr-index"' not in h and 'class="tr-company-jumps"' not in h
    assert 'min-height:44px' in trender.CSS
    assert 'minmax(0,620fr) minmax(0,356fr)' in trender.CSS
    assert 'font-size:17px;line-height:26px' in trender.CSS


def test_uncertainty_not_hidden_in_documentation():
    h=trender.html(); p=HiddenText();p.feed(h)
    visible=' '.join(p.visible);hidden=' '.join(p.hidden)
    for text in ['Ikke testet for tidlighet','Mangelstatus: Mangler data','Andel ikke oppgitt','Hva svekker bildet?','avkastningsmåling er ikke startet']:
        assert text in visible
    assert 'Bakgrunn' in hidden and 'Dokumentert bruk' in visible
    assert 'Eksponert for trenden (ikke testet for avkastning)' in visible
    assert 'Avhengig av' in visible and 'Avhengig av' not in hidden
    for trend in trender.load()['trends']:
        for chain in trend['chain']:
            assert chain['published'] in visible and chain['period'] in visible
    assert '<p class="tr-status">Ikke testet for tidlighet</p>' in h


def test_only_link_companies_with_existing_internal_pages():
    h=trender.html()
    assert 'href="ticker/MP.html"' not in h
    h=trender.html(available_tickers={'MP'})
    assert 'href="ticker/MP.html"' in h
    assert 'href="ticker/CLF.html"' not in h


def test_scores_have_persistent_text_not_just_title():
    h=site.score_badge(2.123,muted=True)
    assert '<span class="sv">2.12</span>' in h
    assert '<span class="score-note">Rangering, ikke testet</span>' in h


def test_secondary_values_retained_and_disclosures_are_interactive():
    e={'ticker':'TEST','stats':{'ret_5d':.1,'ret_20d':None}}
    h=site.row_details(e)
    assert '+10,0 %' in h and '20d: –' in h and '<summary>Detaljer</summary>' in h
    assert '<td' not in h and '</td>' not in h
    assert 'summary,details' in since.JS


def test_layout_does_not_change_scoring_or_order():
    css=usability.CSS
    assert 'text-overflow:clip!important' in css
    assert 'table-layout:fixed' in css
    assert '-webkit-line-clamp:unset!important' in css
    assert '#tf-table table td:nth-child(7){display:none}' in css
    src=open(site.__file__).read()
    assert src.index('sec("Kandidater og røde flagg"')<src.index('sec("Verden nå"')
    assert 'TR.teaser()' in src


def test_unranked_details_do_not_reintroduce_suppressed_returns():
    h=site.row_details({'unranked':True,'stats':{'ret_5d':.1,'ret_20d':.2}})
    assert '5d: –' in h and '20d: –' in h
    assert '+10,0' not in h and '+20,0' not in h


def test_compact_trends_do_not_duplicate_claims_or_company_cards():
    from html import escape
    h=trender.html(); data=trender.load()
    assert h.count('class="tr-company"')==sum(len(t['companies']) for t in data['trends'])
    for t in data['trends']:
        claims=t['background']+t['latest']+[c[k] for c in t['companies'] for k in ['exposure','limits']]
        for c in claims:
            assert h.count(escape(c['text'],quote=True))==1
    assert 'Råvareavhengighet dokumenterer ikke økt fortjeneste hos selskapet.' in h
    assert 'max-width:1000px' in trender.CSS and '@container(min-width:1000px)' in trender.CSS
    assert 'grid-template-areas:"chain" "companies" "follow"' in trender.CSS
    assert '.tr-chain{grid-template-columns:minmax(0,1fr)}' in trender.CSS
    assert 'grid-template-columns:80px minmax(0,1fr)' in trender.CSS


def test_compact_trends_have_progressive_choices_and_old_anchor_targets():
    h=trender.html()
    assert h.count('aria-controls=')==3
    for t in trender.load()['trends']:
        assert f'href="#{t["id"]}"' in h
        for i,c in enumerate(t['companies']):
            assert h.count(f'id="{t["id"]}-selskap-{i}"')==1
    assert 'p.hidden=p!==panel' in trender.JS
    assert "addEventListener('popstate'" in trender.JS
    assert 'localStorage' not in trender.JS and 'fetch(' not in trender.JS
