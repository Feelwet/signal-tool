"""Felles layout for opprydding: navigasjon, sidetopp (tittel + én setning + nøkkeltall), merker,
treffrate-tekst, utdatert-regel fra logs/source_status.jsonl og Metode-siden."""
from __future__ import annotations
import html
import json
from datetime import date, datetime
from pathlib import Path

E = lambda x: html.escape("" if x is None else str(x))
LOG = Path(__file__).resolve().parent.parent / "logs" / "source_status.jsonl"

# (label, href | None, [(href, label)])
NAV = [
    ("Oversikt", "index.html", []),
    ("Aksjer", None, [("rode-flagg.html", "Røde flagg"), ("tickere.html", "Tickere"), ("sektorer.html", "Sektorer"), ("oslo.html", "Oslo")]),
    ("Marked", None, [("makro.html", "Makro"), ("kalender.html", "Kalender")]),
    ("Temaer", "temaer.html", []),
    ("Metode", "metode.html", []),
]

CSS = """
.navgrp{display:flex;flex-direction:column;gap:2px}.navgrp>span{color:#9ea9b5;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;padding:8px 10px 2px}
.navgrp a{padding-left:20px!important}
.xbadge{display:inline-block;border:1px solid #8b949e;color:#c9d1d9;background:transparent;border-radius:2px;padding:0 6px;font-size:.72rem;font-weight:600;vertical-align:middle;margin-left:6px;white-space:nowrap}
.pintro{color:var(--mut);margin:-4px 0 12px}
.kpis.small{margin-bottom:14px}
.kpis.k4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.kpis.k4 .kpi{min-width:0}
@media(max-width:699px){.kpis.k4{grid-template-columns:repeat(2,1fr)}}
.warnline{border-left:3px solid #d29922;padding:6px 10px;margin:0 0 12px;color:#e6edf3;background:rgba(210,153,34,.08);font-size:.9rem}
.stale{color:#d29922;font-weight:600;font-size:.8em;margin-left:6px}
.tsearch{margin:6px 0}.tsearch input{width:100%;min-height:36px;padding:6px 8px;border-radius:4px;border:1px solid #30363d;background:#0d1117;color:#e6edf3;font:inherit}
.ilink{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border:1px solid #9ea9b5;border-radius:50%;font:600 11px/1 system-ui;color:#9ea9b5;cursor:help;margin-left:4px;position:relative}
@media(max-width:699px){.card.tw{overflow-x:auto;max-width:100%}main :not(.xscroll)>table{display:block;overflow-x:auto;max-width:100%}.content,main{min-width:0;max-width:100vw}}
.ilink::after{content:"";position:absolute;inset:-14px}
.info{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;padding:0;margin-left:4px;border:1px solid #9ea9b5;border-radius:50%;background:transparent;color:#9ea9b5;font:600 11px/1 system-ui;cursor:pointer;position:relative;vertical-align:middle}
.info::after{content:"";position:absolute;inset:-14px}.info:focus-visible,.info[aria-expanded=true]{color:#0d1117;background:var(--acc,#6cb6ff);border-color:var(--acc,#6cb6ff)}
.tip{position:fixed;z-index:1000;box-sizing:border-box;width:max-content;max-width:min(280px,calc(100vw - 16px));padding:12px;background:#1c2330;color:#e6edf3;border:1px solid var(--acc,#6cb6ff);border-radius:6px;box-shadow:0 4px 16px rgba(0,0,0,.5);font-size:14px;font-weight:400;line-height:1.45;white-space:normal;overflow-wrap:anywhere;text-align:left;text-transform:none;letter-spacing:normal}
.tip[hidden]{display:none}.tip b{display:block;margin-bottom:4px;font-weight:700}
"""


_TIPN = [0]


def info_tip(text: str, title: str = "") -> str:
    """Felles «i»-komponent: knapp + role=tooltip-boks (ingen title-attributt). Åpnes av TIP_JS."""
    if not text:
        return ""
    _TIPN[0] += 1
    tid = f"tip{_TIPN[0]}"
    lab = f"Hva betyr {title}?" if title else "Forklaring"
    head = f"<b>{E(title)}</b>" if title else ""
    return (f'<button type="button" class="info" aria-label="{E(lab)}" aria-expanded="false" aria-describedby="{tid}">i</button>'
            f'<span role="tooltip" id="{tid}" class="tip" hidden>{head}{E(text)}</span>')


TIP_JS = """<script>(()=>{let cur=null,pinned=false;const d=document,tip=b=>d.getElementById(b.getAttribute('aria-describedby')),btn=e=>e.target&&e.target.closest?e.target.closest('button.info[aria-describedby]'):null;
function show(b){if(cur&&cur!==b)hide(cur);const t=tip(b);if(!t)return;t.hidden=false;const r=b.getBoundingClientRect(),w=t.offsetWidth,h=t.offsetHeight;let top=r.bottom+6;if(top+h>innerHeight-8&&r.top-h-6>8)top=r.top-h-6;
t.style.top=top+'px';t.style.left=Math.max(8,Math.min(r.left-8,innerWidth-w-8))+'px';b.setAttribute('aria-expanded','true');cur=b}
function hide(b){const t=tip(b);if(t)t.hidden=true;b.setAttribute('aria-expanded','false');if(cur===b){cur=null;pinned=false}}
d.addEventListener('pointerover',e=>{const b=btn(e);if(b&&e.pointerType!=='touch'&&cur!==b)show(b)});
d.addEventListener('pointerout',e=>{const b=btn(e);if(b&&!b.contains(e.relatedTarget)&&!(pinned&&cur===b)&&d.activeElement!==b)hide(b)});
d.addEventListener('focusin',e=>{const b=btn(e);if(b)show(b)});
d.addEventListener('focusout',e=>{const b=btn(e);if(b&&!(pinned&&cur===b))hide(b)});
d.addEventListener('click',e=>{const b=btn(e);if(b){e.preventDefault();e.stopPropagation();if(cur===b&&pinned)hide(b);else{show(b);pinned=true}return}if(cur&&!e.target.closest('.tip'))hide(cur)},true);
d.addEventListener('keydown',e=>{if(e.key==='Escape'&&cur)hide(cur)});
const re=()=>{if(cur){const c=cur,k=pinned;show(c);pinned=k}};addEventListener('scroll',re,true);addEventListener('resize',re)})()</script>"""


def xbadge(text: str, tip: str = "") -> str:
    """Grått, firkantet merke (aldri blått/grønt, ikke CLEAR-form)."""
    i = " " + info_tip(tip, text) if tip else ""
    return f'<span class="xbadge">{E(text)}</span>{i}'


EXP = lambda: xbadge("Eksperimentelt · ikke testet", "Temascore er ikke testet mot kursutvikling ennå. Logges daglig (logs/theme_score.csv); treffrate måles ved n ≥ 100.")
RAW = lambda: xbadge("Rådata, ikke signal", "Rå meldinger/registre. Ikke filtrert eller testet som kjøps-/salgssignal.")


def nav_html(cur: str, pre: str) -> str:
    out = []
    for label, href, sub in NAV:
        if href:
            out.append(f'<a class="{"on" if href == cur else ""}" href="{pre}{href}">{E(label)}</a>')
        else:
            on = any(h == cur for h, _ in sub)
            out.append(f'<div class="navgrp"><span{" class=on" if on else ""}>{E(label)}</span>' +
                       "".join(f'<a class="{"on" if h == cur else ""}" href="{pre}{h}">{E(l)}</a>' for h, l in sub) + "</div>")
    return "".join(out)


HASH_JS = ("<script>(()=>{function o(){const h=location.hash.slice(1);if(!h)return;const e=document.getElementById(h);if(!e)return;"
           "let d=e.closest('details');while(d){d.open=true;d=d.parentElement&&d.parentElement.closest('details');}if(e.tagName==='DETAILS')e.open=true;e.scrollIntoView();}"
           "addEventListener('hashchange',o);addEventListener('DOMContentLoaded',o);})()</script>")


def search_html(tickers: list[str], pre: str, slug) -> str:
    if not tickers:
        return HASH_JS
    opts = "".join(f'<option value="{E(t)}">' for t in sorted(set(tickers)))
    m = json.dumps({t: slug(t) for t in tickers})
    return (f'<div class="tsearch"><input list="tk-list" id="tk-q" placeholder="Søk ticker…" aria-label="Søk ticker" autocomplete="off">'
            f'<datalist id="tk-list">{opts}</datalist></div>'
            f'<script>(()=>{{const M={m},q=document.getElementById("tk-q");q.addEventListener("change",()=>{{const v=q.value.trim().toUpperCase();'
            f'const k=Object.keys(M).find(x=>x.toUpperCase()===v);if(k)location.href="{pre}ticker/"+M[k]+".html"}})}})()</script>' + HASH_JS)


def head(title: str, sentence: str, kpis: list[tuple] | None = None, k4: bool = False) -> str:
    """Felles sidetopp: tittel, én setning, nøkkeltall."""
    k = ""
    if kpis:
        k = f'<div class="kpis small{" k4" if k4 else ""}">' + "".join(
            f'<a class="kpi" href="{E(h or "#")}"><div class="lbl">{E(l)}</div><div class="val">{E(v)}</div><div class="sub">{E(s)}</div></a>'
            for v, l, s, h in kpis) + "</div>"
    return f'<h1>{E(title)}</h1><p class="pintro">{E(sentence)}</p>{k}'


# ---------------- treffrate ----------------
def _pc(v, d=1):
    return f"{v * 100:.{d}f}".replace(".", ",")


def watch_text(tr: dict | None) -> str:
    cats = (tr or {}).get("cats") or {}
    w = (cats.get("watch") or {}).get("h5") or {}
    k = (cats.get("kjop") or {}).get("h5") or {}
    if w.get("n") and w.get("hit") is not None:
        ci = w.get("hit_ci") or [None, None]
        sig = ci[0] is not None and ci[0] > 0.5
        wt = (f'Watchlist (5 dager): <b>{_pc(w["hit"])} %</b> (95 %-KI {_pc(ci[0], 0)}–{_pc(ci[1], 0)} %), n={w["n"]}'
              + ("" if sig else ', <span class="xbadge">FLAG: ikke skilt fra tilfeldig</span>'))
    else:
        wt = "Watchlist: n=0, ikke målt ennå"
    kt = f'Kjøp: n={k.get("n") or 0}, ikke målt ennå' if not k.get("n") else f'Kjøp (5 dager): {_pc(k["hit"])} %, n={k["n"]}'
    return f'<p class="mut" style="margin:6px 0 0">Treffrate fra fremoverloggen – {wt}. {kt}. <a href="tickere.html#treffsikkerhet">Detaljer</a></p>'


# ---------------- utdatert-regel ----------------
def load_log(path: Path = LOG) -> list[dict]:
    try:
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    except Exception:
        return []


def staleness(rows: list[dict], source: str, today: date | None = None) -> dict:
    """Per natt (siste kjøring per dato): fail 3 netter på rad => stale; >14 dager uten ok => dead. Partial = ok."""
    today = today or date.today()
    by_day = {}
    for r in rows:
        if r.get("source") == source:
            by_day[r["ts"][:10]] = r            # siste kjøring den dagen vinner
    days = sorted(by_day)
    last_ok = max((d for d in days if by_day[d].get("state") != "fail"), default=None)
    tail = [by_day[d].get("state") for d in days[-3:]]
    stale = len(tail) == 3 and all(s == "fail" for s in tail)
    dead = bool(days) and (last_ok is None and len(days) >= 14 or (last_ok and (today - date.fromisoformat(last_ok)).days > 14))
    return {"stale": stale or dead, "dead": dead, "last_ok": last_ok}


def stale_mark(rows, sources, pre="") -> str:
    for s in sources:
        st = staleness(rows, s)
        if st["stale"]:
            return f'<a class="stale" href="{pre}metode.html#kilder">⏱ Utdatert, data fra {E(st["last_ok"] or "ukjent")}</a>'
    return ""


def is_dead(rows, sources) -> bool:
    return any(staleness(rows, s)["dead"] for s in sources)


def redirect(target: str, title: str) -> str:
    return (f'<!doctype html><html lang="no"><head><meta charset="utf-8"><title>{E(title)}</title>'
            f'<meta http-equiv="refresh" content="0; url={E(target)}"><link rel="canonical" href="{E(target)}"></head>'
            f'<body><p>Flyttet: <a href="{E(target)}">{E(title)}</a></p></body></html>')


_NR = [(r"\brobuste? z(-score[r]?)?", r"z\1 (median/MAD)"), (r"\bRobust krever\b", "Bestått krever"), (r"\bikke robust\b", "ikke bestått testkravet"),
       (r"\bIkke robust\b", "Ikke bestått testkravet"), (r"\brobuste\b", "pålitelige"), (r"\brobust\b", "pålitelig"), (r"\bRobust\b", "Pålitelig")]


def no_robust(h: str) -> str:
    """Rendered text never uses the word «robust» (embedded backtest reports included)."""
    import re
    for a, b in _NR:
        h = re.sub(a, b, h)
    return h
