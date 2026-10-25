"""Læringsløkka – bare rådata (AnalBot regner ut tall og avgjør funn). Alt her er privat: logs/, aldri site/.

Hver natt:
  logs/learn_raw.csv   dato, ticker, rang, score, signaltyper, kurs, 5/20/60-dagers avkastning for tickeren og for hovedindeksen
                       på tickerens børs (samme kobling som den grå indekslinja: since.bench_for).
  logs/learn_exits.csv tickere som var på lista i forrige kjøring, men ikke i dag, med årsak: cut60 (score > 0, rang > 60),
                       score0 (fortsatt kandidat med score 0, eller ingen kandidat lenger), data (ingen kursdata i dag).
  logs/dq_flags.jsonl  datakvalitetsflagg: jump40 (> 40 % endring på én dag, siste 5 dager), factor (Yahoo har justert
                       historikken bakover med en konstant faktor mot loggførte kurser), stale (kurs mangler ≥ 2 handelsdager
                       mot indeksen), log_gap (tickeren manglet i 1 kjøring midt i en periode).
Likt score ved kuttet på 60 (AnalBot 25.10): 1) ticker som allerede er på lista blir, 2) flere uavhengige signaltyper først,
3) tickernavn alfabetisk. Utfall med samme score som plass 60 logges som «lik score, kutt 60»."""
from __future__ import annotations

import csv, json, logging
from datetime import date

from .config import LOGS

log = logging.getLogger(__name__)
RAW, EXITS, DQ = LOGS / "learn_raw.csv", LOGS / "learn_exits.csv", LOGS / "dq_flags.jsonl"
CAT_LOG = LOGS / "categories.csv"
FACTOR_TOL = 0.02     # avvik > 2 % mellom Yahoo i dag og loggført kurs på samme dato
FACTOR_SPREAD = 0.005  # ... og samme forhold (±0,5 %) på minst 2 loggførte datoer = konstant faktor


def _closes(tickers, period="1y"):
    import yfinance as yf
    out = {}
    if not tickers:
        return out
    d = yf.download(sorted(set(tickers)), period=period, auto_adjust=False, progress=False, group_by="column")["Close"]
    if not hasattr(d, "columns"):
        d = d.to_frame(tickers[0])
    for t in d.columns:
        s = d[t].dropna()
        out[str(t)] = {str(k.date()): float(v) for k, v in s.items()}
    return out


def n_types(e: dict) -> int:
    """Antall uavhengige signaltyper = signaltyper med poeng > 0."""
    return sum(1 for v in (e.get("points") or {}).values() if (v or 0) > 0)


def prev_list(today: str = "") -> set:
    rows = _log_rows()
    runs = sorted({r["date"] for r in rows if not today or r["date"] < today})
    return {r["ticker"] for r in rows if runs and r["date"] == runs[-1] and r.get("category") != "tema"}


def rank_candidates(cands: list[dict], prev: set) -> list[dict]:
    """Score synkende; ved likt score: på lista fra før, flere signaltyper, alfabetisk."""
    return sorted(cands, key=lambda e: (-(e.get("score") or 0), e["ticker"] not in prev, -n_types(e), e["ticker"]))


def _ret(ser: dict, n: int):
    ks = sorted(ser)
    if len(ks) <= n:
        return None
    return ser[ks[-1]] / ser[ks[-1 - n]] - 1


def _append_csv(path, cols, rows):
    if not rows:
        return
    head = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if head:
            w.writeheader()
        w.writerows(rows)


def _log_rows():
    if not CAT_LOG.exists():
        return []
    with CAT_LOG.open(newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("date") and r.get("ticker")]


def factor_check(ticker: str, logged: list[tuple[str, float]], ser: dict) -> dict | None:
    """logged = [(price_date, loggført kurs), ...]. Returnerer {"factor", "n", "dates"} når Yahoo i dag avviker fra loggførte
    kurser med samme konstante faktor på ≥ 2 datoer, ellers None."""
    rat = [(d, ser[d] / p) for d, p in logged if p and d in ser]
    dev = [(d, r) for d, r in rat if abs(r - 1) > FACTOR_TOL]
    if len(dev) < 2:
        return None
    # største gruppe med samme forhold
    best = []
    for _, r0 in dev:
        g = [(d, r) for d, r in dev if abs(r / r0 - 1) <= FACTOR_SPREAD]
        if len(g) > len(best):
            best = g
    if len(best) < 2:
        return None
    rs = sorted(r for _, r in best)
    return {"factor": round(rs[len(rs) // 2], 6), "n": len(best), "dates": sorted({d for d, _ in best})}


def dq_write(flags: list[dict]) -> None:
    """Skriv flagg én gang per (dato, ticker, type)."""
    have = set()
    if DQ.exists():
        for l in DQ.read_text().splitlines():
            try:
                j = json.loads(l)
                have.add((j["date"], j["ticker"], j["type"]))
            except Exception:
                pass
    with DQ.open("a") as f:
        for x in flags:
            k = (x["date"], x["ticker"], x["type"])
            if k not in have:
                have.add(k)
                f.write(json.dumps(x, ensure_ascii=False) + "\n")


def record(snap: dict, ranked: list[dict], today: str | None = None) -> dict:
    from .since import bench_for
    today = today or str(snap.get("date") or date.today())
    tick = [e["ticker"] for e in snap.get("tickers", [])]
    benches = {t: bench_for(t) for t in tick}
    idx_t = sorted({b[0] for b in benches.values() if b})
    rows = _log_rows()
    runs = sorted({r["date"] for r in rows if r["date"] < today})
    prev = runs[-1] if runs else None
    prev_t = sorted({r["ticker"] for r in rows if r["date"] == prev and r.get("category") != "tema"}) if prev else []
    try:
        px = _closes(tick + idx_t + [t for t in prev_t if t not in tick])
    except Exception as ex:
        log.warning("learnloop prices: %s", ex)
        px = {}
    # 1) rådata
    raw = []
    for i, e in enumerate(snap.get("tickers", []), 1):
        t, b = e["ticker"], benches.get(e["ticker"])
        s, bs = px.get(t) or {}, (px.get(b[0]) if b else None) or {}
        rr = {"date": today, "ticker": t, "rank": i, "score": e.get("score"), "types": "|".join(sorted(k for k, v in (e.get("points") or {}).items() if v > 0)),
              "close": round(s[max(s)], 4) if s else "", "close_date": max(s) if s else "", "index": b[0] if b else ""}
        for n in (5, 20, 60):
            a, x = _ret(s, n), _ret(bs, n)
            rr[f"r{n}"] = "" if a is None else round(a, 6)
            rr[f"i{n}"] = "" if x is None else round(x, 6)
        raw.append(rr)
    if RAW.exists() and any(l.startswith(today + ",") for l in RAW.read_text().splitlines()):
        raw = []   # én gang per dato
    _append_csv(RAW, ["date", "ticker", "rank", "score", "types", "close", "close_date", "index", "r5", "i5", "r20", "i20", "r60", "i60"], raw)
    # 2) utfall
    pos = {e["ticker"]: (i, e.get("score") or 0, bool((e.get("stats") or {}).get("close"))) for i, e in enumerate(ranked, 1)}
    exits = []
    for t in prev_t:
        if t in tick:
            continue
        if t in pos and not pos[t][2]:
            why = "data"
        elif t in pos and pos[t][1] > 0:
            why = "lik score, kutt 60" if len(ranked) >= 60 and pos[t][1] == (ranked[59].get("score") or 0) else "cut60"
        else:
            why = "score0"
        exits.append({"date": today, "ticker": t, "prev_run": prev, "reason": why,
                      "rank": pos[t][0] if t in pos else "", "score": pos[t][1] if t in pos else ""})
    if EXITS.exists():   # ny kjøring samme dato erstatter dagens utfall (siste kutt gjelder)
        keep = [l for l in EXITS.read_text().splitlines() if not l.startswith(today + ",")]
        EXITS.write_text("\n".join(keep) + "\n" if keep else "")
        if len(keep) <= 1:
            EXITS.unlink()
    _append_csv(EXITS, ["date", "ticker", "prev_run", "reason", "rank", "score"], exits)
    # 3) datakvalitet
    flags = []
    last_idx = {b: max(px[b]) for b in idx_t if px.get(b)}
    by = {}
    for r in rows:
        by.setdefault(r["ticker"], []).append(r)
    for t in tick:
        s = px.get(t) or {}
        ks = sorted(s)
        for a, b2 in zip(ks[-6:-1], ks[-5:]):
            ch = s[b2] / s[a] - 1
            if abs(ch) > 0.40:
                flags.append({"date": today, "ticker": t, "type": "jump40", "day": b2, "change": round(ch, 4)})
        b = benches.get(t)
        if s and b and b[0] in last_idx:
            iks = sorted(px[b[0]])
            lag = sum(1 for d in iks if d > ks[-1])
            if lag >= 2:
                flags.append({"date": today, "ticker": t, "type": "stale", "last_price": ks[-1], "index_last": last_idx[b[0]], "missing_days": lag})
        if not s:
            flags.append({"date": today, "ticker": t, "type": "stale", "last_price": None, "missing_days": None})
        lg = [(r["price_date"], float(r["price"])) for r in by.get(t, []) if r.get("price") and r.get("price_date")]
        fc = factor_check(t, lg, s) if s else None
        if fc:
            flags.append({"date": today, "ticker": t, "type": "factor", **fc})
        mine = sorted({r["date"] for r in by.get(t, [])})
        if len(mine) >= 2 and mine[-1] == today:
            a, b2 = mine[-2], mine[-1]
            gap = [d for d in runs if a < d < b2]
            if gap:
                flags.append({"date": today, "ticker": t, "type": "log_gap", "from": a, "to": b2, "missing_runs": gap})
    dq_write(flags)
    return {"raw": len(raw), "exits": len(exits), "flags": len(flags)}
