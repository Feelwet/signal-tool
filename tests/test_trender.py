import copy
import json
from pathlib import Path
import pytest
from signaltool import trender as T, site, tabbar, site_layout


def test_all_claims_have_sources_and_dates():
    d=T.load()
    assert len(d['trends']) == 3
    assert sum(len(t['companies']) for t in d['trends']) == 2
    for t in d['trends']:
        assert t['status'] == 'Tidlig observasjon'
        for c in t['chain']:
            assert T.valid_source(c['source']) and c['published'] and c['period']


def test_no_invented_growth_shortages_or_returns():
    h=T.html()
    assert 'Mangelstatus: Mangler data' in h
    assert 'Andel ikke oppgitt' in h
    assert 'Rapportert vekst fra denne utviklingen: Mangler data' in h
    assert 'Ikke testet for tidlighet' in h
    assert 'Eksponert for trenden (ikke testet for avkastning)' in h
    assert 'Inngangskurs er ikke registrert' in h
    assert 'FLAG' not in h and 'robust' not in h.lower()
    assert 'class="up"' not in h
    assert 'oppside' not in h.lower()


def test_navigation():
    assert ('Trender','trender.html',[]) in site_layout.NAV
    assert tabbar.MORE[0] == ('trender.html','Trender')
    assert 'href="trender.html"' in T.teaser()
    assert 'aria-current=page' not in tabbar.html('trender.html','')
    assert 'tb-more on' in tabbar.html('trender.html','')


def test_mobile_and_desktop_layout():
    assert 'minmax(0,720px)' in T.CSS
    assert 'font-size:17px;line-height:26px' in T.CSS
    assert 'max-width:600px' in T.CSS
    assert 'data-label=' in T.html()
    assert 'Siste utvikling' in T.html() and 'Bakgrunn' in T.html()


@pytest.mark.parametrize('kind',['source','status','share','growth'])
def test_fail_closed_invalid_content(tmp_path,kind):
    d=copy.deepcopy(T.load()); t=d['trends'][0]
    if kind=='source': t['background'][0]['source']='javascript:alert(1)'
    if kind=='status': t['status']='Bekreftet utvikling'
    if kind=='share': t['chain'][0]['share']=99
    if kind=='growth': t['companies'][0]['growth']='Vekst'
    p=tmp_path/'trender.json';p.write_text(json.dumps(d))
    with pytest.raises(ValueError):T.load(p)


def test_build_does_not_rewrite_first_seen():
    p=Path('logs/trender_observations.jsonl'); before=p.read_bytes()
    a=T.load(); T.html(); b=T.load()
    assert a==b and p.read_bytes()==before


def test_escape_content():
    d=copy.deepcopy(T.load());d['trends'][0]['title']='<script>x</script>'
    assert '<script>x</script>' not in T.html(d)
