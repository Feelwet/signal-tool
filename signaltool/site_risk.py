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


def chip(r: dict | None, small: bool = False) -> str:
    lv = (r or {}).get("level")
    if lv not in ORDER:
        return f'<span class="rk rk-na{" rk-s" if small else ""}">Risiko: –</span>'
    return f'<span class="rk rk-{KEY[lv]}{" rk-s" if small else ""}">Risiko: {lv}</span>'


def info_btn() -> str:
    return ('<button type="button" class="rk-i" aria-expanded="false" aria-controls="rk-tip" aria-label="Om risikonivå">ⓘ</button>')


def tip() -> str:
    return f'<p id="rk-tip" class="rk-tip" hidden>{E(INFO)}</p>'


def src(r: dict | None) -> str:
    return f'<p class="rk-src">Beregnet fra kursdata · {_dm((r or {}).get("date"))}</p>'


def status() -> str:
    return f'<p class="catdisc rk-status">{E(STATUS)}</p>'


def cell(r: dict | None) -> str:
    lv = (r or {}).get("level")
    return f'<td class="rk-c" data-v="{ORDER.get(lv, "")}">{chip(r, small=True)}</td>'


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
"""

JS = """<script>(()=>{const B=[...document.querySelectorAll('.rk-i,.rt-i')];const close=x=>B.forEach(b=>{if(b!==x){b.setAttribute('aria-expanded','false');const t=document.getElementById(b.getAttribute('aria-controls'));if(t)t.hidden=true}});
B.forEach(b=>b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();const t=document.getElementById(b.getAttribute('aria-controls'));const o=b.getAttribute('aria-expanded')!=='true';close(b);b.setAttribute('aria-expanded',o?'true':'false');if(t)t.hidden=!o}));
document.addEventListener('click',e=>{if(!e.target.closest('.rk-tip'))close(null)});document.addEventListener('keydown',e=>{if(e.key==='Escape')close(null)})})()</script>"""
