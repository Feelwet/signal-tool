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


def load(path: Path = LOG) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("date") and r.get("ticker")]


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
        parts.append(pct(ret["r"]))
    return f'<p class="since mut">{chip + " " if chip else ""}{E(" · ".join(parts))}</p>'


def line_rk(s: dict | None, lead: str, ret: dict | None = None) -> str:
    """Risikochip + (i) først (aldri klippet), deretter «Siden … · inn … · +x %» med ellipsis. Ingen kategoridager."""
    parts = []
    if s:
        parts.append(f"Siden {_dm(s['since'])}")
        if s.get("price") is not None:
            parts.append(f"inn {_price(s['price'])}" + (f" ({_dm(s['price_date'])})" if s.get("price_date") else ""))
    t = f'<span class="sl-t">{E(" · ".join(parts))}</span>' if parts else ""
    if ret and ret.get("r") is not None:
        t += (f'<span class="sl-r">&nbsp;·&nbsp;{E(pct(ret["r"]))}</span><button type="button" class="rt-i" aria-expanded="false" '
              f'aria-controls="rt-tip" aria-label="Om avkastning">ⓘ</button>')
    return f'<p class="since mut rk-line">{lead}{t}</p>'


MIN_DAYS = 0   # AnalBot 25.10: avkastning fra price_date fra første dag
NOTE_T = ("Avkastningen er regnet fra sluttkursen dagen aksjen kom på lista (inn {dm}) til siste sluttkurs, og sammenlignet med indeksen "
          "på samme børs. Var aksjen ute av lista en stund, starter tellingen på nytt. Tallet viser hva som har skjedd, ikke hva som vil skje, "
          "og er ikke et kjøpsråd.")
NOTE = NOTE_T.replace(" (inn {dm})", "")   # felles (i) i kolonneoverskriften: ingen enkeltdato


def tip_html(s: dict | None) -> str:
    return f'<p id="rt-tip" class="rk-tip" hidden>{E(note_for(s))}</p>'


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


def ret(s: dict | None, close, last_date: str | None, idx: dict | None = None, ticker: str = "") -> dict | None:
    """Avkastning fra innkurs (sluttkurs på price_date) til siste sluttkurs. None ved manglende data eller < 5 dager på lista.
    Meravkastning (prosentpoeng) mot hovedindeksen på tickerens børs over samme datoer, bare med ekte indeksdata for begge datoene."""
    if not s or s.get("price") in (None, 0) or close in (None, 0) or s.get("list_days", 0) < MIN_DAYS:
        return None
    r = float(close) / float(s["price"]) - 1
    ex, bn = None, None
    b = bench_for(ticker)
    if b:
        bn = b[1]
        ser = (idx or {}).get(b[0])
        if ser and s.get("price_date") and last_date and s["price_date"] in ser and last_date in ser:
            ex = r - (ser[last_date] / ser[s["price_date"]] - 1)
    return {"r": r, "ex": ex, "bench": bn, "illiquid": bool(s.get("illiquid"))}


def _cls(x):
    return "rup" if x > 0.0005 else "rdn" if x < -0.0005 else "r0"


def ret_inner(r: dict | None) -> str:
    if not r:
        return "–"
    w = ' <span class="ill" title="Lite omsatt aksje">⚠</span>' if r["illiquid"] else ""
    ex = f'<span class="rex">{"vs " + r["bench"] + " " + pp(r["ex"]) if r.get("ex") is not None else "–"}</span>'
    return f'<span class="rv {_cls(r["r"])}">{pct(r["r"])}</span>{w}{ex}'


def ret_cell(r: dict | None) -> str:
    v = f"{r['r']:.6f}" if r else ""
    return f'<td class="ret-c" data-v="{v}">{ret_inner(r)}</td>'


def cell(s: dict | None) -> str:
    if not s:
        return '<td class="since-c" data-v="">–</td>'
    return f'<td class="since-c" data-v="{E(s["since"])}">{_dm(s["since"])}</td>'


def mobile(s: dict | None, r: dict | None = None) -> str:
    if not s:
        return ""
    return f'<span class="since-m">siden {_dm(s["since"])}{"<span class=ret-m>" + ret_inner(r) + "</span>" if r else ""}</span>' 


CSS = """.since{margin:-2px 0 8px;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.since .cat{margin-right:2px}@media(max-width:599px){.thead h1.nm1{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}p.since{margin:-8px 0 8px;line-height:20px}p.since .cat{padding-top:0;padding-bottom:0}}.since-m{display:none}
td.ret-c,th.ret-h{text-align:right;white-space:nowrap}.rv.rup{color:#3fb950}.rv.rdn{color:#f85149}.rv.r0{color:var(--mut)}.rex{display:block;color:var(--mut);font-size:.8em}.ill{font-size:.8em}
.ri{position:relative;display:inline-block;cursor:pointer;border:0;background:none;color:var(--mut);font:inherit;padding:0 2px}.ri .tip{display:none;position:absolute;right:0;top:1.4em;z-index:5;width:240px;white-space:normal;text-align:left;font-weight:400;font-size:12px;background:var(--card,#fff);border:1px solid var(--line,#ccc);border-radius:6px;padding:6px}.ri[aria-expanded=true] .tip{display:block}.ri{min-width:44px;min-height:44px;margin:-14px -8px -14px -10px;display:inline-flex;align-items:center;justify-content:center;vertical-align:middle}
.retnote{font-size:12px}tr.rowlink{cursor:pointer}tr.rowlink:hover td,tr.rowlink:focus-visible td{background:#161b22}tr.rowlink td{height:44px}tr.rowlink:focus-visible{outline:2px solid var(--mut)}
th.sortable{cursor:pointer;user-select:none;white-space:nowrap}th.sortable[aria-sort=ascending]::after{content:" ▲"}th.sortable[aria-sort=descending]::after{content:" ▼"}
@media(max-width:599px){#tf-table th.since-h,#tf-table td.since-c{display:none}#tf-table .since-m{display:block;color:var(--mut);font-size:.8em}
#tf-table .ret-m{display:none!important}#tf-table td.ret-c,#tf-table th.ret-h{font-size:12px;padding-left:4px;padding-right:4px;white-space:normal}#tf-table td.ret-c,#tf-table th.ret-h{overflow-wrap:normal;word-break:normal;width:72px;min-width:72px}#tf-table td.ret-c .rv{white-space:nowrap}#tf-table td.ret-c .rex{display:block;font-size:11px;white-space:normal;line-height:1.25}#tf-table td.mcol{padding-left:2px;padding-right:2px}#tf-table th.ret-h .ri .tip{right:-8px}table:has(tr[data-cat]) tr>:nth-child(5),table:has(tr[data-cat]) tr>:nth-child(6){display:none}}
"""

JS = r"""<script>(()=>{document.querySelectorAll('#tf-table th.sortable').forEach(h=>{h.setAttribute('role','button');h.tabIndex=0;
function go(e){if(e&&e.target.closest('.ri'))return;const tb=h.closest('table'),i=[...h.parentNode.children].indexOf(h),rows=[...tb.querySelectorAll('tr[data-cat]:not([data-unr])')],asc=h.getAttribute('aria-sort')!=='ascending',num=h.classList.contains('ret-h')||h.classList.contains('rk-h');
rows.sort((a,b)=>{const x=a.children[i].dataset.v,y=b.children[i].dataset.v;if(!x&&!y)return 0;if(!x)return 1;if(!y)return -1;const c=num?(+x)-(+y):x.localeCompare(y);return asc?c:-c});
const p=rows[0]&&rows[0].parentNode,g=tb.querySelector('tr.grp');rows.forEach(r=>g&&g.parentNode===p?p.insertBefore(r,g):p.appendChild(r));tb.querySelectorAll('th.sortable').forEach(o=>o!==h&&o.removeAttribute('aria-sort'));h.setAttribute('aria-sort',asc?'ascending':'descending')}
h.addEventListener('click',go);h.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}})});
document.querySelectorAll('.ri').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();b.setAttribute('aria-expanded',b.getAttribute('aria-expanded')==='true'?'false':'true')}));const riX=()=>document.querySelectorAll('.ri[aria-expanded=true]').forEach(b=>b.setAttribute('aria-expanded','false'));document.addEventListener('click',e=>{if(!e.target.closest('.ri'))riX()});document.addEventListener('keydown',e=>{if(e.key==='Escape')riX()});
document.querySelectorAll('tr.rowlink').forEach(r=>{const skip=e=>e.target.closest('a,button,input,label,.ri,.mstar');
const go=(e,nt)=>{if(skip(e))return;const u=r.dataset.href;if(nt||e.ctrlKey||e.metaKey||e.shiftKey)window.open(u,'_blank','noopener');else location.href=u};
r.addEventListener('click',e=>go(e,false));r.addEventListener('auxclick',e=>{if(e.button===1){e.preventDefault();go(e,true)}});
r.addEventListener('mousedown',e=>{if(e.button===1&&!skip(e))e.preventDefault()});
r.addEventListener('keydown',e=>{if(e.target===r&&e.key==='Enter'){e.preventDefault();go(e,e.ctrlKey||e.metaKey)}})});
})()</script>"""
