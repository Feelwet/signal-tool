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
                  "days": (ref - date.fromisoformat(cstart)).days}
    return out


def _price(p: float) -> str:
    return f"{p:,.2f}".replace(",", " ").replace(".", ",")


def line(s: dict | None) -> str:
    if not s:
        return ""
    parts = [f"På lista siden {_dm(s['since'])}"]
    if s.get("price") is not None:
        parts.append(f"inn på {_price(s['price'])}" + (f" (sluttkurs {_dm(s['price_date'])})" if s.get("price_date") else ""))
    if s.get("category") in CAT:
        n = s["days"]
        parts.append(f"{CAT[s['category']]} i {n} {'dag' if n == 1 else 'dager'}")
    return f'<p class="since mut">{E(" · ".join(parts))}</p>'


def cell(s: dict | None) -> str:
    if not s:
        return '<td class="since-c" data-v="">–</td>'
    return f'<td class="since-c" data-v="{E(s["since"])}">{_dm(s["since"])}</td>'


def mobile(s: dict | None) -> str:
    return f'<span class="since-m">siden {_dm(s["since"])}</span>' if s else ""


CSS = """.since{margin:-2px 0 8px;font-size:13px}.since-m{display:none}
th.sortable{cursor:pointer;user-select:none;white-space:nowrap}th.sortable[aria-sort=ascending]::after{content:" ▲"}th.sortable[aria-sort=descending]::after{content:" ▼"}
@media(max-width:599px){#tf-table th.since-h,#tf-table td.since-c{display:none}#tf-table .since-m{display:block;color:var(--mut);font-size:.8em}}
"""

JS = r"""<script>(()=>{const h=document.querySelector('#tf-table th.since-h');if(!h)return;h.setAttribute('role','button');h.tabIndex=0;
function go(){const tb=h.closest('table'),i=[...h.parentNode.children].indexOf(h),rows=[...tb.querySelectorAll('tr[data-cat]')],asc=h.getAttribute('aria-sort')!=='ascending';
rows.sort((a,b)=>{const x=a.children[i].dataset.v||'9',y=b.children[i].dataset.v||'9';return asc?x.localeCompare(y):y.localeCompare(x)});
const p=rows[0]&&rows[0].parentNode;rows.forEach(r=>p.appendChild(r));h.setAttribute('aria-sort',asc?'ascending':'descending')}
h.addEventListener('click',go);h.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}})})()</script>"""
