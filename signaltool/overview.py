"""Oversikt (index.html): statusstripe, temascore, kandidater + røde flagg, endringer og varsler, kalender.
Kun ekte data fra snapshot/logger; mangler tallet, vises ingenting (aldri oppdiktede verdier)."""
from __future__ import annotations

import csv
import re
from datetime import date, timedelta
from html import escape as E
from pathlib import Path

from . import evidens as EV
from . import site_layout as L
from . import names as NM

THEME_LOG = Path(__file__).resolve().parent.parent / "logs" / "theme_score.csv"
CATS = (("kjop", "Kjøp", "#56d364"), ("hold", "Hold", "#6cb6ff"), ("watch", "Følg", "#e3b341"))
MIN_N = 30  # under dette: «n for lav (FLAG)»

CSS = """
.ov-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:8px 0 14px}
.ov-tile{display:block;background:var(--card,#161b22);border:1px solid #30363d;border-radius:10px;padding:10px 12px;color:inherit;text-decoration:none;min-width:0}
.ov-tile .lbl{font-size:.8em;color:var(--mut)}.ov-tile{position:relative}.ov-tile .stretch{float:right;font-size:1em;text-decoration:none;color:var(--acc,#6cb6ff)}.ov-tile .stretch::after{content:"";position:absolute;inset:0}.ov-tile .sub a.in{position:relative;z-index:1;color:inherit;text-decoration:none;display:inline-block;padding:4px 0}.ov-tile.tap:hover{border-color:var(--acc,#6cb6ff)}.ov-tile .lbl a{color:var(--mut);text-decoration:none}.ov-tile .lbl a:hover{color:var(--acc)}.ov-tile .big{font-size:1.5em;font-weight:700;line-height:1.25;margin:2px 0}
.ov-tile .sub{font-size:.85em;color:var(--mut)}.ov-tile .sub2{font-size:.78em;color:var(--mut);margin-top:3px}
.ov-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 3px 0 6px;vertical-align:middle}.ov-dot.up{background:#56d364}.ov-dot.dn{background:#f85149}
.ov-stack{display:flex;height:12px;border-radius:6px;overflow:hidden;background:#262d38;margin:6px 0 4px}.ov-stack i{display:block;height:100%}
.ov-th{margin:0 0 8px}.ov-th h2{margin:0 0 6px}.ov-bar{display:grid;grid-template-columns:minmax(0,15em) 1fr 3.2em 4em;gap:8px;align-items:center;padding:3px 0;color:inherit;text-decoration:none}
.ov-bar .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ov-bar .tr{background:#262d38;height:10px;border-radius:5px;overflow:hidden}.ov-bar .tr i{display:block;height:100%;background:var(--acc,#6cb6ff)}
.ov-bar .sc{text-align:right;font-variant-numeric:tabular-nums}.ov-bar .wk{font-size:.85em;text-align:right}.ov-bar .wk.u{color:#56d364}.ov-bar .wk.d{color:#f85149}
.ov-2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 14px}.ov-2 .card{margin:0}.ov-2 h2{margin:0 0 6px;font-size:1.05em}
.ov-list{list-style:none;margin:0;padding:0}.ov-list li{display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px solid #21262d;min-width:0}
.ov-list li>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ov-low h2{font-size:1.05em;margin:0 0 6px}
.ov-th,.ov-2 .card,.ov-low{padding:10px 14px}.ov-th h2,.ov-2 h2,.ov-low h2{font-size:1.05em;margin:0 0 4px}.ov-bar{padding:0;line-height:1.28}
.ov-list li{padding:1px 0;align-items:center}.ov-list .tn{line-height:1.12}.ov-list .tn .tk{font-size:11px}.ov-2 .card>p{margin:4px 0 0!important}.ov-list li>span:last-child{white-space:nowrap;flex:none}.ov-th .vis-alle{margin:0}.ov-foot{display:flex;flex-wrap:wrap;gap:4px 16px;align-items:baseline;margin-top:4px}.ov-foot details[open]{flex-basis:100%}.ov-strip{margin:2px 0 8px}.ov-2>*,.ov-strip>*,.ov-th{min-width:0}.ov-tile{padding:8px 12px}.ov-tile .big{font-size:1.3em;margin:0}.ov-2{margin:0 0 10px}
@media(max-width:599px){.ov-bar{grid-template-columns:1fr auto auto;row-gap:2px;padding:3px 0}.ov-bar .nm{grid-column:1/-1;white-space:normal}}
@media(min-width:600px) and (max-width:699px){.ov-bar{grid-template-columns:minmax(0,1fr) 30% 2.6em 3.4em}}
@media(max-width:699px){.ov-strip{grid-template-columns:1fr 1fr}.ov-2{grid-template-columns:1fr}}
.ov-low2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.ov-low2>*{margin:0;min-width:0}@media(max-width:699px){.ov-low2{grid-template-columns:1fr}}
"""


def _slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", t)


def _nb(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def kjop_hit_line(tr: dict | None) -> str:
    """Kjøp-treffrate fra fremoverloggen, med faktisk n. FLAG når n er for lav eller KI ikke skiller fra 50 %."""
    h = (((tr or {}).get("cats") or {}).get("kjop") or {}).get("h5") or {}
    n = int(h.get("n") or 0)
    if n < MIN_N or h.get("hit") is None:
        return f'Kjøp-treffrate: n={n}, for lav (FLAG)'
    ci = h.get("hit_ci") or [None, None]
    ok = ci[0] is not None and ci[0] > 0.5
    return f'Kjøp-treffrate 5 d: {_nb(h["hit"] * 100, 0)} %, n={n}' + ("" if ok else " (FLAG: ikke skilt fra tilfeldig)")


def week_change(path: Path = THEME_LOG, today: str | None = None) -> dict:
    """Endring i temascore mot loggført verdi 5–9 dager tidligere (nærmest 7). Tom dict hvis loggen mangler slik historikk."""
    try:
        rows = list(csv.DictReader(path.open()))
    except Exception:
        return {}
    by = {}
    for r in rows:
        try:
            by.setdefault(r["date"], {})[r["theme"]] = float(r["score"])
        except (KeyError, ValueError, TypeError):
            continue
    if not by:
        return {}
    t = date.fromisoformat(today or max(by))
    cands = [d for d in by if 5 <= (t - date.fromisoformat(d)).days <= 9]
    if not cands or str(t) not in by:
        return {}
    ref = min(cands, key=lambda d: abs((t - date.fromisoformat(d)).days - 7))
    return {k: (v - by[ref][k], ref) for k, v in by[str(t)].items() if k in by[ref]}


def strip_html(snap: dict) -> str:
    reg = snap.get("regime") or {}
    risk = any(v.get("risk_off") for v in reg.values())
    dots = "".join(f'<span class="ov-dot {"dn" if v.get("below") else "up"}"></span>{E(n)}'
                   for k, n in (("OSEBX.OL", "OSEBX"), ("^GSPC", "S&P")) if (v := reg.get(k)))
    t1 = (f'<div class="ov-tile"><div class="lbl"><a href="metode.html#regler">Marked →</a></div><div class="big">{"Halver nye" if risk else "Normalt"}</div>'
          f'<div class="sub">{dots or "regime ukjent"} <span class="mut">mot 10-mnd snitt</span></div></div>') if reg else \
         '<div class="ov-tile"><div class="lbl">Marked</div><div class="big">–</div><div class="sub">ikke beregnet</div></div>'
    tk = snap.get("tickers") or []
    from . import site_risk as RK
    RC = (("Høy", "hoy", "#FEE2E2"), ("Middels", "middels", "#FEF3C7"), ("Lav", "lav", "#DCFCE7"))
    cnt = {k: sum(1 for e in tk if (e.get("_risk") or {}).get("level") == k) for k, _, _ in RC}
    tot = sum(cnt.values()) or 1
    seg = "".join(f'<i style="width:{cnt[k] / tot * 100:.1f}%;background:{c}"></i>' for k, _, c in RC if cnt[k])
    t2 = (f'<div class="ov-tile tap"><div class="lbl">Risikonivå<a class="stretch" href="tickere.html">Vis alle →</a></div><div class="big">{cnt["Høy"]} Høy</div>'
          f'<div class="ov-stack" role="img" aria-label="Høy {cnt["Høy"]}, Middels {cnt["Middels"]}, Lav {cnt["Lav"]}">{seg}</div>'
          f'<div class="sub">' + " · ".join(f'<a class="in" href="tickere.html?filter={f}">{k} {cnt[k]}</a>' for k, f, _ in RC) + '</div>'
          f'<div class="sub2">{E(RK.STATUS)}</div>'
          '</div>')
    rows, c = EV.red_rows(snap), EV.coverage(snap)
    m = sum(1 for r in rows if EV.ntest(r) >= 2)
    t3 = (f'<div class="ov-tile tap"><div class="lbl">Røde flagg Oslo<a class="stretch" href="tickere.html?filter=flagg">Vis alle →</a></div><div class="big">{m}</div>'
          f'<div class="sub">med 2+ flagg ({len(rows)} totalt)</div></div>') if c["n"] else \
         '<div class="ov-tile"><div class="lbl"><a href="tickere.html?filter=flagg">Røde flagg Oslo →</a></div><div class="big">–</div><div class="sub">ikke beregnet</div></div>'
    nx = upcoming(snap, 1)
    if nx:
        e = nx[0]
        d = date.fromisoformat(str(e["date"])[:10])
        dd = (d - date.fromisoformat(str(snap.get("date"))[:10])).days
        when = "I dag" if dd == 0 else "I morgen" if dd == 1 else f"Om {dd} d"
        t4 = (f'<div class="ov-tile"><div class="lbl"><a href="kalender.html">Neste hendelse →</a></div><div class="big">{when}</div>'
              f'<div class="sub">{E(e["title"])}</div></div>')
    else:
        t4 = '<div class="ov-tile"><div class="lbl"><a href="kalender.html">Neste hendelse →</a></div><div class="big">–</div><div class="sub">ingen i kalenderen</div></div>'
    return f'<section class="ov-strip" aria-label="Status">{t1}{t2}{t3}{t4}</section>'


def upcoming(snap: dict, n: int) -> list:
    today = str(snap.get("date") or date.today())
    return sorted([e for e in snap.get("calendar") or [] if str(e.get("date")) >= today], key=lambda e: (str(e["date"]), e.get("time") or ""))[:n]


def _bar(t, mx, wk) -> str:
    s = float(t.get("score") or 0)
    w = min(100, max(2, s / mx * 100))
    ch = wk.get(t["key"])
    wkh = (f'<span class="wk {"u" if ch[0] > 0 else "d" if ch[0] < 0 else ""}">{"▲" if ch[0] > 0 else "▼" if ch[0] < 0 else "="}{_nb(abs(ch[0]), 1)}</span>'
           if ch else '<span class="wk"></span>')
    return (f'<a class="ov-bar" href="tema/{E(t["key"])}.html"><span class="nm">{E(t["name"])}</span>'
            f'<span class="tr"><i style="width:{w:.0f}%"></i></span><span class="sc">{_nb(s)}</span>{wkh}</a>')


def themes_html(snap: dict, wk: dict | None = None, stale: str = "") -> str:
    th = sorted(snap.get("themes") or [], key=lambda x: -(x.get("score") or 0))
    if not th:
        return ""
    wk = week_change(today=str(snap.get("date"))) if wk is None else wk
    mx = max(float(t.get("score") or 0) for t in th) or 1
    note = (f'<span class="mut" style="font-size:.85em">▲/▼ = endring mot {E(next(iter(wk.values()))[1])}</span>' if wk
            else '<span class="mut" style="font-size:.85em">Ukeendring vises når loggen har en uke historikk.</span>')
    rest = th[6:]
    more = (f'<details class="vis-alle"><summary>Alle temaer ({len(th)})</summary>{"".join(_bar(t, mx, wk) for t in rest)}'
            f'<p class="mut" style="margin:6px 0 0"><a href="temaer.html">Temaer og temakart →</a></p></details>') if rest else ""
    return (f'<section class="card ov-th" id="temascore"><h2>Temascore {L.EXP()} {stale}</h2>'
            f'{"".join(_bar(t, mx, wk) for t in th[:6])}<div class="ov-foot">{more}{note}</div></section>')


def two_col_html(snap: dict) -> str:
    tk = sorted([e for e in snap.get("tickers") or [] if e.get("score") is not None], key=lambda e: -e["score"])[:5]
    from . import site_risk as RK
    li = "".join(f'<li><span>{NM.cell(e["ticker"], "ticker/" + _slug(e["ticker"]) + ".html", e.get("name"))} '
                 f'{RK.chip(e.get("_risk"), small=True)}</span><span class="mut">{_nb(e["score"], 1)} p</span></li>' for e in tk)
    left = (f'<div class="card"><h2>Kandidater</h2><ul class="ov-list">{li or "<li class=mut>Ingen.</li>"}</ul>'
            f'<p style="margin:6px 0 0"><a href="tickere.html">Alle tickere →</a></p></div>')
    rows, c = EV.red_rows(snap), EV.coverage(snap)
    rl = "".join(f'<li><span>{NM.cell(r["ticker"])}</span>'
                 f'<span class="mut">{E(EV.nlabel(r))}</span></li>' for r in rows[:5])
    right = (f'<div class="card"><h2>Røde flagg Oslo</h2><ul class="ov-list">{rl or "<li class=mut>Ingen.</li>"}</ul>'
             f'<p style="margin:6px 0 0"><a href="tickere.html?filter=flagg">Se alle ({len(rows)}) →</a> <span class="mut">data per {E(c["asof"] or "–")}</span></p></div>') if c["n"] else \
            '<div class="card"><h2>Røde flagg Oslo</h2><p class="mut">Ikke beregnet i denne kjøringen.</p></div>'
    return f'<section class="ov-2">{left}{right}</section>'


NOTICE = "HAS, CLF: Kjøp trukket tilbake. Regelen på siden var ikke den som ble testet. Ny test før den slås på igjen."
NOTICE_UNTIL = "2026-11-01"


def changes_alerts_html(snap: dict, link=lambda x: x) -> str:
    b = snap.get("briefing") or {}
    items, seen = [], set()
    if False and str(snap.get("date") or "") <= NOTICE_UNTIL:   # Kjøp vises ikke lenger (risikorunden)   # fast melding i 7 dager (t.o.m. 01.11.2026)
        items.append(f'<li>ⓘ {E(NOTICE)}</li>')
    for a in b.get("alerts") or []:
        k = a["title"].split(":")[0].strip().lower()
        if k not in seen:
            seen.add(k)
            items.append(f'<li>{"🔔" if a.get("level") == "alert" else "ⓘ"} <a href="{E(link(a.get("link", "")))}">{E(a["title"])}</a></li>')
    for x in ((b.get("changes") or {}).get("items") or []):
        if x.get("kind") in ("ny", "opp", "ned"):   # kategoriendringer vises ikke (risikorunden); logges fortsatt
            continue
        items.append(f'<li>{"🔔 " if x.get("level") == "alert" else ""}{change_text(x["text"])}</li>')
    if not items:
        return ""
    pd = (b.get("changes") or {}).get("prev_date")
    return (f'<div class="card ov-low" id="endringer"><h2>Endringer og varsler{f" <span class=mut style=font-weight:400>siden {E(pd)}</span>" if pd else ""}</h2>'
            f'<ul class="ev" style="margin:0">{"".join(items[:5])}</ul></div>')


_ARROW = re.compile(r"^(.*?):?\s*score\s+(-?\d+(?:[.,]\d+)?)\s*→\s*(-?\d+(?:[.,]\d+)?)\s*$")


def change_text(t: str) -> str:
    """«Tema «X»: score 1.48 → 2.48» → «Tema «X» ▲1,00 (nå 2,48)». Bare tall fra teksten; ellers uendret."""
    m = _ARROW.match(t or "")
    if not m:
        return E(t)
    a, b = (float(x.replace(",", ".")) for x in m.group(2, 3))
    d = b - a
    ar, cl = ("▲", "up") if d > 0 else ("▼", "down") if d < 0 else ("=", "mut")
    return f'{E(m.group(1).rstrip(": "))} <span class="{cl}">{ar}{_nb(abs(d))}</span> <span class="mut">(nå {_nb(b)})</span>'


def calendar_html(snap: dict) -> str:
    nx = upcoming(snap, 3)
    if not nx:
        return ""
    return ('<div class="card ov-low"><h2>Kalender</h2><ul class="ev" style="margin:0">'
            + "".join(f'<li>{E(e["date"])} {E(e.get("time") or "")} – {E(e["title"])} <span class="mut">({E(e["source"])})</span></li>' for e in nx)
            + '</ul><a href="kalender.html">Hele kalenderen →</a></div>')
