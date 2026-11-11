"""AnalBot 11.11: en kurs logget før børsens stengetid + 30 min (børsens egen tidssone, ZoneInfo – samme logikk som
displayprices.exchange_close / laering_fwd.day_closed) er IKKE en sluttkurs. Gjelder innkurs-valget i Siden-raden og punktet.

logs/price_log_times.csv (date, ticker, price_date, price, logged_at, basis): når hver logget verdi (categories.csv og
innkurs-sideloggen) ble logget.
- basis=run_start: starttidspunktet for kjøringen som logget raden. Fra 11.11 skriver pipeline dette selv (snap["generated"],
  Oslo-tid, før kursene hentes). Historikk: GitHub-kjøringen (nightly.yml) som laget loggcommiten, createdAt. Starttid er en
  nedre grense for når kursen ble hentet, så «etter stengetid» er aldri overvurdert.
- basis=commit: ingen kjøring funnet rundt commiten; commit-tid (øvre grense) – rapporteres som usikker.
Valg: for (ticker, price_date) vinner den SISTE verdien logget etter stengetid + 30 min. Ingen slik verdi -> datoen brukes
ikke; fallback = neste gyldige sluttkurs (minste senere price_date med en gyldig verdi, siste gyldige verdi for den datoen).
Ukjent børs (ikke i CLOSE-tabellen): aldri gyldig (samme regel som day_closed)."""
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


def close_for(times: dict, ticker: str, price_date: str):
    """Siste verdi for (ticker, price_date) logget etter stengetid + 30 min, ellers None."""
    ok = [v for d, v, at, _ in times.get(ticker, []) if d == price_date and is_close(ticker, d, at)]
    return ok[-1] if ok else None


def entry(times: dict, ticker: str, price_date: str | None):
    """(price_date, innkurs) for innkurs-valget, eller (None, None). Fallback: neste gyldige sluttkurs."""
    if not price_date:
        return None, None
    v = close_for(times, ticker, price_date)
    if v is not None:
        return price_date, v
    later = sorted({d for d, _, _, _ in times.get(ticker, []) if d > price_date})
    for d in later:
        v = close_for(times, ticker, d)
        if v is not None:
            return d, v
    return None, None


def from_rows(rows: list[dict], logged_at: str = "2099-01-01T00:00:00+00:00") -> dict:
    """Tidsstempel-oppslag for gitte rader (tester/syntetiske logger): alle regnes som logget på `logged_at`."""
    out: dict = {}
    for r in rows:
        try:
            out.setdefault(r["ticker"], []).append(((r.get("price_date") or "")[:10], float(r["price"]), logged_at, r["date"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out


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
