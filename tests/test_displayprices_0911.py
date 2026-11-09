"""Kurs bare for visning på Trender (bruker/AnalBot 09.11 runde 2) + nye statuslinjer, nøytralt Kjøp-merke, døde faner fjernet."""
import json, re
from pathlib import Path
import pandas as pd
from html import escape as E
from datetime import datetime, timezone
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
    for s in ('4063.T', '6488.TWO', '005930.KS', 'AI.PA', 'ASML', 'NOD.OL', 'MP', 'CLF'):
        assert s in w, s
    assert 'REC.OL' not in w                     # strøket 25.06.2026 (AnalBot 09.11)
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
    assert 'Ikke i signalutvalget' in r['4063'] and 'Bare kurs' not in h and '5d −8,8 %' in r['4063'] and '(per' not in r['4063']
    assert '20d −34,4 % <span class="sr-per">(per 06.11)</span>' in r['AMAT'] and 'Score' not in r['AMAT']
    assert 'Uvanlig volum' in r['TSM'] and '(per 06.11)' in r['TSM']          # snapshot vinner over visningsdata
    assert 'REC' not in r and '<span class="sr-na">Ikke børsnotert (strøket fra Oslo Børs 25.06.2026)</span>' in h
    assert 'fl-ok">✔ 0' in r['NOD'] and 'Ikke i signalutvalget' in r['NOD']   # flagg fra snapshot, kurs fra visningsfila
    assert 'ikke sjekket' in r['AMAT'] and 'fl-ok' not in r['AMAT']
    assert SR.DISPLAY_NOTE.startswith('Ikke i signalutvalget: ') and E(SR.DISPLAY_NOTE) in h and 'sr-dpnote' in h
    assert 'rup' not in r['4063'] and 'r0">20d 0,0 %' in rows(h)['MP']          # 0 er grått, aldri grønt


def test_sector_status_lines_with_price_population():
    st = re.findall(r'<span class="tr-sec-st">(.*?)</span>', page(disp=DISP))
    assert st[0] == '24 selskaper · 4 med kursdata · 1 Oslo, 1 sjekket for røde flagg · 0 med røde flagg'
    assert st[1] == '1 selskap · 1 med kursdata · ingen sjekket for røde flagg'
    assert st[2] == '1 selskap · 0 med kursdata · ingen sjekket for røde flagg'
    assert st[3] == '0 selskaper · 0 med kursdata · ingen sjekket for røde flagg'
    s = snap(); s['oslo_universe_flags'] = []
    assert re.findall(r'tr-sec-st">(.*?)</span>', page(s))[0] == '24 selskaper · 1 med kursdata · 1 Oslo, ingen sjekket for røde flagg'


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


FULL = {s: {"last_date": "2026-11-06", "ret_5d": -0.01, "ret_20d": -0.02} for s in DP.wanted()}


def test_price_hold_list_in_config_with_reason():
    from signaltool.config import PRICE_HOLD
    assert set(PRICE_HOLD) == {'6488.TWO', '4062.T', 'INTC', 'TER'}
    assert all(isinstance(v, str) and len(v) > 10 for v in PRICE_HOLD.values())
    h = page(disp=FULL)
    r = rows(h)
    for tk in ('6488', '4062', 'INTC', 'TER'):
        assert SR.HOLD_RT in r[tk] and '%' not in r[tk].split('sr-rt')[1].split('</td>')[0], tk
        assert 'Ikke i signalutvalget' in r[tk]                       # resten av raden som vanlig
    assert '<span class="sr-hold">kurs under kontroll</span>' in SR.HOLD_RT
    assert '.sr-hold{font-size:13px;line-height:18px;color:var(--mut)' in SR.CSS


def test_coverage_line_and_status_match():
    h = page(disp=FULL)
    cov = re.findall(r'<p class="sr-cov">(.*?)</p>', h)
    assert cov[0] == 'Kursdata vises for 19 av 24 · 4 under kontroll · 1 ikke børsnotert'
    assert cov[1:] == ['Kursdata vises for 1 av 1', 'Kursdata vises for 1 av 1']   # nulldeler utelates; grafitt har ingen tabell
    st = re.findall(r'tr-sec-st">(.*?)</span>', h)
    assert st[0] == '24 selskaper · 19 med kursdata · 1 Oslo, 1 sjekket for røde flagg · 0 med røde flagg'
    for c, s_ in zip(cov, st):                                           # samme tall, ingen motsigelse (AnalBot 09.11)
        assert re.search(r'vises for (\d+) av (\d+)', c).groups() == re.search(r'^(\d+) selskap(?:er)? · (\d+)', s_).groups()[::-1]
    s5 = h[h.index('id="vk-halvledere-selskaper"'):]
    assert s5.index(V.TICKER_HEAD) < s5.index('class="sr-cov"') < s5.index(V.STAGE5_LINE) < s5.index('<table')   # forbeholdet rett over tabellen
    assert '.sr-cov{font-size:13px;line-height:18px;color:var(--mut)' in SR.CSS


def test_compact_rows_for_no_data_and_delisted():
    h = page(disp=FULL)
    comp = re.findall(r'<tr class="sr-0"[^>]*>(.*?)</tr>', h)
    assert len(comp) == 1 and 'colspan="7"' in comp[0] and comp[0].count('<td') == 1
    assert 'REC Silicon' in comp[0] and 'Ikke børsnotert (strøket fra Oslo Børs 25.06.2026)' in comp[0]
    assert re.search(r'\.sr-t tr\.sr-0 td\{height:32px', SR.CSS) and 'tr.sr-0{display:block;padding:0}' in SR.CSS   # UxBot 09.11: brytes, inntil 52 px
    order = re.findall(r'<td class="sr-(?:tk|miss)"[^>]*>(?:<b>(?:<a [^>]*>)?(\w+)(?:</a>)?</b>)?(?: ?<span class="sr-nm">([^<]*))?',
                       h[h.index('id="vk-halvledere-selskaper"'):h.index('id="sektor-magneter"')])
    assert [n for _t, n in order] == [r[0] for r in V.stock_rows(V.load()['links'])]   # kjedens rekkefølge beholdt


def test_rec_correction_line_append_only():
    raw = [json.loads(l) for l in Path('site_config/verdikjeder/halvledere_links.jsonl').read_text().splitlines()]
    last = raw[-1]
    assert last['corrects_line'] == 9 and raw[8]['company'] == last['company'] == 'REC Silicon' and raw[8]['exchange'] == 'Oslo Børs'
    assert last['listed'] is False and last['delisted'] == '2026-06-25' and last['correction_reason']
    assert last['delisting_source'] == 'https://live.euronext.com/en/products/equities/company-news/2026-06-23-rec-silicon-asa-delisting'
    rec = [r for r in V.stock_rows(V.load()['links']) if r[0] == 'REC Silicon'][0]
    assert rec[1] is None and rec[2] is None and rec[4] == 'strøket' and rec[6] == 'Ikke børsnotert (strøket fra Oslo Børs 25.06.2026)'


def test_closing_prices_only():
    idx = pd.to_datetime(['2026-11-05', '2026-11-06', '2026-11-09'])
    df = pd.DataFrame({'Close': [1.0, 2.0, 3.0]}, index=idx)
    at = lambda h, m: datetime(2026, 11, 9, h, m, tzinfo=timezone.utc)
    assert len(DP.completed(df, 'NOD.OL', at(11, 0))) == 2          # Oslo 12:00 lokal: dagen ikke avsluttet
    assert len(DP.completed(df, 'NOD.OL', at(16, 0))) == 3          # 17:00 lokal: avsluttet
    assert len(DP.completed(df, '4063.T', at(11, 0))) == 3          # Tokyo 20:00 lokal
    assert len(DP.completed(df, '4063.T', at(5, 0))) == 2           # Tokyo 14:00 lokal
    assert len(DP.completed(df, 'AI.PA', at(16, 0))) == 2           # Paris 17:00 < 17:35 + slingring
    assert len(DP.completed(df, 'MP', at(20, 0))) == 2              # New York 15:00 lokal
    assert len(DP.completed(df, 'X.ZZ', at(23, 0))) == 2            # ukjent børs: dagens bar droppes
    assert len(DP.completed(df.iloc[:2], 'NOD.OL', at(11, 0))) == 2  # gårsdagens bar beholdes


def test_status_fits_two_lines_at_390():
    # 390: kort 390 − 2×16 (main) − 2×12 (padding) − 2 (kant) = 332 px; 13 px tekst ≈ 7,2 px/tegn -> ~46 tegn per linje
    per_line = 332 // 7.2
    worst = '24 selskaper · 24 med kursdata · 12 Oslo, 12 sjekket for røde flagg · 12 med røde flagg'
    st = re.findall(r'tr-sec-st">(.*?)</span>', page(disp=FULL))
    assert all(len(x) <= 2 * per_line for x in st + [worst]), [len(x) for x in st]
    assert '.tr-secgrid{grid-template-columns:minmax(0,1fr);gap:8px}' in T.SECTOR_CSS


def test_trend_meta_line_moved_into_trend_panels():
    h = page(disp=FULL)
    meta = re.findall(r'<p class="tr-pmeta">(Innhold kontrollert [^<]*)</p>', h)
    assert len(meta) == len(T.load()['trends']) == 3
    assert h.count('Innhold kontrollert') == 3
    hv = h[h.index('id="sektor-halvledere"'):h.index('id="sektor-magneter"')]
    assert 'Innhold kontrollert' not in hv and 'sist kontrollert 09.11.2026' in hv
    for t in T.load()['trends']:
        p = h[h.index(f'id="sektor-{t["id"]}"'):]
        assert p.index('class="tr-close"') < p.index('class="tr-pmeta"') < p.index('</section>')   # øverst i panelet
    tail = h[h.rindex('</section>'):]
    assert 'Innhold kontrollert' not in tail and 'class="tr-meta">Innhold' not in h
    assert 'p.tr-pmeta{font-size:13px;line-height:18px;color:var(--mut)' in T.SECTOR_CSS


def test_risk_badges_like_flag_badge_no_light_hex():
    from signaltool import site_risk as RK
    assert '.rk-hoy{background:transparent;color:var(--down);border:1px solid var(--down)}' in RK.CSS
    assert '.rk-middels{background:transparent;color:var(--warn);border:1px solid var(--warn)}' in RK.CSS
    assert '.rk-lav{background:transparent;color:var(--mut);border:1px solid var(--line)}' in RK.CSS
    for hx in ('#FEF3C7', '#92400E', '#FEE2E2', '#991B1B'):
        assert hx not in RK.CSS


def test_insider_and_donut_neutral():
    from signaltool import site_extra as X
    css = X.CSS_EXTRA
    assert '.kind{font-size:.78rem;font-weight:700;padding:1px 7px;border-radius:6px;border:1px solid var(--line);color:var(--mut)}' in css
    assert '.kind.kjøp' not in css and '.kind.salg' not in css
    assert X.KIND_WORD == {'kjøp': 'Innsidekjøp', 'salg': 'Innsidesalg'}
    src = Path('signaltool/site_extra.py').read_text()
    m = re.search(r'colors = \{"kjop": "(#\w+)", "hold": "(#\w+)", "watch": "(#\w+)"\}', src)
    assert m and '#56d364' not in m.group(0) and m.group(2) == '#58a6ff'
    for g in (m.group(1), m.group(3)):                                    # gråtoner: r = g = b-ish
        r_, g_, b_ = (int(g[i:i + 2], 16) for i in (1, 3, 5))
        assert max(r_, g_, b_) - min(r_, g_, b_) <= 24
