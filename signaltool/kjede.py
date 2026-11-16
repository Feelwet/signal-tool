"""Bekreftede koblinger og komponentfane på tickersider (UxBot, bindende).

Data ligger i site_config/kjeder/<TICKER>.json, med KOG.OL som første.
Komponentfanen «Hvem lager dette» viser stål, kobber, aluminium og jern
med produsenter og deres kunder der kilden navngir dem.
"""
from __future__ import annotations

import calendar, html, json, re
from datetime import date
from pathlib import Path

from .config import ROOT

DATA_DIR = ROOT / "site_config" / "kjeder"
E = lambda x: html.escape("" if x is None else str(x))


def slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", t)


def add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def parse_iso(s: str | None) -> date | None:
    if not s:
        return None
    s = str(s).strip()[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        y, m, d = map(int, s.split("-"))
        return date(y, m, d)
    if re.fullmatch(r"\d{4}", s):
        return None
    return None


def age_state(doc: date | None, page: date) -> str:
    """'hide' ved ≥36 kalendermåneder, 'year' ved ≥24, ellers 'ok'.

    Sammenligningen er page >= document + N kalendermåneder (ikke rå dagtelling).
    Mangler dokumentdato: 'ok' (årstall styres ev. av year_only i kilden).
    """
    if doc is None:
        return "ok"
    if page >= add_months(doc, 36):
        return "hide"
    if page >= add_months(doc, 24):
        return "year"
    return "ok"


def load(ticker: str, base: Path | None = None) -> dict | None:
    p = (base or DATA_DIR) / f"{ticker}.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def annotate_contract(c: dict, page: date) -> dict | None:
    doc = parse_iso(c.get("dokumentdato"))
    st = age_state(doc, page)
    if st == "hide":
        return None
    out = dict(c)
    out["_state"] = st
    out["_show_year"] = st == "year" or bool(c.get("year_only"))
    out["_doc"] = doc
    return out


def visible_contracts(contracts: list, page: date) -> list:
    out = []
    for c in contracts or []:
        a = annotate_contract(c, page)
        if a:
            out.append(a)
    out.sort(key=lambda c: c.get("dokumentdato") or "", reverse=True)
    return out


def newest_date(contracts: list) -> str:
    dates = [c.get("dokumentdato") or "" for c in contracts]
    return max(dates) if dates else ""


def visible_parties(data: dict, page: date, side: str) -> list:
    rows = []
    for p in data.get("counterparties") or []:
        if p.get("side") != side:
            continue
        cs = visible_contracts(p.get("contracts") or [], page)
        if not cs and not p.get("ikke_offentlig"):
            continue
        q = dict(p)
        q["_contracts"] = cs
        q["_newest"] = newest_date(cs)
        rows.append(q)
    backed = [r for r in rows if not r.get("ikke_offentlig")]
    hidden = [r for r in rows if r.get("ikke_offentlig")]
    backed.sort(key=lambda r: (r["_newest"], r.get("name") or ""), reverse=True)
    # same date: alphabetical by name (stable after date desc — re-sort name asc within date)
    backed.sort(key=lambda r: r.get("name") or "")
    backed.sort(key=lambda r: r["_newest"], reverse=True)
    return backed + hidden


def counts(data: dict, page: date) -> tuple[int, int]:
    s = visible_parties(data, page, "supplier")
    c = visible_parties(data, page, "customer")
    ns = sum(1 for r in s if not r.get("ikke_offentlig"))
    nc = sum(1 for r in c if not r.get("ikke_offentlig"))
    return ns, nc


def can_drill(data: dict, page: date) -> bool:
    for side in ("supplier", "customer"):
        for p in visible_parties(data, page, side):
            kids = p.get("children") or []
            if any(annotate_contract(k, page) if "dokumentdato" in k else k for k in kids):
                # children may be party dicts, not contracts
                if kids:
                    return True
            if kids:
                return True
    return False


def has_ticker_page(ticker: str | None, available: set[str] | None) -> bool:
    if not ticker:
        return False
    avail = set(available or [])
    if ticker in avail:
        return True
    st = slug(ticker)
    if st in avail or any(slug(a) == st for a in avail):
        return True
    p = ROOT / "site" / "ticker" / f"{st}.html"
    return p.is_file()


def fmt_dmy(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def type_and_date(c: dict) -> tuple[str, str]:
    """(kildetype-visning, datotekst). Type først: kontrakt dd.mm.åå / rammeavtale / fast forhold…"""
    raw = (c.get("kildetype") or "").strip()
    show_year = c.get("_show_year")
    doc = c.get("_doc") or parse_iso(c.get("dokumentdato"))
    year_only = bool(c.get("year_only"))

    def typ_kind(s: str) -> str:
        t = s.lower()
        if "fast forhold" in t:
            return "fast"
        if t.startswith("rammeavtale") or "rammeavtale" in t:
            return "ramme"
        if "kontrakt" in t or not t.strip():
            return "kontrakt"
        return "other"

    kind = typ_kind(raw)
    if year_only:
        y = (raw.split()[-1] if re.search(r"\b\d{4}\s*$", raw) else (str(doc.year) if doc else (c.get("dokumentdato") or "")[:4]))
        typ = "rammeavtale" if kind == "ramme" else ("fast forhold oppgitt i rapport" if kind == "fast" else f"kontrakt {y}")
        dato = y
    elif show_year and doc:
        typ = "rammeavtale" if kind == "ramme" else ("fast forhold oppgitt i rapport" if kind == "fast" else f"kontrakt {doc.year}")
        dato = str(doc.year)
    elif kind == "fast":
        typ = "fast forhold oppgitt i rapport"
        dato = fmt_dmy(doc) if doc else (c.get("dokumentdato") or "")
    elif kind == "ramme":
        # keep date in type if present, else rammeavtale
        typ = "rammeavtale"
        dato = fmt_dmy(doc) if doc else (c.get("dokumentdato") or "")
    elif kind == "other":
        typ = raw
        dato = fmt_dmy(doc) if doc else (c.get("dokumentdato") or "")
    else:
        typ = f"kontrakt {fmt_dmy(doc)}" if doc else "kontrakt"
        dato = fmt_dmy(doc) if doc else (c.get("dokumentdato") or "")
    return typ, dato



def party_date(p: dict) -> str:
    """Dato/år for linje 2, fra nyeste synlige kontrakt. År når kilden er ≥24 mnd eller year_only."""
    cs = p.get("_contracts") or []
    if not cs:
        return ""
    _, dato = type_and_date(cs[0])
    return dato or ""


def meta_html(role: str, dato: str) -> str:
    """Linje 2: flex-rad med rolle (ellipsis) og dato/år i eget element (aldri kuttet)."""
    if not role and not dato:
        return ""
    role_h = f'<div class="kjede-role">{E(role)}</div>' if role else '<div class="kjede-role"></div>'
    date_h = f'<span class="kjede-date">{E(dato)}</span>' if dato else ""
    return f'<div class="kjede-meta">{role_h}{date_h}</div>'


def line_style(party: dict) -> str:
    if party.get("ikke_offentlig"):
        return "none"
    cs = party.get("_contracts") or party.get("contracts") or []
    # newest contract's type; solid if that one (we already sort newest first) is ramme/fast
    if not cs:
        return "dashed"
    typ, _ = type_and_date(cs[0] if cs[0].get("_state") or "_doc" in cs[0] else {**cs[0], **{}})
    raw = (cs[0].get("kildetype") or "").lower()
    if "fast forhold" in raw or raw.startswith("rammeavtale") or "rammeavtale" in raw:
        return "solid"
    return "dashed"


def source_line_html(c: dict) -> str:
    typ, dato = type_and_date(c)
    label = c.get("source_label") or "Kilde"
    via = c.get("via") or ""
    # vis via i kildelinja bare når det hjelper, etter type
    bits = [typ]
    if via:
        bits.append("via " + via)
    bits.append(label)
    bits.append(dato)
    text = " · ".join(bits)
    url = c.get("url") or ""
    arrow = (f'<a class="kjede-src" href="{E(url)}" target="_blank" rel="noopener noreferrer" '
             f'aria-label="Kilde: {E(label)}">{E(text)} <span aria-hidden="true">↗</span></a>')
    if not url:
        arrow = f'<span class="kjede-src kjede-src-t">{E(text)}</span>'
    return f'<div class="kjede-src-line">{arrow}</div>'


def chip_html(ticker: str, available: set[str] | None, no_chip: bool = False) -> str:
    if no_chip or not has_ticker_page(ticker, available):
        return ""
    href = f"../ticker/{E(slug(ticker))}.html"
    return f'<a class="kjede-chip" href="{href}">{E(ticker)} <span aria-hidden="true">↗</span></a>'


def party_row_html(p: dict, available: set[str] | None, can: bool) -> str:
    name = p.get("name") or ""
    role = p.get("role") or ""
    ikke = bool(p.get("ikke_offentlig"))
    kids = p.get("children") or []
    drillable = bool(can and kids and not ikke)
    cs = p.get("_contracts") or []
    shown, rest = cs[:3], cs[3:]
    src = "".join(source_line_html(c) for c in shown)
    more = ""
    if rest:
        hidden = "".join(source_line_html(c) for c in rest)
        n = len(cs)
        more = (f'<button type="button" class="kjede-more" aria-expanded="false">'
                f'Alle kontrakter ({n})</button><div class="kjede-extra" hidden>{hidden}</div>')
    chip = ""
    # KOG (via KAMS) skal aldri ha TICKER-chip; land og «ikke offentlig» heller ikke
    tick = p.get("ticker")
    if tick and not ikke and name != "KOG (via KAMS)":
        chip = chip_html(tick, available)
    cls = "kjede-row"
    if ikke:
        cls += " kjede-io"
    if drillable:
        cls += " kjede-drill"
    arrow = '<span class="kjede-gt" aria-hidden="true">›</span>' if drillable else ""
    attrs = f' data-id="{E(p.get("id") or "")}"'
    if drillable:
        attrs += " tabindex=\"0\" role=\"button\""
    # linjestil som data for CSS-kobling
    attrs += f' data-line="{E(line_style(p))}"'
    return (
        f'<article class="{cls}"{attrs}>'
        f'<div class="kjede-id"><span class="kjede-name">{E(name)}</span>{chip}{arrow}</div>'
        f'{meta_html(role, party_date(p))}'
        f'{src}{more}</article>'
    )


def col_html(title: str, n: int, rows: list[str], empty: str = "", area: str = "") -> str:
    vis, rest = rows[:6], rows[6:]
    more = ""
    if rest:
        more = (f'<button type="button" class="kjede-visalle" aria-expanded="false">'
                f'Vis alle {len(rows)}</button>'
                f'<div class="kjede-col-extra" hidden>{"".join(rest)}</div>')
    body = "".join(vis) if vis else f'<p class="kjede-empty">{E(empty or "Ingen offentlig kilde")}</p>'
    # n i overskriften er bare kildebelagte (gitt inn)
    cls = "kjede-col" + (f" kjede-{area}" if area else "")
    return (f'<div class="{cls}">'
            f'<h3 class="kjede-col-h">{E(title)} <span class="kjede-n">({n})</span></h3>'
            f'{body}{more}</div>')


def mid_html(data: dict, path: list, available: set[str] | None) -> str:
    name = data.get("name") or data.get("ticker") or ""
    tick = data.get("ticker") or ""
    chips = "".join(f'<span class="kjede-prod">{E(p)}</span>' for p in (data.get("products") or []))
    dev = ""
    for d in data.get("developed_with") or []:
        # én linje under Produserer, 13/18 grå, uten linje ut, uten TICKER-chip
        dev += f'<p class="kjede-dev">{E(d.get("text") or ("Utviklet med " + (d.get("name") or "")))}</p>'
    prod = ""
    if chips or dev:
        prod = f'<div class="kjede-prod-block"><div class="kjede-prod-h">Produserer</div>{chips}{dev}</div>'
    order = ""
    if len(path) >= 1:
        # vises bare når det faktisk er boret inn (koden er her, skjules på nivå 0)
        order = f'<p class="kjede-ord">{E(str(len(path)))}. ordens fra {E(tick)}</p>'
    return (f'<div class="kjede-mid" tabindex="-1">'
            f'<div class="kjede-mid-name">{E(name)}</div>'
            f'<div class="kjede-mid-tk">{E(tick)}</div>{order}{prod}</div>')


def component_counts(data: dict) -> tuple[int, int]:
    """(kildebelagte komponenter med produsentliste, antall «under kontroll»)."""
    items = ((data.get("components") or {}).get("items") or [])
    n_ok = sum(1 for i in items if i.get("status") == "ok")
    n_uk = sum(1 for i in items if i.get("status") == "under_kontroll")
    return n_ok, n_uk


def visible_source(item: dict, page: date) -> dict | None:
    """Én kildelinje på produsent- eller kunderad; skjul ved ≥36 mnd."""
    return annotate_contract(item, page)


def visible_producers(comp: dict, page: date) -> list:
    rows = []
    for p in comp.get("producers") or []:
        src = visible_source(p, page)
        if not src:
            continue
        q = dict(p)
        q["_source"] = src
        q["_customers"] = [c for c in (p.get("customers") or []) if visible_source(c, page)]
        # behold kundefeltets annoterte kilder
        annotated = []
        for c in (p.get("customers") or []):
            a = visible_source(c, page)
            if a:
                annotated.append(a)
        q["_customers"] = annotated
        rows.append(q)
    return rows


def komp_producer_row_html(p: dict, available: set[str] | None, comp_id: str) -> str:
    name = p.get("name") or ""
    role = p.get("role") or ""
    src = source_line_html(p.get("_source") or p)
    chip = chip_html(p.get("ticker"), available) if p.get("ticker") else ""
    return (
        f'<article class="komp-row komp-drill" data-id="{E(p.get("id") or "")}" '
        f'data-comp="{E(comp_id)}" tabindex="0" role="button">'
        f'<div class="kjede-id"><span class="kjede-name">{E(name)}</span>{chip}</div>'
        f'{f"<div class=kjede-role>{E(role)}</div>" if role else ""}'
        f'{src}</article>'
    )


def komp_customer_row_html(c: dict, available: set[str] | None) -> str:
    name = c.get("name") or ""
    role = c.get("role") or ""
    src = source_line_html(c)
    chip = chip_html(c.get("ticker"), available) if c.get("ticker") else ""
    return (
        f'<article class="komp-row">'
        f'<div class="kjede-id"><span class="kjede-name">{E(name)}</span>{chip}</div>'
        f'{f"<div class=kjede-role>{E(role)}</div>" if role else ""}'
        f'{src}</article>'
    )


def komp_list_html(title: str, n: int, rows: list[str], empty: str) -> str:
    vis, rest = rows[:6], rows[6:]
    more = ""
    if rest:
        more = (
            f'<button type="button" class="kjede-visalle" aria-expanded="false">'
            f'Vis alle {len(rows)}</button>'
            f'<div class="kjede-col-extra" hidden>{"".join(rest)}</div>'
        )
    if vis:
        body = "".join(vis)
    else:
        body = f'<p class="komp-empty">{E(empty)}</p>'
    return (
        f'<div class="komp-list">'
        f'<h3 class="komp-gics">{E(title)}</h3>'
        f'{body}{more}</div>'
    )


def component_panel_html(data: dict, available: set[str] | None, page: date) -> str:
    bundle = data.get("components") or {}
    items = bundle.get("items") or []
    if not items:
        return ""
    disc = bundle.get("disclaimer") or (
        "Viser produsenter av komponenten, ikke bekreftede leverandører til KOG"
    )
    tick = data.get("ticker") or ""
    chips = []
    uk = []
    views = []
    for comp in items:
        st = comp.get("status") or "ok"
        name = comp.get("name") or comp.get("id") or ""
        cid = comp.get("id") or name
        if st == "under_kontroll":
            uk.append(f'<p class="komp-uk">{E(name)}: under kontroll</p>')
            continue
        chips.append(
            f'<button type="button" class="komp-chip" data-id="{E(cid)}" '
            f'aria-pressed="false">{E(name)}</button>'
        )
        producers = visible_producers(comp, page)
        gics = comp.get("gics") or ""
        heading = gics or name
        prow = [komp_producer_row_html(p, available, cid) for p in producers]
        path_p = f"{tick}|{name}"
        views.append(
            f'<div class="komp-view" data-komp-panel="{E(cid)}" '
            f'data-path="{E(path_p)}" hidden>'
            f'{komp_list_html(heading, len(prow), prow, "Ingen offentlig kilde")}'
            f'</div>'
        )
        for p in producers:
            pname = p.get("name") or ""
            pid = p.get("id") or ""
            cust = p.get("_customers") or []
            n = len(cust)
            title = f"Kunder av {pname} ({n})"
            craw = [komp_customer_row_html(c, available) for c in cust]
            path_c = f"{tick}|{name}|{pname}"
            src_p = p.get("_source") or p
            card = (
                f'<aside class="komp-prod-card">'
                f'<div class="kjede-id"><span class="kjede-name">{E(pname)}</span>'
                f'{chip_html(p.get("ticker"), available) if p.get("ticker") else ""}</div>'
                f'{meta_html(p.get("role") or "", type_and_date(src_p)[1] if src_p else "")}'
                f'{source_line_html(src_p)}</aside>'
            )
            views.append(
                f'<div class="komp-view komp-prod-view" data-komp-panel="{E(cid)}/{E(pid)}" '
                f'data-path="{E(path_c)}" hidden>'
                f'<div class="komp-prod-grid">'
                f'<div class="komp-prod-cus">'
                f'{komp_list_html(title, n, craw, "Ingen kunder navngitt i offentlige kilder")}'
                f'</div>{card}</div></div>'
            )
    path = (
        f'<nav class="komp-path" hidden aria-hidden="true">'
        f'<button type="button" class="komp-back">← Tilbake</button>'
        f'<ol class="komp-crumbs"></ol></nav>'
    )
    chiprow = f'<div class="komp-chips">{"".join(chips)}</div>' if chips else ""
    return (
        f'{path}'
        f'<p class="komp-disc">{E(disc)}</p>'
        f'{chiprow}{"".join(uk)}{"".join(views)}'
    )


def jump_html(ticker: str, page_date: date | None = None, base: Path | None = None) -> str:
    data = load(ticker, base=base)
    if not data:
        return ""
    page = page_date or date.today()
    ns, nc = counts(data, page)
    parts = [f'<a href="#kjede">Leverandører {ns} · Kunder {nc}</a>']
    n_ok, n_uk = component_counts(data)
    if n_ok or n_uk:
        komp = ""
        if n_ok:
            komp += f'<a href="#komp">Komponenter {n_ok}</a>'
        if n_uk:
            komp += f'<span class="kjede-jump-uk"> · {n_uk} under kontroll</span>'
        parts.append(f'<span class="kjede-jump-komp"> · {komp}</span>')
    return f'<p class="kjede-jump">{"".join(parts)}</p>'


def section_html(ticker: str, available: set[str] | None = None, page_date: date | None = None,
                 base: Path | None = None) -> str:
    data = load(ticker, base=base)
    if not data:
        return ""
    page = page_date or date.today()
    avail = set(available or [])
    ns, nc = counts(data, page)
    drill = can_drill(data, page)
    sup = visible_parties(data, page, "supplier")
    cus = visible_parties(data, page, "customer")
    sup_h = [party_row_html(p, avail, drill) for p in sup]
    cus_h = [party_row_html(p, avail, drill) for p in cus]
    path = (f'<nav class="kjede-path" hidden aria-hidden="true">'
            f'<button type="button" class="kjede-back" hidden>← Tilbake</button>'
            f'<ol class="kjede-crumbs"></ol></nav>')
    mid = mid_html(data, [], avail)
    # DOM-rekkefølge (fokus) i bekreftet fane: sti → midtkort → leverandører → kunder
    grid = (f'<div class="kjede-grid">'
            f'{mid}'
            f'{col_html("Leverandører", ns, sup_h, area="sup")}'
            f'{col_html("Kunder", nc, cus_h, area="cus")}'
            f'</div>')
    komp = component_panel_html(data, avail, page)
    tabs = ""
    panel_bek = f'{path}{grid}'
    panel_komp = ""
    if komp:
        tabs = (
            f'<div class="kjede-tabs" role="tablist">'
            f'<button type="button" class="kjede-tab" role="tab" id="kjede-tab-bek" '
            f'aria-controls="kjede-panel-bek" aria-selected="true">'
            f'Bekreftede koblinger</button>'
            f'<button type="button" class="kjede-tab" role="tab" id="kjede-tab-komp" '
            f'aria-controls="kjede-panel-komp" aria-selected="false" tabindex="-1">'
            f'Hvem lager dette</button>'
            f'</div>'
        )
        panel_bek = (
            f'<div class="kjede-panel" id="kjede-panel-bek" role="tabpanel" '
            f'aria-labelledby="kjede-tab-bek">{path}{grid}</div>'
        )
        panel_komp = (
            f'<div class="kjede-panel" id="kjede-panel-komp" role="tabpanel" '
            f'aria-labelledby="kjede-tab-komp" hidden>{komp}</div>'
        )
    payload = json.dumps({"ticker": ticker, "canDrill": drill}, ensure_ascii=False)
    return (
        f"<style>{CSS}</style>"
        f'<section id="kjede" class="kjede" data-can-drill="{1 if drill else 0}" '
        f'data-ticker="{E(ticker)}">'
        f'<h2 class="kjede-h">Verdikjede</h2>'
        f'{tabs}{panel_bek}{panel_komp}'
        f'<script type="application/json" id="kjede-data">{payload}</script>'
        f"<script>{JS}</script>"
        f"</section>"
    )




CSS = r"""
.kjede-jump{height:32px;line-height:32px;margin:0 0 8px;font-size:13px;overflow:hidden}
.kjede-jump a{display:inline-flex;align-items:center;min-height:32px;color:inherit;text-decoration:none}
.kjede-jump a:hover,.kjede-jump a:focus-visible{text-decoration:underline}
.kjede-jump-uk{font-size:12px;line-height:16px;color:#94a3b8}
.kjede-jump-komp{white-space:nowrap}
.kjede{margin:16px 0;overflow-x:hidden;min-width:0}
.kjede-h{margin:0 0 12px;font-size:20px;line-height:28px}
.kjede-path{display:flex;flex-wrap:wrap;align-items:center;gap:8px;min-height:44px;margin:0 0 12px}
.kjede-path[hidden],.kjede-back[hidden],.kjede-extra[hidden],.kjede-col-extra[hidden]{display:none}
.kjede-back{box-sizing:border-box;min-width:44px;min-height:44px;padding:0 12px;border:0;background:transparent;color:inherit;font:inherit;cursor:pointer}
.kjede-grid{display:grid;grid-template-columns:1fr;grid-template-areas:"mid" "sup" "cus";gap:24px;min-width:0}
.kjede-mid{grid-area:mid;box-sizing:border-box;min-width:0;padding:16px;background:#1c2430;border:1px solid #3b4757;border-radius:12px}
.kjede-col.kjede-sup{grid-area:sup}
.kjede-col.kjede-cus{grid-area:cus}
.kjede-col{min-width:0;overflow-x:hidden}
.kjede-col-h{margin:0 0 8px;font-size:15px;line-height:20px;font-weight:600}
.kjede-n{font-weight:400;color:#94a3b8}
.kjede-mid-name{font-size:18px;line-height:24px;font-weight:600}
.kjede-mid-tk{font-size:13px;line-height:18px;color:#94a3b8}
.kjede-ord{font-size:13px;line-height:18px;color:#94a3b8;margin:4px 0 0}
.kjede-prod-h{font-size:13px;line-height:18px;color:#94a3b8;margin:10px 0 4px}
.kjede-prod{display:inline-block;margin:0 6px 4px 0;padding:2px 8px;border:1px solid #3b4757;border-radius:4px;font-size:13px;line-height:18px}
.kjede-dev{margin:8px 0 0;font-size:13px;line-height:18px;color:#94a3b8}
.kjede-row{box-sizing:border-box;min-height:64px;max-height:96px;overflow:hidden;margin:0 0 8px;padding:8px 8px 8px 10px;border:1px solid transparent;border-radius:8px;position:relative}
.kjede-row:has(.kjede-more){max-height:140px}
.kjede-row[data-line="solid"]{border-left:1px solid #94a3b8}
.kjede-row[data-line="dashed"]{border-left:1px dashed #94a3b8;background-image:none}
.kjede-row.kjede-io{border:1px dashed #94a3b8;max-height:96px}
.kjede-row.kjede-open{max-height:none;overflow:visible}
.kjede-row:not(.kjede-open)>.kjede-src-line{display:none}
.kjede-id{display:flex;align-items:center;min-width:0;overflow:hidden}
.kjede-name{font-size:15px;line-height:20px;font-weight:600;flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kjede-chip,.kjede-gt{flex:none}
.kjede-meta{display:flex;align-items:baseline;min-width:0;margin:0}
.kjede-role{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;line-height:16px;color:#94a3b8;margin:0}
.kjede-date{flex:none;white-space:nowrap;margin-left:8px;overflow:visible;font-size:12px;line-height:16px;color:#94a3b8}
.kjede-src-line{font-size:12px;line-height:16px;margin:0}
.kjede-src{display:inline-flex;align-items:center;min-width:44px;min-height:44px;color:#94a3b8;text-decoration:none;font-size:12px;line-height:16px}
.kjede-src:hover,.kjede-src:focus-visible{text-decoration:underline}
.kjede-src-t{color:#94a3b8;font-size:12px;line-height:16px}
.kjede-chip{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;margin-left:6px;padding:0 8px;border:1px solid #3b4757;border-radius:4px;color:inherit;text-decoration:none;font-size:13px;line-height:18px;vertical-align:middle}
.kjede-gt{margin-left:6px;color:#94a3b8}
.kjede-more,.kjede-visalle{box-sizing:border-box;display:flex;align-items:center;min-width:44px;min-height:44px;padding:0 8px;border:0;background:transparent;color:inherit;font:inherit;font-size:13px;line-height:18px;cursor:pointer;text-align:left}
.kjede-empty{font-size:13px;line-height:18px;color:#94a3b8;margin:0}
@media(min-width:1280px){
  .kjede-grid{grid-template-columns:minmax(0,9fr) minmax(0,10fr) minmax(0,9fr);grid-template-areas:"sup mid cus";gap:24px}
  .kjede-jump{height:32px;white-space:nowrap;overflow:hidden}
}
@media(max-width:1279px){
  .kjede-grid{grid-template-columns:1fr;grid-template-areas:"mid" "sup" "cus";gap:24px}
  .kjede-jump{height:auto;max-height:56px;line-height:28px;overflow-x:hidden;overflow-y:hidden}
  .kjede-jump a{min-height:28px}
}
.kjede-tabs{display:flex;justify-content:flex-start;height:44px;margin:0 0 12px;padding:0;gap:0}
.kjede-tab{box-sizing:border-box;flex:1 1 50%;height:44px;min-height:44px;min-width:44px;padding:0 12px;border:0;border-bottom:2px solid transparent;background:transparent;color:inherit;font:inherit;font-size:15px;line-height:20px;cursor:pointer}
.kjede-tab[aria-selected="true"]{border-bottom-color:#94a3b8;font-weight:600}
@media(min-width:1280px){
  .kjede-tab{flex:0 0 200px;width:200px}
  .komp-prod-grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr);grid-template-areas:"cus card";gap:24px}
}
.kjede-panel[hidden],.komp-path[hidden],.komp-view[hidden]{display:none}
.komp-disc{margin:0 0 12px;font-size:13px;line-height:18px;color:#94a3b8}
.komp-chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.komp-chip{box-sizing:border-box;min-height:44px;min-width:44px;padding:0 12px;border:1px solid #3b4757;border-radius:4px;background:transparent;color:inherit;font:inherit;font-size:13px;line-height:18px;cursor:pointer}
.komp-chip[aria-pressed="true"]{font-weight:600}
.komp-uk{margin:0 0 8px;font-size:13px;line-height:18px;color:#94a3b8}
.komp-gics{margin:0 0 8px;font-size:15px;line-height:20px;font-weight:600}
.komp-row{box-sizing:border-box;min-height:64px;max-height:96px;overflow:hidden;margin:0 0 8px;padding:8px;border-radius:8px;position:relative}
.komp-row.komp-drill{cursor:pointer}
.komp-empty{box-sizing:border-box;min-height:48px;display:flex;align-items:center;margin:0;font-size:13px;line-height:18px;color:#94a3b8}
.komp-path{display:flex;flex-wrap:wrap;align-items:center;gap:8px;min-height:44px;margin:0 0 12px}
.komp-back{box-sizing:border-box;min-width:44px;min-height:44px;padding:0 12px;border:0;background:transparent;color:inherit;font:inherit;cursor:pointer;flex:none}
.komp-crumbs{display:flex;flex-wrap:wrap;gap:4px;margin:0;padding:0;list-style:none;font-size:13px;line-height:18px;color:#94a3b8}
.komp-prod-grid{display:grid;grid-template-columns:minmax(0,1fr);grid-template-areas:"cus" "card";gap:24px;min-width:0}
.komp-prod-cus{grid-area:cus;min-width:0}
.komp-prod-card{grid-area:card;min-width:0;box-sizing:border-box;padding:16px;background:#1c2430;border:1px solid #3b4757;border-radius:12px}
@media(max-width:599px){
  .komp-path{flex-wrap:nowrap;align-items:center;height:44px;min-height:44px;max-height:44px;overflow:hidden;gap:8px}
  .komp-crumbs{flex-wrap:nowrap;align-items:center;min-width:0;flex:1 1 auto;overflow:hidden}
  .komp-crumb,.komp-crumb-sep{flex:none;white-space:nowrap}
  .komp-crumb-mid{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis}
}
"""


JS = r"""
(function(){
  var root=document.getElementById('kjede');
  if(!root)return;
  var can=root.getAttribute('data-can-drill')==='1';
  var ticker=root.getAttribute('data-ticker')||'';
  var pathEl=root.querySelector('#kjede-panel-bek .kjede-path')||root.querySelector('.kjede-path');
  var back=root.querySelector('#kjede-panel-bek .kjede-back')||root.querySelector('.kjede-back');
  var tabBek=document.getElementById('kjede-tab-bek');
  var tabKomp=document.getElementById('kjede-tab-komp');
  var panBek=document.getElementById('kjede-panel-bek');
  var panKomp=document.getElementById('kjede-panel-komp');
  function isKompHash(){
    var h=location.hash||'';
    return h==='#komp'||h.indexOf('#komp=')===0;
  }
  function parseKjede(){
    var h=location.hash||'';
    var m=h.match(/^#kjede(?:=(.*))?$/);
    if(!m)return [];
    if(!m[1])return [];
    return m[1].split('/').filter(Boolean);
  }
  function parseKomp(){
    var h=location.hash||'';
    var m=h.match(/^#komp(?:=(.*))?$/);
    if(!m||!m[1])return [];
    return m[1].split('/').filter(Boolean).map(function(p){try{return decodeURIComponent(p)}catch(e){return p}});
  }
  function setHash(h){
    if(location.hash!==h)history.replaceState(null,'',h);
  }
  function showTab(komp){
    if(!tabBek||!panBek||!tabKomp||!panKomp)return;
    tabBek.setAttribute('aria-selected', komp?'false':'true');
    tabKomp.setAttribute('aria-selected', komp?'true':'false');
    tabBek.tabIndex=komp?-1:0;
    tabKomp.tabIndex=komp?0:-1;
    panBek.hidden=!!komp;
    panKomp.hidden=!komp;
  }
  function showPath(parts){
    if(!can||!parts.length){
      if(pathEl){pathEl.hidden=true;pathEl.setAttribute('aria-hidden','true');}
      if(back)back.hidden=true;
      return;
    }
    if(pathEl){pathEl.hidden=false;pathEl.removeAttribute('aria-hidden');}
    if(back)back.hidden=false;
  }
  function renderKomp(){
    var parts=parseKomp();
    var views=root.querySelectorAll('.komp-view');
    var i,key,show;
    for(i=0;i<views.length;i++){
      key=views[i].getAttribute('data-komp-panel')||'';
      show=false;
      if(parts.length===1&&key===parts[0])show=true;
      if(parts.length>=2&&key===parts[0]+'/'+parts[1])show=true;
      views[i].hidden=!show;
    }
    var chips=root.querySelectorAll('.komp-chip');
    for(i=0;i<chips.length;i++){
      chips[i].setAttribute('aria-pressed', parts[0]===chips[i].getAttribute('data-id')?'true':'false');
    }
    var path=root.querySelector('.komp-path');
    var kback=root.querySelector('.komp-back');
    var ol=path&&path.querySelector('.komp-crumbs');
    var vis=null;
    for(i=0;i<views.length;i++){if(!views[i].hidden){vis=views[i];break;}}
    if(path){
      if(!parts.length||!vis){path.hidden=true;path.setAttribute('aria-hidden','true');if(ol)ol.textContent='';}
      else{
        path.hidden=false;path.removeAttribute('aria-hidden');
        if(ol){
          ol.textContent='';
          var bits=(vis.getAttribute('data-path')||'').split('|').filter(Boolean);
          for(i=0;i<bits.length;i++){
            if(i){var sep=document.createElement('li');sep.className='komp-crumb-sep';sep.setAttribute('aria-hidden','true');sep.textContent=' › ';ol.appendChild(sep);}
            var li=document.createElement('li');
            li.className='komp-crumb'+(i>0&&i<bits.length-1?' komp-crumb-mid':'');
            li.textContent=bits[i];ol.appendChild(li);
          }
        }
      }
    }
  }
  function apply(){
    var komp=isKompHash();
    showTab(komp);
    if(komp)renderKomp();
    else showPath(parseKjede());
  }
  if(tabBek)tabBek.addEventListener('click',function(){setHash('#kjede');apply();});
  if(tabKomp)tabKomp.addEventListener('click',function(){setHash('#komp');apply();});
  root.addEventListener('click',function(e){
    var more=e.target.closest('.kjede-more');
    if(more){
      var row=more.closest('.kjede-row');
      var extra=row&&row.querySelector('.kjede-extra');
      var open=more.getAttribute('aria-expanded')==='true';
      more.setAttribute('aria-expanded', open?'false':'true');
      if(extra)extra.hidden=open;
      if(row)row.classList.toggle('kjede-open',!open);
      return;
    }
    var all=e.target.closest('.kjede-visalle');
    if(all){
      var col=all.closest('.kjede-col, .komp-list');
      var extra=col&&col.querySelector('.kjede-col-extra');
      var open=all.getAttribute('aria-expanded')==='true';
      all.setAttribute('aria-expanded', open?'false':'true');
      if(extra)extra.hidden=open;
      return;
    }
    var chip=e.target.closest('.komp-chip');
    if(chip){
      var cid=chip.getAttribute('data-id');
      if(cid){setHash('#komp='+encodeURIComponent(cid));apply();}
      return;
    }
    var kback=e.target.closest('.komp-back');
    if(kback){
      var kp=parseKomp();
      if(kp.length)kp=kp.slice(0,-1);
      setHash(kp.length?'#komp='+kp.map(encodeURIComponent).join('/'):'#komp');
      apply();
      return;
    }
    var krow=e.target.closest('.komp-row.komp-drill');
    if(krow&&!e.target.closest('a,button')){
      var id=krow.getAttribute('data-id');
      var comp=krow.getAttribute('data-comp');
      if(id&&comp){setHash('#komp='+encodeURIComponent(comp)+'/'+encodeURIComponent(id));apply();}
      return;
    }
    if(!can)return;
    var row=e.target.closest('.kjede-row.kjede-drill');
    if(row&&!e.target.closest('a,button')){
      var id2=row.getAttribute('data-id');
      if(!id2)return;
      var parts=parseKjede();
      if(!parts.length)parts=[ticker.split('.')[0]||ticker];
      parts=parts.concat([id2]);
      setHash('#kjede='+parts.map(encodeURIComponent).join('/'));apply();
    }
  });
  if(back)back.addEventListener('click',function(){
    var parts=parseKjede();
    if(parts.length)parts=parts.slice(0,-1);
    setHash(parts.length?'#kjede='+parts.map(encodeURIComponent).join('/'):'#kjede');
    apply();
  });
  document.addEventListener('keydown',function(e){
    if(e.key!=='Escape')return;
    if(isKompHash()){
      var kp=parseKomp();
      if(kp.length){kp=kp.slice(0,-1);setHash(kp.length?'#komp='+kp.map(encodeURIComponent).join('/'):'#komp');apply();}
      return;
    }
    if(can){
      var parts=parseKjede();
      if(parts.length){parts=parts.slice(0,-1);setHash(parts.length?'#kjede='+parts.map(encodeURIComponent).join('/'):'#kjede');apply();}
    }
  });
  window.addEventListener('hashchange',apply);
  apply();
})();
"""
