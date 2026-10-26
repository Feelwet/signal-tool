"""GS-indeksen (AnalBots spek, 26.10.2026): likevektet indeks over lista slik den faktisk så ut hver dag (point-in-time).

Metode
- Medlemmer: rader i logs/categories.csv med kategori kjop/hold/watch (den rangerte lista; «tema» er temakart-tickere utenfor
  lista). NB: loggen skiller ikke «Ikke rangert» fra rangerte rader; de få ikke-rangerte radene telles derfor med.
- logs/categories_corrections.csv brukes (exclude-rader tas ut, korrigerte priser brukes). categories.csv endres aldri.
- Logg-dato L = lista kjent den dagen. Inngang/utgang skjer på sluttkurs første handelsdag ETTER L (holdingene som gjelder fra
  sluttkurs dag t er lista fra siste logg-dato < t).
- Likevekt, daglig rebalansering. Kostnad per handel = |vektendring| × 0,2 % (0,5 % lite omsatt, flagget «illiquid» i loggen),
  samme satser som Signal-boka (portfolio_rules.py). Kostnad for handler på sluttkurs t trekkes i raden for t
  (unntak: første rad er 100 før handel; inngangskostnaden trekkes i rad 2).
- Kurs: loggførte sluttkurser (korrigert) når begge dager i et dagspar finnes i loggen, ellers Yahoo-sluttkurser (auto_adjust)
  for begge dager. Aldri oppfunnet: mangler kurs for t eller t-1 (og børsen var åpen), droppes aksjen den dagen (n_no_price).
  Stengt egen børs den dagen (indeksen har ingen kurs) = 0 % avkastning, ikke «uten kurs».
- Referanse: OSEBX / Nasdaq Composite / NYSE Composite vektet etter lista sin børsfordeling den dagen (samme mapping som
  since.bench_for: Oslo -> OSEBX.OL, Nasdaq -> ^IXIC, NYSE/Arca/American -> ^NYA). Ingen kostnader.
- gs_ex_tech: samme beregning uten TECH.OL (bare internt, aldri på siden).
- Start: 100 på første handelsdag etter første logg-dato (27.09.2026).
"""
from __future__ import annotations

import csv
import json
import logging
from html import escape as E
from pathlib import Path

from .config import LOGS
from .portfolio_rules import RULES

log = logging.getLogger(__name__)
CAT_LOG = LOGS / "categories.csv"
CORR = LOGS / "categories_corrections.csv"
OUT = LOGS / "gs_index.csv"
LIST_CATS = {"kjop", "hold", "watch"}
START = "2026-09-27"
MIN_DAYS_PUBLIC = 60
FLAG_TEXT = "FLAG: kort periode, ikke skilt fra tilfeldig"
COLS = ["date", "gs_index", "benchmark", "n_members", "n_no_price", "gs_ex_tech"]
IDX = {"oslo": "OSEBX.OL", "nasdaq": "^IXIC", "nyse": "^NYA"}


def _f(x):
    try:
        v = float(x)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def load_rows(cat_path: Path = CAT_LOG, corr_path: Path = CORR) -> list[dict]:
    with open(cat_path, newline="") as f:
        rows = [dict(r) for r in csv.DictReader(f) if r.get("date") and r.get("ticker")]
    if corr_path and Path(corr_path).exists():
        with open(corr_path, newline="") as f:
            corr = list(csv.DictReader(f))
        excl = {(c["date"], c["ticker"]) for c in corr if c.get("field") == "exclude"}
        fix = {(c["date"], c["ticker"], c["field"]): c["new"] for c in corr if c.get("field") in ("price", "price_date")}
        out = []
        for r in rows:
            k = (r["date"], r["ticker"])
            if k in excl:
                continue
            for fld in ("price", "price_date"):
                if (r["date"], r["ticker"], fld) in fix:
                    r[fld] = fix[(r["date"], r["ticker"], fld)]
                    r["_corrected"] = True
            out.append(r)
        rows = out
    return rows


def lists_by_date(rows: list[dict], start: str = START) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        if r["date"] >= start and r.get("category") in LIST_CATS:
            out.setdefault(r["date"], {})[r["ticker"]] = r
    return out


def logged_prices(rows: list[dict]) -> dict[str, dict[str, tuple]]:
    """{ticker: {price_date: (kurs, korrigert)}}. Et dagspar med én korrigert og én ukorrigert kurs kan ligge på ulik
    justeringsbasis (TECH.OL, faktor ~2,14) og brukes ikke; da tas Yahoo-paret."""
    p: dict[str, dict[str, tuple]] = {}
    for r in rows:
        v, d = _f(r.get("price")), r.get("price_date")
        if v and d:
            p.setdefault(r["ticker"], {})[d] = (v, bool(r.get("_corrected")))
    return p


def compute(lists: dict[str, dict[str, dict]], days: list[str], logp: dict, yfp: dict, exch: dict, idx: dict,
            exclude: frozenset = frozenset()) -> list[dict]:
    """lists: {logdato: {ticker: rad}}, days: handelsdager (stigende), logp/yfp: {ticker: {dato: kurs}},
    exch: {ticker: 'oslo'|'nasdaq'|'nyse'|None}, idx: {indeksticker: {dato: kurs}}. Returnerer rader fra første handelsdag > første logg-dato."""
    ldates = sorted(lists)
    if not ldates:
        return []
    days = [d for d in days if d > ldates[0]]

    def members(t):
        prev = [d for d in ldates if d < t]
        if not prev:
            return {}
        return {k: v for k, v in lists[prev[-1]].items() if k not in exclude}

    def ex_open(tk, d):
        e = exch.get(tk)
        ser = idx.get(IDX[e]) if e else None
        return True if not ser else d in ser

    def ret(tk, a, b):
        lp = logp.get(tk, {})
        if a in lp and b in lp and lp[a][1] == lp[b][1]:
            return lp[b][0] / lp[a][0] - 1
        yp = yfp.get(tk, {})
        if a in yp and b in yp:
            return yp[b] / yp[a] - 1
        return None

    def last_close(series, d):
        ks = [k for k in series if k <= d]
        return series[max(ks)] if ks else None

    out, gs, bm, w, prev, carry, seen = [], 100.0, 100.0, {}, None, 0.0, {}
    for t in days:
        n_no = 0
        if prev is not None and w:
            # avkastning prev -> t for holdingene w
            gr, kept, drift, ret_ok = 0.0, 0.0, {}, {}
            for tk, wt in w.items():
                if not ex_open(tk, t):
                    r = 0.0
                else:
                    r = ret(tk, last_open(tk, prev, exch, idx), t)
                if r is None:          # ingen kurs: ute av dagens avkastning, vekten står (ingen handel)
                    n_no += 1
                    drift[tk] = wt
                    continue
                drift[tk] = wt * (1 + r)
                ret_ok[tk] = True
                kept += wt
                gr += wt * r
            gr = gr / kept if kept else 0.0
            gs *= 1 + gr
            tot = sum(drift.values()) or 1.0
            w = {k: v / tot for k, v in drift.items()}
            # referanse: vekter etter børsfordelingen til holdingene
            comp: dict[str, int] = {}
            for tk in drift:
                if exch.get(tk) and ret_ok.get(tk):
                    comp[exch[tk]] = comp.get(exch[tk], 0) + 1
            n = sum(comp.values())
            br = 0.0
            for e, c in comp.items():
                ser = idx.get(IDX[e], {})
                a, b = last_close(ser, prev), ser.get(t)
                if a and b:
                    br += c / n * (b / a - 1)
            bm *= 1 + br
        # rebalansering på sluttkurs t mot lista fra siste logg-dato < t
        mem = members(t)
        tgt = {k: 1 / len(mem) for k in mem} if mem else {}
        cost = 0.0
        for k in set(w) | set(tgt):
            row = mem.get(k) or seen.get(k)   # utgang: flagg fra siste rad aksjen hadde på lista
            illq = "illiquid" in ((row or {}).get("flags") or "").split("|")
            rate = RULES["cost_each_way_illiquid"] if illq else RULES["cost_each_way"]
            cost += abs(tgt.get(k, 0) - w.get(k, 0)) * rate
        # første rad = 100 (før handel); inngangskostnaden på dag 1 trekkes i rad 2 sammen med den dagens handler
        gs *= 1 - (cost + carry if prev is not None else 0.0)
        carry = cost if prev is None else 0.0
        seen.update(mem)
        w, prev = tgt, t
        out.append({"date": t, "gs_index": gs, "benchmark": bm, "n_members": len(mem), "n_no_price": n_no})
    return out


def last_open(tk, d, exch, idx):
    """Siste dag <= d da tickerens børs var åpen (for stengte dager i dagsparet)."""
    e = exch.get(tk)
    ser = idx.get(IDX[e]) if e else None
    if not ser:
        return d
    ks = [k for k in ser if k <= d]
    return max(ks) if ks else d


def _exch(tickers, cache_path: Path) -> dict:
    from .since import BENCH, bench_for
    rev = {"OSEBX.OL": "oslo", "^IXIC": "nasdaq", "^NYA": "nyse"}
    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
        except Exception:
            cache = {}
    out = {}
    for t in tickers:
        b = bench_for(t)
        if b:
            out[t] = rev[b[0]]
            continue
        if t not in cache:
            try:
                import yfinance as yf
                cache[t] = (yf.Ticker(t).get_info() or {}).get("exchange")
            except Exception:
                cache[t] = None
        ex = (cache.get(t) or "").lower()
        out[t] = ("nasdaq" if ex in ("nms", "ngm", "ncm", "nasdaq") else
                  "nyse" if ex in ("nyq", "ase", "pcx", "nyse", "amex") else "oslo" if ex == "osl" else None)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=0, sort_keys=True))
    return out


def _yf(tickers, start):
    import yfinance as yf
    d = yf.download(sorted(tickers), start=start, auto_adjust=True, progress=False)["Close"]
    out = {}
    for c in d.columns:
        s = d[c].dropna()
        out[c] = {str(k.date()): float(v) for k, v in s.items()}
    return out


def build(out_path: Path = OUT, cat_path: Path = CAT_LOG, corr_path: Path = CORR) -> list[dict]:
    """Beregner hele serien på nytt (deterministisk fra loggen) og skriver logs/gs_index.csv."""
    from datetime import date
    from .config import DATA
    rows = load_rows(cat_path, corr_path)
    lists = lists_by_date(rows)
    tks = sorted({t for v in lists.values() for t in v})
    idx = _yf(list(IDX.values()), "2026-09-20")
    yfp = _yf(tks, "2026-09-20")
    exch = _exch(tks, DATA / "cache" / "gs_exchange.json")
    today = date.today().isoformat()
    days = sorted({d for s in idx.values() for d in s if d < today or d == max(s)})
    res = compute(lists, days, logged_prices(rows), yfp, exch, idx)
    ex = {r["date"]: r["gs_index"] for r in compute(lists, days, logged_prices(rows), yfp, exch, idx, frozenset({"TECH.OL"}))}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=COLS)
        wr.writeheader()
        for r in res:
            wr.writerow({"date": r["date"], "gs_index": f"{r['gs_index']:.4f}", "benchmark": f"{r['benchmark']:.4f}",
                         "n_members": r["n_members"], "n_no_price": r["n_no_price"], "gs_ex_tech": f"{ex.get(r['date'], float('nan')):.4f}"})
    return res


def run(status: dict) -> None:
    try:
        res = build()
        status["GS-indeks (intern)"] = f"ok ({len(res)} handelsdager; vises fra {MIN_DAYS_PUBLIC})"
    except Exception as ex:
        log.exception("gs_index failed")
        status["GS-indeks (intern)"] = f"FAILED: {ex}"


def read(path: Path = OUT) -> list[dict]:
    if not Path(path).exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def section_html(path: Path = OUT) -> str:
    """Seksjon øverst i Signal-boka (UxBot-spek). Tom streng (ingenting i HTML) til >= 60 handelsdager. gs_ex_tech vises aldri."""
    rs = read(path)
    if len(rs) < MIN_DAYS_PUBLIC:
        return ""
    g = [float(r["gs_index"]) for r in rs]
    b = [float(r["benchmark"]) for r in rs]
    lo, hi = min(g + b), max(g + b)
    span = (hi - lo) or 1.0
    W, H, PR = 1000, 300, 110

    def pts(v):
        return " ".join(f"{i / (len(v) - 1) * (W - PR):.1f},{10 + (hi - x) / span * (H - 20):.1f}" for i, x in enumerate(v))

    def ly(x):
        return 10 + (hi - x) / span * (H - 20)
    yg, yb = ly(g[-1]), ly(b[-1])
    if abs(yg - yb) < 16:
        yg, yb = (yg - 8, yb + 8) if yg <= yb else (yg + 8, yb - 8)
    svg = (f'<svg class="gs-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" aria-label="GS-indeksen og referansen">'
           f'<polyline fill="none" stroke="#8b949e" stroke-width="2" vector-effect="non-scaling-stroke" points="{pts(b)}"/>'
           f'<polyline fill="none" stroke="#58a6ff" stroke-width="2" vector-effect="non-scaling-stroke" points="{pts(g)}"/>'
           f'<text x="{W - PR + 6}" y="{yg + 4:.1f}" fill="#58a6ff" font-size="13">GS-indeks</text>'
           f'<text x="{W - PR + 6}" y="{yb + 4:.1f}" fill="#8b949e" font-size="13">Referanse</text></svg>')
    nn = rs[-1].get("n_no_price") or "0"
    return ('<section class="gs-sec card"><h2 style="margin:0 0 6px;font-size:16px">GS-indeksen</h2>'
            '<style>.gs-svg{display:block;width:100%;height:320px}@media(max-width:599px){.gs-svg{height:220px}}</style>'
            f'{svg}<p class="mut" style="margin:6px 0 0;font-size:12px;line-height:16px">'
            f'{E(nn)} aksjer uten kurs {E(rs[-1]["date"][8:10] + "." + rs[-1]["date"][5:7])} · {E(FLAG_TEXT)}</p></section>')
