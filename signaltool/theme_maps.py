"""Temakart («theme maps»): first/second/third-order value chains for two Norwegian-relevant themes (AI-kraft, Forsvar),
plus the EXPERIMENTAL tag «Tema-katalysator».

Companies are ILLUSTRATIONS of exposure, not recommendations. Theme alone never gives Kjøp.

Tema-katalysator (key `tema_kat`, experimental, logged in the forward log `types` column, does NOT count toward Kjøp):
a listed Oslo ticker in one of the maps gets it if ALL of
  (a) a Newsweb announcement from the issuer in the last TK_DAYS (20) calendar days has a title matching
      CONTRACT_RE (contract/kontrakt/avtale/agreement/order/ordre) AND the map's theme terms (THEME_TERMS[key]),
      excluding share awards / legal disputes / calendars etc. (collectors.newsweb.NOT_CONTRACT);
  (b) no red Oslo flag (weak_px, neg_ebit, placement – oslo_flags.FLAG_INFO kind "red");
  (c) 60-session return not above OSEBX's 60-session return (not already run up). Missing price data -> not granted.
Earlier tests of Oslo contract announcements (backtest/oslo_events.py) found no robust excess return on their own; the
tag exists only so that its hit rate can be measured forward.
"""
from __future__ import annotations
import logging, re
from datetime import date, timedelta
import pandas as pd

log = logging.getLogger(__name__)
TK_DAYS = 20          # calendar days for the announcement window
RET_DAYS = 60         # trading sessions for the relative-return check
BENCH = "OSEBX.OL"
TK_LABEL = "eksperimentell – testes framover"
STATEMENT = ("Tema alene gir aldri Kjøp. Kontraktsmeldinger alene har tidligere ikke gitt meravkastning i våre tester av Oslo Børs – "
             "Tema-katalysator er derfor bare et eksperimentelt merke som logges for å måle treffraten framover.")

# ---- documented keyword lists (lower-case regex, matched on Newsweb titles) ----
CONTRACT_RE = re.compile(r"\b(?:contracts?|\w*kontrakt\w*|\w*avtale\w*|agreements?|orders?|ordre\w*)\b", re.I)
EXCLUDE_RE = re.compile(r"oppsig|terminat|avslutt", re.I)   # terminated agreements are not catalysts
THEME_TERMS = {
    "forsvar": re.compile(r"forsvar|defen[cs]e|missil|nasams|\bnsm\b|\bjsm\b|ammunisjon|ammunition|militær|military|\bnato\b", re.I),
    "ai_kraft": re.compile(r"datasenter|data ?cent(?:er|re)|kraftavtale|\bppa\b|power purchase|hyperscal", re.I),
}
KEYWORDS_DOC = {
    "kontrakt": "contract, kontrakt, avtale, agreement, order, ordre",
    "forsvar": "forsvar, defence/defense, missil(e), NASAMS, NSM, JSM, ammunisjon/ammunition, militær/military, NATO",
    "ai_kraft": "datasenter, data center/centre, kraftavtale, PPA, power purchase, hyperscaler",
}


def _c(name, ticker=None, note=""):
    return {"name": name, "ticker": ticker, "note": note}


MAPS: dict[str, dict] = {
    "ai_kraft": dict(
        key="ai_kraft", name="AI-kraft", file="kart_ai_kraft", related=["rare_earths_semis"],
        intro=("AI-modeller trenger datasentre, og datasentre trenger strøm, kjøling, kabler og elektronikk. Jo lenger ut i verdikjeden, "
               "jo mindre er temaet trolig priset inn – men jo svakere og mer usikker er koblingen til AI."),
        layers=[
            dict(order="Første orden", title="Mest priset inn – stort sett utenfor Oslo",
                 desc="Brikker og skyplattformer som tjener direkte på AI-investeringene. Her følger hele verden med.",
                 companies=[_c("Nvidia", "NVDA", "AI-brikker"), _c("Microsoft", "MSFT", "hyperskaler"), _c("Amazon", "AMZN", "hyperskaler (AWS)"),
                            _c("Alphabet/Google", "GOOGL", "hyperskaler"), _c("Green Mountain", None, "norsk datasenter – unotert"),
                            _c("Bulk Infrastructure", None, "norsk datasenter – unotert")]),
            dict(order="Andre orden", title="Flaskehalser: kraft, materialer, kabler, elektronikk",
                 desc="Datasentre begrenses av strøm og nettkapasitet. Norge har vannkraft og kraftkrevende industri; kablene lages mest utenfor Oslo Børs.",
                 companies=[_c("Norsk Hydro", "NHY.OL", "vannkraft + aluminium"), _c("Elkem", "ELK.OL", "silisium/silikoner"),
                            _c("Scatec", "SCATC.OL", "fornybar kraft; katalysator = kraftavtaler med datasentre"),
                            _c("Kitron", "KIT.OL", "elektronikkproduksjon"), _c("Nexans", "NEX.PA", "kabler – utenfor Oslo"),
                            _c("NKT", "NKT.CO", "kabler – utenfor Oslo")]),
            dict(order="Tredje orden", title="Norsk fortrinn – AI i nisjer",
                 desc="Norske selskaper som bruker eller bygger AI inn i egne produkter. Små beløp i forhold til selskapene, og vanskelig å måle.",
                 companies=[_c("Nordic Semiconductor", "NOD.OL", "brikker med maskinlæring (edge-AI)"),
                            _c("Kongsberg Digital", "KOG.OL", "del av Kongsberg Gruppen – ikke egen aksje"),
                            _c("AI i havbruk", None, "små/unoterte selskaper – følg kontrakter")]),
        ],
        catalysts=["Kraftavtaler (PPA) mellom kraftprodusenter og datasentre – meldes på Newsweb",
                   "Konsesjoner og nettilknytning for datasentre (Statnett, NVE)",
                   "Strømpriser i prisområdene NO1–NO5 (Nord Pool)",
                   "Kraftskatt og regulering av datasentre (registreringsplikt, avgifter)"],
        dont=["Vi kjøper ikke «AI-aksjer» fordi temaet er i vinden – første orden er trolig priset inn.",
              "Vi gir ingen kursmål for temaet og vekter ikke temaet inn i Kjøp-reglene.",
              "Vi behandler ikke en kraftavtale-melding som kjøpssignal; den gir bare det eksperimentelle merket Tema-katalysator.",
              "Unoterte selskaper (Green Mountain, Bulk) følges bare som kilde til nyheter."],
    ),
    "forsvar": dict(
        key="forsvar", name="Forsvar (Oslo)", file="kart_forsvar", related=["conflict_defense", "nordic_arctic"],
        intro=("Europeisk opprustning og NATO-mål gir flere forsvarskontrakter. Kongsberg er det åpenbare navnet; leverandører og små "
               "nisjeselskaper er mindre fulgt, men også mer risikable."),
        layers=[
            dict(order="Første orden", title="Åpenbart – og sannsynligvis mye priset inn",
                 desc="Store systemleverandører med ordrebøker som alle analytikere følger.",
                 companies=[_c("Kongsberg Gruppen", "KOG.OL", "NSM/JSM-missiler, NASAMS luftvern, våpenstasjoner")]),
            dict(order="Andre orden", title="Leverandører og komponenter",
                 desc="Elektronikk, sensorer, materialer og ammunisjon til hovedleverandørene.",
                 companies=[_c("Kitron", "KIT.OL", "elektronikkproduksjon for forsvar"), _c("Norbit", "NORBT.OL", "sensorer/elektronikk"),
                            _c("Norsk Titanium", "NTI.OL", "3D-printet titan; lite og tapsbringende – trolig underskuddsflagg"),
                            _c("Nammo", None, "unotert; eksponering via Kongsberg (50 %)")]),
            dict(order="Tredje orden", title="Små selskaper – høy risiko",
                 desc="Droner/ubemannede systemer, sensorer, satellittkommunikasjon og undervannsovervåking. Små, ofte tapsbringende, og bare kontrakter er katalysator.",
                 companies=[_c("Nordic Unmanned", "NUMND.OL", "droner/ubemannede systemer"),
                            _c("Sensorer, satellittkommunikasjon, undervannsovervåking", None, "flere små/unoterte aktører – følg kontrakter")]),
        ],
        catalysts=["NATO-budsjetter og BNP-mål (2 % → 3,5 %/5 %)",
                   "Kontrakter fra Forsvarsmateriell og andre lands forsvar – meldes på Newsweb",
                   "Eksportlisenser (Norge, USA)",
                   "EU-rammeavtaler og -programmer (f.eks. ammunisjonsprogrammet)"],
        dont=["Vi kjøper ikke Kongsberg bare fordi forsvar er i nyhetene – første orden er trolig priset inn.",
              "Vi ser bort fra tapsbringende småselskaper med røde flagg, uansett hvor godt temaet passer.",
              "En kontraktsmelding gir bare det eksperimentelle merket Tema-katalysator – aldri Kjøp.",
              "Vi prøver ikke å handle på våpenhvile-/eskaleringsoverskrifter."],
    ),
}


def oslo_tickers(key: str) -> list[str]:
    return list(dict.fromkeys(c["ticker"] for L in MAPS[key]["layers"] for c in L["companies"] if (c["ticker"] or "").endswith(".OL")))


def maps_for(ticker: str) -> list[str]:
    return [k for k in MAPS if ticker in oslo_tickers(k)]


# ---------------------------------------------------------------- matching / computation (pure)
def theme_announcements(nw: pd.DataFrame | None, ticker: str, key: str, today: date, days: int = TK_DAYS) -> list[dict]:
    """Newsweb titles from the ticker's issuer in the last `days` calendar days matching contract words + theme terms."""
    if nw is None or len(nw) == 0 or not ticker.endswith(".OL"):
        return []
    from .collectors.newsweb import NOT_CONTRACT
    sub = nw[nw["issuer"].fillna("") == ticker[:-3]]
    out = []
    for r in sub.itertuples():
        d = pd.Timestamp(r.published)
        d = (d.tz_convert("Europe/Oslo") if d.tzinfo else d).date()
        if d > today or (today - d).days > days:
            continue
        t = str(r.title or "")
        if CONTRACT_RE.search(t) and THEME_TERMS[key].search(t) and not NOT_CONTRACT.search(t) and not EXCLUDE_RE.search(t):
            url = getattr(r, "url", None) or (f"https://newsweb.oslobors.no/message/{r.id}" if hasattr(r, "id") else None)
            out.append({"date": d.isoformat(), "title": t, "url": url})
    return sorted(out, key=lambda x: x["date"], reverse=True)


def rel_returns(closes: pd.Series | None, bench: pd.Series | None, n: int = RET_DAYS) -> dict:
    """60-session return of the stock and OSEBX over the same dates."""
    if closes is None or len(closes.dropna()) <= n:
        return {}
    c = closes.dropna()
    out = {"ret60": float(c.iloc[-1] / c.iloc[-1 - n] - 1), "close": float(c.iloc[-1]), "asof": str(c.index[-1].date())}
    if bench is not None and len(bench.dropna()):
        b = bench.dropna().reindex(c.index, method="ffill")
        if pd.notna(b.iloc[-1]) and pd.notna(b.iloc[-1 - n]):
            out["bench60"] = float(b.iloc[-1] / b.iloc[-1 - n] - 1)
            out["rel60"] = out["ret60"] - out["bench60"]
    return out


def tema_catalyst(matches: list[dict], flags: dict, rets: dict) -> tuple[bool, list[tuple[str, bool | None, str]]]:
    """(granted, checks). checks = [(label, ok or None if unknown, detail)]."""
    from .oslo_flags import FLAG_INFO
    red = [k for k in flags if FLAG_INFO.get(k, ("", "red"))[1] == "red"]
    a = bool(matches)
    b = not red
    rel = rets.get("rel60")
    c = None if rel is None else rel <= 0
    checks = [(f"Tema-relevant kontraktsmelding på Newsweb siste {TK_DAYS} dager", a,
               f'{matches[0]["date"]}: {matches[0]["title"]}' if a else "ingen treff"),
              ("Ingen røde flagg", b, "ok" if b else ", ".join(FLAG_INFO[k][0] for k in red)),
              (f"Ikke steget mer enn OSEBX siste {RET_DAYS} handelsdager", c,
               "ingen kursdata" if rel is None else f"{rets['ret60']*100:+.1f} % mot OSEBX {rets['bench60']*100:+.1f} %")]
    return bool(a and b and c), checks


def compute(key: str, prices: dict, m: pd.DataFrame, meta: dict, ev: dict, nw, today: date, fetch: bool = True) -> list[dict]:
    from . import oslo_flags as O
    bench = prices.get(BENCH, {}).get("Close") if isinstance(prices.get(BENCH), pd.DataFrame) else None
    names = {c["ticker"]: c["name"] for L in MAPS[key]["layers"] for c in L["companies"] if c["ticker"]}
    rows = []
    for t in oslo_tickers(key):
        px = prices.get(t)
        has = isinstance(px, pd.DataFrame) and len(px) > RET_DAYS
        o = O.ticker_flags(t, m, meta, ev, today, fetch=fetch) if has else {"flags": {}}
        if not has:  # no price data: only the non-price flags we can still verify
            eb = O.ebit_latest(t, fetch=False)
            if eb and eb["ebit"] < 0:
                o["flags"]["neg_ebit"] = f"negativt driftsresultat i siste årsregnskap ({eb['fye'][:4]})"
        rets = rel_returns(px["Close"], bench) if has else {}
        mt = theme_announcements(nw, t, key, today)
        ok, checks = tema_catalyst(mt, o.get("flags") or {}, rets)
        rows.append({"ticker": t, "name": names.get(t, t), "has_data": has, **rets, "flags": o.get("flags") or {},
                     "info": o.get("info") or {}, "matches": mt[:3], "tema_kat": ok, "checks": checks})
    return rows


def apply(snap: dict, nw: pd.DataFrame | None = None, fetch: bool = True, prices: dict | None = None) -> str:
    """snap['theme_maps'] = {key: {'rows': [...], 'asof', 'newsweb'}}; also e['temakart'] on snapshot tickers in a map."""
    from . import oslo_flags as O
    from .categories import _d
    today = _d(snap.get("date")) or date.today()
    prices = O.universe_prices(fetch=fetch, today=today) if prices is None else prices
    meta, m = O.price_ranks(prices)
    if nw is None:
        nw = O.LAST_NW
    if nw is None and fetch:
        try:
            from .collectors import newsweb
            nw, _ = newsweb.collect(days=95)
        except Exception as ex:
            log.warning("newsweb for theme maps: %s", ex)
    ev = O.newsweb_events(nw, today) if nw is not None else {}
    out, n_tk = {}, 0
    for key in MAPS:
        rows = compute(key, prices, m, meta, ev, nw, today, fetch=fetch)
        n_tk += sum(r["tema_kat"] for r in rows)
        out[key] = {"rows": rows, "asof": meta.get("asof"), "newsweb": nw is not None and len(nw) > 0}
    snap["theme_maps"] = out
    by_t = {}
    for key, v in out.items():
        for r in v["rows"]:
            d = by_t.setdefault(r["ticker"], {"maps": [], "tema_kat": False, "checks": {}, "matches": []})
            d["maps"].append(key)
            d["checks"][key] = r["checks"]
            d["matches"] += r["matches"]
            d["tema_kat"] = d["tema_kat"] or r["tema_kat"]
    for e in snap.get("tickers", []):
        if e["ticker"] in by_t:
            e["temakart"] = by_t[e["ticker"]]
        else:
            e.pop("temakart", None)
    return f"ok ({sum(len(v['rows']) for v in out.values())} Oslo-rader i {len(out)} temakart, Tema-katalysator: {n_tk}, Newsweb {'ok' if nw is not None and len(nw) else 'mangler'})"


def log_rows(snap: dict) -> list[dict]:
    """Forward-log rows for map tickers NOT already in the snapshot (category 'tema' – outside the Kjøp/Hold/Watchlist stats).
    types = 'tema_kat' when the tag is set; rows without it are the control group."""
    have = {e["ticker"] for e in snap.get("tickers", [])}
    from .oslo_flags import FLAG_INFO
    rows, seen = [], set()
    for v in (snap.get("theme_maps") or {}).values():
        for r in v["rows"]:
            t = r["ticker"]
            if t in have or t in seen or not r.get("has_data"):
                continue
            seen.add(t)
            tk = any(rr["tema_kat"] for vv in snap["theme_maps"].values() for rr in vv["rows"] if rr["ticker"] == t)
            red = [k for k in r["flags"] if FLAG_INFO.get(k, ("", "red"))[1] == "red"]
            other = sorted(k for k in r["flags"] if k not in red)
            rows.append({"date": snap["date"], "ticker": t, "category": "tema", "price": None if r.get("close") is None else round(r["close"], 4), "price_date": r.get("asof"),
                         "benchmark": BENCH, "score": None, "n_types": 0, "types": "tema_kat" if tk else "", "flags": "|".join(red + other)})
    return rows


# ---------------------------------------------------------------- HTML
def _E(x):
    import html
    return html.escape("" if x is None else str(x))


def tk_badge() -> str:
    return f'<span class="rel mid">🧪 Tema-katalysator – {_E(TK_LABEL)}</span>'


def _flag_pills(r: dict) -> str:
    from .site_extra import _flag_info
    icon = {"red": "🚩", "yellow": "🟡", "note": "ⓘ", "info": "🏷️"}
    ps = [f'<span class="pill" title="{_E(txt)}">{icon.get(_flag_info(k)[1], "•")} {_E(_flag_info(k)[0])}</span>' for k, txt in r["flags"].items()]
    ps += [f'<span class="pill" title="{_E(txt)}">🏷️ {_E(_flag_info(k)[0])}</span>' for k, txt in (r.get("info") or {}).items()]
    return "".join(ps) or '<span class="mut">ingen</span>'


def map_html(key: str, snap: dict, have: set | None = None) -> str:
    from .site_extra import pct
    M = MAPS[key]
    have = have or set()
    comp = (snap.get("theme_maps") or {}).get(key) or {}
    rows = {r["ticker"]: r for r in comp.get("rows", [])}

    def tlink(t):
        if not t:
            return '<span class="mut">unotert</span>'
        if t in have:
            return f'<a href="../ticker/{re.sub(r"[^A-Za-z0-9_-]", "_", t)}.html">{_E(t)}</a>'
        return f'<a href="https://finance.yahoo.com/quote/{_E(t)}">{_E(t)}</a>'

    layers = ""
    for L in M["layers"]:
        lis = ""
        for c in L["companies"]:
            t = c["ticker"]
            extra = ""
            if t and t.endswith(".OL"):
                r = rows.get(t)
                if r is None:
                    extra = ' <span class="mut">(ikke beregnet i denne kjøringen)</span>'
                elif not r["has_data"]:
                    extra = ' <span class="rel lo">ingen kursdata</span>'
                if r and r.get("tema_kat"):
                    extra += " " + tk_badge()
            elif t:
                extra = ' <span class="mut">(utenfor Oslo – kun illustrasjon)</span>'
            lis += f'<li><b>{_E(c["name"])}</b> {tlink(t)} <span class="mut">– {_E(c["note"])}</span>{extra}</li>'
        layers += (f'<div class="card"><h2 style="margin-top:0">{_E(L["order"])}: {_E(L["title"])}</h2><p>{_E(L["desc"])}</p>'
                   f'<ul class="ev">{lis}</ul></div>')

    trs = ""
    for t, r in rows.items():
        if r["has_data"]:
            ret = f'{pct(r.get("ret60"))}'
            rel = f'{pct(r.get("bench60"))} / {pct(r.get("rel60"))}' if r.get("rel60") is not None else "–"
        else:
            ret, rel = '<span class="mut">ingen kursdata</span>', "–"
        chk = "".join(f'<li>{"✅" if ok else "❌" if ok is False else "❔"} {_E(lab)}: <span class="mut">{_E(det)}</span></li>' for lab, ok, det in r["checks"])
        tk = tk_badge() if r["tema_kat"] else '<span class="mut">nei</span>'
        trs += (f'<tr><td>{tlink(t)}<div class="mut">{_E(r["name"])}</div></td><td>{ret}</td><td>{rel}</td><td>{_flag_pills(r)}</td>'
                f'<td>{tk}<details><summary>kriterier</summary><ul class="ev">{chk}</ul></details></td></tr>')
    table = (f'<div class="card tw" id="oslo"><h2 style="margin-top:0">Oslo-tickere i kartet: flagg og kurs</h2>'
             f'<p class="mut">Kurs per {_E(comp.get("asof") or "–")} fra Oslo-universets kurscache. 60 d = 60 handelsdager. '
             'Sektorindeks finnes ikke i cachen, så sammenligningen er mot OSEBX.</p>'
             '<table><tr><th>Ticker</th><th>60 d</th><th>OSEBX 60 d / differanse</th><th>Flagg i dag</th><th>Tema-katalysator</th></tr>'
             f'{trs}</table></div>') if rows else '<div class="card"><p class="mut">Flagg og kurs ikke beregnet i denne kjøringen.</p></div>'

    cat = "".join(f"<li>{_E(x)}</li>" for x in M["catalysts"])
    dont = "".join(f"<li>{_E(x)}</li>" for x in M["dont"])
    rel = " ".join(f'<a class="pill" href="{k}.html">{_E(_theme_name(k, snap))}</a>' for k in M["related"])
    return f"""<h1>Temakart: {_E(M['name'])}</h1>
<div class="warnbox">Selskapene er eksempler på eksponering i verdikjeden – <b>ikke anbefalinger</b>. {_E(STATEMENT)}</div>
<div class="card hl"><p>{_E(M['intro'])}</p><p class="mut">Første orden = direkte og mest fulgt; andre orden = flaskehalser/leverandører; tredje orden = indirekte nisjer. Relaterte temaer: {rel}</p></div>
{layers}
{table}
<div class="card"><h2 style="margin-top:0">Katalysatorer å følge</h2><ul class="ev">{cat}</ul></div>
<div class="card"><h2 style="margin-top:0">🧪 Tema-katalysator ({_E(TK_LABEL)})</h2>
<p>En Oslo-ticker i kartet får merket når <b>alle</b> tre gjelder: (a) selskapet har en Newsweb-melding siste {TK_DAYS} dager der tittelen inneholder et kontraktsord
(<i>{_E(KEYWORDS_DOC['kontrakt'])}</i>) <b>og</b> et temaord (<i>{_E(KEYWORDS_DOC[key])}</i>); (b) ingen røde flagg; (c) aksjen har ikke steget mer enn OSEBX siste {RET_DAYS} handelsdager.</p>
<p>Merket teller <b>ikke</b> mot Kjøp. Det logges i fremoverloggen (kolonnen «types» = tema_kat) slik at treffraten kan måles senere. {_E(STATEMENT)}</p></div>
<div class="card"><h2 style="margin-top:0">Hva vi bevisst ikke gjør</h2><ul class="ev">{dont}</ul></div>"""


def _theme_name(k: str, snap: dict) -> str:
    for t in snap.get("themes", []):
        if t["key"] == k:
            return t["name"]
    return k


def cards_html(pre: str = "") -> str:
    """Section for temaer.html."""
    cs = "".join(f'<div class="card"><h3><a href="{pre}tema/{M["file"]}.html">🗺️ Temakart: {_E(M["name"])}</a></h3><p class="mut">{_E(M["intro"])}</p></div>'
                 for M in MAPS.values())
    return f'<h2>Temakart</h2><p class="mut">Verdikjeder i første, andre og tredje orden med eksempler (ikke anbefalinger). {_E(STATEMENT)}</p><div class="grid">{cs}</div>'


def related_html(theme_key: str) -> str:
    ms = [M for M in MAPS.values() if theme_key in M["related"]]
    if not ms:
        return ""
    return ('<div class="card hl"><h2 style="margin-top:0">🗺️ Temakart</h2><p>' +
            " ".join(f'<a class="pill" href="{M["file"]}.html">{_E(M["name"])}</a>' for M in ms) +
            '</p><p class="mut">Verdikjede (første/andre/tredje orden), katalysatorer og det eksperimentelle merket Tema-katalysator.</p></div>')


def ticker_html(e: dict) -> str:
    tk = e.get("temakart")
    if not tk:
        return ""
    links = " ".join(f'<a class="pill" href="../tema/{MAPS[k]["file"]}.html">🗺️ {_E(MAPS[k]["name"])}</a>' for k in tk["maps"])
    chk = ""
    for k, cs in tk["checks"].items():
        chk += f'<li><b>{_E(MAPS[k]["name"])}</b><ul class="ev">' + "".join(
            f'<li>{"✅" if ok else "❌" if ok is False else "❔"} {_E(lab)}: <span class="mut">{_E(det)}</span></li>' for lab, ok, det in cs) + "</ul></li>"
    mt = "".join(f'<li>{_E(x["date"])}: <a href="{_E(x["url"])}">{_E(x["title"])}</a></li>' for x in tk.get("matches", [])[:3])
    status = tk_badge() + " <b>satt</b>" if tk["tema_kat"] else f'Tema-katalysator: <b>ikke satt</b> <span class="mut">({_E(TK_LABEL)})</span>'
    return (f'<div class="card" id="temakart"><h2 style="margin-top:0">Temakart og Tema-katalysator</h2><p>{links}</p><p>{status}</p>'
            f'<ul class="ev">{chk}</ul>' + (f'<p>Treff på Newsweb:</p><ul class="ev">{mt}</ul>' if mt else "")
            + f'<p class="mut">{_E(STATEMENT)} Teller ikke mot Kjøp.</p></div>')
