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
    assert len(RAW) == 37 and len(d['links']) == 30
    corr = {n: r['corrects_line'] for n, r in RAW.items() if 'corrects_line' in r}
    assert corr == {31: 15, 32: 27, 33: 10, 34: 25, 35: 4, 36: 22, 37: 33}
    h = block()
    final = {n for n in corr if n not in corr.values()}       # 37 retter 33 som retter 10: bare 37 gjelder
    assert final == {31, 32, 34, 35, 36, 37}
    for old in corr.values():                                  # 4, 10, 15, 22, 25, 27, 33: aldri vist
        live = [RAW[n]['claim'] for n in final]
        assert RAW[old]['claim'] in live or RAW[old]['claim'] not in h, old   # L35 beholder L4-påstanden, bare andelen rettes
    for new in final:
        assert RAW[new]['claim'] in h, new
    for n in (4, 22):                                          # AnalBot 09.11: kildens egen prosent, ikke utregnet
        assert RAW[n]['revenue_share'] not in h
    assert '73,3' not in h and '75,3' not in h and '$3,241 mrd' not in h
    assert 'Andel av omsetning 73 % ifølge kilden (FY2024)' in h and 'Andel av omsetning 75 % ifølge kilden (2024)' in h
    assert 'av netto salg 3 241 mill. dollar 2024 (før internsalg)' in h
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
    assert 'Flaskehals · EUV 38,2 % av netto systemsalg 2024' in asml


def test_five_stages_fixed_order_and_two_tracks():
    h = visible(block())
    pos = [h.index(f'{n} · {t}') for n, t in [(1, 'Innsatsvarer og utstyr'), (2, 'Produsenter'),
                                             (3, 'Børsnoterte selskaper i kjeden (ikke testet for avkastning)')]]
    assert pos == sorted(pos)
    # UxBot 09.11: tomme ledd vises ikke – verken i flytlinjen eller trappen
    assert 'Bruksområde' not in h.replace(V.MISSING, '') and 'Berørte industrier og produkter' not in h
    assert block().count('class="vk-stage"') == 2 and block().count('class="vk-stage vk-s5"') == 1 and block().count('<span aria-hidden="true">→</span>') == 2
    assert 'Direkte (1. orden)' in h and 'Leverandører (2. orden)' in h
    assert 'Offentlige kilder · sist kontrollert 09.11.2026' in h
    assert '16 direkte · 1 andre-orden' in h and '8 direkte · 5 andre-orden' in h
    assert 'Innsatsvarer og utstyr · 16 + 1' in h and 'Produsenter · 8 + 5' in h
    assert 'kommer snart' not in h.lower()


def test_stage5_is_stock_table_in_chain_order():
    raw = block()
    s5 = raw[raw.index('id="vk-halvledere-selskaper"'):]
    assert V.STAGE5_HEAD in s5 and V.STAGE5_LINE in s5
    # AnalBot 09.11: overskrift og forbehold rett over tabellen
    assert s5.index(V.STAGE5_HEAD) < s5.index(V.TICKER_HEAD) < s5.index(V.STAGE5_LINE) < s5.index('<table class="sr-t sr-ord">')
    assert V.TICKER_HEAD == 'Data fra ticker-siden, ikke en følge av plassen i kjeden'
    assert re.search(re.escape(V.STAGE5_LINE) + r'</p><table class="sr-t sr-ord">', s5)
    heads = re.findall(r'<th scope="col">(.*?)</th>', s5)
    assert heads == ['Ticker', 'Orden', 'Hovedsignal', '5d / 20d', 'Risiko', 'Flagg', 'Score (rangering, ikke testet)']
    assert '>Alle<' in s5 and '>Oslo<' in s5 and '>USA<' in s5
    oslo = re.findall(r'<tr data-region="oslo"><td class="sr-tk"><b>(?:<a [^>]*>)?(\w+)', s5)
    assert sorted(oslo) == ['NOD', 'REC']
    # AnalBot 09.11: rekkefølgen følger kjeden (første forekomst), ikke score eller avkastning
    order = re.findall(r'<td class="sr-tk"><b>(?:<a [^>]*>)?([\w]+)', s5)
    assert order == [t for (_n, t, *_r) in V.stock_rows(V.load()['links'])]
    assert order[:3] == ['4063', '6488', 'ASML']
    # Air Liquide (Euronext Paris, «AI») lenker aldri til en annen ticker med samme symbol
    ai = re.search(r'<tr data-region="annen"><td class="sr-tk"><b>AI</b>.*?</tr>', s5).group(0)
    assert 'href=' not in ai and 'Ingen data' in ai


def test_chain_lives_in_its_sector_panel():
    h = T.html()
    p = h[h.index('id="sektor-halvledere"'):]
    p = p[:p.index('<section class="tr-panel"', 10)] if '<section class="tr-panel"' in p[10:] else p
    assert 'class="vk"' in p and V.STAGE5_HEAD in p
    for t in T.load()['trends']:
        assert t['title'] in h


def test_mobile_and_desktop_rules_in_css():
    c = V.CSS
    assert 'height:44px' in c and 'height:56px' in c and 'min-height:56px' in c
    assert 'grid-template-columns:1fr 1fr;gap:24px' in c
    assert 'border-left:4px solid' in c and 'border-left:4px dashed' in c
    assert 'background:var(--card)' in c and 'background:' + V.T2_BG in c
    assert 'font-size:13px;line-height:18px;color:var(--mut)' in c
    assert '.vk-sub-name,.vk-sub-n{font-size:14px;line-height:20px;font-weight:600;color:var(--mut)}' in c
    assert '.vk .vk-name{font-size:16px;line-height:24px' in c
    assert 'font-size:14px;line-height:20px;color:var(--mut)' in c
    assert 'min-width:44px;min-height:44px' in c
    m = c[c.index('@media(max-width:600px)'):]
    assert '.vk-flow{display:none}' in m and '.vk-track.vk-empty{display:none}' in m
    assert 'max-height:88px' in m and '.vk-sub>summary{min-height:48px' in m
    assert '.vk .vk-none{font-size:14px;line-height:20px;color:var(--mut);margin:0;max-height:40px' in c
    assert block().count(' open>') == 0   # UxBot 09.11: alle ledd lukket ved lasting


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


# ---- AnalBot 09.11: godkjente tekster
def test_approved_texts():
    h = visible(block())
    assert V.EXPLAIN == ('1. orden: selskapet gjør leddet selv, ifølge kilden. '
                         '2. orden: kilden navngir selskapet som leverandør til et selskap i 1. orden.')
    assert h.count(V.EXPLAIN) == 1
    assert V.MISSING == 'Bruksområder og berørte industrier er ikke med ennå, fordi vi mangler kildebelagte koblinger.'
    raw = block()
    assert raw.index('sist kontrollert 09.11.2026</p><p class="vk-meta vk-missing">' + V.MISSING) > 0
    assert V.EMPTY_DIRECT == 'Ingen dokumentert kobling i kilden'
    assert V.EMPTY_SUPPLIER == 'Ingen dokumentert leverandør i kilden'
    assert 'Fra wafere, gasser og maskiner til brikkeprodusenter og selskapene som er navngitt i kildene.' in h


def test_empty_tracks_use_approved_texts():
    d = V.load()
    links = [l for l in d['links'] if not (l['ui_stage'] == 1 and l['order'] == '2')]
    h = V.html(data={**d, 'links': links})
    assert V.EMPTY_SUPPLIER in h
    only2 = [l for l in d['links'] if not (l['ui_stage'] == 2 and l['order'] == '1')]
    assert V.EMPTY_DIRECT in V.html(data={**d, 'links': only2})


def test_hidden_stages_return_when_log_has_lines():
    d = V.load()
    e3 = {**d['links'][0], 'ui_stage': 3, 'line': 98}
    h = visible(V.html(data={**d, 'links': d['links'] + [e3]}))
    assert '3 · Bruksområde' in h and '4 · Børsnoterte' in h and V.MISSING in h   # ledd 4 mangler fortsatt
    e4 = {**d['links'][0], 'ui_stage': 4, 'line': 99}
    h = visible(V.html(data={**d, 'links': d['links'] + [e3, e4]}))
    assert '4 · Berørte industrier og produkter' in h and '5 · Børsnoterte' in h and V.MISSING not in h


def test_share_texts_have_denominator_year_and_checked_figure():
    d = V.load()
    for l in d['links']:
        sh = l['share']
        if sh == V.NO_SHARE:
            continue
        assert re.search(r'(FY)?20\d\d', sh), sh                     # år
        assert sh.startswith('Andel av omsetning') or sh.startswith('Andel: '), sh
        if sh.startswith('Andel: '):
            assert ' av ' in sh                                      # nevner oppgitt
        figs = re.findall(r'\d+(?:,\d)? %', sh)
        src = l['claim'] + ' ' + RAW[l['line']]['revenue_share']
        for f in figs:
            assert f in src or (l['line'] == 3 and f == '38,2 %'), (l['line'], f)
    shares = {l['line']: l['share'] for l in d['links']}
    assert shares[3] == 'Andel: EUV 38,2 % av netto systemsalg 2024'
    assert shares[37] == 'Andel: Materials 43,2 %; APS 57,1 % av netto salg 3 241 mill. dollar 2024 (før internsalg)'
    assert shares[35] == 'Andel av omsetning 73 % ifølge kilden (FY2024)' and shares[36] == 'Andel av omsetning 75 % ifølge kilden (2024)'
    assert '38 %' not in block()
    for l in d['links']:   # «Andel av omsetning» bare der nevneren er omsetning i kilden
        if l['share'].startswith('Andel av omsetning'):
            # L33 Entegris: nevneren $3,241 mrd er net sales FY2024 (AnalBot: 1 400 + 1 850 − 9 = 3 241)
            assert re.search(r'revenue|net sales|sales|omsetning', l['claim']), l['line']


def _rgb(h):
    h = h.lstrip('#'); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _lum(c):
    c = [x / 255 for x in c]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def css_vars():
    from signaltool import site
    root = re.search(r':root\{color-scheme:dark;([^}]*)\}', site.CSS).group(1)
    return {k: _rgb(v) for k, v in re.findall(r'--([\w-]+):(#[0-9a-fA-F]{6})', root)}


def contrast_table():
    v = css_vars()
    t2 = [round(0.95 * a + 0.05 * b) for a, b in zip(v['card'], v['ink'])]
    surfaces = {'bg': v['bg'], 'card (1. orden)': v['card'], 'card+ink 5 % (2. orden)': t2, 'card2 (valgt chip)': v['card2']}
    return {(f, s): _ratio(v[f], c) for s, c in surfaces.items() for f in ('ink', 'mut', 'acc')}, v, t2


def test_contrast_at_least_4_5_and_no_new_hex():
    table, v, t2 = contrast_table()
    for k, r in table.items():
        assert r >= 4.5, (k, round(r, 2))
    # +4 % lyshet (HSL) for 2. orden
    def L(c): return (max(c) + min(c)) / 2 / 255 * 100
    assert 3.5 <= L(t2) - L(v['card']) <= 4.5
    assert not re.findall(r'#[0-9a-fA-F]{3,8}\b', V.CSS)
    assert not re.search(r'(?<![\w-])(white|black|rgb\(|rgba\(|hsl\()(?![\w-])', V.CSS)
