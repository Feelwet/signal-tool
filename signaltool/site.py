"""Static website generator (Norwegian UI). Output: site/ (plain HTML/CSS, no JS frameworks) -> hostable on
GitHub Pages / Netlify / Cloudflare Pages for free."""
from __future__ import annotations
import html, json, re, shutil
from pathlib import Path
from .config import ROOT, REPORTS
from . import categories as C
from . import site_extra as X
from . import theme_maps as TM
from . import site_quality as Q

SITE = ROOT / "site"
E = lambda x: html.escape("" if x is None else str(x))

CSS = """
/* Dark theme (default). Contrast vs --card #161b22: ink 14.6:1, mut 7.2:1, acc 8.1:1, up 7.6:1, down 7.1:1, warn 8.9:1 (WCAG AA+). */
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--card2:#1c2330;--ink:#e6edf3;--mut:#9ea9b5;--acc:#6cb6ff;--acc-bg:rgba(108,182,255,.14);
--up:#4ac26b;--down:#ff8078;--line:#2d333b;--warn:#e3b341;--hdr:#060a10;--pill:#262d38}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
.app{display:flex;min-height:100vh;align-items:stretch}
.side{position:sticky;top:0;align-self:flex-start;width:240px;flex:0 0 240px;height:100vh;overflow:auto;background:var(--hdr);color:#fff;padding:16px 14px;border-right:1px solid var(--line);display:flex;flex-direction:column;gap:10px}
.side a{color:#fff;text-decoration:none}.side .brand{font-weight:700;font-size:1.1rem;display:block}
.side .gen{color:#a8b5c4;font-size:.78rem;line-height:1.35;display:block}
.side nav{display:flex;flex-direction:column;gap:2px;margin-top:4px;font-size:.92rem}
.side nav a{color:#cfd9e4!important;padding:7px 10px;border-radius:8px}
.side nav a:hover,.side nav a.on{color:#fff!important;background:rgba(108,182,255,.14)}
.side .tools{margin-top:auto;padding-top:12px;border-top:1px solid var(--line);display:flex;flex-direction:column;gap:6px}
.side .tools button{background:var(--pill);color:#d5dde6;border:1px solid #333b47;border-radius:8px;padding:6px 10px;font:inherit;cursor:pointer;text-align:left}
.side .tools button:hover{background:rgba(108,182,255,.14);color:#fff}
.content{flex:1;min-width:0;display:flex;flex-direction:column}
main{max-width:1100px;width:100%;margin:0 auto;padding:16px;flex:1}
details.fold{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:0;margin:0 0 14px}
details.fold>summary{list-style:none;cursor:pointer;padding:12px 16px;display:flex;align-items:center;gap:8px;user-select:none}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary::before{content:"▸";color:var(--acc);font-size:.85rem;width:1em;flex:0 0 auto;transition:transform .12s}
details.fold[open]>summary::before{transform:rotate(90deg)}
details.fold>summary h2,details.fold>summary h3{margin:0;font-size:1.15rem;flex:1}
details.fold .fold-body{padding:0 16px 14px}
details.fold .fold-body>:first-child{margin-top:0}
.side-toggle{display:none;background:transparent;border:1px solid var(--line);color:#cfd9e4;border-radius:8px;padding:6px 10px;font:inherit;cursor:pointer}
header.top{display:none;background:var(--hdr);color:#fff;padding:10px 14px;border-bottom:1px solid var(--line);align-items:center;gap:10px}
header.top .brand{font-weight:700;color:#fff;text-decoration:none;flex:1}
header.top .gen{color:#a8b5c4;font-size:.78rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 14px}
.card.hl{border-left:4px solid var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
h1{font-size:1.5rem;margin:.2rem 0 .6rem;color:#f3f6f9}h2{font-size:1.2rem;margin:1.2rem 0 .6rem;color:#f3f6f9}h3{font-size:1.05rem;margin:.2rem 0 .4rem}
a{color:var(--acc)}a:visited{color:#b392f0}a:hover{color:#9dcbff}.mut{color:var(--mut);font-size:.9rem}.up{color:var(--up)}.down{color:var(--down)}
.score{display:inline-block;min-width:3.2em;text-align:center;font-weight:700;border-radius:6px;padding:2px 8px;background:var(--acc-bg);color:var(--acc);border:1px solid rgba(108,182,255,.35)}
.score.hot{background:rgba(255,128,120,.14);color:#ff9a92;border-color:rgba(255,128,120,.45)}.score.warm{background:rgba(227,179,65,.14);color:var(--warn);border-color:rgba(227,179,65,.45)}
.bar{height:8px;background:#262d38;border-radius:4px;overflow:hidden}.bar>i{display:block;height:100%;background:linear-gradient(90deg,#3d8bdb,var(--acc))}
table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-weight:600;color:var(--mut);white-space:nowrap;background:var(--card2)}tr:hover td{background:rgba(255,255,255,.025)}.tw{overflow-x:auto}
.pill{display:inline-block;font-size:.8rem;padding:1px 8px;border-radius:999px;background:var(--pill);color:#d5dde6;border:1px solid #333b47;margin:2px 4px 2px 0;text-decoration:none}
a.pill{color:var(--acc)}
.warnbox{background:#2a2213;border:1px solid #6b5520;color:#f2dfae;border-radius:10px;padding:10px 14px;margin:0 0 14px;font-size:.92rem}
.ok{color:var(--up)}.fail{color:var(--down)}ul.ev{padding-left:18px;margin:.3rem 0}ul.ev li{margin:.2rem 0}
.rel{display:inline-block;font-size:.78rem;padding:1px 8px;border-radius:8px;border:1px solid;white-space:normal}
.rel.hi{color:var(--up);background:rgba(74,194,107,.12);border-color:rgba(74,194,107,.4)}
.rel.mid{color:var(--warn);background:rgba(227,179,65,.12);border-color:rgba(227,179,65,.4)}
.rel.lo{color:var(--down);background:rgba(255,128,120,.12);border-color:rgba(255,128,120,.4)}
.cat{display:inline-block;font-size:.8rem;font-weight:700;padding:1px 9px;border-radius:6px;border:1px solid;white-space:nowrap}
.cat small{font-weight:400;font-size:.72rem;margin-left:3px;opacity:.9}
.cat.kjop{color:#56d364;background:rgba(86,211,100,.13);border-color:rgba(86,211,100,.5)}
.cat.hold{color:var(--acc);background:var(--acc-bg);border-color:rgba(108,182,255,.5)}
.cat.watch{color:var(--warn);background:rgba(227,179,65,.12);border-color:rgba(227,179,65,.45)}
.why{font-size:.82rem;color:var(--mut);margin-top:3px;min-width:18em;max-width:34em}
.catnote{font-size:.8rem;color:#c9b27a;margin:.4rem 0 0}
td.rule-ok{color:var(--up)}td.rule-no{color:var(--down)}td.rule-na{color:var(--mut)}
pre{background:#0b0f15;border:1px solid var(--line);border-radius:8px;padding:10px;color:#d5dde6}
footer{max-width:1100px;margin:10px auto 30px;padding:0 16px;color:var(--mut);font-size:.85rem}.content footer{width:100%}
svg.spark{vertical-align:middle}svg.spark polyline{stroke:var(--acc)}
@media (max-width:900px){
.app{flex-direction:column}.side{position:fixed;inset:0 auto 0 0;transform:translateX(-105%);transition:transform .18s ease;z-index:40;height:100vh;box-shadow:8px 0 24px rgba(0,0,0,.45)}
body.nav-open .side{transform:none}body.nav-open::after{content:"";position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:30}
header.top{display:flex}.side-toggle{display:inline-block}
}
@media (max-width:600px){body{font-size:15px}main{padding:10px}th,td{padding:5px}}
"""

DISCLAIMER = ("<b>Ikke finansiell rådgivning.</b> Automatisk informasjonsverktøy basert på offentlige data og enkle, "
              "transparente regler. Signaler kan være feil, forsinket eller allerede priset inn. Gjør alltid egne vurderinger.")

COMP_SHORT = {"gdelt_events": "GDELT-hendelser", "gdelt_urls": "Nyhetsvolum (GDELT)", "gdelt_tone": "Negativ tone",
              "news_rss": "RSS-overskrifter", "google_trends": "Google-søk", "sec_8k": "SEC 8-K", "prediction_mkts": "Prediksjonsmarked",
              "price_volume": "Kurs/volum", "ofac": "Sanksjoner (OFAC)", "physical_oil": "Fysisk olje"}
POINT_NO = {"insider_cluster": "Innsidekjøp (USA)", "congress_buys": "Kongresskjøp", "ose_contracts": "Kontrakter (Newsweb)",
            "ose_insider_notices": "Innsidemeldinger (Newsweb)", "federal_award": "Offentlig kontrakt (USA)",
            "unusual_volume": "Uvanlig volum", "price_move": "Uvanlig kursbevegelse", "theme_attention": "Tema-oppmerksomhet",
            "reddit_mentions": "Reddit-omtale", "dod_contract": "DoD-kontrakt", "pead": "Sterk kvartalsrapport"}


def slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", t)


def pct(x, d=1):
    if x is None:
        return "–"
    cls = "up" if x > 0 else "down" if x < 0 else ""
    return f'<span class="{cls}">{x*100:+.{d}f}%</span>'


def num(x, d=2):
    return "–" if x is None else f"{x:.{d}f}"


CAT_LABEL = {"kjop": 'Kjøp<small>kandidat</small>', "hold": "Hold", "watch": "Watchlist"}
CAT_NOTE = ('<p class="catnote">ⓘ Kategoriene Kjøp-kandidat / Hold / Watchlist er regelbaserte og mekaniske – ikke personlig '
            'finansiell rådgivning, og <b>ikke bevist å slå markedet</b> (ingen kjøpssignal har robust støtte i våre tester; «sterk kvartalsrapport» er eksperimentell med svak evidens – '
            'styrken er de røde flaggene som hjelper deg å unngå svake aksjer). '
            '<a href="{pre}kilder.html#kategorier">Reglene</a> · <a href="{pre}tickere.html#treffsikkerhet">Treffsikkerhet</a></p>')
TICKER_HEAD = "<tr><th>Ticker</th><th>Kategori</th><th>Poeng</th><th>Signaler</th><th>5d</th><th>20d</th></tr>"


def cat_badge(cat):
    return f'<span class="cat {cat}">{CAT_LABEL[cat]}</span>' if cat in CAT_LABEL else '<span class="mut">–</span>'


def cat_cell(e, why=True):
    if not e or not e.get("category"):
        return '<span class="mut">–</span>'
    return cat_badge(e["category"]) + (f'<div class="why">Hvorfor: {E(e.get("cat_reason"))}</div>' if why else "")


def theme_cat(catmap, r):
    return '<span class="mut">–</span>' if r.get("role") == "taper" else cat_cell(catmap.get(r["ticker"]))


def cat_summary_html(snap):
    tk = [e for e in snap.get("tickers", []) if e.get("category")]
    if not tk:
        return ""
    cnt = {k: sum(e["category"] == k for e in tk) for k in C.CAT_NO}
    top = [e for e in tk if e["category"] in ("kjop", "hold")]
    items = "".join(f'<li>{cat_badge(e["category"])} <a href="ticker/{slug(e["ticker"])}.html"><b>{E(e["ticker"])}</b></a> '
                    f'<span class="mut">{E(e.get("name") or "")}</span><div class="why">Hvorfor: {E(e["cat_reason"])}</div>'
                    f'<div class="tline">{E(X.P.one_liner(e, {t["key"]: t for t in snap.get("themes", [])}))}</div>{X.plan_html(e, compact=True)}</li>' for e in top)
    none = ('<p>Ingen aksjer oppfyller alle Kjøp-kriteriene i dag. Det er normalt – reglene er bevisst strenge '
            '(minst to uavhengige, pålitelige signaltyper + kursbekreftelse + ingen røde flagg).</p>') if not cnt["kjop"] else ""
    return (f'<div class="card"><h2 style="margin-top:0">Kategorier i dag</h2><p>{cat_badge("kjop")} {cnt["kjop"]} &nbsp; '
            f'{cat_badge("hold")} {cnt["hold"]} &nbsp; {cat_badge("watch")} {cnt["watch"]}</p>{none}'
            + (f'<ul class="ev" style="list-style:none;padding-left:0">{items}</ul>' if items else "")
            + CAT_NOTE.format(pre="") + "</div>")


def cat_rules_html(e):
    if not e.get("category"):
        return ""
    mark = {True: ("rule-ok", "✔ oppfylt"), False: ("rule-no", "✘ ikke oppfylt"), None: ("rule-na", "– ukjent")}
    rows = "".join(f'<tr><td>{E(r[0])}</td><td class="{mark[r[1]][0]}">{mark[r[1]][1]}</td><td class="mut">{E(r[2])}</td></tr>' for r in e.get("cat_rules", []))
    meaning = {"kjop": "Alle regler for Kjøp-kandidat er oppfylt i dag. Det betyr «verdt en grundig egen vurdering», ikke en garanti.",
               "hold": "Har du aksjen, støtter signalene den fortsatt – men inngangen er sen/strukket. Ikke jag kursen.",
               "watch": "Noe uvanlig skjer, men bekreftelse mangler. Følg med."}[e["category"]]
    return (f'<div class="card"><h2 style="margin-top:0">Kategori: {cat_badge(e["category"])}</h2><p><b>Hvorfor:</b> {E(e.get("cat_reason"))}</p>'
            f'<p class="mut">{meaning}</p><div class="tw"><table><tr><th>Regel (Kjøp-kandidat krever alle)</th><th>Status</th><th>Detalj</th></tr>{rows}</table></div>'
            + CAT_NOTE.format(pre="../") + "</div>")


def _ci(v):
    return "" if not v or v[0] != v[0] else f"{v[0]*100:+.1f} til {v[1]*100:+.1f} %"


def _track_cells(v, min_n):
    cells = ""
    for h in C.HORIZONS:
        x = v.get(f"h{h}", {})
        if "mean" in x:
            cells += (f'<td>{pct(x["mean"])} <span class="mut">(95 %: {_ci(x.get("mean_ci")) or "–"})</span><br>'
                      f'<span class="mut">slo indeks {x["hit"]*100:.0f} % (95 %: {x["hit_ci"][0]*100:.0f}–{x["hit_ci"][1]*100:.0f} %), median {pct(x["median"])}, n={x["n"]}</span></td>')
        else:
            cells += f'<td class="mut">n={x.get("n", 0)} – for få (vises fra {min_n})</td>'
    return cells


def track_html(snap):
    tr = snap.get("track_record")
    head = ('<div class="card tw" id="treffsikkerhet"><h2 style="margin-top:0">Treffsikkerhet (fremoverlogg)</h2>'
            '<p class="mut">Hver kjøring lagrer dato, ticker, kategori, kurs, <b>signaltyper</b> og <b>flagg</b>. Her måles hvordan <b>uavhengige nye</b> plasseringer '
            'gjorde det 5, 20 og 60 handelsdager senere mot referanseindeks (OSEBX for Oslo Børs, SPY – S&amp;P 500 inkl. utbytte – for USA). '
            'Inngang = første sluttkurs <i>etter</i> kjøringsdatoen. Meravkastning = aksje − indeks, uten kurtasje/spread. '
            'Bare enkeltaksjer på amerikanske børser og Oslo Børs telles (ETF-er og andre børser utelates). '
            '<a href="historikk/kategorier.csv">Last ned loggen (CSV)</a>.</p>')
    if not tr:
        return head + "<p><b>Ikke nok data ennå.</b></p></div>"
    mn = tr.get("min_n")
    rows = "".join(f'<tr><td>{cat_badge(cat)}</td><td>{v["entries"]}</td>{_track_cells(v, mn)}</tr>' for cat, v in tr["cats"].items())
    TN = {**C.TYPE_NO}
    trows = "".join(f'<tr><td>{E(TN.get(k, k))}</td><td>{v["entries"]}</td>{_track_cells(v, mn)}</tr>' for k, v in (tr.get("types") or {}).items())
    from .site_extra import _flag_info
    frows = "".join(f'<tr><td>{E(_flag_info(k)[0])}</td><td>{v["entries"]}</td>{_track_cells(v, mn)}</tr>' for k, v in (tr.get("flags") or {}).items())
    enough = any("mean" in v.get(f"h{h}", {}) for v in tr["cats"].values() for h in C.HORIZONS)
    if not enough:
        head += (f'<p><b>Ikke nok data ennå.</b> Tall (snitt, treffrate og 95 %-intervall) vises først når minst {mn} <i>uavhengige</i> nye plasseringer har nådd '
                 f'horisonten. Uavhengig = første dag i en sammenhengende rekke kjøringsdager, og maks én per ticker og kategori per {tr.get("spacing", 60)} handelsdager '
                 '(overlappende 60-dagersvinduer ville blåst opp n). Med få kjøringsdager tar dette flere måneder.</p>')
    miss = ""
    if tr.get("missing") or tr.get("stopped") or tr.get("excluded"):
        miss = ('<p class="mut">' + (f'Uten kursdata (ikke målt): {E(", ".join(tr["missing"]))}. ' if tr.get("missing") else "")
                + (f'Sluttet å handle i vinduet (siste kurs brukt): {E(", ".join(tr["stopped"]))}. ' if tr.get("stopped") else "")
                + (f'Utelatt fra målingen (ETF/annen børs): {E(", ".join(tr["excluded"]))}.' if tr.get("excluded") else "") + '</p>')
    info = (f'<p class="mut">Loggen startet {E(tr.get("first_date"))}; {tr.get("n_days", 0)} kjøringsdager, {tr.get("n_log_rows", 0)} rader.</p>')
    th = '<tr><th>{}</th><th>Uavh. oppføringer</th><th>5 dager</th><th>20 dager</th><th>60 dager</th></tr>'
    return (head + info + f'<h3>Per kategori</h3><table>{th.format("Kategori")}{rows}</table>'
            + (f'<h3>Per signaltype</h3><table>{th.format("Signaltype")}{trows}</table>' if trows else '<p class="mut">Per signaltype: ingen signaltyper logget ennå (kolonnen ble lagt til 2026-09-28).</p>')
            + (f'<h3>Per flagg</h3><table>{th.format("Flagg")}{frows}</table>' if frows else "")
            + miss + '<p class="catnote">Få observasjoner og korte perioder gir mye tilfeldighet – se på intervallene, ikke bare snittet. '
            'Selv gode tall her er ikke bevis for at reglene virker.</p></div>')


def categories_method_html():
    R = C.RULES
    from .oslo_flags import FLAG_INFO
    fl = "".join(f'<li><b>{E(v[0])}</b> ({ {"red": "rødt – blokkerer Kjøp", "yellow": "gult – halver størrelsen", "note": "tillegg", "info": "info-merke"}[v[1]] }; '
                 f'evidens: {E(v[2])}): {E(v[3])}</li>' for v in FLAG_INFO.values())
    return f"""<div class="card" id="kategorier"><h2 style="margin-top:0">Kategorier: Kjøp-kandidat, Hold, Watchlist</h2>
<div class="warnbox">{E(C.DISCLAIMER_NO)} Våre historiske tester fant ingen robust fordel for innsidekjøp-klynger, DoD-kontrakter, GDELT-topper,
prediksjonsmarkeder, kursbekreftelsen i seg selv – eller for noe annet kjøpssignal. «Sterk kvartalsrapport» er med som <b>eksperimentell</b> signaltype (svak evidens).
Det som faktisk har holdt i testene, er de <b>røde flaggene for Oslo Børs</b> – de hindrer Kjøp. Reglene er laget for å være strenge og etterprøvbare – ikke for å love avkastning.</div>
<h3>{cat_badge("kjop")} Kjøp-kandidat – krever at ALT dette er oppfylt</h3><ol>
<li><b>Minst {R["min_types"]} uavhengige signaltyper</b> fra kilder med høyere pålitelighet: offentlig kontrakt (DoD-kunngjøring/USAspending, teller som én type),
innsidekjøp-klynge (≥ 2 innsidere kjøper i markedet for ≥ $50k siste 7 dager, inkl. ledelse/styre – ikke bare 10 %-eiere), kontraktsmelding på Oslo Børs (Newsweb),
tema med score ≥ {R["theme_min"]:.1f} der fysisk oljemarked (crack spread, Brent–WTI, futureskurve) bekrefter med z ≥ {R["theme_market_z"]:.1f},
eller <b>sterk kvartalsrapport</b> (kun USA, <b>eksperimentell / svak evidens</b>): EPS-overraskelse ≥ 15 % <i>og</i> kursreaksjon ≥ +4 % mot SPY på reaksjonsdagen, siste 45 dager.
Med punkt-i-tid S&amp;P 500 (inkl. tidligere medlemmer) ga sidens terskler +0,76 pp (t 1,9) før 2016 og +0,36 pp (t 0,7) etter over 60 dager – omtrent null etter
0,75 % kurtasje/valuta (forskningsdefinisjonen: ~+0,6 pp brutto). Variant <b>PEAD-S</b> (1-års daglig volatilitet over median blant S&amp;P 500-aksjene) ≈ +1 pp brutto
(t 1,1–1,3), ≈ +0,25 pp netto – merkes, men er også eksperimentell.
Uvanlig volum, kursbevegelser, Reddit, kongresshandler og innsidemeldinger med ukjent retning teller <i>ikke</i>.</li>
<li>Minst ett av signalene er <b>ferskere enn {R["fresh_days"]} dager</b>.</li>
<li><b>Kursbekreftelse:</b> kurs over 50-dagers glidende snitt <i>og</i> 20-dagers avkastning bedre enn referanseindeksen (OSEBX for .OL, SPY – S&amp;P 500 inkl. utbytte – ellers).</li>
<li><b>Ikke strukket:</b> 5d-avkastning under +{R["stretch_5d"]*100:.0f} %, 20d under +{R["stretch_20d"]*100:.0f} % og under {R["stretch_sma"]*100:.0f} % over 50-dagers snitt.</li>
<li><b>Ingen røde flagg:</b> kraftig økende short (Oslo: +{R["short_7d"]} pp på 7 d eller +{R["short_30d"]} pp på 30 d), kursfall ≥ {abs(R["crash"])*100:.0f} % i løpet av 20 handelsdager,
lav likviditet (median omsetning under ca. ${R["min_adv_usd"]/1e6:.0f}M per dag), pennyaksje (under ca. ${R["min_price_usd"]:.0f}), bare volum-/kurssignal – og for Oslo Børs flaggene under.</li></ol>
<h3>Oslo-flagg (rangert blant likvide Oslo-aksjer ≥ ~2 MNOK/dag, oppdatert daglig)</h3><ul class="ev">{fl}</ul>
<h3>{cat_badge("hold")} Hold</h3><p>Minst én pålitelig signaltype, kursbekreftelse og ingen røde flagg – men inngangen er sen: kursen er strukket,
signalene er eldre enn {R["fresh_days"]} dager, eller aksjen var Kjøp-kandidat de siste {R["hold_memory_days"]} dagene uten ny utløser.
Betydning: <i>har du aksjen, støtter signalene den fortsatt – men ikke jag kursen.</i></p>
<h3>{cat_badge("watch")} Watchlist</h3><p>Alt annet med oppmerksomhet/avvik: bare én kildetype, bare volum eller tema, fallende kurs, røde flagg eller manglende kursdata.</p>
<p class="mut">Forventning: få eller ingen Kjøp-kandidater de fleste dager. Hver kjøring logges (dato, ticker, kategori, kurs, signaltyper, flagg) slik at treffsikkerheten kan måles
over tid – se <a href="tickere.html#treffsikkerhet">Treffsikkerhet</a>. Terskler: signaltool/categories.py og signaltool/oslo_flags.py.</p></div>"""


def rel_label(txt):
    """Coloured reliability label: høy -> green, middels -> amber, lav -> red."""
    t = str(txt or "").lower()
    lvl = "lo" if "lav" in t else "mid" if ("middels" in t or "foreløp" in t) else "hi" if "høy" in t else "mid"
    return f'<span class="rel {lvl}">{E(txt)}</span>'


def score_badge(s, hi=2.0, mid=1.0):
    cls = "hot" if s >= hi else "warm" if s >= mid else ""
    return f'<span class="score {cls}">{s:.2f}</span>'


def spark(vals, w=140, h=32):
    v = [x for x in (vals or []) if x is not None]
    if len(v) < 2:
        return ""
    lo, hi = min(v), max(v)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i*(w-2)/(len(v)-1)+1:.1f},{h-1-(x-lo)/rng*(h-2):.1f}" for i, x in enumerate(v))
    return f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><polyline fill="none" stroke="#6cb6ff" stroke-width="1.5" points="{pts}"/></svg>'


NAV = [
    ("index.html", "Oversikt"),
    ("temaer.html", "Temaer"),
    ("tickere.html", "Tickere"),
    ("makro.html", "Makro"),
    ("kalender.html", "Kalender"),
    ("oslo.html", "Oslo Børs"),
    ("kilder.html", "Kilder og metode"),
]


def fold(title: str, body: str, *, open_: bool = True, hid: str | None = None) -> str:
    """Collapsible section. open_=True keeps it expanded on first load."""
    if not (body or "").strip():
        return ""
    o = " open" if open_ else ""
    i = f' id="{E(hid)}"' if hid else ""
    return (f'<details class="fold"{o}{i}><summary><h2>{title}</h2></summary>'
            f'<div class="fold-body">{body}</div></details>')


def page(title: str, body: str, depth=0, snap=None) -> str:
    pre = "../" * depth
    gen = f"Oppdatert {E(snap['generated'])} (norsk tid)" if snap else ""
    active = {
        "Oversikt": "index.html", "Temaer": "temaer.html", "Tickere": "tickere.html",
        "Makro": "makro.html", "Kalender": "kalender.html", "Oslo Børs": "oslo.html",
        "Kilder og metode": "kilder.html",
    }
    cur = active.get(title)
    if cur is None:
        # Theme/ticker detail pages: no top-level match; highlight parent section.
        low = title.lower()
        if "tema" in low:
            cur = "temaer.html"
        elif any(x in low for x in (".ol", ".us", "ticker")) or re.match(r"^[A-Z0-9.-]{1,12}$", title):
            cur = "tickere.html"
    nav = "".join(
        f'<a class="{"on" if href == cur else ""}" href="{pre}{href}">{label}</a>'
        for href, label in NAV
    )
    script = """<script>
(function(){
  function folds(){return Array.from(document.querySelectorAll('details.fold'));}
  function setAll(open){folds().forEach(function(d){d.open=open;});}
  var openBtn=document.getElementById('folds-open');
  var closeBtn=document.getElementById('folds-close');
  if(openBtn) openBtn.addEventListener('click',function(){setAll(true);});
  if(closeBtn) closeBtn.addEventListener('click',function(){setAll(false);});
  var tog=document.getElementById('nav-toggle');
  if(tog) tog.addEventListener('click',function(){document.body.classList.toggle('nav-open');});
  document.querySelectorAll('.side nav a').forEach(function(a){
    a.addEventListener('click',function(){document.body.classList.remove('nav-open');});
  });
  // Auto-wrap legacy cards that start with h2/h3 into folds (once).
  document.querySelectorAll('main .card').forEach(function(card){
    if(card.closest('details.fold')) return;
    var h=null;
    for(var i=0;i<card.children.length;i++){
      var c=card.children[i];
      if(c.tagName==='H2'||c.tagName==='H3'){h=c;break;}
      if(c.tagName==='P' && c.classList.contains('mut')) continue;
      break;
    }
    if(!h) return;
    var d=document.createElement('details');
    d.className='fold';
    d.open=true;
    if(card.id){d.id=card.id;card.removeAttribute('id');}
    var sum=document.createElement('summary');
    var hx=document.createElement('h2');
    hx.innerHTML=h.innerHTML;
    sum.appendChild(hx);
    var body=document.createElement('div');
    body.className='fold-body';
    while(card.firstChild){
      var ch=card.firstChild;
      if(ch===h){card.removeChild(ch);continue;}
      body.appendChild(ch);
    }
    d.appendChild(sum);d.appendChild(body);
    card.replaceWith(d);
  });
})();
</script>"""
    return f"""<!doctype html><html lang="no"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)} – Geo-signal</title><link rel="stylesheet" href="{pre}style.css"><meta name="color-scheme" content="dark"><meta name="theme-color" content="#060a10"><meta name="robots" content="noindex"></head><body>
<div class="app">
<aside class="side" id="side">
<a class="brand" href="{pre}index.html">🛰️ Geo-signal</a>
<span class="gen">{gen}</span>
<nav>{nav}</nav>
<div class="tools">
<button type="button" id="folds-open">Åpne alle områder</button>
<button type="button" id="folds-close">Lukk alle områder</button>
</div>
</aside>
<div class="content">
<header class="top"><button type="button" class="side-toggle" id="nav-toggle" aria-label="Meny">☰ Meny</button>
<a class="brand" href="{pre}index.html">🛰️ Geo-signal</a><span class="gen">{gen}</span></header>
<main>{body}</main>
<footer>{DISCLAIMER}<br>Data: GDELT, SEC EDGAR, Polymarket, Oslo Børs Newsweb, Finanstilsynet, SSB, Eurostat, FRED, ONS, SCB, DST, OECD, IMF m.fl. Se «Kilder og metode».</footer>
</div></div>
{script}</body></html>"""


def theme_card(t, pre=""):
    comps = sorted([(k, v) for k, v in t["components"].items() if v["score"] is not None], key=lambda kv: -kv[1]["score"])
    drivers = "".join(f'<span class="pill">{E(COMP_SHORT.get(k, k))} {v["score"]:+.1f}</span>' for k, v in comps[:3])
    w = min(100, t["score"] / 5 * 100)
    pm = t["polymarket"][:1]
    pmh = f'<div class="mut">Marked: <a href="{E(pm[0]["url"])}">{E(pm[0]["question"])}</a> – {num((pm[0]["p_yes"] or 0)*100,0)}%</div>' if pm else ""
    return f"""<div class="card"><h3><a href="{pre}tema/{t['key']}.html">{E(t['name'])}</a></h3>
<div>{score_badge(t['score'])} <span class="mut">{t['headline_count_3d']} overskrifter siste 3 døgn</span></div>
<div class="bar" style="margin:8px 0"><i style="width:{w:.0f}%"></i></div>{drivers}{pmh}
<div class="mut" style="margin-top:6px">Eksponert: {E(', '.join((t['tickers_ose'] + t['tickers_us'])[:6]))}</div></div>"""


def ticker_row(e, pre=""):
    st = e.get("stats") or {}
    pts = " ".join(f'<span class="pill">{E(POINT_NO.get(k, k))} {v:.1f}</span>' for k, v in sorted(e["points"].items(), key=lambda kv: -kv[1]) if v > 0)
    return (f'<tr><td><a href="{pre}ticker/{slug(e["ticker"])}.html"><b>{E(e["ticker"])}</b></a><br><span class="mut">{E(e.get("name") or "")}</span></td>'
            f'<td>{cat_cell(e)}</td><td>{score_badge(e["score"], 4, 2)}</td><td>{pts}</td><td>{pct(st.get("ret_5d"))}</td><td>{pct(st.get("ret_20d"))}</td></tr>')


def _prep(snap: dict) -> dict:
    """Render-time normalisation (also applied to older snapshots)."""
    for t in snap.get("themes", []):
        t["polymarket"] = sorted(t.get("polymarket", []), key=lambda m: (-abs(m.get("chg_1w") or 0), -(m.get("volume_24h") or 0)))
    snap["insider_clusters"] = [r for r in snap.get("insider_clusters", []) if str(r.get("ticker") or "").upper() not in ("", "NONE", "N/A", "NA")]
    from . import regime
    for e in snap.get("tickers", []):
        e["_regime"] = regime.for_ticker(snap, e["ticker"])
    return snap


def build(snap: dict) -> Path:
    snap = _prep(snap)
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "tema").mkdir(parents=True)
    (SITE / "ticker").mkdir()
    (SITE / "style.css").write_text(CSS + X.CSS_EXTRA + ".card.stale{border-left:4px solid var(--down)}\n")
    Q.FAILED_SECTIONS.clear()
    sec = lambda name, fn, *a: Q.section(name, fn, *a, snap=snap)
    (SITE / ".nojekyll").write_text("")
    themes, tickers = snap["themes"], snap["tickers"]

    # ---------- dashboard ----------
    b = [f'<div class="warnbox">{DISCLAIMER}</div>',
         f'<h1>Oversikt {E(snap["date"])}</h1><p class="mut">Hvilke geopolitiske temaer får uvanlig mye oppmerksomhet nå, målt mot sin egen historikk – og hvilke aksjer som viser tidlige tegn. GDELT-data t.o.m. {E(snap.get("gdelt_latest"))}.</p>',
         sec("Dashboard", X.dashboard_html, snap),
         sec("Hva bør jeg se på i dag?", X.focus_html, snap),
         sec("Nytt siden i går", X.changes_html, snap),
         sec("Helgeoppsummering", weekend_html, snap.get("weekend")),
         sec("Kategorier", cat_summary_html, snap),
         sec("Ærlig status", lambda: X.honesty_html(extra=Q.section("Datakvalitet", Q.dq_line, snap, snap=snap))),
         sec("Markedsregime", X.regime_html, snap),
         X.portfolio_rules_html(),
         sec("Topp fremvoksende temaer", lambda: '<h2>Topp fremvoksende temaer</h2><div class="grid">' + "".join(theme_card(t) for t in themes[:6]) + "</div>"),
         '<h2>Kandidat-tickere koblet til temaene</h2><div class="card tw"><table>' + TICKER_HEAD + ''
         + "".join(ticker_row(e) for e in [x for x in tickers if x["themes"]][:12]) + '</table><p class="mut">Høy poengsum betyr «verdt å undersøke», ikke «kjøp». <a href="tickere.html">Alle tickere →</a></p>' + CAT_NOTE.format(pre="") + '</div>',
         '<h2>Annen uvanlig aktivitet</h2><div class="card tw"><p class="mut">Ikke koblet til et geopolitisk tema – uvanlig volum/kurs, innsidehandler eller kontrakter.</p><table>' + TICKER_HEAD + ''
         + "".join(ticker_row(e) for e in [x for x in tickers if not x["themes"]][:8]) + '</table>' + CAT_NOTE.format(pre="") + '</div>']
    try:   # optional dashboard blocks: a malformed source must not break the build
        pmm = snap.get("polymarket_movers") or []
        if pmm:
            b.append('<h2>Største bevegelser i prediksjonsmarkeder (1 uke)</h2><div class="card tw"><table><tr><th>Spørsmål</th><th>Sannsynlighet</th><th>1 uke</th><th>Volum 24t</th></tr>' +
                     "".join(f'<tr><td><a href="{E(m["url"])}">{E(m["question"])}</a></td><td>{num((m["p_yes"] or 0)*100,0)}%</td><td>{num((m["chg_1w"] or 0)*100,1)} pp</td><td>${m["volume_24h"]:,.0f}</td></tr>' for m in pmm[:8]) + "</table></div>")
        surprises = [r for r in (snap.get("macro") or {}).get("series", []) if r.get("surprise_z") is not None and abs(r["surprise_z"]) >= 1.5]
        if surprises:
            b.append('<h2>Makro-overraskelser</h2><div class="card"><ul class="ev">' + "".join(
                f'<li><a href="{E(r["url"])}">{E(r["name"])}</a>: siste {num(r["last"])} ({E(r["last_period"])}), overraskelse z={r["surprise_z"]:+.1f} – {E(r["why"])}</li>' for r in surprises) + '</ul><a href="makro.html">Mer makro →</a></div>')
        cal = [e for e in snap.get("calendar", [])][:8]
        if cal:
            b.append('<h2>Neste hendelser</h2><div class="card"><ul class="ev">' + "".join(f'<li>{E(e["date"])} {E(e.get("time") or "")} – <b>{E(e["source"])}</b>: {E(e["title"])}</li>' for e in cal) + '</ul><a href="kalender.html">Hele kalenderen →</a></div>')
    except Exception as ex:
        import logging; logging.getLogger(__name__).warning("dashboard extras failed: %s", ex)
        b.append(Q.stale_card("Prediksjonsmarkeder / makro / kalender", None))
    (SITE / "index.html").write_text(page("Oversikt", "".join(b), 0, snap))

    # ---------- themes list + pages ----------
    rows = "".join(f'<tr><td>{i}</td><td><a href="tema/{t["key"]}.html">{E(t["name"])}</a></td><td>{score_badge(t["score"])}</td><td>{t["headline_count_3d"]}</td></tr>' for i, t in enumerate(themes, 1))
    (SITE / "temaer.html").write_text(page("Temaer", f'<h1>Alle temaer</h1><div class="card tw"><table><tr><th>#</th><th>Tema</th><th>Score</th><th>Overskrifter 3d</th></tr>{rows}</table></div>' + sec("Temakart", TM.cards_html), 0, snap))
    have = {e["ticker"] for e in tickers}
    for M in TM.MAPS.values():
        (SITE / "tema" / f"{M['file']}.html").write_text(page(f"Temakart: {M['name']}", sec(f"Temakart: {M['name']}", TM.map_html, M["key"], snap, have), 1, snap))
    for t in themes:
        (SITE / "tema" / f"{t['key']}.html").write_text(page(t["name"], sec(t["name"], theme_page, t, {e["ticker"]: e for e in tickers}, snap), 1, snap))

    # ---------- tickers ----------
    lf = "".join(f'<li>{E(x["date"])} {E(x["form"])}: <a href="{E(x["url"])}">{E(x["company"])}</a></li>' for x in snap.get("late_filings", [])[:20])
    ins = "".join(f'<tr><td>{E(r["ticker"])}</td><td><a href="{E(r["url"])}">{E(r["issuer"])}</a></td><td>{r["n_insiders"]}</td><td>${r["total_value"]:,.0f}</td><td class="mut">{E(r["roles"])}</td></tr>' for r in snap.get("insider_clusters", [])[:20])
    (SITE / "tickere.html").write_text(page("Tickere", '<h1>Kandidat-tickere</h1><div class="card tw"><table>' + TICKER_HEAD + ''
                                            + "".join(ticker_row(e) for e in tickers) + "</table>" + CAT_NOTE.format(pre="") + "</div>"
                                            + sec("Treffsikkerhet", track_html, snap)
                                            + (f'<div class="card tw"><h2 style="margin-top:0">Innsidekjøp i USA (SEC Form 4, 7 dager)</h2><table><tr><th>Ticker</th><th>Selskap</th><th>Innsidere</th><th>Verdi</th><th>Roller</th></tr>{ins}</table></div>' if ins else "")
                                            + (f'<div class="card"><h2 style="margin-top:0">🚩 Forsinkede regnskap (NT 10-K/10-Q, 7 dager)</h2><p class="mut">Klassisk varselsignal (regnskapsproblemer). Ikke automatisk negativt, men verdt å sjekke før kjøp.</p><ul class="ev">{lf}</ul></div>' if lf else ""), 0, snap))
    tmap = {t["key"]: t for t in themes}
    for e in tickers:
        (SITE / "ticker" / f"{slug(e['ticker'])}.html").write_text(page(e["ticker"], sec(e["ticker"], ticker_page, e, tmap), 1, snap))

    (SITE / "makro.html").write_text(page("Makro", sec("Makro", makro_page, snap), 0, snap))
    (SITE / "kalender.html").write_text(page("Kalender", sec("Kalender", kalender_page, snap), 0, snap))
    (SITE / "oslo.html").write_text(page("Oslo Børs", sec("Oslo Børs", oslo_page, snap), 0, snap))
    (SITE / "kilder.html").write_text(page("Kilder og metode", sec("Kilder og metode", kilder_page, snap), 0, snap))
    (SITE / "data.json").write_text(json.dumps(snap, default=str))
    if C.LOG_PATH.exists():  # public forward log of every day's categories (also restores CI state if the cache is lost)
        (SITE / "historikk").mkdir(exist_ok=True)
        shutil.copy(C.LOG_PATH, SITE / "historikk" / "kategorier.csv")
    return SITE / "index.html"


def weekend_html(wk):
    if not wk:
        return ""
    cnt = ", ".join(f"{E(k)}: {v}" for k, v in list(wk["theme_headline_counts"].items())[:6])
    hs = "".join(f"<li><b>{E(k)}</b>: " + " · ".join(f'<a href="{E(h["link"])}">{E(h["title"])}</a>' for h in v[:2]) + "</li>" for k, v in wk["top_headlines"].items())
    pm = "".join(f'<li><a href="{E(m["url"])}">{E(m["question"])}</a> – {num((m["p_yes"] or 0)*100,0)}% ({num((m["chg_1d"] or 0)*100,1)} pp siste døgn)</li>' for m in wk["polymarket_1d_movers"][:5])
    return (f'<div class="card hl"><h2 style="margin-top:0">🗓️ Helgeoppsummering</h2><p class="mut">Siden fredag {E(wk["since"])} (norsk tid). Futures åpner {E(wk["futures_reopen"])}.</p>'
            f'<p>Overskrifter per tema: {cnt or "ingen"}</p><ul class="ev">{hs}</ul>' + (f'<h3>Prediksjonsmarkeder – største døgnbevegelser</h3><ul class="ev">{pm}</ul>' if pm else "") + "</div>")


def theme_page(t, catmap=None, snap=None):
    catmap = catmap or {}
    scen = X.scenario_html(t, snap or {})
    comp_rows = "".join(f'<tr><td>{E(v["label"])}</td><td>{num(v["score"])}</td><td>{v["weight"]}</td><td class="mut">{E(v["detail"])}</td></tr>' for v in t["components"].values())
    ser = t.get("gdelt_series") or {}
    trend = f'<p class="mut">GDELT-andel siste {len(ser.get("share", []))} dager: {spark(ser.get("share"), 300, 50)} &nbsp; nyhets-URL-andel: {spark(ser.get("url"), 300, 50)}</p>' if ser else ""
    tick = "".join(f'<tr><td><a href="../ticker/{slug(r["ticker"])}.html">{E(r["ticker"])}</a></td><td>{theme_cat(catmap, r)}</td><td>{E(r["role"])}</td><td>{pct(r["ret_1d"])}</td><td>{pct(r["ret_5d"])}</td><td>{pct(r["ret_20d"])}</td><td>{num(r["ret5_z"],1)}</td><td>{num(r["vol5_z"],1)}</td></tr>' for r in t["tickers"])
    pm = "".join(f'<tr><td><a href="{E(m["url"])}">{E(m["question"])}</a></td><td>{num((m["p_yes"] or 0)*100,0)}%</td><td>{num((m["chg_1d"] or 0)*100,1)} pp</td><td>{num((m["chg_1w"] or 0)*100,1)} pp</td><td>${m["volume_24h"]:,.0f}</td></tr>' for m in t["polymarket"])
    heads = "".join(f'<li><a href="{E(h["link"])}">{E(h["title"])}</a> <span class="mut">– {E(h["source"])}, {E(str(h.get("published") or "")[:16].replace("T", " "))} UTC</span></li>' for h in t["headlines"])
    red = "".join(f'<li><a href="{E(r["link"])}">{E(r["title"])}</a> <span class="mut">r/{E(r["sub"])}</span></li>' for r in t["reddit"])
    ek = "".join(f'<li><a href="{E(x["url"])}">{E(x["company"])}</a> <span class="mut">{E(x["date"])}</span></li>' for x in t["eightk_examples"])
    return f"""<h1>{E(t['name'])} {score_badge(t['score'])}</h1>
<div class="card"><h2 style="margin-top:0">Geopolitisk scenario</h2><p>{E(t['reasoning'])}</p>
<p><b>⚠️ Hva kan gå galt:</b> {E(t['risks'])}</p>
<p><b>Sektorer:</b> {E(', '.join(t['sectors']))}<br><b>Vinnere ved eskalering (eksempler):</b> USA: {E(', '.join(t['tickers_us']))}; Oslo: {E(', '.join(t['tickers_ose']) or '–')}{('; andre: ' + E(', '.join(t['tickers_other']))) if t['tickers_other'] else ''}<br>
<b>Tapere:</b> {E(', '.join(t['losers']) or '–')} &nbsp; <b>Råvarer/FX:</b> {E(', '.join(t['commodities']) or '–')}</p></div>
{scen}
{TM.related_html(t['key'])}
<div class="card tw"><h2 style="margin-top:0">Hvorfor scoren er {t['score']:.2f}</h2>{trend}<table><tr><th>Komponent</th><th>Score (z)</th><th>Vekt</th><th>Detalj</th></tr>{comp_rows}</table></div>
{'<div class="card tw"><h2 style="margin-top:0">Prediksjonsmarkeder (Polymarket)</h2><p class="mut">Pris = markedets sannsynlighet for «Ja».</p><table><tr><th>Spørsmål</th><th>Sanns.</th><th>1d</th><th>1u</th><th>Volum 24t</th></tr>' + pm + '</table></div>' if pm else ''}
<div class="card tw"><h2 style="margin-top:0">Berørte aksjer og råvarer</h2><table><tr><th>Ticker</th><th>Kategori</th><th>Rolle</th><th>1d</th><th>5d</th><th>20d</th><th>5d-z</th><th>Volum-z</th></tr>{tick}</table>{CAT_NOTE.format(pre="../")}</div>
<div class="card"><h2 style="margin-top:0">Siste nyheter</h2><ul class="ev">{heads or '<li class="mut">Ingen treff siste 3 døgn.</li>'}</ul>
{('<h3>Reddit</h3><ul class="ev">' + red + '</ul>') if red else ''}{('<h3>Siste 8-K som nevner temaet</h3><ul class="ev">' + ek + '</ul>') if ek else ''}</div>"""


def ticker_page(e, tmap):
    st = e.get("stats") or {}
    pts = "".join(f'<tr><td>{E(POINT_NO.get(k, k))}</td><td>{v:.2f}</td></tr>' for k, v in sorted(e["points"].items(), key=lambda kv: -kv[1]))
    ev = "".join(f'<li>{("<a href=" + chr(34) + E(x["url"]) + chr(34) + ">" + E(x["text"]) + "</a>") if x.get("url") else E(x["text"])}</li>' for x in e["evidence"])
    flags = "".join(f'<li>⚠️ {E(f)}</li>' for f in e.get("flags", []))
    th = "".join(f'<a class="pill" href="../tema/{k}.html">{E(tmap[k]["name"])}</a>' for k in e["themes"] if k in tmap)
    return f"""<h1>{E(e['ticker'])} <span class="mut">{E(e.get('name') or '')}</span> {score_badge(e['score'], 4, 2)} {cat_badge(e.get('category'))}</h1>
{X.thesis_html(e, tmap)}
{cat_rules_html(e)}
{X.flags_html(e)}
{TM.ticker_html(e)}
{X.plan_html(e, compact=False) if e.get("category") in ("kjop", "hold") else ""}
{X.base_rate_html(e)}
{X.decision_html(e)}
{X.plan_html(e, compact=True) if e.get("category") == "watch" else ""}
<div class="card"><p>{th}</p><table><tr><th>Kurs</th><th>1d</th><th>5d</th><th>20d</th><th>5d-z</th><th>Volum 5d vs normalt</th><th>Sist handlet</th></tr>
<tr><td>{num(st.get('close'))}</td><td>{pct(st.get('ret_1d'))}</td><td>{pct(st.get('ret_5d'))}</td><td>{pct(st.get('ret_20d'))}</td><td>{num(st.get('ret5_z'),1)}</td><td>{num(st.get('vol_ratio_5d'),1)}x</td><td>{E(st.get('last_date'))}</td></tr></table>
<p class="mut"><a href="https://finance.yahoo.com/quote/{E(e['ticker'])}">Yahoo Finance</a></p></div>
<div class="card"><h2 style="margin-top:0">Signaler og bevis</h2><table><tr><th>Signal</th><th>Poeng</th></tr>{pts}</table><ul class="ev">{ev}{flags}</ul></div>
<div class="card"><h3>Hvorfor dette kan bety noe</h3><p>{E(e['why'])}</p><h3>Hva kan gå galt</h3><p>{E(e['risks'])}</p></div>"""


def makro_page(snap):
    mac = snap.get("macro") or {}
    rows = ""
    for r in mac.get("series", []):
        ch = "–" if r["change"] is None else (f"{r['change']:+.2f}%" if r["change_type"] == "%" else f"{r['change']:+.2f}")
        z = r.get("surprise_z")
        zc = "down" if z is not None and abs(z) >= 2 else ""
        rows += (f'<tr><td><a href="{E(r["url"])}">{E(r["name"])}</a><br><span class="mut">{E(r["why"])}</span></td><td>{E(r["source"])}<br><span class="mut">{E(r["country"])}</span></td>'
                 f'<td>{E(r["last_period"])}</td><td>{num(r["last"])} {E(r["unit"])}</td><td>{ch}</td><td class="{zc}">{num(z,1)}</td><td>{spark(r.get("spark"))}</td><td>{rel_label(r["reliability"])}</td></tr>')
    imf = mac.get("imf_weo_gdp") or {}
    imf_rows = "".join(f'<tr><td>{E(c)}</td>' + "".join(f'<td>{num(v,1)}</td>' for v in vals.values()) + "</tr>" for c, vals in imf.items())
    imf_head = "".join(f"<th>{E(y)}</th>" for y in (next(iter(imf.values())).keys() if imf else []))
    eu = "".join(f'<li><a href="{E(x["link"])}">{E(x["title"])}</a> <span class="mut">{E(x["published"])}</span></li>' for x in mac.get("eurostat_updates", []))
    fx = snap.get("nok_fx") or {}
    fxh = "".join(f'<p>{E(k)}: siste {num(v[-1],4)} {spark(v, 220, 36)}</p>' for k, v in fx.items() if k != "dates" and v)
    press = "".join(f'<li><a href="{E(p["link"])}">{E(p["title"])}</a> <span class="mut">{E(p.get("published"))}</span></li>' for p in snap.get("norgesbank_press", []))
    oil = snap.get("oil") or {}
    oilh = "".join(f'<tr><td>{E(v["label"])}</td><td>{num(v["last"])}</td><td>{num(v.get("z"),1)}</td><td>{spark(v.get("spark"))}{(" " + E(", ".join(f"{c}: {p}" for c, p in v["contracts"].items()))) if v.get("contracts") else ""}</td></tr>' for v in oil.values())
    dodh = "".join(f'<tr><td>{E(r["day"])}</td><td>{E(r["company"])}</td><td>${r["amount"]/1e6:,.1f}M</td><td>{E(r.get("ticker") or "")}</td><td><a href="{E(r["url"])}">kunngjøring</a></td></tr>' for r in snap.get("dod_awards", [])[:20])
    top = X.chokepoints_html(snap) + X.policy_html(snap) + X.taiwan_html(snap) + X.oil_nowcast_html(snap)
    if top:
        top = ('<p class="mut">Hopp til: <a href="#sund">Sundpassasjer</a> · <a href="#politikk">Politikkvarsler</a> · <a href="#taiwan">Taiwan-radar</a> · '
               '<a href="#olje">Oljelagre</a> · <a href="#stat">Offisiell statistikk</a></p>') + top
    extra = ""
    if oilh:
        extra += f'<div class="card tw"><h2 style="margin-top:0">Fysisk oljemarked (futures via Yahoo)</h2><table><tr><th>Mål</th><th>Siste</th><th>z (1 år)</th><th>Trend / kontrakter</th></tr>{oilh}</table><p class="mut">Pålitelighet: markedsdata – høy, men uoffisiell tilgang (yfinance).</p></div>'
    if dodh:
        extra += f'<div class="card tw"><h2 style="margin-top:0">Amerikanske forsvarskontrakter (daglige DoD-kunngjøringer)</h2><table><tr><th>Dag</th><th>Selskap</th><th>Beløp</th><th>Ticker</th><th>Kilde</th></tr>{dodh}</table><p class="mut">Pålitelighet: offisiell kunngjøring – høy. Ticker-kobling er automatisk (navnematch) og kan bomme.</p></div>'
    return f"""<h1>Makro og fysiske indikatorer</h1>{top}
<h2 id="stat">Offisiell statistikk</h2><p class="mut">«Overraskelse (z)» = hvor uvanlig siste endring er sammenlignet med de 24 foregående endringene (robust z-score). Ikke det samme som avvik fra analytikerforventning (konsensus er ikke fritt tilgjengelig).</p>
<div class="card tw"><table><tr><th>Serie</th><th>Kilde</th><th>Periode</th><th>Siste</th><th>Endring</th><th>Overr. (z)</th><th>Trend</th><th>Pålitelighet</th></tr>{rows}</table></div>
<div class="card"><h2 style="margin-top:0">Norges Bank</h2>{fxh}<ul class="ev">{press}</ul></div>
{('<div class="card tw"><h2 style="margin-top:0">IMF WEO – BNP-vekst (prognose, %)</h2><table><tr><th>Land</th>' + imf_head + '</tr>' + imf_rows + '</table><p class="mut">Pålitelighet: offisiell prognose – anslag, ikke fasit.</p></div>') if imf else ''}
{('<div class="card"><h2 style="margin-top:0">Nylig oppdatert hos Eurostat</h2><ul class="ev">' + eu + '</ul></div>') if eu else ''}""" + extra


def kalender_page(snap):
    rows = "".join(f'<tr><td>{E(e["date"])}</td><td>{E(e.get("time") or "")}</td><td>{E(e.get("kind",""))}</td><td>{E(e["source"])}</td><td>{E(e["title"])}</td></tr>' for e in snap.get("calendar", []))
    return f"""<h1>Kalender</h1><p class="mut">Tider i norsk tid der kilden oppgir tid. «(estimert)» = beregnet fra fast publiseringsrytme, ikke offisiell kalender. Sentralbankmøter vises 45 dager frem, øvrige 14–21 dager.</p>
<div class="card tw"><table><tr><th>Dato</th><th>Tid</th><th>Type</th><th>Kilde</th><th>Hendelse</th></tr>{rows}</table></div>"""


def oslo_page(snap):
    con = "".join(f'<tr><td class="nw">{E(r["published"][:10])}</td><td><b>{E(r["issuer"])}</b></td><td><a href="{E(r["url"])}">{E(r["title"])}</a></td></tr>' for r in snap.get("newsweb_contracts", [])[:40])
    ins = "".join(f'<tr><td class="nw">{E(r["published"][:10])}</td><td><b>{E(r["issuer"])}</b></td><td><a href="{E(r["url"])}">{E(r["title"])}</a></td></tr>' for r in snap.get("newsweb_insider", [])[:40])
    sh = "".join(f'<tr><td>{E(r["issuer"])}</td><td>{E(r["ticker"] or "")}</td><td>{r["short_pct"]:.2f}%</td><td>{r["chg_7d"]:+.2f}</td><td>{r["chg_30d"]:+.2f}</td><td class="mut">{E(r["top_holders"])}</td></tr>' for r in snap.get("shorts", []))
    return f"""<h1>Oslo Børs</h1>{Q.source_note(snap, "Oslo Børs Newsweb", "Finanstilsynet short register")}
<div class="card tw"><h2 style="margin-top:0">Kontrakts- og ordremeldinger (Newsweb, 14 dager)</h2><table><tr><th>Dato</th><th>Selskap</th><th>Melding</th></tr>{con}</table></div>
{X.oslo_insider_html(snap)}
<div class="card tw"><h2 style="margin-top:0">Meldepliktige handler – primærinnsidere (14 dager)</h2><p class="mut">Tittelen sier ikke alltid om det er kjøp eller salg – åpne meldingen.</p><table><tr><th>Dato</th><th>Selskap</th><th>Melding</th></tr>{ins}</table></div>
<div class="card tw"><h2 style="margin-top:0">Shortposisjoner (Finanstilsynet) – største endringer</h2><p class="mut">Netto shortposisjoner ≥ 0,5 % offentliggjøres. Økende short = noen profesjonelle vedder på fall.</p><table><tr><th>Selskap</th><th>Ticker</th><th>Short</th><th>Endr. 7d (pp)</th><th>Endr. 30d</th><th>Største aktører</th></tr>{sh}</table></div>"""


def kilder_page(snap):
    st = "".join(f'<tr><td>{E(k)}</td><td class="{"ok" if str(v).startswith("ok") else "fail" if "FAIL" in str(v) else "mut"}">{E(v)}</td></tr>' for k, v in snap["status"].items())
    bt = REPORTS / "backtest.md"
    bt_html = ""
    if bt.exists():
        txt = bt.read_text()
        bt_html = '<div class="card"><h2 style="margin-top:0">Historisk validering (backtest)</h2><pre style="white-space:pre-wrap;font-size:.85rem">' + E(txt) + "</pre></div>"
    cb = REPORTS / "backtest_categories.md"
    if cb.exists():
        bt_html += '<div class="card"><h2 style="margin-top:0">Historisk sjekk av Kjøp-reglene</h2><pre style="white-space:pre-wrap;font-size:.85rem">' + E(cb.read_text()) + "</pre></div>"
    bn = REPORTS / "backtest_natt.md"
    if bn.exists():
        bt_html = ('<div class="card" id="natt"><h2 style="margin-top:0">Nattens tester (2026-09-28): hva leder faktisk kursene?</h2>'
                   '<pre style="white-space:pre-wrap;font-size:.8rem">' + E(bn.read_text()) + "</pre></div>") + bt_html
    return f"""<h1>Kilder og metode</h1><div class="warnbox">{DISCLAIMER}</div>
{X.honesty_html()}
{Q.section("Datakvalitet", Q.dq_html, snap, snap=snap)}
{Q.section("Kontroll mot overtilpasning", Q.kontroll_html, snap, snap=snap)}
{categories_method_html()}
{X.base_rate_table_html()}
{X.dropped_html()}
<div class="card"><h2 style="margin-top:0">Slik fungerer det</h2><ol>
<li><b>Innsamling</b> fra gratis, offentlige kilder (ingen betalte tjenester, ingen API-nøkler).</li>
<li><b>Temakart:</b> 10 geopolitiske temaer koblet til sektorer, råvarer og eksempel-tickere (USA og Oslo Børs), med skriftlig begrunnelse.</li>
<li><b>Avviksdeteksjon:</b> for hvert tema og hver ticker sammenlignes siste periode med egen historikk (robust z-score = (siste − median) / (1,4826 × MAD)).</li>
<li><b>Temascore 0–5</b> = vektet snitt av positive, avkortede komponentscorer: GDELT-hendelser, nyhetsvolum, tone, RSS, Google-søk, SEC 8-K, prediksjonsmarkeder, kurs/volum, OFAC.</li>
<li><b>Ticker-poeng</b> = sum av enkle, dokumenterte poeng (innsidekjøp-klynger, kongresskjøp, kontraktsmeldinger, uvanlig volum/kurs, tema-oppmerksomhet).</li>
<li><b>Beslutningsgrunnlag per ticker</b> (Yahoo via yfinance): hva som allerede er priset inn (avkastning mot indeks og sektor-ETF, avstand til 52-ukers topp),
verdsettelse (P/E, EV/EBITDA, P/B, utbytte, analytikersnitt der det er gratis), risiko (volatilitet, største fall, beta, ATR, likviditet, short, neste rapport)
og ugyldiggjøringsnivå (50-dagers snitt og 2×ATR under kurs).</li>
<li><b>Scenarioer per tema</b> (bull/base/bear) med levende nøkkelindikatorer: kurs, sundpassasjer (IMF PortWatch), oljelagre mot 5-årssnitt (EIA),
Taiwans månedsomsetning (MOPS), politikkdokumenter (Federal Register/EU) og prediksjonsmarked.</li>
<li><b>Testbar tese</b> per ticker (hvorfor den kan stige, hva som bekrefter og hva som avkrefter – med konkrete nivåer), <b>historisk treffrate</b>
for hvert signal fra våre egne tester, og en <b>eksempelplan</b> for Kjøp/Hold: inngangssone, stopp (strengeste av 50-dagers snitt og 2×ATR),
første mål (2:1) og størrelse ved 1 % risiko per handel (maks 5 %, halvert ved høy volatilitet, lav likviditet eller svakt markedsregime). Eksempelberegning – ikke råd.</li>
<li><b>Markedsregime</b>: S&amp;P 500 og OSEBX mot 10-måneders snitt og 1-måneds volatilitet – brukes bare til å halvere nye posisjoner, ikke som salgssignal.</li>
<li><b>«Hva bør jeg se på i dag?»</b> og <b>«Nytt siden i går»</b>: automatisk prioritering og sammenligning med forrige lagrede kjøring; 🔔 = varsel.</li></ol>
<h3>Viktige forbehold</h3><ul>
<li>Ingen språkmodell – nøkkelord kan gi feiltreff (f.eks. «strait» eller «war» i andre sammenhenger).</li>
<li>Oppmerksomhet er ikke det samme som avkastning; mye kan allerede være priset inn.</li>
<li>RSS- og Reddit-baseline bygges opp over tid; de første dagene er disse komponentene svake.</li>
<li>Innsidedata (Form 4) kommer inntil 2 virkedager etter handel; kongresshandler inntil 45 dager.</li>
<li>Pålitelighet: offisiell statistikk (høy, men revideres) &gt; markedsdata (høy) &gt; nyheter (middels) &gt; sosiale medier (lav).</li></ul></div>
{bt_html}
<div class="card tw"><h2 style="margin-top:0">Kildestatus ved siste kjøring</h2><table><tr><th>Kilde</th><th>Status</th></tr>{st}</table>
<p class="mut">Full dokumentasjon av kildene: research/sources.md i prosjektet.</p></div>"""
