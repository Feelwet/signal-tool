"""Trender som sektoroversikt + felles aksjerad (bruker/UxBot/AnalBot 09.11)."""
import re
from pathlib import Path
from signaltool import trender as T, stockrow as SR, verdikjeder as V, overview as OV


def snap():
    return {
        'date': '2026-11-08',
        'tickers': [
            {'ticker': 'TSM', 'name': 'TSMC', 'score': 3.3, 'points': {'unusual_volume': 2.0},
             'stats': {'ret_5d': -0.076, 'ret_20d': -0.172, 'last_date': '2026-11-06'}, '_risk': {'level': 'Middels'}},
            {'ticker': 'MU', 'name': 'Micron', 'score': 9.9, 'points': {'price_move': 1.0},
             'stats': {'ret_5d': 0.0004, 'ret_20d': None, 'last_date': '2026-11-06'}, '_risk': {'level': 'Lav'}},
            {'ticker': 'NVDA', 'name': 'NVIDIA', 'score': 1.0, 'points': {'price_move': 1.0},
             'stats': {'ret_5d': 0.021, 'ret_20d': 0.05}, '_risk': {'level': 'Høy'}},   # ingen kursdato
        ],
        'oslo_universe_flags': [
            {'ticker': 'NOD.OL', 'flags': {}},
            {'ticker': 'REC.OL', 'flags': {'weak_px': 'x', 'high_vol': 'y'}},
        ],
    }


def page(s=None):
    s = snap() if s is None else s
    return T.html(available_tickers={e['ticker'] for e in s['tickers']}, snap=s)


def visible(h):
    h = re.sub(r'<style.*?</style>|<script.*?</script>', '', h, flags=re.S)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h))


def test_sector_cards_first_under_intro_all_closed():
    h = page()
    assert h.index('</header>') < h.index('<div class="tr-secgrid"') < h.index('class="tr-panel"')
    cards = re.findall(r'<button type="button" class="tr-sec" id="kort-([\w-]+)" aria-expanded="false" aria-controls="sektor-([\w-]+)">', h)
    ids = ['halvledere'] + [t['id'] for t in T.load()['trends']]
    assert [c for c, _ in cards] == ids and [p for _, p in cards] == ids
    assert h.count('class="tr-tag">Verdikjede<') == 1 and h.index('class="tr-tag">Verdikjede<') < h.index('id="kort-magneter"')
    for sid in ids:
        p = h[h.index(f'id="sektor-{sid}"'):]
        p = p[:p.find('</section><section class="tr-panel"') if '</section><section class="tr-panel"' in p else len(p)]
        assert '<button type="button" class="tr-close">Lukk</button>' in p and f'href="#sektor-{sid}"' in p
    js = T.SECTOR_JS
    assert 'P.forEach(p=>p.hidden=true)' in js and "get('sektor')" in js and 'aria-expanded' in js
    assert 'set(cur===i?-1:i,true)' in js     # samme kort igjen lukker; ett åpent om gangen
    assert 'class="tr-tabs"' not in h


def test_existing_trend_content_and_caveats_kept_behind_sector():
    h = page()
    for t in T.load()['trends']:
        p = h[h.index(f'id="sektor-{t["id"]}"'):]
        assert p.index(f'<article class="tr-card" id="{t["id"]}">') < p.index('</article>')
        assert t['title'] in p
    v = visible(h)
    for x in ('Ikke testet for tidlighet', 'Mangelstatus: Mangler data', 'Hva svekker bildet?', 'avkastningsmåling er ikke startet',
              'Eksponert for trenden (ikke testet for avkastning)', V.STAGE5_LINE, V.MISSING, V.EXPLAIN, 'sist kontrollert 09.11.2026'):
        assert x in v, x


def test_sector_status_states_population_and_vetoed_form_absent():
    h = page()
    st = re.findall(r'<span class="tr-sec-st">(.*?)</span>', h)
    pat = r'^\d+ aksjer? · (\d+ Oslo sjekket · \d+ med røde flagg|ingen sjekket for røde flagg)$'
    assert all(re.match(pat, x) for x in st), st
    # AnalBot 09.11: flagg telles bare blant sjekkede Oslo-aksjer (NOD 0, REC 2 -> 1 med røde flagg)
    assert st[0] == '24 aksjer · 2 Oslo sjekket · 1 med røde flagg'
    assert st[1] == '1 aksje · ingen sjekket for røde flagg' and st[3] == '0 aksjer · ingen sjekket for røde flagg'
    assert 'med rødt flagg' not in h and 'børsnotert med data' not in h   # vetoet / erstattet form (AnalBot 09.11)


def rows_by_ticker(h):
    return {re.search(r'<b>(?:<a [^>]*>)?([\w]+)', r).group(1): r for r in re.findall(r'<tr data-region="\w+">.*?</tr>', h)}


def test_stock_row_values_from_snapshot_only():
    h = page()
    rows = rows_by_ticker(h)
    tsm = rows['TSM']
    assert 'href="ticker/TSM.html"' in tsm
    # alle med kursdato deler 06.11 -> datoen står i kolonneoverskriften, ikke ved verdien
    assert '<th scope="col">5d / 20d (per 06.11)</th>' in h and '<p class="sr-kurs">Kurs per 06.11</p>' in h
    assert '<span class="sr-ret rdn">5d −7,6 %</span> <span class="sr-ret rdn">20d −17,2 %</span>' in tsm
    assert 'rk rk-middels rk-s">Middels' in tsm and 'Score 3,3 · ikke testet' in tsm
    assert OV._main_signal(snap()['tickers'][0]) in tsm          # samme etikett som tickersiden
    assert '<span class="sr-fl fl-na">ikke sjekket</span>' in tsm and '✔' not in tsm
    mu = rows['MU']
    assert '<span class="sr-ret r0">5d 0,0 %</span>' in mu and '<span class="sr-ret r0">20d –</span>' in mu   # 0 grå, mangler «–», aldri 0
    nv = rows['NVDA']
    assert '<span class="sr-ret r0">5d –</span>' in nv           # uten kursdato vises ikke tall
    # «Ingen data» grå over hele raden; sjekket Oslo-flagg vises likevel (ekte data)
    assert '<td class="sr-miss" colspan="5"><span class="sr-na">Ingen data</span> · <span class="sr-fl fl-ok">✔ 0</span></td>' in rows['NOD']
    assert '<span class="sr-fl fl-red">⚑ 2</span>' in rows['REC']
    assert '<td class="sr-miss" colspan="5"><span class="sr-na">Ingen data</span></td>' in rows['AI'] and 'ikke sjekket' not in rows['AI']
    for r in rows.values():
        assert '<td></td>' not in r and '<td class="sr-sc"></td>' not in r   # aldri tomme felt
    assert 'Ikke i datasettet' not in h
    assert '<p class="sr-rkline">Testet for kurssvingninger, ikke avkastning</p>' in h
    assert '.sr-note,.sr-rkline,.sr-kurs{font-size:13px;line-height:18px;color:var(--mut)' in SR.CSS


def test_older_price_date_shown_next_to_value():
    # AnalBot 09.11: overskriftsdato bare når alle deler den; eldre kursdato står ved verdien
    s = snap()
    s['tickers'][1]['stats']['last_date'] = '2026-11-05'
    s['tickers'][1]['stats']['ret_20d'] = -0.031
    h = page(s)
    rows = rows_by_ticker(h)
    assert '<th scope="col">5d / 20d (per 06.11)</th>' in h
    assert '<span class="sr-ret rdn">20d −3,1 % <span class="sr-per">(per 05.11)</span></span>' in rows['MU']
    assert '(per' not in rows['TSM']
    assert SR.panel_date([('X', 'X', 'NONE', None)], s) is None
    assert '<th scope="col">5d / 20d</th>' in SR.table([('X', 'X', 'NONE', None)], s) and 'sr-kurs' not in SR.date_line([('X', 'X', 'NONE', None)], s)


def test_sector_cards_layout_rules():
    c = T.SECTOR_CSS
    assert 'min-height:80px' in c and '.tr-sec{min-height:88px}' in c
    assert '.tr-secgrid{grid-template-columns:minmax(0,1fr)}' in c     # 390: én kolonne
    assert '.tr-sec-st{font-size:13px;line-height:18px;color:var(--mut);max-height:36px' in c   # maks 2 linjer


def test_rows_not_sorted_by_score_or_return():
    h = page()
    order = re.findall(r'<td class="sr-tk"><b>(?:<a [^>]*>)?([\w]+)', h.split('id="sektor-magneter"')[0])
    assert order.index('TSM') < order.index('MU') < order.index('NVDA')   # kjedens rekkefølge; MU har høyest score


def test_unlisted_and_format_helpers():
    assert SR.pct(-0.031) == '−3,1 %' and SR.pct(0.021) == '+2,1 %' and SR.pct(0.0) == '0,0 %'
    assert SR.ret('20d', -0.031, '2026-11-08') == '<span class="sr-ret rdn">20d −3,1 % <span class="sr-per">(per 08.11)</span></span>'
    assert SR.ret('5d', None, '2026-11-08') == '<span class="sr-ret r0">5d –</span>'
    t = SR.table([('Unotert AS', None, None, None)], {})
    assert 'Ikke børsnotert' in t and 'href' not in t
    assert T.trend_row({'name': 'MP Materials', 'ticker': 'NYSE: MP'}) == ('MP Materials', 'MP', 'MP', None)
    assert T.trend_row({'name': 'X', 'ticker': 'OSE: NHY'})[2] == 'NHY.OL'
    assert T.trend_row({'name': 'Y', 'ticker': 'TSE: 4063'})[2] is None
    assert 'Testet for kurssvingninger, ikke avkastning' in t   # risikolinjen beholdes (AnalBot)


def test_colour_rules_green_only_for_returns():
    assert SR.CSS.count('var(--up)') == 1 and '.rup{color:var(--up)}' in SR.CSS
    assert OV.CSS.count('var(--up)') == 1 and '.ov-ct .ov-ret.tup{color:var(--up)}' in OV.CSS
    assert '#56d364' not in OV.CSS.split('CATS')[0]
    src = Path('signaltool/site_risk.py').read_text()
    assert '#DCFCE7' not in src and '#166534' not in src      # Lav aldri grønn (UxBot 09.11)
    assert '.ov-dot.up{background:var(--mut)}' in OV.CSS        # markedsstatus fortsatt grå
    assert '.fl-red{color:var(--down);border:1px solid var(--down)' in SR.CSS
    assert not re.findall(r'#[0-9a-fA-F]{3,8}\b', SR.CSS + T.SECTOR_CSS)
    assert 'FLAG' not in page()


def test_forbidden_words_absent_on_whole_trender_page():
    low = visible(page()).lower()
    for w in V.FORBIDDEN:
        assert w.lower() not in low, w


def test_stockrow_only_used_by_trender_pages():
    users = sorted(p.name for p in Path('signaltool').rglob('*.py')
                   if re.search(r'stockrow', p.read_text(errors='ignore')) and p.name != 'stockrow.py')
    assert users == ['trender.py', 'verdikjeder.py']
    s = snap(); before = repr(s)
    page(s)
    assert repr(s) == before                                    # bygging endrer aldri snapshot (score/kategori)


def _rgb(h):
    h = h.lstrip('#'); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _lum(c):
    c = [x / 255 for x in c]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def test_return_and_flag_colours_contrast():
    from signaltool import site
    root = re.search(r':root\{color-scheme:dark;([^}]*)\}', site.CSS).group(1)
    v = {k: _rgb(x) for k, x in re.findall(r'--([\w-]+):(#[0-9a-fA-F]{6})', root)}
    for fg in ('up', 'down', 'mut', 'ink', 'acc'):
        for bg in ('bg', 'card', 'pill'):
            la, lb = sorted((_lum(v[fg]), _lum(v[bg])), reverse=True)
            assert (la + 0.05) / (lb + 0.05) >= 4.5, (fg, bg)
