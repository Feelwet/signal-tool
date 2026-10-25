"""Tickere-listen med filterrad (Alle · Kjøp · Hold · Følg · Røde flagg) lagret i URL (?filter=)."""
from __future__ import annotations

from html import escape as E

from . import evidens as EV

FILTERS = (("alle", "Alle"), ("kjop", "Kjøp"), ("hold", "Hold"), ("folg", "Følg"), ("flagg", "Røde flagg"))
CAT_OF = {"kjop": "kjop", "hold": "hold", "folg": "watch"}
NAME = dict(FILTERS)

CSS = """
.tf-row{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 10px}
.tf-row button{min-height:44px;min-width:44px;padding:0 14px;border-radius:22px;border:1px solid #30363d;background:#161b22;color:inherit;font:inherit;cursor:pointer}
.tf-row button[aria-pressed=true]{background:var(--acc,#6cb6ff);color:#06101c;border-color:var(--acc,#6cb6ff);font-weight:700}
.fchip{display:inline-block;margin-left:6px;padding:0 6px;border-radius:9px;background:#3a1418;color:#ff7b72;border:1px solid #f8514966;font-size:.8em;white-space:nowrap}
.tf-empty{padding:10px 0}.tf-flag .grp{margin:10px 0 4px}.tf-flag .rfr{padding:5px 0;border-bottom:1px solid #21262d}.tf-flag .fb{margin-top:3px}
.tf-only{font-size:.85em;color:var(--mut);margin:0 0 6px}
@media(max-width:599px){.tf-row{flex-wrap:nowrap;overflow-x:auto;gap:4px}.tf-row button{padding:0 10px;flex:none}
#tf-table th:nth-child(4),#tf-table td:nth-child(4){display:none}#tf-table .why,#tf-table .mer,#tf-table td:first-child .mut{display:none}#tf-table td{padding:6px 4px;white-space:nowrap;font-size:.9em}#tf-table th{padding:6px 4px}}
"""

JS = """<script>(()=>{const F=['alle','kjop','hold','folg','flagg'],B=[...document.querySelectorAll('.tf-row button')],T=document.getElementById('tf-table'),G=document.getElementById('tf-flag');
function set(f,push){if(!F.includes(f))f='alle';B.forEach(b=>b.setAttribute('aria-pressed',b.dataset.f===f?'true':'false'));
const fl=f==='flagg';if(G)G.hidden=!fl;if(T)T.hidden=fl;let n=0;
document.querySelectorAll('#tf-table tr[data-cat]').forEach(r=>{const on=f==='alle'||r.dataset.cat===({kjop:'kjop',hold:'hold',folg:'watch'})[f];r.hidden=!on;if(on)n++});
document.querySelectorAll('.tf-empty').forEach(p=>p.hidden=!(p.dataset.f===f&&n===0));
if(push){const u=new URL(location.href);if(f==='alle')u.searchParams.delete('filter');else u.searchParams.set('filter',f);history.replaceState(null,'',u)}}
B.forEach(b=>b.addEventListener('click',()=>{const cur=new URL(location.href).searchParams.get('filter')||'alle';set(b.dataset.f===cur?'alle':b.dataset.f,true)}));
set(new URL(location.href).searchParams.get('filter')||'alle',false)})()</script>"""


def flag_map(snap: dict) -> dict:
    return {r["ticker"]: r for r in EV.red_rows(snap)}


def chip(r: dict | None) -> str:
    """Rød ⚑-chip med antall testede flagg (+EBIT). Ingen chip for ikke-sjekkede (f.eks. US)."""
    if not r:
        return ""
    return f'<span class="fchip">⚑ {E(EV.nlabel(r))}</span>'


def filter_row(snap: dict) -> str:
    n = len(EV.red_rows(snap))
    return '<div class="tf-row" role="group" aria-label="Filter">' + "".join(
        f'<button type="button" data-f="{k}" aria-pressed="{"true" if k == "alle" else "false"}">{E(lab)}{f" ({n})" if k == "flagg" else ""}</button>'
        for k, lab in FILTERS) + "</div>"


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
        return (f'<div class="rfr"><b>{E(t)}</b>{SEC.tv_ext(t)}{chip(r)}'
                f'<div class="fb">{"".join(EV.short_badge(k) for k in EV.RED_FLAGS if k in r["flags"])}</div></div>')
    body = "".join(f'<h3 class="grp">{t} ({len(rs)})</h3>' + "".join(row(r) for r in rs) for t, rs in groups if rs)
    return (f'<div id="tf-flag" class="tf-flag card" hidden><p class="tf-only">Bare Oslo-aksjer er sjekket for røde flagg. '
            f'{len(rows)} av {c["n"]} likvide Oslo-aksjer har minst ett flagg; data per {E(c["asof"] or "–")}.</p>'
            f'<details class="vis-alle"><summary>Hva betyr flaggene?</summary>{legend}'
            f'<p class="mut">Ingen flagg har bestått testkravet. Se <a href="metode.html">Metode</a> og <a href="{EV.EVREPORT}">testrapport</a>.</p></details>'
            f'{body}</div>')


def empties() -> str:
    return "".join(f'<p class="tf-empty mut" data-f="{k}" hidden>Ingen tickere i {E(NAME[k])} nå.</p>' for k in CAT_OF)
