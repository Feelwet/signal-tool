"""«På lista siden DD.MM · inn på <kurs> (sluttkurs DD.MM) · <kategori> i N dager» fra logs/categories.csv.

«Siden» = første dato i den siste sammenhengende perioden på lista. Én enkelt kjøring der tickeren mangler (f.eks. en kilde
som feilet den dagen) bryter ikke perioden; mangler den i to eller flere kjøringer på rad, starter en ny periode når den
kommer tilbake. N = dagens dato minus første dato i nåværende kategori-periode, i kalenderdager (ikke antall rader).
Kursen er sluttkursen i periodens første rad, med price_date."""
from __future__ import annotations

import csv
from datetime import date
from html import escape as E
from pathlib import Path

from .config import LOGS

LOG = LOGS / "categories.csv"
CAT = {"kjop": "Kjøp", "hold": "Hold", "watch": "Følg"}
MAX_MISS = 1   # antall kjøringer på rad tickeren kan mangle uten at perioden brytes


def _dm(d: str) -> str:
    return f"{d[8:10]}.{d[5:7]}"


ENTRY_LOG = LOGS / "entry_prices.csv"
ENTRY_COLS = ["date", "ticker", "category", "price", "price_date"]


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("date") and r.get("ticker")]


def load(path: Path = LOG, entry_path: Path | None = None) -> list[dict]:
    """Rader fra fremoverloggen + innkurs-sideloggen (logs/entry_prices.csv) for tickere som ikke logges i categories.csv
    (ETF-er, BA.L o.l.). Sideloggen brukes bare til «siden»/innkurs/avkastning på siden, aldri i treffrater eller GS-indeks."""
    rows = _read(path)
    if entry_path is None:
        entry_path = ENTRY_LOG if path == LOG else None
    if entry_path is not None:
        have = {(r["date"], r["ticker"]) for r in rows}
        rows += [r for r in _read(entry_path) if (r["date"], r["ticker"]) not in have]
    return rows


def append_entries(snap: dict, logged: set[str], path: Path = ENTRY_LOG) -> int:
    """AnalBot 28.10: snapshot-tickere som ikke får rad i categories.csv (ikke loggbare) får innkurs (sluttkurs + price_date)
    i sideloggen. Bare dagens rader skrives (en ny kjøring samme dag erstatter dem); rader for andre datoer røres aldri."""
    day = str(snap.get("date") or "")
    if not day:
        return 0
    new = []
    for e in snap.get("tickers", []):
        st = e.get("stats") or {}
        if e["ticker"] in logged or st.get("close") in (None, "") or st.get("close") != st.get("close"):
            continue
        new.append({"date": day, "ticker": e["ticker"], "category": e.get("category") or "", "price": round(float(st["close"]), 4),
                    "price_date": str(st.get("last_date") or "")[:10]})
    old = [r for r in _read(path) if r["date"] != day]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ENTRY_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(old + new)
    return len(new)


def compute(rows: list[dict], today: str | None = None) -> dict:
    runs = sorted({r["date"] for r in rows})
    by: dict[str, dict[str, dict]] = {}
    for r in rows:
        by.setdefault(r["ticker"], {})[r["date"]] = r
    out = {}
    for t, rs in by.items():
        last = max(rs)
        if today and last < max(runs):
            continue                      # ikke på lista i siste kjøring
        idx = runs.index(last)
        start, miss, i = last, 0, idx
        while i >= 0:
            d = runs[i]
            if d in rs:
                start, miss = d, 0
            else:
                miss += 1
                if miss > MAX_MISS:
                    break
            i -= 1
        cat = rs[last]["category"]
        cstart = last
        for d in sorted((d for d in rs if start <= d <= last), reverse=True):
            if rs[d]["category"] != cat:
                break
            cstart = d
        first = rs[start]
        ref = date.fromisoformat(today or last)
        try:
            price = float(first.get("price") or "")
        except ValueError:
            price = None
        out[t] = {"since": start, "price": price, "price_date": first.get("price_date") or None, "category": cat,
                  "days": (ref - date.fromisoformat(cstart)).days,
                  "list_days": (ref - date.fromisoformat(start)).days, "illiquid": "illiquid" in (rs[last].get("flags") or "").split("|")}
    return out


def _price(p: float) -> str:
    return f"{p:,.2f}".replace(",", " ").replace(".", ",")


def line(s: dict | None, chip: str = "", ret: dict | None = None) -> str:
    """«[chip] Siden DD.MM · inn 109,52 (DD.MM) · N dager · +4,7 %» – én linje, nowrap + ellipsis."""
    if not s:
        return f'<p class="since mut">{chip}</p>' if chip else ""
    parts = [f"Siden {_dm(s['since'])}"]
    if s.get("price") is not None:
        parts.append(f"inn {_price(s['price'])}" + (f" ({_dm(s['price_date'])})" if s.get("price_date") else ""))
    if s.get("category") in CAT:
        n = s["days"]
        parts.append(f"{n} {'dag' if n == 1 else 'dager'}")
    if ret and ret.get("r") is not None:
        parts.append(NEW_T if ret.get("new") else pct(ret["r"]))
    return f'<p class="since mut">{chip + " " if chip else ""}{E(" · ".join(parts))}</p>'


def line_rk(s: dict | None, lead: str, ret: dict | None = None) -> str:
    """Risikochip + (i) først (aldri klippet), deretter «Siden … · inn … · +x %» med ellipsis. Ingen kategoridager."""
    parts = []
    if s:
        parts.append(f"Siden {_dm(s['since'])}")
        if s.get("price") is not None:
            parts.append(f"inn {_price(s['price'])}" + (f" ({_dm(s['price_date'])})" if s.get("price_date") else ""))
    t = f'<span class="sl-t">{E(" · ".join(parts))}</span>' if parts else ""
    if ret and ret.get("new"):
        t += f'<span class="sl-r rnew">&nbsp;·&nbsp;{NEW_T}</span>{ri(NEW_TIP)}'
    elif ret and ret.get("r") is not None:
        t += (f'<span class="sl-r">&nbsp;·&nbsp;{E(pct(ret["r"]))}</span><button type="button" class="rt-i" aria-expanded="false" '
              f'aria-controls="rt-tip" aria-label="Om avkastning">ⓘ</button>')
    elif ret and ret.get("stale"):
        t += f'<span class="sl-r rst">&nbsp;·&nbsp;–</span>{ri(ret_tip(ret))}'
    return f'<p class="since mut rk-line">{lead}{t}</p>'


MIN_DAYS = 0   # AnalBot 25.10: avkastning fra price_date fra første dag
NOTE_T = ("Avkastningen er regnet fra sluttkursen dagen aksjen kom på lista (inn {dm}) til siste sluttkurs, og sammenlignet med indeksen "
          "på samme børs. Var aksjen ute av lista en stund, starter tellingen på nytt. Tallet viser hva som har skjedd, ikke hva som vil skje, "
          "og er ikke et kjøpsråd.")
NOTE = NOTE_T.replace(" (inn {dm})", "")   # felles (i) i kolonneoverskriften: ingen enkeltdato


def tip_html(s: dict | None, r: dict | None = None) -> str:
    k = ret_tip(r, s) if r and r.get("last") and not r.get("stale") else ""
    return f'<p id="rt-tip" class="rk-tip" hidden>{E(k + ". ") if k else ""}{E(note_for(s))} <a href="../metode.html#laering">Slik bruker vi dette tallet ›</a></p>'


def note_for(s: dict | None) -> str:
    return NOTE_T.format(dm=_dm(s["price_date"])) if s and s.get("price_date") else NOTE


def pct(x: float) -> str:
    return f"{x*100:+.1f} %".replace(".", ",").replace("-", "−")


BENCH = {"oslo": ("OSEBX.OL", "OSEBX"), "nasdaq": ("^IXIC", "Nasdaq"), "nyse": ("^NYA", "NYSE"), "arca": ("^NYA", "NYSE")}


def bench_for(ticker: str):
    """Hovedindeksen på børsen tickeren er notert på (exchange fra names.json / Yahoo). None = ukjent børs."""
    from .names import exchange
    ex = (exchange(ticker) or "").lower().replace(" ", "")
    if ticker.endswith(".OL") or ex.startswith("oslo"):
        return BENCH["oslo"]
    if ex.startswith("nasdaq") or ex in ("nms", "ngm", "ncm"):
        return BENCH["nasdaq"]
    if "arca" in ex or ex in ("amex", "nysemkt", "nyseamerican", "pcx", "ase"):
        return BENCH["arca"]
    if ex.startswith("nyse") or ex == "nyq":
        return BENCH["nyse"]
    return None


def pp(x: float) -> str:
    return f"{x*100:+.1f} pp".replace(".", ",").replace("-", "−")


def ret(s: dict | None, close, last_date: str | None, idx: dict | None = None, ticker: str = "", run_date: str | None = None) -> dict | None:
    """Avkastning fra innkurs (sluttkurs på price_date) til siste sluttkurs. None ved manglende data eller < 5 dager på lista.
    Meravkastning (prosentpoeng) mot hovedindeksen på tickerens børs over samme datoer, bare med ekte indeksdata for begge datoene.
    AnalBot 28.10: «last» = datoen for siste sluttkurs; er den mer enn 2 handelsdager eldre enn kjøringsdatoen (run_date),
    skjules tallet (r = None, stale = True)."""
    if not s or s.get("price") in (None, 0) or close in (None, 0) or s.get("list_days", 0) < MIN_DAYS:
        return None
    from .freshness import is_stale
    last = str(last_date)[:10] if last_date else None
    if run_date and is_stale(last, run_date):
        return {"r": None, "ex": None, "bench": None, "illiquid": bool(s.get("illiquid")), "stale": True, "last": last}
    r = float(close) / float(s["price"]) - 1
    ex, bn = None, None
    b = bench_for(ticker)
    if b:
        bn = b[1]
        ser = (idx or {}).get(b[0])
        if ser and s.get("price_date") and last_date and s["price_date"] in ser and last_date in ser:
            ex = r - (ser[last_date] / ser[s["price_date"]] - 1)
    # UxBot/AnalBot 28.10: kom på lista i dag (innkursdato = siste kursdato) -> «Ny i dag», sorteres som tom
    new = bool(last and s.get("price_date") and str(s["price_date"])[:10] == last)
    return {"r": r, "ex": ex, "bench": bn, "illiquid": bool(s.get("illiquid")), "stale": False, "last": last, "new": new}


def _cls(x):
    return "rup" if x > 0.0005 else "rdn" if x < -0.0005 else "r0"


NO_ENTRY = "Ingen innkurs ennå"


def ri(text: str, label: str = "") -> str:
    """Eksisterende ⓘ-mønster (som i kolonneoverskriften), kompakt variant i tabellcellen. `label` (f.eks. «Ny i dag» eller «–»)
    ligger inne i trykkflaten, så et trykk på teksten åpner samme popover som ⓘ (UxBot 28.10)."""
    return f'<span class="ri ri-c" tabindex="0" aria-expanded="false" aria-label="{E(text)}">{label}ⓘ<span class="tip">{E(text)}</span></span>'


NEW_T, NEW_TIP = "Ny i dag", "Avkastning vises fra neste handelsdag"


def ret_tip(r: dict | None, s: dict | None = None) -> str:
    """Tooltip-tekst: «Kurs per DD.MM», «Kurs mangler etter DD.MM» eller «Ingen innkurs ennå»."""
    if r and r.get("stale"):
        return f"Kurs mangler etter {_dm(r['last'])}" if r.get("last") else "Kurs mangler"
    if r and r.get("last"):
        return f"Kurs per {_dm(r['last'])}"
    if not r and (not s or s.get("price") in (None, 0)):
        return NO_ENTRY
    return ""


def ret_inner(r: dict | None, s: dict | None = None) -> str:
    tip = ret_tip(r, s)
    if not r or r.get("r") is None:
        cls = "rv rst" if r and r.get("stale") else "rv rna"
        return ri(tip, f'<span class="{cls}">–</span>') if tip else f'<span class="{cls}">–</span>'
    if r.get("new"):
        return ri(NEW_TIP, f'<span class="rnew">{NEW_T}</span>')
    w = ' <span class="ill" title="Lite omsatt aksje">⚠</span>' if r["illiquid"] else ""
    ex = f'<span class="rex">{"vs " + r["bench"] + " " + pp(r["ex"]) if r.get("ex") is not None else "–"}</span>'
    return f'<span class="rv {_cls(r["r"])}">{pct(r["r"])}</span>{ri(tip) if tip else ""}{w}{ex}'


def ret_cell(r: dict | None, s: dict | None = None) -> str:
    v = f"{r['r']:.6f}" if r and r.get("r") is not None and not r.get("new") else ""
    st = ' data-stale="1"' if r and r.get("stale") else ""
    lt = f' data-last="{E(r["last"])}"' if r and r.get("last") else ""
    lt += ' data-new="1"' if r and r.get("new") else ""
    return f'<td class="ret-c" data-v="{v}"{st}{lt}>{ret_inner(r, s)}</td>'


def cell(s: dict | None) -> str:
    if not s:
        return '<td class="since-c" data-v="" data-sort="">–</td>'
    return f'<td class="since-c" data-v="{E(s["since"])}" data-sort="{E(s["since"])}">{_dm(s["since"])}</td>'


def mobile(s: dict | None, r: dict | None = None) -> str:
    if not s:
        return ""
    return f'<span class="since-m">siden {_dm(s["since"])}{"<span class=ret-m>" + ret_inner(r, s) + "</span>" if r else ""}</span>' 


CSS = """.since{margin:-2px 0 8px;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.since .cat{margin-right:2px}@media(max-width:599px){.thead h1.nm1{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}p.since{margin:-8px 0 8px;line-height:20px}p.since .cat{padding-top:0;padding-bottom:0}}.since-m{display:none}
td.ret-c,th.ret-h{text-align:right;white-space:nowrap}.rv.rup{color:#3fb950}.rv.rdn{color:#f85149}.rv.r0{color:var(--mut)}.rv.rst,.sl-r.rst{color:#64748b}.rnew{font-size:11px;color:#94a3b8;white-space:nowrap}.ri.ri-c{min-width:0;min-height:0;margin:0;padding:0 0 0 2px;font-size:.8em;vertical-align:baseline;display:inline;position:relative}.ri.ri-c>.rv,.ri.ri-c>.rnew{font-size:1.25em}.ri.ri-c .rnew{font-size:11px}.ri.ri-c::before{content:"";position:absolute;left:50%;top:50%;width:max(100%,32px);height:max(100%,32px);transform:translate(-50%,-50%)}.ri.ri-c .tip{width:max-content;max-width:260px;font-size:13px;line-height:1.35}.ri.ri-c .tip.pop{position:fixed;right:auto}.rex{display:block;color:var(--mut);font-size:.8em}.ill{font-size:.8em}
.ri{position:relative;display:inline-block;cursor:pointer;border:0;background:none;color:var(--mut);font:inherit;padding:0 2px}.ri .tip{display:none;position:absolute;right:0;top:1.4em;z-index:5;width:240px;white-space:normal;text-align:left;font-weight:400;font-size:12px;background:var(--card,#fff);border:1px solid var(--line,#ccc);border-radius:6px;padding:6px}.ri[aria-expanded=true] .tip{display:block}.ri{min-width:44px;min-height:44px;margin:-14px -8px -14px -10px;display:inline-flex;align-items:center;justify-content:center;vertical-align:middle}
.retnote{font-size:12px}tr.rowlink{cursor:pointer}tr.rowlink:hover td,tr.rowlink:focus-visible td{background:#161b22}tr.rowlink td{height:44px}tr.rowlink:focus-visible{outline:2px solid var(--mut)}
th.sortable{cursor:pointer;user-select:none;white-space:nowrap}th.sortable[aria-sort]::after{font-size:12px}th.sortable[aria-sort=ascending]::after{content:" ▲"}th.sortable[aria-sort=descending]::after{content:" ▼"}
@media(max-width:599px){#tf-table th.since-h,#tf-table td.since-c{display:none}#tf-table .since-m{display:block;color:var(--mut);font-size:.8em}
#tf-table .ret-m{display:none!important}#tf-table td.ret-c,#tf-table th.ret-h{font-size:12px;padding-left:4px;padding-right:4px;white-space:normal}#tf-table td.ret-c,#tf-table th.ret-h{overflow-wrap:normal;word-break:normal;width:auto;min-width:0}#tf-table td.ret-c .rv{white-space:nowrap}#tf-table td.ret-c .rex{display:block;font-size:11px;white-space:normal;line-height:1.25}#tf-table td.mcol{padding-left:2px;padding-right:2px}#tf-table th.ret-h .ri .tip{right:-8px}table:has(tr[data-cat]) tr>:nth-child(5),table:has(tr[data-cat]) tr>:nth-child(6){display:none}}
"""

JS = r"""<script>(()=>{const score=r=>{const t=(r.children[2]&&r.children[2].querySelector('.score'));const n=t?parseFloat(t.textContent):NaN;return Number.isFinite(n)?n:-Infinity};
const place=(tb,rows)=>{const p=rows[0]&&rows[0].parentNode,g=tb.querySelector('tr.grp');if(!p)return;rows.forEach(r=>g&&g.parentNode===p?p.insertBefore(r,g):p.appendChild(r))};
const urlSort=dir=>{const u=new URL(location.href);if(dir==='descending')u.searchParams.set('sort','dato_desc');else if(dir==='ascending')u.searchParams.set('sort','dato_asc');else u.searchParams.delete('sort');history.replaceState(null,'',u)};
const clearSortUrl=()=>{const u=new URL(location.href);if(u.searchParams.has('sort')){u.searchParams.delete('sort');history.replaceState(null,'',u)}};
function sortDato(h,dir){const tb=h.closest('table'),rows=[...tb.querySelectorAll('tr[data-cat]:not([data-unr])')],desc=dir==='descending';
rows.sort((a,b)=>{const x=(a.querySelector('td.since-c')||{}).dataset.sort||'',y=(b.querySelector('td.since-c')||{}).dataset.sort||'';
if(!x&&!y)return score(b)-score(a);if(!x)return 1;if(!y)return -1;const c=x.localeCompare(y);if(c)return desc?-c:c;return score(b)-score(a)});
place(tb,rows);tb.querySelectorAll('th.sortable').forEach(o=>o!==h&&o.removeAttribute('aria-sort'));h.setAttribute('aria-sort',dir);urlSort(dir)}
document.querySelectorAll('#tf-table th.sortable').forEach(h=>{h.setAttribute('role','button');h.tabIndex=0;
function go(e){if(e&&e.target.closest('.ri'))return;if(h.classList.contains('since-h')){const next=h.getAttribute('aria-sort')==='descending'?'ascending':'descending';return sortDato(h,next)}
const tb=h.closest('table'),i=[...h.parentNode.children].indexOf(h),rows=[...tb.querySelectorAll('tr[data-cat]:not([data-unr])')],asc=h.getAttribute('aria-sort')!=='ascending',num=h.classList.contains('ret-h')||h.classList.contains('rk-h');
rows.sort((a,b)=>{const x=a.children[i].dataset.v,y=b.children[i].dataset.v;if(!x&&!y)return 0;if(!x)return 1;if(!y)return -1;const c=num?(+x)-(+y):x.localeCompare(y);return asc?c:-c});
place(tb,rows);tb.querySelectorAll('th.sortable').forEach(o=>o!==h&&o.removeAttribute('aria-sort'));h.setAttribute('aria-sort',asc?'ascending':'descending');clearSortUrl()}
h.addEventListener('click',go);h.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}})});
const sp=new URL(location.href).searchParams.get('sort'),sh=document.querySelector('#tf-table th.since-h');
if(sh&&(sp==='dato_desc'||sp==='dato_asc'))sortDato(sh,sp==='dato_desc'?'descending':'ascending');
const riPos=b=>{const t=b.querySelector('.tip');if(!t||!b.classList.contains('ri-c'))return;t.classList.add('pop');const r=b.getBoundingClientRect(),w=Math.min(260,innerWidth-16);t.style.maxWidth=w+'px';const tw=Math.min(t.offsetWidth||w,w);t.style.left=Math.max(8,Math.min(r.left+r.width/2-tw/2,innerWidth-tw-8))+'px';t.style.top=(r.bottom+6)+'px'};
document.querySelectorAll('.ri').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();const o=b.getAttribute('aria-expanded')==='true';document.querySelectorAll('.ri[aria-expanded=true]').forEach(x=>x!==b&&x.setAttribute('aria-expanded','false'));b.setAttribute('aria-expanded',o?'false':'true');if(!o)riPos(b)}));addEventListener('scroll',()=>document.querySelectorAll('.ri.ri-c[aria-expanded=true]').forEach(b=>b.setAttribute('aria-expanded','false')),{passive:true});const riX=()=>document.querySelectorAll('.ri[aria-expanded=true]').forEach(b=>b.setAttribute('aria-expanded','false'));document.addEventListener('click',e=>{if(!e.target.closest('.ri'))riX()});document.addEventListener('keydown',e=>{if(e.key==='Escape')riX()});
document.querySelectorAll('tr.rowlink').forEach(r=>{const skip=e=>e.target.closest('a,button,input,label,.ri,.mstar');
const go=(e,nt)=>{if(skip(e))return;const u=r.dataset.href;if(nt||e.ctrlKey||e.metaKey||e.shiftKey)window.open(u,'_blank','noopener');else location.href=u};
r.addEventListener('click',e=>go(e,false));r.addEventListener('auxclick',e=>{if(e.button===1){e.preventDefault();go(e,true)}});
r.addEventListener('mousedown',e=>{if(e.button===1&&!skip(e))e.preventDefault()});
r.addEventListener('keydown',e=>{if(e.target===r&&e.key==='Enter'){e.preventDefault();go(e,e.ctrlKey||e.metaKey)}})});
})()</script>"""
