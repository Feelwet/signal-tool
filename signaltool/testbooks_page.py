"""Signal-boka: «Testporteføljer (under måling)» (bruker 02.11.2026; AnalBots veto 02.11 innarbeidet).

Per bok: kjøringer, «X av 30 lukkede», åpne, univers, manglende kjøringer, «uten kurs» og regelboks. Ingen grafer, ingen NAV-tall og
ingen tall mot referansen før 30 lukkede. GS-indeksen: bare «Skjult til 60 handelsdager (n av 60)» + regelboks; gs_with_tech vises
aldri. Alle tall leses fra loggene; ingenting fylles inn. Usikkerhet står synlig (aldri i ⓘ). Regeltekst leses fra konfigurasjonen."""
from __future__ import annotations

from html import escape as E
from pathlib import Path

from . import gs_index as G
from . import portfolio as P
from . import portfolio_books as B
from .config import LOGS
from .portfolio_rules import RULES

MIN_CLOSED = RULES["min_closed_for_returns"]
# AnalBot 02.11, ordrett i regelboksene for alle tre bøkene
NO_PRICE_RULE = "Mangler sluttkurs for en åpen posisjon, står den som «uten kurs» og selges første dag kursen finnes, til den kursen. Innkurs brukes aldri som verdi."
# Kjente hull med kjent årsak (dato -> årsak). Ukjente hull vises uten årsak.
KNOWN_GAPS = {("kontroll_tilfeldig_v1", "2026-10-31"): "programfeil (posisjon utenfor lista), rettet 02.11",
              ("kontroll_tilfeldig_v1", "2026-11-01"): "programfeil (posisjon utenfor lista), rettet 02.11",
              ("kontroll_tilfeldig_v1", "2026-11-02"): "programfeil (posisjon utenfor lista), rettet 02.11"}
BOOK_TITLES = {"rules_v1": "Signal-boka", "hoy_risiko_v1": "Høy risiko", "kontroll_tilfeldig_v1": "Kontroll: tilfeldige kjøp"}

CSS = """
.tb-sec{margin:0 0 14px}.tb-sec>h2{margin:0 0 4px;font-size:18px}.tb-sec>.tb-lead{margin:0 0 10px;font-size:13px;line-height:18px;color:#cbd5e1}
.tb-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:10px}
@media(min-width:900px){.tb-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.tb-card{background:#1c2430;border:1px solid #3b4757;border-top:3px solid #58a6ff;border-radius:12px;padding:12px;min-width:0;box-sizing:border-box}
.tb-h{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}.tb-h b{font-size:16px}.tb-h code{font-size:12px;color:#94a3b8}.tb-h a{margin-left:auto;font-size:12px}
.tb-k{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:8px 0}
.tb-k>div{background:#111821;border-radius:6px;padding:8px;min-width:0}.tb-k .l{display:block;font-size:12px;line-height:16px;text-transform:uppercase;color:#cbd5e1}
.tb-k .v{display:block;font-size:20px;line-height:24px;font-weight:600;overflow-wrap:anywhere}.tb-k .s{display:block;font-size:11px;line-height:14px;color:#94a3b8}
.tb-u{margin:6px 0 0;font-size:12px;line-height:16px;color:#cbd5e1}
.tb-rules ul{margin:0 0 8px;padding-left:18px}.tb-rules li{margin:0 0 4px}
@media(max-width:599px){.tb-k .v{font-size:16px;line-height:20px}.tb-k>div{padding:6px}}
"""


def _n(x: float, d: int = 2) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "\u2212")


def _dt(d: str) -> str:
    return f"{d[8:10]}.{d[5:7]}.{d[:4]}" if d and len(d) >= 10 else "–"


def _last_universe(book: str, logs: Path) -> tuple[str | None, int | None]:
    rs = [r for r in P._read(logs / B.CANDS.name) if r.get("book_id") == book]
    return (rs[-1]["date"], int(rs[-1]["universe_n"])) if rs and str(rs[-1].get("universe_n") or "").isdigit() else (None, None)


def book_data(book: str, logs: Path = LOGS, snap: dict | None = None) -> dict:
    tp, npth = (logs / "portfolio_trades.csv", logs / "portfolio_nav.csv") if book == "rules_v1" else B.paths(book, logs)
    navs, trades = P._read(npth), P._read(tp)
    s = P.state(trades)
    if book == "rules_v1":   # universet for bok 1 = tickere i Kjøp i dagens liste
        udate = (snap or {}).get("date")
        un = sum(1 for e in (snap or {}).get("tickers", []) if e.get("category") == RULES["buy_category"]) if snap else None
    else:
        udate, un = _last_universe(book, logs)
    miss = [r for r in P._read(logs / P.MISSING.name) if r.get("book_id") == book]
    last_run = navs[-1]["date"] if navs else None
    no_px = sorted({r["ticker"] for r in miss if r["date"] == last_run and r.get("status") == "åpen"})
    return {"book": book, "dates": [r["date"] for r in navs], "open": len(s["open"]), "closed": len(s["closed"]),
            "pending": len(s["pending"]), "fills": len([r for r in trades if r["event"] == "fill"]),
            "start": navs[0]["date"] if navs else None, "universe_n": un, "universe_date": udate, "no_price": no_px}


def book_card(d: dict, all_dates: list[str]) -> str:
    """AnalBot 02.11: ingen grafer, ingen NAV-tall, ingen tall mot referansen. Kjøringer, åpne/lukkede, univers, hull, regler."""
    book = d["book"]
    own = set(d["dates"])
    gaps = [x for x in all_dates if d["start"] and x > d["start"] and x not in own]
    un = "–" if d["universe_n"] is None else str(d["universe_n"])
    k = (f'<div class="tb-k"><div><span class="l">Kjøringer</span><span class="v">{len(d["dates"])}</span><span class="s">fra {E(_dt(d["start"]))}</span></div>'
         f'<div><span class="l">Handler</span><span class="v">{d["closed"]} av {MIN_CLOSED}</span><span class="s">lukkede · {d["open"]} åpne</span></div>'
         f'<div><span class="l">Univers</span><span class="v">{E(un)}</span><span class="s">{"Kjøp i dag" if book == "rules_v1" else "aksjer"}'
         f'{" " + E(_dt(d["universe_date"])[:5]) if d["universe_date"] else ""}</span></div></div>')
    u = [f"Få dager med data. {d['closed']} av {MIN_CLOSED} lukkede handler, resultater sier ingenting før {MIN_CLOSED} lukkede."]
    if book == "rules_v1" and not d["fills"]:
        u.append("0 handler: ingen aksjer har oppfylt Kjøp-reglene ennå, så kontoen står i kontanter.")
    if book == "hoy_risiko_v1":
        u.append("Eksperimentell. Teller bare hvis den slår kontrollporteføljen.")
    if book == "kontroll_tilfeldig_v1":
        u.append("Sammenligningsgrunnlag for Høy risiko: tilfeldige kjøp fra samme utvalg.")
    if gaps:
        why = {KNOWN_GAPS.get((book, g)) for g in gaps} - {None}
        u.append(f"Mangler kjøring {', '.join(_dt(g)[:5] for g in gaps)}" + (f" ({'; '.join(sorted(why))})" if why else "")
                 + ". Dagene fylles ikke inn i etterkant.")
    if d["no_price"]:
        u.append(f"Uten kurs siste kjøring: {', '.join(d['no_price'])}. Selges første dag det finnes kurs.")
    return (f'<div class="tb-card" id="tb-{E(book)}"><div class="tb-h"><b>{E(BOOK_TITLES.get(book, book))}</b><code>{E(book)}</code>'
            f'<a href="#{"regler" if book == "rules_v1" else "regler-" + E(book)}">Regler</a></div>{k}'
            + "".join(f'<p class="tb-u">{E(x)}</p>' for x in u) + "</div>")


def gs_card(path: Path = G.OUT) -> str:
    """AnalBot 02.11: bare «Skjult til 60 handelsdager (n av 60)» + regelboks. gs_with_tech vises aldri."""
    n = len(G.read(path))
    return (f'<div class="tb-card" id="tb-gs"><div class="tb-h"><b>GS-indeksen</b><a href="#regler-gs">Regler</a></div>'
            f'<p class="tb-u">Skjult til {G.MIN_DAYS_PUBLIC} handelsdager ({min(n, G.MIN_DAYS_PUBLIC)} av {G.MIN_DAYS_PUBLIC}).</p></div>')


def _pct(x: float) -> str:
    return f"{x * 100:.1f}".rstrip("0").rstrip(",.").replace(".", ",") + " %"


def rules_items(book: str, start: str | None) -> list[str]:
    """Regeltekst lest fra konfigurasjonen (portfolio_books.BOOKS). Endrer ingen regler."""
    R = B.BOOKS[book]
    if book == "hoy_risiko_v1":
        buy = (f"Hver kjøring velges topp {R['top_n']} etter score blant Følg og Hold der 20-dagers avkastning er over 0. "
               "Tema er ute. Kjøp skjer til sluttkurs dagen etter signalet.")
    else:
        buy = ("Hver kjøring trekkes like mange tickere som Høy risiko velger samme dag, tilfeldig fra nøyaktig samme utvalg "
               "(Følg og Hold med score og 20-dagers avkastning over 0). Trekningen bruker et fast tall per dato, så den kan etterprøves. "
               "Kjøp skjer til sluttkurs dagen etter signalet.")
    return [
        buy,
        f"Hver posisjon er {_pct(R['position_pct'])} av kontoverdien når den kjøpes, maks {R['max_positions']} posisjoner. "
        + ("Det kjøpes ikke mer i en posisjon som allerede eies. " if not R["add_to_position"] else "")
        + f"Kontanter gir {_pct(R['cash_rate'])} rente.",
        f"Salg etter {R['hold_trading_days']} handelsdager eller ved rødt flagg. "
        + ("Ingen salg på kategori. " if not R["sell_on_folg_or_lower"] else "")
        + ("Ingen kursmål eller stopp-loss. " if R["price_target"] is None and R["stop_loss"] is None else "")
        + "Faller en aksje ut av lista, hentes sluttkursen likevel, og holdetiden telles videre.",
        NO_PRICE_RULE,
        f"Hver handel koster {_pct(R['cost_each_way'])} hver vei, {_pct(R['cost_each_way_illiquid'])} for lite omsatte aksjer. "
        "Amerikanske aksjer regnes om til NOK med dagskurs. "
        f"Kjøpsordre som ikke får kurs innen {R['order_expiry_runs']} kjøringer, kanselleres. Salgsordre kanselleres aldri.",
        "Referanse: OSEBX og S&P 500 vektet slik porteføljen faktisk er investert. Kontanter teller 0.",
        f"Start: {_dt(start)} med {_n(R['start_nok'], 0)} kr i fiktive penger. Resultat vises fra {R['min_closed_for_returns']} lukkede handler.",
    ] + (["Eksperimentell. Teller bare hvis den slår kontrollporteføljen."] if book == "hoy_risiko_v1" else [])


def gs_rules_items(start: str | None, n_old: int = 0, n_days: int = 0) -> list[str]:
    return [
        "Medlemmer: aksjene på lista i kategoriene Kjøp, Hold, Følg og Tema som er rangert, slik lista faktisk så ut hver dag.",
        "Inngang og utgang på sluttkurs første handelsdag etter at lista er kjent. Lik vekt, rebalansert hver dag.",
        f"Kostnad per handel er vektendringen ganger {_pct(RULES['cost_each_way'])}, {_pct(RULES['cost_each_way_illiquid'])} for lite omsatte aksjer (samme satser som Signal-boka).",
        f"Dagsbevegelser over {_pct(G.MAX_DAY_MOVE)} uten kjent splitt regnes som ugyldige og tas ut av dagens avkastning. Mangler kurs, er aksjen ute den dagen. Ingen kurser fylles inn.",
        "Referanse: OSEBX, Nasdaq Composite og NYSE Composite vektet etter listas børsfordeling samme dag, uten kostnader.",
        "TECH.OL er holdt utenfor til årsaken til kurshoppet er bekreftet.",
        f"Start: 100 på {_dt(start)}.",
    ] + ([f"{n_old} av {n_days} dager bygger på lister fra før rangeringsfeltet fantes, så urangerte aksjer kan være med de dagene."]
         if n_old else [])


def _fold(fid: str, title: str, code: str, items: list[str]) -> str:
    return (f'<details class="fold tb-rules" id="{E(fid)}"><summary><h2>{E(title)} <code>{E(code)}</code></h2></summary><div class="fold-body"><ul>'
            + "".join(f"<li>{E(x)}</li>" for x in items) + '</ul><p class="mut">Fiktive penger. Ikke investeringsråd.</p></div></details>')


def rules_html(logs: Path = LOGS, gs_path: Path = G.OUT) -> str:
    out = []
    for book in ("hoy_risiko_v1", "kontroll_tilfeldig_v1"):
        d = book_data(book, logs)
        out.append(_fold(f"regler-{book}", f"Regler {BOOK_TITLES[book]}", book, rules_items(book, d["start"])))
    rs = G.read(gs_path)
    out.append(_fold("regler-gs", "Regler GS-indeksen", "gs_index",
                     gs_rules_items(rs[0]["date"] if rs else None, sum(1 for r in rs if r.get("flag")), len(rs))))
    return "".join(out)


def section_html(logs: Path = LOGS, gs_path: Path = G.OUT, snap: dict | None = None) -> str:
    data = [book_data(b, logs, snap) for b in ("rules_v1", "hoy_risiko_v1", "kontroll_tilfeldig_v1")]
    all_dates = sorted({x for d in data for x in d["dates"]})
    cards = [book_card(d, all_dates) for d in data if d["dates"]] + [gs_card(gs_path)]
    return (f'<style>{CSS}</style><section class="tb-sec" id="testportefoljer"><h2>Testporteføljer (under måling)</h2>'
            '<p class="tb-lead">Papirporteføljer med fiktive 1 000 000 kr. Ingen resultater vises før 30 lukkede handler per portefølje. '
            'Ikke investeringsråd.</p>'
            f'<div class="tb-grid">{"".join(c for c in cards if c)}</div></section>')
