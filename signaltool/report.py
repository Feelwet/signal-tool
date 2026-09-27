"""Daily markdown report (Norwegian) from a pipeline snapshot."""
from __future__ import annotations
import json
from pathlib import Path
from .config import REPORTS, ROOT

DISCLAIMER = ("**Ikke finansiell rådgivning.** Dette er et automatisk informasjonsverktøy basert på offentlige data og "
              "enkle, transparente regler. Signaler kan være feil, forsinkede eller allerede priset inn. Gjør egne vurderinger.")


def pct(x, d=1):
    return "–" if x is None else f"{x*100:+.{d}f}%"


def num(x, d=2):
    return "–" if x is None else f"{x:.{d}f}"


def md_link(text, url):
    text = str(text).replace("|", "/").replace("[", "(").replace("]", ")")
    return f"[{text}]({url})" if url else text


def render(snap: dict) -> str:
    from .site import _prep
    snap = _prep(snap)
    L = []
    a = L.append
    a(f"# Signalrapport {snap['date']}")
    a(f"_Generert {snap['generated']} (norsk tid). GDELT-data til og med {snap.get('gdelt_latest')}. Kjøretid {snap.get('runtime_s')} s._\n")
    a(DISCLAIMER + "\n")
    wk = snap.get("weekend")
    if wk:
        a(f"## 0. Helgeoppsummering (siden fredag {wk['since']} norsk tid) – futures åpner {wk['futures_reopen']}\n")
        if wk["theme_headline_counts"]:
            a("Overskrifter per tema i helgen: " + ", ".join(f"{k}: {v}" for k, v in wk["theme_headline_counts"].items()) + "\n")
        for k, hs in wk["top_headlines"].items():
            a(f"**{k}:**")
            for h in hs[:3]:
                a(f"- {md_link(h['title'], h['link'])} — _{h['source']}_")
        if wk["polymarket_1d_movers"]:
            a("\n**Største 1-døgns bevegelser i prediksjonsmarkeder:**")
            for m in wk["polymarket_1d_movers"][:6]:
                a(f"- {md_link(m['question'], m['url'])}: {num((m['p_yes'] or 0)*100,0)}% ({num((m['chg_1d'] or 0)*100,1)} pp)")
        if wk["ofac"]:
            a("\n**OFAC i helgen:** " + "; ".join(md_link(o["title"], o["url"]) for o in wk["ofac"]))
        a("")
    a("## 1. Topp fremvoksende temaer\n")
    a("Score 0–5 = vektet snitt av positive avvik (robuste z-scorer) mot temaets egen historikk. Se metode nederst.\n")
    a("| # | Tema | Score | Sterkeste drivere |")
    a("|---|---|---|---|")
    for i, t in enumerate(snap["themes"], 1):
        comps = sorted([(k, v) for k, v in t["components"].items() if v["score"] is not None], key=lambda kv: -kv[1]["score"])
        drivers = ", ".join(f"{k} {v['score']:+.1f}" for k, v in comps[:3])
        a(f"| {i} | {t['name']} | **{t['score']:.2f}** | {drivers} |")
    a("")
    for t in snap["themes"][:5]:
        a(f"### {t['name']} — score {t['score']:.2f}\n")
        a(f"**Hvorfor dette kan bety noe:** {t['reasoning']}\n")
        a(f"- **Ved eskalering:** {t['escalation']}")
        a(f"- **Ved nedtrapping:** {t['deescalation']}")
        a(f"- **Hva kan gå galt:** {t['risks']}\n")
        a("| Komponent | Score (z) | Detalj |")
        a("|---|---|---|")
        for k, v in t["components"].items():
            a(f"| {v['label']} | {num(v['score'])} | {v['detail']} |")
        a("")
        if t["polymarket"]:
            a("**Prediksjonsmarkeder (Polymarket, markedets sannsynlighet):**\n")
            for m in t["polymarket"][:5]:
                a(f"- {md_link(m['question'], m['url'])}: {num((m['p_yes'] or 0)*100,0)}% "
                  f"(1d {num((m['chg_1d'] or 0)*100,1)} pp, 1u {num((m['chg_1w'] or 0)*100,1)} pp, volum 24t ${m['volume_24h']:,.0f})")
            a("")
        if t["tickers"]:
            a("| Ticker | Rolle | 1d | 5d | 20d | 5d-z | Volum-z (5d) |")
            a("|---|---|---|---|---|---|---|")
            for r in t["tickers"]:
                a(f"| {r['ticker']} | {r['role']} | {pct(r['ret_1d'])} | {pct(r['ret_5d'])} | {pct(r['ret_20d'])} | {num(r['ret5_z'],1)} | {num(r['vol5_z'],1)} |")
            a("")
        if t["headlines"]:
            a("**Siste overskrifter:**\n")
            for h in t["headlines"][:6]:
                a(f"- {md_link(h['title'], h['link'])} — _{h['source']}_")
            a("")
        if t["eightk_examples"]:
            a("**Siste 8-K som nevner temaet:** " + "; ".join(md_link(e["company"], e["url"]) for e in t["eightk_examples"][:3]) + "\n")
    a("## 2. Kandidat-tickere\n")
    a("Poeng summeres fra: innsidekjøp-klynger, kongresskjøp, Oslo Børs-kontrakter/innsidemeldinger, føderale kontrakter, "
      "uvanlig volum/kurs, Reddit-omtale og temaets oppmerksomhet. Høy score = mer å undersøke, ikke et kjøpssignal.\n")
    cats = [e for e in snap["tickers"] if e.get("category") in ("kjop", "hold")]
    if any(e.get("category") for e in snap["tickers"]):
        cnt = {k: sum(e.get("category") == k for e in snap["tickers"]) for k in ("kjop", "hold", "watch")}
        a(f"**Kategorier i dag:** Kjøp-kandidat {cnt['kjop']}, Hold {cnt['hold']}, Watchlist {cnt['watch']}. "
          "_Regelbaserte kategorier – ikke personlig finansiell rådgivning, og ikke bevist å slå markedet._\n")
        for e in cats:
            a(f"- **{'Kjøp-kandidat' if e['category'] == 'kjop' else 'Hold'}: {e['ticker']}** – {e.get('cat_reason')}")
        a("")
    linked = [e for e in snap["tickers"] if e["themes"]][:12]
    other = [e for e in snap["tickers"] if not e["themes"]][:8]
    for title, group in (("### 2a. Koblet til geopolitiske temaer", linked), ("### 2b. Annen uvanlig aktivitet (ikke koblet til tema)", other)):
        a(title + "\n")
        for e in group:
            pts = ", ".join(f"{k} {v:.1f}" for k, v in sorted(e["points"].items(), key=lambda kv: -kv[1]))
            st = e.get("stats") or {}
            catl = {"kjop": "Kjøp-kandidat", "hold": "Hold", "watch": "Watchlist"}.get(e.get("category"), "")
            a(f"#### {e['ticker']} {('– ' + e['name']) if e.get('name') else ''} — {e['score']:.2f} poeng" + (f" — **{catl}**" if catl else ""))
            if e.get("cat_reason"):
                a(f"_Kategori: {catl}. Hvorfor: {e['cat_reason']}_\n")
            a(f"_Poeng: {pts}. Kurs {num(st.get('close'))}, 5d {pct(st.get('ret_5d'))}, 20d {pct(st.get('ret_20d'))}._\n")
            for ev in e["evidence"][:5]:
                a(f"- {md_link(ev['text'], ev.get('url'))}")
            for f in e.get("flags", []):
                a(f"- ⚠️ {f}")
            a(f"\n**Hvorfor det kan bety noe:** {e['why']}\n\n**Hva kan gå galt:** {e['risks']}\n")
    if snap.get("insider_clusters"):
        a("## 3. Innsidekjøp i USA (SEC Form 4, siste 7 dager, kjøp i markedet)\n")
        a("| Ticker | Selskap | Innsidere | Verdi | Roller | Klynge |")
        a("|---|---|---|---|---|---|")
        for r in snap["insider_clusters"][:15]:
            a(f"| {r['ticker']} | {md_link(r['issuer'], r['url'])} | {r['n_insiders']} | ${r['total_value']:,.0f} | {r['roles']} | {'ja' if r['cluster'] else ''} |")
        a("")
    if snap.get("oil"):
        a("## 3b. Fysisk oljemarked (futures)\n")
        for k, v in snap["oil"].items():
            extra = f" (z mot 1 år {v['z']:+.1f})" if v.get("z") is not None else ""
            ctr = (" – " + ", ".join(f"{c} {p}" for c, p in v["contracts"].items())) if v.get("contracts") else ""
            a(f"- **{v['label']}:** {v['last']}{extra}{ctr}")
        a("")
    if snap.get("dod_awards"):
        a("## 3c. Amerikanske forsvarskontrakter (daglige DoD-kunngjøringer, største)\n")
        for r in snap["dod_awards"][:12]:
            a(f"- {r['day']}: **{r['company']}** ${r['amount']/1e6:,.1f}M {('(' + r['ticker'] + ')') if r.get('ticker') else ''} — {md_link('kunngjøring', r['url'])}")
        a("")
    if snap.get("newsweb_contracts"):
        a("## 4. Oslo Børs – kontrakts-/ordremeldinger (14 dager)\n")
        for r in snap["newsweb_contracts"][:15]:
            a(f"- {r['published'][:10]} **{r['issuer']}**: {md_link(r['title'], r['url'])}")
        a("")
    if snap.get("shorts"):
        a("## 5. Shortposisjoner Oslo Børs (Finanstilsynet) – største endringer siste 7 dager\n")
        a("| Selskap | Ticker | Short % | Endr. 7d | Endr. 30d | Største |")
        a("|---|---|---|---|---|---|")
        for r in snap["shorts"][:12]:
            a(f"| {r['issuer']} | {r['ticker'] or ''} | {r['short_pct']:.2f} | {r['chg_7d']:+.2f} | {r['chg_30d']:+.2f} | {r['top_holders'][:80]} |")
        a("")
    if snap.get("congress"):
        buys = [r for r in snap["congress"] if r.get("type") == "P" and r.get("ticker")]
        a(f"## 6. Kongresshandler (House PTR, siste 45 dager) – {len(buys)} kjøp\n")
        for r in buys[:15]:
            a(f"- {r['filing_date']} {r['member']}: kjøp **{r['ticker']}** {r['amount']} ({md_link('PDF', r['url'])})")
        a("")
    if snap.get("polymarket_movers"):
        a("## 7. Største bevegelser i geopolitiske prediksjonsmarkeder (1 uke)\n")
        for m in snap["polymarket_movers"][:10]:
            a(f"- {md_link(m['question'], m['url'])}: {num((m['p_yes'] or 0)*100,0)}% (1u {num((m['chg_1w'] or 0)*100,1)} pp)")
        a("")
    mac = snap.get("macro", {})
    if mac.get("series"):
        a("## 8. Makro (offisiell statistikk)\n")
        a("| Serie | Kilde | Periode | Siste | Endring | Overraskelse (z) | Pålitelighet |")
        a("|---|---|---|---|---|---|---|")
        for r in mac["series"]:
            ch = "–" if r["change"] is None else (f"{r['change']:+.2f}%" if r["change_type"] == "%" else f"{r['change']:+.2f}")
            a(f"| {md_link(r['name'], r['url'])} | {r['source']} | {r['last_period']} | {r['last']:.2f} | {ch} | {num(r['surprise_z'],1)} | {r['reliability']} |")
        a("")
    if snap.get("calendar"):
        a("## 9. Kalender – kommende publiseringer og møter\n")
        for e in snap["calendar"][:30]:
            a(f"- {e['date']} {e.get('time') or ''} — **{e['source']}**: {e['title']}")
        a("")
    if snap.get("ofac"):
        a("## 10. OFAC (amerikanske sanksjoner) – siste vedtak\n")
        for r in snap["ofac"][:8]:
            a(f"- {r['date'][:10]}: {md_link(r['title'], r['url'])}")
        a("")
    a("## 11. Kildestatus\n")
    a("| Kilde | Status |")
    a("|---|---|")
    for k, v in snap["status"].items():
        a(f"| {k} | {str(v).replace('|', '/')[:200]} |")
    a("")
    bt = ROOT / "reports" / "backtest.md"
    a("## 12. Metode og validering\n")
    a("- Robust z-score: (siste verdi − median i basisperioden) / (1,4826 × MAD). Basis: 60 dager for GDELT, 12 uker for 8-K, 3 mnd for Google Trends.")
    a("- Temascore = vektet snitt av positive, avkortede (maks 5) komponentscorer. Vekter: " +
      ", ".join(f"{k} {v}" for k, v in __import__('signaltool.pipeline', fromlist=['WEIGHTS']).WEIGHTS.items()) + ".")
    a("- Prediksjonsmarked-score = største 1-ukes sannsynlighetsendring i prosentpoeng / 5 blant markeder med ≥ $10k volum siste 24t.")
    if bt.exists():
        a(f"- Historisk test av signalene: se [backtest.md](backtest.md).")
    a("")
    return "\n".join(L)


def write(snap: dict) -> Path:
    p = REPORTS / f"report_{snap['date']}.md"
    p.write_text(render(snap))
    (REPORTS / "latest.md").write_text(render(snap))
    return p
