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


# AnalBot 11.11: linje i bokrapporten + forberedt «med/uten intradag-fills» (vises først fra 30 lukkede handler per bok).
FILTER_FROM = "11.11"          # sluttkursfilteret gjelder fra denne datoen; fills i loggen er alle fra før


def _pct1(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + " %"


def stats(path: Path = OUT) -> dict:
    """{book: {"n", "n_close", "mean_abs_pct"}} + "samlet". Leses fra loggen; ingenting hardkodet."""
    from .portfolio import _f
    with Path(path).open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for key, rs in [(b, [r for r in rows if r["book"] == b]) for b in dict.fromkeys(r["book"] for r in rows)] + [("samlet", rows)]:
        d = [abs(_f(r["diff_pct"])) for r in rs if _f(r.get("diff_pct")) is not None]
        out[key] = {"n": len(rs), "n_close": len(d), "mean_abs_pct": sum(d) / len(d) if d else None}
    return out


def line(st: dict) -> str:
    a = "–" if st["mean_abs_pct"] is None else _pct1(st["mean_abs_pct"])
    return f"{st['n']} fills før {FILTER_FROM} på intradag-kurs, snitt absolutt avvik {a}"


def report_lines(path: Path = OUT) -> list[str]:
    """Én linje per bok med intradag-fills, pluss samlet."""
    st = stats(path)
    from .testbooks_page import BOOK_TITLES
    return [f"{BOOK_TITLES.get(k, k) if k != 'samlet' else 'Samlet'}: {line(v)}" for k, v in st.items()]


def _drop_intraday(trades: list[dict], ids: set) -> list[dict]:
    """Handlene uten posisjonene som har en intradag-fill (kjøp eller salg): hele rundturen tas ut, som om den ikke fantes."""
    drop, open_ = set(), {}
    for i, r in enumerate(trades):
        if r["event"] != "fill":
            continue
        if r["side"] == "buy":
            open_[r["ticker"]] = [i]
            if r["order_id"] in ids:
                open_[r["ticker"]].append("x")
        else:
            rt = open_.pop(r["ticker"], [])
            if "x" in rt or r["order_id"] in ids:
                drop.update(j for j in rt if j != "x")
                drop.add(i)
    for rt in open_.values():
        if "x" in rt:
            drop.update(j for j in rt if j != "x")
    oids = {trades[i]["order_id"] for i in drop}
    return [r for i, r in enumerate(trades) if i not in drop and r["order_id"] not in oids]


def with_without(book: str, logs: Path = LOGS, path: Path = OUT, usdnok=None, fx=None) -> dict | None:
    """Avkastning med og uten intradag-fillene. None (skjult) til boka har min_closed_for_returns lukkede handler."""
    from . import portfolio as P, portfolio_books as PB
    rules = P.RULES if book == "rules_v1" else PB.BOOKS[book]
    tp = logs / P.TRADES.name if book == "rules_v1" else PB.paths(book, logs)[0]
    trades = P._read(tp)
    corr, last = P.load_corrections(logs / P.CORR.name), P.last_closes(logs / P.CLOSES.name)
    if len(P.state(trades, corr)["closed"]) < rules["min_closed_for_returns"]:
        return None
    with Path(path).open(newline="") as fh:
        ids = {r["order_id"] for r in csv.DictReader(fh) if r["book"] == book}
    out = {}
    for k, tr in (("med", trades), ("uten", _drop_intraday(trades, ids))):
        s = P.state(tr, corr)
        val = sum(p["shares"] * (last.get(t, (0.0, None))[0] or 0.0) * (P._rate(p["currency"], usdnok, fx) or 0.0) for t, p in s["open"].items())
        nav = s["cash"] + val
        out[k] = {"closed": len(s["closed"]), "nav_est": round(nav, 2), "total_pct": nav / rules["start_nok"] - 1}
    out["line"] = f"Avkastning med intradag-fills {_pct1(out['med']['total_pct'])}, uten {_pct1(out['uten']['total_pct'])}"
    return out


if __name__ == "__main__":
    print("\n".join(report_lines()))
