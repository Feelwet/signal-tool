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
CSS = '''
body:has(.tr-page) main{padding:16px;max-width:1100px}
.tr-page{font-size:17px;line-height:26px;overflow-wrap:anywhere}
.tr-grid{display:grid;grid-template-columns:200px minmax(0,720px);gap:24px;justify-content:center}
.tr-head{grid-column:2;grid-row:1}.tr-index{grid-column:1;grid-row:2;align-self:start;position:sticky;top:16px;font-size:15px;line-height:22px}
.tr-index a{display:block;padding:10px 0;min-height:44px;box-sizing:border-box;white-space:normal}
.tr-read{grid-column:2;grid-row:2;min-width:0;max-width:720px}
.tr-card{background:#1c2430;border:1px solid #3b4757;border-top:3px solid #58a6ff;border-radius:12px;padding:20px;margin:0 0 24px;scroll-margin-top:16px}
.tr-page h1{font-size:26px;line-height:32px}.tr-page h2{font-size:22px;line-height:29px;margin:0 0 8px}.tr-page h3{font-size:18px;line-height:26px;margin:24px 0 8px}
.tr-page p{margin:8px 0 16px}.tr-meta{color:#cbd5e1;font-size:13px;line-height:20px}.tr-missing{color:#fdba74}
.tr-source{font-size:13px;line-height:20px;display:block;color:#cbd5e1}.tr-status{font-size:14px;line-height:22px;color:#cbd5e1}
.tr-company{background:#111821;border:1px solid #3b4757;border-radius:8px;padding:14px;margin:12px 0}
.tr-company h4{font-size:18px;margin:0 0 8px}.tr-chain{width:100%;font-size:14px;line-height:22px;table-layout:fixed}.tr-chain th{white-space:normal}.tr-chain td,.tr-chain th{padding:8px;overflow-wrap:anywhere;white-space:normal;min-width:0;box-sizing:border-box}
@media(max-width:1000px){.tr-grid{grid-template-columns:minmax(0,720px);gap:16px}.tr-head,.tr-index,.tr-read{grid-column:1;grid-row:auto}.tr-index{position:static;display:flex;flex-wrap:wrap;gap:8px 16px}.tr-index a{padding:10px 12px;border:1px solid #3b4757;border-radius:8px;display:flex;align-items:center}}
@media(max-width:600px){.tr-card{padding:16px 12px}.tr-chain,.tr-chain tbody,.tr-chain tr,.tr-chain td{display:block;width:100%}.tr-chain thead{display:none}.tr-chain td:before{content:attr(data-label);display:block;font-weight:600;color:#cbd5e1}.tr-chain tr{margin-bottom:16px;border:1px solid #3b4757}.tr-page h2{font-size:21px}.tr-source{overflow-wrap:anywhere}}
.tr-head h1{margin:0}.tr-head>p{margin:6px 0}.tr-page .tr-doc{margin:16px 0}.tr-doc>summary{min-height:44px;cursor:pointer;color:#58a6ff;padding:8px 0}.tr-company-jumps{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 16px}.tr-company-jumps a{display:flex;align-items:center;min-height:44px;padding:8px 12px;box-sizing:border-box;border:1px solid #3b4757;border-radius:8px;white-space:normal}.tr-card>.tr-status,.tr-card>.tr-meta{margin:4px 0}.tr-source-short{display:block;font-size:13px;line-height:20px;color:#cbd5e1}.tr-company{scroll-margin-top:24px}.tr-missing{display:block}.tr-page .tr-chain{table-layout:fixed}.tr-page .tr-chain td{white-space:normal;overflow-wrap:anywhere}
'''


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
    nav = ''.join(f'<a href="#{E(t["id"])}">{E(t["title"])}</a>' for t in data['trends'])
    cards = []
    for t in data['trends']:
        date = datetime.fromisoformat(t['first_seen']).strftime('%d.%m.%Y')
        companies, jumps, claims = [], [], list(t['background']) + list(t['latest'])
        for number, c in enumerate(t['companies']):
            cid = f'{t["id"]}-selskap-{number}'
            symbol = c['ticker'].split(':')[-1].strip()
            # Bygget genererer bare sider for tickere vi faktisk har data for.
            from .site import slug
            name = (f'<a href="ticker/{E(slug(symbol))}.html">{E(c["name"])}</a>'
                    if symbol in available else E(c['name']))
            jumps.append(f'<a href="#{E(cid)}">{E(c["name"])}</a>')
            claims.extend([c['exposure'], c['limits']])
            companies.append(f'<section class="tr-company" id="{E(cid)}"><h4>{name} · {E(c["ticker"])}</h4>'
                             '<p class="tr-status">Dokumentert eksponering</p>' + claim(c['exposure']) +
                             '<p class="tr-missing">Rapportert vekst fra denne utviklingen: Mangler data.</p>' +
                             '<h4>Hva svekker bildet?</h4>' + claim(c['limits']) +
                             '<p class="tr-missing">Verdsettelse og kursutvikling mot indeks: Mangler data.</p>'
                             '<p class="tr-missing">Inngangskurs er ikke registrert; avkastningsmåling er ikke startet.</p></section>')
        rows = []
        for c in t['chain']:
            vals = [('Råvare / materiale', c['material']), ('Komponent', c['component']),
                    ('Industri', c['industry']), ('Sektor', c['sector'])]
            rows.append('<tr>' + ''.join(f'<td data-label="{E(label)}">{E(value)}</td>' for label, value in vals) + '</tr>')
            rows.append('<tr><td colspan="4" data-label="Dokumentasjon">Avhengig av · Andel av råvarens sluttbruk: '
                        'Andel ikke oppgitt.' + source(c['source'], c['published'], c['period']) + '</td></tr>')
        documentation = ('<details class="tr-doc"><summary>Les dokumentasjonen</summary><h3>Bakgrunn</h3>' +
                         ''.join(claim(c, full=True) for c in t['background']) + '</details>')
        dependencies = ('<h3>Komponenter, industrier og sektorer</h3><table class="tr-chain"><thead><tr><th>Råvare / materiale</th><th>Komponent</th><th>Industri</th><th>Sektor</th></tr></thead><tbody>' +
                         ''.join(rows) + '</tbody></table><h3>Kildedetaljer</h3>' +
                         ''.join(source(c['source'], c['published'], c['period']) for c in claims))
        cards.append(f'<article class="tr-card" id="{E(t["id"])}"><h2>{E(t["title"])}</h2>'
                     f'<p class="tr-meta">Først registrert {date}</p>'
                     '<p class="tr-status">Ikke testet for tidlighet</p>'
                     f'<p class="tr-status">{E(t["status"])}</p>' +
                     ('<nav class="tr-company-jumps" aria-label="Selskaper i denne trenden">' + ''.join(jumps) + '</nav>' if jumps else '') +
                     '<h3>Eksponert for trenden (ikke testet for avkastning)</h3>' +
                     (''.join(companies) or '<p class="tr-missing">Dokumenterte selskapskoblinger: Mangler data.</p>') +
                     '<h3>Siste utvikling</h3>' +
                     (''.join(claim(c) for c in t['latest']) or '<p class="tr-missing">Ferske observasjoner: Mangler data.</p>') +
                     '<h3>Mangelstatus og virkning</h3>' +
                     '<p class="tr-missing">Mangelstatus: Mangler data.</p>'
                     '<p>Lagerbeholdning eller eksportvedtak er ikke verifisert for denne kjeden.</p>' +
                     '<p class="tr-missing">Dokumentert virkning på produksjon: Mangler data.</p>' +
                     '<h3>Hva følger vi videre?</h3><p>Vi undersøker lagerbeholdning, eksportvedtak, rapporterte leveranser, ordre og marginer. '
                     'Dette er en undersøkelsesliste, ikke en prognose.</p>' + documentation + dependencies + '</article>')
    reviewed = datetime.fromisoformat(data['reviewed_at']).strftime('%d.%m.%Y kl. %H:%M')
    return ('<style>' + CSS + '</style><div class="tr-page"><div class="tr-grid">'
            '<header class="tr-head"><h1>Trender</h1><p>Materialer, komponenter og dokumenterte selskapskoblinger.</p></header>'
            '<nav class="tr-index" aria-label="Trender på siden">' + nav +
            '</nav><div class="tr-read">' + ''.join(cards) +
            f'<p class="tr-meta">Innhold kontrollert {E(reviewed)} norsk tid. Begrenset første utvalg; '
            'teksten oppdateres ikke automatisk av timesjobben.</p></div></div></div>')


def teaser():
    return ('<section class="card"><h2>Trender</h2><p>Materialer, komponenter og dokumenterte selskapskoblinger. '
            'Ikke testet for tidlighet eller avkastning.</p><a href="trender.html">Åpne Trender</a></section>')
