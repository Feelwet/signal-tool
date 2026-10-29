"""Tickere-listen med filterrad (Alle · Høy · Middels · Lav · Røde flagg) lagret i URL (?filter=)."""
from __future__ import annotations

from html import escape as E

from . import evidens as EV
from . import names as NM
from .mine import EMPTY

FILTERS = (("mine", "★ Mine"), ("alle", "Alle"), ("hoy", "Høy"), ("middels", "Middels"), ("lav", "Lav"), ("flagg", "Røde flagg"))
CAT_OF = {"hoy": "Høy", "middels": "Middels", "lav": "Lav"}
NAME = dict(FILTERS)

CSS = """
/* UxBot 26.10: knapper 36 px, 12 px padding, 8 px mellomrom; fade 24 px til høyre, skjult når raden er scrollet helt ut */
.tf-wrap{position:relative;margin:6px 0 10px}
.tf-wrap::after{content:"";position:absolute;top:0;right:0;bottom:0;width:24px;pointer-events:none;background:linear-gradient(to right,transparent,var(--bg,#0d1117))}
.tf-wrap.at-end::after{display:none}
.tf-row{display:flex;flex-wrap:wrap;gap:8px;margin:0}
.tf-row button{height:36px;min-height:36px;padding:0 12px;white-space:nowrap;flex:none;border-radius:22px;border:1px solid #30363d;background:#161b22;color:inherit;font:inherit;cursor:pointer}
.tf-row button[aria-pressed=true]{background:var(--acc,#6cb6ff);color:#06101c;border-color:var(--acc,#6cb6ff);font-weight:700}
.fchip{display:inline-block;margin-left:6px;padding:0 6px;border-radius:9px;background:#3a1418;color:#ff7b72;border:1px solid #f8514966;font-size:.8em;white-space:nowrap}
.tf-empty{padding:10px 0}.tf-flag .grp{margin:10px 0 4px}.tf-flag .rfr{padding:5px 0;border-bottom:1px solid #21262d}.tf-flag .fb{margin-top:3px}
.nokurs{display:inline-block;margin-left:6px;padding:0 6px;border-radius:9px;font-size:11px;line-height:16px;color:#64748b;background:#1e293b;white-space:nowrap}
.tf-only{font-size:.85em;color:var(--mut);margin:0 0 6px}
@media(max-width:599px){.tf-row{flex-wrap:nowrap;overflow-x:auto;gap:8px;scrollbar-width:none}.tf-row::-webkit-scrollbar{display:none}
#tf-table th:nth-child(4),#tf-table td:nth-child(4){display:none}#tf-table .why,#tf-table .mer,#tf-table td:first-child .mut{display:none}#tf-table td{padding:6px 4px;white-space:nowrap;font-size:.9em}#tf-table th{padding:6px 4px}}
"""

JS = """<script>(()=>{const F=['mine','alle','hoy','middels','lav','flagg'].concat(document.querySelector('.tf-row button[data-f=ny]')?['ny']:[]),NM={mine:'★ Mine',alle:'Alle',hoy:'Risiko Høy',middels:'Risiko Middels',lav:'Risiko Lav',flagg:'Røde flagg',ny:'Ingen avkastning ennå'},B=[...document.querySelectorAll('.tf-row button')],T=document.getElementById('tf-table'),G=document.getElementById('tf-flag'),P=document.getElementById('tf-empty');
let cur='alle';function mine(){return window.STMine?window.STMine.load():[]}
function set(f,push){if(!F.includes(f))f='alle';cur=f;B.forEach(b=>b.setAttribute('aria-pressed',b.dataset.f===f?'true':'false'));
const fl=f==='flagg';if(G)G.hidden=!fl;if(T)T.hidden=fl;let n=0;const M=mine();
document.querySelectorAll('#tf-table tr[data-cat]').forEach(r=>{const on=f==='alle'||(f==='mine'?M.includes(r.dataset.t):f==='ny'?!!r.querySelector('td.ret-c[data-new]'):r.dataset.cat===({hoy:'Høy',middels:'Middels',lav:'Lav'})[f]);r.hidden=!on;if(on)n++});
if(fl&&G)n=G.querySelectorAll('.rfr').length;
if(P){P.hidden=n>0;P.textContent=f==='mine'?'""" + EMPTY + """':'Ingen tickere i '+NM[f]+' nå.';if(fl&&G)G.after(P);else if(T)T.prepend(P)}
if(push){const u=new URL(location.href);if(f==='alle')u.searchParams.delete('filter');else u.searchParams.set('filter',f);history.replaceState(null,'',u)}}
B.forEach(b=>b.addEventListener('click',()=>{set(b.dataset.f===cur&&b.dataset.f!=='alle'?'alle':b.dataset.f,true)}));
document.addEventListener('mine:change',e=>set(e.detail&&e.detail.imp?'mine':cur,false));
set(new URL(location.href).searchParams.get('filter')||'alle',false)})()</script>"""


def flag_map(snap: dict) -> dict:
    return {r["ticker"]: r for r in EV.red_rows(snap)}


def chip(r: dict | None) -> str:
    """Rød ⚑-chip med antall testede flagg (+EBIT). Ingen chip for ikke-sjekkede (f.eks. US)."""
    if not r:
        return ""
    return f'<span class="fchip">⚑ {E(EV.nlabel(r))}</span>'


FADE_JS = ("<script>(()=>{const r=document.querySelector('.tf-row'),w=r&&r.parentElement;if(!w)return;"
           "const u=()=>w.classList.toggle('at-end',r.scrollLeft+r.clientWidth>=r.scrollWidth-1);"
           "r.addEventListener('scroll',u,{passive:true});addEventListener('resize',u);u()})()</script>")


def nokurs(e: dict) -> str:
    """Grå chip når tickeren mangler kursdata (UxBot 26.10): raden vises, hullet synes."""
    return "" if (e.get("stats") or {}).get("close") is not None else '<span class="nokurs">Ingen kursdata</span>'


def n_new(snap: dict) -> int:
    """Rader der innkursdato = siste kursdato (samme regel som «Ny i dag» i avkastningscellen)."""
    return sum(1 for e in snap.get("tickers", []) if (e.get("_ret") or {}).get("new") and not e.get("unranked"))


def filter_row(snap: dict) -> str:
    n, nn = len(EV.red_rows(snap)), n_new(snap)
    ny = f'<button type="button" data-f="ny" aria-pressed="false">Ingen avkastning ennå ({nn})</button>' if nn else ""   # UxBot 28.10: sist, skjult når 0
    return '<div class="tf-wrap"><div class="tf-row" role="group" aria-label="Filter">' + "".join(
        f'<button type="button" data-f="{k}" aria-pressed="{"true" if k == "alle" else "false"}">{E(lab)}{f" ({n})" if k == "flagg" else ' (<span class="mine-n">0</span>)' if k == "mine" else ""}</button>'
        for k, lab in FILTERS) + ny + "</div></div>" + FADE_JS


def flag_block(snap: dict) -> str:
    rows, c = EV.red_rows(snap), EV.coverage(snap)
    if not c["n"]:
        return ('<div id="tf-flag" class="tf-flag" hidden><p class="tf-only">Bare Oslo-aksjer er sjekket for røde flagg.</p>'
                '<p class="warnline">Flaggene er ikke beregnet i denne kjøringen. Ingen tall vises heller enn oppdiktede.</p></div>')
    from . import sectors as SEC
    ebx = (f" Dekning: negativ EBIT er bare kjent for {c['ebit']} av {c['n']} aksjer – manglende ≠ positiv EBIT." if c["ebit"] < c["n"] else "")
    legend = EV._legend([k for k in EV.RED_FLAGS if any(k in r["flags"] for r in rows)], ebx)
    groups = ((f'{EV.badge("two_plus")} 2+ flagg', [r for r in rows if EV.ntest(r) >= 2]),
              ("1 flagg, ingen målt underavkastning", [r for r in rows if EV.ntest(r) == 1]),
              (f'Bare negativ EBIT, ikke testet', [r for r in rows if EV.ntest(r) == 0]))
    def row(r):
        t = r["ticker"]
        return (f'<div class="rfr">{NM.cell(t, extra=chip(r))}'
                f'<div class="fb">{"".join(EV.short_badge(k) for k in EV.RED_FLAGS if k in r["flags"])}</div></div>')
    body = "".join(f'<h3 class="grp">{t} ({len(rs)})</h3>' + "".join(row(r) for r in rs) for t, rs in groups if rs)
    return (f'<div id="tf-flag" class="tf-flag card" hidden><p class="tf-only">Bare Oslo-aksjer er sjekket for røde flagg. '
            f'{len(rows)} av {c["n"]} likvide Oslo-aksjer har minst ett flagg; data per {E(c["asof"] or "–")}.</p>'
            f'<details class="vis-alle"><summary>Hva betyr flaggene?</summary>{legend}'
            f'<p class="mut">Ingen flagg har bestått testkravet. Se <a href="metode.html">Metode</a> og <a href="{EV.EVREPORT}">testrapport</a>.</p></details>'
            f'{body}</div>')


def empties() -> str:
    """Én felles melding: «Ingen tickere i X nå.» for alle filtre med 0 treff (★ Mine: hint om ☆)."""
    return '<p id="tf-empty" class="tf-empty mut" hidden></p>'
