"""Kildebundet trendleser. Ingen rangering, kjøpsmerker eller automatisk bekreftelse.
Bygging er uten nett og skriver aldri observasjonsloggen. Innhold endres eksplisitt.
"""
from __future__ import annotations
from datetime import datetime
from html import escape
import json
from pathlib import Path
from urllib.parse import urlsplit

DATA = Path(__file__).resolve().parent.parent / 'site_config' / 'trender.json'
CSS = r'''
body:has(.tr-page) main{padding:16px;max-width:1032px}
.tr-page{font-size:17px;line-height:26px;overflow-wrap:anywhere;max-width:1000px;margin:0 auto;container-type:inline-size}
.tr-head h1{font-size:26px;line-height:32px;margin:0}.tr-head>p{margin:6px 0 16px}
.tr-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px}
.tr-tabs a{display:flex;align-items:center;justify-content:center;min-height:44px;padding:8px 12px;border:1px solid #3b4757;border-radius:8px;color:#cbd5e1;font-size:15px;line-height:22px;text-decoration:none;box-sizing:border-box;white-space:normal}
.tr-tabs a[aria-current=true]{background:#1c2430;color:#fff;border-color:#58a6ff}.tr-tabs a:focus-visible{outline:2px solid #58a6ff;outline-offset:3px}
.tr-card{margin:0 0 24px;scroll-margin-top:16px}.tr-card[hidden]{display:none}
.tr-trend-head{margin:0 0 16px}.tr-page h2{font-size:22px;line-height:29px;margin:0 0 8px}.tr-page h3{font-size:18px;line-height:26px;margin:0 0 12px}.tr-page h4{font-size:17px;line-height:24px;margin:20px 0 8px}
.tr-page p{margin:8px 0 16px}.tr-meta{color:#cbd5e1;font-size:13px;line-height:20px}.tr-trend-head .tr-meta,.tr-trend-head .tr-status{margin:4px 0}
.tr-status{font-size:14px;line-height:22px;color:#cbd5e1}.tr-missing{display:block;color:#fdba74}
.tr-source,.tr-source-short{display:block;font-size:13px;line-height:20px;color:#cbd5e1;overflow-wrap:anywhere}
.tr-layout{display:grid;grid-template-columns:minmax(0,1fr);grid-template-areas:"chain" "companies" "follow";grid-template-rows:auto;gap:16px;align-items:start}
.tr-explanation{grid-area:chain}.tr-companies{grid-area:companies;min-width:0}.tr-follow{grid-area:follow}
.tr-explanation,.tr-follow{background:#1c2430;border:1px solid #3b4757;border-top:3px solid #58a6ff;border-radius:12px;padding:20px;min-width:0}
.tr-company{background:#111821;border:1px solid #3b4757;border-radius:8px;padding:16px;margin:0 0 16px;min-width:0;scroll-margin-top:24px}.tr-company>h4:first-child{font-size:18px;line-height:26px;margin:0 0 8px}
.tr-chain{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:0 0 12px}
.tr-chain>div{padding:10px;background:#111821;border:1px solid #3b4757;border-radius:6px;min-width:0}
.tr-chain dt{font-size:13px;line-height:20px;color:#cbd5e1}.tr-chain dd{margin:4px 0 0;font-size:17px;line-height:26px}
.tr-page .tr-doc{margin:16px 0 0}.tr-doc>summary{min-height:44px;cursor:pointer;color:#58a6ff;padding:8px 0;box-sizing:border-box}.tr-follow h3:not(:first-child){margin-top:24px}
@container(min-width:1000px){.tr-layout{grid-template-columns:minmax(0,620fr) minmax(0,356fr);grid-template-areas:"chain companies" "follow companies";grid-template-rows:auto 1fr;gap:24px}}
@media(max-width:600px){.tr-page h2{font-size:21px}.tr-explanation,.tr-follow{padding:16px 12px}.tr-company{padding:14px 12px}.tr-tabs{gap:6px}.tr-tabs a{padding:8px 10px}.tr-chain{grid-template-columns:minmax(0,1fr)}.tr-chain>div{display:grid;grid-template-columns:80px minmax(0,1fr);gap:8px;padding:8px}.tr-chain dd{margin:0;font-size:17px;line-height:26px}}
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


def html(data=None, available_tickers=()):
    data = load() if data is None else data
    available = set(available_tickers)
    nav = ''.join(f'<a href="#{E(t["id"])}" aria-controls="{E(t["id"])}" title="{E(t["title"])}">{E(t["id"].replace("-", " ").capitalize())}</a>' for t in data['trends'])
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
                    latest.append(claim(observation, full=True)); used_latest.add(n)
            companies.append(f'<section class="tr-company" id="{E(cid)}"><h4>{name} · {E(c["ticker"])}</h4>'
                             '<p class="tr-status">Dokumentert eksponering</p>' + claim(c['exposure'], full=True) +
                             ('<h4>Siste utvikling</h4>' + ''.join(latest) if latest else '') +
                             '<p class="tr-missing">Rapportert vekst fra denne utviklingen: Mangler data.</p>' +
                             '<h4>Hva svekker bildet?</h4>' + claim(c['limits'], full=True) +
                             '<p class="tr-missing">Verdsettelse og kursutvikling mot indeks: Mangler data.</p>'
                             '<p class="tr-missing">Inngangskurs er ikke registrert; avkastningsmåling er ikke startet.</p></section>')
        chains = []
        for c in t['chain']:
            vals = [('Råvare / materiale', c['material']), ('Komponent', c['component']),
                    ('Industri', c['industry']), ('Sektor', c['sector'])]
            chains.append('<dl class="tr-chain">' + ''.join(f'<div data-label="{E(label)}"><dt>{E(label)}</dt><dd>{E(value)}</dd></div>' for label,value in vals) + '</dl>' +
                          '<p class="tr-status">Avhengig av · Andel av råvarens sluttbruk: Andel ikke oppgitt.' + source(c['source'], c['published'], c['period']) + '</p>')
        documentation = ('<details class="tr-doc"><summary>Les dokumentasjonen</summary><h3>Bakgrunn</h3>' +
                         ''.join(claim(c, full=True) for c in t['background']) + '</details>')
        remaining = ''.join(claim(c, full=True) for n,c in enumerate(t['latest']) if n not in used_latest)
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
                     '<p class="tr-status">Råvareavhengighet dokumenterer ikke økt fortjeneste hos selskapet.</p></section>'
                     '<section class="tr-companies"><h3>Eksponert for trenden (ikke testet for avkastning)</h3>' +
                     (''.join(companies) or '<p class="tr-missing">Dokumenterte selskapskoblinger: Mangler data.</p>') + '</section>' +
                     '<section class="tr-follow">' + follow + '</section></div></article>')
    reviewed = datetime.fromisoformat(data['reviewed_at']).strftime('%d.%m.%Y kl. %H:%M')
    return ('<style>' + CSS + '</style><div class="tr-page">'
            '<header class="tr-head"><h1>Trender</h1><p>Materialer, komponenter og dokumenterte selskapskoblinger.</p></header>'
            '<nav class="tr-tabs" aria-label="Trender på siden">' + nav + '</nav>' + ''.join(cards) +
            f'<p class="tr-meta">Innhold kontrollert {E(reviewed)} norsk tid. Begrenset første utvalg; '
            'teksten oppdateres ikke automatisk av timesjobben.</p></div>' + JS)


def teaser():
    return ('<section class="card"><h2>Trender</h2><p>Materialer, komponenter og dokumenterte selskapskoblinger. '
            'Ikke testet for tidlighet eller avkastning.</p><a href="trender.html">Åpne Trender</a></section>')
