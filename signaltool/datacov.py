"""«Data X/7»: hvilke av sju grunnfelt som faktisk finnes i snapshotet for en ticker.

Bare det som allerede er hentet telles; ingenting hentes fra reservekilder. ETF-er måles av 2 (kurs, 50-dagers snitt):
sektor, markedsverdi, P/E, neste rapport og analytikere gjelder ikke for fond."""
from __future__ import annotations

from html import escape as E

FIELDS = (("close", "Kurs"), ("sma50", "50-dagers snitt"), ("sector", "Sektor"), ("marketCap", "Markedsverdi"),
          ("trailingPE", "P/E"), ("next_earnings", "Neste rapport"), ("numberOfAnalystOpinions", "Analytikere"))
ETF_ONLY = ("close", "sma50")
NA = "Ikke tilgjengelig ennå"
NOT_REL = "Ikke relevant"


def is_etf(e: dict) -> bool:
    from .categories import ETFS
    return e.get("ticker") in ETFS or str((e.get("decision") or {}).get("quoteType") or "").upper() == "ETF"


def _val(e: dict, k: str):
    st, dec = e.get("stats") or {}, e.get("decision") or {}
    v = st.get(k) if k in ("close", "sma50") else dec.get(k)
    if v is None and k in ("close", "sma50"):
        v = dec.get(k)
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, float) and v != v:   # NaN
        return None
    return v


def coverage(e: dict) -> dict:
    etf = is_etf(e)
    keys = [k for k, _ in FIELDS if not etf or k in ETF_ONLY]
    have = [k for k in keys if _val(e, k) is not None]
    return {"etf": etf, "have": len(have), "of": len(keys), "missing": [lab for k, lab in FIELDS if k in keys and k not in have]}


def chip(e: dict) -> str:
    c = coverage(e)
    if c["have"] >= c["of"]:
        return ""
    tip = "Mangler: " + ", ".join(c["missing"])
    return f'<span class="dchip" title="{E(tip)}" aria-label="Data {c["have"]} av {c["of"]}. {E(tip)}">Data {c["have"]}/{c["of"]}</span>'


def _fmt(k: str, v) -> str:
    if k == "marketCap":
        v = float(v)
        return f"{v/1e12:.2f} bill." if v >= 1e12 else f"{v/1e9:.1f} mrd." if v >= 1e9 else f"{v/1e6:.0f} mill."
    if k in ("close", "sma50", "trailingPE"):
        return f"{float(v):.2f}".replace(".", ",")
    if k == "numberOfAnalystOpinions":
        return f"{int(v)}"
    return E(str(v)[:10] if k == "next_earnings" else str(v))


def card(e: dict) -> str:
    etf = is_etf(e)
    rows = []
    for k, lab in FIELDS:
        if etf and k not in ETF_ONLY:
            cell = f'<span class="mut">{NOT_REL}</span>'
        else:
            v = _val(e, k)
            cell = f'<span class="mut">{NA}</span>' if v is None else _fmt(k, v)
        rows.append(f"<tr><td>{lab}</td><td>{cell}</td></tr>")
    c = coverage(e)
    return (f'<div class="card dcov"><h2 style="margin-top:0">Grunndata <span class="mut" style="font-weight:400;font-size:.7em">{c["have"]} av {c["of"]}'
            f'{" (ETF)" if etf else ""}</span></h2><table>{"".join(rows)}</table></div>')


CSS = ".dchip{display:inline-block;margin-left:6px;padding:0 6px;border-radius:9px;background:#21262d;color:var(--mut);border:1px solid #30363d;font-size:.8em;white-space:nowrap;cursor:help}\n"
