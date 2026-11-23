"""Tickere-listen med filter på risiko, sektor og børs (UxBot 17.11). Tilstand i URL og localStorage."""
from __future__ import annotations

import csv
import re
import unicodedata
from datetime import date
from functools import lru_cache
from html import escape as E
from pathlib import Path

from . import evidens as EV
from . import names as NM
from . import site_risk as RK
from .bors import UKJENT_BORS, bors_of as _bors_of, bors_slug as _bors_slug
from .config import LOGS
from .mine import EMPTY

# Yahoo-sektor og offisiell GICS-sektor → de 11 GICS-sektorene på norsk.
# Mangler eller ukjent verdi blir «Ukjent sektor». Aldri gjett.
GICS_NO = {
    "Energy": "Energi",
    "Materials": "Råvarer",
    "Basic Materials": "Råvarer",
    "Industrials": "Industri",
    "Consumer Discretionary": "Syklisk forbruk",
    "Consumer Cyclical": "Syklisk forbruk",
    "Consumer Staples": "Defensivt forbruk",
    "Consumer Defensive": "Defensivt forbruk",
    "Health Care": "Helse",
    "Healthcare": "Helse",
    "Financials": "Finans",
    "Financial Services": "Finans",
    "Information Technology": "Teknologi",
    "Technology": "Teknologi",
    "Communication Services": "Kommunikasjon",
    "Utilities": "Forsyning",
    "Real Estate": "Eiendom",
}
SEKTOR_NAV = (
    "Energi", "Råvarer", "Industri", "Syklisk forbruk", "Defensivt forbruk",
    "Helse", "Finans", "Teknologi", "Kommunikasjon", "Forsyning", "Eiendom",
    "Ukjent sektor",
)
UKJENT_SEKTOR = "Ukjent sektor"
RISIKO_NAV = (("hoy", "Høy"), ("middels", "Middels"), ("lav", "Lav"), ("ingen", "Ingen risikonivå"))
BORS_NAV = (
    ("oslo", "Oslo"), ("usa", "USA"), ("tyskland", "Tyskland"),
    ("danmark", "Danmark"), ("sverige", "Sverige"), ("storbritannia", "Storbritannia"),
    ("japan", "Japan"), ("taiwan", "Taiwan"), ("ukjent-bors", "Ukjent børs"),
)
RISK_CAVEAT = "Risikonivå er rangert innen hver børs."
ANNET_NAV = (("mine", "★ Mine"), ("flagg", "Røde flagg"), ("ny", "Ingen avkastning"))
CAT_OF = {"hoy": "Høy", "middels": "Middels", "lav": "Lav"}
BORS_FROM_MARKET = {
    "Oslo": "Oslo", "OSLO": "Oslo",
    "US": "USA", "USA": "USA",
    "DE": "Tyskland", "Germany": "Tyskland", "Tyskland": "Tyskland",
}
LS_KEY = "signaltool.tickere-filter"
# Eldre enkle filtre (oversikt, rode-flagg.html, ?mine=…-import)
LEGACY_FILTER = {
    "hoy": ("risiko", "hoy"),
    "middels": ("risiko", "middels"),
    "lav": ("risiko", "lav"),
    "flagg": ("annet", "flagg"),
    "mine": ("annet", "mine"),
    "ny": ("annet", "ny"),
}

FILTERS = (("mine", "★ Mine"), ("alle", "Alle"), ("hoy", "Høy"), ("middels", "Middels"), ("lav", "Lav"), ("flagg", "Røde flagg"))
NAME = dict(FILTERS)


def _slug(s: str) -> str:
    t = (s or "").strip().lower().replace("æ", "ae").replace("ø", "o").replace("å", "a")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


SEKTOR_SLUG = {n: _slug(n) for n in SEKTOR_NAV}
SLUG_SEKTOR = {v: k for k, v in SEKTOR_SLUG.items()}


def sektor_label(raw) -> str:
    """Oversett snapshotets sektor til norsk GICS-navn. Tom eller ukjent → «Ukjent sektor»."""
    s = (raw or "").strip() if isinstance(raw, str) else ("" if raw is None else str(raw).strip())
    if not s:
        return UKJENT_SEKTOR
    return GICS_NO.get(s) or GICS_NO.get(s.title()) or UKJENT_SEKTOR


def sektor_of(e: dict | None) -> str:
    d = (e or {}).get("decision") or {}
    return sektor_label(d.get("sector") if isinstance(d, dict) else None)


def sektor_slug(e: dict | None) -> str:
    return SEKTOR_SLUG[sektor_of(e)]


@lru_cache(maxsize=1)
def markets_from_csv(path: str | None = None) -> dict[str, str]:
    """Siste kjente market-verdi per ticker fra logs/risk_levels.csv. Tom dict hvis fila mangler."""
    p = Path(path) if path else (LOGS / "risk_levels.csv")
    if not p.exists():
        return {}
    last: dict[str, tuple[str, str]] = {}
    with p.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t, d, m = (r.get("ticker") or "").strip(), r.get("date") or "", (r.get("market") or "").strip()
            if t and m and d >= last.get(t, ("", ""))[0]:
                last[t] = (d, m)
    return {t: v[1] for t, v in last.items()}


def bors_of(ticker: str, market: str | None = None, use_csv: bool = True) -> str:
    """Børs fra tickersuffiks alene. market og use_csv ignoreres (beholdt for kallsteder)."""
    return _bors_of(ticker)


def bors_slug(ticker: str, market: str | None = None, use_csv: bool = True) -> str:
    return _bors_slug(ticker)


def bors_of_entry(e: dict | None, use_csv: bool = True) -> str:
    return _bors_of((e or {}).get("ticker") or "")


def row_meta(e: dict) -> dict:
    """Filterfelter for én ticker-rad (slugs + flagg)."""
    tkr = e.get("ticker") or ""
    rk = e.get("_risk") if isinstance(e.get("_risk"), dict) else None
    lv = RK.shown_level(rk, tkr)
    risiko = next((k for k, lab in RISIKO_NAV if lab == lv), "ingen")
    return {
        "ticker": tkr,
        "name": e.get("name") or "",
        "risiko": risiko,
        "sektor": sektor_slug(e),
        "bors": bors_slug(tkr),
        "flag": bool(e.get("_flag")),
        "ny": bool((e.get("_ret") or {}).get("new")),
        "mine": False,
        "risk": bool(lv),
    }


def matches(row: dict, flt: dict) -> bool:
    """ELLER innen gruppe, OG på tvers. Søk og ★ Mine kombineres med alt."""
    def group(key: str, val: str) -> bool:
        sel = [x for x in (flt.get(key) or []) if x]
        return (not sel) or (val in sel)
    if not group("risiko", row.get("risiko") or ""):
        return False
    if not group("sektor", row.get("sektor") or ""):
        return False
    if not group("bors", row.get("bors") or ""):
        return False
    annet = [x for x in (flt.get("annet") or []) if x]
    if "mine" in annet and not row.get("mine"):
        return False
    if "flagg" in annet and not row.get("flag"):
        return False
    if "ny" in annet and not row.get("ny"):
        return False
    q = (flt.get("q") or "").strip().lower()
    if q:
        tk = (row.get("ticker") or "").lower()
        nm = (row.get("name") or "").lower()
        if not (tk == q or tk.startswith(q) or q in nm):
            return False
    return True


def facet_count(rows: list[dict], flt: dict, group: str, value: str) -> int:
    """Antall rader som matcher denne verdien gitt de andre gruppene (og søk)."""
    other = {k: list(v) for k, v in flt.items() if k != group}
    if group == "q":
        other["q"] = value
        return sum(1 for r in rows if matches(r, other))
    other[group] = [value]
    return sum(1 for r in rows if matches(r, other))


def flag_map(snap: dict) -> dict:
    return {r["ticker"]: r for r in EV.red_rows(snap)}


def chip(r: dict | None) -> str:
    """Rød ⚑-chip med antall testede flagg (+EBIT). Ingen chip for ikke-sjekkede (f.eks. US)."""
    if not r:
        return ""
    return f'<span class="fchip">⚑ {E(EV.nlabel(r))}</span>'


def nokurs(e: dict) -> str:
    """Grå chip når tickeren mangler kursdata (UxBot 26.10): raden vises, hullet synes."""
    return "" if (e.get("stats") or {}).get("close") is not None else '<span class="nokurs">Ingen kursdata</span>'


def listed_tickers(snap: dict) -> list[dict]:
    """Rader brukeren ser i tabellen, inkludert «Ikke rangert»."""
    return list(snap.get("tickers") or [])


def listed_count(snap: dict) -> int:
    return len(listed_tickers(snap))


def tickere_intro(snap: dict) -> str:
    n = listed_count(snap)
    return (f'<p class="pintro">{n} kandidat-tickere med risikonivå og poengsum – '
            f'«verdt å undersøke», ikke «kjøp».</p>')


def n_new(snap: dict) -> int:
    """Rader der innkursdato = siste kursdato (samme regel som «Ny i dag» i avkastningscellen)."""
    return sum(1 for e in snap.get("tickers", []) if (e.get("_ret") or {}).get("new") and not e.get("unranked"))


def empties() -> str:
    """Rad på 48 px ved 0 treff, med Nullstill."""
    return ('<p id="tf-empty" class="tf-empty" hidden>Ingen tickere matcher filtrene. '
            '<button type="button" class="tf-empty-reset" id="tf-empty-reset">Nullstill</button></p>')


def risk_asof(path: str | None = None) -> date | None:
    """Siste dato i logs/risk_levels.csv, eller None hvis fila mangler."""
    pth = Path(path) if path else (LOGS / "risk_levels.csv")
    if not pth.exists():
        return None
    last = ""
    with pth.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = (r.get("date") or "").strip()
            if d > last:
                last = d
    if len(last) >= 10:
        try:
            return date.fromisoformat(last[:10])
        except ValueError:
            return None
    return None


def build_date(snap: dict | None) -> date:
    s = ""
    if snap:
        s = str(snap.get("date") or "")[:10] or str(snap.get("generated") or "")[:10]
    if len(s) >= 10 and s[4] == "-":
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            pass
    return date.today()


def risk_per_label(asof: date | None) -> str:
    return f"{asof.day:02d}.{asof.month:02d}" if asof else ""


def risk_filter_open(asof: date | None, build: date | None) -> bool:
    """Risikofilter vises når as-of ikke er mer enn 8 dager eldre enn byggdatoen."""
    if not asof or not build:
        return False
    return (build - asof).days <= 8


def count_text(n: int, total: int, omitted: int = 0, per: str = "") -> str:
    t = f"Viser {n} av {total}"
    if omitted:
        t += f" · {omitted} uten risikonivå utelatt"
    if per:
        t += f" · Risiko per {per}"
    return t


def count_line(n: int, total: int, omitted: int = 0, per: str = "", caveat: bool = False) -> str:
    note_h = "" if caveat else " hidden"
    return (f'<p id="tf-count" class="tf-count">{E(count_text(n, total, omitted, per))}</p>'
            f'<p id="tf-risk-note" class="tf-count"{note_h}>{E(RISK_CAVEAT)}</p>')


def _opt(group: str, key: str, lab: str, n: int) -> str:
    z = " is-zero" if n == 0 else ""
    return (f'<label class="tf-opt{z}" data-g="{E(group)}" data-k="{E(key)}">'
            f'<input type="checkbox" value="{E(key)}"><span class="tf-opt-lab">{E(lab)} ({n})</span></label>')


def _opts(group: str, items: list[tuple[str, str, int]]) -> str:
    return "".join(_opt(group, k, lab, n) for k, lab, n in items)


def _counts(snap: dict) -> dict[str, dict[str, int]]:
    rows = [row_meta(e) for e in listed_tickers(snap)]
    empty = {"risiko": [], "sektor": [], "bors": [], "annet": [], "q": ""}
    out = {"risiko": {}, "sektor": {}, "bors": {}, "annet": {}}
    for k, _lab in RISIKO_NAV:
        out["risiko"][k] = facet_count(rows, empty, "risiko", k)
    for lab in SEKTOR_NAV:
        out["sektor"][SEKTOR_SLUG[lab]] = facet_count(rows, empty, "sektor", SEKTOR_SLUG[lab])
    for k, _lab in BORS_NAV:
        out["bors"][k] = facet_count(rows, empty, "bors", k)
    n_flag = len(EV.red_rows(snap))  # vises i Annet som dekningstall; radfilter bruker data-flag på lista
    # Antall i lista (kandidater) med rødt flagg, ikke hele Oslo-universet
    out["annet"]["flagg"] = sum(1 for r in rows if r["flag"])
    out["annet"]["ny"] = sum(1 for r in rows if r["ny"])
    out["annet"]["mine"] = 0
    return out


def filter_row(snap: dict) -> str:
    c = _counts(snap)
    n_flag_all = len(EV.red_rows(snap))
    # Annet «Røde flagg»: vis antall i lista; flag_block har fortsatt hele Oslo-settet
    risiko = _opts("risiko", [(k, lab, c["risiko"][k]) for k, lab in RISIKO_NAV])
    sektor = _opts("sektor", [(SEKTOR_SLUG[lab], lab, c["sektor"][SEKTOR_SLUG[lab]]) for lab in SEKTOR_NAV])
    bors = _opts("bors", [(k, lab, c["bors"][k]) for k, lab in BORS_NAV])
    annet = _opts("annet", [(k, lab, c["annet"][k]) for k, lab in ANNET_NAV])
    total = listed_count(snap)
    asof = snap.get("_risk_asof") if isinstance(snap.get("_risk_asof"), date) else risk_asof()
    today = snap.get("_risk_today") if isinstance(snap.get("_risk_today"), date) else build_date(snap)
    ropen = risk_filter_open(asof, today)
    per = risk_per_label(asof)
    from .ux2 import SEARCH_HTML
    desk_dd = "".join(
        f'<div class="tf-dd" data-g="{g}">'
        f'<button type="button" class="tf-dd-btn" aria-expanded="false" aria-haspopup="true">{E(lab)}</button>'
        f'<div class="tf-dd-list" hidden role="group" aria-label="{E(lab)}">{html}</div></div>'
        for g, lab, html in (("risiko", "Risiko", risiko), ("sektor", "Sektor", sektor), ("bors", "Børs", bors))
    )
    annet_dd = (f'<div class="tf-dd" data-g="annet">'
                f'<button type="button" class="tf-dd-btn" aria-expanded="false" aria-haspopup="true">Annet ▾</button>'
                f'<div class="tf-dd-list" hidden role="group" aria-label="Annet">{annet}</div></div>')
    sections = "".join(
        f'<section class="tf-sec" data-g="{g}"><h3>{E(lab)}</h3>{html}</section>'
        for g, lab, html in (("risiko", "Risiko", risiko), ("sektor", "Sektor", sektor),
                             ("bors", "Børs", bors), ("annet", "Annet", annet))
    )
    # n_flag_all holdes i data-attributt så flag_block-lenker fortsatt kan vises
    return (
        f'<div class="tf-wrap" id="tf-wrap" data-total="{total}" data-flag-all="{n_flag_all}" data-ls="{LS_KEY}"'
        f' data-risk-open="{"1" if ropen else "0"}" data-risk-per="{E(per)}">'
        f'<div class="tf-top">'
        f'{SEARCH_HTML}'
        f'<button type="button" class="tf-fbtn" id="tf-fbtn" aria-controls="tf-sheet" aria-expanded="false">Filter (0)</button>'
        f'{desk_dd}'
        f'<button type="button" class="tf-mine" id="tf-mine" aria-pressed="false">★ Mine</button>'
        f'{annet_dd}'
        f'</div>'
        f'<div class="tf-chips" id="tf-chips" hidden></div>'
        f'{count_line(total, total, per=per)}'
        f'</div>'
        f'<div class="tf-sheet-bg" id="tf-sheet-bg" hidden></div>'
        f'<div class="tf-sheet" id="tf-sheet" role="dialog" aria-label="Filter" hidden>'
        f'<div class="tf-sheet-head"><h2>Filter</h2>'
        f'<button type="button" class="tf-slukk" id="tf-slukk" aria-label="Lukk">Lukk</button></div>'
        f'{sections}'
        f'<div class="tf-sheet-foot">'
        f'<button type="button" class="tf-apply" id="tf-apply">Vis {total} tickere</button>'
        f'<button type="button" class="tf-sheet-reset" id="tf-sheet-reset">Nullstill</button>'
        f'</div></div>'
    )


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
    from .ux2 import dm

    def row(r):   # UxBot 01.11: ett kort per ticker, antall som brikke til høyre, flaggene som liste med dato
        t = r["ticker"]
        li = "".join(f'<li>{EV.short_badge(k)}<span class="d">{E(dm(r.get("asof") or c["asof"]))}</span></li>' for k in EV.RED_FLAGS if k in r["flags"])
        return (f'<div class="rfr rfc"><div class="rfc-h">{NM.cell(t)}<span class="rfc-n">⚑ {E(EV.nlabel(r))}</span></div>'
                f'<ul class="fb">{li}</ul></div>')
    body = "".join(f'<h3 class="grp">{t} ({len(rs)})</h3>' + "".join(row(r) for r in rs) for t, rs in groups if rs)
    return (f'<div id="tf-flag" class="tf-flag" hidden><p class="tf-only">Bare Oslo-aksjer er sjekket for røde flagg. '
            f'{len(rows)} av {c["n"]} likvide Oslo-aksjer har minst ett flagg; data per {E(c["asof"] or "–")}.</p>'
            f'<details class="vis-alle"><summary>Hva betyr flaggene?</summary>{legend}'
            f'<p class="mut">Ingen flagg har bestått testkravet. Se <a href="metode.html">Metode</a> og <a href="{EV.EVREPORT}">testrapport</a>.</p></details>'
            f'{body}</div>')


CSS = """
/* UxBot 17.11: filtre og kontrast på Tickere */
.tf-wrap{position:sticky;top:0;z-index:20;background:var(--bg,#0b0f14);padding:6px 0;margin:0 0 6px}
.tf-wrap::after{display:none}
.tf-top{display:flex;flex-wrap:wrap;align-items:center;gap:8px;min-height:44px}
.tf-wrap .tf-q,#tf-q{flex:1 1 auto;min-width:0;height:44px;min-height:44px;box-sizing:border-box;padding:0 10px;border-radius:6px;border:1px solid #6b7787;background:var(--card,#161b22);color:var(--ink,#e6edf3);font:inherit;font-size:14px}
.tf-fbtn{flex:0 0 auto;min-width:44px;height:44px;min-height:44px;padding:0 10px;box-sizing:border-box;border:1px solid #6b7787;border-radius:6px;background:var(--card,#161b22);color:var(--ink,#e6edf3);font:500 13px/16px inherit;cursor:pointer;white-space:nowrap}
.tf-mine,.tf-dd-btn{height:44px;min-height:44px;padding:0 12px;border:1px solid #6b7787;border-radius:6px;background:var(--card,#161b22);color:var(--ink,#e6edf3);font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}
.tf-mine[aria-pressed=true],.tf-dd-btn.is-on,.tf-opt.is-on,.tf-fbtn.is-on{
  background:rgba(108,182,255,.18);border-color:var(--acc,#6cb6ff);color:#e6edf3}
.tf-mine[aria-pressed=true]::before{content:"✓ ";}
.tf-dd{position:relative;display:none}
.tf-dd-list{position:absolute;top:calc(100% + 4px);left:0;z-index:30;min-width:180px;max-width:320px;max-height:320px;overflow:auto;background:var(--card,#161b22);border:1px solid #6b7787;border-radius:8px;padding:4px 0}
.tf-opt{display:flex;align-items:center;gap:8px;min-height:44px;height:44px;padding:0 12px;box-sizing:border-box;cursor:pointer;color:var(--ink,#e6edf3);font-size:14px}
.tf-opt input{flex:none;width:16px;height:16px;margin:0}
.tf-opt.is-zero{opacity:.45}
.tf-opt:focus-within{outline:2px solid var(--acc,#6cb6ff);outline-offset:-2px}
.tf-chips{display:flex;flex-wrap:nowrap;align-items:center;gap:8px;overflow-x:auto;overflow-y:hidden;min-height:44px;margin-top:6px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.tf-chips::-webkit-scrollbar{display:none}
.tf-chip{flex:none;display:inline-flex;align-items:center;height:32px;min-height:32px;padding:0 4px 0 10px;border:1px solid var(--acc,#6cb6ff);border-radius:16px;background:rgba(108,182,255,.18);color:#e6edf3;font-size:13px;line-height:16px;white-space:nowrap}
.tf-chip-x{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;margin:-6px -4px -6px 0;padding:0;border:0;background:transparent;color:#e6edf3;font:inherit;cursor:pointer}
.tf-chips-reset{flex:none;height:32px;min-height:32px;padding:0 8px;border:0;background:none;color:var(--acc,#6cb6ff);font:inherit;font-size:13px;cursor:pointer}
.tf-count{margin:8px 0 6px;font-size:13px;line-height:18px;color:var(--mut,#9ea9b5)}
.tf-count + .tf-count{margin-top:0}
.tf-wrap[data-risk-open="0"] .tf-dd[data-g="risiko"],
.tf-wrap[data-risk-open="0"] .tf-sec[data-g="risiko"]{display:none!important}
.tf-empty{display:flex;align-items:center;gap:8px;min-height:48px;height:48px;margin:0;padding:0 12px;box-sizing:border-box;font-size:14px;color:var(--ink,#e6edf3)}
.tf-empty[hidden]{display:none}
.tf-empty-reset,.tf-sheet-reset{border:0;background:none;color:var(--acc,#6cb6ff);font:inherit;font-size:14px;line-height:18px;cursor:pointer;padding:0;margin:0;box-sizing:border-box;min-width:44px;min-height:44px;height:44px;display:inline-flex;align-items:center;justify-content:center}
.tf-sheet-reset{width:100%}
.tf-sheet-bg{display:block;position:fixed;inset:0;z-index:70;background:rgba(0,0,0,.5)}
.tf-sheet-bg[hidden]{display:none}
.tf-sheet{display:block;position:fixed;left:0;right:0;bottom:0;z-index:71;max-height:min(80vh,560px);overflow:auto;background:#1c2430;border-top:1px solid #3b4757;border-radius:12px 12px 0 0;padding:8px 0 calc(16px + env(safe-area-inset-bottom,0px))}
.tf-sheet[hidden]{display:none}
.tf-sheet-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:0 8px 0 16px;box-sizing:border-box;position:sticky;top:0;background:#1c2430;z-index:1}
.tf-sheet-head h2{margin:0;padding:8px 0;font:600 15px/20px inherit;flex:1 1 auto;min-width:0}
.tf-slukk{flex:none;width:44px;height:44px;min-width:44px;min-height:44px;padding:0;border:0;border-radius:6px;background:transparent;color:var(--ink,#e6edf3);font:500 13px/16px inherit;cursor:pointer}
.tf-sec{padding:8px 0 4px}
.tf-sec h3{margin:0;padding:8px 16px 4px;font:600 13px/16px inherit;color:var(--mut,#9ea9b5);text-transform:uppercase;letter-spacing:.03em}
.tf-sheet-foot{position:sticky;bottom:0;display:flex;flex-direction:column;gap:8px;padding:8px 16px 0;background:#1c2430}
.tf-apply{height:48px;min-height:48px;width:100%;border:0;border-radius:8px;background:var(--acc,#6cb6ff);color:#06101c;font:700 15px/20px inherit;cursor:pointer}
.fchip{display:inline-block;margin-left:6px;padding:0 6px;border-radius:9px;background:#3a1418;color:#ff7b72;border:1px solid #f8514966;font-size:.8em;white-space:nowrap}
.tf-flag .grp{margin:10px 0 4px}.tf-flag .rfr{padding:5px 0;border-bottom:1px solid #21262d}.tf-flag .fb{margin-top:3px}
.nokurs{display:inline-block;margin-left:6px;padding:0 6px;border-radius:9px;font-size:11px;line-height:16px;color:#64748b;background:#1e293b;white-space:nowrap}
.tf-only{font-size:.85em;color:var(--mut);margin:0 0 6px}
#tf-table th{background:#1f2733;color:#c9d1d9}
#tf-table tr.rowlink:hover td,#tf-table tr.rowlink:focus-within td{background:#1f2733}
#tf-table tr.rowlink:focus-visible{outline:2px solid var(--acc,#6cb6ff);outline-offset:-2px}
@media(max-width:699px){
  .tf-top{flex-wrap:nowrap;height:44px;min-height:44px;max-height:44px}
  .tf-wrap .tf-q,#tf-q{flex:1 1 auto;width:auto}
  .tf-dd,.tf-mine{display:none!important}
  .tf-fbtn{display:inline-flex;align-items:center;justify-content:center}
  #tf-table th:nth-child(4),#tf-table td:nth-child(4){display:none}
  #tf-table .why,#tf-table .mer,#tf-table td:first-child .mut{display:none}
  #tf-table td{padding:6px 4px;white-space:nowrap;font-size:.9em}#tf-table th{padding:6px 4px}
}
@media(min-width:700px){
  .tf-fbtn,.tf-sheet,.tf-sheet-bg{display:none!important}
  .tf-wrap .tf-q,#tf-q{flex:0 0 280px;width:280px;max-width:280px}
  .tf-dd,.tf-mine{display:inline-flex;align-items:center}
  .tf-mine{display:inline-flex}
  .tf-dd[data-g=annet] .tf-opt[data-k=mine]{display:none}
}
body.pg-tickere{overflow-x:hidden}
"""

JS = r"""<script>(()=>{
const wrap=document.getElementById('tf-wrap');
if(!wrap) return;
const LS=wrap.getAttribute('data-ls')||'signaltool.tickere-filter';
const TOTAL=parseInt(wrap.getAttribute('data-total')||'0',10)||0;
const riskOpen=wrap.getAttribute('data-risk-open')!=='0';
const riskPer=wrap.getAttribute('data-risk-per')||'';
const qEl=document.getElementById('tf-q');
const fbtn=document.getElementById('tf-fbtn');
const sheet=document.getElementById('tf-sheet');
const sheetBg=document.getElementById('tf-sheet-bg');
const slukk=document.getElementById('tf-slukk');
const applyBtn=document.getElementById('tf-apply');
const sheetReset=document.getElementById('tf-sheet-reset');
const chips=document.getElementById('tf-chips');
const countEl=document.getElementById('tf-count');
const noteEl=document.getElementById('tf-risk-note');
const empty=document.getElementById('tf-empty');
const emptyReset=document.getElementById('tf-empty-reset');
const table=document.getElementById('tf-table');
const flagBox=document.getElementById('tf-flag');
const mineBtn=document.getElementById('tf-mine');
const GROUPS=['risiko','sektor','bors','annet'];
const LAB={hoy:'Høy',middels:'Middels',lav:'Lav',ingen:'Ingen risikonivå',
  oslo:'Oslo',usa:'USA',tyskland:'Tyskland',danmark:'Danmark',sverige:'Sverige',
  storbritannia:'Storbritannia',japan:'Japan',taiwan:'Taiwan','ukjent-bors':'Ukjent børs',
  energi:'Energi',ravarer:'Råvarer',industri:'Industri','syklisk-forbruk':'Syklisk forbruk',
  'defensivt-forbruk':'Defensivt forbruk',helse:'Helse',finans:'Finans',teknologi:'Teknologi',
  kommunikasjon:'Kommunikasjon',forsyning:'Forsyning',eiendom:'Eiendom','ukjent-sektor':'Ukjent sektor',
  mine:'★ Mine',flagg:'Røde flagg',ny:'Ingen avkastning'};
const LEGACY={hoy:['risiko','hoy'],middels:['risiko','middels'],lav:['risiko','lav'],
  flagg:['annet','flagg'],mine:['annet','mine'],ny:['annet','ny']};
const emptyFlt=()=>({risiko:[],sektor:[],bors:[],annet:[],q:''});
let applied=emptyFlt();
let draft=emptyFlt();

function mineList(){return window.STMine?window.STMine.load():[]}
function copy(f){return {risiko:f.risiko.slice(),sektor:f.sektor.slice(),bors:f.bors.slice(),annet:f.annet.slice(),q:f.q}}
function nActive(f){return GROUPS.reduce((n,g)=>n+(f[g]||[]).length,0)}
function rows(){return [...document.querySelectorAll('#tf-table tr.rowlink')]}
function rowMatch(r,f){
  const group=(k,v)=>{const sel=f[k]||[]; return !sel.length||sel.includes(v)};
  const risk=r.dataset.cat==='Høy'?'hoy':r.dataset.cat==='Middels'?'middels':r.dataset.cat==='Lav'?'lav':'ingen';
  if(!group('risiko',risk)) return false;
  if(!group('sektor',r.dataset.sektor||'')) return false;
  if(!group('bors',r.dataset.bors||'')) return false;
  const an=f.annet||[];
  if(an.includes('mine')&&!mineList().includes(r.dataset.t)) return false;
  if(an.includes('flagg')&&r.dataset.flag!=='1') return false;
  if(an.includes('ny')&&r.dataset.ny!=='1') return false;
  const q=(f.q||'').trim().toLowerCase();
  if(q){
    const tk=(r.dataset.t||'').toLowerCase();
    const nm=((r.querySelector('.nm')||{}).textContent||'').toLowerCase();
    if(!(tk===q||tk.startsWith(q)||nm.includes(q))) return false;
  }
  return true;
}
function facet(f,g,val){
  const o=copy(f); if(g==='q'){o.q=val; return rows().filter(r=>rowMatch(r,o)).length;}
  o[g]=[val]; return rows().filter(r=>rowMatch(r,o)).length;
}
function parseUrl(){
  const u=new URL(location.href), f=emptyFlt();
  const leg=u.searchParams.get('filter');
  if(leg && LEGACY[leg]){const [g,k]=LEGACY[leg]; f[g]=[k];}
  GROUPS.forEach(g=>{
    const raw=u.searchParams.get(g);
    if(raw) f[g]=raw.split(',').map(s=>s.trim()).filter(Boolean);
  });
  const q=u.searchParams.get('q'); if(q) f.q=q;
  if(!riskOpen) f.risiko=[];
  return f;
}
function hasUrl(){
  const u=new URL(location.href);
  return !!(u.searchParams.get('filter')||u.searchParams.get('q')||GROUPS.some(g=>u.searchParams.get(g)));
}
function loadLs(){
  try{const j=JSON.parse(localStorage.getItem(LS)||''); if(j&&typeof j==='object'){
    const f=emptyFlt();
    GROUPS.forEach(g=>{ if(Array.isArray(j[g])) f[g]=j[g].map(String); });
    if(typeof j.q==='string') f.q=j.q;
    if(!riskOpen) f.risiko=[];
    return f;
  }}catch(e){}
  return emptyFlt();
}
function saveLs(f){
  try{localStorage.setItem(LS,JSON.stringify({risiko:f.risiko,sektor:f.sektor,bors:f.bors,annet:f.annet,q:f.q}))}catch(e){}
}
function writeUrl(f){
  const u=new URL(location.href);
  u.searchParams.delete('filter');
  GROUPS.forEach(g=>{
    if(g==='risiko' && !riskOpen){ u.searchParams.delete('risiko'); return; }
    if(f[g]&&f[g].length) u.searchParams.set(g,f[g].join(',')); else u.searchParams.delete(g);
  });
  if(f.q) u.searchParams.set('q',f.q); else u.searchParams.delete('q');
  history.replaceState(null,'',u);
}
function countText(n,total,omitted){
  let s='Viser '+n+' av '+total;
  if(omitted) s+=' · '+omitted+' uten risikonivå utelatt';
  if(riskPer) s+=' · Risiko per '+riskPer;
  return s;
}
function omittedCount(f,rs){
  const sel=f.risiko||[];
  if(!sel.length || sel.includes('ingen')) return 0;
  const f0=copy(f); f0.risiko=[];
  return rs.filter(r=>rowMatch(r,f0) && r.dataset.risk!=='1').length;
}
function showCaveat(f){
  return riskOpen && (f.risiko||[]).length>0 && (f.bors||[]).length!==1;
}
function setChecks(root,f){
  if(!root) return;
  root.querySelectorAll('.tf-opt').forEach(lab=>{
    const g=lab.getAttribute('data-g'), k=lab.getAttribute('data-k');
    const on=(f[g]||[]).includes(k);
    const inp=lab.querySelector('input');
    if(inp) inp.checked=on;
    lab.classList.toggle('is-on',on);
  });
}
function readChecks(root,f){
  if(!root) return f;
  GROUPS.forEach(g=>f[g]=[]);
  root.querySelectorAll('.tf-opt input:checked').forEach(inp=>{
    const lab=inp.closest('.tf-opt'); if(!lab) return;
    const g=lab.getAttribute('data-g'), k=lab.getAttribute('data-k');
    if(g&&k&&!(f[g]||[]).includes(k)) f[g].push(k);
  });
  return f;
}
function updateOptCounts(root,f){
  if(!root) return;
  root.querySelectorAll('.tf-opt').forEach(lab=>{
    const g=lab.getAttribute('data-g'), k=lab.getAttribute('data-k');
    const n=facet(f,g,k);
    const span=lab.querySelector('.tf-opt-lab');
    const name=LAB[k]||k;
    if(span) span.textContent=name+' ('+n+')';
    lab.classList.toggle('is-zero',n===0);
  });
}
function closeDd(){
  document.querySelectorAll('.tf-dd-list').forEach(l=>{l.hidden=true});
  document.querySelectorAll('.tf-dd-btn').forEach(b=>b.setAttribute('aria-expanded','false'));
}
function setSheet(open){
  if(!sheet) return;
  const was=!sheet.hidden;
  sheet.hidden=!open; if(sheetBg) sheetBg.hidden=!open;
  if(fbtn) fbtn.setAttribute('aria-expanded',open?'true':'false');
  if(open){ draft=copy(applied); syncDraftUi(); }
  if(!open && was && fbtn) fbtn.focus();
}
function syncDraftUi(){
  setChecks(sheet,draft);
  updateOptCounts(sheet,draft);
  if(applyBtn){
    const n=rows().filter(r=>rowMatch(r,draft)).length;
    applyBtn.textContent='Vis '+n+' tickere';
  }
}
function renderChips(f){
  if(!chips) return;
  const items=[];
  GROUPS.forEach(g=>(f[g]||[]).forEach(k=>items.push({g,k,lab:LAB[k]||k})));
  if(!items.length){ chips.hidden=true; chips.innerHTML=''; return; }
  chips.hidden=false;
  chips.innerHTML=items.map(it=>'<span class="tf-chip">'+it.lab+
    '<button type="button" class="tf-chip-x" data-g="'+it.g+'" data-k="'+it.k+'" aria-label="Fjern '+it.lab+'">×</button></span>'
  ).join('')+'<button type="button" class="tf-chips-reset" id="tf-chips-reset">Nullstill</button>';
}
function apply(f,push){
  applied=copy(f);
  if(qEl && qEl.value!==applied.q) qEl.value=applied.q;
  setChecks(document,applied);
  if(mineBtn) mineBtn.setAttribute('aria-pressed', applied.annet.includes('mine')?'true':'false');
  const rs=rows();
  let n=0;
  rs.forEach(r=>{const on=rowMatch(r,applied); r.hidden=!on; if(on) n++});
  const flagOnly=applied.annet.includes('flagg') && !applied.risiko.length && !applied.sektor.length && !applied.bors.length
    && applied.annet.filter(x=>x!=='flagg').length===0 && !applied.q;
  if(flagBox) flagBox.hidden=!applied.annet.includes('flagg');
  if(table && flagOnly){ /* behold eldre visning: bare flaggblokka når filter=flagg alene */ table.querySelector('.card') && (table.hidden=false); }
  if(countEl) countEl.textContent=countText(n, rs.length||TOTAL, omittedCount(applied,rs));
  if(noteEl) noteEl.hidden=!showCaveat(applied);
  if(empty){ empty.hidden=n>0; if(!n && table) table.prepend(empty); }
  if(fbtn){ const a=nActive(applied); fbtn.textContent='Filter ('+a+')'; fbtn.classList.toggle('is-on',a>0); }
  document.querySelectorAll('.tf-dd').forEach(dd=>{
    const g=dd.getAttribute('data-g');
    const btn=dd.querySelector('.tf-dd-btn');
    if(btn && g!=='annet') btn.classList.toggle('is-on', (applied[g]||[]).length>0);
    if(btn && g==='annet') btn.classList.toggle('is-on', (applied.annet||[]).filter(x=>x!=='mine').length>0);
  });
  updateOptCounts(document,applied);
  renderChips(applied);
  if(push!==false){ writeUrl(applied); saveLs(applied); }
}
function clearAll(){ apply(emptyFlt(), true); }

if(fbtn) fbtn.addEventListener('click',()=>setSheet(sheet.hidden));
if(slukk) slukk.addEventListener('click',()=>setSheet(false));
if(sheetBg) sheetBg.addEventListener('click',()=>setSheet(false));
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){
    if(sheet && !sheet.hidden){ setSheet(false); return; }
    closeDd();
  }
});
if(applyBtn) applyBtn.addEventListener('click',()=>{ readChecks(sheet,draft); draft.q=qEl?qEl.value:''; apply(draft,true); setSheet(false); });
if(sheetReset) sheetReset.addEventListener('click',()=>{ draft=emptyFlt(); if(qEl) draft.q=''; syncDraftUi(); apply(draft,true); setSheet(false); });
if(emptyReset) emptyReset.addEventListener('click',clearAll);
if(qEl) qEl.addEventListener('input',()=>{ applied.q=qEl.value; apply(applied,true); });
if(mineBtn) mineBtn.addEventListener('click',()=>{
  const on=!applied.annet.includes('mine');
  applied.annet=applied.annet.filter(x=>x!=='mine');
  if(on) applied.annet.push('mine');
  apply(applied,true);
});
document.querySelectorAll('.tf-dd-btn').forEach(btn=>{
  btn.addEventListener('click',e=>{
    e.stopPropagation();
    const list=btn.nextElementSibling;
    const open=list && list.hidden;
    closeDd();
    if(open && list){ list.hidden=false; btn.setAttribute('aria-expanded','true'); }
  });
});
document.addEventListener('click',e=>{
  if(!e.target.closest('.tf-dd')) closeDd();
});
document.querySelectorAll('.tf-dd-list .tf-opt input, .tf-sheet .tf-opt input').forEach(inp=>{
  inp.addEventListener('change',()=>{
    const inSheet=inp.closest('.tf-sheet');
    if(inSheet){ readChecks(sheet,draft); syncDraftUi(); return; }
    const lab=inp.closest('.tf-opt'); if(!lab) return;
    const g=lab.getAttribute('data-g'), k=lab.getAttribute('data-k');
    if(!g||!k) return;
    const on=inp.checked;
    applied[g]=applied[g].filter(x=>x!==k);
    if(on) applied[g].push(k);
    if(g==='annet' && k==='mine' && mineBtn) mineBtn.setAttribute('aria-pressed',on?'true':'false');
    apply(applied,true);
  });
});
if(chips) chips.addEventListener('click',e=>{
  const x=e.target.closest('.tf-chip-x');
  if(x){
    const g=x.getAttribute('data-g'), k=x.getAttribute('data-k');
    if(g&&k) applied[g]=(applied[g]||[]).filter(v=>v!==k);
    apply(applied,true); return;
  }
  if(e.target.closest('.tf-chips-reset')) clearAll();
});
document.addEventListener('mine:change',e=>{
  if(e.detail&&e.detail.imp){ if(!applied.annet.includes('mine')) applied.annet.push('mine'); apply(applied,true); }
  else apply(applied,false);
});

applied = hasUrl()? parseUrl() : loadLs();
if(qEl && applied.q) qEl.value=applied.q;
apply(applied, hasUrl() || nActive(applied)>0 || !!(applied.q));
})()</script>"""


# Behold tom SEARCH-kompatibilitet for tester som leter etter gammel tom-melding i JS
# (oppdateres i testene). «Ingen tickere i» er erstattet av «Ingen tickere matcher filtrene.»
