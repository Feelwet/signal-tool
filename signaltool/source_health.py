"""Nattlig kildekontroll (AnalBot/bruker 26.10): dekning per kilde og felt mot en terskel.

- Dekning = andel av tickerne i kjøringen som har feltet (fond/ETF måles bare på kursfeltene).
- Under terskel (MIN_COVERAGE) = kildefeil for hele kjøringen. Da brukes siste fungerende versjon per ticker (høyst
  FALLBACK_MAX_TD handelsdager gammel, fra data/cache/source_lastgood.json) og tickeren får e["source_fallback"] =
  {"source", "date"}. Ingen verdier diktes opp: finnes ingen siste gode, står feltet tomt.
- Berørte rader skrives med source_fallback=1 i logs/source_fallback.csv (sidelogg; categories.csv røres ikke) og i
  learn_raw.csv. De holdes utenfor treffrater (categories.track_record), GS-indeksen og læringen.
- Siden viser «Data fra DD.MM» på tickeren.
- SIGNAL_FORCE_SOURCE_FAIL="Kurs (Yahoo)" (kommaseparert) tvinger en kilde til å feile (tørrkjøring/test): dagens
  verdier for kildens felt fjernes før målingen.
"""
from __future__ import annotations
import csv, json, logging, os
from datetime import date
from pathlib import Path
import numpy as np
from .config import DATA, LOGS

log = logging.getLogger(__name__)
MIN_COVERAGE = 0.5          # samme grense som Yahoo-vakten (> 50 % feil = kildefeil)
FALLBACK_MAX_TD = 5         # AnalBot 25.10
LASTGOOD = DATA / "cache" / "source_lastgood.json"
SIDELOG = LOGS / "source_fallback.csv"
SIDE_COLS = ["date", "ticker", "source", "fallback_date", "source_fallback"]
PRICE = "Kurs (Yahoo)"
FUND = "Fundamentaldata (Yahoo)"
# kilde -> [(felt, hvor: "stats"|"decision", gjelder fond)]
SOURCES = {PRICE: [("close", "stats", True), ("sma50", "stats", True), ("last_date", "stats", True)],
           FUND: [("sector", "decision", False), ("marketCap", "decision", False), ("trailingPE", "decision", False),
                  ("numberOfAnalystOpinions", "decision", False)]}


def _get(e, where, k):
    v = (e.get(where) or {}).get(k)
    if v is None or (isinstance(v, float) and v != v) or (isinstance(v, str) and not v.strip()):
        return None
    return v


def _etf(e):
    from .datacov import is_etf
    try:
        return is_etf(e)
    except Exception:
        return False


def coverage(tickers: list[dict]) -> dict:
    """{kilde: {felt: {"have", "of", "pct", "ok"}}}"""
    out = {}
    for src, fields in SOURCES.items():
        out[src] = {}
        for k, where, etf_ok in fields:
            pool = [e for e in tickers if etf_ok or not _etf(e)]
            have = sum(1 for e in pool if _get(e, where, k) is not None)
            pct = have / len(pool) if pool else None
            out[src][k] = {"have": have, "of": len(pool), "pct": None if pct is None else round(pct, 4),
                           "ok": pct is None or pct >= MIN_COVERAGE}
    return out


def forced() -> set[str]:
    return {s.strip() for s in os.environ.get("SIGNAL_FORCE_SOURCE_FAIL", "").split(",") if s.strip()}


def _force(tickers, srcs):
    for e in tickers:
        for src in srcs:
            for k, where, _ in SOURCES.get(src, []):
                if isinstance(e.get(where), dict):
                    e[where].pop(k, None)


def check(snap: dict, status: dict | None = None, today: str | None = None, path: Path | None = None,
          force: set | None = None) -> dict:
    """Måler dekning, bruker siste gode ved kildefeil og lagrer dagens gode når kilden er frisk."""
    path = Path(path or LASTGOOD)
    today = today or str(snap.get("date") or date.today().isoformat())
    tk = snap.get("tickers") or []
    force = forced() if force is None else set(force)
    if force:
        _force(tk, force)
    try:
        good = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        good = {}
    cov = coverage(tk)
    failed = sorted(s for s, f in cov.items() if not all(x["ok"] for x in f.values()))
    used: dict[str, list] = {}
    for src in SOURCES:
        g = good.setdefault(src, {})
        if src in failed:
            for e in tk:
                miss = [(k, w) for k, w, etf_ok in SOURCES[src] if (etf_ok or not _etf(e)) and _get(e, w, k) is None]
                lg = g.get(e["ticker"])
                if not miss or not lg or int(np.busday_count(lg["date"], today)) > FALLBACK_MAX_TD:
                    continue
                n = 0
                for k, w in miss:
                    if lg["vals"].get(k) is not None:
                        e.setdefault(w, {})[k] = lg["vals"][k]
                        n += 1
                if n:
                    e["source_fallback"] = {"source": src, "date": lg["date"]}
                    used.setdefault(src, []).append(e["ticker"])
        else:
            for e in tk:
                vals = {k: _get(e, w, k) for k, w, _ in SOURCES[src]}
                if any(v is not None for v in vals.values()):
                    g[e["ticker"]] = {"date": today, "vals": {k: v for k, v in vals.items() if v is not None}}
    # fundamentaldata gjenbrukt av Yahoo-vakten i decision.py teller også som fallback
    for e in tk:
        fd = (e.get("decision") or {}).get("fund_fallback")
        if fd and not e.get("source_fallback"):
            e["source_fallback"] = {"source": FUND, "date": fd}
            used.setdefault(FUND, []).append(e["ticker"])
    after = coverage(tk)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(good, ensure_ascii=False, default=str))
    except OSError as ex:
        log.warning("source_lastgood: %s", ex)
    res = {"date": today, "threshold": MIN_COVERAGE, "before": cov, "after": after, "failed": failed,
           "forced": sorted(force), "used": {k: sorted(v) for k, v in used.items()}}
    snap["source_health"] = res
    if status is not None:
        for src in SOURCES:
            lo = min((x["pct"] for x in cov[src].values() if x["pct"] is not None), default=None)
            lab = f"Kildekontroll: {src} (≥ {int(MIN_COVERAGE * 100)} % per felt)"
            if src in failed:
                status[lab] = (f"FAILED: laveste dekning {lo * 100:.0f} %{' (tvunget)' if src in force else ''} – siste gode brukt for "
                               f"{len(used.get(src, []))} tickere, source_fallback=1")
            else:
                status[lab] = f"ok (laveste dekning {'–' if lo is None else f'{lo * 100:.0f} %'})"
    return res


def rows(snap: dict) -> list[dict]:
    return [{"date": str(snap["date"]), "ticker": e["ticker"], "source": e["source_fallback"]["source"],
             "fallback_date": e["source_fallback"]["date"], "source_fallback": 1}
            for e in snap.get("tickers") or [] if e.get("source_fallback")]


def append_rows(snap: dict, path: Path | None = None) -> int:
    """Skriver dagens fallback-rader. Bare dagens dato erstattes; avsluttede datoer røres aldri."""
    path = Path(path or SIDELOG)
    day = str(snap["date"])
    old = []
    if path.exists():
        with path.open(newline="") as f:
            old = [r for r in csv.DictReader(f)]
    keep = [r for r in old if r.get("date") != day]
    new = rows(snap)
    if not new and len(keep) == len(old):
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SIDE_COLS)
        w.writeheader()
        for r in keep + new:
            w.writerow({k: r.get(k, "") for k in SIDE_COLS})
    return len(new)


def excluded(path: Path | None = None) -> set[tuple[str, str]]:
    """{(dato, ticker)} med source_fallback=1 – holdes utenfor treffrater, GS-indeksen og læringen."""
    path = Path(path or SIDELOG)
    if not path.exists():
        return set()
    with path.open(newline="") as f:
        return {(r["date"], r["ticker"]) for r in csv.DictReader(f) if str(r.get("source_fallback")).strip() in ("1", "1.0")}


def text(e: dict) -> str:
    fb = e.get("source_fallback")
    if not fb:
        return ""
    d = str(fb["date"])
    return f"Data fra {d[8:10]}.{d[5:7]} ({fb['source']} feilet i dag)"
