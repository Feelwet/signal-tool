"""portefolje.html – «Signal-boka» (UxBot-spec). Ingen avkastningstall før 30 lukkede handler; ingen graf ennå."""
from __future__ import annotations

from html import escape as E

import numpy as np

from . import names as NM
from . import portfolio as P
from .portfolio_rules import RULES, RULES_VERSION

RULES_LOCKED = "25.10.2026"
# AnalBots tekst, ordrett (25.10.2026)
RULES_TEXT = [
    "Kontoen kjøper bare tickere i kategorien Kjøp, til sluttkurs dagen etter signalet. Hold og Følg blir aldri kjøpt.",
    "Hver posisjon er 5 % av kontoverdien når den kjøpes, og kontoen har maks 20 posisjoner. Det kjøpes ikke mer i en posisjon den allerede har. Kontanter gir 0 % rente.",
    "Den selger etter 60 handelsdager, ved rødt flagg, eller når kategorien faller til Følg eller lavere. Den bruker ikke kursmål eller stopp-loss.",
    "Hver handel koster 0,2 % hver vei, og 0,5 % for lite omsatte aksjer. Amerikanske aksjer regnes om til NOK med dagskurs, og valutaeffekten vises for seg.",
    "Avkastningen sammenlignes med en blanding av OSEBX og S&P 500, vektet slik porteføljen faktisk er fordelt. Resultatet vises først når kontoen har minst 30 lukkede handler.",
    "Handler kan ikke endres i etterkant. Endres reglene, blir det en ny versjon og en ny konto.",
]
RULES_FOOT = "Fiktive penger. Ikke investeringsråd."

CSS = """
.pf-h1{margin:0 0 2px;font-size:22px}.pf-h1 a{color:var(--acc)}.pf-sub{margin:0 0 10px;font-size:13px}
.pf-status{margin:0 0 10px}.pf-bar{height:8px;border-radius:4px;background:#21262d;overflow:hidden;margin-top:8px}.pf-bar i{display:block;height:100%;background:var(--acc)}
.pf-k3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0 0 12px}.pf-k3 .card{margin:0;padding:10px}.pf-k3 b{display:block;font-size:20px}.pf-k3 span{font-size:12px;color:var(--mut)}
.pf-cards{display:none}.pf-card{border-bottom:1px solid #21262d;padding:8px 0}
@media(max-width:599px){.pf-k3 b{font-size:16px}.pf-k3 .card{padding:8px}.pf-tab{display:none}.pf-cards{display:block}}
"""


def _nok(x):
    return f"{x:,.0f}".replace(",", " ") + " kr"


def _px(x):
    return "–" if x is None else f"{x:,.2f}".replace(",", " ").replace(".", ",")


def html(snap: dict, trades_path=P.TRADES, nav_path=P.NAV) -> str:
    trades = P._read(trades_path)
    navs = P._read(nav_path)
    s = P.state(trades)
    by = {e["ticker"]: e for e in snap.get("tickers", [])}
    n_closed, need = len(s["closed"]), RULES["min_closed_for_returns"]
    nav = P._f(navs[-1]["nav"]) if navs else RULES["start_nok"]
    cash = s["cash"]
    status = ("0 handler: ingen tickere har oppfylt Kjøp-reglene ennå" if not trades
              else f"{n_closed} av {need} lukkede handler før resultatet vises")
    w = min(100, n_closed / need * 100)
    top = (f'<h1 class="pf-h1">Signal-boka · fiktive penger · regler <a href="#regler">{RULES_VERSION}</a></h1>'
           f'<p class="pf-sub mut">Ikke investeringsråd</p>'
           f'<div class="card pf-status"><b>{E(status)}</b><div class="pf-bar" role="progressbar" aria-valuemin="0" aria-valuemax="{need}" aria-valuenow="{n_closed}"><i style="width:{w:.0f}%"></i></div></div>'
           f'<div class="pf-k3"><div class="card"><span>Kontoverdi</span><b>{_nok(nav)}</b></div>'
           f'<div class="card"><span>Kontanter</span><b>{cash / nav * 100 if nav else 100:.0f} %</b></div>'
           f'<div class="card"><span>Åpne posisjoner</span><b>{len(s["open"])} av {RULES["max_positions"]}</b></div></div>')
    rows, cards = [], []
    for t, p in s["open"].items():
        e = by.get(t) or {}
        pdt = (e.get("stats") or {}).get("last_date")
        day = int(np.busday_count(p["date"], pdt)) if pdt and p["date"] else 0
        fl = "; ".join(str(v) for v in (e.get("cat_flags") or {}).values()) or "–"
        nm = NM.name(t, e.get("name")) or ""
        rows.append(f'<tr><td><a href="ticker/{E(t.replace(".", "_"))}.html">{E(t)}</a></td><td>{E(nm)}</td><td>{E(p["date"])}</td><td>{_px(p["price"])}</td><td>dag {day} av {RULES["hold_trading_days"]}</td><td>{E(fl)}</td></tr>')
        cards.append(f'<div class="pf-card"><b>{E(t)}</b> <span class="mut">{E(nm)}</span><br>Inn {E(p["date"])} på {_px(p["price"])} · dag {day} av {RULES["hold_trading_days"]}<br><span class="mut">Flagg: {E(fl)}</span></div>')
    pos = ('<div class="card"><h2 style="margin-top:0">Åpne posisjoner</h2>' +
           (f'<div class="tw pf-tab"><table><tr><th>Ticker</th><th>Navn</th><th>Inn</th><th>Kurs</th><th>Holdetid</th><th>Flagg</th></tr>{"".join(rows)}</table></div><div class="pf-cards">{"".join(cards)}</div>'
            if rows else '<p class="mut">Ingen åpne posisjoner.</p>') + "</div>")
    fills = [r for r in trades if r["event"] == "fill"]
    lg = "".join(f'<tr><td>{E(r["price_date"])}</td><td>{"Kjøp" if r["side"] == "buy" else "Salg"}</td><td>{E(r["ticker"])}</td><td>{_px(P._f(r["price"]))}</td>'
                 f'<td>{_nok(P._f(r["cost_nok"]) or 0)}</td><td>{E(r["reason"].split(";")[0])}</td></tr>' for r in reversed(fills))
    pend = [r for r in s["pending"].values()]
    pl = "".join(f'<li>{E(r["signal_date"])}: {"kjøp" if r["side"] == "buy" else "salg"} {E(r["ticker"])} ({E(r["reason"].split(";")[0])}) – fylles til neste sluttkurs</li>' for r in pend)
    logh = ('<div class="card"><h2 style="margin-top:0">Handelslogg</h2>' + (f'<ul class="ev">{pl}</ul>' if pl else "") +
            (f'<div class="tw"><table><tr><th>Dato</th><th>Kjøp/salg</th><th>Ticker</th><th>Kurs</th><th>Kostnad</th><th>Regel</th></tr>{lg}</table></div>' if lg
             else '<p class="mut">Ingen gjennomførte handler ennå.</p>') + "</div>")
    rules = (f'<details class="fold" id="regler"><summary><h2>Regler <code>{RULES_VERSION}</code> (låst {RULES_LOCKED})</h2></summary><div class="fold-body"><ol>'
             + "".join(f"<li>{E(x)}</li>" for x in RULES_TEXT) + f'</ol><p class="mut">{E(RULES_FOOT)}</p></div></details>')
    return f"<style>{CSS}</style>" + top + pos + logh + rules
