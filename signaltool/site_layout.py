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
    ("Aksjer", None, [("tickere.html", "Tickere"), ("sektorer.html", "Sektorer"), ("oslo.html", "Oslo")]),
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
.warnline{border-left:3px solid #d29922;padding:6px 10px;margin:0 0 12px;color:#e6edf3;background:rgba(210,153,34,.08);font-size:.9rem}
.stale{color:#d29922;font-weight:600;font-size:.8em;margin-left:6px}
.tsearch{margin:6px 0}.tsearch input{width:100%;min-height:36px;padding:6px 8px;border-radius:4px;border:1px solid #30363d;background:#0d1117;color:#e6edf3;font:inherit}
.ilink{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border:1px solid #9ea9b5;border-radius:50%;font:600 11px/1 system-ui;color:#9ea9b5;cursor:help;margin-left:4px;position:relative}
@media(max-width:699px){.card.tw{overflow-x:auto;max-width:100%}main :not(.xscroll)>table{display:block;overflow-x:auto;max-width:100%}.content,main{min-width:0;max-width:100vw}}
.ilink::after{content:"";position:absolute;inset:-14px}
"""


def xbadge(text: str, tip: str = "") -> str:
    """Grått, firkantet merke (aldri blått/grønt, ikke CLEAR-form)."""
    i = f' <span class="ilink" tabindex="0" role="img" aria-label="{E(tip)}" title="{E(tip)}">i</span>' if tip else ""
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


def head(title: str, sentence: str, kpis: list[tuple] | None = None) -> str:
    """Felles sidetopp: tittel, én setning, nøkkeltall."""
    k = ""
    if kpis:
        k = '<div class="kpis small">' + "".join(
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
