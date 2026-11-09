"""Kurs bare for visning på Trender (bruker/AnalBot 09.11 runde 2) + nye statuslinjer, nøytralt Kjøp-merke, døde faner fjernet."""
import json, re
from pathlib import Path
import pandas as pd
import pytest
from signaltool import displayprices as DP, stockrow as SR, trender as T, verdikjeder as V, site

SNAP = Path(__file__).resolve().parent.parent / "site" / "data.json"
DISP = {"4063.T": {"last_date": "2026-11-09", "ret_5d": -0.088, "ret_20d": -0.1111},
        "AMAT": {"last_date": "2026-11-06", "ret_5d": -0.1471, "ret_20d": -0.3438},
        "MP": {"last_date": "2026-11-06", "ret_5d": -0.105, "ret_20d": 0.0},
        "NOD.OL": {"last_date": "2026-11-09", "ret_5d": -0.018, "ret_20d": 0.012}}


def snap():
    return {'date': '2026-11-08',
            'tickers': [{'ticker': 'TSM', 'name': 'TSMC', 'score': 3.3, 'points': {'unusual_volume': 2.0},
                         'stats': {'ret_5d': -0.076, 'ret_20d': -0.172, 'last_date': '2026-11-06'}, '_risk': {'level': 'Middels'}}],
            'oslo_universe_flags': [{'ticker': 'NOD.OL', 'flags': {}}]}


def page(s=None, disp=None):
    s = snap() if s is None else s
    return T.html(available_tickers={e['ticker'] for e in s['tickers']}, snap=s, disp=disp)


def rows(h):
    return {re.search(r'<b>(?:<a [^>]*>)?(\w+)', r).group(1): r for r in re.findall(r'<tr[^>]*>(?:(?!</tr>).)*sr-tk.*?</tr>', h)}


def test_yahoo_symbols_for_listings():
    assert DP.yahoo_symbol('4063', 'TSE') == '4063.T' and DP.yahoo_symbol('6488', 'TPEx') == '6488.TWO'
    assert DP.yahoo_symbol('005930', 'KRX') == '005930.KS' and DP.yahoo_symbol('AI', 'Euronext Paris') == 'AI.PA'
    assert DP.yahoo_symbol('ASML', 'NASDAQ/Euronext') == 'ASML' and DP.yahoo_symbol('NOD', 'Oslo Børs') == 'NOD.OL'
    assert DP.yahoo_symbol('X', 'Ukjent børs') is None and DP.yahoo_symbol(None, 'NASDAQ') is None
    w = DP.wanted()
    for s in ('4063.T', '6488.TWO', '005930.KS', 'AI.PA', 'ASML', 'NOD.OL', 'REC.OL', 'MP', 'CLF'):
        assert s in w, s
    assert len(w) == len(set(w))


def test_stats_same_definition_as_ticker_pages():
    from signaltool.collectors import markets
    idx = pd.bdate_range('2026-08-01', periods=40)
    c = pd.Series([100 + i + (i % 3) for i in range(40)], index=idx, dtype=float)
    st = DP.stats(c)
    ref = markets.ticker_stats(pd.DataFrame({'Close': c, 'Volume': 1000.0}))
    assert st['last_date'] == ref['last_date'] == str(idx[-1].date())
    assert st['ret_5d'] == round(ref['ret_5d'], 4) and st['ret_20d'] == round(ref['ret_20d'], 4)
    assert DP.stats(c.iloc[:20]) is None    # for kort historikk -> «Ingen data», aldri et anslag


def test_refresh_keeps_previous_file_on_failure(tmp_path, monkeypatch):
    p = tmp_path / 'display_prices.json'
    p.write_text(json.dumps({'prices': DISP}))
    monkeypatch.setattr(DP, 'path', lambda: p)
    monkeypatch.setattr(DP, 'fetch', lambda syms: (_ for _ in ()).throw(RuntimeError('nett nede')))
    assert DP.refresh().startswith('FAILED') and DP.load(p) == DISP
    monkeypatch.setattr(DP, 'fetch', lambda syms: {})
    assert DP.refresh().startswith('FAILED') and DP.load(p) == DISP
    monkeypatch.setattr(DP, 'fetch', lambda syms: {'MP': DISP['MP']})
    assert DP.refresh().startswith('ok (1/') and DP.load(p) == {'MP': DISP['MP']}
    assert DP.load(tmp_path / 'mangler.json') == {}


def test_display_rows_values_own_dates_and_missing():
    h = page(disp=DISP)
    r = rows(h)
    # panelets dato = nyeste kursdato (09.11, Tokyo); eldre kurser får egen dato (AnalBot 09.11)
    assert '5d / 20d (per 09.11)' in h and '<p class="sr-kurs">Kurs per 09.11</p>' in h
    assert 'Bare kurs' in r['4063'] and '5d −8,8 %' in r['4063'] and '(per' not in r['4063']
    assert '20d −34,4 % <span class="sr-per">(per 06.11)</span>' in r['AMAT'] and 'Score' not in r['AMAT']
    assert 'Uvanlig volum' in r['TSM'] and '(per 06.11)' in r['TSM']          # snapshot vinner over visningsdata
    assert 'Ingen data' in r['REC'] and 'Bare kurs' not in r['REC']          # kilden har ikke REC.OL
    assert 'fl-ok">✔ 0' in r['NOD'] and 'Bare kurs' in r['NOD']              # flagg fra snapshot, kurs fra visningsfila
    assert 'ikke sjekket' in r['AMAT'] and 'fl-ok' not in r['AMAT']
    assert h.count(SR.DISPLAY_NOTE.split(':')[0]) >= 1 and 'sr-dpnote' in h
    assert 'rup' not in r['4063'] and 'r0">20d 0,0 %' in rows(h)['MP']          # 0 er grått, aldri grønt


def test_sector_status_lines_with_price_population():
    st = re.findall(r'<span class="tr-sec-st">(.*?)</span>', page(disp=DISP))
    assert st[0] == '24 selskaper · 4 med kursdata · 2 Oslo, 1 sjekket for røde flagg · 0 med røde flagg'
    assert st[1] == '1 selskap · 1 med kursdata · ingen sjekket for røde flagg'
    assert st[2] == '1 selskap · 0 med kursdata · ingen sjekket for røde flagg'
    assert st[3] == '0 selskaper · 0 med kursdata · ingen sjekket for røde flagg'
    s = snap(); s['oslo_universe_flags'] = []
    assert re.findall(r'tr-sec-st">(.*?)</span>', page(s))[0] == '24 selskaper · 1 med kursdata · 2 Oslo, ingen sjekket for røde flagg'


def test_trend_panels_use_full_ticker_heading():
    h = page(disp=DISP)
    for t in T.load()['trends']:
        p = h[h.index(f'id="sektor-{t["id"]}"'):]
        p = p[:p.index('</article>')]
        if t['companies']:
            assert f'<h3>{V.TICKER_HEAD}</h3>' in p
    assert '<h3>Data fra ticker-siden</h3>' not in h and h.count(V.TICKER_HEAD) == 1 + sum(1 for t in T.load()['trends'] if t['companies'])


def test_kjop_badge_neutral_green_only_for_returns():
    rule = re.search(r'\.cat\.kjop\{[^}]*\}', site.CSS).group(0)
    assert rule == '.cat.kjop{color:var(--ink);background:var(--pill);border-color:var(--line)}'
    for g in ('#56d364', 'var(--up)', '86,211,100', '74,194,107'):
        assert g not in rule


def test_dead_tab_code_removed():
    assert 'tr-tabs' not in T.CSS and not hasattr(T, 'JS') and 'tr-tabs' not in Path('signaltool/trender.py').read_text()


def test_pipeline_wiring_refreshes_display_prices():
    assert 'DP.refresh()' in Path('signaltool/verden.py').read_text()     # timesjobben
    cli = Path('signaltool/cli.py').read_text()
    assert cli.index('DP.refresh()') < cli.index('site.build(snap)')       # nattjobben, etter at snapshotet er skrevet
    assert 'DP.load()' in Path('signaltool/site.py').read_text()


def test_display_prices_never_enter_snapshot():
    s = snap(); before = repr(s)
    page(s, DISP)
    assert repr(s) == before and not any(e['ticker'] in DISP for e in s['tickers'] if e['ticker'] != 'TSM')


@pytest.mark.skipif(not SNAP.exists(), reason="no snapshot available")
def test_site_byte_identical_with_and_without_display_prices(tmp_path, monkeypatch):
    """Kandidatutvalg, score, Kjøp, Signal-boka, kategorier og GS-indeks: alle filer unntatt trender.html er like byte for byte."""
    from signaltool import risk, site_layout as L
    base = json.loads(SNAP.read_text())
    memo = {}
    real = risk.refresh
    monkeypatch.setattr(risk, 'refresh', lambda t, *a, **k: memo.setdefault('r', real(t, *a, **k)))   # samme risikotall i begge byggene
    dp = tmp_path / 'display_prices.json'
    dp.write_text(json.dumps({'prices': {s: DISP['AMAT'] for s in DP.wanted()}}))
    snaps = {}
    for nm, path in (('uten', tmp_path / 'finnes_ikke.json'), ('med', dp)):
        monkeypatch.setattr(DP, 'path', lambda path=path: path)
        monkeypatch.setattr(site, 'SITE', tmp_path / nm)
        L._TIPN[0] = 0
        s = json.loads(json.dumps(base))
        site.build(s)
        snaps[nm] = json.dumps(s, sort_keys=True, default=str)
    a, b = tmp_path / 'uten', tmp_path / 'med'
    fa = sorted(str(p.relative_to(a)) for p in a.rglob('*') if p.is_file())
    assert fa == sorted(str(p.relative_to(b)) for p in b.rglob('*') if p.is_file())
    diff = [f for f in fa if (a / f).read_bytes() != (b / f).read_bytes()]
    assert diff == ['trender.html'], diff
    assert snaps['uten'] == snaps['med']
    for f in ('index.html', 'portefolje.html', 'tickere.html', 'data.json'):
        if (a / f).exists():
            assert (a / f).read_bytes() == (b / f).read_bytes(), f
