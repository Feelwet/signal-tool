"""Risikochip (UxBot-spec, AnalBots tekster ordrett). Ingen ikon, pil eller tall i chipen."""
from __future__ import annotations
from html import escape as E

INFO = ("Risikonivået er regnet ut fra hvor mye aksjen har svingt de siste 60 dagene, det største fallet de siste 12 månedene og hvor mye "
        "aksjen omsettes. Det er relativt til andre aksjer på samme børs: Høy i USA er omtrent som Middels i Oslo. I historiske tester "
        "svingte Høy klart mer enn Lav de neste 60 dagene, men nivåene overlapper. Risikonivået sier ingenting om avkastning og er ikke et kjøpsråd.")
STATUS = "Risikonivå er testet på historiske data. Kategoriene er ikke bekreftet."
ORDER = {"Lav": 1, "Middels": 2, "Høy": 3}
KEY = {"Lav": "lav", "Middels": "middels", "Høy": "hoy"}


def _dm(d: str | None) -> str:
    return f"{d[8:10]}.{d[5:7]}" if d else "–"


def chip(r: dict | None, small: bool = False, bare: bool = False) -> str:
    """bare=True: kun nivået (tabellceller under kolonneoverskriften «Risiko»)."""
    lv = (r or {}).get("level")
    pre = "" if bare else "Risiko: "
    if lv not in ORDER:
        return f'<span class="rk rk-na{" rk-s" if small else ""}">{pre}–</span>'
    return f'<span class="rk rk-{KEY[lv]}{" rk-s" if small else ""}">{pre}{lv}</span>'


def info_btn() -> str:
    return ('<button type="button" class="rk-i" aria-expanded="false" aria-controls="rk-tip" aria-label="Om risikonivå">ⓘ</button>')


def tip() -> str:
    return f'<p id="rk-tip" class="rk-tip" hidden>{E(INFO)}</p>'


def src(r: dict | None) -> str:
    return f'<p class="rk-src">Beregnet fra kursdata · {_dm((r or {}).get("date"))}</p>'


def status() -> str:
    return f'<p class="catdisc rk-status">{E(STATUS)}</p>'


NA_TIP = "Risikonivå mangler data"


def cell(r: dict | None, score_html: str = "") -> str:
    """Risikocelle. score_html: poengboksen dupliseres under brikken, vises bare på 390 px (kolonne «Risiko · Poeng», UxBot 29.10)."""
    sc = f'<span class="rkp-s">{score_html}</span>' if score_html else ""
    lv = (r or {}).get("level")
    if lv not in ORDER:   # UxBot 28.10: «–» beholdes, ⓘ-tooltip som i avkastningscellen
        return (f'<td class="rk-c" data-v=""><span class="ri ri-c" tabindex="0" aria-expanded="false" aria-label="{NA_TIP}">'
                f'<span class="rk rk-na rk-s" title="{NA_TIP}">–</span>ⓘ<span class="tip">{NA_TIP}</span></span>{sc}</td>')
    return f'<td class="rk-c" data-v="{ORDER.get(lv, "")}">{chip(r, small=True, bare=True)}{sc}</td>'


EMPTY_BOOK = "Ingen avsluttede handler ennå. Resultater vises etter 30."

CSS = """
.rk{display:inline-flex;align-items:center;box-sizing:border-box;height:28px;padding:0 10px;border-radius:6px;font-size:13px;font-weight:700;line-height:1;white-space:nowrap;color:#fff;vertical-align:middle}
.rk-lav{background:#DCFCE7;color:#166534}.rk-middels{background:#FEF3C7;color:#92400E}.rk-hoy{background:#FEE2E2;color:#991B1B}.rk-na{background:transparent;color:var(--mut);border:1px solid #30363d}
.rk.rk-s{height:20px;padding:0 7px;font-size:11px;border-radius:5px}
p.since.rk-line{display:flex;align-items:center;gap:0;overflow:visible;white-space:nowrap;margin:0 0 8px;min-height:28px}
p.since.rk-line .sl-t{overflow:hidden;text-overflow:ellipsis;min-width:0}
.rk-i{flex:none;display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;margin:-8px 0 -8px -6px;padding:0;border:0;background:none;color:var(--mut);font:inherit;font-size:16px;cursor:pointer}
.rt-i{flex:none;display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;margin:-8px -10px -8px -10px;padding:0;border:0;background:none;color:var(--mut);font:inherit;font-size:14px;cursor:pointer}.sl-r{flex:none;white-space:nowrap}.rt-i[aria-expanded=true],.rk-i[aria-expanded=true]{color:var(--fg,#e6edf3)}
.rk-tip{margin:0 0 6px;padding:8px 10px;font-size:13px;line-height:1.4;border:1px solid #30363d;border-radius:6px;background:#161b22}
.rk-src{margin:-6px 0 0;font-size:11px;line-height:14px;color:#8b949e}
p.catdisc.rk-status{margin:2px 0 4px;font-size:11px;line-height:1.3;color:#8b949e;white-space:nowrap}
@media(max-width:599px){p.since.rk-line{margin:-8px 0 8px}}
td.rk-c{white-space:nowrap}
td.rk-c,th.rk-h{width:1%;min-width:64px;box-sizing:border-box}
.rkp-m,.rkp-s{display:none}
@media(max-width:599px){#tf-table th.pt-h,#tf-table td.pt-c{display:none}#tf-table .rkp-m{display:inline}#tf-table th.rk-h,#tf-table td.rk-c{width:68px;min-width:68px;max-width:68px;padding-left:2px;padding-right:2px;text-align:center}#tf-table th.rk-h{white-space:normal;line-height:1.2}#tf-table td.rk-c{white-space:normal;vertical-align:top}#tf-table td.rk-c .rkp-s{display:block;margin-top:4px}}
"""

JS = """<script>(()=>{const B=[...document.querySelectorAll('.rk-i,.rt-i')];const close=x=>B.forEach(b=>{if(b!==x){b.setAttribute('aria-expanded','false');const t=document.getElementById(b.getAttribute('aria-controls'));if(t)t.hidden=true}});
B.forEach(b=>b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();const t=document.getElementById(b.getAttribute('aria-controls'));const o=b.getAttribute('aria-expanded')!=='true';close(b);b.setAttribute('aria-expanded',o?'true':'false');if(t)t.hidden=!o}));
document.addEventListener('click',e=>{if(!e.target.closest('.rk-tip'))close(null)});document.addEventListener('keydown',e=>{if(e.key==='Escape')close(null)})})()</script>"""

# Brukeren 29.10: ⓘ (.ri, .rk-i, .rt-i) åpnes ved mus-hover og lukkes når musa går ut – bare (hover:hover) and (pointer:fine).
# Klikk mens hover-åpen fester popoveren (lukkes med klikk utenfor / Esc). Touch: uendret (bare trykk).
HOVER_JS = r"""<script>(()=>{if(window.__stHov)return;window.__stHov=1;const mq=matchMedia('(hover:hover) and (pointer:fine)'),d=document,Q='.ri,.rk-i,.rt-i';
const tgt=b=>b.classList.contains('ri')?null:d.getElementById(b.getAttribute('aria-controls'));
const pos=b=>{const t=b.querySelector('.tip');if(!t||!b.classList.contains('ri-c'))return;t.classList.add('pop');const r=b.getBoundingClientRect(),w=Math.min(260,innerWidth-16);t.style.maxWidth=w+'px';const tw=Math.min(t.offsetWidth||w,w);t.style.left=Math.max(8,Math.min(r.left+r.width/2-tw/2,innerWidth-tw-8))+'px';t.style.top=(r.bottom+6)+'px'};
const set=(b,o)=>{b.setAttribute('aria-expanded',o?'true':'false');const t=tgt(b);if(t)t.hidden=!o;if(o)pos(b)};
const fine=e=>mq.matches&&e.pointerType==='mouse';
d.querySelectorAll(Q).forEach(b=>{
b.addEventListener('pointerenter',e=>{if(!fine(e))return;d.querySelectorAll(Q).forEach(x=>{if(x!==b&&x.getAttribute('aria-expanded')==='true'&&!x.dataset.pin)set(x,false)});if(b.getAttribute('aria-expanded')!=='true'){b.dataset.hov='1';b.dataset.pin='';set(b,true)}});
b.addEventListener('pointerleave',e=>{if(!fine(e))return;if(b.dataset.hov&&!b.dataset.pin)set(b,false);b.dataset.hov=''})});
d.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest(Q);if(!b||!b.dataset.hov||b.dataset.pin||!mq.matches)return;if(e.target.closest('.tip a'))return;e.preventDefault();e.stopPropagation();b.dataset.pin='1'},true);
const shut=()=>d.querySelectorAll(Q).forEach(x=>{x.dataset.pin='';x.dataset.hov='';if(x.getAttribute('aria-expanded')==='true')set(x,false)});
d.addEventListener('focusin',e=>{const b=e.target.closest&&e.target.closest(Q);if(b&&mq.matches&&b.matches(':focus-visible')&&b.getAttribute('aria-expanded')!=='true'){b.dataset.hov='1';b.dataset.pin='';set(b,true)}});
d.addEventListener('focusout',e=>{const b=e.target.closest&&e.target.closest(Q);if(b&&mq.matches&&b.dataset.hov&&!b.dataset.pin&&!b.contains(e.relatedTarget)){b.dataset.hov='';set(b,false)}});
d.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('.ri.ri-c');if(b)setTimeout(()=>{if(b.getAttribute('aria-expanded')==='true')pos(b)},0)},true);
addEventListener('scroll',()=>d.querySelectorAll('.ri.ri-c[aria-expanded=true]').forEach(pos),{passive:true});
d.addEventListener('click',e=>{if(e.target.closest&&e.target.closest(Q))return;shut()});d.addEventListener('keydown',e=>{if(e.key==='Escape')shut()})})()</script>"""
JS += HOVER_JS
