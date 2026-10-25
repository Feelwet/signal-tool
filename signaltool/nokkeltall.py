"""Nøkkeltall på tickersiden: bare Yahoo-data vi allerede henter (decision.INFO_KEYS), aldri fylt inn. «–» når et tall mangler.
P/E, EPS og omsetning = faktiske tall siste 12 mnd (trailing), ikke estimater. Utbytte = faktisk utbetalt siste 12 mnd.
Markedsverdi og P/B regnes på siste sluttkurs (aksjer × kurs, kurs / bokført egenkapital per aksje)."""
from __future__ import annotations
import json
from html import escape as E

FIELDS = [("mcap", "Børsverdi"), ("pe", "P/E"), ("rev", "Omsetning"), ("ebit", "EBIT"), ("eps", "EPS"),
          ("dps", "Utbytte per aksje"), ("yld", "Direkteavkastning"), ("pb", "P/B"), ("ps", "P/S"), ("next", "Neste rapport")]
MISSING = "–"
MISSING_INFO = "Tallet mangler hos kilden."
MOBILE_SHOW = 6
SPARK_MIN = 4


def spark_svg(qs) -> str:
    """40×16 px linje over kvartalene (eldst til venstre). Bare ekte kvartalstall, ingen hull (krav: ≥ 4 sammenhengende)."""
    ys = [y for _, y in qs]
    lo, hi = min(ys), max(ys)
    rng = (hi - lo) or 1
    pts = " ".join(f"{1 + i * 38 / (len(ys) - 1):.1f},{1 + (hi - y) * 14 / rng:.1f}" for i, y in enumerate(ys))
    n = len(qs)
    return (f'<span class="spk"><svg width="40" height="16" viewBox="0 0 40 16" aria-hidden="true"><polyline points="{pts}" fill="none" stroke="#8b949e" stroke-width="1.2"/></svg>'
            f'<span class="ri" tabindex="0" aria-expanded="false" aria-label="siste {n} kv.">ⓘ<span class="tip">siste {n} kv.</span></span></span>')
ETF_HIDE = {"eps", "pe", "ebit", "pb", "ps"}


def _f(x):
    try:
        x = float(x)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _n(x: float, dec: int = 2) -> str:
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


def _big(x: float, cur: str) -> str:
    a = abs(x)
    s = (_n(x / 1e12, 2) + " bill." if a >= 1e12 else _n(x / 1e9, 0 if a >= 1e11 else 1) + " mrd." if a >= 1e9 else _n(x / 1e6, 0) + " mill.")
    return f"{s} {cur}".strip()


def compute(e: dict) -> dict:
    from .datacov import is_etf
    d = e.get("decision") or {}
    close = _f(d.get("close")) or _f((e.get("stats") or {}).get("close"))
    cur, fcur = d.get("currency") or "", d.get("financialCurrency") or d.get("currency") or ""
    sh, eps, bv, rev = _f(d.get("sharesOutstanding")), _f(d.get("trailingEps")), _f(d.get("bookValue")), _f(d.get("totalRevenue"))
    mcap = sh * close if sh and close else None
    v = {"mcap": _big(mcap, cur) if mcap else None,
         "rev": _big(rev, fcur) if rev else None,
         "eps": ("Negativ" if eps < 0 else f"{_n(eps)} {fcur}".strip()) if eps is not None else None,
         "pe": ("Negativ" if eps < 0 else _n(close / eps, 1) if eps > 0 else None) if eps is not None and close and fcur == cur else None,
         "pb": _n(close / bv, 1) if bv and bv > 0 and close and fcur == cur else None,
         "ps": _n(mcap / rev, 1) if mcap and rev and rev > 0 and fcur == cur else None}
    ebit = _f(d.get("ebit_ttm"))   # sum av fire siste kvartaler fra Yahoo (decision.ebit_ttm); aldri avledet
    v["ebit"] = ("Negativ" if ebit < 0 else _big(ebit, fcur)) if ebit is not None else None
    nx = d.get("next_earnings")
    v["next"] = (f"{nx[8:10]}.{nx[5:7]}.{nx[:4]}" + ("" if d.get("isEarningsDateEstimate") is False else " (anslått)")) if nx else None
    dps = _f(d.get("trailingAnnualDividendRate"))
    v["dps"] = (f"{_n(dps)} {cur}".strip() if dps else "0") if dps is not None else None
    v["yld"] = (_n(dps / close * 100, 1) + " %" if dps and close else "0 %") if dps is not None and close else None
    spark = {k: d.get(src) for k, src in (("rev", "rev_q"), ("eps", "eps_q")) if len(d.get(src) or []) >= SPARK_MIN}
    etf = is_etf(e)
    return {"ticker": e["ticker"], "etf": etf, "date": d.get("info_date"),
            "fields": [{"key": k, "label": lab, "value": v.get(k), **({"quarters": spark[k]} if k in spark and v.get(k) else {})} for k, lab in FIELDS if not (etf and k in ETF_HIDE)]}


CSS = """.nk{display:grid;grid-template-columns:repeat(4,1fr);column-gap:24px}
.nk .r{display:flex;flex-direction:column;justify-content:center;height:52px;border-bottom:1px solid #30363d;min-width:0}
.nk .l{color:var(--mut);font-size:12px}.nk .v{font-variant-numeric:tabular-nums;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:nowrap}
.nkh{display:flex;align-items:baseline;justify-content:space-between;gap:6px}.nkh h2{white-space:nowrap;flex-shrink:0}.nksrc{font-size:11px;text-align:right;white-space:nowrap;flex-shrink:0}
.spk{display:inline-flex;align-items:center;gap:2px;margin-left:6px;vertical-align:middle}.spk svg{display:block}.spk .ri{font-size:11px}.nkmore{display:none}#nokkeltall h2{font-size:1em;margin:0 0 2px}
@media(max-width:599px){#nokkeltall{padding:6px 10px;margin:0 0 12px}#nokkeltall h2{margin:0;font-size:14px;line-height:20px}
.nk{grid-template-columns:1fr 1fr;column-gap:12px}.nk .r{height:36px;gap:2px}.nk .l{font-size:11px;line-height:12px}.nk .v{font-size:15px;line-height:18px}
.nk .r.mx{display:none}.nkall .nk .r.mx{display:flex}
.nkmore{display:block;height:32px;line-height:32px;padding:0;margin:0;background:none;border:0;color:#58a6ff;font:inherit;font-size:13px;cursor:pointer;text-decoration:underline}}"""


MISS_HTML = (f'– <span class="ri" tabindex="0" aria-expanded="false" aria-label="{MISSING_INFO}">ⓘ<span class="tip">{MISSING_INFO}</span></span>')


def html(n: dict) -> str:
    from .since import _dm
    fs = n["fields"]
    rows = "".join(f'<div class="r{" mx" if i >= MOBILE_SHOW else ""}"><span class="l">{E(f["label"])}</span><span class="v">{E(f["value"]) if f["value"] else MISS_HTML}{spark_svg(f["quarters"]) if f.get("quarters") else ""}</span></div>'
                   for i, f in enumerate(fs))
    per = (len(fs) + 1) // 2
    more = (f'<button type="button" class="nkmore" onclick="this.closest(\'.card\').classList.add(\'nkall\');this.remove()">Vis alle ({len(fs)})</button>'
            if len(fs) > MOBILE_SHOW else "")
    upd = f" · {_dm(n['date'])}" if n.get("date") else ""
    full = f"Kilde: Yahoo Finance · siste 12 mnd. (trailing){' · oppdatert ' + _dm(n['date']) if n.get('date') else ''}"
    return (f'<div class="card nofold" id="nokkeltall"><div class="nkh"><h2>Nøkkeltall</h2><span class="mut nksrc">Yahoo{upd} <span class="ri" tabindex="0" aria-expanded="false" aria-label="{E(full)}">ⓘ<span class="tip">{E(full)}</span></span></span></div><div class="nk">{rows}</div>{more}'
            '<script>document.querySelectorAll("#nokkeltall .ri").forEach(b=>b.addEventListener("click",e=>{e.stopPropagation();b.setAttribute("aria-expanded",b.getAttribute("aria-expanded")==="true"?"false":"true")}))</script></div>')


def write_json(n: dict, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(n, ensure_ascii=False))
