"""Static website generator (Norwegian UI). Output: site/ (plain HTML/CSS, no JS frameworks) -> hostable on
GitHub Pages / Netlify / Cloudflare Pages for free."""
from __future__ import annotations
import html, json, re, shutil
from pathlib import Path
from .config import ROOT, REPORTS

SITE = ROOT / "site"
E = lambda x: html.escape("" if x is None else str(x))

CSS = """
/* Dark theme (default). Contrast vs --card #161b22: ink 14.6:1, mut 7.2:1, acc 8.1:1, up 7.6:1, down 7.1:1, warn 8.9:1 (WCAG AA+). */
:root{color-scheme:dark;--bg:#0d1117;--card:#161b22;--card2:#1c2330;--ink:#e6edf3;--mut:#9ea9b5;--acc:#6cb6ff;--acc-bg:rgba(108,182,255,.14);
--up:#4ac26b;--down:#ff8078;--line:#2d333b;--warn:#e3b341;--hdr:#060a10;--pill:#262d38}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--hdr);color:#fff;padding:14px 18px;border-bottom:1px solid var(--line)}header a{color:#fff;text-decoration:none}
header .brand{font-weight:700;font-size:1.15rem}header .gen{color:#a8b5c4;font-size:.9rem}nav{margin-top:6px;display:flex;flex-wrap:wrap;gap:4px 14px;font-size:.95rem}
nav a{color:#cfd9e4!important;opacity:1}nav a:hover{color:#fff!important;text-decoration:underline}
main{max-width:1100px;margin:0 auto;padding:16px}
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
pre{background:#0b0f15;border:1px solid var(--line);border-radius:8px;padding:10px;color:#d5dde6}
footer{max-width:1100px;margin:10px auto 30px;padding:0 16px;color:var(--mut);font-size:.85rem}
svg.spark{vertical-align:middle}svg.spark polyline{stroke:var(--acc)}
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
            "reddit_mentions": "Reddit-omtale", "dod_contract": "DoD-kontrakt"}


def slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", t)


def pct(x, d=1):
    if x is None:
        return "–"
    cls = "up" if x > 0 else "down" if x < 0 else ""
    return f'<span class="{cls}">{x*100:+.{d}f}%</span>'


def num(x, d=2):
    return "–" if x is None else f"{x:.{d}f}"


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


def page(title: str, body: str, depth=0, snap=None) -> str:
    pre = "../" * depth
    gen = f"Oppdatert {E(snap['generated'])} (norsk tid)" if snap else ""
    return f"""<!doctype html><html lang="no"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)} – Geo-signal</title><link rel="stylesheet" href="{pre}style.css"><meta name="color-scheme" content="dark"><meta name="theme-color" content="#060a10"><meta name="robots" content="noindex"></head><body>
<header><a class="brand" href="{pre}index.html">🛰️ Geo-signal</a> <span class="gen">{gen}</span>
<nav><a href="{pre}index.html">Oversikt</a><a href="{pre}temaer.html">Temaer</a><a href="{pre}tickere.html">Tickere</a>
<a href="{pre}makro.html">Makro</a><a href="{pre}kalender.html">Kalender</a><a href="{pre}oslo.html">Oslo Børs</a><a href="{pre}kilder.html">Kilder og metode</a></nav></header>
<main>{body}</main><footer>{DISCLAIMER}<br>Data: GDELT, SEC EDGAR, Polymarket, Oslo Børs Newsweb, Finanstilsynet, SSB, Eurostat, FRED, ONS, SCB, DST, OECD, IMF m.fl. Se «Kilder og metode».</footer></body></html>"""


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
            f'<td>{score_badge(e["score"], 4, 2)}</td><td>{pts}</td><td>{pct(st.get("ret_5d"))}</td><td>{pct(st.get("ret_20d"))}</td></tr>')


def _prep(snap: dict) -> dict:
    """Render-time normalisation (also applied to older snapshots)."""
    for t in snap.get("themes", []):
        t["polymarket"] = sorted(t.get("polymarket", []), key=lambda m: (-abs(m.get("chg_1w") or 0), -(m.get("volume_24h") or 0)))
    snap["insider_clusters"] = [r for r in snap.get("insider_clusters", []) if str(r.get("ticker") or "").upper() not in ("", "NONE", "N/A", "NA")]
    return snap


def build(snap: dict) -> Path:
    snap = _prep(snap)
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "tema").mkdir(parents=True)
    (SITE / "ticker").mkdir()
    (SITE / "style.css").write_text(CSS)
    (SITE / ".nojekyll").write_text("")
    themes, tickers = snap["themes"], snap["tickers"]

    # ---------- dashboard ----------
    b = [f'<div class="warnbox">{DISCLAIMER}</div>',
         f'<h1>Oversikt {E(snap["date"])}</h1><p class="mut">Hvilke geopolitiske temaer får uvanlig mye oppmerksomhet nå, målt mot sin egen historikk – og hvilke aksjer som viser tidlige tegn. GDELT-data t.o.m. {E(snap.get("gdelt_latest"))}.</p>',
         weekend_html(snap.get("weekend")),
         '<h2>Topp fremvoksende temaer</h2><div class="grid">' + "".join(theme_card(t) for t in themes[:6]) + "</div>",
         '<h2>Kandidat-tickere koblet til temaene</h2><div class="card tw"><table><tr><th>Ticker</th><th>Poeng</th><th>Signaler</th><th>5d</th><th>20d</th></tr>'
         + "".join(ticker_row(e) for e in [x for x in tickers if x["themes"]][:12]) + '</table><p class="mut">Høy poengsum betyr «verdt å undersøke», ikke «kjøp». <a href="tickere.html">Alle tickere →</a></p></div>',
         '<h2>Annen uvanlig aktivitet</h2><div class="card tw"><p class="mut">Ikke koblet til et geopolitisk tema – uvanlig volum/kurs, innsidehandler eller kontrakter.</p><table><tr><th>Ticker</th><th>Poeng</th><th>Signaler</th><th>5d</th><th>20d</th></tr>'
         + "".join(ticker_row(e) for e in [x for x in tickers if not x["themes"]][:8]) + '</table></div>']
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
    (SITE / "index.html").write_text(page("Oversikt", "".join(b), 0, snap))

    # ---------- themes list + pages ----------
    rows = "".join(f'<tr><td>{i}</td><td><a href="tema/{t["key"]}.html">{E(t["name"])}</a></td><td>{score_badge(t["score"])}</td><td>{t["headline_count_3d"]}</td></tr>' for i, t in enumerate(themes, 1))
    (SITE / "temaer.html").write_text(page("Temaer", f'<h1>Alle temaer</h1><div class="card tw"><table><tr><th>#</th><th>Tema</th><th>Score</th><th>Overskrifter 3d</th></tr>{rows}</table></div>', 0, snap))
    for t in themes:
        (SITE / "tema" / f"{t['key']}.html").write_text(page(t["name"], theme_page(t), 1, snap))

    # ---------- tickers ----------
    lf = "".join(f'<li>{E(x["date"])} {E(x["form"])}: <a href="{E(x["url"])}">{E(x["company"])}</a></li>' for x in snap.get("late_filings", [])[:20])
    ins = "".join(f'<tr><td>{E(r["ticker"])}</td><td><a href="{E(r["url"])}">{E(r["issuer"])}</a></td><td>{r["n_insiders"]}</td><td>${r["total_value"]:,.0f}</td><td class="mut">{E(r["roles"])}</td></tr>' for r in snap.get("insider_clusters", [])[:20])
    (SITE / "tickere.html").write_text(page("Tickere", '<h1>Kandidat-tickere</h1><div class="card tw"><table><tr><th>Ticker</th><th>Poeng</th><th>Signaler</th><th>5d</th><th>20d</th></tr>'
                                            + "".join(ticker_row(e) for e in tickers) + "</table></div>"
                                            + (f'<div class="card tw"><h2 style="margin-top:0">Innsidekjøp i USA (SEC Form 4, 7 dager)</h2><table><tr><th>Ticker</th><th>Selskap</th><th>Innsidere</th><th>Verdi</th><th>Roller</th></tr>{ins}</table></div>' if ins else "")
                                            + (f'<div class="card"><h2 style="margin-top:0">🚩 Forsinkede regnskap (NT 10-K/10-Q, 7 dager)</h2><p class="mut">Klassisk varselsignal (regnskapsproblemer). Ikke automatisk negativt, men verdt å sjekke før kjøp.</p><ul class="ev">{lf}</ul></div>' if lf else ""), 0, snap))
    tmap = {t["key"]: t for t in themes}
    for e in tickers:
        (SITE / "ticker" / f"{slug(e['ticker'])}.html").write_text(page(e["ticker"], ticker_page(e, tmap), 1, snap))

    (SITE / "makro.html").write_text(page("Makro", makro_page(snap), 0, snap))
    (SITE / "kalender.html").write_text(page("Kalender", kalender_page(snap), 0, snap))
    (SITE / "oslo.html").write_text(page("Oslo Børs", oslo_page(snap), 0, snap))
    (SITE / "kilder.html").write_text(page("Kilder og metode", kilder_page(snap), 0, snap))
    (SITE / "data.json").write_text(json.dumps(snap, default=str))
    return SITE / "index.html"


def weekend_html(wk):
    if not wk:
        return ""
    cnt = ", ".join(f"{E(k)}: {v}" for k, v in list(wk["theme_headline_counts"].items())[:6])
    hs = "".join(f"<li><b>{E(k)}</b>: " + " · ".join(f'<a href="{E(h["link"])}">{E(h["title"])}</a>' for h in v[:2]) + "</li>" for k, v in wk["top_headlines"].items())
    pm = "".join(f'<li><a href="{E(m["url"])}">{E(m["question"])}</a> – {num((m["p_yes"] or 0)*100,0)}% ({num((m["chg_1d"] or 0)*100,1)} pp siste døgn)</li>' for m in wk["polymarket_1d_movers"][:5])
    return (f'<div class="card hl"><h2 style="margin-top:0">🗓️ Helgeoppsummering</h2><p class="mut">Siden fredag {E(wk["since"])} (norsk tid). Futures åpner {E(wk["futures_reopen"])}.</p>'
            f'<p>Overskrifter per tema: {cnt or "ingen"}</p><ul class="ev">{hs}</ul>' + (f'<h3>Prediksjonsmarkeder – største døgnbevegelser</h3><ul class="ev">{pm}</ul>' if pm else "") + "</div>")


def theme_page(t):
    comp_rows = "".join(f'<tr><td>{E(v["label"])}</td><td>{num(v["score"])}</td><td>{v["weight"]}</td><td class="mut">{E(v["detail"])}</td></tr>' for v in t["components"].values())
    ser = t.get("gdelt_series") or {}
    trend = f'<p class="mut">GDELT-andel siste {len(ser.get("share", []))} dager: {spark(ser.get("share"), 300, 50)} &nbsp; nyhets-URL-andel: {spark(ser.get("url"), 300, 50)}</p>' if ser else ""
    tick = "".join(f'<tr><td><a href="../ticker/{slug(r["ticker"])}.html">{E(r["ticker"])}</a></td><td>{E(r["role"])}</td><td>{pct(r["ret_1d"])}</td><td>{pct(r["ret_5d"])}</td><td>{pct(r["ret_20d"])}</td><td>{num(r["ret5_z"],1)}</td><td>{num(r["vol5_z"],1)}</td></tr>' for r in t["tickers"])
    pm = "".join(f'<tr><td><a href="{E(m["url"])}">{E(m["question"])}</a></td><td>{num((m["p_yes"] or 0)*100,0)}%</td><td>{num((m["chg_1d"] or 0)*100,1)} pp</td><td>{num((m["chg_1w"] or 0)*100,1)} pp</td><td>${m["volume_24h"]:,.0f}</td></tr>' for m in t["polymarket"])
    heads = "".join(f'<li><a href="{E(h["link"])}">{E(h["title"])}</a> <span class="mut">– {E(h["source"])}, {E(str(h.get("published") or "")[:16].replace("T", " "))} UTC</span></li>' for h in t["headlines"])
    red = "".join(f'<li><a href="{E(r["link"])}">{E(r["title"])}</a> <span class="mut">r/{E(r["sub"])}</span></li>' for r in t["reddit"])
    ek = "".join(f'<li><a href="{E(x["url"])}">{E(x["company"])}</a> <span class="mut">{E(x["date"])}</span></li>' for x in t["eightk_examples"])
    return f"""<h1>{E(t['name'])} {score_badge(t['score'])}</h1>
<div class="card"><h2 style="margin-top:0">Geopolitisk scenario</h2><p>{E(t['reasoning'])}</p>
<div class="grid"><div><h3>📈 Ved eskalering</h3><p>{E(t['escalation'])}</p></div><div><h3>📉 Ved nedtrapping</h3><p>{E(t['deescalation'])}</p></div>
<div><h3>⚠️ Hva kan gå galt</h3><p>{E(t['risks'])}</p></div></div>
<p><b>Sektorer:</b> {E(', '.join(t['sectors']))}<br><b>Vinnere ved eskalering (eksempler):</b> USA: {E(', '.join(t['tickers_us']))}; Oslo: {E(', '.join(t['tickers_ose']) or '–')}{('; andre: ' + E(', '.join(t['tickers_other']))) if t['tickers_other'] else ''}<br>
<b>Tapere:</b> {E(', '.join(t['losers']) or '–')} &nbsp; <b>Råvarer/FX:</b> {E(', '.join(t['commodities']) or '–')}</p></div>
<div class="card tw"><h2 style="margin-top:0">Hvorfor scoren er {t['score']:.2f}</h2>{trend}<table><tr><th>Komponent</th><th>Score (z)</th><th>Vekt</th><th>Detalj</th></tr>{comp_rows}</table></div>
{'<div class="card tw"><h2 style="margin-top:0">Prediksjonsmarkeder (Polymarket)</h2><p class="mut">Pris = markedets sannsynlighet for «Ja».</p><table><tr><th>Spørsmål</th><th>Sanns.</th><th>1d</th><th>1u</th><th>Volum 24t</th></tr>' + pm + '</table></div>' if pm else ''}
<div class="card tw"><h2 style="margin-top:0">Berørte aksjer og råvarer</h2><table><tr><th>Ticker</th><th>Rolle</th><th>1d</th><th>5d</th><th>20d</th><th>5d-z</th><th>Volum-z</th></tr>{tick}</table></div>
<div class="card"><h2 style="margin-top:0">Siste nyheter</h2><ul class="ev">{heads or '<li class="mut">Ingen treff siste 3 døgn.</li>'}</ul>
{('<h3>Reddit</h3><ul class="ev">' + red + '</ul>') if red else ''}{('<h3>Siste 8-K som nevner temaet</h3><ul class="ev">' + ek + '</ul>') if ek else ''}</div>"""


def ticker_page(e, tmap):
    st = e.get("stats") or {}
    pts = "".join(f'<tr><td>{E(POINT_NO.get(k, k))}</td><td>{v:.2f}</td></tr>' for k, v in sorted(e["points"].items(), key=lambda kv: -kv[1]))
    ev = "".join(f'<li>{("<a href=" + chr(34) + E(x["url"]) + chr(34) + ">" + E(x["text"]) + "</a>") if x.get("url") else E(x["text"])}</li>' for x in e["evidence"])
    flags = "".join(f'<li>⚠️ {E(f)}</li>' for f in e.get("flags", []))
    th = "".join(f'<a class="pill" href="../tema/{k}.html">{E(tmap[k]["name"])}</a>' for k in e["themes"] if k in tmap)
    return f"""<h1>{E(e['ticker'])} <span class="mut">{E(e.get('name') or '')}</span> {score_badge(e['score'], 4, 2)}</h1>
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
    extra = ""
    if oilh:
        extra += f'<div class="card tw"><h2 style="margin-top:0">Fysisk oljemarked (futures via Yahoo)</h2><table><tr><th>Mål</th><th>Siste</th><th>z (1 år)</th><th>Trend / kontrakter</th></tr>{oilh}</table><p class="mut">Pålitelighet: markedsdata – høy, men uoffisiell tilgang (yfinance).</p></div>'
    if dodh:
        extra += f'<div class="card tw"><h2 style="margin-top:0">Amerikanske forsvarskontrakter (daglige DoD-kunngjøringer)</h2><table><tr><th>Dag</th><th>Selskap</th><th>Beløp</th><th>Ticker</th><th>Kilde</th></tr>{dodh}</table><p class="mut">Pålitelighet: offisiell kunngjøring – høy. Ticker-kobling er automatisk (navnematch) og kan bomme.</p></div>'
    return f"""<h1>Makro – offisiell statistikk</h1>
<p class="mut">«Overraskelse (z)» = hvor uvanlig siste endring er sammenlignet med de 24 foregående endringene (robust z-score). Ikke det samme som avvik fra analytikerforventning (konsensus er ikke fritt tilgjengelig).</p>
<div class="card tw"><table><tr><th>Serie</th><th>Kilde</th><th>Periode</th><th>Siste</th><th>Endring</th><th>Overr. (z)</th><th>Trend</th><th>Pålitelighet</th></tr>{rows}</table></div>
<div class="card"><h2 style="margin-top:0">Norges Bank</h2>{fxh}<ul class="ev">{press}</ul></div>
{('<div class="card tw"><h2 style="margin-top:0">IMF WEO – BNP-vekst (prognose, %)</h2><table><tr><th>Land</th>' + imf_head + '</tr>' + imf_rows + '</table><p class="mut">Pålitelighet: offisiell prognose – anslag, ikke fasit.</p></div>') if imf else ''}
{('<div class="card"><h2 style="margin-top:0">Nylig oppdatert hos Eurostat</h2><ul class="ev">' + eu + '</ul></div>') if eu else ''}""" + extra


def kalender_page(snap):
    rows = "".join(f'<tr><td>{E(e["date"])}</td><td>{E(e.get("time") or "")}</td><td>{E(e.get("kind",""))}</td><td>{E(e["source"])}</td><td>{E(e["title"])}</td></tr>' for e in snap.get("calendar", []))
    return f"""<h1>Kalender</h1><p class="mut">Tider i norsk tid der kilden oppgir tid. «(estimert)» = beregnet fra fast publiseringsrytme, ikke offisiell kalender. Sentralbankmøter vises 45 dager frem, øvrige 14–21 dager.</p>
<div class="card tw"><table><tr><th>Dato</th><th>Tid</th><th>Type</th><th>Kilde</th><th>Hendelse</th></tr>{rows}</table></div>"""


def oslo_page(snap):
    con = "".join(f'<tr><td>{E(r["published"][:10])}</td><td><b>{E(r["issuer"])}</b></td><td><a href="{E(r["url"])}">{E(r["title"])}</a></td></tr>' for r in snap.get("newsweb_contracts", [])[:40])
    ins = "".join(f'<tr><td>{E(r["published"][:10])}</td><td><b>{E(r["issuer"])}</b></td><td><a href="{E(r["url"])}">{E(r["title"])}</a></td></tr>' for r in snap.get("newsweb_insider", [])[:40])
    sh = "".join(f'<tr><td>{E(r["issuer"])}</td><td>{E(r["ticker"] or "")}</td><td>{r["short_pct"]:.2f}%</td><td>{r["chg_7d"]:+.2f}</td><td>{r["chg_30d"]:+.2f}</td><td class="mut">{E(r["top_holders"])}</td></tr>' for r in snap.get("shorts", []))
    return f"""<h1>Oslo Børs</h1>
<div class="card tw"><h2 style="margin-top:0">Kontrakts- og ordremeldinger (Newsweb, 14 dager)</h2><table><tr><th>Dato</th><th>Selskap</th><th>Melding</th></tr>{con}</table></div>
<div class="card tw"><h2 style="margin-top:0">Meldepliktige handler – primærinnsidere (14 dager)</h2><p class="mut">Tittelen sier ikke alltid om det er kjøp eller salg – åpne meldingen.</p><table><tr><th>Dato</th><th>Selskap</th><th>Melding</th></tr>{ins}</table></div>
<div class="card tw"><h2 style="margin-top:0">Shortposisjoner (Finanstilsynet) – største endringer</h2><p class="mut">Netto shortposisjoner ≥ 0,5 % offentliggjøres. Økende short = noen profesjonelle vedder på fall.</p><table><tr><th>Selskap</th><th>Ticker</th><th>Short</th><th>Endr. 7d (pp)</th><th>Endr. 30d</th><th>Største aktører</th></tr>{sh}</table></div>"""


def kilder_page(snap):
    st = "".join(f'<tr><td>{E(k)}</td><td class="{"ok" if str(v).startswith("ok") else "fail" if "FAIL" in str(v) else "mut"}">{E(v)}</td></tr>' for k, v in snap["status"].items())
    bt = REPORTS / "backtest.md"
    bt_html = ""
    if bt.exists():
        txt = bt.read_text()
        bt_html = '<div class="card"><h2 style="margin-top:0">Historisk validering (backtest)</h2><pre style="white-space:pre-wrap;font-size:.85rem">' + E(txt) + "</pre></div>"
    return f"""<h1>Kilder og metode</h1><div class="warnbox">{DISCLAIMER}</div>
<div class="card"><h2 style="margin-top:0">Slik fungerer det</h2><ol>
<li><b>Innsamling</b> fra gratis, offentlige kilder (ingen betalte tjenester, ingen API-nøkler).</li>
<li><b>Temakart:</b> 10 geopolitiske temaer koblet til sektorer, råvarer og eksempel-tickere (USA og Oslo Børs), med skriftlig begrunnelse.</li>
<li><b>Avviksdeteksjon:</b> for hvert tema og hver ticker sammenlignes siste periode med egen historikk (robust z-score = (siste − median) / (1,4826 × MAD)).</li>
<li><b>Temascore 0–5</b> = vektet snitt av positive, avkortede komponentscorer: GDELT-hendelser, nyhetsvolum, tone, RSS, Google-søk, SEC 8-K, prediksjonsmarkeder, kurs/volum, OFAC.</li>
<li><b>Ticker-poeng</b> = sum av enkle, dokumenterte poeng (innsidekjøp-klynger, kongresskjøp, kontraktsmeldinger, uvanlig volum/kurs, tema-oppmerksomhet).</li></ol>
<h3>Viktige forbehold</h3><ul>
<li>Ingen språkmodell – nøkkelord kan gi feiltreff (f.eks. «strait» eller «war» i andre sammenhenger).</li>
<li>Oppmerksomhet er ikke det samme som avkastning; mye kan allerede være priset inn.</li>
<li>RSS- og Reddit-baseline bygges opp over tid; de første dagene er disse komponentene svake.</li>
<li>Innsidedata (Form 4) kommer inntil 2 virkedager etter handel; kongresshandler inntil 45 dager.</li>
<li>Pålitelighet: offisiell statistikk (høy, men revideres) &gt; markedsdata (høy) &gt; nyheter (middels) &gt; sosiale medier (lav).</li></ul></div>
{bt_html}
<div class="card tw"><h2 style="margin-top:0">Kildestatus ved siste kjøring</h2><table><tr><th>Kilde</th><th>Status</th></tr>{st}</table>
<p class="mut">Full dokumentasjon av kildene: research/sources.md i prosjektet.</p></div>"""
