"""Kongress-rad på tickersiden (UxBot): offentlige House PTR-meldinger fra congress-collectoren. Ingen parti, ingen avkastningspåstander.
Manglende felt vises som «–». Eier (ektefelle/felles/barn) bare når PTR-teksten har eierkoden først i aktivafeltet."""
from __future__ import annotations
import re
from html import escape as E

TYPE = {"P": "Kjøp", "S": "Salg", "E": "Bytte"}
OWNER = {"SP": "ektefelle", "JT": "felles", "DC": "barn"}
SRC = "Kilde: Representantenes hus (House PTR). Senatet er ikke med. Meldes opptil 45 dager etter handelen."


def _k(n: int) -> str:
    return f"{n / 1e6:g}M" if n >= 1e6 else f"{round(n / 1e3):g}k"


def amount(a) -> str:
    ns = [int(x.replace(",", "")) for x in re.findall(r"\$?([\d,]{4,})", a or "")]
    if len(ns) >= 2:
        a, b = _k(ns[0] - 1 if ns[0] % 1000 == 1 else ns[0]), _k(ns[1])
        return f"${a[:-1]}–{b}" if a[-1] == b[-1] else f"${a}–{b}"
    # bare ett tall = PTR-teksten ble brutt over linjer; beløpsintervallet er ukjent -> «–»
    return "–"


def _dm(d) -> str:
    d = str(d or "")
    if re.match(r"\d{2}/\d{2}/\d{4}", d):
        return f"{d[3:5]}.{d[0:2]}"
    if re.match(r"\d{4}-\d{2}-\d{2}", d):
        return f"{d[8:10]}.{d[5:7]}"
    return "–"


def _iso(d) -> str:
    d = str(d or "")
    return f"{d[6:10]}-{d[0:2]}-{d[3:5]}" if re.match(r"\d{2}/\d{2}/\d{4}", d) else d


def parts(r: dict) -> dict:
    m = re.match(r"\s*(.*?)\s*\(([A-Z]{2})\d*\)\s*$", r.get("member") or "")
    name, st = (m.group(1), m.group(2)) if m else ((r.get("member") or "–").strip() or "–", "–")
    ow = (r.get("asset") or "").split(" ", 1)[0]
    return {"name": name, "state": st, "type": TYPE.get(r.get("type"), "–"), "amount": amount(r.get("amount")),
            "trade": _dm(r.get("trans_date")), "filed": _dm(r.get("filing_date")), "owner": OWNER.get(ow, "–"), "url": r.get("url") or ""}


def rows_for(snap: dict, ticker: str) -> list[dict]:
    seen, out = set(), []
    for r in snap.get("congress") or []:
        if (r.get("ticker") or "").upper() != ticker.upper():
            continue
        k = (r.get("member"), r.get("type"), r.get("trans_date"), r.get("amount"), r.get("url"))
        if k in seen:
            continue
        seen.add(k); out.append(r)
    return sorted(out, key=lambda r: (_iso(r.get("trans_date")), str(r.get("filing_date"))), reverse=True)


def _line(r: dict) -> str:
    p = parts(r)
    a1 = f'{E(p["name"])} ({E(p["state"])}) · {E(p["type"])} · {E(p["amount"])}'
    a2 = f'handlet {p["trade"]} · meldt {p["filed"]} · {E(p["owner"])}'
    inner = f'<span class="cg-1">{a1}</span><span class="cg-2">{a2}</span>'
    return (f'<li><a class="cg-row" href="{E(p["url"])}" rel="noopener">{inner}</a></li>' if p["url"]
            else f'<li><span class="cg-row">{inner}</span></li>')


def html(rows: list[dict]) -> str:
    if not rows:
        return ""
    first = "".join(_line(r) for r in rows[:5])
    rest = "".join(_line(r) for r in rows[5:])
    more = (f'<details class="cg-more"><summary>Vis alle ({len(rows)})</summary><ul class="cg">{rest}</ul></details>' if rest else "")
    return (f'<div class="cg-box"><h3>Kongress</h3><ul class="cg">{first}</ul>{more}<p class="cg-src">{E(SRC)}</p></div>')


CSS = """
.cg{list-style:none;margin:0;padding:0}.cg li{border-bottom:1px solid #21262d}
.cg-row{display:flex;flex-direction:column;justify-content:center;min-height:40px;box-sizing:border-box;padding:2px 0;color:inherit;text-decoration:none}
a.cg-row:hover .cg-1{text-decoration:underline}
.cg-1{font-size:13px;line-height:18px}.cg-2{font-size:11px;line-height:15px;color:#8b949e}
.cg-more summary{cursor:pointer;color:var(--acc);min-height:32px;line-height:32px}
.cg-src{margin:6px 0 0;font-size:11px;line-height:15px;color:#8b949e}
@media(min-width:600px){.cg-row{flex-direction:row;align-items:center;gap:10px;min-height:32px}.cg-2{white-space:nowrap}}
"""
