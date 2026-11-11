"""Bekreftede koblinger på tickersider (UxBot 11.11.2026, bindende).

Data ligger i site_config/kjeder/<TICKER>.json, med KOG.OL som første.
Komponentfanen «Hvem lager dette» bygges ikke her.
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
        return "kontrakt"

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
    else:
        typ = f"kontrakt {fmt_dmy(doc)}" if doc else "kontrakt"
        dato = fmt_dmy(doc) if doc else (c.get("dokumentdato") or "")
    return typ, dato


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
        f'{f"<div class=kjede-role>{E(role)}</div>" if role else ""}'
        f'{src}{more}</article>'
    )


def col_html(title: str, n: int, rows: list[str], empty: str = "") -> str:
    vis, rest = rows[:6], rows[6:]
    more = ""
    if rest:
        more = (f'<button type="button" class="kjede-visalle" aria-expanded="false">'
                f'Vis alle {len(rows)}</button>'
                f'<div class="kjede-col-extra" hidden>{"".join(rest)}</div>')
    body = "".join(vis) if vis else f'<p class="kjede-empty">{E(empty or "Ingen offentlig kilde")}</p>'
    # n i overskriften er bare kildebelagte (gitt inn)
    return (f'<div class="kjede-col">'
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


def jump_html(ticker: str, page_date: date | None = None, base: Path | None = None) -> str:
    data = load(ticker, base=base)
    if not data:
        return ""
    page = page_date or date.today()
    ns, nc = counts(data, page)
    return (f'<p class="kjede-jump"><a href="#kjede">Leverandører {ns} · Kunder {nc}</a></p>')


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
    # DOM-rekkefølge (fokus): sti → midtkort → leverandører → kunder
    grid = (f'<div class="kjede-grid">'
            f'{mid}'
            f'{col_html("Leverandører", ns, sup_h)}'
            f'{col_html("Kunder", nc, cus_h)}'
            f'</div>')
    payload = json.dumps({"ticker": ticker, "canDrill": drill}, ensure_ascii=False)
    return (
        f"<style>{CSS}</style>"
        f'<section id="kjede" class="kjede" data-can-drill="{1 if drill else 0}" '
        f'data-ticker="{E(ticker)}">'
        f'<h2 class="kjede-h">Verdikjede</h2>'
        f'{path}{grid}'
        f'<script type="application/json" id="kjede-data">{payload}</script>'
        f"<script>{JS}</script>"
        f"</section>"
    )


CSS = r"""
.kjede-jump{height:32px;line-height:32px;margin:0 0 8px;font-size:13px;overflow:hidden}
.kjede-jump a{display:inline-flex;align-items:center;min-height:32px;color:inherit;text-decoration:none}
.kjede-jump a:hover,.kjede-jump a:focus-visible{text-decoration:underline}
.kjede{margin:16px 0;overflow-x:hidden;min-width:0}
.kjede-h{margin:0 0 12px;font-size:20px;line-height:28px}
.kjede-path{display:flex;flex-wrap:wrap;align-items:center;gap:8px;min-height:44px;margin:0 0 12px}
.kjede-path[hidden],.kjede-back[hidden],.kjede-extra[hidden],.kjede-col-extra[hidden]{display:none}
.kjede-back{box-sizing:border-box;min-width:44px;min-height:44px;padding:0 12px;border:0;background:transparent;color:inherit;font:inherit;cursor:pointer}
.kjede-grid{display:grid;grid-template-columns:1fr;grid-template-areas:"mid" "sup" "cus";gap:24px;min-width:0}
.kjede-mid{grid-area:mid;box-sizing:border-box;min-width:0;padding:16px;background:#1c2430;border:1px solid #3b4757;border-radius:12px}
.kjede-col:nth-of-type(1){grid-area:sup}
.kjede-col:nth-of-type(2){grid-area:cus}
.kjede-col{min-width:0;overflow-x:hidden}
.kjede-col-h{margin:0 0 8px;font-size:15px;line-height:20px;font-weight:600}
.kjede-n{font-weight:400;color:#94a3b8}
.kjede-mid-name{font-size:18px;line-height:24px;font-weight:600}
.kjede-mid-tk{font-size:13px;line-height:18px;color:#94a3b8}
.kjede-ord{font-size:13px;line-height:18px;color:#94a3b8;margin:4px 0 0}
.kjede-prod-h{font-size:13px;line-height:18px;color:#94a3b8;margin:10px 0 4px}
.kjede-prod{display:inline-block;margin:0 6px 4px 0;padding:2px 8px;border:1px solid #3b4757;border-radius:4px;font-size:13px;line-height:18px}
.kjede-dev{margin:8px 0 0;font-size:13px;line-height:18px;color:#94a3b8}
.kjede-row{box-sizing:border-box;max-height:140px;overflow:hidden;margin:0 0 8px;padding:8px 8px 8px 10px;border:1px solid transparent;border-radius:8px;position:relative}
.kjede-row[data-line="solid"]{border-left:1px solid #94a3b8}
.kjede-row[data-line="dashed"]{border-left:1px dashed #94a3b8;background-image:none}
.kjede-row.kjede-io{border:1px dashed #94a3b8;max-height:140px}
.kjede-row.kjede-open{max-height:none;overflow:visible}
.kjede-name{font-size:15px;line-height:20px;font-weight:600}
.kjede-role{font-size:13px;line-height:18px;color:#94a3b8;margin:0 0 4px}
.kjede-src-line{font-size:12px;line-height:16px;margin:0}
.kjede-src{display:inline-flex;align-items:center;min-width:44px;min-height:44px;color:#94a3b8;text-decoration:none;font-size:12px;line-height:16px}
.kjede-src:hover,.kjede-src:focus-visible{text-decoration:underline}
.kjede-src-t{color:#94a3b8;font-size:12px;line-height:16px}
.kjede-chip{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;margin-left:6px;padding:0 8px;border:1px solid #3b4757;border-radius:4px;color:inherit;text-decoration:none;font-size:13px;line-height:18px;vertical-align:middle}
.kjede-gt{margin-left:6px;color:#94a3b8}
.kjede-more,.kjede-visalle{box-sizing:border-box;display:flex;align-items:center;min-width:44px;min-height:44px;padding:0 8px;border:0;background:transparent;color:inherit;font:inherit;font-size:13px;line-height:18px;cursor:pointer;text-align:left}
.kjede-empty{font-size:13px;line-height:18px;color:#94a3b8;margin:0}
@media(min-width:1280px){
  .kjede-grid{grid-template-columns:360px 400px 360px;grid-template-areas:"sup mid cus";gap:24px}
  .kjede-mid{width:400px}
  .kjede-col{width:360px}
}
@media(max-width:1279px){
  .kjede-grid{grid-template-columns:1fr;grid-template-areas:"mid" "sup" "cus";gap:24px}
}
"""

JS = r"""
(function(){
  var root=document.getElementById('kjede');
  if(!root)return;
  var can=root.getAttribute('data-can-drill')==='1';
  var ticker=root.getAttribute('data-ticker')||'';
  var pathEl=root.querySelector('.kjede-path');
  var back=root.querySelector('.kjede-back');
  function parseHash(){
    var h=location.hash||'';
    var m=h.match(/^#kjede(?:=(.*))?$/);
    if(!m)return [];
    if(!m[1])return [];
    var parts=m[1].split('/').filter(Boolean);
    if(parts[0]&&ticker&&parts[0]!==ticker.split('.')[0]&&parts[0]!==ticker)parts=parts;
    return parts;
  }
  function setHash(parts){
    var h=!parts.length?'#kjede':'#kjede='+parts.map(encodeURIComponent).join('/');
    if(location.hash!==h)history.replaceState(null,'',h);
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
  function apply(){
    var parts=parseHash();
    showPath(parts);
  }
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
      var col=all.closest('.kjede-col');
      var extra=col&&col.querySelector('.kjede-col-extra');
      var open=all.getAttribute('aria-expanded')==='true';
      all.setAttribute('aria-expanded', open?'false':'true');
      if(extra)extra.hidden=open;
      return;
    }
    if(!can)return;
    var row=e.target.closest('.kjede-row.kjede-drill');
    if(row&&!e.target.closest('a,button')){
      var id=row.getAttribute('data-id');
      if(!id)return;
      var parts=parseHash();
      if(!parts.length)parts=[ticker.split('.')[0]||ticker];
      parts=parts.concat([id]);
      setHash(parts);apply();
    }
  });
  if(back)back.addEventListener('click',function(){
    var parts=parseHash();
    if(parts.length)parts=parts.slice(0,-1);
    setHash(parts);apply();
  });
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&can){
      var parts=parseHash();
      if(parts.length){parts=parts.slice(0,-1);setHash(parts);apply();}
    }
  });
  window.addEventListener('hashchange',apply);
  apply();
})();
"""
