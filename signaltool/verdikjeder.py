"""Verdikjeder i Trender (låst spesifikasjon 09.11.2026, UxBot layout + AnalBot ordlyd).

Kun visning. Leser append-only lenkelogg; linjer med «corrects_line» erstatter linjen de peker på,
og erstattet tekst vises aldri. Elementer uten kilde vises ikke. Kjeder påvirker aldri score,
Kjøp-kandidat eller Signal-boka: modulen importeres bare av trender.py.
"""
from __future__ import annotations
from datetime import date
from html import escape
import json
from pathlib import Path
from urllib.parse import urlsplit

DIR = Path(__file__).resolve().parent.parent / 'site_config' / 'verdikjeder'
CHAINS = ('halvledere',)
STAGES = [(1, 'raavare', 'Råvare og komponent'), (2, 'produsenter', 'Produsenter'),
          (3, 'bruk', 'Bruksområde'), (4, 'berorte', 'Berørte industrier og produkter'),
          (5, 'selskaper', 'Børsnoterte selskaper')]
STAGE5_HEAD = 'Børsnoterte selskaper i kjeden (ikke testet for avkastning)'
STAGE5_LINE = 'En plass i kjeden dokumenterer verken økt fortjeneste eller kursoppgang.'
FORBIDDEN = ('Mulige aksjer', 'verdt å undersøke', 'tjener på', 'drar nytte', 'vinner', 'oppside',
             'flaskehalsvinner', 'nisje')
EMPTY_SUPPLIER = 'Ingen dokumentert leverandør i kilden'
EXPLAIN = '1. orden gjør leddet selv. 2. orden er navngitt leverandør til et selskap i 1. orden.'
REQUIRED = ('stage', 'order', 'company', 'exchange', 'claim', 'source_url', 'source_year', 'revenue_share')


def E(v):
    return escape(str(v), quote=True)


def valid_source(url):
    p = urlsplit(url or '')
    return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password


def resolve(lines):
    """[(linjenr, dict)] -> gjeldende linjer i opprinnelig rekkefølge. Feiler lukket ved uklar retting."""
    by_no = dict(lines)
    replaced = {}
    for no, d in lines:
        t = d.get('corrects_line')
        if t is None:
            continue
        if not isinstance(t, int) or t not in by_no or t >= no or 'corrects_line' in by_no[t]:
            raise ValueError(f'Ugyldig rettelse i linje {no}')
        if t in replaced:
            raise ValueError(f'Linje {t} rettet to ganger')
        if not d.get('correction_reason'):
            raise ValueError(f'Rettelse i linje {no} mangler begrunnelse')
        replaced[t] = no
    out = []
    for no, d in lines:
        if 'corrects_line' in d:
            continue
        if no in replaced:
            c = replaced[no]
            out.append({**by_no[c], 'line': c, 'replaces': no})
        else:
            out.append({**d, 'line': no})
    return out


def load(chain='halvledere', base=DIR):
    meta = json.loads((Path(base) / f'{chain}.json').read_text())
    date.fromisoformat(meta['checked'])
    raw = (Path(base) / meta['links_file']).read_text().splitlines()
    lines = [(n, json.loads(s)) for n, s in enumerate(raw, 1) if s.strip()]
    if [n for n, _ in lines] != list(range(1, len(lines) + 1)):
        raise ValueError('Tomme linjer i loggen')
    links = []
    for d in resolve(lines):
        if any(d.get(k) in (None, '') for k in REQUIRED) or d['order'] not in ('1', '2'):
            raise ValueError(f'Linje {d["line"]} mangler felt')
        if not valid_source(d['source_url']):
            continue  # uten kilde vises ikke
        if d['stage'] not in meta['substages']:
            raise ValueError(f'Ukjent ledd i linje {d["line"]}')
        links.append({**d, 'ui_stage': meta['substages'][d['stage']]['stage'],
                      'label': meta['substages'][d['stage']]['label']})
    if not any(l['line'] == meta['bottleneck_line'] and l['ticker'] == 'ASML' for l in links):
        raise ValueError('Flaskehals-merket krever ASML-linjen')
    return {**meta, 'links': links}


def region(exchange):
    if 'Oslo' in exchange:
        return 'oslo'
    if 'NASDAQ' in exchange or 'NYSE' in exchange:
        return 'usa'
    return 'annen'


def page_symbol(l):
    r = region(l['exchange'])
    return l['ticker'] + '.OL' if r == 'oslo' else (l['ticker'] if r == 'usa' else None)


def share_text(s):
    return s if s.startswith('Andel') else f'Andel: {s}'


def element(l, bottleneck):
    tag = ''
    if l['line'] == bottleneck:
        tag = (f'<span class="vk-tag">Flaskehals · {E(l["revenue_share"])}</span>')
    ticker = f' · {E(l["ticker"])}' if l.get('ticker') else ''
    role = f'{l["label"]} · {l["claim"]}'
    return (f'<li class="vk-el" data-line="{l["line"]}"><div class="vk-el-txt"><p class="vk-name">{E(l["company"])}{ticker}</p>'
            f'<p class="vk-role" title="{E(role)}">{E(role)}</p>'
            f'<p class="vk-share">{E(share_text(l["revenue_share"]))} · Kilde {E(l["source_year"])}</p>{tag}</div>'
            f'<a class="vk-src" href="{E(l["source_url"])}" rel="noopener noreferrer" aria-label="Kilde for {E(l["company"])} ({E(l["source_year"])})">↗</a></li>')


def track(items, order, bottleneck):
    name = 'Direkte (1. orden)' if order == '1' else 'Leverandører (2. orden)'
    cls = 'vk-t1' if order == '1' else 'vk-t2'
    if not items:
        empty = EMPTY_SUPPLIER if order == '2' else 'Ingen kildebelagt kobling i loggen'
        return f'<div class="vk-track {cls} vk-empty"><p class="vk-track-name">{name}</p><p class="vk-none">{empty}</p></div>'
    return (f'<div class="vk-track {cls}"><p class="vk-track-name">{name}</p><ul>' +
            ''.join(element(l, bottleneck) for l in items) + '</ul></div>')


def companies(links):
    seen = {}
    for l in links:
        key = (l['company'], l.get('ticker'))
        seen.setdefault(key, []).append(l)
    return seen


def stage5(links, available):
    rows, cards = [], []
    for (name, ticker), ls in companies(links).items():
        r = region(ls[0]['exchange'])
        where = ', '.join(dict.fromkeys(f'{l["label"]} · {l["order"]}. orden' for l in ls))
        src = ''.join(f'<a class="vk-src" href="{E(u)}" rel="noopener noreferrer" aria-label="Kilde {i}">↗</a>'
                      for i, u in enumerate(dict.fromkeys(l['source_url'] for l in ls), 1))
        sym = page_symbol(ls[0])
        from .site import slug
        see = (f' <a class="vk-see" href="ticker/{E(slug(sym))}.html">Se ticker →</a>'
               if sym and sym in available else '')
        tk = E(ticker) if ticker else 'Ikke børsnotert'
        rows.append(f'<tr data-region="{r}"><td><b>{tk}</b> {E(name)}{see}</td><td>{E(ls[0]["exchange"])}</td><td>{E(where)}</td><td>{src}</td></tr>')
    return rows


def html(chain='halvledere', data=None, available_tickers=()):
    d = load(chain) if data is None else data
    available = set(available_tickers)
    links, bn = d['links'], d['bottleneck_line']
    checked = date.fromisoformat(d['checked']).strftime('%d.%m.%Y')
    comp = companies(links)
    flow, body = [], []
    for n, sid, title in STAGES:
        aid = f'vk-{d["id"]}-{sid}'
        if n == 5:
            cnt_flow, cnt_mob = f'{len(comp)}', f'{len(comp)} selskaper'
        else:
            a = [l for l in links if l['ui_stage'] == n and l['order'] == '1']
            b = [l for l in links if l['ui_stage'] == n and l['order'] == '2']
            cnt_flow, cnt_mob = f'{len(a)} + {len(b)}', f'{len(a)} direkte · {len(b)} andre-orden'
        flow.append(f'<a href="#{aid}">{E(title)} · {cnt_flow}</a>')
        if n == 5:
            inner = (f'<p class="vk-s5line">{STAGE5_LINE}</p>'
                     '<div class="vk-filter" role="group" aria-label="Filtrer selskaper">'
                     '<button type="button" data-f="alle" aria-pressed="true">Alle</button>'
                     '<button type="button" data-f="oslo" aria-pressed="false">Oslo</button>'
                     '<button type="button" data-f="usa" aria-pressed="false">USA</button></div>'
                     '<table class="vk-table"><thead><tr><th>Ticker og navn</th><th>Børs</th><th>Ledd og orden</th><th>Kilde</th></tr></thead><tbody>' +
                     ''.join(stage5(links, available)) + '</tbody></table>')
            head = STAGE5_HEAD
        else:
            inner = '<div class="vk-tracks">' + track(a, '1', bn) + track(b, '2', bn) + '</div>'
            head = title
        body.append(f'<details class="vk-stage" id="{aid}"{" open" if n == 1 else ""}><summary>'
                    f'<span class="vk-stage-title">{n} · {E(head)}</span><span class="vk-count">{E(cnt_mob)}</span></summary>'
                    f'<div class="vk-stage-body">{inner}</div></details>')
    return ('<section class="vk" aria-labelledby="vk-title">'
            '<nav class="vk-picker" aria-label="Verdikjeder"><a href="#vk-title" aria-current="true">Halvledere</a></nav>'
            f'<h2 id="vk-title">{E(d["name"])}</h2><p class="vk-sentence">{E(d["sentence"])}</p>'
            f'<p class="vk-meta">Offentlige kilder · sist kontrollert {checked}</p>'
            '<nav class="vk-flow" aria-label="Ledd i kjeden">' + '<span aria-hidden="true">→</span>'.join(flow) + '</nav>'
            f'<p class="vk-explain">{EXPLAIN}</p>' + ''.join(body) + '<p class="vk-meta">Til egen undersøkelse.</p></section>')


CSS = r'''
.vk{margin:0 0 32px}
.vk-picker{display:flex;gap:8px;margin:0 0 12px}.vk-picker a{display:flex;align-items:center;height:44px;padding:0 14px;border:1px solid #58a6ff;border-radius:22px;background:#1c2430;color:#fff;text-decoration:none;font-size:15px;box-sizing:border-box}
.vk h2{font-size:22px;line-height:29px;margin:0 0 4px}.vk .vk-sentence{margin:0 0 4px}
.vk .vk-meta{font-size:13px;line-height:18px;color:#9ca3af;margin:0 0 12px}
.vk-flow{display:flex;align-items:center;gap:8px;height:56px;margin:0 0 12px;white-space:nowrap;overflow:hidden}
.vk-flow a{color:#58a6ff;font-size:14px;line-height:20px;text-decoration:none;display:inline-flex;align-items:center;min-height:44px}.vk-flow span{color:#9ca3af}
.vk .vk-explain{font-size:14px;line-height:20px;color:#cbd5e1;margin:0 0 12px}
.vk-stage{border-top:2px solid #6b7280;scroll-margin-top:16px}
.vk-stage>summary{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:56px;cursor:pointer;list-style:none;box-sizing:border-box}
.vk-stage>summary::-webkit-details-marker{display:none}
.vk-stage-title{font-size:18px;line-height:26px;font-weight:600}.vk-count{font-size:14px;line-height:20px;color:#9ca3af}
.vk-stage-body{padding:0 0 16px}
.vk-tracks{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.vk-track{border-left:4px solid #1f2937;background:#fff;color:#111827;padding:8px 12px;min-width:0}
.vk-track.vk-t2{border-left:4px dashed #4b5563;background:#f1f3f5}
.vk-track ul{list-style:none;margin:0;padding:0}
.vk .vk-track-name{font-size:13px;line-height:18px;font-weight:600;color:#374151;margin:0 0 4px}
.vk .vk-none{font-size:14px;line-height:20px;color:#4b5563;margin:0;max-height:40px;overflow:hidden}
.vk-track.vk-empty{max-height:none}
.vk-el{display:flex;justify-content:space-between;gap:8px;padding:6px 0;max-height:none}.vk-el+.vk-el{border-top:1px solid #e5e7eb}
.vk-el-txt{min-width:0;flex:1}
.vk .vk-name{font-size:16px;line-height:24px;margin:0;color:#111827;font-weight:600}
.vk .vk-role,.vk .vk-share{font-size:14px;line-height:20px;color:#4b5563;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vk-tag{display:inline-block;font-size:13px;line-height:18px;border:1px solid #374151;border-radius:4px;padding:0 6px;color:#111827;margin:2px 0 0}
.vk-src{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;color:#1d4ed8;text-decoration:none;flex:none}
.vk .vk-s5line{margin:0 0 12px}
.vk-filter{display:flex;gap:8px;margin:0 0 12px}.vk-filter button{height:44px;padding:0 14px;border:1px solid #3b4757;border-radius:22px;background:transparent;color:#cbd5e1;font:inherit;font-size:15px;cursor:pointer}
.vk-filter button[aria-pressed=true]{border-color:#58a6ff;color:#fff;background:#1c2430}
.vk-table{width:100%;border-collapse:collapse;font-size:14px;line-height:20px}.vk-table th,.vk-table td{text-align:left;padding:6px 8px;border-bottom:1px solid #3b4757;vertical-align:middle}
.vk-table .vk-src{color:#58a6ff}.vk-see{color:#58a6ff;white-space:nowrap}
.vk-table tr[hidden]{display:none}
@media(min-width:601px){.vk-stage>summary{pointer-events:none}.vk-stage>summary .vk-count{display:none}}
@media(max-width:600px){.vk-flow{display:none}.vk-tracks{grid-template-columns:minmax(0,1fr);gap:12px}.vk-track.vk-empty{display:none}
.vk-el{max-height:88px;overflow:hidden}
.vk-table thead{display:none}.vk-table,.vk-table tbody,.vk-table tr,.vk-table td{display:block;width:100%}
.vk-table tr{max-height:96px;overflow:hidden;border-bottom:1px solid #3b4757;padding:6px 0;position:relative}.vk-table td{border:0;padding:0 48px 0 0}
.vk-table td:last-child{position:absolute;right:0;top:4px;width:auto;padding:0}}
'''

JS = r'''<script>(()=>{const r=document.querySelector('.vk');if(!r)return;
const st=[...r.querySelectorAll('.vk-stage')],wide=matchMedia('(min-width:601px)');
const sync=()=>{if(wide.matches)st.forEach(s=>s.open=true)};sync();wide.addEventListener('change',sync);
r.querySelectorAll('.vk-flow a').forEach(a=>a.addEventListener('click',e=>{const t=document.getElementById(a.getAttribute('href').slice(1));if(!t)return;e.preventDefault();t.open=true;t.scrollIntoView({block:'start'})}));
const bs=[...r.querySelectorAll('.vk-filter button')],rows=[...r.querySelectorAll('.vk-table tbody tr')];
bs.forEach(b=>b.addEventListener('click',()=>{const f=b.dataset.f;bs.forEach(x=>x.setAttribute('aria-pressed',x===b?'true':'false'));
rows.forEach(t=>t.hidden=f!=='alle'&&t.dataset.region!==f)}));})();</script>'''
