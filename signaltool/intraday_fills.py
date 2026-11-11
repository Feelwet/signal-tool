"""AnalBot 11.11: papirhandler som ble fylt til intradagkurs (før børsens stengetid + 30 min). Rettes IKKE bakover; bare logget
i logs/intraday_fills.csv (privat, vises ikke på siden).

Kolonner: book, order_id, ticker, side, fill_date (price_date), fill_time (starten på kjøringen som skrev fillen), fill_price,
close (Yahoo-sluttkurs samme dato fra dagshistorikken, bare når stengetid + 30 har passert; ellers tom), diff_pct
(fill/close − 1), diff_nok (aksjer × (fill − close) × fx; positivt = fillen var dyrere enn sluttkursen).
fill_time: GitHub-kjøringen (nightly.yml) som laget commiten der fill-raden først dukket opp (createdAt = kjøringens start,
nedre grense for når kursen ble hentet); uten slik kjøring: commit-tid (basis=commit)."""
from __future__ import annotations

import csv
import json
import subprocess
from datetime import timedelta
from pathlib import Path

from .config import LOGS, ROOT

OUT = LOGS / "intraday_fills.csv"
COLS = ["book", "order_id", "ticker", "side", "fill_date", "fill_time", "basis", "fill_price", "close", "diff_pct", "diff_nok"]


def books() -> dict[str, Path]:
    from . import portfolio as P, portfolio_books as PB
    out = {"rules_v1": P.TRADES}
    for b in PB.BOOKS:
        out[b] = PB.paths(b)[0]
    return out


def _first_seen(path: Path, runs: list, repo: Path = ROOT) -> dict:
    """{(order_id, event): (tid, basis)} – første commit der raden finnes, tid = starten på kjøringen som laget commiten."""
    from .close_valid import _dt
    rel = str(Path(path).resolve().relative_to(Path(repo).resolve()))
    log = subprocess.check_output(["git", "-C", str(repo), "log", "--reverse", "--format=%H %cI", "--", rel], text=True).split("\n")
    out = {}
    for line in filter(None, log):
        h, ct = line.split()
        t = _dt(ct)
        st = [a for a, b in runs if a <= t <= b + timedelta(minutes=5)]
        at, basis = (max(st), "run_start") if st else (t, "commit")
        try:
            txt = subprocess.check_output(["git", "-C", str(repo), "show", f"{h}:{rel}"], text=True)
        except subprocess.CalledProcessError:
            continue
        for r in csv.DictReader(txt.splitlines()):
            k = (r.get("order_id"), r.get("event"))
            if r.get("event") == "fill" and k not in out:
                out[k] = (at, basis)
    return out


def build(runs_json: Path, hist=None, out: Path = OUT, now=None) -> dict:
    from . import closedbars as CB
    from .close_valid import _dt, is_close
    from .portfolio import _read, _f
    runs = [(_dt(r["createdAt"]), _dt(r["updatedAt"])) for r in json.loads(Path(runs_json).read_text())]
    rows, need = [], set()
    for book, tp in books().items():
        seen = _first_seen(tp, runs)
        for r in _read(tp):
            if r.get("event") != "fill":
                continue
            at, basis = seen.get((r["order_id"], "fill"), (None, ""))
            if at is None:
                continue
            if is_close(r["ticker"], r["price_date"], at):
                continue          # fylt etter stengetid + 30: sluttkurs, ikke med
            rows.append({"book": book, "order_id": r["order_id"], "ticker": r["ticker"], "side": r["side"], "fill_date": r["price_date"],
                         "fill_time": at.isoformat(), "basis": basis, "fill_price": r["price"], "_sh": _f(r["shares"]), "_fx": _f(r["fx"]) or 1.0})
            need.add(r["ticker"])
    h = hist(sorted(need)) if hist else _hist(sorted(need))
    for x in rows:
        ser = CB.series(h.get(x["ticker"]) or {}, x["ticker"], now)
        c = ser.get(x["fill_date"])
        f = _f(x["fill_price"])
        x["close"] = round(c, 4) if c else ""
        x["diff_pct"] = round(f / c - 1, 6) if c and f else ""
        x["diff_nok"] = round((x["_sh"] or 0) * (f - c) * x["_fx"], 2) if c and f else ""
    with Path(out).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    by = {}
    for x in rows:
        b = by.setdefault(x["book"], {"n": 0, "n_close": 0, "sum_diff_nok": 0.0, "sum_abs_diff_nok": 0.0})
        b["n"] += 1
        if x["diff_nok"] != "":
            b["n_close"] += 1
            b["sum_diff_nok"] = round(b["sum_diff_nok"] + x["diff_nok"], 2)
            b["sum_abs_diff_nok"] = round(b["sum_abs_diff_nok"] + abs(x["diff_nok"]), 2)
    return by


def _hist(tickers: list[str]) -> dict:
    import yfinance as yf
    out = {}
    if not tickers:
        return out
    d = yf.download(tickers, start="2026-09-20", progress=False, auto_adjust=False)["Close"]
    if not hasattr(d, "columns"):
        d = d.to_frame(tickers[0])
    for t in d.columns:
        s = d[t].dropna()
        out[str(t)] = {str(k)[:10]: float(v) for k, v in s.items()}
    return out
