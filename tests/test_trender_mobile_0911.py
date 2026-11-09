"""Oppfølging 09.11 (bruker/AnalBot/UxBot): REC-note i kjedelista, felles telling, offisielle handelstider, nytt forsøk per
symbol, mobilrader uten avkutting, Oslo-filter, kortavstand og trykkflate for ↗ på Oversikt."""
import re
from pathlib import Path
import pandas as pd
from signaltool import displayprices as DP, stockrow as SR, trender as T, verdikjeder as V, overview as OV

FULL = {s: {"last_date": "2026-11-06", "ret_5d": -0.01, "ret_20d": -0.02} for s in DP.wanted()}
REC_TXT = 'Ikke børsnotert (strøket fra Oslo Børs 25.06.2026)'


def snap():
    return {'date': '2026-11-08', 'tickers': [], 'oslo_universe_flags': [{'ticker': 'NOD.OL', 'flags': {}}]}


def page(disp=FULL):
    return T.html(available_tickers=set(), snap=snap(), disp=disp)


def test_rec_note_own_line_below_name_in_chain_list():
    h = V.html(snap=snap(), disp=FULL)
    li = [x for x in re.findall(r'<li class="vk-el" data-line="\d+">.*?</li>', h, re.S) if 'REC Silicon' in x]
    assert li, 'REC mangler i kjedelista'
    for x in li:
        assert f'<p class="vk-name">REC Silicon</p><p class="vk-gone">{REC_TXT}</p>' in x   # egen linje under navnet
        assert 'REC Silicon · REC' not in x and 'Se ticker' not in x and 'ticker/REC' not in x
    assert '.vk .vk-gone{font-size:13px;line-height:18px;margin:0;color:var(--mut);white-space:normal}' in V.CSS


def test_status_and_table_line_share_one_count():
    src = Path('signaltool/stockrow.py').read_text()
    for fn in ('def status(', 'def cov_line('):
        body = src[src.index(fn):].split('\ndef ', 1)[0]
        assert 'counts(rows, snap, disp)' in body and 'shown(' not in body, fn
    d = {k: v for k, v in FULL.items() if k != 'AMAT'}         # AMAT uteblir fra kilden
    h = page(d)
    assert re.findall(r'<p class="sr-cov">(.*?)</p>', h)[0] == 'Kursdata vises for 18 av 24 · 4 under kontroll · 1 ikke børsnotert'
    assert re.findall(r'tr-sec-st">(.*?)</span>', h)[0] == '24 selskaper · 18 med kursdata · 1 Oslo, 1 sjekket for røde flagg · 0 med røde flagg'
    assert 'AMAT' in h and '<span class="sr-na">Ingen data</span>' in h
    assert SR.counts(V.stock_rows(V.load()['links']), snap(), d) == {'n': 24, 'k': 18, 'h': 4, 'u': 1}


def test_official_trading_hours_links_next_to_close_table():
    src = Path('signaltool/displayprices.py').read_text()
    block = src[:src.index('CLOSE = {')]
    for u in ('https://www.jpx.co.jp/english/equities/trading/domestic/01.html',
              'https://www.twse.com.tw/en/products/system/trading.html',
              'https://www.tpex.org.tw/en-us/mainboard/trading/rules/system.html',
              'https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf',
              'https://www.euronext.com/en/trading/trading-hours-holidays',
              'https://www.nyse.com/trade/hours-calendars'):
        assert u in block, u


def _df(n=40):
    idx = pd.bdate_range('2026-09-01', periods=n)
    return pd.DataFrame({'Close': [100.0 + i for i in range(n)], 'Volume': 1.0}, index=idx)


def test_per_symbol_retry_then_honest_missing(monkeypatch):
    import yfinance as yf
    from signaltool import http
    batch = pd.concat({'AAA': _df(), 'BBB': _df().assign(Close=float('nan'))}, axis=1)
    monkeypatch.setattr(http, 'yf_download', lambda *a, **k: batch)
    calls, sleeps = [], []
    monkeypatch.setattr('time.sleep', lambda s: sleeps.append(s))
    # BBB: tom første gang, data andre gang
    seq = iter([pd.DataFrame(), pd.concat({'BBB': _df()}, axis=1)])
    monkeypatch.setattr(yf, 'download', lambda s, **k: (calls.append(s), next(seq))[1])
    now = pd.Timestamp('2026-11-09 23:00', tz='UTC').to_pydatetime()
    out = DP.fetch(['AAA', 'BBB'], now=now)
    assert set(out) == {'AAA', 'BBB'} and calls == ['BBB', 'BBB'] and len(sleeps) == 2 and sleeps[0] < sleeps[1] <= 5
    # fortsatt tom etter 2 forsøk -> ingen verdi (siden viser «Ingen data»)
    calls.clear(); sleeps.clear()
    monkeypatch.setattr(yf, 'download', lambda s, **k: (calls.append(s), pd.DataFrame())[1])
    out = DP.fetch(['AAA', 'BBB'], now=now)
    assert set(out) == {'AAA'} and calls == ['BBB', 'BBB'] and DP.RETRIES == 2


def test_mobile_rows_stacked_never_truncated():
    css = SR.CSS
    mob = css[css.index('@media(max-width:600px)'):]
    assert 'text-overflow' not in css and 'ellipsis' not in css and 'clamp' not in css
    assert 'grid-template-areas' not in mob and 'max-height' not in mob
    assert '.sr-t tr{display:flex;flex-wrap:wrap' in mob
    assert '.sr-t td.sr-tk{order:1;flex:0 0 100%;font-size:16px;line-height:24px;font-weight:600}' in mob
    assert '.sr-t td.sr-or{order:2;flex:0 0 100%;font-size:13px;line-height:18px;color:var(--mut)}' in mob
    assert '.sr-t td.sr-rt{order:3;flex:0 0 100%;font-size:14px;line-height:20px' in mob
    assert '.sr-t td.sr-sg,.sr-t td.sr-rk,.sr-t td.sr-flc,.sr-t td.sr-sc{order:4;flex:0 0 auto;font-size:13px;line-height:18px}' in mob
    assert 'white-space:normal;overflow:visible' in mob
    # 4 linjer: 24 + 18 + 20 + 18 + 2×8 padding = 96 – uten padding 80; rader med kort rolle holder seg innen 88 px
    assert '.sr-t tr{display:flex;flex-wrap:wrap;align-items:baseline;column-gap:0;padding:8px 0' in mob


def test_rec_row_wraps_up_to_52px():
    css = SR.CSS
    assert '.sr-t tr.sr-0 td{height:32px;box-sizing:border-box;padding:6px 8px;line-height:20px;white-space:normal}' in css
    assert '.sr-t tr.sr-0 td{display:block;padding:6px 0;height:auto;min-height:32px;line-height:20px;white-space:normal}' in css
    assert 2 * 20 + 2 * 6 == 52                                   # to linjer à 20 px + 6 px over og under
    assert REC_TXT in page()


def test_oslo_filter_shows_only_nod():
    h = page()
    s5 = h[h.index('id="vk-halvledere-selskaper"'):h.index('id="sektor-magneter"')]
    regions = re.findall(r'<tr(?: class="sr-0")? data-region="([^"]+)"><td class="sr-(?:tk|miss)"[^>]*>(?:<b>(?:<a [^>]*>)?(\w+))?', s5)
    assert [t for r, t in regions if r == 'oslo'] == ['NOD']
    assert ('strøket', '') in regions
    # Årsak live: «.sr-t tr.sr-0{display:block}» vant over «tr[hidden]» -> skjult REC-rad ble likevel vist
    assert '.sr-t tr[hidden]{display:none!important}' in SR.CSS
    assert "t.hidden=f!=='alle'&&t.dataset.region!==f" in V.JS


def test_sector_grid_gap_8_under_600():
    assert '@media(max-width:600px){.tr-secgrid{grid-template-columns:minmax(0,1fr);gap:8px}' in T.SECTOR_CSS
    # 390: 4 kort × min 88 + 3 × 8 = 376 px rutenett
    assert 4 * 88 + 3 * 8 == 376


def test_overview_tv_link_tap_area():
    from signaltool import names as NM
    c = NM.cell('PWR', 'ticker/PWR.html', 'Quanta')
    tv = re.search(r'<a class="tv"[^>]*href="([^"]+)"', c)
    assert tv and tv.group(1) != 'ticker/PWR.html'          # annen URL enn navnelenken -> beholdes, med 44×44 trykkflate
    assert '.ov-page a.tv,.ov-ct a.tv{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;' in OV.CSS
