"""Verdikjeder i Trender (låst spesifikasjon 09.11.2026)."""
import json, re
from pathlib import Path
import pytest
from signaltool import verdikjeder as V, trender as T

LOG = Path('site_config/verdikjeder/halvledere_links.jsonl')
RAW = {n: json.loads(s) for n, s in enumerate(LOG.read_text().splitlines(), 1)}


def block():
    return V.html(available_tickers={'NOD.OL', 'NVDA', 'AI'})


def visible(h):
    h = re.sub(r'<style.*?</style>|<script.*?</script>', '', h, flags=re.S)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h))


def test_corrections_replace_and_superseded_text_never_shown():
    d = V.load()
    assert len(RAW) == 34 and len(d['links']) == 30
    corr = {n: r['corrects_line'] for n, r in RAW.items() if 'corrects_line' in r}
    assert corr == {31: 15, 32: 27, 33: 10, 34: 25}
    h = block()
    for new, old in corr.items():
        assert RAW[old]['claim'] not in h
        assert RAW[new]['claim'] in h
        assert RAW[old]['revenue_share'] not in h.replace(RAW[new]['revenue_share'], '')
    assert '86,9' not in h
    assert 'Fabless' not in [l for l in d['links'] if l['ticker'] == 'NVDA'][0]['claim']
    nv = re.search(r'<li class="vk-el" data-line="34">.*?</li>', h, re.S).group(0)
    assert 'fabless' not in nv.lower()


def test_every_element_has_source_year_and_share_text():
    for l in V.load()['links']:
        assert V.valid_source(l['source_url']) and l['source_year']
    h = block()
    assert h.count('class="vk-el"') == 30
    assert h.count('Kilde 20') == 30


def test_bad_source_is_hidden_and_corrections_fail_closed(tmp_path):
    meta = json.loads(Path('site_config/verdikjeder/halvledere.json').read_text())
    rows = [dict(r) for r in RAW.values()]
    def run(rs):
        (tmp_path / 'halvledere.json').write_text(json.dumps(meta))
        (tmp_path / meta['links_file']).write_text('\n'.join(json.dumps(r) for r in rs) + '\n')
        return V.load(base=tmp_path)
    bad = [dict(r) for r in rows]; bad[0]['source_url'] = 'javascript:alert(1)'
    assert all(l['line'] != 1 for l in run(bad)['links'])
    twice = rows + [dict(rows[30])]
    with pytest.raises(ValueError): run(twice)
    fwd = [dict(r) for r in rows]; fwd[30]['corrects_line'] = 40
    with pytest.raises(ValueError): run(fwd)
    unk = [dict(r) for r in rows]; unk[0]['stage'] = 'ukjent'
    with pytest.raises(ValueError): run(unk)


def test_forbidden_words_absent_from_chain_block():
    h = block().lower()
    for w in V.FORBIDDEN:
        assert w.lower() not in h, w


def test_flaskehals_only_on_asml_euv():
    h = block()
    assert h.count('Flaskehals') == 1
    asml = re.search(r'<li class="vk-el" data-line="3">.*?</li>', h, re.S).group(0)
    assert 'Flaskehals · EUV 38 %' in asml and '2024' in asml


def test_five_stages_fixed_order_and_two_tracks():
    h = visible(block())
    pos = [h.index(f'{n} · {t}') for n, t in [(1, 'Råvare og komponent'), (2, 'Produsenter'), (3, 'Bruksområde'),
                                             (4, 'Berørte industrier og produkter'),
                                             (5, 'Børsnoterte selskaper i kjeden (ikke testet for avkastning)')]]
    assert pos == sorted(pos)
    assert 'Direkte (1. orden)' in h and 'Leverandører (2. orden)' in h
    assert 'Offentlige kilder · sist kontrollert 09.11.2026' in h
    assert '16 direkte · 1 andre-orden' in h and '8 direkte · 5 andre-orden' in h
    assert 'Råvare og komponent · 16 + 1' in h and 'Produsenter · 8 + 5' in h
    assert 'kommer snart' not in h.lower()


def test_stage5_wording_and_no_price_score_or_colour():
    raw = block()
    s5 = raw[raw.index('id="vk-halvledere-selskaper"'):]
    assert V.STAGE5_HEAD in s5 and V.STAGE5_LINE in s5
    assert s5.index(V.STAGE5_HEAD) < s5.index(V.STAGE5_LINE)
    for bad in ('score', 'kurs:', 'avkastning:', 'class="up"', 'class="down"', 'class="hot', 'class="warm', 'class="score', 'Kjøp', 'kandidat', ' %'):
        assert bad not in visible(s5.split('</table>')[0].split('<table')[1]) and 'class="' + bad not in s5, bad
    assert '>Alle<' in s5 and '>Oslo<' in s5 and '>USA<' in s5
    oslo = re.findall(r'<tr data-region="oslo"><td><b>(\w+)</b>', s5)
    assert sorted(oslo) == ['NOD', 'REC']
    # Air Liquide (Euronext Paris, «AI») skal ikke lenke til en annen ticker med samme symbol
    ai = re.search(r'<tr data-region="annen"><td><b>AI</b>.*?</tr>', s5).group(0)
    assert 'Se ticker' not in ai


def test_chain_is_first_block_under_intro_and_existing_content_unchanged(monkeypatch):
    h = T.html()
    assert h.index('</header>') < h.index('class="vk"') < h.index('class="tr-tabs"')
    monkeypatch.setattr(T.VK, 'html', lambda **k: '')
    monkeypatch.setattr(T.VK, 'CSS', '')
    monkeypatch.setattr(T.VK, 'JS', '')
    without = T.html()
    # alt etter verdikjedeblokken er byte-likt med siden uten blokken
    rest = h.split('<p class="vk-meta">Til egen undersøkelse.</p></section>', 1)[1]
    assert rest.split('<script>')[0] == without.split('</header>', 1)[1].split('<script>')[0]
    for t in T.load()['trends']:
        assert t['title'] in h


def test_mobile_and_desktop_rules_in_css():
    c = V.CSS
    assert 'height:44px' in c and 'height:56px' in c and 'min-height:56px' in c
    assert 'grid-template-columns:1fr 1fr;gap:24px' in c
    assert 'border-left:4px solid' in c and 'border-left:4px dashed' in c
    assert 'background:#fff' in c and 'background:#f1f3f5' in c
    assert 'font-size:13px;line-height:18px;color:#9ca3af' in c
    assert '.vk .vk-name{font-size:16px;line-height:24px' in c
    assert 'font-size:14px;line-height:20px;color:#4b5563' in c
    assert 'min-width:44px;min-height:44px' in c
    m = c[c.index('@media(max-width:600px)'):]
    assert '.vk-flow{display:none}' in m and '.vk-track.vk-empty{display:none}' in m
    assert 'max-height:88px' in m and 'max-height:96px' in m
    assert '.vk .vk-none{font-size:14px;line-height:20px;color:#4b5563;margin:0;max-height:40px' in c
    assert block().count(' open>') == 1


def test_chains_never_touch_score_candidates_or_signal_book():
    # Bare trender.py (og modulen selv) kjenner verdikjedene; scoring, kategorier, portefølje og Signal-boka gjør ikke.
    users = [p.name for p in Path('signaltool').rglob('*.py')
             if re.search(r'\bVK\b|import verdikjeder|verdikjeder as', p.read_text(errors='ignore')) and p.name != 'verdikjeder.py']
    assert users == ['trender.py']
    trender_users = {p.name for p in Path('signaltool').rglob('*.py')
                     if re.search(r'import trender|trender as|from \.trender|from \. import .*\btrender\b', p.read_text(errors='ignore'))}
    assert trender_users <= {'site.py'}
    logs = {p: p.stat().st_mtime_ns for p in Path('logs').glob('*') if p.is_file()}
    block(); T.html()
    assert logs == {p: p.stat().st_mtime_ns for p in logs}
    from signaltool import categories, portfolio
    for mod in (categories, portfolio):
        assert not hasattr(mod, 'VK') and 'verdikjeder' not in Path(mod.__file__).read_text()


def test_no_private_paths_in_public_copy():
    txt = LOG.read_text() + Path('site_config/verdikjeder/halvledere.json').read_text()
    for bad in ('/workspace', '/home/', '/cursor/', 'file:'):
        assert bad not in txt
