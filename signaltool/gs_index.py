"""GS-indeksen (AnalBots spek, 26.10.2026): likevektet indeks over lista slik den faktisk så ut hver dag (point-in-time).

Metode
- Medlemmer: rader i logs/categories.csv med kategori kjop/hold/watch/tema og rangert=1 (AnalBot 26.10: tema tas med igjen;
  utelukkelsen var aldri godkjent). Logg-datoer uten rangert-feltet (før feltet kom) kan ikke skille «Ikke rangert» fra
  rangerte rader: alle radene tas med, og dagene som bruker en slik liste får flag=FLAG (telles).
- Ugyldige dagsavkastninger: |r| > 30 % uten kjent splitt (SPLITS) er ugyldige: ute av dagens avkastning (ikke et tap),
  vekten står, telles i n_invalid og logges i logs/gs_invalid.csv (type=invalid_jump).
- Tynt omsatt: volum < 20 000 (Yahoo, aksjevolum) på åpen børs logges i gs_invalid.csv (type=thin_volume). Aksjen tas
  ikke ut av avkastningen (AnalBot 16.11).
- NOKBF (OTC/PNK) er med og regnes på US-siden av referansen (^NYA).
- logs/categories_corrections.csv brukes (exclude-rader tas ut, korrigerte priser brukes). categories.csv endres aldri.
- Logg-dato L = lista kjent den dagen. Inngang/utgang skjer på sluttkurs første handelsdag ETTER L (holdingene som gjelder fra
  sluttkurs dag t er lista fra siste logg-dato < t).
- Likevekt, daglig rebalansering. Kostnad per handel = |vektendring| × 0,2 % (0,5 % lite omsatt, flagget «illiquid» i loggen),
  samme satser som Signal-boka (portfolio_rules.py). Kostnad for handler på sluttkurs t trekkes i raden for t
  (unntak: første rad er 100 før handel; inngangskostnaden trekkes i rad 2).
- Kurs: én kurstype i hele serien for både nivå og avkastning (PRICE_TYPE = adj_close: Yahoo Adj Close, samme tall som
  auto_adjust=True Close). Loggførte sluttkurser brukes bare når begge dager i dagsparet er av den typen; ujusterte
  loggkurser (typisk frosset før et utbytte) brukes ikke, da tas Yahoo-paret. Blanding av justert og ujustert stopper
  ombyggingen (RebuildStopped, dq_flags gs_price_type_mismatch). Aldri oppfunnet: mangler kurs for t eller t-1 (og børsen
  var åpen), droppes aksjen den dagen (n_no_price).
  Stengt egen børs den dagen (indeksen har ingen kurs) = 0 % avkastning, ikke «uten kurs».
- Referanse: OSEBX / Nasdaq Composite / NYSE Composite vektet etter lista sin børsfordeling den dagen (samme mapping som
  since.bench_for: Oslo -> OSEBX.OL, Nasdaq -> ^IXIC, NYSE/Arca/American -> ^NYA). Ingen kostnader.
- gs_index = hovedindeksen = uten TECH.OL til årsaken til kurshoppet er bekreftet; gs_with_tech = med TECH.OL (internt).
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
LIST_CATS = {"kjop", "hold", "watch", "tema"}
MAX_DAY_MOVE = 0.30
THIN_VOLUME = 20_000   # AnalBot 16.11: flagges i gs_invalid, tas ikke ut
SPLITS: frozenset = frozenset()   # {(ticker, dato)} kjente splitter/hendelser som gjør |r| > 30 % gyldig
MAIN_EXCLUDE = frozenset({"TECH.OL"})
PRICE_TYPE = "adj_close"  # AnalBot 16.11: samme type for nivå og avkastning (Yahoo Adj Close / auto_adjust)
INVALID = LOGS / "gs_invalid.csv"
START = "2026-09-27"
MIN_DAYS_PUBLIC = 60
FLAG_TEXT = "Kort periode, mest tilfeldig svingning."   # results.SHORT_TIP; ordet FLAG vises aldri
COLS = ["date", "gs_index", "benchmark", "n_members", "n_no_price", "n_invalid", "flag", "gs_with_tech"]
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
    from .source_health import excluded   # source_fallback=1 (kildefeil, siste gode brukt) holdes utenfor indeksen den dagen
    fb = excluded()
    rows = [r for r in rows if (r["date"], r["ticker"]) not in fb]
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


def _rv(v):
    from .categories import rangert_val
    return rangert_val(v)


def lists_by_date(rows: list[dict], start: str = START) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        if r["date"] >= start and r.get("category") in LIST_CATS and _rv(r.get("rangert")) != 0:
            out.setdefault(r["date"], {})[r["ticker"]] = r
    return out


def unflagged_dates(rows: list[dict]) -> set[str]:
    """Logg-datoer der rangert-feltet (1/0) finnes på alle radene, så «Ikke rangert» kan skilles ut."""
    by: dict[str, bool] = {}
    for r in rows:
        ok = _rv(r.get("rangert")) is not None
        by[r["date"]] = by.get(r["date"], True) and ok
    return {d for d, ok in by.items() if ok}


def logged_prices(rows: list[dict]) -> dict[str, dict[str, tuple]]:
    """{ticker: {price_date: (kurs, korrigert)}}. Et dagspar med én korrigert og én ukorrigert kurs kan ligge på ulik
    justeringsbasis (TECH.OL, faktor ~2,14) og brukes ikke; da tas Yahoo-paret."""
    p: dict[str, dict[str, tuple]] = {}
    for r in rows:
        v, d = _f(r.get("price")), r.get("price_date")
        if v and d:
            p.setdefault(r["ticker"], {})[d] = (v, bool(r.get("_corrected")))
    return p


def closed_logged(rows: list[dict], times: dict | None = None) -> list[dict]:
    """Radene med kurs bare når kursen var en sluttkurs da den ble logget (close_valid: logget etter stengetid + 30).
    Korrigerte kurser (categories_corrections) beholdes. Ukjent loggtid: kursen tas bort (Yahoo brukes)."""
    from . import close_valid as CV
    t = CV.load() if times is None else times
    at = {}
    for tk, lst in t.items():
        for pd_, v, when, dd in lst:
            at.setdefault((dd, tk, pd_, round(v, 6)), []).append(when)
    out = []
    for r in rows:
        v, d = _f(r.get("price")), (r.get("price_date") or "")[:10]
        if v and d and not r.get("_corrected"):
            ws = at.get((r["date"], r["ticker"], d, round(v, 6))) or []
            if not any(CV.is_close(r["ticker"], d, w) for w in ws):
                r = {**r, "price": "", "_intraday": True}
        out.append(r)
    return out


def compute(lists: dict[str, dict[str, dict]], days: list[str], logp: dict, yfp: dict, exch: dict, idx: dict,
            exclude: frozenset = frozenset(), known: set | None = None, splits: frozenset = SPLITS,
            invalid_log: list | None = None, volumes: dict | None = None) -> list[dict]:
    """lists: {logdato: {ticker: rad}}, days: handelsdager (stigende), logp/yfp: {ticker: {dato: kurs}},
    exch: {ticker: 'oslo'|'nasdaq'|'nyse'|None}, idx: {indeksticker: {dato: kurs}}. Returnerer rader fra første handelsdag > første logg-dato."""
    ldates = sorted(lists)
    if not ldates:
        return []
    days = [d for d in days if d > ldates[0]]

    def members(t):
        prev = [d for d in ldates if d < t]
        if not prev:
            return {}, None
        return {k: v for k, v in lists[prev[-1]].items() if k not in exclude}, prev[-1]

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
        n_no = n_inv = 0
        if prev is not None and w:
            # avkastning prev -> t for holdingene w
            gr, kept, drift, ret_ok = 0.0, 0.0, {}, {}
            for tk, wt in w.items():
                if not ex_open(tk, t):
                    r = 0.0
                else:
                    r = ret(tk, last_open(tk, prev, exch, idx), t)
                    if volumes is not None and invalid_log is not None:
                        vol = (volumes.get(tk) or {}).get(t)
                        if vol is not None and vol < THIN_VOLUME:
                            invalid_log.append({"date": t, "prev": prev, "ticker": tk, "ret": r,
                                                "type": "thin_volume", "volume": vol})
                if r is not None and abs(r) > MAX_DAY_MOVE and (tk, t) not in splits:
                    n_inv += 1         # ugyldig (splitt-/faktorfeil): ute av dagens avkastning, ikke et tap; vekten står
                    if invalid_log is not None:
                        invalid_log.append({"date": t, "prev": prev, "ticker": tk, "ret": r})
                    drift[tk] = wt
                    continue
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
        mem, ld = members(t)
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
        out.append({"date": t, "gs_index": gs, "benchmark": bm, "n_members": len(mem), "n_no_price": n_no,
                    "n_invalid": n_inv, "flag": "FLAG" if (known is not None and ld is not None and ld not in known) else ""})
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
        if not b and (cache.get(t) or "").lower() in ("pnk", "oth", "otc", "oqx", "oqb"):
            out[t] = "nyse"   # OTC (f.eks. NOKBF): US-siden av referansen (AnalBot 26.10)
            continue
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


def _extract(d, field: str) -> dict:
    """{ticker: {dato: verdi}} fra en yf.download-ramme (felt Close eller Volume). Tom dict hvis feltet mangler."""
    out = {}
    if d is None or getattr(d, "empty", True):
        return out
    try:
        c = d[field]
    except KeyError:
        return out
    cols = getattr(c, "columns", None)
    if cols is None:
        return out
    for col in cols:
        s = c[col].dropna()
        if len(s):
            out[col] = {str(k.date()): float(v) for k, v in s.items()}
    return out


def _series(d) -> dict:
    """Justert sluttkurs: Adj Close når feltet finnes (auto_adjust=False), ellers Close (auto_adjust=True er allerede justert)."""
    out = _extract(d, "Adj Close")
    for t, ser in _extract(d, "Close").items():
        out.setdefault(t, ser)
    return out


def _yf(tickers, start, retries: int = 3, pause: float = 5.0, download=None, volume_out: dict | None = None,
        unadj_out: dict | None = None):
    """Yahoo-kurser for GS: justert sluttkurs (PRICE_TYPE=adj_close). auto_adjust=True (standard) gir justert verdi i Close;
    når unadj_out er gitt, hentes auto_adjust=False så ujustert Close kan klassifiseres, og returen er Adj Close.
    16.11 (hentehullet): yf.download i én batch gir stille en tom kolonne for tickere som feiler (tidsavbrudd/ratebegrensning)
    – AKRBP.OL, OKTA og CRWD manglet i ombyggingen 16.11 uten feilmelding. Tickere uten serie etter batchen hentes derfor på
    nytt én og én (opptil `retries` forsøk med pause). Det som fortsatt mangler, mangler i resultatet; build() avgjør om det
    stopper ombyggingen (missing_check).
    volume_out: {ticker: {dato: volum}} fra samme nedlasting (Volume, ikke justert).
    unadj_out: {ticker: {dato: ujustert Close}} fra samme nedlasting."""
    import time
    if download is None:
        import yfinance as yf
        download = yf.download
    want = sorted(set(tickers))
    aa = unadj_out is None

    def take(raw):
        if volume_out is not None:
            volume_out.update(_extract(raw, "Volume"))
        if unadj_out is not None:
            unadj_out.update(_extract(raw, "Close"))
        return _series(raw)

    out = take(download(want, start=start, auto_adjust=aa, progress=False, threads=False))
    for i in range(retries):
        miss = [t for t in want if not out.get(t)]
        if not miss:
            break
        if i:
            time.sleep(pause * i)
        for t in miss:
            try:
                got = take(download([t], start=start, auto_adjust=aa, progress=False, threads=False))
            except Exception as ex:   # noqa: BLE001 – en feilet enkeltticker skal bare telles som manglende
                log.warning("gs_index: Yahoo %s forsøk %d: %s", t, i + 1, ex)
                continue
            if got.get(t):
                out[t] = got[t]
    return out

def price_kind(value, close=None, adj=None, rel: float = 0.005, abs_tol: float = 0.05) -> str | None:
    """Klassifiserer en loggført kurs mot Yahoo Close og Adj Close: 'adj_close', 'close', 'both', eller None."""
    def ok(x):
        if x is None or not value:
            return False
        try:
            x = float(x)
        except (TypeError, ValueError):
            return False
        return abs(float(value) - x) <= max(abs_tol, rel * abs(x))
    a, c = ok(adj), ok(close)
    if a and c:
        return "both"
    if a:
        return "adj_close"
    if c:
        return "close"
    return None


def logged_prices_of_type(logp: dict, close_px: dict, adj_px: dict, want: str = PRICE_TYPE) -> tuple[dict, list]:
    """Beholder bare loggførte kurser av typen `want` eller 'both'. Avviste (annen type eller ukjent) returneres i lista."""
    kept, rejected = {}, []
    for tk, days in logp.items():
        for d, (v, corr) in days.items():
            kind = price_kind(v, (close_px.get(tk) or {}).get(d), (adj_px.get(tk) or {}).get(d))
            if kind in (want, "both"):
                kept.setdefault(tk, {})[d] = (v, corr)
            else:
                rejected.append({"ticker": tk, "date": d, "price": v, "price_type": kind or "unknown",
                                 "close": (close_px.get(tk) or {}).get(d),
                                 "adj_close": (adj_px.get(tk) or {}).get(d)})
    return kept, rejected


def check_price_types(level_type: str, return_types, dq_path: Path | None = None, date: str | None = None) -> None:
    """Stopper ombyggingen hvis nivå og avkastning ikke bruker samme kurstype. Logges i dq_flags (gs_price_type_mismatch)."""
    raw = {level_type, *({t for t in return_types if t} if not isinstance(return_types, str) else {return_types})}
    norm = {t for t in raw if t != "both"}
    if len(norm) <= 1:
        return
    note = (f"nivå={level_type}, avkastning={sorted(raw)} – blanding gir feil avkastning på utbyttedager")
    dq_log([{"date": date or today_iso(), "ticker": "GS", "type": "gs_price_type_mismatch",
             "level_type": level_type, "return_types": sorted(raw), "price_type": PRICE_TYPE, "note": note}], dq_path)
    raise RebuildStopped(f"ulik kurstype for nivå og avkastning ({note})")


def record_price_type(dq_path: Path | None = None) -> None:
    """Lagrer den låste kurstypen én gang (AnalBot 16.11)."""
    dq_log([{"date": "2026-11-16", "ticker": "GS", "type": "gs_price_type", "price_type": PRICE_TYPE,
             "note": "justert sluttkurs (Yahoo Adj Close / auto_adjust) for nivå og avkastning"}], dq_path)


DQ = LOGS / "dq_flags.jsonl"


class RebuildStopped(RuntimeError):
    """AnalBot 16.11: ombyggingen stoppes (gs_index.csv uendret) ved manglende data eller ulik kurstype for nivå og avkastning."""


def missing_check(tks, yfp: dict, rows: list[dict], idx: dict) -> tuple[list[str], list[str]]:
    """(stopper, uten_kilde). stopper = tickere som har hatt kurs (en loggført kurs i categories.csv) eller indekser, men
    mangler Yahoo-serie nå = hull i hentingen. uten_kilde = tickere som aldri har hatt en kurs fra noen kilde (ingen
    loggført kurs og ingen Yahoo-serie, f.eks. SFLN.OL, SWG.OL): de har alltid stått som «uten kurs» (n_no_price) og
    stopper ikke ombyggingen."""
    had = {r["ticker"] for r in rows if _f(r.get("price"))}
    stop = sorted([t for t in tks if not yfp.get(t) and t in had] + [k for k in IDX.values() if not idx.get(k)])
    nosrc = sorted(t for t in tks if not yfp.get(t) and t not in had)
    return stop, nosrc


def dq_log(flags: list[dict], path: Path | None = None) -> None:
    """Append-only, én gang per (dato, ticker, type)."""
    path = Path(path or DQ)
    have = set()
    if path.exists():
        for l in path.read_text().splitlines():
            try:
                j = json.loads(l)
                have.add((j.get("date"), j.get("ticker"), j.get("type")))
            except Exception:
                pass
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for x in flags:
            k = (x["date"], x["ticker"], x["type"])
            if k not in have:
                have.add(k)
                f.write(json.dumps(x, ensure_ascii=False) + "\n")


def build(out_path: Path = OUT, cat_path: Path = CAT_LOG, corr_path: Path = CORR, rewrite: bool = False,
          dq_path: Path | None = None) -> list[dict]:
    """Beregner hele serien på nytt (deterministisk fra loggen). Standard (nattkjøringen): bare nye rader legges til
    logs/gs_index.csv (append_only). rewrite=True skriver hele fila (lokal ombygging, krever AnalBots godkjente diff)."""
    from datetime import date
    from .config import DATA
    rows = load_rows(cat_path, corr_path)
    lists = lists_by_date(rows)
    tks = sorted({t for v in lists.values() for t in v})
    # AnalBot 11.11: bare LUKKEDE barer (stengetid + 30 min, børsens tidssone): dagens Yahoo-bar før det droppes, og loggførte
    # kurser som ble logget før stengetid + 30 (intradag, logs/price_log_times.csv) brukes ikke – da tas Yahoo-paret.
    from . import closedbars as CB
    idx = {k: CB.series(v, k) for k, v in _yf(list(IDX.values()), "2026-09-20").items()}
    vols: dict = {}
    unadj: dict = {}
    yfp = {k: CB.series(v, k) for k, v in _yf(tks, "2026-09-20", volume_out=vols, unadj_out=unadj).items()}
    vol_closed = {k: CB.series(v, k) for k, v in vols.items()}
    close_px = {k: CB.series(v, k) for k, v in unadj.items()}
    stop, nosrc = missing_check(tks, yfp, rows, idx)
    if stop:
        dq_log([{"date": today_iso(), "ticker": t, "type": "gs_rebuild_missing",
                 "note": "mangler Yahoo-serie i GS-ombyggingen; ombyggingen stoppet, gs_index.csv uendret"} for t in stop],
               dq_path)
        raise RebuildStopped(f"mangler data for {', '.join(stop)} – ombyggingen stoppet (ingen omregning uten dem)")
    if nosrc:
        log.info("gs_index: %d tickere uten kurs fra noen kilde (n_no_price som før): %s", len(nosrc), nosrc)
    rows = closed_logged(rows)
    exch = _exch(tks, DATA / "cache" / "gs_exchange.json")
    today = date.today().isoformat()
    days = sorted({d for s in idx.values() for d in s if d < today or d == max(s)})
    known = unflagged_dates(rows)
    logp, _rejected = logged_prices_of_type(logged_prices(rows), close_px, yfp, PRICE_TYPE)
    used_types = {PRICE_TYPE}
    for tk, ds in logp.items():
        for d, (v, _) in ds.items():
            used_types.add(price_kind(v, (close_px.get(tk) or {}).get(d), (yfp.get(tk) or {}).get(d)) or PRICE_TYPE)
    check_price_types(PRICE_TYPE, used_types, dq_path)
    record_price_type(dq_path)
    res = compute(lists, days, logp, yfp, exch, idx, MAIN_EXCLUDE, known, volumes=vol_closed)
    inv: list = []
    wt = {r["date"]: r for r in compute(lists, days, logp, yfp, exch, idx, frozenset(), known,
                                        invalid_log=inv, volumes=vol_closed)}
    with open(Path(out_path).with_name("gs_invalid.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "prev", "ticker", "ret", "type", "volume"])
        w.writeheader()
        for x in inv:
            ret = x.get("ret")
            vol = x.get("volume")
            w.writerow({"date": x["date"], "prev": x["prev"], "ticker": x["ticker"],
                        "ret": "" if ret is None else f"{ret:.4f}",
                        "type": x.get("type") or "invalid_jump",
                        "volume": "" if vol is None else f"{vol:.0f}"})
    jumps = [x for x in inv if (x.get("type") or "invalid_jump") == "invalid_jump"]
    if jumps:
        log.warning("gs_index: %d ugyldige dagsavkastninger (|r| > 30 %%): %s", len(jumps), jumps)
    fmt = [{"date": r["date"], "gs_index": f"{r['gs_index']:.4f}", "benchmark": f"{r['benchmark']:.4f}",
            "n_members": r["n_members"], "n_no_price": r["n_no_price"], "n_invalid": r["n_invalid"], "flag": r["flag"],
            "gs_with_tech": f"{wt[r['date']]['gs_index']:.4f}" if r["date"] in wt else ""} for r in res]
    if rewrite:
        write_full(out_path, fmt)
    else:
        append_only(out_path, fmt, dq_path)
    return res


def write_full(out_path: Path, fmt: list[dict]) -> None:
    """Full omskriving. Bare for lokal ombygging (diff til AnalBot); aldri i nattkjøringen."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=COLS)
        wr.writeheader()
        wr.writerows(fmt)


def chain_log(last: dict, base: dict, dq_path: Path | None = None) -> bool:
    """AnalBot 16.11: kjedepunktet (dato + fryst nivå, og omregnet nivå samme dato) logges i dq_flags første gang det skjer."""
    path = Path(dq_path or DQ)
    if path.exists() and any('"type": "gs_chain"' in l for l in path.read_text().splitlines()):
        return False
    dq_log([{"date": last["date"], "ticker": "GS", "type": "gs_chain", "level": last["gs_index"], "benchmark": last["benchmark"],
             "rebuilt_level": base["gs_index"], "rebuilt_benchmark": base["benchmark"],
             "note": "nye rader kjedes fra fryst nivå denne datoen (ny[t] / ny[dato])"}], path)
    return True


def append_only(out_path: Path, fmt: list[dict], dq_path: Path | None = None) -> int:
    """AnalBot 16.11: logs/gs_index.csv er fryst historikk. Nattkjøringen legger bare til rader med dato etter siste
    eksisterende rad; eksisterende rader (bytene i fila) endres aldri. Nye rader kjedes fra siste fryste nivå med den nyberegnede
    dagsendringen (ny[t] / ny[siste fryste dato]), så en avvikende omregning av historikken ikke gir et hopp. Finnes ikke siste
    fryste dato i den nye serien, legges ingenting til. Returnerer antall nye rader."""
    out_path = Path(out_path)
    if not out_path.exists() or out_path.stat().st_size == 0:
        write_full(out_path, fmt)
        return len(fmt)
    old = read(out_path)
    if not old:
        write_full(out_path, fmt)
        return len(fmt)
    last = old[-1]
    by = {r["date"]: r for r in fmt}
    base = by.get(last["date"])
    new = [r for r in fmt if r["date"] > last["date"]]
    if not new:
        return 0
    if base is None:
        log.warning("gs_index: siste fryste dato %s finnes ikke i ny serie – ingen rader lagt til", last["date"])
        return 0
    add = []
    for r in new:
        x = dict(r)
        for c in ("gs_index", "benchmark", "gs_with_tech"):
            try:
                x[c] = f"{float(last[c]) * float(r[c]) / float(base[c]):.4f}"
            except (TypeError, ValueError, ZeroDivisionError, KeyError):
                x[c] = ""
        add.append(x)
    chain_log(last, base, dq_path)
    raw = out_path.read_bytes()
    with open(out_path, "a", newline="") as f:
        if raw and not raw.endswith(b"\n"):
            f.write("\r\n" if b"\r\n" in raw else "\n")
        csv.DictWriter(f, fieldnames=COLS).writerows(add)
    return len(add)


def today_iso() -> str:
    from datetime import date
    return date.today().isoformat()


def run(status: dict) -> None:
    try:
        res = build()
        status["GS-indeks (intern)"] = f"ok ({len(res)} handelsdager; vises fra {MIN_DAYS_PUBLIC})"
    except RebuildStopped as ex:
        log.error("gs_index: %s", ex)
        status["GS-indeks (intern)"] = f"STOPPET: {ex}"
    except Exception as ex:
        log.exception("gs_index failed")
        status["GS-indeks (intern)"] = f"FAILED: {ex}"


def read(path: Path = OUT) -> list[dict]:
    if not Path(path).exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def section_html(path: Path = OUT) -> str:
    """Seksjon øverst i Signal-boka (UxBot-spek). Tom streng (ingenting i HTML) til >= 60 handelsdager. gs_with_tech vises aldri."""
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
