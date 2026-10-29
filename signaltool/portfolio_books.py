"""Papirbok 2 og 3 ved siden av «Signal-boka» (bok 1, rules_v1 – uendret). Kun simulert, ingen ekte handler.

Bok 2 `hoy_risiko_v1` (EKSPERIMENTELL, AnalBots låste spek 29.10): hver natt kandidater = topp 10 etter score blant Følg (watch),
Hold og Tema der 20-dagers avkastning > 0. Holdetid 20 handelsdager; ellers rules_v1-mekanikk (neste sluttkurs, 5 % av
bokverdi, maks 20 åpne, salg ved rødt flagg, kostnad 0,2 %/0,5 % illikvid). Ingen salg på kategori.
Bok 3 `kontroll_tilfeldig_v1`: samme antall kandidater som bok 2 samme dag, trukket tilfeldig fra samme univers
(Følg/Hold/Tema, uten 20d-filter) med deterministisk seed per dato. Samme mekanikk som bok 2.
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

UNIVERSE_CATS = ("watch", "hold", "tema")
HOY = {**RULES, "version": "hoy_risiko_v1", "experimental": True, "buy_category": None,
       "selection": "topp 10 etter score blant Følg/Hold/Tema med 20d-avkastning > 0", "top_n": 10,
       "hold_trading_days": 20, "sell_on_folg_or_lower": False}
KONTROLL = {**HOY, "version": "kontroll_tilfeldig_v1", "experimental": True,
            "selection": "tilfeldig fra Følg/Hold/Tema, samme antall som hoy_risiko_v1 samme dag, seed per dato"}
BOOKS = {"hoy_risiko_v1": HOY, "kontroll_tilfeldig_v1": KONTROLL}
# Bok 2/3: samme kolonner som portfolio_trades.csv + begrunnelse på kjøpsrader (AnalBot 29.10). Tomt felt = ikke tilgjengelig.
# bench_signal = indeksnivå ved signal (ordre), bench_entry = indeksnivå ved inngang (fill, samme kjøring som sluttkursen).
WHY_COLS = ["score", "signal_types", "risk_level", "sector", "category", "ret_20d", "bench", "bench_signal", "bench_entry"]
B_COLS = P.T_COLS + WHY_COLS
CANDS = LOGS / "portfolio_candidates.csv"
C_COLS = ["date", "book_id", "seed", "universe_n", "n", "tickers"]


def paths(book: str, logs: Path = LOGS) -> tuple[Path, Path]:
    return logs / f"portfolio_{book}_trades.csv", logs / f"portfolio_{book}_nav.csv"


def tema_rows(snap: dict) -> list[dict]:
    """Tema-kart-tickere som ikke er i snapshotet (kategori «tema», samme som theme_maps.log_rows) i snapshot-form."""
    from .oslo_flags import FLAG_INFO
    have = {e["ticker"] for e in snap.get("tickers", [])}
    out, seen = [], set()
    for v in (snap.get("theme_maps") or {}).values():
        for r in v.get("rows", []):
            t = r["ticker"]
            if t in have or t in seen or not r.get("has_data"):
                continue
            seen.add(t)
            red = {k: x for k, x in (r.get("flags") or {}).items() if FLAG_INFO.get(k, ("", "red"))[1] == "red"}
            out.append({"ticker": t, "category": "tema", "score": None, "cat_flags": red,
                        "stats": {"close": r.get("close"), "last_date": r.get("asof"), "ret_20d": r.get("ret20")}})
    return out


def universe(snap: dict) -> list[dict]:
    return [e for e in snap.get("tickers", []) if e.get("category") in UNIVERSE_CATS] + tema_rows(snap)


def hoy_candidates(univ: list[dict], n: int = HOY["top_n"]) -> list[dict]:
    """Topp n etter score der 20d-avkastning > 0. Rader uten score eller uten 20d-avkastning kan ikke rangeres og tas ikke med."""
    ok = [e for e in univ if e.get("category") in UNIVERSE_CATS and e.get("score") is not None
          and ((e.get("stats") or {}).get("ret_20d") or 0) > 0]
    return sorted(ok, key=lambda e: (-e["score"], e["ticker"]))[:n]


def seed_for(day: str, book: str = "kontroll_tilfeldig_v1") -> int:
    return int(hashlib.sha256(f"{book}:{day}".encode()).hexdigest()[:8], 16)


def control_candidates(univ: list[dict], n: int, day: str) -> tuple[list[dict], int]:
    seed = seed_for(day)
    pool = sorted((e for e in univ if e.get("category") in UNIVERSE_CATS), key=lambda e: e["ticker"])
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
                "risk_level": (levels.get(e["ticker"]) or {}).get("level"), "sector": (e.get("decision") or {}).get("sector"),
                "category": e.get("category"), "ret_20d": st.get("ret_20d"),
                "bench": "S&P 500 (^GSPC)" if P.is_us(e["ticker"]) else "OSEBX (OSEBX.OL)"}
    return why


def _log_cands(path: Path, row: dict) -> None:
    rows = list(csv.DictReader(path.open(newline=""))) if path.exists() else []
    if any(r["date"] == row["date"] and r["book_id"] == row["book_id"] for r in rows):
        return
    P._append(path, C_COLS, [row])


def run(snap: dict, status: dict, usd, bench, logs: Path = LOGS) -> dict:
    day = str(snap.get("date"))
    univ = universe(snap)
    extra = tema_rows(snap)
    hoy = hoy_candidates(univ)
    ctl, seed = control_candidates(univ, len(hoy), day)
    why_fn = annotator(risk_levels())
    out = {}
    for book, picks, why, sd in (("hoy_risiko_v1", hoy, "topp10 20d>0", ""), ("kontroll_tilfeldig_v1", ctl, f"tilfeldig seed={seed}", seed)):
        tp, npth = paths(book, logs)
        ran = any(r["date"] == day for r in P._read(npth))
        if not ran:
            _log_cands(logs / CANDS.name, {"date": day, "book_id": book, "seed": sd, "universe_n": len(univ), "n": len(picks),
                                           "tickers": "|".join(e["ticker"] for e in picks)})
        s = P.step(snap, usd, bench, tp, npth, rules=BOOKS[book], picks=picks, extra=extra, why_buy=why,
                   cols=B_COLS, annotate=why_fn)
        out[book] = s
        status[f"Papirbok {book}"] = (f"ok ({len(picks)} kandidater i dag, {len(s['open'])} åpne, {len(s['pending'])} ventende, "
                                      f"{len(s['closed'])} lukket)" + (" – allerede kjørt i dag" if ran else ""))
        log.info("papirbok %s %s: %d kandidater [%s]%s", book, day, len(picks), ",".join(e["ticker"] for e in picks),
                 f" seed={seed}" if sd != "" else "")
        print(f"Papirbok {book} {day}: {len(picks)} kandidater [{','.join(e['ticker'] for e in picks)}]"
              + (f" seed={seed}" if sd != "" else "") + (" (allerede kjørt i dag)" if ran else ""), flush=True)
    return out


def summaries(logs: Path = LOGS) -> dict:
    """Data for bøkene; avkastning skjult til 30 lukkede handler per bok (portfolio.summary). Bok 2 merket eksperimentell."""
    out = {}
    for book, rules in BOOKS.items():
        tp, npth = paths(book, logs)
        out[book] = {**P.summary(tp, npth, rules, name=book), "experimental": rules["experimental"]}
    return out
