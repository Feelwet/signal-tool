"""Sanity check of the built site before deploy (python -m signaltool check-site). Exit code 1 = do NOT deploy; the previous
GitHub Pages version stays live. Checks only structure (files, sizes, key sections), never content quality."""
from __future__ import annotations
import json
from pathlib import Path

MIN_INDEX, MAX_INDEX = 15_000, 15_000_000     # bytes
REQUIRED = {
    "index.html": ['id="aerlig"', "Ærlig status", "<nav", "Oversikt"],
    "kilder.html": ['id="datakvalitet"', 'id="kontroll"', "Kildestatus ved siste kjøring"],
    "tickere.html": ["Kandidat-tickere"],
    "temaer.html": ["Alle temaer"],
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
    return problems
