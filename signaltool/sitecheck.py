"""Sanity check of the built site before deploy (python -m signaltool check-site). Exit code 1 = do NOT deploy; the previous
GitHub Pages version stays live. Checks only structure (files, sizes, key sections), never content quality."""
from __future__ import annotations
import json
from pathlib import Path

MIN_INDEX, MAX_INDEX = 8_000, 15_000_000      # bytes (ny kompakt forside ~15 kB)
REQUIRED = {
    "index.html": ["<nav", "Oversikt", "Temascore"],
    "metode.html": ['id="datakvalitet"', 'id="kontroll"', "Kildestatus ved siste kjøring", 'id="aerlig"', "Ærlig status"],
    "kilder.html": ["metode.html"],
    "tickere.html": ["Tickere"],
    "temaer.html": ["Temaer"],
    "oslo.html": ["Oslo Børs"],
    "makro.html": [], "kalender.html": [], "style.css": [],
}


def check(site: Path) -> list[str]:
    problems = []
    idx = site / "index.html"
    if not idx.exists():
        return [f"{idx} mangler"]
    n = idx.stat().st_size
    if not MIN_INDEX <= n <= MAX_INDEX:
        problems.append(f"index.html har urimelig størrelse ({n} byte, forventet {MIN_INDEX}–{MAX_INDEX})")
    for f, needles in REQUIRED.items():
        p = site / f
        if not p.exists():
            problems.append(f"{f} mangler")
            continue
        txt = p.read_text(errors="replace")
        problems += [f"{f}: mangler «{x}»" for x in needles if x not in txt]
    try:
        d = json.loads((site / "data.json").read_text())
        if not d.get("date") or not d.get("themes"):
            problems.append("data.json mangler dato eller temaer")
    except (OSError, ValueError) as ex:
        problems.append(f"data.json uleselig: {ex}")
    try:
        from .theme_maps import MAPS
        problems += [f"tema/{M['file']}.html mangler" for M in MAPS.values() if not (site / "tema" / f"{M['file']}.html").exists()]
    except Exception as ex:   # the check itself must not crash on an import problem
        problems.append(f"temakart-sjekk feilet: {ex}")
    if not list((site / "ticker").glob("*.html")):
        problems.append("ingen ticker-sider")
    try:
        from .config import LOGS
        problems += log_page_problems(site, LOGS / "categories.csv")
    except Exception as ex:
        problems.append(f"loggsjekk feilet: {ex}")
    return problems


def log_page_problems(site: Path, log: Path) -> list[str]:
    """Hver ticker i fremoverloggen for siste dato (alle kategorier) skal ha ticker/<slug>.html. Sider for tickere som ikke er
    i dagens logg er bare lov for kandidater som bevisst ikke logges (ETF-er o.l., categories.loggable) – ellers feil."""
    import csv
    from .site import slug
    if not log.exists():
        return []
    rows = [r for r in csv.DictReader(log.open(newline="")) if r.get("date")]
    if not rows:
        return []
    last = max(r["date"] for r in rows)
    today = {r["ticker"] for r in rows if r["date"] == last}
    pages = {p.stem for p in (site / "ticker").glob("*.html")}
    out = [f"ticker/{slug(t)}.html mangler (i loggen {last})" for t in sorted(today) if slug(t) not in pages]
    try:
        dj = json.loads((site / "data.json").read_text())
    except (OSError, ValueError):
        dj = {}
    if str(dj.get("date")) != last:
        return []   # reserve-bygg fra eldre snapshot: sjekken gjelder bare når siden og loggen er fra samme kjøring
    snap = {e["ticker"]: e for e in dj.get("tickers", [])}
    from .categories import loggable
    allowed = {slug(t) for t, e in snap.items() if not loggable(t, (e.get("decision") or {}).get("quoteType"))}
    out += [f"ticker/{p}.html finnes, men tickeren er ikke i loggen {last}" for p in sorted(pages - {slug(t) for t in today} - allowed)]
    return out
