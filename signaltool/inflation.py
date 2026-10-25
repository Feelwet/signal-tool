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
    ("DE", "Tyskland", "#79c0ff", "HICP (Eurostat)", ("ECB", "European Central Bank")),
    ("CN", "Kina", "#f778ba", "KPI (NBS), ikke HICP – via OECD", ()),
]
CN_TARGET = {"label": "regjeringens mål ~2 %", "url": "https://english.www.gov.cn/news/202603/13/content_WS69b4b144c6d00ca5f9a09dfd.html",
             "source": "Government Work Report 2026 (godkjent 12.03.2026): «CPI increase of around 2 percent»"}
MONTHS = 60


def _get(url, **kw):
    r = requests.get(url, headers=UA, timeout=30, **kw)
    r.raise_for_status()
    return r


def eurostat_hicp(geos=("NO", "SE", "DK", "EA", "DE")) -> dict:
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


def cn_cpi_yoy() -> list:
    """Kina KPI 12-mnd endring (NBS-tall) via OECD SDMX (DF_PRICES_ALL, CHN.M.N.CPI.PA._T.N.GY). NBS selv gir 403 fra CI."""
    t = _get("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/CHN.M.N.CPI.PA._T.N.GY",
             params={"startPeriod": "2020-01", "dimensionAtObservation": "AllDimensions", "format": "csvfile"}).text
    rows = list(csv.DictReader(io.StringIO(t)))
    out = sorted([[r["TIME_PERIOD"][:7], float(r["OBS_VALUE"])] for r in rows if r.get("OBS_VALUE") not in (None, "")])
    if not out:
        raise ValueError("ingen observasjoner")
    return out


def imf_weo_cn(today=None) -> dict:
    """IMF WEO PCPIPCH (årssnitt KPI) for Kina fra DataMapper. Utgave: april (apr–sep) eller oktober (okt–mar)."""
    from datetime import date
    today = today or date.today()
    v = _get("https://www.imf.org/external/datamapper/api/v1/PCPIPCH/CHN").json()["values"]["PCPIPCH"]["CHN"]
    y, m = today.year, today.month
    ed, pub = (("apr.", f"{y}-04-14") if 4 <= m < 10 else (("okt.", f"{y}-10-13") if m >= 10 else ("okt.", f"{y - 1}-10-13")))
    pts = [[k, float(x)] for k, x in sorted(v.items()) if int(k) >= today.year and int(k) <= today.year + 3]
    return {"source": "IMF WEO", "edition": f"{ed} {pub[:4]}", "measure": "KPI årssnitt", "kind": "annual", "published": pub,
            "url": "https://www.imf.org/external/datamapper/PCPIPCH@WEO/CHN", "grey": True, "points": pts}


def _prev_card(k):
    from .config import ROOT
    for load in (lambda: json.loads((ROOT / "data" / "snapshots" / "latest.json").read_text()),
                 lambda: requests.get("https://feelwet.github.io/signal-tool/data.json", timeout=30).json()):
        try:
            v = load()["macro"]["inflation"]["cards"][k]
            if v:
                return v
        except Exception:
            pass
    return None


def us_cpi_yoy() -> list:
    s = fred("CPIAUCSL")["CPIAUCSL"]
    by = {d[:7]: v for d, v in s}
    return [[m, round((v / by[f"{int(m[:4]) - 1}{m[4:]}"] - 1) * 100, 1)] for m, v in by.items() if f"{int(m[:4]) - 1}{m[4:]}" in by]


def policy_rates() -> dict:
    out = {}
    out["NO"] = _rate_no()
    try:
        f = fred("DFEDTARU,ECBDFR", "2025-01-01")
        if f.get("DFEDTARU"):
            out["US"] = {"rate": f["DFEDTARU"][-1][1], "date": f["DFEDTARU"][-1][0], "source": "Fed, øvre grense (FRED DFEDTARU)"}
        if f.get("ECBDFR"):
            out["EA"] = {"rate": f["ECBDFR"][-1][1], "date": f["ECBDFR"][-1][0], "source": "ECB innskuddsrente (FRED ECBDFR)"}
    except Exception:
        pass
    if out.get("NO") is None:
        out.pop("NO", None)
    for k, fn in (("SE", _rate_se), ("DK", _rate_dk), ("UK", _rate_uk)):
        try:
            out[k] = fn()
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
    "DE": ("HICP", "Eurostat HICP (prc_hicp_minr)"),
    "CN": ("KPI", "KPI (NBS), ikke HICP – hentet via OECD SDMX (DF_PRICES_ALL)"),
}


def _yoy(pairs):
    by = dict(pairs)
    return [[m, round((v / by[f"{int(m[:4]) - 1}{m[4:]}"] - 1) * 100, 1)] for m, v in pairs if f"{int(m[:4]) - 1}{m[4:]}" in by]


def ssb_kpi_yoy() -> list:
    from .collectors import macro as M
    s = M.ssb("14710", {"ContentsCode": "KpiIndMnd"}, top=90)
    return _yoy([[str(i)[:7], float(v)] for i, v in s.items()])


def scb_kpif() -> list:
    j = _get("https://statistikdatabasen.scb.se/api/v2/tables/TAB6590/data",
             params={"lang": "sv", "valueCodes[ContentsCode]": "000007ZM", "valueCodes[Tid]": "top(72)", "outputFormat": "json-stat2"}).json()
    ti = j["dimension"]["Tid"]["category"]["index"]
    return sorted([[t.replace("M", "-"), float(j["value"][i])] for t, i in ti.items() if j["value"][i] is not None])


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


def _rate_no():
    """Norges Bank styringsrente med retry + UA; faller tilbake til siste gode verdi i forrige snapshot (merket)."""
    import time
    url = "https://data.norges-bank.no/api/data/IR/B.KPRA.SD.?format=csv&lastNObservations=1&locale=en"
    for i in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (signal-tool; github.com/Feelwet/signal-tool)", "Accept": "text/csv"}, timeout=(10, 25))
            r.raise_for_status()
            rows = [x for x in csv.reader(io.StringIO(r.text), delimiter=";") if x]
            head, last = rows[0], rows[-1]
            iv = head.index("OBS_VALUE") if "OBS_VALUE" in head else len(last) - 3
            it = head.index("TIME_PERIOD") if "TIME_PERIOD" in head else len(last) - 4
            return {"rate": float(last[iv]), "date": last[it][:10], "source": "Norges Bank (styringsrente)"}
        except Exception:
            time.sleep(2 * (i + 1))
    from .config import ROOT
    loaders = (lambda: json.loads((ROOT / "data" / "snapshots" / "latest.json").read_text()),
               lambda: requests.get("https://feelwet.github.io/signal-tool/data.json", timeout=30).json())
    for load in loaders:
        try:
            prev = load()["macro"]["inflation"]["rates"]["NO"]
            if prev.get("rate") is not None:
                return {**prev, "source": prev["source"].split(" – ")[0] + " – siste gode verdi (henting feilet)", "stale": True}
        except Exception:
            continue
    return None


def _rate_se():
    j = _get("https://api.riksbank.se/swea/v1/Observations/Latest/SECBREPOEFF").json()
    return {"rate": float(j["value"]), "date": j["date"], "source": "Riksbanken styrränta (SWEA)"}


def _rate_dk():
    r = requests.post("https://api.statbank.dk/v1/data", headers=UA, timeout=30, json={"table": "DNRENTD", "format": "CSV", "variables": [
        {"code": "INSTRUMENT", "values": ["OFONAA"]}, {"code": "LAND", "values": ["DK"]}, {"code": "OPGOER", "values": ["E"]}, {"code": "Tid", "values": ["(-n+1)"]}]})
    r.raise_for_status()
    row = r.text.strip().splitlines()[-1].split(";")
    t = row[-2]
    return {"rate": float(row[-1].replace(",", ".")), "date": f"{t[:4]}-{t[5:7]}-{t[8:10]}", "source": "Nationalbanken, foliorente (Statbank DNRENTD)"}


def _rate_uk():
    from datetime import datetime
    t = requests.get("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2026&Dateto=now&SeriesCodes=IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text.strip().splitlines()[-1].split(",")
    return {"rate": float(t[1]), "date": datetime.strptime(t[0], "%d %b %Y").date().isoformat(), "source": "Bank of England, Bank Rate (IADB IUDBEDR)"}


FC_PATH = __import__("pathlib").Path(__file__).with_name("inflation_forecasts.json")


def load_forecasts() -> dict:
    try:
        return {k: v for k, v in json.loads(FC_PATH.read_text()).items() if not k.startswith("_")}
    except Exception:
        return {}


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
    cn = run("Inflasjon Kina KPI (NBS via OECD)", cn_cpi_yoy)
    stale = set()
    if not cn:
        cn = _prev_card("CN")
        if cn: stale.add("CN")
    if cn:
        series["CN"] = cn; cards["CN"] = cn
    for k in ("DK", "EA", "DE"):
        if k in h: cards[k] = h[k]
    if uk: cards["UK"] = uk
    for k, lab, fn in (("NO", "Inflasjon Norge KPI (SSB)", ssb_kpi_yoy), ("SE", "Inflasjon Sverige KPIF (SCB)", scb_kpif), ("US", "Inflasjon USA PCE (FRED)", us_pce_yoy)):
        r = run(lab, fn)
        if r: cards[k] = r
    fc.update(load_forecasts())
    sep = run("Prognose Fed SEP (FRED PCECTPIMD)", fed_sep)
    if sep: fc["US"] = sep
    imf = run("Prognose Kina (IMF WEO PCPIPCH)", imf_weo_cn)
    if imf: fc["CN"] = imf
    rates = policy_rates()
    if rates.get("EA"):
        rates["DE"] = {**rates["EA"], "source": "ECB-renten (innskuddsrente, FRED ECBDFR) – gjelder Tyskland"}
    return {"series": {k: v[-MONTHS:] for k, v in series.items()}, "cards": {k: v[-MONTHS:] for k, v in cards.items()},
            "forecasts": fc, "rates": rates, "stale": sorted(stale)}, st


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
    return f'{f.get("short_source") or f["source"]} {when}, {f["measure"]}', pub, old


def card_chart(hist, fc, col, today, W=300, H=170, floor=0.0, target=2.0, tlabel=None):
    """Historikk (heltrukket) + prognose (stiplet, trinn per år) i samme mål. Ingen interpolering utover publiserte punkter."""
    L, R, T, B = 28, 6, 8, 18
    last = hist[-1]
    steps = []
    if fc:
        lm = _mi(last[0])
        q3 = fc.get("kind") == "q3"
        steps = [(int(y), v) for y, v in fc["points"] if (int(y) * 12 + 8 if q3 else int(y) * 12 + 11) > lm]
    x0 = _mi(hist[0][0])
    x1 = max(_mi(last[0]), *(y * 12 + 11 for y, _ in steps)) if steps else _mi(last[0])
    tm = today.year * 12 + today.month - 1
    fcol = "#8b949e" if fc and fc.get("grey") else col
    vals = [v for _, v in hist] + [v for _, v in steps] + [floor] + ([target] if target is not None else [])
    lo, hi = min(vals), max(vals)
    X = lambda i: L + (i - x0) / max(1, x1 - x0) * (W - L - R)
    Y = lambda v: T + (hi - v) / ((hi - lo) or 1) * (H - T - B)
    g = []
    if x1 > tm:
        g.append(f'<rect x="{X(tm):.1f}" y="{T}" width="{W - R - X(tm):.1f}" height="{H - T - B}" fill="#6cb6ff" opacity=".07"/>'
                 f'<text x="{W - R - 2}" y="{(H - B - 4) if tlabel else (T + 10)}" text-anchor="end">Prognose</text>')
    for v in range(int(lo // 2 * 2), int(hi) + 2, 2):
        if lo <= v <= hi:
            g.append(f'<text x="{L - 3}" y="{Y(v) + 3:.1f}" text-anchor="end">{v}</text>')
    for yy in range(int(hist[0][0][:4]) + 1, x1 // 12 + 1):
        g.append(f'<text x="{X(yy * 12):.1f}" y="{H - 4}" text-anchor="middle">{str(yy)[2:]}</text>')
    if target is not None:
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(target):.1f}" y2="{Y(target):.1f}" stroke="#8b949e" stroke-dasharray="1 3" stroke-width="1"/>')
        if tlabel:
            g.append(f'<text class="tlabel" x="{W - R - 2}" y="{Y(target) - 6:.1f}" text-anchor="end">{_E(tlabel)}</text>')
    pts = " ".join(f"{X(_mi(m)):.1f},{Y(v):.1f}" for m, v in hist)
    g.append(f'<polyline fill="none" stroke="{col}" stroke-width="1.8" points="{pts}"/>')
    if steps:
        lx, ly = X(_mi(last[0])), Y(last[1])
        d = f"M{lx:.1f},{ly:.1f}"
        for y, v in steps:
            if q3:   # publiserte kvartalspunkter (Q3), ikke årssnitt: punkt-til-punkt
                d += f" L{X(y * 12 + 7):.1f},{Y(v):.1f}"
            else:
                xa, xb = X(max(y * 12, _mi(last[0]))), X(y * 12 + 11)
                d += f" L{xa:.1f},{Y(v):.1f} L{xb:.1f},{Y(v):.1f}"
        g.append(f'<path d="{d}" fill="none" stroke="{fcol}" stroke-width="1.8" stroke-dasharray="5 4"/>')
        g += [f'<circle cx="{X(y * 12 + (7 if q3 else 6)):.1f}" cy="{Y(v):.1f}" r="3" fill="{fcol}"><title>{y}: {_nf(v)} %</title></circle>' for y, v in steps]
    return (f'<svg class="cchart" viewBox="0 0 {W} {H}" width="100%" height="{H}" role="img" aria-label="Inflasjon og prognose">{"".join(g)}</svg>')


def _spark(vals, w=120, h=32):
    return ""


CSS = """<style>
.infl-chart{display:block}@media(max-width:699px){.infl-chart{display:none}}
.infl-leg{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}.infl-leg button{min-height:32px;padding:3px 10px;border:1px solid #778;border-radius:3px;background:transparent;color:inherit;font:inherit;cursor:pointer}
.infl-leg button[aria-pressed=false]{opacity:.45;text-decoration:line-through}.infl-leg i{display:inline-block;width:12px;height:3px;vertical-align:middle;margin-right:6px}
.infl-svg{width:100%;height:auto}.infl-svg .hit{pointer-events:stroke;cursor:pointer}.infl-svg .htip{fill:#e6edf3!important;font-size:12px!important;pointer-events:none;paint-order:stroke;stroke:#0d1117;stroke-width:3px}.infl-svg text,.cchart text{fill:#9ea9b5;font-size:11px}
.infl-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-top:12px}
.infl-card{border:1px solid #30363d;border-radius:6px;padding:10px 12px}.infl-card .big{font-size:1.5em;font-weight:600;color:#e6edf3}
.cchart{display:block;min-height:160px;margin:6px 0}.fcl{font-size:.8em}
</style>"""
JS = """<script>(()=>{const B=c=>document.querySelector('.infl-leg button[data-c="'+c+'"]');
function tog(c){const b=B(c);if(!b)return;const on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',on);
document.querySelectorAll('.infl-svg [data-c="'+c+'"]').forEach(e=>e.style.display=on?'':'none');if(!on)tip('')}
document.querySelectorAll('.infl-leg button').forEach(b=>b.onclick=()=>tog(b.dataset.c));
const svg=document.querySelector('.infl-svg');if(!svg)return;const NS='http://www.w3.org/2000/svg';
const t=document.createElementNS(NS,'text');t.setAttribute('class','htip');svg.appendChild(t);
function tip(s,x,y){t.textContent=s;if(s){t.setAttribute('x',Math.min(x+8,svg.viewBox.baseVal.width-150));t.setAttribute('y',Math.max(y-8,12))}}
const P=e=>{const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(svg.getScreenCTM().inverse())};
function near(e){const p=P(e),k=svg.getScreenCTM().a||1;let best=null,bd=1e9;
svg.querySelectorAll('.hit').forEach(h=>{if(h.style.display==='none')return;const q=h.points;for(let i=1;i<q.length;i++){const a=q[i-1],b=q[i],dx=b.x-a.x,dy=b.y-a.y,L=dx*dx+dy*dy||1;
let u=((p.x-a.x)*dx+(p.y-a.y)*dy)/L;u=Math.max(0,Math.min(1,u));const d=Math.hypot(p.x-a.x-u*dx,p.y-a.y-u*dy);if(d<bd){bd=d;best=h}}});
return bd*k<=24?best:null}
svg.addEventListener('click',e=>{const h=near(e);if(h)tog(h.dataset.c)});
svg.querySelectorAll('.hit').forEach(h=>{const ln=svg.querySelector('.ln[data-c="'+h.dataset.c+'"]');
h.addEventListener('mouseenter',()=>ln.setAttribute('stroke-width','3.5'));
h.addEventListener('mousemove',e=>{const p=P(e);tip(h.dataset.l,p.x,p.y)});
h.addEventListener('mouseleave',()=>{ln.setAttribute('stroke-width','2');tip('')})})})()</script>"""


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
            lines.append(f'<polyline class="ln" data-c="{k}" fill="none" stroke="{col}" stroke-width="2" points="{pts}"><title>{_E(name)}: {_E(note)}</title></polyline>')
            lines.append(f'<polyline class="hit" data-c="{k}" data-l="{_E(name)} {_nf(v[-1][1])} % ({_E(v[-1][0])})" fill="none" stroke="transparent" stroke-width="14" points="{pts}"/>')
            leg.append(f'<button data-c="{k}" aria-pressed="true"><i style="background:{col}"></i>{_E(name + (" – KPI (NBS), ikke HICP" if k == "CN" else ""))}</button>')
        meas, msrc = CARD_MEASURE[k]
        hist = C.get(k) or []
        last = hist[-1] if hist else None
        stale = (last and (today.year * 12 + today.month - 1) - _mi(last[0]) > 3) or k in (inf.get("stale") or [])
        hicp = S.get(k, [])[-1] if S.get(k) else None
        sub = (f'<div class="src">{"KPI-U" if k == "US" else ("ONS CPI" if k == "UK" else "HICP")} {_nf(hicp[1])} % ({_E(hicp[0])}) – samme som i felles graf</div>'
               if hicp and meas != "HICP" and k not in ("UK", "CN") else "")
        f = F.get(k)
        if f:
            lab, pub, old = _fc_label(f, today)
            src = f' · <a href="{_E(f["url"])}" target="_blank" rel="noopener">kilde</a>' if f.get("url") else ""
            fcl = (f'<div class="fcl" style="color:{"#9ea9b5" if f.get("grey") else col}" title="Publisert {_E(pub or "ukjent")}">- - Prognose: {_E(lab)}{", ikke sentralbank" if f.get("grey") else ""}{src}'
                   f'{" · <b>⏱ Utdatert</b>" if old else ""}</div>')
        else:
            fcl = '<div class="fcl mut">Ingen prognose</div>'
        rt = R.get(k)
        tgt = (f'<div class="src">Mål: <a href="{_E(CN_TARGET["url"])}" target="_blank" rel="noopener">{_E(CN_TARGET["label"])}</a> – {_E(CN_TARGET["source"])}</div>' if k == "CN" else "")
        nm = _next_meeting(cal, cb)
        cards.append(f'<div class="infl-card"><b>{_E(name)}</b>'
                     f'<div class="big">{_E(meas)} {"–" if not last else _nf(last[1]) + " %"}</div>'
                     f'<div class="src">{_E(msrc)}{f" · {_E(last[0])}" if last else " · Mangler data"}{" · <b>⏱ Utdatert</b>" if stale else ""}</div>{sub}'
                     f'{(card_chart(hist, f, col, today, floor=-2.0, target=2.0, tlabel=CN_TARGET["label"]) if k == "CN" else card_chart(hist, f, col, today)) if len(hist) > 1 else ""}{fcl}'
                     f'{tgt}'
                     f'<p style="margin:6px 0 0">Styringsrente: {f"<b>{_nf(rt["rate"], 2)} %</b> <span class=src>{_E(rt["source"])}, {_E(rt["date"])}</span>" if rt else ("<span class=mut>ingen fri kilde</span>" if k == "CN" else "<span class=mut>ikke hentet</span>")}<br>'
                     f'Neste møte: {"<span class=mut>LPR settes den 20. hver måned</span>" if k == "CN" else ""}{"" if k == "CN" else f"{_E(nm["date"])} {_E(nm.get("time") or "")}" + (" (estimert)" if "estimert" in nm.get("source", "").lower() else "") if nm else "<span class=mut>ikke i kalenderen (45 dager frem)</span>"}</p></div>'.replace("Neste møte: <span class=mut>LPR settes den 20. hver måned</span><span class=mut>ikke i kalenderen (45 dager frem)</span>", "Neste møte: <span class=mut>LPR settes den 20. hver måned</span>"))
    two = f'<line x1="{L}" x2="{W-8}" y1="{Y(2):.1f}" y2="{Y(2):.1f}" stroke="#8b949e" stroke-dasharray="1 3" stroke-width="1"/><text x="{W-10}" y="{Y(2)-4:.1f}" text-anchor="end">2 % mål</text>'
    svg = (f'<svg class="infl-svg" viewBox="0 0 {W} {H}" role="img" aria-label="Inflasjon siste 5 år, årlig prosent, per land">{grid}{years}{two}{"".join(lines)}</svg>')
    return (f'{CSS}<div class="card" id="inflasjon"><h2 style="margin-top:0">Inflasjon siste 5 år (årlig %, faktiske tall)</h2>'
            f'<div class="infl-chart"><div class="infl-leg" role="group" aria-label="Vis/skjul land">{"".join(leg)}</div>{svg}'
            f'<p class="src">Felles graf: Eurostat HICP (prc_hicp_minr) for Norge, Sverige, Danmark, eurosonen og Tyskland – sammenlignbare. Kina: KPI (NBS), ikke HICP, hentet via OECD SDMX. '
            f'UK: ONS KPI (D7G7); Eurostat HICP for UK stopper nov. 2020 (seriebrudd). USA: KPI-U, ikke HICP (FRED CPIAUCSL, årlig endring). Ingen prognoser i denne grafen.</p></div>'
            f'<h3>Per land – målet sentralbanken bruker, med offisiell prognose der den finnes</h3>'
            f'<p class="src">Prognoser er årssnitt og vises som trinn per år (stiplet). Offisielle prognoser fra sentralbanker, eller fra IMF der sentralbanken ikke publiserer noen (grå stiplet); ingen egne anslag. '
            f'Forventninger fra markeder/spørreundersøkelser: Ingen fri kilde.</p>'
            f'<div class="infl-cards">{"".join(cards)}</div></div>{JS}')


if __name__ == "__main__":
    d, st = collect()
    print(st, {k: (len(v), v[-1]) for k, v in d["series"].items()}, d["rates"])
