"""Revisjonslogg (AnalBot 11.11): når hver logget kurs (categories.csv og innkurs-sideloggen) ble logget, og om den var
en sluttkurs (logget etter børsens stengetid + 30 min, børsens egen tidssone – samme regel som displayprices / laering_fwd.day_closed).

STYRER IKKE INNKURSEN. Innkursen i Siden-raden/punktet hentes fra Yahoos dagshistorikk (since.yahoo_entry). Loggen beholdes for å
kunne si hvilke loggede verdier (læringsløkka, framovertestene, papirbøkene) som var intradag.

logs/price_log_times.csv (date, ticker, price_date, price, logged_at, basis):
- basis=run_start: starttidspunktet for kjøringen som logget raden. Fra 11.11 skriver pipeline dette selv (snap["generated"],
  Oslo-tid, før kursene hentes). Historikk: GitHub-kjøringen (nightly.yml) som laget loggcommiten, createdAt (nedre grense).
- basis=commit: ingen kjøring funnet rundt commiten; commit-tid (øvre grense)."""
from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import LOGS, ROOT

TIMES = LOGS / "price_log_times.csv"
COLS = ["date", "ticker", "price_date", "price", "logged_at", "basis"]
OSLO = ZoneInfo("Europe/Oslo")
_CACHE: dict = {}


def _dt(s: str) -> datetime:
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=OSLO)


def is_close(ticker: str, price_date: str, logged_at) -> bool:
    from .laering_fwd import day_closed
    if not price_date or not logged_at:
        return False
    return day_closed(str(price_date)[:10], ticker, _dt(logged_at) if isinstance(logged_at, str) else logged_at)


def load(path: Path | None = None) -> dict:
    """{ticker: [(price_date, price, logged_at, date), ...]} sortert på logged_at."""
    p = Path(path or TIMES)
    key = (str(p), p.stat().st_mtime if p.exists() else 0)
    if _CACHE.get("k") == key:
        return _CACHE["v"]
    out: dict = {}
    if p.exists():
        with p.open(newline="") as f:
            for r in csv.DictReader(f):
                try:
                    v = float(r["price"])
                except (TypeError, ValueError):
                    continue
                out.setdefault(r["ticker"], []).append((r["price_date"][:10], v, r["logged_at"], r["date"]))
    for k in out:
        out[k].sort(key=lambda x: _dt(x[2]))
    _CACHE.update(k=key, v=out)
    return out


def intraday(times: dict, ticker: str) -> list[tuple]:
    """Loggede verdier for tickeren som IKKE var sluttkurs da de ble logget: [(date, price_date, price, logged_at)]."""
    return [(dd, d, v, at) for d, v, at, dd in times.get(ticker, []) if not is_close(ticker, d, at)]


# ------------------------------------------------------------------------------------------------ logging
def append_run(snap: dict, path: Path | None = None, cat_path: Path | None = None, entry_path: Path | None = None) -> int:
    """Dagens rader i categories.csv og sideloggen med logged_at = kjøringens start (snap['generated'], Oslo)."""
    from .since import ENTRY_LOG
    from .categories import LOG_PATH
    day, gen = str(snap.get("date") or ""), snap.get("generated")
    if not day or not gen:
        return 0
    at = _dt(str(gen).replace(" ", "T")).isoformat()
    new = []
    for f in (cat_path or LOG_PATH, entry_path or ENTRY_LOG):
        if Path(f).exists():
            with Path(f).open(newline="") as fh:
                new += [{"date": day, "ticker": r["ticker"], "price_date": (r.get("price_date") or "")[:10], "price": r.get("price") or "",
                         "logged_at": at, "basis": "run_start"} for r in csv.DictReader(fh)
                        if r.get("date") == day and r.get("price") not in ("", None) and r.get("price_date")]
    return _merge(new, path)


def _merge(new: list[dict], path: Path | None = None) -> int:
    p = Path(path or TIMES)
    old = list(csv.DictReader(p.open(newline=""))) if p.exists() else []
    seen = {tuple(r[c] for c in COLS[:5]) for r in old}
    add = [r for r in new if tuple(str(r[c]) for c in COLS[:5]) not in seen]
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(old + add)
    _CACHE.clear()
    return len(add)


def backfill(runs_json: Path, path: Path | None = None, repo: Path = ROOT) -> dict:
    """Engangs: historikk fra git (hver commit av categories.csv / entry_prices.csv). Hver (date, ticker, price_date, price)
    får starttiden til nightly-kjøringen som laget commiten (createdAt ≤ commit ≤ updatedAt + 5 min); ellers commit-tid."""
    runs = [(_dt(r["createdAt"]), _dt(r["updatedAt"])) for r in json.loads(Path(runs_json).read_text())]
    out, n_commit = {}, 0
    for f in ("logs/categories.csv", "logs/entry_prices.csv"):
        log = subprocess.check_output(["git", "-C", str(repo), "log", "--reverse", "--format=%H %cI", "--", f], text=True).split("\n")
        for line in filter(None, log):
            h, ct = line.split()
            t = _dt(ct)
            st = [a for a, b in runs if a <= t <= b + timedelta(minutes=5)]
            at, basis = (max(st), "run_start") if st else (t, "commit")
            try:
                txt = subprocess.check_output(["git", "-C", str(repo), "show", f"{h}:{f}"], text=True)
            except subprocess.CalledProcessError:
                continue
            for r in csv.DictReader(txt.splitlines()):
                if not r.get("date") or not r.get("ticker") or r.get("price") in ("", None) or not r.get("price_date"):
                    continue
                try:
                    pv = str(float(r["price"]))
                except ValueError:
                    continue
                k = (r["date"], r["ticker"], r["price_date"][:10], pv)
                if k not in out:   # første gang verdien dukker opp = når den ble logget
                    out[k] = (at.astimezone(timezone.utc).isoformat(), basis)
                    n_commit += basis == "commit"
    rows = [{"date": k[0], "ticker": k[1], "price_date": k[2], "price": k[3], "logged_at": v[0], "basis": v[1]} for k, v in sorted(out.items())]
    _merge(rows, path)
    return {"rows": len(rows), "commit_basis": n_commit}
