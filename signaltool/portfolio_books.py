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


def run(snap: dict, status: dict, usd, bench, logs: Path = LOGS, px_extra: dict | None = None, fx: dict | None = None,
        closed: dict | None = None) -> dict:
    day = str(snap.get("date"))
    univ = universe(snap)
    hoy = hoy_candidates(univ)
    ctl, seed = control_candidates(univ, len(hoy), day)
    why_fn = annotator(risk_levels())
    apply_manual_fills(logs)   # AnalBot 16.11: idempotent, før stegene (ellers fyller steget 0099 på dagens kurs)
    out = {}
    for book, picks, why, sd in (("hoy_risiko_v1", hoy, "topp10 20d>0", ""), ("kontroll_tilfeldig_v1", ctl, f"tilfeldig seed={seed}", seed)):
        tp, npth = paths(book, logs)
        ran = any(r["date"] == day for r in P._read(npth))
        s = P.step(snap, usd, bench, tp, npth, rules=BOOKS[book], picks=picks, why_buy=why,
                   cols=B_COLS, annotate=why_fn, px_extra=px_extra, logs=logs, fx=fx, closed=closed)   # samme lukkede barer som bok 1
        # 16.11: kandidatraden bare når steget faktisk skrev NAV (ellers vises et univers uten kjøring).
        if not ran and any(r["date"] == day for r in P._read(npth)):
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
    {"date": "2026-11-16", "book_id": "hoy_risiko_v1", "kind": "kandidatlogg_uten_kjoring", "order_id": "cands-2026-11-16",
     "ticker": "CLX|BONHR.OL|TTWO|HUM|BOUV.OL|DFENS.OL|IDEX.OL|NKR.OL|SCANA.OL|SNTIA.OL", "side": "buy",
     "order_run": "2026-11-16", "fill_run": "", "missed_runs": "", "n_missed": "",
     "note": ("Kandidatradene 2026-11-16 i portfolio_candidates.csv (hoy_risiko_v1 og kontroll_tilfeldig_v1, universe_n=45) "
              "ble skrevet av nattkjøringen 43878284648, men NAV- og handelsfilene for bok 2/3 ble ikke tatt med i fremoverloggen "
              "(origin beholdt b3f3338-omregningen). Ingen kjøring 16.11. Raden står urettet. Siste fullførte univers er 29 (11.11). "
              "Blant 16.11-valgene står DFENS.OL, ODL.OL og SCANA.OL med 20d-avkastning ≤ 0 i samme natts learn_raw.")},
    {"date": "2026-11-16", "book_id": "kontroll_tilfeldig_v1", "kind": "kandidatlogg_uten_kjoring", "order_id": "cands-2026-11-16",
     "ticker": "REGN|DFENS.OL|TTWO|ODL.OL|NCLH|CEG|HII|FOXA|NKR.OL|SWK", "side": "buy",
     "order_run": "2026-11-16", "fill_run": "", "missed_runs": "", "n_missed": "",
     "note": ("Samme avvik som hoy_risiko_v1 cands-2026-11-16: kandidatrad uten NAV/handler. universe_n=45 (begge bøker samme tall). "
              "Siste fullførte univers er 29 (11.11). Kontrollfills fra før 16.11 er ikke rullert tilbake.")},
]


# AnalBot 16.11: nattkjøringen feilet 12.–16.11 (testene leste ekte logger, rettet 16.11 i 6aad3c3). Dagene er hull: ingen
# signaler i ettertid, bøkene viser «ingen kjøring». Salgsordre 2026-11-11-0099 (SCANA.OL, rødt flagg) fylles på sluttkurs 12.11
# fra Yahoo dagshistorikk (auto_adjust=False, samme kilde som portfolio._hist) = første lukkede bar etter ordren.
NO_RUN_DATES = ("2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16")
NO_RUN_WHY = "nattkjøringen feilet"
MANUAL_FILLS = [{"book_id": "kontroll_tilfeldig_v1", "order_id": "2026-11-11-0099", "ticker": "SCANA.OL", "side": "sell",
                 "price_date": "2026-11-12", "price": 1.43, "fx": 1.0, "run_date": "2026-11-16",
                 "source": "Yahoo dagshistorikk SCANA.OL 12.11.2026, Close (auto_adjust=False), hentet 16.11"}]


def apply_manual_fills(logs: Path = LOGS) -> list[dict]:
    """Fører MANUAL_FILLS én gang (idempotent): fill-rad i bokas trades-logg regnet som portfolio.step (salg: hele posisjonen,
    kostnad etter bokas sats, pnl mot nok_cost) + avviksrad «sen fylling, nattkjøring feilet». Eksisterende rader endres aldri."""
    out = []
    dpath = logs / DEV.name
    have_dev = {(r["book_id"], r["order_id"], r["kind"]) for r in P._read(dpath)}
    for m in MANUAL_FILLS:
        b, R = m["book_id"], BOOKS[m["book_id"]]
        tp = paths(b, logs)[0]
        trades = P._read(tp)
        if any(r["event"] in ("fill", "cancel") and r["order_id"] == m["order_id"] for r in trades):
            continue
        o = next((r for r in trades if r["event"] == "order" and r["order_id"] == m["order_id"]), None)
        s = P.state(trades)
        p = s["open"].get(m["ticker"])
        if not o or not p or m["order_id"] not in s["pending"]:
            log.warning("manuell fylling %s: ordre/posisjon finnes ikke – ikke ført", m["order_id"])
            continue
        illq = o["reason"].endswith("illiquid")
        rate = R["cost_each_way_illiquid"] if illq else R["cost_each_way"]
        nok = p["shares"] * m["price"] * m["fx"]
        cost = nok * rate
        row = {**o, "event": "fill", "run_date": m["run_date"], "price_date": m["price_date"], "price": m["price"], "fx": m["fx"],
               "shares": p["shares"], "nok_value": round(nok, 2), "cost_nok": round(cost, 2), "fx_effect_nok": 0.0,
               "pnl_nok": round(nok - cost - p["nok_cost"], 2)}
        cols = list(trades[0].keys()) if trades else P.T_COLS
        P._append(tp, cols, [row])
        out.append(row)
        if (b, m["order_id"], "sen_fylling") not in have_dev:
            P._append(dpath, D_COLS, [{"date": m["run_date"], "book_id": b, "kind": "sen_fylling", "order_id": m["order_id"],
                                       "ticker": m["ticker"], "side": m["side"], "order_run": o["signal_date"], "fill_run": m["run_date"],
                                       "missed_runs": "|".join(d for d in NO_RUN_DATES if d < m["run_date"]),
                                       "n_missed": len([d for d in NO_RUN_DATES if d < m["run_date"]]),
                                       "note": f"sen fylling, nattkjøring feilet; sluttkurs {m['price_date']} ({m['source']})"}])
            have_dev.add((b, m["order_id"], "sen_fylling"))
    hull_d = [d for d in NO_RUN_DATES if d < "2026-11-16"]   # 16.11: hull bare om dagen går uten kjøring (vises da i bøkene)
    hull = [{"date": "2026-11-16", "book_id": bk, "kind": "ingen_kjoring", "order_id": "runs-2026-11-12..2026-11-15", "ticker": "",
             "side": "", "order_run": "", "fill_run": "", "missed_runs": "|".join(hull_d), "n_missed": len(hull_d),
             "note": "hull: ingen kjøring (nattkjøringen feilet); ingen signaler i ettertid, dagene fylles ikke inn"}
            for bk in ["rules_v1", *BOOKS]]
    P._append(dpath, D_COLS, [h for h in hull if (h["book_id"], h["order_id"], h["kind"]) not in have_dev])
    return out


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
