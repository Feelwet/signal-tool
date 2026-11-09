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
from . import briefing as BR
from . import ux2 as UX2

THEME_LOG = Path(__file__).resolve().parent.parent / "logs" / "theme_score.csv"
CATS = (("kjop", "Kjøp", "#56d364"), ("hold", "Hold", "#6cb6ff"), ("watch", "Følg", "#e3b341"))
MARKET_HREF = "metode.html#regime"   # Markedsregime-kortet (OSEBX/S&P mot 10-mnd snitt) – det flisa viser; HASH_JS åpner folden
MIN_N = 30  # under dette: «For få handler (n=X)» (results.py)

CSS = """
.ov-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:8px 0 14px}
.ov-tile{display:block;background:var(--card,#161b22);border:1px solid #30363d;border-radius:10px;padding:10px 12px;color:inherit;text-decoration:none;min-width:0}
.ov-tile .lbl{font-size:.8em;color:var(--mut)}.ov-tile{position:relative}.ov-tile .stretch{float:right;font-size:1em;text-decoration:none;color:var(--acc,#6cb6ff)}.ov-tile .stretch::after{content:"";position:absolute;inset:0}.ov-tile .sub a.in{position:relative;z-index:1;color:inherit;text-decoration:none;display:inline-block;padding:4px 0}.ov-tile.tap:hover{border-color:var(--acc,#6cb6ff)}.ov-tile .lbl a{color:var(--mut);text-decoration:none}.ov-tile .lbl a:hover{color:var(--acc)}.ov-tile .big{font-size:1.5em;font-weight:700;line-height:1.25;margin:2px 0}
.ov-tile .sub{font-size:.85em;color:var(--mut)}.ov-tile .sub2{font-size:.78em;color:var(--mut);margin-top:3px}
.ov-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 3px 0 6px;vertical-align:middle}.ov-dot.up{background:#56d364}.ov-dot.dn{background:#f85149}
.ov-stack{display:flex;height:12px;border-radius:6px;overflow:hidden;background:#262d38;margin:6px 0 4px}.ov-stack i{display:block;height:100%}
.ov-th{margin:0 0 8px}.ov-th h2{margin:0 0 6px}.ov-bar{display:grid;grid-template-columns:minmax(0,15em) 1fr 3.2em 4em;gap:8px;align-items:center;padding:3px 0;color:inherit;text-decoration:none}
.ov-bar .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ov-bar .tr{background:#262d38;height:10px;border-radius:5px;overflow:hidden}.ov-bar .tr i{display:block;height:100%;background:var(--acc,#6cb6ff)}
.ov-bar .sc{text-align:right;font-variant-numeric:tabular-nums}.ov-bar .wk{font-size:.85em;text-align:right}.ov-bar .wk{color:#94a3b8}
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

.ov-page{font-size:16px;line-height:24px}.ov-page>header,.ov-page>section,.ov-page>.ov-low2{margin:0 0 32px}
.ov-page h2{margin:0 0 16px}.ov-market{display:grid;gap:16px}.ov-market h2{margin:0}.ov-page .ov-market .ov-strip{margin:0;gap:16px}.ov-strip-three{grid-template-columns:repeat(3,minmax(0,1fr))}
.ov-page .ov-candidates{padding:20px;margin:0 0 16px}.ov-page .ov-candidates>h2{margin:0 0 16px}.ov-page .ov-list li{padding:8px 0;gap:16px;align-items:flex-start}.ov-page .ov-list li>span:first-child{overflow:visible;text-overflow:clip;white-space:normal}.ov-page .ov-list .nm{white-space:normal;overflow:visible;text-overflow:clip}.ov-page .ov-list a{min-height:44px;display:inline-flex;align-items:center;white-space:normal}.ov-page .ov-list .tn{line-height:24px}
.ov-entries{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.ov-entries>a{display:flex;flex-direction:column;justify-content:center;min-height:44px;padding:12px 0;border-top:1px solid var(--line);text-decoration:none;color:inherit}.ov-entries span{color:#cbd5e1;font-size:14px;line-height:22px}.ov-page .ov-low2{gap:16px}.ov-page .ov-low2>.ov-low{padding:0}.ov-page .ov-about{display:inline-flex;align-items:center;min-height:44px}.ov-page .ov-tile .lbl>a{display:inline-flex;align-items:center;min-height:44px}body.pg-index .ov-page .ov-tile .sub a.in{display:inline-flex;align-items:center;min-height:44px;padding:0 6px}.ov-page .sc-i{min-width:44px;min-height:44px}.ov-page .ov-low2 a{display:inline-flex;align-items:center;min-height:44px}
@media(max-width:699px){.ov-page>header,.ov-page>section,.ov-page>.ov-low2{margin-bottom:24px}.ov-market .ov-strip{grid-template-columns:minmax(0,1fr)}.ov-entries{grid-template-columns:minmax(0,1fr)}.ov-page .ov-candidates{padding:16px}}
"""


def _slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", t)


def _nb(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def kjop_hit_line(tr: dict | None) -> str:
    """Kjøp-treffrate fra fremoverloggen, med faktisk n. FLAG når n er for lav eller KI ikke skiller fra 50 %."""
    from . import results as RS
    h = (((tr or {}).get("cats") or {}).get("kjop") or {}).get("h5") or {}
    n = int(h.get("n") or 0)
    if not RS.enough(n) or h.get("hit") is None:
        return f'Kjøp-treffrate: {RS.few(n)}'
    ci = h.get("hit_ci") or [None, None]
    ok = ci[0] is not None and ci[0] > 0.5
    ct = RS.control_text((((tr or {}).get("null") or {}).get("cats") or {}).get("kjop"))
    return (f'Kjøp-treffrate 5 d: slo indeks {_nb(h["hit"] * 100, 0)} % (95 %: {_nb(ci[0] * 100, 0)}–{_nb(ci[1] * 100, 0)} %), n={n}'
            + ("" if ok else ", ikke skilt fra tilfeldig") + (f"; {ct}" if ct else "; kontroll: ikke beregnet"))


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


def strip_html(snap: dict, include_calendar: bool = True) -> str:
    reg = snap.get("regime") or {}
    risk = any(v.get("risk_off") for v in reg.values())
    dots = "".join(f'<span class="ov-dot {"dn" if v.get("below") else "up"}"></span>{E(n)}'
                   for k, n in (("OSEBX.OL", "OSEBX"), ("^GSPC", "S&P")) if (v := reg.get(k)))
    t1 = (f'<div class="ov-tile"><div class="lbl"><a href="{MARKET_HREF}">Marked →</a></div><div class="big">{"Halver nye" if risk else "Normalt"}</div>'
          f'<div class="sub">{dots or "regime ukjent"} <span class="mut">mot 10-mnd snitt</span></div></div>') if reg else \
         '<div class="ov-tile"><div class="lbl">Marked</div><div class="big">–</div><div class="sub">ikke beregnet</div></div>'
    tk = candidates(snap)   # UxBot 09.11: populasjonen er kandidatene (samme utvalg som tabellen)
    from . import site_risk as RK
    RC = (("Lav", "lav"), ("Middels", "middels"), ("Høy", "hoy"))
    cnt = {k: sum(1 for e in tk if (e.get("_risk") or {}).get("level") == k) for k, _ in RC}
    k0 = len(tk) - sum(cnt.values())
    # Tre like, nøytrale segmenter med antall. Ingen aktivt trinn: dataene har ikke ett samlet risikonivå (UxBot 09.11);
    # trinnet utledes aldri fra største gruppe.
    t2 = (f'<div class="ov-tile tap"><div class="lbl">Kandidater etter risiko<a class="stretch" href="tickere.html">Vis alle →</a></div>'
          f'<div class="ov-steps" role="group" aria-label="Lav {cnt["Lav"]}, Middels {cnt["Middels"]}, Høy {cnt["Høy"]}">'
          + "".join(f'<a class="in" href="tickere.html?filter={f}">{k} <b>{cnt[k]}</b></a>' for k, f in RC) + '</div>'
          + (f'<div class="sub2 ov-r0">{k0} uten risikonivå</div>' if k0 else "")   # egen grå linje, ikke et fjerde segment
          + f'<div class="sub2 rkl">{E(UX2.RISK_LINE)}{UX2.i(RK.STATUS, "Om risikonivået")}</div>'   # AnalBot 01.11
          '</div>')
    rows, c = EV.red_rows(snap), EV.coverage(snap)
    m = sum(1 for r in rows if EV.ntest(r) >= 2)
    t3 = (f'<div class="ov-tile tap"><div class="lbl">Røde flagg Oslo<a class="stretch" href="tickere.html?filter=flagg">Vis alle →</a></div><div class="big">{m}</div>'
          f'<div class="sub">med 2+ flagg ({len(rows)} totalt)</div><div class="sub2">data per {E(c["asof"] or "–")}</div></div>') if c["n"] else \
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
    return f'<section class="ov-strip{" ov-strip-three" if not include_calendar else ""}" aria-label="Status">{t1}{t2}{t3}{t4 if include_calendar else ""}</section>'


def upcoming(snap: dict, n: int) -> list:
    today = str(snap.get("date") or date.today())
    return sorted([e for e in snap.get("calendar") or [] if str(e.get("date")) >= today], key=lambda e: (str(e["date"]), e.get("time") or ""))[:n]


def _bar(t, mx, wk) -> str:
    s = float(t.get("score") or 0)
    w = min(100, max(2, s / mx * 100))
    ch = wk.get(t["key"])
    # AnalBot 01.11: temascoreendring grå, uten piler og farge (rangering, ikke testet)
    wkh = (f'<span class="wk">{"+" if ch[0] > 0 else "−" if ch[0] < 0 else "±"}{_nb(abs(ch[0]), 1)}</span>'
           if ch else '<span class="wk"></span>')
    return (f'<a class="ov-bar" href="tema/{E(t["key"])}.html"><span class="nm">{E(t["name"])}</span>'
            f'<span class="tr"><i class="mu" style="width:{w:.0f}%"></i></span><span class="sc sc-mu">{_nb(s)}</span>{wkh}</a>')   # dempet (plan 29.10)


def themes_html(snap: dict, wk: dict | None = None, stale: str = "") -> str:
    th = sorted(snap.get("themes") or [], key=lambda x: -(x.get("score") or 0))
    if not th:
        return ""
    wk = week_change(today=str(snap.get("date"))) if wk is None else wk
    mx = max(float(t.get("score") or 0) for t in th) or 1
    note = (f'<span class="mut" style="font-size:.85em">Endring mot {E(next(iter(wk.values()))[1])}. Rangering, ikke testet.</span>' if wk
            else '<span class="mut" style="font-size:.85em">Ukeendring vises når loggen har en uke historikk. Rangering, ikke testet.</span>')
    rest = th[6:]
    more = (f'<details class="vis-alle"><summary>Alle temaer ({len(th)})</summary>{"".join(_bar(t, mx, wk) for t in rest)}'
            f'<p class="mut" style="margin:6px 0 0"><a href="temaer.html">Temaer og temakart →</a></p></details>') if rest else ""
    from .site import score_info   # én ⓘ i overskriften, ikke på hver stolpe (plan 29.10)
    return (f'<section class="card ov-th" id="temascore"><h2>Temascore {score_info("Om temascore")} {stale}{UX2.csrc("GDELT", snap.get("gdelt_latest")) if snap.get("gdelt_latest") else ""}</h2>'
            f'{"".join(_bar(t, mx, wk) for t in th[:6])}<div class="ov-foot">{more}{note}</div></section>')


def candidates_html(snap: dict) -> str:
    tk = sorted([e for e in snap.get("tickers") or [] if e.get("score") is not None], key=lambda e: -e["score"])[:5]
    from . import site_risk as RK
    li = "".join(f'<li><span>{NM.cell(e["ticker"], "ticker/" + _slug(e["ticker"]) + ".html", e.get("name"))} '
                 f'{RK.chip(e.get("_risk"), small=True)}</span><span class="sc-mu" title="Rangering, ikke testet">{_nb(e["score"], 1)} p<span class="score-note">Rangering, ikke testet</span></span></li>' for e in tk)
    from .site import score_info
    left = (f'<div class="card"><h2>Kandidater {score_info()}</h2><ul class="ov-list">{li or "<li class=mut>Ingen.</li>"}</ul>'
            f'<p style="margin:6px 0 0"><a href="tickere.html">Alle tickere →</a></p></div>')
    return left


def two_col_html(snap: dict) -> str:
    left = candidates_html(snap)
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
            items.append(f'<li>{"🔔" if a.get("level") == "alert" else "ⓘ"} <a href="{E(link(a.get("link", "")))}">{E(BR.fix_days_text(a["title"]))}</a></li>')
    for x in ((b.get("changes") or {}).get("items") or []):
        if x.get("kind") in ("ny", "opp", "ned", "tema"):   # kategoriendringer vises ikke (risikorunden); temascore ut av «Endringer» (AnalBot 01.11); logges fortsatt
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


def entries_html() -> str:
    return ('<nav class="ov-entries" aria-label="Undersøk videre">'
            '<a href="temaer.html"><b>Temaer</b><span>Nyhetsoppmerksomhet og temakart</span></a>'
            '<a href="trender.html"><b>Trender</b><span>Dokumentert bruk og selskapskoblinger</span></a></nav>')


# ---------------------------------------------------------------------------------------------------------------------------
# UxBot 09.11 (låst, med AnalBots krav): statuslinje, tre innganger, kompakt kandidattabell og risikotrinn.
# Bare oppsett: tall, signaltekster, merker, sortering og kategoriregler er uendret og leses fra snapshotet (aldri oppdiktet).
SCORE_HEAD = "Score (rangering, ikke testet)"   # AnalBot 09.11: én gang i kolonneoverskriften på PC
TOP_N = 6
NO_FLAG_NOTE = "Bare Oslo-aksjer er sjekket for røde flagg."   # ordrett fra Tickere › Røde flagg

CSS += """
.ov-status{margin:0 0 8px;font-size:14px;line-height:20px;color:#94a3b8}.ov-status .ov-when{white-space:nowrap}
.ov-hmeta{display:flex;flex-wrap:wrap;align-items:center;column-gap:16px}.ov-page .ov-hmeta .pmeta{margin:0}
.ov-page>header .page-intro{margin:0 0 4px}
.ov-go{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.ov-go>a,.ov-go>button{box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;height:56px;min-height:44px;margin:0;padding:6px 12px;background:#111821;border:1px solid #3b4757;border-radius:6px;color:inherit;font:inherit;font-size:16px;line-height:22px;font-weight:600;text-align:left;text-decoration:none;cursor:pointer}
.ov-go>a:hover,.ov-go>button:hover{border-color:var(--acc,#6cb6ff)}.ov-go>button[aria-pressed=true]{border-color:var(--acc,#6cb6ff)}
.ov-go .gsub{display:block;font-size:13px;line-height:18px;font-weight:400;color:#94a3b8}
.ov-fbar{display:flex;flex-wrap:wrap;align-items:center;column-gap:8px;margin:0 0 8px;font-size:14px;line-height:20px}.ov-fbar[hidden]{display:none}
.ov-fbar button{min-height:44px;padding:0 4px;background:none;border:0;color:var(--acc,#6cb6ff);font:inherit;cursor:pointer}.ov-fbar .mut{flex-basis:100%;font-size:13px;line-height:18px}
.ov-page .ov-cand{padding:12px 16px;margin:0 0 16px}.ov-page .ov-cand>h2{margin:0 0 8px}
.ov-page table.ov-ct{display:table;overflow:visible;width:100%;border-collapse:collapse;margin:0}
.ov-ct thead th{position:sticky;top:0;z-index:2;background:var(--bg,#0d1117);font-size:12px;line-height:16px;font-weight:600;color:#94a3b8;text-align:left;padding:8px;white-space:nowrap}
.ov-ct td{padding:8px;vertical-align:middle;border-top:1px solid #21262d}
.ov-ct tr[hidden]{display:none}
.ov-ct .tn{display:block;line-height:20px}.ov-ct .tn .nm{display:block;font-size:15px;line-height:20px;font-weight:600;white-space:normal;overflow:visible;text-overflow:clip}.ov-ct .tn .tk{display:block;font-size:12px;line-height:16px;color:#94a3b8}
.ov-ct .fl{white-space:nowrap;font-size:13px;line-height:18px}.ov-ct .fl.n0{color:#94a3b8}
.ov-ct .sgc{display:inline-flex;align-items:center;gap:4px;max-width:100%;padding:1px 8px;border-radius:999px;border:1px solid #333b47;background:var(--pill,#1c2430);font-size:12px;line-height:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ov-ct .sc{white-space:nowrap;font-variant-numeric:tabular-nums;color:#94a3b8}.ov-ct .sc .sl,.ov-ct .sc .snt{display:none}
.ov-ct .rt{white-space:nowrap;font-variant-numeric:tabular-nums;font-size:13px;line-height:18px}.ov-ct .ov-ret{display:inline-block;padding:0 4px;border-radius:4px}.ov-ct .ov-ret.tup{background:rgba(63,185,80,.12)}.ov-ct .ov-ret.tdn{background:rgba(248,81,73,.12)}
.ov-more{min-height:44px;margin:4px 0 0;padding:0;background:none;border:0;color:var(--acc,#6cb6ff);font:inherit;cursor:pointer}.ov-more[hidden]{display:none}
.ov-steps{display:flex;gap:2px;margin:4px 0}.ov-steps a{flex:1 1 0;display:flex;align-items:center;justify-content:center;gap:4px;min-height:44px;border-radius:4px;background:#1c2430;color:#cbd5e1;font-size:12px;line-height:16px;text-decoration:none}
.ov-steps a{position:relative;z-index:1}body.pg-index .ov-tile .sub2.ov-r0,.ov-tile .sub2.ov-r0{display:block;margin:2px 0 0;font-size:13px;line-height:18px;color:#94a3b8}.ov-steps a b{font-weight:600}
@media(max-width:699px){
.ov-go{grid-template-columns:minmax(0,1fr)}
.ov-page>header,.ov-page>section.ov-entry{margin-bottom:16px}.ov-page .ov-cand{padding:12px}
.ov-page table.ov-ct,.ov-ct tbody{display:block;width:100%}.ov-ct thead{display:none}
.ov-ct tr{display:grid;grid-template-columns:auto auto minmax(0,1fr) auto;grid-template-areas:"nm nm nm nm" "rk fl sg sg" "sc sc sc rt";gap:4px 8px;align-items:center;padding:8px 0;border-top:1px solid #21262d}
.ov-ct tr[hidden]{display:none}
.ov-ct td{display:block;padding:0;border:0;min-width:0}
.ov-ct td.nmc{grid-area:nm}.ov-ct td.rkc{grid-area:rk}.ov-ct td.fl{grid-area:fl}.ov-ct td.sgt{grid-area:sg}.ov-ct td.sc{grid-area:sc}.ov-ct td.rt{grid-area:rt;justify-self:end}
.ov-ct .tn .nm{display:inline;font-size:15px;line-height:20px}.ov-ct .tn .tk{display:inline;margin-left:6px}
.ov-ct .sc{font-size:13px;line-height:18px}.ov-ct .sc .sl,.ov-ct .sc .snt{display:inline}
}
"""


def _flag_state(snap: dict) -> tuple[set, dict]:
    """(sjekkede Oslo-tickere, {ticker: flaggrad}) fra samme snapshot som kandidattabellen."""
    return {r.get("ticker") for r in snap.get("oslo_universe_flags") or []}, {r["ticker"]: r for r in EV.red_rows(snap)}


def candidates(snap: dict) -> list:
    """Kandidattabellens rader: samme utvalg og sortering som før (har score, høyest først)."""
    return sorted([e for e in snap.get("tickers") or [] if e.get("score") is not None], key=lambda e: -e["score"])


def status_line_html(snap: dict) -> str:
    """«{n} kandidater · {m} med 2+ flagg · Oppdatert {dato kl}» – n, m og tidspunkt fra samme snapshot som tabellen (AnalBot 09.11)."""
    tk = candidates(snap)
    _, fm = _flag_state(snap)
    m = sum(1 for e in tk if e["ticker"] in fm and EV.ntest(fm[e["ticker"]]) >= 2)
    parts = [E(f"{len(tk)} kandidat{'' if len(tk) == 1 else 'er'}"), E(f"{m} med 2+ flagg")]
    from .site import gen_short
    if snap.get("generated"):   # snap["generated"] er lokal Oslo-tid; tidspunkt + sone brytes aldri (UxBot 09.11)
        parts.append(f'<span class="ov-when">Oppdatert {E(gen_short(snap["generated"]).replace(" ", " kl. ", 1))} Oslo-tid</span>')
    return f'<p class="ov-status">{" · ".join(parts)}</p>'


def go_html() -> str:
    """Tre like innganger (UxBot 09.11). «Kandidater uten røde flagg» er bare et filter – samme utseende, ingen farge eller ikon."""
    return ('<nav class="ov-go" aria-label="Snarveier">'
            '<button type="button" class="go-nf" aria-pressed="false" aria-controls="kandidater">Kandidater uten røde flagg</button>'
            f'<a href="temaer.html">Høyest temascore<span class="gsub">{E(THEME_SUB)}</span></a>'
            '<a href="tickere.html?filter=flagg">Røde flagg Oslo</a></nav>')


SCORE_TIP_TEXT = "Rangering, ikke testet"
THEME_SUB = "Temaets score · " + SCORE_TIP_TEXT   # UxBot 09.11: temaets score, ikke kandidatens; AnalBots ordlyd intakt


def _ret(label: str, x) -> str:
    if x is None:
        return f'<span class="ov-ret">{label} –</span>'
    return f'<span class="ov-ret {"tup" if x > 0 else "tdn" if x < 0 else ""}">{label} {x*100:+.1f}%</span>'   # samme format og farger som 5d/20d i Tickere


def _main_signal(e: dict) -> str:
    from .site import POINT_NO
    from . import evidens_status as ES
    pts = [(k, v) for k, v in (e.get("points") or {}).items() if v and v > 0]
    if e.get("unranked") or not pts:
        return '<span class="mut">–</span>'
    k = max(pts, key=lambda kv: kv[1])[0]
    d, lab = ES.dot(k)
    nm = POINT_NO.get(k, k)
    return f'<span class="sgc" title="{E(nm + (". " + lab if lab else ""))}">{d}{E(nm)}</span>'


def _flag_cell(t: str, checked: set, fm: dict) -> tuple[str, bool]:
    if t in fm:
        return f'<td class="fl">⚑ {E(EV.nlabel(fm[t]))}</td>', False
    if t in checked:
        return '<td class="fl n0">0 flagg</td>', True
    return '<td class="fl n0">ikke sjekket</td>', False


def candidates_table_html(snap: dict) -> str:
    from . import site_risk as RK
    tk = candidates(snap)
    checked, fm = _flag_state(snap)
    rows = []
    for i, e in enumerate(tk):
        t = e["ticker"]
        fl, nf = _flag_cell(t, checked, fm)
        st = e.get("stats") or {}
        rt = "–" if e.get("unranked") else _ret("5d", st.get("ret_5d")) + " " + _ret("20d", st.get("ret_20d"))
        rows.append(f'<tr data-nf="{1 if nf else 0}"{" class=\"more\" hidden" if i >= TOP_N else ""}>'
                    f'<td class="nmc">{NM.cell(t, "ticker/" + _slug(t) + ".html", e.get("name"))}</td>'
                    f'<td class="rkc">{RK.chip(e.get("_risk"), small=True)}</td>{fl}<td class="sgt">{_main_signal(e)}</td>'
                    f'<td class="sc"><span class="sl">Score </span><span class="sv">{_nb(e["score"], 1)}</span><span class="snt"> · ikke testet</span></td>'
                    f'<td class="rt">{rt}</td></tr>')
    more = (f'<button type="button" class="ov-more" aria-expanded="false">Vis alle ({len(tk)})</button>' if len(tk) > TOP_N else "")
    head = (f'<thead><tr><th scope="col">Aksje</th><th scope="col">Risiko</th><th scope="col">Røde flagg</th><th scope="col">Hovedsignal</th>'
            f'<th scope="col">{E(SCORE_HEAD)}</th><th scope="col">5d / 20d</th></tr></thead>')
    fbar = (f'<p class="ov-fbar" hidden>Filter: 0 røde flagg · <button type="button" class="ov-clear">Vis alle</button>'
            f'<span class="mut">{E(NO_FLAG_NOTE)}</span></p>')
    empty = '<p class="ov-none mut" hidden>Ingen kandidater uten røde flagg nå.</p>'
    body = (f'<table class="ov-ct">{head}<tbody>{"".join(rows)}</tbody></table>' if rows else '<p class="mut">Ingen.</p>')
    return (f'<div class="card ov-candidates ov-cand" id="kandidater"><h2>Kandidater</h2>{fbar}{empty}{body}{more}'
            f'<p style="margin:6px 0 0"><a href="tickere.html">Alle tickere →</a></p></div>{CAND_JS}')


CAND_JS = """<script>(()=>{const c=document.getElementById('kandidater');if(!c)return;const R=[...c.querySelectorAll('.ov-ct tbody tr')],
M=c.querySelector('.ov-more'),F=c.querySelector('.ov-fbar'),N=c.querySelector('.ov-none'),G=document.querySelector('.ov-go .go-nf');let all=false,nf=false;
function draw(){let n=0;R.forEach((r,i)=>{const on=nf?r.dataset.nf==='1':(all||i<""" + str(TOP_N) + """);r.hidden=!on;if(on)n++});
if(F)F.hidden=!nf;if(N)N.hidden=!(nf&&n===0);if(M){M.hidden=nf;M.setAttribute('aria-expanded',all?'true':'false');M.textContent=all?'Vis færre':'Vis alle ('+R.length+')'}
if(G)G.setAttribute('aria-pressed',nf?'true':'false')}
if(M)M.addEventListener('click',()=>{all=!all;draw()});
const clr=c.querySelector('.ov-clear');if(clr)clr.addEventListener('click',()=>{nf=false;draw()});
if(G)G.addEventListener('click',()=>{nf=!nf;draw();if(nf)c.scrollIntoView({block:'start'})});draw()})()</script>"""
