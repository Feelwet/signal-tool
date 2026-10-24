"""Inflasjon 5 år (sammenlignbar HICP) + styringsrente + neste møte, til makrosiden.

NO/SE/DK/EA: Eurostat HICP årlig % (prc_hicp_minr, coicop18=TOTAL, RCH_A).
UK: Eurostat HICP slutter nov. 2020 -> ONS CPI årlig % (D7G7) etter det (seriebrudd, merkes).
USA: FRED CPIAUCSL, årlig endring (KPI-U, ikke HICP).
Styringsrente: Norges Bank (KPRA), FRED DFEDTARU (Fed, øvre grense), FRED ECBDFR (ECB innskuddsrente). Øvrige: ikke hentet.
"""
from __future__ import annotations
import csv
import html
import io
import json
import requests

UA = {"User-Agent": "signal-tool (github.com/Feelwet/signal-tool)"}
COUNTRIES = [  # key, navn, farge, serienotat, sentralbank-navn i kalenderen
    ("NO", "Norge", "#6cb6ff", "HICP (Eurostat)", ("Norges Bank",)),
    ("SE", "Sverige", "#e3b341", "HICP (Eurostat)", ("Riksbank",)),
    ("DK", "Danmark", "#ff7b72", "HICP (Eurostat)", ("Nationalbank",)),
    ("EA", "Eurosonen", "#3fb950", "HICP (Eurostat)", ("ECB", "European Central Bank")),
    ("UK", "Storbritannia", "#d2a8ff", "ONS KPI (D7G7) – Eurostat HICP stopper nov. 2020, seriebrudd", ("Bank of England",)),
    ("US", "USA", "#f0883e", "KPI-U, ikke HICP (FRED CPIAUCSL, årlig endring)", ("Federal Reserve", "FOMC")),
]
MONTHS = 60


def _get(url, **kw):
    r = requests.get(url, headers=UA, timeout=30, **kw)
    r.raise_for_status()
    return r


def eurostat_hicp(geos=("NO", "SE", "DK", "EA")) -> dict:
    q = [("format", "JSON"), ("coicop18", "TOTAL"), ("unit", "RCH_A"), ("sinceTimePeriod", "2020-01")] + [("geo", g) for g in geos]
    d = _get("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr", params=q).json()
    gi, ti = d["dimension"]["geo"]["category"]["index"], d["dimension"]["time"]["category"]["index"]
    T, out = len(ti), {}
    for g, i in gi.items():
        out[g] = [[t, float(d["value"][str(i * T + j)])] for t, j in sorted(ti.items(), key=lambda x: x[1]) if str(i * T + j) in d["value"]]
    return out


def ons_uk() -> list:
    txt = _get("https://www.ons.gov.uk/generator?format=csv&uri=/economy/inflationandpriceindices/timeseries/d7g7/mm23").text
    mm = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
    out = []
    for row in csv.reader(io.StringIO(txt)):
        if len(row) == 2 and len(row[0].split()) == 2 and row[0].split()[1] in mm:
            y, m = row[0].split()
            out.append([f"{y}-{mm[m]:02d}", float(row[1])])
    return sorted(out)


def fred(ids: str, start="2019-01-01") -> dict:
    rows = list(csv.reader(io.StringIO(_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={ids}&cosd={start}").text)))
    head, out = rows[0], {k: [] for k in rows[0][1:]}
    for r in rows[1:]:
        for k, v in zip(head[1:], r[1:]):
            if v not in ("", "."):
                out[k].append([r[0][:10], float(v)])
    return out


def us_cpi_yoy() -> list:
    s = fred("CPIAUCSL")["CPIAUCSL"]
    by = {d[:7]: v for d, v in s}
    return [[m, round((v / by[f"{int(m[:4]) - 1}{m[4:]}"] - 1) * 100, 1)] for m, v in by.items() if f"{int(m[:4]) - 1}{m[4:]}" in by]


def policy_rates() -> dict:
    out = {}
    try:
        r = list(csv.reader(io.StringIO(_get("https://data.norges-bank.no/api/data/IR/B.KPRA.SD.?format=csv&lastNObservations=1&locale=en").text), delimiter=";"))
        out["NO"] = {"rate": float(r[-1][-3]), "date": r[-1][-4], "source": "Norges Bank (styringsrente)"}
    except Exception:
        pass
    try:
        f = fred("DFEDTARU,ECBDFR", "2025-01-01")
        if f.get("DFEDTARU"):
            out["US"] = {"rate": f["DFEDTARU"][-1][1], "date": f["DFEDTARU"][-1][0], "source": "Fed, øvre grense (FRED DFEDTARU)"}
        if f.get("ECBDFR"):
            out["EA"] = {"rate": f["ECBDFR"][-1][1], "date": f["ECBDFR"][-1][0], "source": "ECB innskuddsrente (FRED ECBDFR)"}
    except Exception:
        pass
    return out


CARD_MEASURE = {  # mål sentralbanken bruker (kortgraf): (kort navn, kilde)
    "NO": ("KPI", "SSB KPI (tabell 14710), 12-mnd endring"),
    "SE": ("KPIF", "SCB KPIF, 12-mnd endring"),
    "DK": ("HICP", "Eurostat HICP"),
    "EA": ("HICP", "Eurostat HICP"),
    "UK": ("CPI", "ONS CPI (D7G7)"),
    "US": ("PCE", "FRED PCEPI, årlig endring"),
}


def _yoy(pairs):
    by = dict(pairs)
    return [[m, round((v / by[f"{int(m[:4]) - 1}{m[4:]}"] - 1) * 100, 1)] for m, v in pairs if f"{int(m[:4]) - 1}{m[4:]}" in by]


def ssb_kpi_yoy() -> list:
    from .collectors import macro as M
    s = M.ssb("14710", {"ContentsCode": "KpiIndMnd"}, top=90)
    return _yoy([[str(i)[:7], float(v)] for i, v in s.items()])


def scb_kpif() -> list:
    q = {"query": [{"code": "ContentsCode", "selection": {"filter": "item", "values": ["PR0101F1"]}},
                   {"code": "Tid", "selection": {"filter": "top", "values": ["72"]}}], "response": {"format": "json"}}
    d = requests.post("https://api.scb.se/OV0104/v1/doris/sv/ssd/PR/PR0101/PR0101G/KPIF", json=q, headers=UA, timeout=30).json()
    return sorted([[r["key"][0].replace("M", "-"), float(r["values"][0])] for r in d["data"] if r["values"][0] not in ("..", "")])


def us_pce_yoy() -> list:
    return _yoy([[d[:7], v] for d, v in fred("PCEPI")["PCEPI"]])


def fed_sep() -> dict:
    """Fed SEP median PCE (årssnitt Q4/Q4) fra FRED PCECTPIMD; publiseringsdato fra seriesiden."""
    import re
    pts = [[d[:4], v] for d, v in fred("PCECTPIMD", "2024-01-01")["PCECTPIMD"]]
    pub = None
    try:
        t = re.sub(r"<[^>]+>", " ", _get("https://fred.stlouisfed.org/series/PCECTPIMD").text)
        m = re.search(r"Updated:\s+([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", t)
        if m:
            from datetime import datetime
            pub = datetime.strptime(" ".join(m.groups()), "%b %d %Y").date().isoformat()
    except Exception:
        pass
    return {"points": pts, "measure": "PCE", "source": "Fed SEP (median)", "published": pub,
            "url": "https://fred.stlouisfed.org/series/PCECTPIMD"}


def collect() -> tuple[dict, dict]:
    series, cards, fc, st = {}, {}, {}, {}
    def run(lab, fn):
        try:
            r = fn(); st[lab] = "ok"; return r
        except Exception as ex:
            st[lab] = f"FAILED: {str(ex)[:80]}"; return None
    h = run("Inflasjon HICP (Eurostat)", eurostat_hicp) or {}
    series.update(h)
    uk = run("Inflasjon UK (ONS D7G7)", ons_uk)
    if uk: series["UK"] = uk
    us = run("Inflasjon USA KPI-U (FRED CPIAUCSL)", us_cpi_yoy)
    if us: series["US"] = us
    for k in ("DK", "EA"):
        if k in h: cards[k] = h[k]
    if uk: cards["UK"] = uk
    for k, lab, fn in (("NO", "Inflasjon Norge KPI (SSB)", ssb_kpi_yoy), ("SE", "Inflasjon Sverige KPIF (SCB)", scb_kpif), ("US", "Inflasjon USA PCE (FRED)", us_pce_yoy)):
        r = run(lab, fn)
        if r: cards[k] = r
    sep = run("Prognose Fed SEP (FRED PCECTPIMD)", fed_sep)
    if sep: fc["US"] = sep
    return {"series": {k: v[-MONTHS:] for k, v in series.items()}, "cards": {k: v[-MONTHS:] for k, v in cards.items()},
            "forecasts": fc, "rates": policy_rates()}, st


# ---------------- html ----------------
def _E(x):
    return html.escape("" if x is None else str(x))


def _next_meeting(cal, names):
    ev = sorted((e for e in cal or [] if (e.get("kind") == "sentralbank") and any(n.lower() in (e.get("source", "") + " " + e.get("title", "")).lower() for n in names)), key=lambda e: e.get("date", ""))
    return ev[0] if ev else None


MN = ["jan", "feb", "mars", "april", "mai", "juni", "juli", "aug", "sept", "okt", "nov", "des"]


def _nf(v, d=1):
    return f"{v:.{d}f}".replace(".", ",")


def _mi(m):  # "YYYY-MM" -> månedsindeks
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def _fc_label(f, today):
    from datetime import date
    pub = f.get("published")
    when = f"{MN[int(pub[5:7]) - 1]} {pub[:4]}" if pub else "dato ukjent"
    old = (not pub) or (today - date.fromisoformat(pub)).days > 183
    return f'{f["source"]} {when}, {f["measure"]}', pub, old


def card_chart(hist, fc, col, today, W=300, H=170):
    """Historikk (heltrukket) + prognose (stiplet, trinn per år) i samme mål. Ingen interpolering utover publiserte punkter."""
    L, R, T, B = 28, 6, 8, 18
    last = hist[-1]
    steps = []
    if fc:
        lm = _mi(last[0])
        steps = [(int(y), v) for y, v in fc["points"] if int(y) * 12 + 11 > lm]
    x0 = _mi(hist[0][0])
    x1 = max(_mi(last[0]), *(y * 12 + 11 for y, _ in steps)) if steps else _mi(last[0])
    tm = today.year * 12 + today.month - 1
    vals = [v for _, v in hist] + [v for _, v in steps] + [2.0, 0.0]
    lo, hi = min(vals), max(vals)
    X = lambda i: L + (i - x0) / max(1, x1 - x0) * (W - L - R)
    Y = lambda v: T + (hi - v) / ((hi - lo) or 1) * (H - T - B)
    g = []
    if x1 > tm:
        g.append(f'<rect x="{X(tm):.1f}" y="{T}" width="{W - R - X(tm):.1f}" height="{H - T - B}" fill="#6cb6ff" opacity=".07"/>'
                 f'<text x="{W - R - 2}" y="{T + 10}" text-anchor="end">Prognose</text>')
    for v in range(int(lo // 2 * 2), int(hi) + 2, 2):
        if lo <= v <= hi:
            g.append(f'<text x="{L - 3}" y="{Y(v) + 3:.1f}" text-anchor="end">{v}</text>')
    for yy in range(int(hist[0][0][:4]) + 1, x1 // 12 + 1):
        g.append(f'<text x="{X(yy * 12):.1f}" y="{H - 4}" text-anchor="middle">{str(yy)[2:]}</text>')
    g.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(2):.1f}" y2="{Y(2):.1f}" stroke="#8b949e" stroke-dasharray="1 3" stroke-width="1"/>')
    pts = " ".join(f"{X(_mi(m)):.1f},{Y(v):.1f}" for m, v in hist)
    g.append(f'<polyline fill="none" stroke="{col}" stroke-width="1.8" points="{pts}"/>')
    if steps:
        lx, ly = X(_mi(last[0])), Y(last[1])
        d = f"M{lx:.1f},{ly:.1f}"
        for y, v in steps:
            xa, xb = X(max(y * 12, _mi(last[0]))), X(y * 12 + 11)
            d += f" L{xa:.1f},{Y(v):.1f} L{xb:.1f},{Y(v):.1f}"
        g.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.8" stroke-dasharray="5 4"/>')
        g += [f'<circle cx="{X(y * 12 + 6):.1f}" cy="{Y(v):.1f}" r="3" fill="{col}"><title>{y}: {_nf(v)} %</title></circle>' for y, v in steps]
    return (f'<svg class="cchart" viewBox="0 0 {W} {H}" width="100%" height="{H}" role="img" aria-label="Inflasjon og prognose">{"".join(g)}</svg>')


def _spark(vals, w=120, h=32):
    return ""


CSS = """<style>
.infl-chart{display:block}@media(max-width:699px){.infl-chart{display:none}}
.infl-leg{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}.infl-leg button{min-height:32px;padding:3px 10px;border:1px solid #778;border-radius:3px;background:transparent;color:inherit;font:inherit;cursor:pointer}
.infl-leg button[aria-pressed=false]{opacity:.45;text-decoration:line-through}.infl-leg i{display:inline-block;width:12px;height:3px;vertical-align:middle;margin-right:6px}
.infl-svg{width:100%;height:auto}.infl-svg text,.cchart text{fill:#9ea9b5;font-size:11px}
.infl-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-top:12px}
.infl-card{border:1px solid #30363d;border-radius:6px;padding:10px 12px}.infl-card .big{font-size:1.5em;font-weight:600}
.cchart{display:block;min-height:160px;margin:6px 0}.fcl{font-size:.8em}
</style>"""
JS = """<script>document.querySelectorAll('.infl-leg button').forEach(b=>b.onclick=()=>{const on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',on);
document.querySelectorAll('.infl-svg [data-c="'+b.dataset.c+'"]').forEach(e=>e.style.display=on?'':'none')})</script>"""


def html_block(inf: dict | None, cal: list | None, today=None) -> str:
    from datetime import date
    today = today or date.today()
    inf = inf or {}
    S, R = inf.get("series") or {}, inf.get("rates") or {}
    C, F = inf.get("cards") or {}, inf.get("forecasts") or {}
    if not S and not C:
        return '<div class="card"><h2 style="margin-top:0">Inflasjon</h2><p class="mut">Mangler data (inflasjonsseriene ble ikke hentet i denne kjøringen).</p></div>'
    months = sorted({m for v in S.values() for m, _ in v})[-MONTHS:]
    allv = [x for v in S.values() for m, x in v if m in months] + [2.0, 0.0]
    lo, hi = min(allv), max(allv)
    W, H, L, B, T = 760, 300, 34, 22, 8
    X = lambda i: L + i * (W - L - 8) / max(1, len(months) - 1)
    Y = lambda v: T + (hi - v) / ((hi - lo) or 1) * (H - T - B)
    grid = "".join(f'<line x1="{L}" x2="{W-8}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#30363d"/><text x="{L-4}" y="{Y(v)+4:.1f}" text-anchor="end">{v:g}</text>'
                   for v in range(int(lo // 2 * 2), int(hi) + 2, 2) if lo <= v <= hi)
    years = "".join(f'<text x="{X(i):.1f}" y="{H-6}" text-anchor="middle">{m[:4]}</text>' for i, m in enumerate(months) if m.endswith("-01"))
    idx = {m: i for i, m in enumerate(months)}
    lines, leg, cards = [], [], []
    for k, name, col, note, cb in COUNTRIES:
        v = [(m, x) for m, x in S.get(k, []) if m in idx]
        if v:
            pts = " ".join(f"{X(idx[m]):.1f},{Y(x):.1f}" for m, x in v)
            lines.append(f'<polyline data-c="{k}" fill="none" stroke="{col}" stroke-width="2" points="{pts}"><title>{_E(name)}: {_E(note)}</title></polyline>')
            leg.append(f'<button data-c="{k}" aria-pressed="true"><i style="background:{col}"></i>{_E(name)}</button>')
        meas, msrc = CARD_MEASURE[k]
        hist = C.get(k) or []
        last = hist[-1] if hist else None
        stale = last and (today.year * 12 + today.month - 1) - _mi(last[0]) > 3
        hicp = S.get(k, [])[-1] if S.get(k) else None
        sub = (f'<div class="src">{"KPI-U" if k == "US" else ("ONS CPI" if k == "UK" else "HICP")} {_nf(hicp[1])} % ({_E(hicp[0])}) – samme som i felles graf</div>'
               if hicp and meas != "HICP" and k != "UK" else "")
        f = F.get(k)
        if f:
            lab, pub, old = _fc_label(f, today)
            fcl = (f'<div class="fcl" style="color:{col}" title="Publisert {_E(pub or "ukjent")}">- - Prognose: {_E(lab)}'
                   f'{" · <b>⏱ Utdatert</b>" if old else ""}</div>')
        else:
            fcl = '<div class="fcl mut">Ingen prognose</div>'
        rt = R.get(k)
        nm = _next_meeting(cal, cb)
        cards.append(f'<div class="infl-card"><b>{_E(name)}</b>'
                     f'<div class="big" style="color:{col}">{_E(meas)} {"–" if not last else _nf(last[1]) + " %"}</div>'
                     f'<div class="src">{_E(msrc)}{f" · {_E(last[0])}" if last else " · Mangler data"}{" · <b>⏱ Utdatert</b>" if stale else ""}</div>{sub}'
                     f'{card_chart(hist, f, col, today) if len(hist) > 1 else ""}{fcl}'
                     f'<p style="margin:6px 0 0">Styringsrente: {f"<b>{_nf(rt["rate"], 2)} %</b> <span class=src>{_E(rt["source"])}, {_E(rt["date"])}</span>" if rt else "<span class=mut>ikke hentet</span>"}<br>'
                     f'Neste møte: {f"{_E(nm["date"])} {_E(nm.get("time") or "")}" + (" (estimert)" if "estimert" in nm.get("source", "").lower() else "") if nm else "<span class=mut>ikke i kalenderen (45 dager frem)</span>"}</p></div>')
    two = f'<line x1="{L}" x2="{W-8}" y1="{Y(2):.1f}" y2="{Y(2):.1f}" stroke="#8b949e" stroke-dasharray="1 3" stroke-width="1"/><text x="{W-10}" y="{Y(2)-4:.1f}" text-anchor="end">2 % mål</text>'
    svg = (f'<svg class="infl-svg" viewBox="0 0 {W} {H}" role="img" aria-label="Inflasjon siste 5 år, årlig prosent, per land">{grid}{years}{two}{"".join(lines)}</svg>')
    return (f'{CSS}<div class="card" id="inflasjon"><h2 style="margin-top:0">Inflasjon siste 5 år (årlig %, faktiske tall)</h2>'
            f'<div class="infl-chart"><div class="infl-leg" role="group" aria-label="Vis/skjul land">{"".join(leg)}</div>{svg}'
            f'<p class="src">Felles graf: Eurostat HICP (prc_hicp_minr) for Norge, Sverige, Danmark og eurosonen – sammenlignbare. '
            f'UK: ONS KPI (D7G7); Eurostat HICP for UK stopper nov. 2020 (seriebrudd). USA: KPI-U, ikke HICP (FRED CPIAUCSL, årlig endring). Ingen prognoser i denne grafen.</p></div>'
            f'<h3>Per land – målet sentralbanken bruker, med offisiell prognose der den finnes</h3>'
            f'<p class="src">Prognoser er årssnitt og vises som trinn per år (stiplet). Vi viser bare publiserte sentralbankprognoser; ingen egne anslag. '
            f'Forventninger fra markeder/spørreundersøkelser: Ingen fri kilde.</p>'
            f'<div class="infl-cards">{"".join(cards)}</div></div>{JS}')


if __name__ == "__main__":
    d, st = collect()
    print(st, {k: (len(v), v[-1]) for k, v in d["series"].items()}, d["rates"])
