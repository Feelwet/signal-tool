"""Render helpers for the decision layers (Norwegian UI): today's focus, change log, alerts, per-ticker decision panel,
theme scenarios, chokepoints, oil nowcast, Taiwan radar, policy alerts, classified Oslo insider trades."""
from __future__ import annotations
import html, re
from . import scenarios

E = lambda x: html.escape("" if x is None else str(x))


def slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", t)


def _fl(x):
    try:
        x = float(x)
        return None if x != x or x in (float("inf"), float("-inf")) else x
    except (TypeError, ValueError):
        return None


def pct(x, d=1):
    x = _fl(x)
    if x is None:
        return "–"
    cls = "up" if x > 0 else "down" if x < 0 else ""
    return f'<span class="{cls}">{x*100:+.{d}f}%</span>'


def ppct(x, d=0):
    """Plain (uncoloured, unsigned) percentage for magnitudes like volatility."""
    x = _fl(x)
    return "–" if x is None else f"{x*100:.{d}f}%"


def num(x, d=2):
    x = _fl(x)
    return "–" if x is None else f"{x:,.{d}f}".replace(",", " ")


def link(target: str, pre: str = "") -> str:
    """Briefing links: 'ticker/X' -> ticker/X.html, 'tema/k' -> tema/k.html, else as-is."""
    if not target:
        return ""
    if target.startswith("ticker/"):
        return f"{pre}ticker/{slug(target[7:])}.html"
    if target.startswith("tema/"):
        return f"{pre}{target}.html"
    return pre + target


CSS_EXTRA = """
.focus{list-style:none;padding:0;margin:0}.focus li{padding:8px 0;border-bottom:1px solid var(--line)}.focus li:last-child{border-bottom:0}
.focus .n{display:inline-block;width:1.6em;height:1.6em;line-height:1.6em;text-align:center;border-radius:50%;background:var(--acc-bg);color:var(--acc);font-weight:700;margin-right:6px}
.focus li.alert .n{background:rgba(255,128,120,.16);color:#ff9a92}
.bell{font-size:.9rem}.lean{display:inline-block;font-size:.78rem;padding:1px 8px;border-radius:8px;border:1px solid var(--line)}
.lean.bull{color:var(--up);border-color:rgba(74,194,107,.5)}.lean.bear{color:var(--down);border-color:rgba(255,128,120,.5)}.lean.base,.lean.nøytral{color:var(--mut)}
.scen{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}.scen>div{background:var(--card2);border:1px solid var(--line);border-radius:8px;padding:10px}
.scen>div.on{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc) inset}
.kv{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}.kv>div{background:var(--card2);border:1px solid var(--line);border-radius:8px;padding:10px}
.kv table td{border-bottom:1px solid #232a33;padding:4px 6px}.kv table td:first-child{color:var(--mut)}
.verdict{border-left:4px solid var(--warn);padding:6px 10px;background:rgba(227,179,65,.07);margin:8px 0;border-radius:4px}
td.nw{white-space:nowrap}
details summary{cursor:pointer;color:var(--acc);margin:6px 0}
.kind{font-size:.78rem;font-weight:700;padding:1px 7px;border-radius:6px;border:1px solid}.kind.kjøp{color:var(--up);border-color:rgba(74,194,107,.5)}
.kind.salg{color:var(--down);border-color:rgba(255,128,120,.5)}.kind.tegning{color:var(--acc);border-color:rgba(108,182,255,.5)}.kind.annet,.kind.ukjent,.kind.ikke{color:var(--mut);border-color:var(--line)}
"""


# ---------------------------------------------------------------- dashboard
def focus_html(snap: dict) -> str:
    b = snap.get("briefing")
    if not b:
        return ""
    items = b.get("focus") or []
    lis = "".join(f'<li class="{E(it.get("level"))}"><span class="n">{i}</span>{"🔔 " if it.get("level") == "alert" else ""}'
                  f'<a href="{E(link(it.get("link", "")))}"><b>{E(it["title"])}</b></a><div class="why">{E(it.get("why"))}</div></li>'
                  for i, it in enumerate(items, 1))
    if not lis:
        lis = '<li class="mut">Ingenting som krever oppmerksomhet i dag – ingen Kjøp-kandidater, brutte stopp eller fysiske varsler.</li>'
    return (f'<div class="card hl" id="fokus"><h2 style="margin-top:0">🎯 Hva bør jeg se på i dag?</h2><ol class="focus">{lis}</ol>'
            '<p class="mut">Prioritert automatisk: Kjøp-kandidater → brutte stopp og fysiske varsler (🔔) → kategoriendringer → mest aktive tema → Hold med hendelsesrisiko. '
            'Poenget er å peke på hva som er verdt å undersøke – ikke å gi råd.</p></div>')


def changes_html(snap: dict) -> str:
    b = snap.get("briefing") or {}
    c = b.get("changes")
    if not c:
        return ""
    title = f'Nytt siden {E(c["prev_date"])}' if c.get("prev_date") else "Nytt siden i går"
    lis = "".join(f'<li>{"🔔 " if x.get("level") == "alert" else ""}<b>{E(x["text"])}</b>'
                  + (f' <span class="mut">– {E(x.get("why"))}</span>' if x.get("why") else "") + "</li>" for x in c.get("items", [])[:12])
    al = b.get("alerts") or []
    alh = "".join(f'<li>{"🔔" if a["level"] == "alert" else "ⓘ"} <a href="{E(link(a.get("link", "")))}">{E(a["title"])}</a> <span class="mut">– {E(a.get("why"))}</span></li>' for a in al[:8])
    return (f'<div class="card" id="endringer"><h2 style="margin-top:0">🆕 {title}</h2>'
            + (f'<ul class="ev">{lis}</ul>' if lis else f'<p class="mut">{E(c.get("note"))}</p>')
            + (f'<h3>Varsler</h3><ul class="ev">{alh}</ul>' if alh else "") + "</div>")


# ---------------------------------------------------------------- ticker decision panel
TXT_KEYS = {"recommendationKey", "currency", "sector", "next_earnings", "last_earnings", "sector_etf"}


def clean(d: dict) -> dict:
    """Older snapshots may hold Yahoo strings such as 'Infinity' in numeric fields."""
    return {k: (_fl(v) if isinstance(v, str) and k not in TXT_KEYS else v) for k, v in (d or {}).items()}


def priced_in_verdict(d: dict) -> list[str]:
    """Plain-language, rule-based notes on how much may already be priced in (never a recommendation)."""
    d, out = clean(d), []
    ph, r60, rb60 = d.get("pct_from_hi52"), d.get("ret_60d"), d.get("rel_bench_60d")
    if ph is not None and ph >= -0.03 and (rb60 or 0) >= 0.15:
        out.append(f"Nær 52-ukers toppen ({pct(ph)}) etter {pct(rb60)} meravkastning på 60 dager – mye av historien kan allerede være priset inn.")
    elif ph is not None and ph <= -0.35:
        out.append(f"{pct(ph)} fra 52-ukers toppen – markedet priser inn betydelige problemer; signalet må veie opp for det.")
    if d.get("forwardPE") and d.get("trailingPE") and d["forwardPE"] > 0 and d["trailingPE"] > 0:
        if d["forwardPE"] > 40:
            out.append(f"Høy verdsettelse (P/E fremover {d['forwardPE']:.0f}) – høye forventninger er priset inn.")
    if d.get("target_upside") is not None and d.get("numberOfAnalystOpinions"):
        if d["target_upside"] < 0:
            out.append(f"Kursen er over analytikernes snittmål ({pct(d['target_upside'])}, {int(d['numberOfAnalystOpinions'])} analytikere).")
    if d.get("rel_sector_20d") is not None and abs(d["rel_sector_20d"]) >= 0.08:
        out.append(f"Har beveget seg {pct(d['rel_sector_20d'])} mot sektor ({E(d.get('sector_etf'))}) på 20 dager – aksjespesifikk bevegelse, ikke bare sektoren.")
    if d.get("eps_rev30") is not None and abs(d["eps_rev30"]) >= 0.05:
        out.append(f"Analytikerne har {'oppjustert' if d['eps_rev30'] > 0 else 'nedjustert'} årets resultatestimat {pct(d['eps_rev30'])} siste 30 dager – "
                   + ("kursen kan allerede reflektere dette." if d["eps_rev30"] > 0 else "sjekk om kursen har tatt det inn."))
    if d.get("days_to_earnings") is not None and 0 <= d["days_to_earnings"] <= 14:
        out.append(f"Kvartalsrapport om {d['days_to_earnings']} dager ({E(d.get('next_earnings'))}) – hendelsesrisiko.")
    if d.get("pead"):
        out.append(f"Sterk kvartalsrapport {E(d.get('last_earnings'))}: EPS-overraskelse {d.get('eps_surprise'):+.0f} % og kursreaksjon {pct(d.get('earn_reaction'))} mot SPY"
                   + (" (PEAD-S: volatilitet over median)" if d.get("pead_s") else "")
                   + " – eksperimentelt signal: historisk ca. +0,4–1 pp brutto over 60 d, omtrent null etter kurtasje (se metode).")
    return out


REC_NO = {"strong_buy": "sterkt kjøp", "buy": "kjøp", "hold": "hold", "underperform": "under marked", "sell": "selg", "none": "–"}


def decision_html(e: dict) -> str:
    d = clean(e.get("decision"))
    if not d:
        return ('<div class="card"><h2 style="margin-top:0">Beslutningsgrunnlag</h2><p class="mut">Ingen kurs-/nøkkeltall tilgjengelig for denne tickeren '
                '(mangler historikk eller er ikke en aksje).</p></div>')
    cur = d.get("currency") or ""
    bn = "OSEBX" if e["ticker"].endswith(".OL") else "S&P 500"
    close = d.get("close")
    def dist(level):
        return "" if not level or not close else f' <span class="mut">({(level/close-1)*100:+.1f} %)</span>'
    rows_p = [("Avkastning 5 / 20 / 60 d", f'{pct(d.get("ret_5d"))} / {pct(d.get("ret_20d"))} / {pct(d.get("ret_60d"))}'),
              (f"Mot {bn} 20 / 60 d", f'{pct(d.get("rel_bench_20d"))} / {pct(d.get("rel_bench_60d"))}'),
              (f"Mot sektor ({E(d.get('sector_etf') or '–')}) 20 / 60 d", f'{pct(d.get("rel_sector_20d"))} / {pct(d.get("rel_sector_60d"))}'),
              ("Fra 52-ukers topp / bunn", f'{pct(d.get("pct_from_hi52"))} <span class="mut">(topp {num(d.get("hi52"))}, bunn {num(d.get("lo52"))})</span>'),
              ("Momentum 12-1 mnd", pct(d.get("mom12_1"))),
              ("Analytikerestimat i år, endring 30 / 90 d", f'{pct(d.get("eps_rev30"))} / {pct(d.get("eps_rev90"))}'
               + ("" if d.get("eps_up30") is None else f' <span class="mut">({int(d["eps_up30"])} opp, {int(d.get("eps_down30") or 0)} ned siste 30 d)</span>'))]
    mc = d.get("marketCap")
    rows_v = [("P/E siste 12 mnd / fremover", f'{num(d.get("trailingPE"), 1)} / {num(d.get("forwardPE"), 1)}'),
              ("EV/EBITDA", num(d.get("enterpriseToEbitda"), 1)), ("P/B", num(d.get("priceToBook"), 1)),
              ("Markedsverdi", "–" if not mc else f"{mc/1e9:,.1f} mrd. {E(cur)}"),
              ("Utbytte", "–" if d.get("dividendYield") is None else f'{d["dividendYield"]:.2f} %'),
              ("Analytikere (gratis Yahoo-data)", "–" if not d.get("numberOfAnalystOpinions") else
               f'{E(REC_NO.get(d.get("recommendationKey"), d.get("recommendationKey")))}, {int(d["numberOfAnalystOpinions"])} stk, snittmål {num(d.get("targetMeanPrice"))} ({pct(d.get("target_upside"))})')]
    rows_r = [("Volatilitet (60 d, årlig)", ppct(d.get("vol60"))), ("Største fall siste år", pct(d.get("maxdd1y"), 0)),
              (f"Beta mot {bn} (1 år)", num(d.get("beta1y"))), ("Daglig svingning (ATR 14)", f'{num(d.get("atr14"))} ({ppct(d.get("atr_pct"), 1)})'),
              ("Likviditet (median omsetning 20 d)", "–" if not (e.get("stats") or {}).get("adv20") else f'{(e["stats"]["adv20"])/1e6:,.1f} mill. {E(cur)}/dag'),
              ("Short i % av fri flyt (Yahoo)", "–" if d.get("shortPercentOfFloat") is None else f'{d["shortPercentOfFloat"]*100:.1f} %'),
              ("Neste kvartalsrapport", "–" if not d.get("next_earnings") else f'{E(d["next_earnings"])} (om {d.get("days_to_earnings")} d)')]
    if d.get("last_earnings"):
        rows_r.append(("Siste rapport: EPS-overraskelse / reaksjon", f'{E(d.get("last_earnings"))}: {num(d.get("eps_surprise"), 0)} % / {pct(d.get("earn_reaction"))}'))
    rows_i = [("Siste kurs", f"{num(close)} {E(cur)}"), ("50-dagers snitt", num(d.get("sma50")) + dist(d.get("sma50"))),
              ("Stopp 2×ATR under kurs", num(d.get("stop_atr")) + dist(d.get("stop_atr")))]
    tab = lambda rows: "<table>" + "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in rows) + "</table>"
    ver = priced_in_verdict(d)
    verh = "".join(f'<div class="verdict">{v}</div>' for v in ver)
    inv = ("<p class='mut'>Ugyldiggjøring = nivået der signalet regnes som feil. Tommelfingerregel: lukk under 50-dagers snitt "
           "(trendbrudd) eller under 2×ATR (normal svingning overskredet). Velg én før du handler – og still posisjonsstørrelsen slik at tapet ved stopp er akseptabelt.</p>")
    return (f'<div class="card" id="beslutning"><h2 style="margin-top:0">Beslutningsgrunnlag</h2>{verh}<div class="kv">'
            f'<div><h3>Allerede priset inn?</h3>{tab(rows_p)}</div><div><h3>Verdsettelse</h3>{tab(rows_v)}</div>'
            f'<div><h3>Risiko og hendelser</h3>{tab(rows_r)}</div><div><h3>Ugyldiggjøring (stopp)</h3>{tab(rows_i)}{inv}</div></div>'
            '<p class="mut">Kilde: Yahoo Finance via yfinance (gratis, uoffisiell; nøkkeltall og analytikerdata kan være forsinket eller mangle). Ikke råd.</p></div>')


# ---------------------------------------------------------------- theme scenarios
def scenario_html(t: dict, snap: dict) -> str:
    s = scenarios.scenario(t, snap)
    lab = {"bull": "📈 Bull (eskalering)", "base": "➖ Base", "bear": "📉 Bear (nedtrapping)"}
    boxes = "".join(f'<div class="{"on" if s["lean"] == k else ""}"><h3>{lab[k]}{" ← heller mot" if s["lean"] == k else ""}</h3><p>{E(s[k])}</p></div>' for k in ("bull", "base", "bear"))
    leanno = {"bull": "bull", "bear": "bear", "nøytral": "nøytral"}
    rows = "".join(f'<tr><td>{E(i["label"])}</td><td><b>{E(i["value"])}</b></td><td><span class="lean {i["lean"]}">{leanno[i["lean"]]}</span></td><td class="mut">{E(i["watch"])}</td></tr>' for i in s["indicators"])
    return (f'<div class="card" id="scenario"><h2 style="margin-top:0">Scenarioer for de eksponerte aksjene</h2><div class="scen">{boxes}</div>'
            f'<h3 style="margin-top:12px">Nøkkelindikatorer å følge (live)</h3><div class="tw"><table><tr><th>Indikator</th><th>Nå</th><th>Heller mot</th><th>Hva du ser etter</th></tr>{rows}</table></div>'
            f'<p class="mut">«Heller mot» er en enkel telling ({s["n_bull"]} bull / {s["n_bear"]} bear av {len(s["indicators"])} indikatorer; krever overvekt på minst 2) – ikke en prognose.</p></div>')


# ---------------------------------------------------------------- makro sections
def chokepoints_html(snap: dict) -> str:
    cp = snap.get("chokepoints") or {}
    if not cp:
        return ""
    rows = ""
    for v in cp.values():
        a, tk = v.get("alle") or {}, v.get("tankskip") or {}
        new_drop = a.get("z90") is not None and a["z90"] <= -2 and (a.get("vs90") is None or a["vs90"] <= -0.15)
        persistent = a.get("yoy") is not None and a["yoy"] <= -0.5
        mark = "🔔 " if new_drop else ("⚠️ " if persistent else "")
        rows += (f'<tr><td>{mark}<b>{E(v["name"])}</b></td><td>{num(a.get("last7"), 1)}</td><td>{pct(a.get("yoy"), 0)}</td><td>{pct(a.get("vs90"), 0)} <span class="mut">(z {num(a.get("z90"), 1)})</span></td>'
                 f'<td>{num(tk.get("last7"), 1)} ({pct(tk.get("yoy"), 0)})</td><td>{_spark(v.get("spark"))}</td><td class="mut">{E(v.get("last_date"))}</td></tr>')
    return (f'<div class="card tw" id="sund"><h2 style="margin-top:0">🚢 Sundpassasjer – skip per dag (IMF PortWatch)</h2>'
            f'<p class="mut">7-dagers snitt av skipspasseringer (AIS-satellittdata), mot samme periode i fjor og mot siste ~90 dager (robust z). '
            f'Fysisk bekreftelse på om en krise faktisk påvirker handelen. Forsinkelse ca. 1 uke. 🔔 = nytt fall (z ≤ −2 og minst 15 % under 90-dagers median); ⚠️ = vedvarende forstyrrelse (≥ 50 % under i fjor).</p>'
            f'<table><tr><th>Sund</th><th>Skip/dag</th><th>Mot i fjor</th><th>Mot 90 d</th><th>Tankskip/dag (å/å)</th><th>Trend (4 mnd)</th><th>Data t.o.m.</th></tr>{rows}</table>'
            '<p class="mut">Pålitelighet: høy (IMF/Oxford, satellitt-AIS), men modellbasert. Vår test fant <b>ingen</b> statistisk sikker sammenheng mellom fall i passeringer og '
            'påfølgende avkastning for tankrederier/Brent (se metode) – bruk som bekreftelse av situasjonen, ikke som kjøpssignal.</p></div>')


def _spark(vals, w=140, h=32):
    v = [x for x in (vals or []) if x is not None]
    if len(v) < 2:
        return ""
    lo, hi = min(v), max(v)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i*(w-2)/(len(v)-1)+1:.1f},{h-1-(x-lo)/rng*(h-2):.1f}" for i, x in enumerate(v))
    return f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><polyline fill="none" stroke="#6cb6ff" stroke-width="1.5" points="{pts}"/></svg>'


def oil_nowcast_html(snap: dict) -> str:
    on = snap.get("oil_nowcast") or {}
    if not on:
        return ""
    rows = "".join(f'<tr><td>{E(v["label"])}</td><td>{num(v["last"], 1)}</td><td>{num(v.get("avg5y"), 1)}</td><td>{pct(v.get("dev_pct"))}</td>'
                   f'<td class="mut">{num(v.get("min5y"), 1)}–{num(v.get("max5y"), 1)}</td><td>{num(v.get("chg_w"), 1)}</td><td>{_spark(v.get("spark"))}</td><td class="mut">{E(v["date"])}</td></tr>' for v in on.values())
    return (f'<div class="card tw" id="olje"><h2 style="margin-top:0">🛢️ Oljelagre mot sesongnormal (EIA, ukentlig)</h2>'
            '<p class="mut">Lagre i millioner fat mot snittet for samme uke de siste 5 årene. Under normalen = stramt fysisk marked.</p>'
            f'<table><tr><th>Serie</th><th>Siste</th><th>5-årssnitt</th><th>Avvik</th><th>5-års spenn</th><th>Endring uke</th><th>1 år</th><th>Uke t.o.m.</th></tr>{rows}</table>'
            '<p class="mut">Pålitelighet: offisiell (EIA), revideres lite. Historisk test 2001–2026: avviket forutsa <b>ikke</b> Brent/WTI eller energiaksjer robust '
            '(fortegn skiftet mellom perioder) – kontekst, ikke signal.</p></div>')


def taiwan_html(snap: dict) -> str:
    tw = snap.get("taiwan_revenue") or {}
    if not tw:
        return ""
    lt, se = tw.get("latest") or {}, tw.get("series") or {}
    firms = "".join(f'<tr><td>{E(f["code"])}</td><td>{E(f["name"])}</td><td>{num(f["rev_bn_twd"], 1)}</td><td>{pct(f.get("yoy"))}</td></tr>' for f in tw.get("firms", []))
    lines = [("AI/halvleder-kurv (12 selskaper)", "basket"), ("AI-servere (Quanta, Wistron, Wiwynn, Foxconn)", "ai_server"), ("Minne (Nanya, Winbond)", "memory"), ("TSMC", "tsmc"), ("Bredde: andel av alle børsnoterte med vekst å/å", "breadth")]
    summ = "".join(f'<tr><td>{E(l)}</td><td>{pct(lt.get(k))}</td><td>{_spark(se.get(k))}</td></tr>' for l, k in lines)
    return (f'<div class="card tw" id="taiwan"><h2 style="margin-top:0">🔌 Forsyningskjede-radar: Taiwans månedlige omsetning ({E(tw.get("month"))})</h2>'
            '<p class="mut">Taiwanske selskaper må rapportere forrige måneds omsetning innen den 10. – uker før amerikanske kvartalstall. Vekst mot samme måned i fjor (å/å). Kilde: MOPS/TWSE (offisiell).</p>'
            f'<table><tr><th>Indikator</th><th>Siste å/å</th><th>24 mnd</th></tr>{summ}</table>'
            f'<p class="mut">Akselerasjon siste 3 mnd vs 3 mnd før: {pct(tw.get("accel_3m"))}.</p>'
            f'<details><summary>Selskapene i kurven</summary><table><tr><th>Kode</th><th>Selskap</th><th>Omsetning (mrd. TWD)</th><th>å/å</th></tr>{firms}</table></details>'
            '<p class="mut">Test 2013–2026: kurvens vekst/akselerasjon forutsa <b>ikke</b> SMH/TSM/EWT robust. Unntak å følge med på: akselerasjon i minneomsetning '
            '→ Micron neste måned (+11,7 pp topp- mot bunntredjedel, t=3,2 etter 2020, men svak før 2020 – ikke bekreftet).</p></div>')


def _theme_names(keys):
    from .themes_no import NO
    return ", ".join(NO.get(k, {}).get("name", k) for k in keys or [])


def policy_html(snap: dict) -> str:
    al = snap.get("policy_alerts") or []
    if not al:
        return ""
    al = sorted(al, key=lambda a: a.get("date") or "", reverse=True)
    al = sorted(al, key=lambda a: (0 if a.get("hot") and a.get("themes") else 1 if a.get("hot") else 2))  # stable: newest first within group
    def row(a):
        return (f'<tr><td class="nw">{E(a["date"])}</td><td>{"🔥 " if a.get("hot") else ""}{E(a["kind"])}</td><td><a href="{E(a["url"])}">{E(a["title"][:180])}</a>'
                + (f'<br><span class="mut">Tema: {E(_theme_names(a.get("themes")))}</span>' if a.get("themes") else "") + "</td></tr>")
    head = "<tr><th>Dato</th><th>Type</th><th>Dokument</th></tr>"
    top, rest = al[:12], al[12:60]
    n_hot = sum(1 for a in al if a.get("hot"))
    return (f'<div class="card tw" id="politikk"><h2 style="margin-top:0">⚖️ Politikkvarsler: eksportkontroll, sanksjoner, toll (10 dager)</h2>'
            '<p class="mut">USA: Federal Register (BIS eksportkontroll/Entity List, ITA antidumping, OFAC, USTR) – publiseres kl. 06 ET (~12 norsk tid). EU: Rådets pressemeldinger og EU-tidende (sanksjoner). '
            f'🔥 = nøkkelord med markedsrelevans (halvledere, Russland/Iran/Kina, olje, skip, toll). {len(al)} dokumenter, {n_hot} 🔥. Viktigste først.</p>'
            f'<table>{head}{"".join(row(a) for a in top)}</table>'
            + (f'<details><summary>Vis {len(rest)} flere</summary><table>{head}{"".join(row(a) for a in rest)}</table></details>' if rest else "")
            + '<p class="mut">Pålitelighet: offisielle kilder – høy. Ikke backtestet (kort historikk i verktøyet); ment som tidligvarsel.</p></div>')


# ---------------------------------------------------------------- Oslo insider
def oslo_insider_html(snap: dict) -> str:
    rows = snap.get("newsweb_insider_classified") or []
    if not rows:
        return ""
    cnt = {}
    for r in rows:
        cnt[r["kind"]] = cnt.get(r["kind"], 0) + 1
    tr = "".join(f'<tr><td class="nw">{E(str(r["published"])[:10])}</td><td><b>{E(r.get("issuer"))}</b></td><td><span class="kind {E(str(r["kind"]).split()[0])}">{E(r["kind"])}</span></td>'
                 f'<td>{"–" if not _fl(r.get("value_nok")) else num(_fl(r["value_nok"])/1e6, 2) + " mill."}</td><td><a href="{E(r["url"])}">{E(r["title"])}</a></td></tr>' for r in rows[:60])
    return (f'<div class="card tw" id="innside"><h2 style="margin-top:0">Innsidehandler med retning (Newsweb, 21 dager)</h2>'
            f'<p class="mut">Retningen er lest automatisk fra meldingsteksten: kjøp / salg / tegning (emisjon) / annet (opsjoner, aksjeprogram, lån) / ukjent (bare vedlegg). '
            f'Stikkprøve: 20 av 20 kjøp/salg riktig klassifisert. I dag: {E(", ".join(f"{v} {k}" for k, v in cnt.items()))}.</p>'
            f'<p class="mut">Test (6 418 meldinger 2021–2026, inngang dagen etter): verken innsidekjøp, store kjøp (≥ 1 mill. NOK) eller kjøpsklynger har gitt robust '
            f'meravkastning mot OSEBX etter kostnader. Derfor vises dette her, men gir <b>ikke</b> poeng i Kjøp-reglene. <a href="kilder.html#natt">Se testen</a>.</p>'
            f'<table><tr><th>Dato</th><th>Selskap</th><th>Retning</th><th>Verdi NOK</th><th>Melding</th></tr>{tr}</table></div>')


# ---------------------------------------------------------------- thesis, base rates, entry/exit plan (signaltool/plan.py)
from . import plan as P


def thesis_html(e: dict, themes: dict) -> str:
    th = P.thesis(e, themes)
    return (f'<div class="card thesis" id="tese"><h2 style="margin-top:0">Testbar tese</h2>'
            f'<p><b>Tese:</b> {E(th["tese"])}</p><p class="ok-line"><b>✔ Bekreftes hvis</b> {E(th["bekreftes"])}</p>'
            f'<p class="no-line"><b>✘ Avkreftes hvis</b> {E(th["avkreftes"])}</p>'
            '<p class="mut">Regelbasert mal fylt med dagens tall. Sjekk punktene igjen etter neste rapport eller ved stoppnivået.</p></div>')


def _br_row(k: str, b: dict) -> str:
    if not b or not b.get("n"):
        return f'<tr><td>{E(P.BR_LABEL.get(k, k))}</td><td colspan="5" class="mut">Ingen historikk. {E((b or {}).get("note", ""))}</td></tr>'
    def cell(h):
        if b.get(f"hit{h}") is None:
            return '<span class="mut">for få</span>'
        return f'{b[f"hit{h}"]*100:.0f} % · {pct(b[f"med{h}"])} / {pct(b[f"mean{h}"])}'
    base = k.startswith("baseline")
    net = "–" if b.get("net60") is None else (f'{pct(b["net60"])} <span class="mut">(−{b.get("cost", 0)*100:.2f} %)</span>'
                                             + (f'<div class="mut">60 d brutto før/etter 2016: {pct(b.get("mean60_is"))} (t {b.get("t60_is", 0):.1f}) / '
                                                f'{pct(b.get("mean60_oos"))} (t {b.get("t60_oos", 0):.1f})</div>' if b.get("mean60_is") is not None else ""))
    return (f'<tr{" class=mut" if base else ""}><td>{E(P.BR_LABEL.get(k, k))}</td><td>{b["n"]:,}'.replace(",", " ") + f'</td><td>{cell(20)}</td><td>{cell(60)}</td>'
            f'<td>{net}</td><td class="nw">{E(b.get("period", ""))} · {E(b.get("bench", ""))}</td></tr>')


BR_HEAD = ('<tr><th>Signal / kategori</th><th>Tilfeller</th><th>20 d: slo indeks · median / snitt</th><th>60 d: slo indeks · median / snitt</th>'
           '<th>60 d netto etter kostnad</th><th>Periode · indeks</th></tr>')


def base_rate_html(e: dict) -> str:
    br = P.base_rates()
    if not br:
        return '<div class="card"><h2 style="margin-top:0">Historisk treffrate</h2><p class="mut">Ingen historikk beregnet (kjør python -m signaltool.backtest.base_rates).</p></div>'
    rows = "".join(_br_row(k, br.get(k)) for k in P.signal_keys(e))
    return (f'<div class="card" id="treffrate"><h2 style="margin-top:0">Historisk treffrate</h2><div class="tw"><table class="br">{BR_HEAD}{rows}</table></div>'
            '<p class="mut">Fra våre egne tester: meravkastning mot indeks fra inngang dagen etter signalet, før kurtasje. «Slo indeks» = andel tilfeller med positiv meravkastning. '
            'Sammenlign med den grå raden (tilfeldig aksje) – et signal er bare nyttig hvis det gjør det klart bedre. '
            '<a href="../kilder.html#treffrate">Alle signaler og forbehold</a>.</p></div>')


def base_rate_table_html() -> str:
    br = P.base_rates()
    if not br:
        return ""
    rows = "".join(_br_row(k, br.get(k)) for k in P.BR_ORDER)
    notes = "".join(f'<li><b>{E(P.BR_LABEL.get(k, k))}:</b> {E((br.get(k) or {}).get("note", ""))}</li>' for k in P.BR_ORDER if (br.get(k) or {}).get("note"))
    return (f'<div class="card" id="treffrate"><h2 style="margin-top:0">Historisk treffrate per signal og kategori</h2>'
            f'<p>{E(br.get("_meta", {}).get("what", ""))}</p><div class="tw"><table class="br">{BR_HEAD}{rows}</table></div>'
            f'<details><summary>Definisjoner og forbehold</summary><ul class="ev">{notes}</ul></details>'
            '<p class="mut">Kode: signaltool/backtest/base_rates.py (bruker bare data som allerede er lastet ned av de andre testene).</p></div>')


def plan_html(e: dict, compact: bool = False) -> str:
    lv = P.levels(e)
    d = e.get("decision") or {}
    cur = d.get("currency") or ""
    if not lv:
        return ""
    lvl = P._lvl
    if not lv.get("stop"):
        return (f'<div class="card" id="plan"><h2 style="margin-top:0">Eksempelplan</h2><p>Inngangssone: {lvl(lv["entry_lo"])}–{lvl(lv["entry_hi"])} {E(cur)} ({E(lv["entry_how"])}). '
                'Ingen fornuftig stopp under inngangssonen (kursen ligger under både 50-dagers snitt og 2×ATR-nivået) – derfor ingen størrelsesberegning.</p></div>')
    pk = P._primary(e)
    br = P.base_rates().get(pk or "", {})
    hist = ""
    if br.get("med60") is not None:
        hp = lv["entry"] * (1 + br["med60"])
        hist = (f'Historisk median meravkastning over 60 d for «{E(P.BR_LABEL[pk])}» er {pct(br["med60"])} (≈ {lvl(hp)} {E(cur)}). '
                + ("Målet på 2:1 er derfor ambisiøst i forhold til historikken." if hp < lv["target_rr"] else "Historikken støtter et mål i denne størrelsen."))
    size = lv.get("size")
    val = None if size is None else EXAMPLE_VALUE(size)
    shares = None if size is None or not lv["entry"] else int(val / lv["entry"])
    red = (" (" + "; ".join(lv["size_reasons"]) + ")") if lv.get("size_reasons") else ""
    rows = [("Inngangssone", f'{lvl(lv["entry_lo"])}–{lvl(lv["entry_hi"])} {E(cur)} <span class="mut">({E(lv["entry_how"])})</span>'),
            ("Stopp / ugyldiggjøring", f'{lvl(lv["stop"])} {E(cur)} <span class="mut">({E(lv["stop_name"])}, strengeste nivå under inngang; {lv["stop_dist"]*100:.1f} % risiko)</span>'),
            ("Første mål (2:1)", f'{lvl(lv["target_rr"])} {E(cur)} <span class="mut">(+{(lv["target_rr"]/lv["entry"]-1)*100:.1f} %)</span>'),
            ("Posisjonsstørrelse", "–" if size is None else f'{size*100:.1f} % av porteføljen{E(red)} <span class="mut">= 1 % risiko ÷ {lv["stop_dist"]*100:.1f} % stoppavstand, maks {P.MAX_POSITION*100:.0f} %</span>')]
    if compact:
        return (f'<div class="plan-line">Eksempel: inngang {lvl(lv["entry_lo"])}–{lvl(lv["entry_hi"])}, stopp {lvl(lv["stop"])}, mål {lvl(lv["target_rr"])}, '
                f'størrelse {"–" if size is None else f"{size*100:.1f} %"} av porteføljen.</div>')
    ex = ""
    if size is not None:
        loss = val * lv["stop_dist"]
        ex = (f'<p class="mut">Regneeksempel med portefølje på {_sp(P.EXAMPLE_PORTFOLIO)} {E(cur or "kr")}: kjøp for ca. {_sp(val)} {E(cur)} (≈ {shares} aksjer). '
              f'Treffer stoppen, er tapet ca. {_sp(loss)} {E(cur)} ≈ {loss / P.EXAMPLE_PORTFOLIO * 100:.1f} % av porteføljen.</p>')
    tab = "<table>" + "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in rows) + "</table>"
    return (f'<div class="card" id="plan"><h2 style="margin-top:0">Eksempelplan: inngang, stopp, mål og størrelse</h2>'
            f'<div class="warnbox">Eksempelberegning – ikke råd. Mekanisk regel fylt med dagens kurs, ATR og snitt; tar ikke hensyn til din økonomi, skatt eller kurtasje.</div>'
            f'{tab}<p>{hist}</p>{ex}<p class="mut">{P.net_note(e)} Porteføljeregler: {P.MIN_POSITIONS[0]}–{P.MIN_POSITIONS[1]} posisjoner, '
            f'maks {P.MAX_SECTOR*100:.0f} % per sektor, maks {P.MAX_POSITION*100:.0f} % per aksje.</p></div>')


def _sp(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def EXAMPLE_VALUE(size: float) -> float:
    return P.EXAMPLE_PORTFOLIO * size


CSS_EXTRA += """
.thesis .ok-line{border-left:3px solid #3fb950;padding-left:8px}
.thesis .no-line{border-left:3px solid #f85149;padding-left:8px}
table.br td,table.br th{font-size:13px}
.warnbox{background:#2d2410;border:1px solid #6e5410;color:#e3c47a;border-radius:6px;padding:6px 10px;font-size:13px;margin-bottom:8px}
.plan-line{font-size:12px;color:#9aa4b2;margin-top:2px}
.tline{font-size:12px;color:#c9d1d9;margin-top:2px}
"""


# ---------------------------------------------------------------- flags, regime, portfolio rules, honesty, dropped strategies
LEVEL_CLASS = {"sterk": "hi", "moderat": "mid", "svak": "lo"}
GENERIC_FLAG_INFO = {  # existing risk rules - caution rules, not separately backtested as signals
    "short": ("Økende short", "red", "forsiktighetsregel", "Høy/økende short-andel har i litteraturen predikert lav avkastning (Asquith m.fl. 2005); vår korte Oslo-test: −1 til −4 % (t ≈ −1,8)."),
    "crash": ("Nylig krasj", "red", "forsiktighetsregel", "≥ 20 % fall på 20 handelsdager – ikke testet som eget signal."),
    "illiquid": ("Lav likviditet", "red", "forsiktighetsregel", "Spread og kurtasje spiser små effekter; tallene i testene gjelder likvide aksjer."),
    "penny": ("Pennyaksje", "red", "forsiktighetsregel", "Under ca. 1 USD – støyete kurser, store spreader."),
    "volume_only": ("Bare volum/kurs", "red", "forsiktighetsregel", "Uvanlig volum alene: 52 % slo indeks (median +0,5 %) mot 52 % (+0,4 %) for tilfeldig aksje – ingen fordel."),
}


def _flag_info(k):
    from .oslo_flags import FLAG_INFO
    return FLAG_INFO.get(k) or GENERIC_FLAG_INFO.get(k) or (k, "red", "–", "")


def evidence_badge(level: str) -> str:
    cls = next((c for w, c in LEVEL_CLASS.items() if str(level).startswith(w)), "mid")
    return f'<span class="rel {cls}">evidens: {E(level)}</span>'


def flags_html(e: dict) -> str:
    """Ticker page: every red/yellow flag and info tag with its evidence level."""
    rows = []
    keymap = dict(zip(e.get("cat_flag_keys") or [], e.get("cat_flags") or []))
    for k, txt in keymap.items():
        rows.append(("🚩", k, txt))
    for k, txt in (e.get("cat_warnings") or {}).items():
        rows.append(("🟡" if _flag_info(k)[1] == "yellow" else "ⓘ", k, txt))
    for k, txt in (e.get("cat_info") or {}).items():
        rows.append(("🏷️", k, txt))
    osl = e.get("oslo") or {}
    if not rows:
        if not e["ticker"].endswith(".OL"):
            return ""
        return ('<div class="card" id="flagg"><h2 style="margin-top:0">Røde flagg og merker</h2><p>Ingen røde eller gule flagg i dag.</p>'
                '<p class="mut">Oslo-flaggene (svak kurs, negativt driftsresultat, rettet emisjon, høy volatilitet) er det mest robuste sidens tester har funnet – '
                'de sier hva du bør unngå, ikke hva du bør kjøpe.</p></div>')
    kind_no = {"red": "rødt flagg – blokkerer Kjøp", "yellow": "gult flagg – halver størrelsen", "note": "tillegg", "info": "info-merke – ikke kjøpssignal"}
    lis = ""
    for icon, k, txt in rows:
        lab, kind, lvl, ev = _flag_info(k)
        lis += (f'<tr><td>{icon} <b>{E(lab)}</b><div class="mut">{E(kind_no.get(kind, kind))}</div></td><td>{E(txt)}</td>'
                f'<td>{evidence_badge(lvl)}<div class="mut">{E(ev)}</div></td></tr>')
    src = ""
    if osl.get("placement"):
        src += f'<li>Emisjonsmelding: <a href="{E(osl["placement"].get("url"))}">{E(osl["placement"].get("title"))}</a> ({E(osl["placement"].get("date"))})</li>'
    if osl.get("buyback"):
        src += f'<li>Egne aksjer: <a href="{E(osl["buyback"].get("url"))}">{E(osl["buyback"].get("title"))}</a> ({E(osl["buyback"].get("date"))})</li>'
    return (f'<div class="card" id="flagg"><h2 style="margin-top:0">Røde flagg og merker</h2><div class="tw"><table>'
            f'<tr><th>Flagg</th><th>I dag</th><th>Evidensnivå (våre tester)</th></tr>{lis}</table></div>'
            + (f'<ul class="ev">{src}</ul>' if src else "")
            + '<p class="mut">Tallene er meravkastning mot snittaksjen over 60 handelsdager fra egne tester (strategy-research). '
              'Oslo-kursflaggene rangeres blant likvide Oslo-aksjer (≥ ~2 MNOK/dag). <a href="../kilder.html#kategorier">Reglene</a>.</p></div>')


def regime_html(snap: dict) -> str:
    reg = snap.get("regime") or {}
    if not reg:
        return ""
    rows = ""
    for v in reg.values():
        state = ('<span class="down">under</span>' if v["below"] else '<span class="up">over</span>')
        rows += (f'<tr><td><b>{E(v["name"])}</b></td><td>{num(v["last"])} {state} 10-mnd snitt {num(v["sma10m"])} ({pct(v["dist"])})</td>'
                 f'<td>{ppct(v["vol1m"])}{" ⚠️" if v["high_vol"] else ""}</td><td>{"🟠 halver nye posisjoner" if v["risk_off"] else "🟢 normal størrelse"}</td>'
                 f'<td class="mut">{E(v["asof"])}</td></tr>')
    return (f'<div class="card" id="regime"><h2 style="margin-top:0">Markedsregime</h2><div class="tw"><table>'
            f'<tr><th>Indeks</th><th>Trend (10 måneder)</th><th>Volatilitet 1 mnd (årlig)</th><th>Regel</th><th>Data t.o.m.</th></tr>{rows}</table></div>'
            '<p class="mut">Regel: er indeksen under sitt 10-måneders snitt <i>eller</i> 1-måneds volatilitet over 25 %, halveres størrelsen på <b>nye</b> posisjoner i eksempelplanen '
            '(for US-aksjer S&amp;P 500, for Oslo OSEBX). <b>Ikke et salgssignal.</b> Historikk: 10-måneders-regelen kuttet verste fall for SPY 2007–2026 (−22 % mot −51 %), '
            'men ga lavere avkastning (8,4 % mot 11,0 % per år); for OSEBX 2016–2026 reduserte den ikke engang fallet. Utenfor ASK koster hvert salg skatt.</p></div>')


def honesty_html(pre: str = "") -> str:
    return ('<div class="card hl" id="aerlig"><h2 style="margin-top:0">Ærlig status</h2>'
            '<p><b>Vi har ikke funnet noe robust kjøpssignal.</b> Av over 200 testede regler og varianter (bøker, forum, egne ideer – USA og Oslo; tre testrunder) har ingen kjøpsregel '
            'klart kravet om |t| ≥ ~3 med samme fortegn både før og etter 2016/2018, og etter kurtasje. Det beste kjøpssignalet, «sterk kvartalsrapport» (PEAD), '
            'gir med punkt-i-tid-data bare ca. +0,6 pp brutto over 60 dager og omtrent null etter kostnader – det er merket <b>eksperimentelt / svak evidens</b>.</p>'
            '<p><b>Sidens styrke er å hjelpe deg å unngå svake aksjer:</b> på Oslo Børs har svak kurs (laveste 20 % momentum eller langt under 52-ukers topp) gjort det '
            '3–4 % dårligere enn snittet over 60 dager i begge testperioder, og tapsbringende selskaper, rettede emisjoner og høy volatilitet peker samme vei. '
            f'<a href="{pre}kilder.html#droppet">Testet og droppet</a> · <a href="{pre}kilder.html#kategorier">Reglene</a></p></div>')


def portfolio_rules_html() -> str:
    return ('<div class="card" id="portefolje"><h2 style="margin-top:0">Porteføljeregler (eksempel)</h2><ul class="ev">'
            f'<li><b>Maks {P.MAX_POSITION*100:.0f} % per posisjon</b> (ingen signal her har t ≥ 3; Kelly med realistisk ~1 pp forventning tilsier små, like store posisjoner).</li>'
            '<li><b>Halv størrelse</b> for aksjer med høy volatilitet (over 50 % årlig, eller høyeste 20 % på Oslo Børs) og når markedsregimet er «halver».</li>'
            f'<li><b>{P.MIN_POSITIONS[0]}–{P.MIN_POSITIONS[1]} posisjoner</b> før en effekt på ~1–3 pp kan slå gjennom, og <b>maks {P.MAX_SECTOR*100:.0f} % i én sektor</b> (Oslo er tung på energi og sjømat).</li>'
            '<li>Hold i signalets horisont (~60 handelsdager) – hyppig handel skader personinvestorer.</li>'
            f'<li><b>Netto etter kostnad og skatt:</b> US-aksjer kan ikke ligge på ASK; vanlig konto skatter realisert gevinst med {P.TAX*100:.2f} % og tur-retur koster ca. '
            f'{P.COST_US[0]*100:.1f}–{P.COST_US[1]*100:.1f} %. Et signal på +1 pp brutto blir ≈ +0,25 pp etter 0,75 % kostnad og ≈ +0,16 pp etter skatt. '
            'Oslo-aksjer på ASK: skatten utsettes, men kurtasje og spread gjelder fortsatt.</li></ul></div>')


DROPPED = [
    ("Minervini-trendmal / CAN SLIM (kurs + relativ styrke)", "USA punkt-i-tid −0,7 % (t −1,1) / −0,7 % (t −1,4) per 60 d; Oslo +0,1 % / +0,9 % (t 1,1). Ingen fordel."),
    ("Momentum og 52-ukers topp som kjøp i USA", "Punkt-i-tid: momentum topp −0,8 % (t −1,3) / +0,2 % (t 0,3); nær 52-ukers topp −0,6 % / −0,5 %. Gevinstene i dagens S&P 500 var overlevelsesskjevhet."),
    ("Magic Formula (Greenblatt) som kjøp", "2022–26: USA topp −0,6 % (t −0,6), Oslo topp +0,8 % (t 0,6). Bare bunnen (tapsbringende) brukes – som rødt flagg."),
    ("Piotroski F-score / brutto lønnsomhet (GP/A)", "F-score 8–9: USA −1,5 % (t −1,5), Oslo +0,4 % (t 0,3); GP/A topp +0,2 % / −0,4 %. Kun 2022–26, ikke punkt-i-tid-regnskap."),
    ("Dual Momentum (Antonacci GEM)", "2014–2026: 8,2 % per år mot SPY 13,7 %."),
    ("Faber 10-måneders timing som kjøp/salg", "SPY 2007–26: mindre fall (−22 % mot −51 %), men 8,4 % mot 11,0 % per år; OSEBX 2016–26 7,7 % mot 12,1 %. Brukes bare til størrelse (regimeboksen)."),
    ("Analytikerrevisjoner (rating- og kursmålsendringer)", "126 442 endringer 2019–26: topp 20 % −0,5 % (t −1,1) / −0,3 % (t −0,6). Kursmål følger kursen."),
    ("Frog-in-the-pan og kortsiktig reversering", "Ingen forskjell i USA; reversering netto −6 %/år (t −1,9) i USA og negativ i Oslo."),
    ("«Kjøp krigen» / geopolitiske sjokk", "Høyere geopolitisk risiko henger sammen med lavere avkastning (Caldara & Iacoviello); våre GDELT-, sund- og Polymarket-tester fant ingen ledende effekt."),
    ("Short-squeeze-screens", "Høy short-andel og «days to cover» predikerer lav avkastning; Oslo-test −1 til −4 % (t ≈ −1,8). Brukes bare som rødt flagg."),
    ("WSB/Reddit-DD og forumtips (Hegnar, Shareville)", "DD-innlegg forutsa avkastning bare før januar 2021 (Bradley m.fl. 2024); pump-and-dump er dokumentert på norske forum."),
    ("Lead-lag mot andre markeder (Brent, USD/NOK, S&P 500, XLE, OIH, kobber, laks, tørrbulk)", "Sterk i første periode (|t| 3,1–4,8), forsvant eller snudde etterpå."),
    ("Oslo-PEAD (kursreaksjon ≥ +5 % på rapportdagen)", "−2,7 % (t −1,5) i 2013–18 og +2,1 % (t 1,5) i 2019–26; i likvide aksjer negativ (−4,1 %, t −3,9). Ikke robust – vises ikke."),
    ("PEAD-filtre (omsetning, egen historikk, analytikerdekning, størrelse, fredag, røde flagg)", "Ingen robust forbedring av sterk-rapport-signalet; bare høy volatilitet peker samme vei (t 1,2–1,4), derfor PEAD-S som eksperiment."),
    ("Innsidekjøp (USA-klynger og Oslo)", "USA: 44 % slo indeks, median −2,8 % over 60 d; Oslo 6 418 meldinger uten robust meravkastning. Vises, men gir ikke Kjøp."),
    ("Nye kurs-/volumflagg (MAX, idiosynkratisk vol, Amihud, intradag)", "48–83 % overlapp med dagens flagg – dobbelttelling."),
    ("Åpningsgap / tidssone Oslo og utbyttefangst", "Gapet er mikrostruktur (forsvinner i likvide aksjer); utbyttefangst spises av skatt."),
    ("Småselskapspremie Oslo, Rule of 40, PEG, Seeking Alpha", "For dyrt å handle eller uten dokumentert fordel / ikke testbart gratis."),
]


def dropped_html() -> str:
    lis = "".join(f"<li><b>{E(a)}:</b> {E(b)}</li>" for a, b in DROPPED)
    return ('<div class="card" id="droppet"><h2 style="margin-top:0">Testet og droppet</h2>'
            '<p><b>Konklusjon: vi fant ikke noe robust kjøpssignal.</b> Sidens styrke er å unngå svake aksjer (røde flagg), ikke å finne vinnere. '
            'Listen under er strategier fra bøker, forum og egne ideer som er testet og <i>ikke</i> bygget inn – med én linje om hvorfor. '
            'Tall: meravkastning over 60 handelsdager, periode 1 / periode 2 (t-verdi), fra strategy-research/RAPPORT*.md.</p>'
            f'<ul class="ev">{lis}</ul>'
            '<p class="mut">Krav for «bygg inn»: samme fortegn i begge perioder og |t| ≥ ~3, rimelig forklaring og gevinst etter kostnader. '
            'Med ~70 + ~700 t-verdier testet er t ≈ 2 i én periode det man venter av ren tilfeldighet.</p></div>')


CSS_EXTRA += """
#flagg td:first-child{min-width:12em}#flagg td:last-child{max-width:28em}
"""
