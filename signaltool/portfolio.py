"""«Signal-boka»: papirkonto etter fryste regler (portfolio_rules.py).

Logg (append-only, rules_version på hver rad):
  logs/portfolio_trades.csv – event=order skrives når signalet kommer (uten kurs); event=fill legges til ved neste
                              kjøring med sluttkursen dagen etter; event=cancel hvis ordren aldri får kurs.
  logs/portfolio_nav.csv    – én rad per kjøring: kontoverdi, kontanter, referanseindeks (OSEBX/S&P 500 vektet etter beholdning).
All tilstand rekonstrueres fra loggene. Avkastning vises ikke før 30 lukkede handler."""
from __future__ import annotations

import csv, json, logging
from datetime import date
from pathlib import Path

import numpy as np

from .config import LOGS
from .portfolio_rules import RULES, RULES_VERSION

log = logging.getLogger(__name__)
TRADES = LOGS / "portfolio_trades.csv"
NAV = LOGS / "portfolio_nav.csv"
T_COLS = ["rules_version", "event", "order_id", "run_date", "signal_date", "ticker", "side", "reason", "price_date", "price",
          "currency", "fx", "shares", "nok_value", "cost_nok", "fx_effect_nok", "pnl_nok"]
N_COLS = ["rules_version", "date", "nav", "cash", "n_open", "usdnok", "osebx", "spx", "w_ose", "w_us", "bench_index"]


def is_us(t: str) -> bool:
    return "." not in t and not t.startswith("^") and "=" not in t


def _read(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(newline="") as f:
        return list(csv.DictReader(f))


def _append(p: Path, cols: list[str], rows: list[dict]) -> None:
    """Bare tillegg – eksisterende rader røres aldri."""
    if not rows:
        return
    new = not p.exists() or p.stat().st_size == 0
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def state(trades: list[dict]) -> dict:
    """Kontanter, åpne posisjoner, ventende ordre og lukkede handler fra loggen."""
    cash, opn, pend, closed = RULES["start_nok"], {}, {}, []
    for r in trades:
        ev, oid, t = r["event"], r["order_id"], r["ticker"]
        if ev == "order":
            pend[oid] = r
        elif ev == "cancel":
            pend.pop(oid, None)
        elif ev == "fill":
            pend.pop(oid, None)
            v, c = _f(r["nok_value"]) or 0.0, _f(r["cost_nok"]) or 0.0
            if r["side"] == "buy":
                cash -= v + c
                opn[t] = {"ticker": t, "shares": _f(r["shares"]), "price": _f(r["price"]), "fx": _f(r["fx"]) or 1.0,
                          "nok_cost": v + c, "date": r["price_date"], "currency": r["currency"]}
            else:
                cash += v - c
                p = opn.pop(t, None)
                closed.append({"ticker": t, "pnl_nok": _f(r["pnl_nok"]), "fx_effect_nok": _f(r["fx_effect_nok"]),
                               "entry": p["date"] if p else None, "exit": r["price_date"], "reason": r["reason"]})
    return {"cash": cash, "open": opn, "pending": pend, "closed": closed}


def _cost_rate(illiquid: bool) -> float:
    return RULES["cost_each_way_illiquid"] if illiquid else RULES["cost_each_way"]


def _px(e: dict | None):
    st = (e or {}).get("stats") or {}
    return _f(st.get("close")), st.get("last_date")


def _value(s: dict, by: dict, usdnok: float) -> float:
    v = s["cash"]
    for t, p in s["open"].items():
        px, _ = _px(by.get(t))
        v += p["shares"] * (px or p["price"]) * (usdnok if p["currency"] == "USD" else 1.0)
    return v


def step(snap: dict, usdnok: float | None, bench: dict, trades_path: Path = TRADES, nav_path: Path = NAV) -> dict:
    """Én kjøring: fyll ventende ordre (sluttkurs dagen etter signalet), legg nye ordre, skriv NAV-rad."""
    today = str(snap.get("date"))
    trades = _read(trades_path)
    if any(r["run_date"] == today for r in trades) or any(r["date"] == today for r in _read(nav_path)):
        return state(trades)                                      # allerede kjørt i dag
    by = {e["ticker"]: e for e in snap.get("tickers", [])}
    s = state(trades)
    new = []
    runs = sorted({r["date"] for r in _read(nav_path)})
    # 1) fyll ventende ordre
    for oid, o in list(s["pending"].items()):
        px, pdt = _px(by.get(o["ticker"]))
        fxv = usdnok if is_us(o["ticker"]) else 1.0
        if px and pdt and pdt > (o["price_date"] or "") and fxv:
            illq = o["reason"].endswith("illiquid")
            if o["side"] == "buy":
                if len(s["open"]) >= RULES["max_positions"] or o["ticker"] in s["open"]:
                    new.append({**o, "event": "cancel", "run_date": today, "reason": "full eller allerede eid"}); continue
                nok = RULES["position_pct"] * _value(s, by, usdnok or 0)
                nok = min(nok, s["cash"] / (1 + _cost_rate(illq)))
                if nok <= 0:
                    new.append({**o, "event": "cancel", "run_date": today, "reason": "ingen kontanter"}); continue
                sh = nok / (px * fxv)
                r = {**o, "event": "fill", "run_date": today, "price_date": pdt, "price": px, "fx": fxv, "shares": round(sh, 6),
                     "nok_value": round(nok, 2), "cost_nok": round(nok * _cost_rate(illq), 2)}
            else:
                p = s["open"].get(o["ticker"])
                if not p:
                    new.append({**o, "event": "cancel", "run_date": today, "reason": "ingen posisjon"}); continue
                nok = p["shares"] * px * fxv
                cost = nok * _cost_rate(illq)
                fx_eff = p["shares"] * px * (fxv - p["fx"]) if p["currency"] == "USD" else 0.0
                r = {**o, "event": "fill", "run_date": today, "price_date": pdt, "price": px, "fx": fxv, "shares": p["shares"],
                     "nok_value": round(nok, 2), "cost_nok": round(cost, 2), "fx_effect_nok": round(fx_eff, 2),
                     "pnl_nok": round(nok - cost - p["nok_cost"], 2)}
            new.append(r)
            s = state(trades + new)
        else:
            n_runs = len([d for d in runs if d > o["run_date"]]) + 1
            if n_runs >= RULES["order_expiry_runs"]:
                new.append({**o, "event": "cancel", "run_date": today, "reason": "ingen kurs"})
                s = state(trades + new)
    # 2) salgsordre for åpne posisjoner
    pend_t = {(o["ticker"], o["side"]) for o in s["pending"].values()}
    seq = len(trades) + len(new)
    def order(t, side, why, e):
        nonlocal seq
        seq += 1
        px, pdt = _px(e)
        illq = "illiquid" in ((e or {}).get("cat_flags") or {})
        return {"rules_version": RULES_VERSION, "event": "order", "order_id": f"{today}-{seq:04d}", "run_date": today, "signal_date": today,
                "ticker": t, "side": side, "reason": why + (";illiquid" if illq else ""), "price_date": pdt or today,
                "currency": "USD" if is_us(t) else "NOK"}
    for t, p in s["open"].items():
        if (t, "sell") in pend_t:
            continue
        e = by.get(t)
        _, pdt = _px(e)
        why = None
        if e is None or e.get("category") not in ("kjop", "hold"):
            why = "under Hold"
        elif e.get("cat_flags"):
            why = "rødt flagg"
        elif pdt and int(np.busday_count(p["date"], pdt)) >= RULES["hold_trading_days"]:
            why = "60 handelsdager"
        if why:
            new.append(order(t, "sell", why, e or {"stats": {}}))
    # 3) kjøpsordre: Kjøp, ikke eid, ikke ventende, plass igjen
    slots = RULES["max_positions"] - len(s["open"]) - len([o for o in s["pending"].values() if o["side"] == "buy"])
    for e in sorted(snap.get("tickers", []), key=lambda x: -(x.get("score") or 0)):
        if slots <= 0:
            break
        t = e["ticker"]
        if e.get("category") == RULES["buy_category"] and t not in s["open"] and (t, "buy") not in pend_t:
            new.append(order(t, "buy", "Kjøp", e)); slots -= 1
    _append(trades_path, T_COLS, new)
    s = state(trades + new)
    # 4) NAV + vektet referanse
    nav = _value(s, by, usdnok or 0)
    prev = (_read(nav_path) or [None])[-1]
    bi = 100.0
    if prev:
        bi = _f(prev["bench_index"]) or 100.0
        r = 0.0
        for k, w in (("osebx", "w_ose"), ("spx", "w_us")):
            a, b = _f(prev.get(k)), _f(bench.get(k))
            if a and b and _f(prev.get(w)):
                r += _f(prev[w]) * (b / a - 1)
        bi *= 1 + r
    w_ose = sum(p["shares"] * (_px(by.get(t))[0] or p["price"]) for t, p in s["open"].items() if p["currency"] != "USD") / nav if nav else 0
    w_us = sum(p["shares"] * (_px(by.get(t))[0] or p["price"]) * (usdnok or 0) for t, p in s["open"].items() if p["currency"] == "USD") / nav if nav else 0
    _append(nav_path, N_COLS, [{"rules_version": RULES_VERSION, "date": today, "nav": round(nav, 2), "cash": round(s["cash"], 2),
                                "n_open": len(s["open"]), "usdnok": usdnok, "osebx": bench.get("osebx"), "spx": bench.get("spx"),
                                "w_ose": round(w_ose, 4), "w_us": round(w_us, 4), "bench_index": round(bi, 4)}])
    return s


def fetch_market() -> tuple[float | None, dict]:
    import yfinance as yf
    out = {}
    try:
        d = yf.download(["NOK=X", "OSEBX.OL", "^GSPC"], period="10d", progress=False, auto_adjust=False)["Close"].ffill()
        last = d.iloc[-1]
        usd = _f(last.get("NOK=X"))
        out = {"osebx": _f(last.get("OSEBX.OL")), "spx": _f(last.get("^GSPC"))}
        return usd, out
    except Exception as ex:
        log.warning("portfolio market data: %s", ex)
        return None, out


def run(snap: dict, status: dict) -> None:
    try:
        usd, bench = fetch_market()
        s = step(snap, usd, bench)
        status["Signal-boka (papirkonto)"] = f"ok ({len(s['open'])} åpne, {len(s['pending'])} ventende, {len(s['closed'])} lukket)"
    except Exception as ex:
        log.exception("portfolio failed")
        status["Signal-boka (papirkonto)"] = f"FAILED: {ex}"


def summary(trades_path: Path = TRADES, nav_path: Path = NAV) -> dict:
    """JSON for siden. Ingen avkastningstall før RULES['min_closed_for_returns'] lukkede handler."""
    trades, navs = _read(trades_path), _read(nav_path)
    s = state(trades)
    n = len(s["closed"])
    show = n >= RULES["min_closed_for_returns"]
    out = {"name": "Signal-boka", "rules_version": RULES_VERSION, "rules": RULES, "start_nok": RULES["start_nok"],
           "closed_trades": n, "open_positions": [{"ticker": p["ticker"], "since": p["date"], "currency": p["currency"]} for p in s["open"].values()],
           "pending_orders": [{"ticker": o["ticker"], "side": o["side"], "signal_date": o["signal_date"], "reason": o["reason"]} for o in s["pending"].values()],
           "as_of": navs[-1]["date"] if navs else None, "returns_visible": show,
           "returns_note": None if show else f"Avkastning vises fra {RULES['min_closed_for_returns']} lukkede handler ({n} så langt)."}
    if show and navs:
        nav, bi = _f(navs[-1]["nav"]), _f(navs[-1]["bench_index"])
        wins = [c for c in s["closed"] if (c["pnl_nok"] or 0) > 0]
        out["returns"] = {"nav": nav, "total_pct": nav / RULES["start_nok"] - 1, "bench_pct": bi / 100 - 1,
                          "fx_effect_nok": sum(c["fx_effect_nok"] or 0 for c in s["closed"]), "hit_rate": len(wins) / n,
                          "nav_series": [[r["date"], _f(r["nav"]), _f(r["bench_index"])] for r in navs]}
    return out


def write_json(path: Path) -> None:
    path.write_text(json.dumps(summary(), ensure_ascii=False, default=str))
