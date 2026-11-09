"""Kildebundet trendleser. Ingen rangering, kjøpsmerker eller automatisk bekreftelse.
Bygging er uten nett og skriver aldri observasjonsloggen. Innhold endres eksplisitt.
"""
from __future__ import annotations
from datetime import datetime
from html import escape
import json
from pathlib import Path
from urllib.parse import urlsplit
from . import site_intro as INTRO
from . import verdikjeder as VK

DATA = Path(__file__).resolve().parent.parent / 'site_config' / 'trender.json'
CSS = r'''
body:has(.tr-page) main{padding:16px;max-width:1032px}
.tr-page{font-size:17px;line-height:26px;overflow-wrap:anywhere;max-width:1000px;margin:0 auto;container-type:inline-size}
.tr-head h1{font-size:26px;line-height:32px;margin:0}.tr-head>p{margin:6px 0 16px}
.tr-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 32px}
.tr-tabs a{display:flex;align-items:center;justify-content:center;min-height:44px;padding:8px 12px;border:1px solid #3b4757;border-radius:8px;color:#cbd5e1;font-size:15px;line-height:22px;text-decoration:none;box-sizing:border-box;white-space:normal}
.tr-tabs a[aria-current=true]{background:#1c2430;color:#fff;border-color:#58a6ff}.tr-tabs a:focus-visible{outline:2px solid #58a6ff;outline-offset:3px}
.tr-card{margin:0 0 24px;scroll-margin-top:16px}.tr-card[hidden]{display:none}
.tr-trend-head{margin:0 0 16px}.tr-page h2{font-size:22px;line-height:29px;margin:0 0 8px}.tr-page h3{font-size:18px;line-height:26px;margin:0 0 12px}.tr-page h4{font-size:17px;line-height:24px;margin:20px 0 8px}
.tr-page p{margin:8px 0 16px}.tr-meta{color:#cbd5e1;font-size:13px;line-height:20px}.tr-trend-head .tr-meta,.tr-trend-head .tr-status{margin:4px 0}
.tr-status{font-size:14px;line-height:22px;color:#cbd5e1}.tr-missing{display:block;color:#fdba74}
.tr-source,.tr-source-short{display:block;font-size:13px;line-height:20px;color:#cbd5e1;overflow-wrap:anywhere}
.tr-layout{display:grid;grid-template-columns:minmax(0,1fr);grid-template-areas:"chain" "companies" "follow";grid-template-rows:auto;gap:16px;align-items:start}
.tr-explanation{grid-area:chain}.tr-companies{grid-area:companies;min-width:0}.tr-follow{grid-area:follow}
.tr-explanation,.tr-companies,.tr-follow{background:#1c2430;border:1px solid #3b4757;border-top:3px solid #58a6ff;border-radius:12px;padding:20px;min-width:0}
.tr-company{margin:0;min-width:0;scroll-margin-top:24px}.tr-company+.tr-company{margin-top:20px;padding-top:20px;border-top:1px solid #3b4757}.tr-company>h4:first-child{font-size:18px;line-height:26px;margin:0 0 8px}
.tr-chain{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:0 0 16px}
.tr-chain>div{padding:0;background:none;border:0;border-radius:0;min-width:0}
.tr-chain dt{font-size:13px;line-height:20px;color:#cbd5e1}.tr-chain dd{margin:4px 0 0;font-size:17px;line-height:26px}
.tr-page .tr-doc{margin:16px 0 0}.tr-doc>summary{min-height:44px;cursor:pointer;color:#58a6ff;padding:8px 0;box-sizing:border-box}.tr-follow h3:not(:first-child){margin-top:24px}
@container(min-width:1000px){.tr-layout{grid-template-columns:minmax(0,620fr) minmax(0,356fr);grid-template-areas:"chain companies" "follow companies";grid-template-rows:auto 1fr;gap:24px}}
@media(max-width:600px){.tr-page h2{font-size:21px}.tr-explanation,.tr-companies,.tr-follow{padding:16px 12px}.tr-tabs{gap:6px}.tr-tabs a{padding:8px 10px}.tr-chain{grid-template-columns:minmax(0,1fr)}.tr-chain>div{display:grid;grid-template-columns:80px minmax(0,1fr);gap:8px;padding:0}.tr-chain dd{margin:0;font-size:17px;line-height:26px}}
.tr-page .tr-source a,.tr-page .tr-source-short a,.tr-company h4>a{display:inline-flex;align-items:center;min-width:44px;min-height:44px;max-width:100%}.tr-doc li{margin:0 0 16px}.tr-card{margin-bottom:32px}
@media(max-width:600px){.tr-tabs{margin-bottom:24px}.tr-card{margin-bottom:24px}}
'''

JS = r'''<script>(()=>{
const root=document.querySelector('.tr-page');if(!root)return;
const panels=[...root.querySelectorAll('article.tr-card')],links=[...root.querySelectorAll('.tr-tabs a')];
if(!panels.length)return;
const show=id=>{let target=document.getElementById(id),panel=target&&target.closest('article.tr-card');
if(!panel||!panels.includes(panel))panel=panels[0];
panels.forEach(p=>p.hidden=p!==panel);links.forEach(a=>{if(a.getAttribute('href')==='#'+panel.id)a.setAttribute('aria-current','true');else a.removeAttribute('aria-current')});return target};
const fromHash=()=>{let id='';try{id=decodeURIComponent(location.hash.slice(1))}catch(_){}return show(id)};
links.forEach(a=>a.addEventListener('click',e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();history.pushState(null,'',a.getAttribute('href'));show(a.getAttribute('href').slice(1))}));
addEventListener('hashchange',fromHash);addEventListener('popstate',fromHash);
const target=fromHash();if(target&&target.classList.contains('tr-company'))requestAnimationFrame(()=>target.scrollIntoView({block:'start'}));
})();</script>'''



def E(value):
    return escape(str(value), quote=True)


def valid_source(url):
    p = urlsplit(url)
    return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password


def check_claim(c):
    if not c.get('text') or not valid_source(c.get('source', '')) or not c.get('period') or not c.get('published'):
        raise ValueError('Påstand mangler kilde, periode eller publiseringsdato')


def load(path=DATA):
    data = json.loads(Path(path).read_text())
    datetime.fromisoformat(data['reviewed_at'])
    ids = set()
    for t in data['trends']:
        if t['id'] in ids or not t['id'].replace('-', '').isalnum():
            raise ValueError('Ugyldig eller duplisert trend-id')
        ids.add(t['id'])
        datetime.fromisoformat(t['first_seen'])
        # Første versjon har ingen kontrollert prosess for å bekrefte nye trender.
        if t['status'] != 'Tidlig observasjon':
            raise ValueError('Bekreftet utvikling krever separat kontroll av ferske data')
        for c in t['background'] + t['latest']:
            check_claim(c)
        for c in t['chain']:
            if not valid_source(c['source']) or not c.get('period') or not c.get('published'):
                raise ValueError('Avhengighet mangler kilde og datering')
            if c.get('share') is not None:
                raise ValueError('Sluttbruksandeler må godkjennes før visning')
        for c in t['companies']:
            check_claim(c['exposure']); check_claim(c['limits'])
            if c.get('growth') is not None:
                raise ValueError('Rapportert vekst må godkjennes før visning')
    return data


def source(url, published, period):
    host = urlsplit(url).hostname
    return (f'<span class="tr-source"><a href="{E(url)}" rel="noopener noreferrer">{E(host)}</a>'
            f' · Kildedato: {E(published)} · Dataperiode: {E(period)}</span>')


def claim(c, full=False):
    src = source(c['source'], c['published'], c['period']) if full else (
        f'<span class="tr-source-short"><a href="{E(c["source"])}">Kilde</a> · {E(c["published"])}</span>')
    return f'<p>{E(c["text"])}{src}</p>'


def html(data=None, available_tickers=(), snap=None):
    from . import stockrow as SR
    data = load() if data is None else data
    snap = snap or {}
    available = set(available_tickers)
    cards = []
    for t in data['trends']:
        date = datetime.fromisoformat(t['first_seen']).strftime('%d.%m.%Y')
        companies, used_latest = [], set()
        for number, c in enumerate(t['companies']):
            cid = f'{t["id"]}-selskap-{number}'
            symbol = c['ticker'].split(':')[-1].strip()
            from .site import slug
            name = (f'<a href="ticker/{E(slug(symbol))}.html">{E(c["name"])}</a>'
                    if symbol in available else E(c['name']))
            # Knytt dagens dokumenterte utvikling til riktig selskapskilde, én gang.
            latest = []
            for n, observation in enumerate(t['latest']):
                if n not in used_latest and observation['source'] == c['exposure']['source']:
                    latest.append(claim(observation)); used_latest.add(n)
            companies.append(f'<section class="tr-company" id="{E(cid)}"><h4>{name} · {E(c["ticker"])}</h4>'
                             '<p class="tr-status">Dokumentert eksponering</p>' + claim(c['exposure']) +
                             ('<h4>Siste utvikling</h4>' + ''.join(latest) if latest else '') +
                             '<p class="tr-missing">Rapportert vekst fra denne utviklingen: Mangler data.</p>' +
                             '<h4>Hva svekker bildet?</h4>' + claim(c['limits']) +
                             '<p class="tr-missing">Verdsettelse og kursutvikling mot indeks: Mangler data.</p>'
                             '<p class="tr-missing">Inngangskurs er ikke registrert; avkastningsmåling er ikke startet.</p></section>')
        chains = []
        for c in t['chain']:
            vals = [('Råvare / materiale', c['material']), ('Komponent', c['component']),
                    ('Industri', c['industry']), ('Sektor', c['sector'])]
            chains.append('<dl class="tr-chain">' + ''.join(f'<div data-label="{E(label)}"><dt>{E(label)}</dt><dd>{E(value)}</dd></div>' for label,value in vals) + '</dl>' +
                          '<p class="tr-status">Avhengig av · Andel av råvarens sluttbruk: Andel ikke oppgitt.' + f'<span class="tr-source-short"><a href="{E(c["source"])}">Kilde</a> · {E(c["published"])} · {E(c["period"])}</span>' + '</p>')
        # Reference details move under disclosure; local claims and caveats remain visible.
        refs = t['background'] + t['latest'] + t['chain'] + [q for c in t['companies'] for q in (c['exposure'], c['limits'])]
        unique = {(q['source'], q['published'], q['period']): q for q in refs}
        documentation = ('<details class="tr-doc"><summary>Les dokumentasjonen</summary><h3>Bakgrunn</h3>' +
                         ''.join(claim(c) for c in t['background']) + '<h3>Kilder og dataperioder</h3><ul>' +
                         ''.join('<li>' + source(q['source'], q['published'], q['period']) + '</li>' for q in unique.values()) + '</ul></details>')
        remaining = ''.join(claim(c) for n,c in enumerate(t['latest']) if n not in used_latest)
        follow = (('<h3>Siste utvikling</h3>' + remaining if remaining else '') +
                  ('<p class="tr-missing">Ferske observasjoner: Mangler data.</p>' if not t['latest'] else '') +
                  '<h3>Mangelstatus og virkning</h3><p class="tr-missing">Mangelstatus: Mangler data.</p>'
                  '<p>Lagerbeholdning eller eksportvedtak er ikke verifisert for denne kjeden.</p>'
                  '<p class="tr-missing">Dokumentert virkning på produksjon: Mangler data.</p>'
                  '<h3>Hva følger vi videre?</h3><p>Vi undersøker lagerbeholdning, eksportvedtak, rapporterte leveranser, ordre og marginer. '
                  'Dette er en undersøkelsesliste, ikke en prognose.</p>' + documentation)
        cards.append(f'<article class="tr-card" id="{E(t["id"])}"><header class="tr-trend-head"><h2>{E(t["title"])}</h2>'
                     f'<p class="tr-meta">Først registrert {date} · {E(t["status"])}</p>'
                     '<p class="tr-status">Ikke testet for tidlighet</p></header>'
                     '<div class="tr-layout"><section class="tr-explanation"><h3>Dokumentert bruk</h3>' + ''.join(chains) +
                     '</section>'
                     '<section class="tr-companies"><h3>Eksponert for trenden (ikke testet for avkastning)</h3>' +
                     (''.join(companies) or '<p class="tr-missing">Dokumenterte selskapskoblinger: Mangler data.</p>') + '</section>' +
                     '<section class="tr-follow">' + follow + '</section></div></article>')
    reviewed = datetime.fromisoformat(data['reviewed_at']).strftime('%d.%m.%Y kl. %H:%M')
    # Sektoroversikt (bruker/UxBot 09.11): kort øverst, ett åpent panel om gangen, alt innhold og alle forbehold bak sektoren.
    vk = VK.load()
    sectors = [('halvledere', vk['name'], 'Verdikjede', VK.stock_rows(vk['links']), '',
                VK.html(data=vk, available_tickers=available, snap=snap))]
    for t, card in zip(data['trends'], cards):
        rows = [trend_row(c) for c in t['companies']]
        table = (('<section class="tr-stocks"><h3>Data fra ticker-siden</h3>' + SR.table(rows, snap) + '</section>') if rows else '')
        sectors.append((t['id'], t['title'], None, rows, '', table + card))
    grid = []
    for sid, name, tag, rows, _x, content in sectors:
        pid = f'sektor-{sid}'
        tg = f'<span class="tr-tag">{E(tag)}</span>' if tag else ''
        grid.append(f'<button type="button" class="tr-sec" id="kort-{E(sid)}" aria-expanded="false" aria-controls="{E(pid)}">'
                    f'<span class="tr-sec-nm">{E(name)}</span>{tg}<span class="tr-sec-st">{E(SR.status(rows, snap))}</span></button>')
    panels = []
    for sid, name, tag, rows, _x, content in sectors:
        pid = f'sektor-{sid}'
        panels.append(f'<section class="tr-panel" id="{E(pid)}" aria-labelledby="kort-{E(sid)}" data-sektor="{E(sid)}">'
                      f'<div class="tr-panel-bar"><h2 class="tr-panel-h">{E(name)}</h2>'
                      f'<a class="tr-deep" href="#{E(pid)}">Lenke til sektoren</a>'
                      '<button type="button" class="tr-close">Lukk</button></div>' + SR.date_line(rows, snap) + content + '</section>')
    return ('<style>' + CSS + VK.CSS + SR.CSS + SECTOR_CSS + '</style><div class="tr-page">'
            '<header class="tr-head"><h1>Trender</h1>' + INTRO.html('Trender') + '</header>'
            '<div class="tr-secgrid" role="group" aria-label="Sektorer">' + ''.join(grid) + ''.join(panels) + '</div>'
            f'<p class="tr-meta">Innhold kontrollert {E(reviewed)} norsk tid. Begrenset første utvalg; '
            'teksten oppdateres ikke automatisk av timesjobben.</p></div>' + SECTOR_JS + VK.JS)


def trend_row(c):
    """Trendselskap -> (navn, ticker, symbol i datasettet). «NYSE: MP» -> MP; Oslo -> «.OL»."""
    exch, _, tk = c['ticker'].rpartition(':')
    tk, exch = tk.strip(), exch.strip().upper()
    if not tk:
        return (c['name'], None, None, None)
    sym = tk + '.OL' if exch in ('OSE', 'OSLO', 'OSLO BØRS') else (tk if exch in ('NYSE', 'NASDAQ', 'NYSE AMERICAN', '') else None)
    return (c['name'], tk, sym, None)


SECTOR_CSS = r"""
.tr-secgrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0 0 32px}
.tr-sec{display:flex;flex-direction:column;align-items:flex-start;gap:4px;min-height:80px;padding:12px;text-align:left;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:10px;font:inherit;cursor:pointer;box-sizing:border-box;min-width:0}
.tr-sec[aria-expanded=true]{border:2px solid var(--acc);padding:11px}
.tr-sec:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.tr-sec-nm{font-size:16px;line-height:24px;font-weight:600}
.tr-sec-st{font-size:13px;line-height:18px;color:var(--mut);max-height:36px;overflow:hidden}
.tr-tag{font-size:12px;line-height:16px;padding:0 6px;border:1px solid var(--line);border-radius:999px;color:var(--mut)}
.tr-panel{grid-column:1/-1;border-top:1px solid var(--line);padding:16px 0 0;min-width:0}
.tr-secgrid.js .tr-panel[hidden]{display:none}
.tr-panel-bar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;margin:0 0 16px}
.tr-panel .tr-panel-h{font-size:18px;line-height:24px;font-weight:600;margin:0;flex:1 1 auto}
.tr-deep{display:inline-flex;align-items:center;min-height:44px;color:var(--acc);font-size:14px}
.tr-close{min-height:44px;min-width:44px;padding:0 14px;background:transparent;border:1px solid var(--line);border-radius:8px;color:var(--ink);font:inherit;cursor:pointer}
.tr-panel .tr-stocks,.tr-panel .vk-s5{border-top:1px solid var(--line);padding-top:16px;margin:0 0 32px}
.tr-panel h3{font-size:18px;line-height:24px;font-weight:600}
.tr-panel .tr-card{margin:0}
/* UxBot 09.11: én kolonne ved 390 (statuslinjen får plass på maks to linjer), kort min 88 px */
@media(max-width:600px){.tr-secgrid{grid-template-columns:minmax(0,1fr)}.tr-sec{min-height:88px}}
"""

SECTOR_JS = r"""<script>(()=>{const g=document.querySelector('.tr-secgrid');if(!g)return;
const C=[...g.querySelectorAll('.tr-sec')],P=C.map(c=>document.getElementById(c.getAttribute('aria-controls')));
g.classList.add('js');C.forEach((c,i)=>c.style.order=2*i);P.forEach(p=>p.hidden=true);let cur=-1;
const place=i=>{const n=getComputedStyle(g).gridTemplateColumns.split(' ').filter(Boolean).length||1;P[i].style.order=2*(Math.min(Math.ceil((i+1)/n)*n,C.length)-1)+1};
const set=(i,url)=>{cur=i;C.forEach((c,j)=>{c.setAttribute('aria-expanded',j===i?'true':'false');P[j].hidden=j!==i});if(i>=0)place(i);
if(url)history.replaceState(null,'',i>=0?'#'+P[i].id:location.pathname+location.search.replace(/([?&])sektor=[^&]*&?/,'$1').replace(/[?&]$/,''))};
C.forEach((c,i)=>c.addEventListener('click',()=>set(cur===i?-1:i,true)));
P.forEach((p,i)=>{const b=p.querySelector('.tr-close');if(b)b.addEventListener('click',()=>{set(-1,true);C[i].focus()})});
addEventListener('resize',()=>{if(cur>=0)place(cur)});
const deep=()=>{let id='';try{id=decodeURIComponent(location.hash.slice(1))}catch(_){}
const q=new URLSearchParams(location.search).get('sektor');if(!id&&q)id='sektor-'+q;if(!id)return;
const t=document.getElementById(id);if(!t)return;const i=P.findIndex(p=>p.contains(t));if(i<0)return;set(i,false);
if(t.tagName==='DETAILS')t.open=true;requestAnimationFrame(()=>t.scrollIntoView({block:'start'}))};
deep();addEventListener('hashchange',deep)})();</script>"""


def teaser():
    return ('<section class="card"><h2>Trender</h2><p>Materialer, komponenter og dokumenterte selskapskoblinger. '
            'Ikke testet for tidlighet eller avkastning.</p><a href="trender.html">Åpne Trender</a></section>')
