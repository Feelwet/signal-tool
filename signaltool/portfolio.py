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


# AnalBot 02.11: handelsvaluta etter børssuffiks. Før 02.11 ble alt som ikke var USD regnet som NOK (NKT.CO er i DKK).
CCY_SUFFIX = {".CO": "DKK", ".ST": "SEK", ".HE": "EUR"}
FX_TICKERS = {"DKK": "DKKNOK=X", "SEK": "SEKNOK=X", "EUR": "EURNOK=X"}


def ccy(t: str) -> str:
    if is_us(t):
        return "USD"
    for suf, c in CCY_SUFFIX.items():
        if t.endswith(suf):
            return c
    return "NOK"


def _rate(cur: str, usdnok, fx: dict | None):
    """NOK per enhet valuta. None = ukjent (ingen fylling; verdi 0 og logget)."""
    if cur == "NOK":
        return 1.0
    if cur == "USD":
        return usdnok or None
    return (fx or {}).get(cur) or None


CORR = LOGS / "portfolio_corrections.csv"
K_COLS = ["date", "book_id", "order_id", "event", "ticker", "kind", "logged", "corrected", "fx", "fx_date", "note"]


def load_corrections(path: Path = CORR) -> dict:
    """{(book_id, order_id, event): {felt: korrigert verdi}} for kind=valuta. Handelsradene endres aldri; korreksjonene legges på."""
    out = {}
    for r in _read(path):
        if r.get("kind") == "valuta" and r.get("corrected"):
            try:
                out[(r["book_id"], r["order_id"], r["event"])] = json.loads(r["corrected"])
            except ValueError:
                pass
    return out


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


def state(trades: list[dict], corr: dict | None = None) -> dict:
    """Kontanter, åpne posisjoner, ventende ordre og lukkede handler fra loggen. `corr` = korreksjoner (load_corrections)."""
    cash, opn, pend, closed = RULES["start_nok"], {}, {}, []
    for r in trades:
        k = corr.get((r.get("rules_version"), r.get("order_id"), r.get("event"))) if corr else None
        if k:
            r = {**r, **{f: str(v) for f, v in k.items()}}
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


# AnalBot 02.11 (alle bøker): sluttkurs hentes for alle åpne posisjoner, også de som har falt ut av lista. Verdsetting til innkurs
# er ikke lov. Mangler kurs: siste markedskurs fra closes-loggen (aldri innkursen); finnes ingen, teller posisjonen 0 og dagen
# logges i price_missing. Posisjonen merkes «uten kurs» og selges første dag det finnes kurs, til den kursen. Salg kanselleres aldri.
CLOSES = LOGS / "portfolio_closes.csv"
C_COLS = ["date", "ticker", "close", "price_date", "source"]
MISSING = LOGS / "portfolio_price_missing.csv"
M_COLS = ["date", "book_id", "ticker", "status", "valued_at", "valued_from"]
NO_PRICE = "uten kurs"


def last_closes(path: Path = CLOSES) -> dict:
    """Siste loggede markedskurs per ticker: {ticker: (close, price_date)}. Bare markedskurser, aldri fill-/innkurs."""
    out = {}
    for r in sorted(_read(path), key=lambda r: (r["price_date"] or "", r["date"] or "")):
        c = _f(r["close"])
        if c:
            out[r["ticker"]] = (c, r["price_date"])
    return out


def _mark(t: str, by: dict, last: dict | None):
    """Kurs for verdsetting: dagens (snapshot/henting) eller siste loggede markedskurs. (kurs, kilde) – (None, '') = ingen kurs."""
    px, pdt = _px(by.get(t))
    if px:
        return px, "dagens"
    if last and t in last:
        return last[t][0], f"siste kjente {last[t][1]}"
    return None, ""


def _value(s: dict, by: dict, usdnok: float, last: dict | None = None, fx: dict | None = None) -> float:
    v = s["cash"]
    for t, p in s["open"].items():
        px, _ = _mark(t, by, last)
        v += p["shares"] * (px or 0.0) * (_rate(p["currency"], usdnok, fx) or 0.0)
    return v


def step(snap: dict, usdnok: float | None, bench: dict, trades_path: Path = TRADES, nav_path: Path = NAV,
         rules: dict = RULES, picks: list[dict] | None = None, extra: list[dict] | None = None, why_buy: str = "Kjøp",
         cols: list[str] = T_COLS, annotate=None, px_extra: dict | None = None, logs: Path | None = None,
         fx: dict | None = None) -> dict:
    """Én kjøring: fyll ventende ordre (sluttkurs dagen etter signalet), legg nye ordre, skriv NAV-rad.
    Standardverdiene = bok 1 (rules_v1, kjøp kun Kjøp). Andre bøker (portfolio_books.py) sender egne regler, ferdig valgte
    kandidater (`picks`, i rekkefølge), `extra` (tema-rader utenfor snapshot, for kurs og røde flagg), egne kolonner (`cols`) og
    `annotate(e)` -> dict med begrunnelse på kjøpsordren (signaldagen). Da logges også referanseindeksens nivå ved inngang (fill)."""
    RULES, RULES_VERSION = rules, rules["version"]   # lokale navn: bok 1 bruker de fryste rules_v1 uendret
    today = str(snap.get("date"))
    trades = _read(trades_path)
    corr = load_corrections(Path(logs or Path(nav_path).parent) / CORR.name)
    if any(r["run_date"] == today for r in trades) or any(r["date"] == today for r in _read(nav_path)):
        return state(trades, corr)                                # allerede kjørt i dag
    by = {e["ticker"]: e for e in snap.get("tickers", [])}
    for e in extra or []:
        by.setdefault(e["ticker"], e)
    s = state(trades, corr)
    logs = logs or Path(nav_path).parent
    cpath, mpath = logs / CLOSES.name, logs / MISSING.name
    held = set(s["open"]) | {o["ticker"] for o in s["pending"].values() if o["side"] == "sell"}
    for t, (c, d) in (px_extra or {}).items():   # utenfor lista: hentet sluttkurs (bare for åpne posisjoner / ventende salg)
        if t in held and t not in by and c:
            by[t] = {"ticker": t, "stats": {"close": c, "last_date": d}, "off_list": True}
    last = last_closes(cpath)
    new = []
    runs = sorted({r["date"] for r in _read(nav_path)})
    # 1) fyll ventende ordre
    for oid, o in list(s["pending"].items()):
        px, pdt = _px(by.get(o["ticker"]))
        cur = ccy(o["ticker"])                                       # valuta etter suffiks (ordreraden kunne før 02.11 si NOK for DKK)
        fxv = _rate(cur, usdnok, fx)
        if px and pdt and pdt > (o["price_date"] or "") and fxv:
            illq = o["reason"].endswith("illiquid")
            if o["side"] == "buy":
                if len(s["open"]) >= RULES["max_positions"] or o["ticker"] in s["open"]:
                    new.append({**o, "event": "cancel", "run_date": today, "reason": "full eller allerede eid"}); continue
                nok = RULES["position_pct"] * _value(s, by, usdnok or 0, last, fx)
                nok = min(nok, s["cash"] / (1 + _cost_rate(illq)))
                if nok <= 0:
                    new.append({**o, "event": "cancel", "run_date": today, "reason": "ingen kontanter"}); continue
                sh = nok / (px * fxv)
                r = {**o, "event": "fill", "run_date": today, "price_date": pdt, "price": px, "fx": fxv, "shares": round(sh, 6), "currency": cur,
                     "nok_value": round(nok, 2), "cost_nok": round(nok * _cost_rate(illq), 2)}
                if annotate:
                    r["bench_entry"] = (bench or {}).get("spx" if is_us(o["ticker"]) else "osebx")
            else:
                p = s["open"].get(o["ticker"])
                if not p:
                    new.append({**o, "event": "cancel", "run_date": today, "reason": "ingen posisjon"}); continue
                nok = p["shares"] * px * fxv
                cost = nok * _cost_rate(illq)
                fx_eff = p["shares"] * px * (fxv - p["fx"]) if p["currency"] != "NOK" else 0.0
                r = {**o, "event": "fill", "run_date": today, "price_date": pdt, "price": px, "fx": fxv, "shares": p["shares"],
                     "nok_value": round(nok, 2), "cost_nok": round(cost, 2), "fx_effect_nok": round(fx_eff, 2),
                     "pnl_nok": round(nok - cost - p["nok_cost"], 2)}
            new.append(r)
            s = state(trades + new, corr)
        elif o["side"] == "buy":                                      # salg kanselleres aldri (AnalBot 02.11): venter på første kurs
            n_runs = len([d for d in runs if d > o["run_date"]]) + 1
            if n_runs >= RULES["order_expiry_runs"]:
                new.append({**o, "event": "cancel", "run_date": today, "reason": "ingen kurs"})
                s = state(trades + new, corr)
    # 2) salgsordre for åpne posisjoner
    pend_t = {(o["ticker"], o["side"]) for o in s["pending"].values()}
    seq = len(trades) + len(new)
    def order(t, side, why, e):
        nonlocal seq
        seq += 1
        px, pdt = _px(e)
        illq = "illiquid" in ((e or {}).get("cat_flags") or {})
        row = {"rules_version": RULES_VERSION, "event": "order", "order_id": f"{today}-{seq:04d}", "run_date": today, "signal_date": today,
               "ticker": t, "side": side, "reason": why + (";illiquid" if illq else ""), "price_date": pdt or ("" if why == NO_PRICE else today),
               "currency": ccy(t)}
        if annotate and side == "buy":
            row.update(annotate(e))
            row["bench_signal"] = (bench or {}).get("spx" if is_us(t) else "osebx")
        return row
    for t, p in s["open"].items():
        if (t, "sell") in pend_t:
            continue
        e = by.get(t)
        _, pdt = _px(e)
        why = None
        if e is None and not RULES["sell_on_folg_or_lower"]:
            pdt = today                                               # ute av lista: holdetid telles mot kjøringsdatoen
        if RULES["sell_on_folg_or_lower"] and (e is None or e.get("category") not in ("kjop", "hold")):
            why = "under Hold"
        elif not _px(e)[0]:
            why = NO_PRICE                                            # ingen kurs i dag: selges første dag det finnes kurs
        elif (e or {}).get("cat_flags"):   # e er None når tickeren har falt ut av lista (bok 2/3); før 02.11 krasjet det her
            why = "rødt flagg"
        elif pdt and int(np.busday_count(p["date"], pdt)) >= RULES["hold_trading_days"]:
            why = f"{RULES['hold_trading_days']} handelsdager"
        if why:
            new.append(order(t, "sell", why, e or {"stats": {}}))
    # 3) kjøpsordre: Kjøp, ikke eid, ikke ventende, plass igjen
    slots = RULES["max_positions"] - len(s["open"]) - len([o for o in s["pending"].values() if o["side"] == "buy"])
    cands = sorted(snap.get("tickers", []), key=lambda x: -(x.get("score") or 0)) if picks is None else picks
    for e in cands:
        if slots <= 0:
            break
        t = e["ticker"]
        if (picks is not None or e.get("category") == RULES["buy_category"]) and t not in s["open"] and (t, "buy") not in pend_t:
            new.append(order(t, "buy", why_buy, e)); slots -= 1
    _append(trades_path, cols, new)
    s = state(trades + new, corr)
    # 4) NAV + vektet referanse
    nav = _value(s, by, usdnok or 0, last, fx)
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
    w_ose = sum(p["shares"] * (_mark(t, by, last)[0] or 0.0) * (_rate(p["currency"], usdnok, fx) or 0.0) for t, p in s["open"].items() if p["currency"] != "USD") / nav if nav else 0
    w_us = sum(p["shares"] * (_mark(t, by, last)[0] or 0.0) * (usdnok or 0) for t, p in s["open"].items() if p["currency"] == "USD") / nav if nav else 0
    # kurslogg (markedskurser for åpne posisjoner) + price_missing per dag
    seen = {(r["date"], r["ticker"]) for r in _read(cpath)}
    _append(cpath, C_COLS, [{"date": today, "ticker": t, "close": _px(by.get(t))[0], "price_date": _px(by.get(t))[1],
                             "source": "yahoo" if (by.get(t) or {}).get("off_list") else "snapshot"}
                            for t in s["open"] if _px(by.get(t))[0] and (today, t) not in seen])
    miss = []
    for t in sorted(set(s["open"]) | {o["ticker"] for o in s["pending"].values() if o["side"] == "sell"}):
        if not _px(by.get(t))[0]:
            v, src = _mark(t, by, last)
            miss.append({"date": today, "book_id": RULES_VERSION, "ticker": t, "status": "åpen" if t in s["open"] else "ventende salg",
                         "valued_at": v if v else "", "valued_from": src or "ingen kurs: teller 0"})
    _append(mpath, M_COLS, miss)
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


def fetch_fx() -> dict:
    """Dagskurs NOK per DKK/SEK/EUR (Yahoo, siste sluttkurs). Mangler = utelatt (ingen fylling i den valutaen den dagen)."""
    out = {}
    try:
        import yfinance as yf
        d = yf.download(sorted(FX_TICKERS.values()), period="10d", progress=False, auto_adjust=False)["Close"].ffill()
        for c, t in FX_TICKERS.items():
            v = _f(d[t].dropna().iloc[-1]) if t in d and len(d[t].dropna()) else None
            if v:
                out[c] = v
    except Exception as ex:
        log.warning("portfolio fx: %s", ex)
    return out


def fx_history(cur: str, day: str) -> tuple[float | None, str | None]:
    """Sluttkurs NOK per `cur` på `day` eller siste handelsdag før (Yahoo). Brukes til korreksjoner bakover."""
    try:
        import datetime as dt
        import yfinance as yf
        d0 = dt.date.fromisoformat(day[:10])
        h = yf.download(FX_TICKERS[cur], start=str(d0 - dt.timedelta(days=10)), end=str(d0 + dt.timedelta(days=1)),
                        progress=False, auto_adjust=False)["Close"]
        h = h.iloc[:, 0] if hasattr(h, "columns") else h
        h = h.dropna()
        return (float(h.iloc[-1]), str(h.index[-1])[:10]) if len(h) else (None, None)
    except Exception as ex:
        log.warning("fx history %s %s: %s", cur, day, ex)
        return None, None


def fetch_closes(tickers: list[str]) -> dict:
    """Siste sluttkurs (Yahoo, 1 mnd) for tickere utenfor dagens liste: {ticker: (close, 'YYYY-MM-DD')}. Mangler = utelatt."""
    out = {}
    if not tickers:
        return out
    try:
        import yfinance as yf
        d = yf.download(sorted(tickers), period="1mo", progress=False, auto_adjust=False)["Close"]
        if not hasattr(d, "columns"):
            d = d.to_frame(sorted(tickers)[0])
        for t in d.columns:
            ser = d[t].dropna()
            if len(ser):
                out[str(t)] = (float(ser.iloc[-1]), str(ser.index[-1])[:10])
    except Exception as ex:
        log.warning("portfolio closes: %s", ex)
    return out


def held_off_list(snap: dict, paths: list[Path]) -> list[str]:
    """Åpne posisjoner og ventende salg i alle bøkene som ikke er i dagens liste."""
    on = {e["ticker"] for e in snap.get("tickers", [])}
    out = set()
    for tp in paths:
        s = state(_read(tp))
        out |= set(s["open"]) | {o["ticker"] for o in s["pending"].values() if o["side"] == "sell"}
    return sorted(out - on)


def sync_logs_from_origin(logs: Path = LOGS, show=None) -> dict:
    """AnalBot 02.11: rett før papirbøkene kjøres hentes portfolio_*-loggene fra origin på nytt (en annen kjøring kan ha pushet
    samme dato i mellomtiden; 02.11 ble kontroll-boka overskrevet slik). Loggene er bare-tillegg: er lokal fil et prefiks av
    origin-versjonen, tas origin-versjonen; ellers beholdes lokal fil (konflikt logges). Bøker/datoer som da allerede finnes,
    hoppes over av step() («allerede kjørt»). `show(name) -> bytes | None` kan byttes ut i tester; standard er git i CI."""
    import os, subprocess
    if show is None:
        if not os.environ.get("GITHUB_ACTIONS"):
            return {"skipped": "ikke CI"}
        ref = os.environ.get("GITHUB_REF_NAME") or "master"
        subprocess.run(["git", "fetch", "-q", "origin", ref], check=True, timeout=180)
        names = subprocess.run(["git", "ls-tree", "--name-only", f"origin/{ref}", f"{logs.name}/"], capture_output=True, text=True,
                               check=True).stdout.split()

        def show(name):
            r = subprocess.run(["git", "show", f"origin/{ref}:{logs.name}/{name}"], capture_output=True)
            return r.stdout if r.returncode == 0 else None
        files = sorted({Path(n).name for n in names if Path(n).name.startswith("portfolio_")} |
                       {p.name for p in logs.glob("portfolio_*")})
    else:
        files = sorted({p.name for p in logs.glob("portfolio_*")} | set(getattr(show, "names", [])))
    out = {"updated": [], "same": [], "conflict": []}
    for name in files:
        o = show(name)
        if o is None:
            continue
        p = logs / name
        loc = p.read_bytes() if p.exists() else b""
        if o == loc:
            out["same"].append(name)
        elif o.startswith(loc):
            p.write_bytes(o)
            out["updated"].append(name)
        else:
            out["conflict"].append(name)
            log.warning("portfolio log %s: lokal fil er ikke et prefiks av origin – beholdes lokalt", name)
    return out


def run(snap: dict, status: dict) -> None:
    px_extra, fx = {}, {}
    try:
        sy = sync_logs_from_origin()
        print(f"Papirbøker: logger fra origin {sy}", flush=True)
    except Exception as ex:
        log.warning("portfolio log sync: %s", ex)
    try:
        from . import portfolio_books as PB
        px_extra = fetch_closes(held_off_list(snap, [TRADES] + [PB.paths(b)[0] for b in PB.BOOKS]))
    except Exception as ex:
        log.warning("portfolio off-list closes: %s", ex)
    try:
        usd, bench = fetch_market()
        fx = fetch_fx()
        try:
            from . import portfolio_books as PB
            PB.ensure_corrections(fx_hist=fx_history)
        except Exception as ex:
            log.warning("portfolio corrections: %s", ex)
        s = step(snap, usd, bench, px_extra=px_extra, fx=fx)
        status["Signal-boka (papirkonto)"] = f"ok ({len(s['open'])} åpne, {len(s['pending'])} ventende, {len(s['closed'])} lukket)"
    except Exception as ex:
        log.exception("portfolio failed")
        status["Signal-boka (papirkonto)"] = f"FAILED: {ex}"
    try:   # bok 2 (høy risiko, eksperimentell) + bok 3 (tilfeldig kontroll) – egne logger, påvirker aldri bok 1
        from . import portfolio_books
        portfolio_books.run(snap, status, usd, bench, px_extra=px_extra, fx=fx)
    except Exception as ex:
        log.exception("portfolio books failed")
        status["Papirbøker 2/3"] = f"FAILED: {ex}"


def summary(trades_path: Path = TRADES, nav_path: Path = NAV, rules: dict = RULES, name: str = "Signal-boka") -> dict:
    """JSON for siden. Ingen avkastningstall før RULES['min_closed_for_returns'] lukkede handler."""
    RULES, RULES_VERSION = rules, rules["version"]
    trades, navs = _read(trades_path), _read(nav_path)
    s = state(trades)
    n = len(s["closed"])
    show = n >= RULES["min_closed_for_returns"]
    out = {"name": name, "rules_version": RULES_VERSION, "rules": RULES, "start_nok": RULES["start_nok"],
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
