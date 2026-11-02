"""Papirbok 2 og 3 ved siden av «Signal-boka» (bok 1, rules_v1 – uendret). Kun simulert, ingen ekte handler.

Bok 2 `hoy_risiko_v1` (EKSPERIMENTELL, AnalBots låste spek 29.10): hver natt kandidater = topp 10 etter score blant Følg (watch)
og Hold der 20-dagers avkastning > 0 (Tema er ute: ingen score/20d-avkastning). Holdetid 20 handelsdager; ellers rules_v1-mekanikk (neste sluttkurs, 5 % av
bokverdi, maks 20 åpne, salg ved rødt flagg, kostnad 0,2 %/0,5 % illikvid). Ingen salg på kategori.
Bok 3 `kontroll_tilfeldig_v1`: samme antall kandidater som bok 2 samme dag, trukket tilfeldig fra NØYAKTIG samme univers
som bok 2 velger fra (Følg/Hold, score, 20d > 0) med deterministisk seed per dato. Samme mekanikk som bok 2.
Bok 2 teller bare hvis den slår bok 3. Resultater vises ikke før 30 lukkede handler per bok (bøkene er ikke på siden ennå).

Logger (samme format som bok 1, egne filer – eksisterende lesere/tester av bok 1 røres ikke):
  logs/portfolio_<bok>_trades.csv, logs/portfolio_<bok>_nav.csv  (rules_version-kolonnen = bok-id)
  logs/portfolio_candidates.csv – én rad per bok og dato: seed, universstørrelse, antall og tickere."""
from __future__ import annotations

import csv, hashlib, logging, random
from pathlib import Path

from .config import LOGS
from .portfolio_rules import RULES
from . import portfolio as P

log = logging.getLogger(__name__)

UNIVERSE_CATS = ("watch", "hold")
HOY = {**RULES, "version": "hoy_risiko_v1", "experimental": True, "buy_category": None,
       "selection": "topp 10 etter score blant Følg/Hold med 20d-avkastning > 0 (Tema ute)", "top_n": 10,
       "hold_trading_days": 20, "sell_on_folg_or_lower": False}
KONTROLL = {**HOY, "version": "kontroll_tilfeldig_v1", "experimental": True,
            "selection": "tilfeldig fra hoy_risiko_v1-universet (Følg/Hold, score, 20d > 0), samme antall samme dag, seed per dato"}
BOOKS = {"hoy_risiko_v1": HOY, "kontroll_tilfeldig_v1": KONTROLL}
# Bok 2/3: samme kolonner som portfolio_trades.csv + begrunnelse på kjøpsrader (AnalBot 29.10). Tomt felt = ikke tilgjengelig.
# bench_signal = indeksnivå ved signal (ordre), bench_entry = indeksnivå ved inngang (fill, samme kjøring som sluttkursen).
WHY_COLS = ["score", "signal_types", "risk_level", "risk_date", "sector", "category", "ret_20d", "bench", "bench_signal", "bench_entry"]
B_COLS = P.T_COLS + WHY_COLS
CANDS = LOGS / "portfolio_candidates.csv"
C_COLS = ["date", "book_id", "seed", "universe_n", "n", "tickers"]


def paths(book: str, logs: Path = LOGS) -> tuple[Path, Path]:
    return logs / f"portfolio_{book}_trades.csv", logs / f"portfolio_{book}_nav.csv"


def universe(snap: dict) -> list[dict]:
    """Felles univers for bok 2 og 3 (AnalBot 29.10): Følg/Hold med score og 20d-avkastning > 0. Tema er ute av begge bøkene."""
    return [e for e in snap.get("tickers", []) if e.get("category") in UNIVERSE_CATS and e.get("score") is not None
            and ((e.get("stats") or {}).get("ret_20d") or 0) > 0]


def hoy_candidates(univ: list[dict], n: int = HOY["top_n"]) -> list[dict]:
    """Topp n etter score i universet (filteret sjekkes på nytt, så funksjonen er trygg også på rå lister)."""
    ok = [e for e in univ if e.get("category") in UNIVERSE_CATS and e.get("score") is not None
          and ((e.get("stats") or {}).get("ret_20d") or 0) > 0]
    return sorted(ok, key=lambda e: (-e["score"], e["ticker"]))[:n]


def seed_for(day: str, book: str = "kontroll_tilfeldig_v1") -> int:
    return int(hashlib.sha256(f"{book}:{day}".encode()).hexdigest()[:8], 16)


def control_candidates(univ: list[dict], n: int, day: str) -> tuple[list[dict], int]:
    seed = seed_for(day)
    pool = sorted(univ, key=lambda e: e["ticker"])   # samme univers som bok 2 (universe())
    return random.Random(seed).sample(pool, min(n, len(pool))), seed


def risk_levels() -> dict:
    """Siste ukentlige risikonivå fra cache (risk.py kjører etter papirbøkene i pipelinen). Leses bare."""
    import json
    from .risk import CPATH
    try:
        return json.loads(CPATH.read_text()).get("levels", {}) if CPATH.exists() else {}
    except Exception:
        return {}


def annotator(levels: dict):
    def why(e: dict) -> dict:
        st = (e or {}).get("stats") or {}
        return {"score": e.get("score"), "signal_types": "|".join(sorted(e.get("cat_types") or {})),
                "risk_level": (levels.get(e["ticker"]) or {}).get("level"),
                "risk_date": (levels.get(e["ticker"]) or {}).get("date"), "sector": (e.get("decision") or {}).get("sector"),
                "category": e.get("category"), "ret_20d": st.get("ret_20d"),
                "bench": "S&P 500 (^GSPC)" if P.is_us(e["ticker"]) else "OSEBX (OSEBX.OL)"}
    return why


def _log_cands(path: Path, row: dict) -> None:
    rows = list(csv.DictReader(path.open(newline=""))) if path.exists() else []
    if any(r["date"] == row["date"] and r["book_id"] == row["book_id"] for r in rows):
        return
    P._append(path, C_COLS, [row])


def run(snap: dict, status: dict, usd, bench, logs: Path = LOGS, px_extra: dict | None = None, fx: dict | None = None) -> dict:
    day = str(snap.get("date"))
    univ = universe(snap)
    hoy = hoy_candidates(univ)
    ctl, seed = control_candidates(univ, len(hoy), day)
    why_fn = annotator(risk_levels())
    out = {}
    for book, picks, why, sd in (("hoy_risiko_v1", hoy, "topp10 20d>0", ""), ("kontroll_tilfeldig_v1", ctl, f"tilfeldig seed={seed}", seed)):
        tp, npth = paths(book, logs)
        ran = any(r["date"] == day for r in P._read(npth))
        s = P.step(snap, usd, bench, tp, npth, rules=BOOKS[book], picks=picks, why_buy=why,
                   cols=B_COLS, annotate=why_fn, px_extra=px_extra, logs=logs, fx=fx)
        if not ran:   # 02.11: kandidatraden skrives først etter at steget har gått (morgenkjøringen 02.11 krasjet etter å ha logget)
            _log_cands(logs / CANDS.name, {"date": day, "book_id": book, "seed": sd, "universe_n": len(univ), "n": len(picks),
                                           "tickers": "|".join(e["ticker"] for e in picks)})
        out[book] = s
        status[f"Papirbok {book}"] = (f"ok ({len(picks)} kandidater i dag, {len(s['open'])} åpne, {len(s['pending'])} ventende, "
                                      f"{len(s['closed'])} lukket)" + (" – allerede kjørt i dag" if ran else ""))
        log.info("papirbok %s %s: %d kandidater [%s]%s", book, day, len(picks), ",".join(e["ticker"] for e in picks),
                 f" seed={seed}" if sd != "" else "")
        print(f"Papirbok {book} {day}: {len(picks)} kandidater [{','.join(e['ticker'] for e in picks)}]"
              + (f" seed={seed}" if sd != "" else "") + (" (allerede kjørt i dag)" if ran else ""), flush=True)
    log_late_fills(logs)
    return out


DEV = LOGS / "portfolio_deviations.csv"
D_COLS = ["date", "book_id", "kind", "order_id", "ticker", "side", "order_run", "fill_run", "missed_runs", "n_missed", "note"]


def log_late_fills(logs: Path = LOGS) -> list[dict]:
    """Avvik (AnalBot 02.11): fill som kom senere enn neste kjøring fordi boka manglet kjøringer som de andre bøkene hadde.
    Leses fra loggene (idempotent, også i etterkant). Kjøringene fylles aldri inn."""
    navs = {b: [r["date"] for r in P._read(paths(b, logs)[1])] for b in BOOKS}
    navs["rules_v1"] = [r["date"] for r in P._read(logs / P.NAV.name)]
    runs = sorted({d for v in navs.values() for d in v})
    path = logs / DEV.name
    have = {(r["book_id"], r["order_id"], r["kind"]) for r in P._read(path)}
    new = []
    for b in BOOKS:
        own = set(navs[b])
        for r in P._read(paths(b, logs)[0]):
            if r["event"] != "fill":
                continue
            miss = [d for d in runs if r["signal_date"] < d < r["run_date"] and d not in own]
            if miss and (b, r["order_id"], "sen_fylling") not in have:
                new.append({"date": r["run_date"], "book_id": b, "kind": "sen_fylling", "order_id": r["order_id"], "ticker": r["ticker"],
                            "side": r["side"], "order_run": r["signal_date"], "fill_run": r["run_date"], "missed_runs": "|".join(miss),
                            "n_missed": len(miss), "note": f"fylt {len(miss)} kjøringer for sent (boka manglet kjøring; dagene fylles ikke inn)"})
                have.add((b, r["order_id"], "sen_fylling"))
    for r in STATIC_DEVIATIONS:
        if (r["book_id"], r["order_id"], r["kind"]) not in have:
            new.append(r); have.add((r["book_id"], r["order_id"], r["kind"]))
    P._append(path, D_COLS, new)
    return new


# Faste avviksrader (AnalBot 02.11). Skrives én gang (idempotent); eksisterende rader endres aldri.
STATIC_DEVIATIONS = [
    {"date": "2026-11-02", "book_id": "kontroll_tilfeldig_v1", "kind": "overskrevet_kjoring", "order_id": "run-2026-11-02",
     "ticker": "", "side": "", "order_run": "2026-11-02", "fill_run": "2026-11-02", "missed_runs": "", "n_missed": "",
     "note": ("Kjøringen 2026-11-02 ble regnet to ganger: run 41442171788 (logger i c5852bb: NAV 1000100.7, 11 åpne, nye ordre "
              "2026-11-02-0041..0044 BRG.OL|GD|KOG.OL|TEKNA.OL) ble overskrevet av run 41443441078 (2bba4c5: NAV 1000737.51, 10 åpne, "
              "ordre 2026-11-02-0042..0046). Den andre hentet koden før den første hadde pushet loggene, og loggene kopieres hele. "
              "2bba4c5-versjonen gjelder. Rettet: loggene hentes fra origin rett før papirbøkene kjøres.")},
    {"date": "2026-11-02", "book_id": "kontroll_tilfeldig_v1", "kind": "kandidatlogg_avvik", "order_id": "cands-2026-11-02",
     "ticker": "BRG.OL|GD|KOG.OL|TECH.OL|NCLH", "side": "buy", "order_run": "2026-11-02", "fill_run": "", "missed_runs": "", "n_missed": "",
     "note": ("Kandidatraden 2026-11-02 i portfolio_candidates.csv (BONHR.OL|GILD|LHX|NOFIN.OL|WEC|KOG.OL|DNB.OL|DOFG.OL|NXPI|LNG) "
              "ble skrevet av morgenkjøringen 41361721155 som krasjet før ordrene ble lagt. Raden står urettet. Faktiske ordre "
              "2026-11-02 (2026-11-02-0042..0046): BRG.OL, GD, KOG.OL, TECH.OL, NCLH.")},
]


# AnalBot 02.11: TECH.OL-kurshoppet er uavklart (samme liste som GS-indeksens MAIN_EXCLUDE). Alle handler i disse merkes
# invalid_price i korreksjonsloggen. Ingen regelendring: handlene står; resultat kan regnes internt med og uten. Vises ikke på siden.
from .gs_index import MAIN_EXCLUDE as INVALID_PRICE


def _all_trade_files(logs: Path) -> list[tuple[str, Path]]:
    return [("rules_v1", logs / P.TRADES.name)] + [(b, paths(b, logs)[0]) for b in BOOKS]


def ensure_corrections(logs: Path = LOGS, fx_hist=None) -> list[dict]:
    """Korreksjonslogg (bare tillegg, én rad per berørt handelsrad; handelsradene endres aldri):
    - kind=invalid_price: alle rader (ordre/fill) i tickere med uavklart kurshopp (INVALID_PRICE).
    - kind=valuta: rader der valutafeltet ikke stemmer med børsens valuta (P.ccy), f.eks. NKT.CO logget som NOK men i DKK.
      For fill regnes antall, NOK-verdi, kostnad og resultat om med dagskurs på kursdatoen (fx_hist(valuta, dato)); NAV bruker
      korreksjonene via P.state(..., corr). Uten dagskurs hoppes raden over og prøves igjen neste kjøring."""
    path = logs / P.CORR.name
    have = {(r["book_id"], r["order_id"], r["event"], r["kind"]) for r in P._read(path)}
    today = __import__("datetime").date.today().isoformat()
    new = []
    for book, tp in _all_trade_files(logs):
        trades = P._read(tp)
        shares_c, cost_c = {}, {}
        for r in trades:
            t, key = r["ticker"], (book, r["order_id"], r["event"])
            if t in INVALID_PRICE and (*key, "invalid_price") not in have:
                new.append({"date": today, "book_id": book, "order_id": r["order_id"], "event": r["event"], "ticker": t,
                            "kind": "invalid_price", "logged": r.get("price") or "", "corrected": "", "fx": "", "fx_date": "",
                            "note": "kurshopp uavklart; handelen står (ingen regelendring), resultat regnes internt med og uten"})
                have.add((*key, "invalid_price"))
            want = P.ccy(t)
            if (r.get("currency") or want) == want:
                if r["event"] == "fill" and r["side"] == "buy":
                    shares_c[t], cost_c[t] = P._f(r["shares"]), (P._f(r["nok_value"]) or 0) + (P._f(r["cost_nok"]) or 0)
                continue
            if (*key, "valuta") in have:
                continue
            c = {"currency": want}
            fxv = fxd = None
            if r["event"] == "fill":
                fxv, fxd = (fx_hist or P.fx_history)(want, r["price_date"])
                if not fxv:
                    continue
                px = P._f(r["price"])
                if r["side"] == "buy":
                    nok, cost = P._f(r["nok_value"]), P._f(r["cost_nok"]) or 0
                    sh = nok / (px * fxv)
                    shares_c[t], cost_c[t] = sh, nok + cost
                    c.update({"fx": fxv, "shares": round(sh, 6)})
                else:
                    sh = shares_c.get(t, P._f(r["shares"]))
                    nok = sh * px * fxv
                    rate = (P._f(r["cost_nok"]) or 0) / (P._f(r["nok_value"]) or 1)
                    cost = nok * rate
                    c.update({"fx": fxv, "shares": round(sh, 6), "nok_value": round(nok, 2), "cost_nok": round(cost, 2),
                              "pnl_nok": round(nok - cost - cost_c.get(t, 0), 2)})
            new.append({"date": today, "book_id": book, "order_id": r["order_id"], "event": r["event"], "ticker": t, "kind": "valuta",
                        "logged": r.get("currency"), "corrected": __import__("json").dumps(c), "fx": fxv or "", "fx_date": fxd or "",
                        "note": f"{t} handles i {want}, logget som {r.get('currency')}; regnet om til NOK med dagskurs"})
            have.add((*key, "valuta"))
    P._append(path, P.K_COLS, new)
    return new


def internal_result(book: str, logs: Path = LOGS, exclude: frozenset = INVALID_PRICE, usdnok=None, fx=None) -> dict:
    """Internt (vises ikke): resultat med og uten handlene i `exclude`. Uten = som om handlene ikke fantes (kontantstrømmene tas ut).
    Verdsetting av åpne posisjoner: siste loggede markedskurs (portfolio_closes), aldri innkurs; mangler den, teller posisjonen 0."""
    tp = logs / P.TRADES.name if book == "rules_v1" else paths(book, logs)[0]
    trades, corr, last = P._read(tp), P.load_corrections(logs / P.CORR.name), P.last_closes(logs / P.CLOSES.name)
    out = {}
    for k, tr in (("med", trades), ("uten", [r for r in trades if r["ticker"] not in exclude])):
        s = P.state(tr, corr)
        val = sum(p["shares"] * (last.get(t, (0.0, None))[0] or 0.0) * (P._rate(p["currency"], usdnok, fx) or 0.0) for t, p in s["open"].items())
        out[k] = {"closed": len(s["closed"]), "pnl_closed_nok": round(sum(c["pnl_nok"] or 0 for c in s["closed"]), 2),
                  "open": len(s["open"]), "cash": round(s["cash"], 2), "nav_est": round(s["cash"] + val, 2),
                  "unpriced": sorted(t for t in s["open"] if t not in last or (P._rate(s["open"][t]["currency"], usdnok, fx) is None))}
    out["excluded"] = sorted(exclude)
    return out


def summaries(logs: Path = LOGS) -> dict:
    """Data for bøkene; avkastning skjult til 30 lukkede handler per bok (portfolio.summary). Bok 2 merket eksperimentell."""
    out = {}
    for book, rules in BOOKS.items():
        tp, npth = paths(book, logs)
        out[book] = {**P.summary(tp, npth, rules, name=book), "experimental": rules["experimental"]}
    return out
