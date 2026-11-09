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
STAGES = [(1, 'raavare', 'Innsatsvarer og utstyr'), (2, 'produsenter', 'Produsenter'),
          (3, 'bruk', 'Bruksområde'), (4, 'berorte', 'Berørte industrier og produkter'),
          (5, 'selskaper', 'Børsnoterte selskaper')]
STAGE5_HEAD = 'Børsnoterte selskaper i kjeden (ikke testet for avkastning)'
STAGE5_LINE = 'En plass i kjeden dokumenterer verken økt fortjeneste eller kursoppgang.'
TICKER_HEAD = 'Data fra ticker-siden, ikke en følge av plassen i kjeden'
FORBIDDEN = ('Mulige aksjer', 'verdt å undersøke', 'tjener på', 'drar nytte', 'vinner', 'oppside',
             'flaskehalsvinner', 'nisje')
EMPTY_SUPPLIER = 'Ingen dokumentert leverandør i kilden'
EMPTY_DIRECT = 'Ingen dokumentert kobling i kilden'
EXPLAIN = ('1. orden: selskapet gjør leddet selv, ifølge kilden. '
           '2. orden: kilden navngir selskapet som leverandør til et selskap i 1. orden.')
MISSING = 'Bruksområder og berørte industrier er ikke med ennå, fordi vi mangler kildebelagte koblinger.'
NO_SHARE = 'Andel ikke oppgitt'
REQUIRED = ('stage', 'order', 'company', 'exchange', 'claim', 'source_url', 'source_year', 'revenue_share')


def E(v):
    return escape(str(v), quote=True)


def valid_source(url):
    p = urlsplit(url or '')
    return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password


def resolve(lines):
    """[(linjenr, dict)] -> gjeldende linjer i opprinnelig rekkefølge. En rettelse kan rette en rettelse (37 -> 33 -> 10);
    da gjelder den siste. Feiler lukket ved uklar retting (fremoverpeker, gaffel, manglende begrunnelse)."""
    by_no = dict(lines)
    root, latest = {}, {}
    for no, d in lines:
        t = d.get('corrects_line')
        if t is None:
            continue
        if not isinstance(t, int) or t not in by_no or t >= no:
            raise ValueError(f'Ugyldig rettelse i linje {no}')
        if not d.get('correction_reason'):
            raise ValueError(f'Rettelse i linje {no} mangler begrunnelse')
        r = root.get(t, t)
        if latest.get(r, r) != t:
            raise ValueError(f'Linje {t} rettet to ganger')
        root[no], latest[r] = r, no
    out = []
    for no, d in lines:
        if 'corrects_line' in d:
            continue
        if no in latest:
            c = latest[no]
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
        share = d['revenue_share']
        if share != NO_SHARE:
            share = meta.get('share_display', {}).get(str(d['line']))
            if not share:
                raise ValueError(f'Linje {d["line"]}: andel uten godkjent visningstekst (nevner og år)')
        links.append({**d, 'ui_stage': meta['substages'][d['stage']]['stage'], 'share': share,
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


def element(l, bottleneck):
    tag = f'<span class="vk-tag">Flaskehals · {E(l["share"].removeprefix("Andel: "))}</span>' if l['line'] == bottleneck else ''
    ticker = f' · {E(l["ticker"])}' if l.get('ticker') else ''
    return (f'<li class="vk-el" data-line="{l["line"]}"><div class="vk-el-txt"><p class="vk-name">{E(l["company"])}{ticker}</p>'
            f'<p class="vk-role" title="{E(l["claim"])}">{E(l["claim"])}</p>'
            f'<p class="vk-share">{E(l["share"])} · Kilde {E(l["source_year"])}</p>{tag}</div>'
            f'<a class="vk-src" href="{E(l["source_url"])}" rel="noopener noreferrer" aria-label="Kilde for {E(l["company"])} ({E(l["source_year"])})">↗</a></li>')


def groups(items):
    out = {}
    for l in items:
        out.setdefault(l['label'], []).append(l)
    return out


def track(items, order, bottleneck):
    name = 'Direkte (1. orden)' if order == '1' else 'Leverandører (2. orden)'
    cls = 'vk-t1' if order == '1' else 'vk-t2'
    if not items:
        empty = EMPTY_SUPPLIER if order == '2' else EMPTY_DIRECT
        return f'<div class="vk-track {cls} vk-empty"><p class="vk-track-name">{name}</p><p class="vk-none">{empty}</p></div>'
    return (f'<div class="vk-track {cls}"><p class="vk-track-name">{name}</p>' +
            ''.join(f'<details class="vk-sub"><summary><span class="vk-sub-name">{E(g)}</span><span class="vk-sub-n">{len(ls)}</span></summary>'
                    '<ul>' + ''.join(element(l, bottleneck) for l in ls) + '</ul></details>'
                    for g, ls in groups(items).items()) + '</div>')


def companies(links):
    seen = {}
    for l in links:
        seen.setdefault((l['company'], l.get('ticker')), []).append(l)
    return seen


def stock_rows(links):
    """Børsnoterte selskaper i kjedens rekkefølge (ikke sortert på score/avkastning): (navn, ticker, symbol, ledd·orden, region)."""
    out = []
    for (name, ticker), ls in companies(links).items():
        where = ', '.join(dict.fromkeys(f'{l["label"]} · {l["order"]}. orden' for l in ls))
        out.append((name, ticker, page_symbol(ls[0]) if ticker else None, where, region(ls[0]['exchange'])))
    return out


def visible_stages(links):
    """Tomme ledd vises ikke (UxBot 09.11); ledd 3–4 kommer automatisk med når loggen får kildebelagte linjer."""
    return [s for s in STAGES if s[0] == 5 or any(l['ui_stage'] == s[0] for l in links)]


def html(chain='halvledere', data=None, available_tickers=(), snap=None):
    from . import stockrow as SR
    snap = snap or {}
    d = load(chain) if data is None else data
    available = set(available_tickers)
    links, bn = d['links'], d['bottleneck_line']
    checked = date.fromisoformat(d['checked']).strftime('%d.%m.%Y')
    comp = companies(links)
    shown = visible_stages(links)
    missing = len(shown) < len(STAGES)
    flow, body = [], []
    for pos, (n, sid, title) in enumerate(shown, 1):
        aid = f'vk-{d["id"]}-{sid}'
        if n == 5:
            cnt_flow, cnt_mob = f'{len(comp)}', f'{len(comp)} selskaper'
        else:
            a = [l for l in links if l['ui_stage'] == n and l['order'] == '1']
            b = [l for l in links if l['ui_stage'] == n and l['order'] == '2']
            cnt_flow, cnt_mob = f'{len(a)} + {len(b)}', f'{len(a)} direkte · {len(b)} andre-orden'
        flow.append(f'<a href="#{aid}">{E(title)} · {cnt_flow}</a>')
        if n == 5:
            # AnalBot 09.11: overskrift + forbehold rett over tabellen; kjedens rekkefølge, ingen sortering på score/avkastning
            inner = ('<div class="vk-filter" role="group" aria-label="Filtrer selskaper">'
                     '<button type="button" data-f="alle" aria-pressed="true">Alle</button>'
                     '<button type="button" data-f="oslo" aria-pressed="false">Oslo</button>'
                     '<button type="button" data-f="usa" aria-pressed="false">USA</button></div>'
                     f'<h4 class="vk-dh">{TICKER_HEAD}</h4><p class="vk-s5line">{STAGE5_LINE}</p>' +
                     SR.table(stock_rows(links), snap, order_col=True))
            head = STAGE5_HEAD
        else:
            inner = '<div class="vk-tracks">' + track(a, '1', bn) + track(b, '2', bn) + '</div>'
            head = title
        if n == 5:
            body.append(f'<section class="vk-stage vk-s5" id="{aid}"><h3 class="vk-stage-title">{pos} · {E(head)}</h3>'
                        f'<div class="vk-stage-body">{inner}</div></section>')
        else:   # UxBot 09.11 (sektoroversikt): alle ledd lukket ved lasting
            body.append(f'<details class="vk-stage" id="{aid}"><summary>'
                        f'<span class="vk-stage-title">{pos} · {E(head)}</span><span class="vk-count">{E(cnt_mob)}</span></summary>'
                        f'<div class="vk-stage-body">{inner}</div></details>')
    # Sektorkortene i Trender er nå velgeren (UxBot 09.11); panelet bærer kjedenavnet som overskrift.
    return (f'<section class="vk" aria-label="Verdikjede {E(d["name"])}"><p class="vk-sentence">{E(d["sentence"])}</p>'
            f'<p class="vk-meta">Offentlige kilder · sist kontrollert {checked}</p>' +
            (f'<p class="vk-meta vk-missing">{MISSING}</p>' if missing else '') +
            '<nav class="vk-flow" aria-label="Ledd i kjeden">' + '<span aria-hidden="true">→</span>'.join(flow) + '</nav>'
            f'<p class="vk-explain">{EXPLAIN}</p>' + ''.join(body) + '<p class="vk-meta">Til egen undersøkelse.</p></section>')


# Mørkt tema, bare eksisterende CSS-variabler (UxBot 09.11). 2. orden: kortflate +4 % lyshet via color-mix med --ink.
T2_BG = 'color-mix(in srgb,var(--card) 95%,var(--ink) 5%)'
CSS = r"""
.vk{margin:0 0 32px}
.vk-picker{display:flex;gap:8px;margin:0 0 12px}.vk-picker a{display:flex;align-items:center;height:44px;padding:0 14px;border:1px solid var(--acc);border-radius:22px;background:var(--card2);color:var(--ink);text-decoration:none;font-size:15px;box-sizing:border-box}
.vk h2{font-size:22px;line-height:29px;margin:0 0 4px}.vk .vk-sentence{margin:0 0 4px}
.vk .vk-meta{font-size:13px;line-height:18px;color:var(--mut);margin:0 0 12px}.vk .vk-meta+.vk-missing{margin-top:-8px}
.vk-flow{display:flex;align-items:center;gap:8px;height:56px;margin:0 0 12px;white-space:nowrap;overflow:hidden}
.vk-flow a{color:var(--acc);font-size:14px;line-height:20px;text-decoration:none;display:inline-flex;align-items:center;min-height:44px}.vk-flow span{color:var(--mut)}
.vk .vk-explain{font-size:14px;line-height:20px;color:var(--mut);margin:0 0 12px}
.vk-stage{border-top:2px solid var(--line);scroll-margin-top:16px}
.vk-stage>summary{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:56px;cursor:pointer;list-style:none;box-sizing:border-box}
.vk-stage>summary::-webkit-details-marker,.vk-sub>summary::-webkit-details-marker{display:none}
.vk-stage-title{font-size:18px;line-height:26px;font-weight:600}.vk-count{font-size:14px;line-height:20px;color:var(--mut)}
.vk-stage-body{padding:0 0 16px}
.vk-tracks{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.vk-track{border-left:4px solid var(--mut);background:var(--card);color:var(--ink);padding:8px 12px;min-width:0}
.vk-track.vk-t2{border-left:4px dashed var(--mut);background:""" + T2_BG + r"""}
.vk-track ul{list-style:none;margin:0;padding:0}
.vk .vk-track-name{font-size:13px;line-height:18px;font-weight:600;color:var(--mut);margin:0 0 4px}
.vk-sub>summary{display:flex;align-items:center;justify-content:space-between;gap:8px;list-style:none;cursor:pointer;margin:8px 0 0}
.vk-sub-name,.vk-sub-n{font-size:14px;line-height:20px;font-weight:600;color:var(--mut)}
.vk .vk-none{font-size:14px;line-height:20px;color:var(--mut);margin:0;max-height:40px;overflow:hidden}
.vk-el{display:flex;justify-content:space-between;gap:8px;padding:6px 0}.vk-el+.vk-el{border-top:1px solid var(--line)}
.vk-el-txt{min-width:0;flex:1}
.vk .vk-name{font-size:16px;line-height:24px;margin:0;color:var(--ink);font-weight:600}
.vk .vk-role,.vk .vk-share{font-size:14px;line-height:20px;color:var(--mut);margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vk-tag{display:inline-block;font-size:13px;line-height:18px;border:1px solid var(--mut);border-radius:4px;padding:0 6px;color:var(--ink);margin:2px 0 0}
.vk-src{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;color:var(--acc);text-decoration:none;flex:none}
.vk .vk-s5line{margin:0 0 8px}.vk .vk-dh{font-size:18px;line-height:24px;font-weight:600;margin:16px 0 4px}
.vk-filter{display:flex;gap:8px;margin:0 0 12px}.vk-filter button{height:44px;padding:0 14px;border:1px solid var(--line);border-radius:22px;background:transparent;color:var(--ink);font:inherit;font-size:15px;cursor:pointer}
.vk-filter button[aria-pressed=true]{border-color:var(--acc);background:var(--card2)}
@media(min-width:601px){.vk-sub>summary{pointer-events:none}.vk-sub-n{display:none}}
@media(max-width:600px){.vk-flow{display:none}.vk-tracks{grid-template-columns:minmax(0,1fr);gap:12px}.vk-track.vk-empty{display:none}
.vk-sub>summary{min-height:48px;margin:0}.vk-sub+.vk-sub{border-top:1px solid var(--line)}
.vk-el{max-height:88px;overflow:hidden}}
"""

JS = r"""<script>(()=>{const r=document.querySelector('.vk');if(!r)return;
const st=[...r.querySelectorAll('.vk-sub')],wide=matchMedia('(min-width:601px)');
const sync=()=>{if(wide.matches)st.forEach(s=>s.open=true)};sync();wide.addEventListener('change',sync);
r.querySelectorAll('.vk-flow a').forEach(a=>a.addEventListener('click',e=>{const t=document.getElementById(a.getAttribute('href').slice(1));if(!t)return;e.preventDefault();t.open=true;t.scrollIntoView({block:'start'})}));
const bs=[...r.querySelectorAll('.vk-filter button')],rows=[...r.querySelectorAll('.sr-t tbody tr')];
bs.forEach(b=>b.addEventListener('click',()=>{const f=b.dataset.f;bs.forEach(x=>x.setAttribute('aria-pressed',x===b?'true':'false'));
rows.forEach(t=>t.hidden=f!=='alle'&&t.dataset.region!==f)}));})();</script>"""
