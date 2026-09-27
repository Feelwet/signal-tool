"""Run all collectors, compute anomaly scores, and write a JSON snapshot used by the report and website."""
from __future__ import annotations
import json, logging, math, time
from datetime import date, datetime, timedelta
import numpy as np
import pandas as pd
from . import anomaly
from .config import DATA
from .themes import THEMES, THEME_BY_KEY, all_watch_tickers
from .collectors import (gdelt_events, gdelt_doc, rss, markets, trends, sec, congress, usaspending, ofac,
                         reddit, polymarket, kalshi, newsweb, norgesbank, macro, calendar_cb, shorts, oil, dod)

log = logging.getLogger(__name__)
SNAP_DIR = DATA / "snapshots"
SNAP_DIR.mkdir(parents=True, exist_ok=True)

WEIGHTS = {"gdelt_events": 1.0, "gdelt_urls": 1.0, "gdelt_tone": 0.5, "news_rss": 0.75, "google_trends": 0.75,
           "sec_8k": 0.5, "prediction_mkts": 1.0, "price_volume": 0.75, "ofac": 1.0, "physical_oil": 1.0}

COMPONENT_LABELS = {  # Norwegian + English labels used in report/site
    "gdelt_events": "GDELT hendelser (andel konflikt-/tiltakshendelser i temaets land)",
    "gdelt_urls": "GDELT nyhetsvolum (andel artikler med tema-nøkkelord)",
    "gdelt_tone": "GDELT tone (mer negativ enn normalt)",
    "news_rss": "RSS-overskrifter fra store medier",
    "google_trends": "Google Trends søkeinteresse",
    "sec_8k": "SEC 8-K-meldinger som nevner temaet",
    "prediction_mkts": "Prediksjonsmarkeder (største 1-ukes bevegelse)",
    "price_volume": "Kurs/volum-avvik i temaets aksjer",
    "ofac": "OFAC-sanksjonsvedtak siste 14 dager",
    "physical_oil": "Fysisk oljemarked (crack spread, Brent–WTI, z mot 1 år)",
}


def _f(x):
    """JSON-safe float."""
    try:
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else round(x, 4)
    except (TypeError, ValueError):
        return None


def _records(df: pd.DataFrame, cols=None, n=None) -> list[dict]:
    if df is None or df.empty:
        return []
    d = df[cols] if cols else df
    if n:
        d = d.head(n)
    out = json.loads(d.to_json(orient="records", date_format="iso", default_handler=str))
    return out


def run(fast: bool = False) -> dict:
    t0 = time.time()
    status: dict[str, str] = {}
    snap: dict = {"date": date.today().isoformat(), "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                  "timezone": "Europe/Oslo"}

    # ---------- GDELT daily events ----------
    latest = gdelt_events.latest_available()
    gser = pd.DataFrame()
    if latest:
        gdelt_events.backfill(latest - timedelta(days=75), latest)
        gser = gdelt_events.load_theme_series(latest - timedelta(days=75), latest)
        status["GDELT 1.0 daily events"] = f"ok (latest {latest}, {len(gser)} days baseline)"
    else:
        status["GDELT 1.0 daily events"] = "FAILED: no recent file"
    snap["gdelt_latest"] = latest.isoformat() if latest else None

    # ---------- GDELT DOC API (often rate limited) ----------
    first = THEMES[0]
    _, status["GDELT DOC 2.0 API"] = gdelt_doc.collect({first.key: " OR ".join(f'"{k}"' for k in first.keywords[:3])})
    if not status["GDELT DOC 2.0 API"].startswith("ok"):
        status["GDELT DOC 2.0 API"] += " -> using GDELT daily event files instead"

    # ---------- News RSS ----------
    heads, rss_status = rss.collect()
    ok_feeds = sum(v.startswith("ok") for v in rss_status.values())
    status["News RSS"] = f"ok ({ok_feeds}/{len(rss_status)} feeds)" + (
        "; failed: " + ", ".join(k for k, v in rss_status.items() if not v.startswith("ok")) if ok_feeds < len(rss_status) else "")
    rss_daily = rss.theme_daily_counts(heads)

    # ---------- Markets ----------
    watch = all_watch_tickers() + ["SPY"]
    mstats, mdata, status["Prices (yfinance)"] = markets.collect(watch)

    # ---------- Google Trends ----------
    if fast:
        tr, status["Google Trends (pytrends)"] = {}, "skipped (--fast)"
    else:
        tr, status["Google Trends (pytrends)"] = trends.collect({t.key: t.trends_terms for t in THEMES})

    # ---------- SEC ----------
    ek, ek_examples, status["SEC EDGAR 8-K full-text"] = sec.eightk_weekly_counts(weeks=13)
    tx, status["SEC EDGAR Form 4"] = sec.fetch_form4_transactions(days=7, cap=800 if fast else 2500)
    clusters = sec.insider_buy_clusters(tx)
    if not clusters.empty:
        clusters = clusters[~clusters["ticker"].fillna("").str.upper().isin(["", "NONE", "N/A", "NA"])]
    nt, status["SEC late-filing notices (NT 10-K/Q)"] = sec.forensic_late_filings()

    # ---------- other sources ----------
    cong, status["US House PTR (congress trades)"] = congress.collect(days=45)
    status["US Senate eFD"] = "not automated (requires interactive terms acceptance); see research/sources.md"
    awards, status["USAspending awards"] = usaspending.collect()
    status["SAM.gov"] = "not used (API requires free key via sign-up)"
    ofa, status["OFAC recent actions"] = ofac.collect()
    red, status["Reddit (public RSS)"] = reddit.collect()
    pm, status["Polymarket (Gamma API)"] = polymarket.collect()
    ka, status["Kalshi"] = kalshi.collect()
    nw, status["Oslo Børs Newsweb"] = newsweb.collect(days=60)
    nb, status["Norges Bank"] = norgesbank.collect()
    oilx, status["Oil spreads & curves (yfinance futures)"] = oil.collect()
    dodx, dod_days, status["US DoD daily contracts (war.gov)"] = dod.collect()
    sh, status["Finanstilsynet short register"] = shorts.collect()
    sh = shorts.map_to_tickers(sh, nw)
    mac, mac_status = macro.collect()
    status.update(mac_status)
    cb, cb_status = calendar_cb.collect()
    status.update(cb_status)
    eq_tickers = [t for th in THEMES for t in th.tickers_us + th.tickers_ose + th.tickers_other]
    eq_tickers = [t for t in dict.fromkeys(eq_tickers) if t not in ("ITA", "BDRY", "FXI", "EWW", "REMX", "SMH", "SPY", "FEZ", "EWZ", "EWG", "XLE", "JETS", "XRT", "GLD", "GDX")]
    earn, status["Earnings calendar (yfinance)"] = ([], "skipped (--fast)") if fast else markets.earnings_calendar(eq_tickers)

    # ---------- theme scoring ----------
    themes_out = []
    for th in THEMES:
        comp: dict[str, dict] = {}
        def add(name, score, detail):
            comp[name] = {"score": _f(score), "weight": WEIGHTS[name], "detail": detail, "label": COMPONENT_LABELS[name]}
        if not gser.empty:
            z, info = anomaly.robust_z(gser[f"{th.key}_share"], recent_n=2, baseline_n=60)
            add("gdelt_events", z, f"siste 2 dager {info.get('recent', float('nan')):.3f}% av alle GDELT-artikler vs median {info.get('baseline_median', float('nan')):.3f}% (60 dager)" if info.get("recent") is not None else "for kort historikk")
            z, info = anomaly.robust_z(gser[f"{th.key}_url"], recent_n=2, baseline_n=60)
            add("gdelt_urls", z, f"{info.get('recent', float('nan')):.2f}% av kilde-URLer vs median {info.get('baseline_median', float('nan')):.2f}%" if info.get("recent") is not None else "for kort historikk")
            z, info = anomaly.robust_z(-gser[f"{th.key}_tone"], recent_n=2, baseline_n=60)
            add("gdelt_tone", z, f"tone {-info.get('recent', float('nan')):.2f} vs median {-info.get('baseline_median', float('nan')):.2f} (lavere = mer negativ)" if info.get("recent") is not None else "")
        if not rss_daily.empty and th.key in rss_daily.columns:
            s = rss_daily[th.key].asfreq("D", fill_value=0)
            run_days = rss.collection_days()
            z, info = anomaly.robust_z(s.iloc[:-1] if len(s) > 1 else s, recent_n=1, baseline_n=30, min_baseline=7)
            if run_days < 7:   # feeds only carry 1-3 days of items; a fair baseline needs our own stored history
                z, info = float("nan"), {"n_baseline": 0}
            add("news_rss", z, f"{int(s.iloc[-2]) if len(s) > 1 else int(s.iloc[-1])} overskrifter i går; " +
                ("baseline bygges opp (trenger ≥7 dager lagret historikk)" if info.get("n_baseline", 0) < 7 else f"median {info.get('baseline_median'):.0f}/dag"))
        if th.key in tr:
            s = tr[th.key].mean(axis=1)
            z, info = anomaly.robust_z(s, recent_n=3, baseline_n=60)
            add("google_trends", z, f"snitt siste 3 dager {info.get('recent', 0):.1f} vs median {info.get('baseline_median', 0):.1f} (søk: {', '.join(th.trends_terms)})")
        if not ek.empty and th.key in ek.columns:
            s = ek[th.key]
            z, info = anomaly.robust_z(s, recent_n=1, baseline_n=12, min_baseline=8)
            add("sec_8k", z, f"{int(s.iloc[-1])} 8-K siste uke vs median {info.get('baseline_median', 0):.0f}/uke (søk {sec.EIGHTK_PHRASES[th.key]})")
        tpm = pd.DataFrame()
        if not pm.empty:
            tpm = pm[pm["themes"].str.contains(th.key, regex=False) & (pm["volume_24h"] >= 10_000) & ~pm["resolving_soon"]].copy()
            if not tpm.empty:
                tpm["abs1w"] = tpm["chg_1w"].abs()
                mv = tpm["abs1w"].max()
                add("prediction_mkts", (mv or 0) / 0.05, f"største 1-ukes endring {mv*100:.1f} prosentpoeng blant {len(tpm)} likvide markeder (score = pp/5)")
        tick = [t for t in th.all_tickers + th.commodities if t in mstats.index]
        if tick:
            sub = mstats.loc[tick]
            v = pd.to_numeric(sub["vol5_z"], errors="coerce").mean()
            r = pd.to_numeric(sub["ret5_z"], errors="coerce").abs().mean()
            add("price_volume", np.nanmean([v, r]), f"snitt volum-z (5d) {v:.2f}, snitt |5d avkastning-z| {r:.2f} over {len(tick)} instrumenter")
        if not ofa.empty and th.key in ("sanctions_energy", "mideast_energy", "conflict_defense"):
            o = ofa.copy()
            if th.key == "mideast_energy":
                o = o[o["title"].str.contains("Iran", case=False)]
            elif th.key == "conflict_defense":
                o = o[o["title"].str.contains("Russia|Belarus|Ukraine", case=False, regex=True)]
            o = o[o["designations"]]
            wk = o.set_index("date").resample("W").size()
            full = pd.Series(0, index=pd.date_range(ofa["date"].min(), pd.Timestamp(date.today()), freq="W"))
            wk = full.add(wk, fill_value=0)
            recent14 = int((o["date"] >= pd.Timestamp(date.today() - timedelta(days=14))).sum())
            z, info = anomaly.robust_z(wk.rolling(2).sum().dropna(), recent_n=1, baseline_n=20, min_baseline=8)
            add("ofac", z, f"{recent14} relevante sanksjonsvedtak (designations) siste 14 dager")
        if oilx and th.key in ("mideast_energy", "sanctions_energy"):
            zs = {k: v["z"] for k, v in oilx.items() if v.get("z") is not None}
            if zs:
                kmax = max(zs, key=lambda k: abs(zs[k]))
                add("physical_oil", abs(zs[kmax]), "; ".join(f"{oilx[k]['label']}: {oilx[k]['last']} (z={v:+.1f})" for k, v in zs.items()))
        score = anomaly.weighted_positive_score(comp)
        # evidence
        th_heads = heads[heads["themes"].fillna("").str.contains(th.key, regex=False)].sort_values("published", ascending=False) if not heads.empty else pd.DataFrame()
        th_heads = th_heads[th_heads["published"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=3)] if not th_heads.empty else th_heads
        red_th = red[red["themes"].fillna("").str.contains(th.key, regex=False)] if not red.empty else pd.DataFrame()
        tick_rows = []
        for t in th.all_tickers + th.commodities + th.losers:
            if t in mstats.index:
                st = mstats.loc[t]
                tick_rows.append({"ticker": t, "role": "taper" if t in th.losers else ("råvare/FX" if t in th.commodities else "vinner ved eskalering"),
                                  **{k: _f(st.get(k)) for k in ["close", "ret_1d", "ret_5d", "ret_20d", "ret5_z", "vol5_z", "vol_ratio_5d"]},
                                  "last_date": st.get("last_date")})
        series = {}
        if not gser.empty:
            series = {"dates": [d.strftime("%Y-%m-%d") for d in gser.index],
                      "share": [_f(x) for x in gser[f"{th.key}_share"]], "url": [_f(x) for x in gser[f"{th.key}_url"]]}
        themes_out.append({
            "key": th.key, "name": th.name, "score": score, "components": comp,
            "reasoning": th.reasoning, "sectors": th.sectors, "escalation": th.escalation,
            "deescalation": th.deescalation, "risks": th.risks, "tickers_us": th.tickers_us, "tickers_ose": th.tickers_ose,
            "tickers_other": th.tickers_other, "losers": th.losers, "commodities": th.commodities,
            "headlines": _records(th_heads, ["source", "title", "link", "published"], 12),
            "headline_count_3d": int(len(th_heads)),
            "reddit": _records(red_th.sort_values("published", ascending=False) if not red_th.empty else red_th, ["sub", "title", "link"], 6),
            "polymarket": _records(tpm.assign(_m=tpm["chg_1w"].abs().fillna(0)).sort_values(["_m", "volume_24h"], ascending=False) if not tpm.empty else tpm,
                                   ["question", "p_yes", "chg_1d", "chg_1w", "volume_24h", "url"], 8),
            "eightk_examples": ek_examples.get(th.key, []), "tickers": tick_rows, "gdelt_series": series,
        })
    themes_out.sort(key=lambda x: x["score"], reverse=True)
    snap["themes"] = themes_out
    theme_score = {t["key"]: t["score"] for t in themes_out}

    # ---------- ticker candidates ----------
    cand: dict[str, dict] = {}
    def c(t):
        return cand.setdefault(t, {"ticker": t, "points": {}, "evidence": [], "themes": []})
    for th in THEMES:
        for t in th.all_tickers:
            c(t)["themes"].append(th.key)
    # insider clusters (US)
    if not clusters.empty:
        for _, r in clusters[clusters["cluster"]].head(25).iterrows():
            if not r["ticker"] or r["ticker"] in ("NONE", "N/A"):
                continue
            e = c(r["ticker"])
            # modest weight: our 2022-2025 backtest (reports/backtest.md) found no excess return after cluster filings
            e["points"]["insider_cluster"] = min(2.0, 0.5 * r["n_insiders"])
            e["evidence"].append({"text": f"SEC Form 4: {r['n_insiders']} innsidere kjøpte i markedet for ${r['total_value']:,.0f} ({r['owners']}; {r['roles']})", "url": r["url"]})
            e["name"] = r["issuer"]
    # congress buys
    if not cong.empty:
        buys = cong[(cong["type"] == "P") & (cong["asset_type"] == "ST")]
        for t, g in buys.groupby("ticker"):
            e = c(t)
            # low weight: research (research/x_accounts) found politician trades rarely preceded moves
            e["points"]["congress_buys"] = min(1.0, 0.5 * float(g["member"].nunique()))
            e["evidence"].append({"text": f"Kongressen (House PTR): kjøp av {', '.join(sorted(g['member'].unique())[:3])} ({g['amount'].iloc[0]})", "url": g["url"].iloc[0]})
    # Oslo Børs announcements
    if not nw.empty:
        recent = nw[nw["published"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=14)]
        for iss, g in recent.groupby("issuer"):
            t = f"{iss}.OL"
            ncon, nins = int(g["contract"].sum()), int(g["insider_trade"].sum())
            if ncon == 0 and nins == 0 and t not in cand:
                continue
            e = c(t)
            e["name"] = g["issuer_name"].iloc[0]
            if ncon:
                e["points"]["ose_contracts"] = min(3.0, 1.5 * ncon)
                row = g[g["contract"]].iloc[0]
                e["evidence"].append({"text": f"Newsweb: {ncon} kontrakt-/ordremelding(er) siste 14 d, f.eks. «{row['title']}»", "url": row["url"]})
            if nins:
                e["points"]["ose_insider_notices"] = min(2.0, 0.5 * nins)
                row = g[g["insider_trade"]].iloc[0]
                e["evidence"].append({"text": f"Newsweb: {nins} meldepliktige handler (primærinnsidere) siste 14 d – retning (kjøp/salg) må sjekkes i meldingen", "url": row["url"]})
    # US federal awards
    if not awards.empty:
        for _, r in awards.dropna(subset=["ticker"]).iterrows():
            e = c(r["ticker"])
            e["points"]["federal_award"] = min(2.0, e["points"].get("federal_award", 0) + 1.0)
            e["evidence"].append({"text": f"USAspending: ny kontrakt ${r['Award Amount']/1e6:,.0f}M fra {r['Awarding Agency']}", "url": r["url"]})
    # DoD daily contract awards (policy/official signal - weighted relatively high)
    if not dodx.empty:
        for t, g in dodx.dropna(subset=["ticker"]).groupby("ticker"):
            e = c(t)
            e["points"]["dod_contract"] = min(3.0, 1.0 + g["amount"].sum() / 1e9)
            top = g.sort_values("amount", ascending=False).iloc[0]
            e["evidence"].append({"text": f"DoD-kontrakt(er): {len(g)} stk, totalt ${g['amount'].sum()/1e6:,.0f}M ({top['day']})", "url": top["url"]})
    # reddit cashtags
    if not red.empty:
        rr = red[red["published"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=2)]
        tags = rr["cashtags"].fillna("").str.split("|").explode()
        for t, n in tags[tags != ""].value_counts().items():
            if n >= 2 and t in cand:
                cand[t]["points"]["reddit_mentions"] = min(1.0, 0.25 * n)
                cand[t]["evidence"].append({"text": f"Reddit: {n} innlegg med ${t} siste 2 dager", "url": f"https://www.reddit.com/search/?q=%24{t}"})
    # Oslo short positions (risk flag, not added to score)
    if not sh.empty:
        for _, r in sh.dropna(subset=["ticker"]).iterrows():
            if r["ticker"] in cand and (abs(r["chg_7d"]) >= 0.2 or r["short_pct"] >= 2):
                cand[r["ticker"]].setdefault("flags", []).append(
                    f"Short {r['short_pct']:.2f}% av aksjene (endring 7d {r['chg_7d']:+.2f} pp, 30d {r['chg_30d']:+.2f} pp) – {r['top_holders']}")
    # prices for discovered tickers
    extra = [t for t in cand if t not in mstats.index]
    if extra:
        es, ed, _ = markets.collect(extra)
        if not es.empty:
            mstats = pd.concat([mstats, es])
    for t, e in cand.items():
        if t in mstats.index:
            st = mstats.loc[t]
            e["stats"] = {k: _f(st.get(k)) for k in ["close", "ret_1d", "ret_5d", "ret_20d", "ret5_z", "vol5_z", "vol_ratio_5d"]}
            e["stats"]["last_date"] = st.get("last_date")
            vz = e["stats"].get("vol5_z")
            if vz is not None and vz > 1.5:
                e["points"]["unusual_volume"] = round(min(3.0, vz - 0.5), 2)
                e["evidence"].append({"text": f"Uvanlig volum: snitt siste 5 dager {e['stats']['vol_ratio_5d']:.1f}x normalt (z={vz:.1f})", "url": f"https://finance.yahoo.com/quote/{t}"})
            rz = e["stats"].get("ret5_z")
            if rz is not None and abs(rz) > 2:
                e["points"]["price_move"] = round(min(2.0, abs(rz) - 1), 2)
                e["evidence"].append({"text": f"Kursbevegelse 5d {e['stats']['ret_5d']*100:+.1f}% (z={rz:.1f} vs eget år)", "url": f"https://finance.yahoo.com/quote/{t}"})
        if e["themes"]:
            best = max(e["themes"], key=lambda k: theme_score.get(k, 0))
            e["points"]["theme_attention"] = round(0.75 * theme_score.get(best, 0), 2)
        e["score"] = round(sum(e["points"].values()), 2)
        e["why"], e["risks"] = explain(e)
    ranked = sorted(cand.values(), key=lambda x: x["score"], reverse=True)
    snap["tickers"] = [e for e in ranked if e["score"] > 0][:60]

    # ---------- raw tables for report/site ----------
    snap["insider_clusters"] = _records(clusters, ["ticker", "issuer", "n_insiders", "n_tx", "total_value", "owners", "roles", "last_date", "url", "cluster"], 30) if not clusters.empty else []
    snap["congress"] = _records(cong.sort_values("filing_date", ascending=False) if not cong.empty else cong, None, 60)
    snap["awards"] = _records(awards, ["Recipient Name", "Award Amount", "Awarding Agency", "Start Date", "Description", "ticker", "url"], 25) if not awards.empty else []
    snap["ofac"] = _records(ofa, ["date", "title", "url", "designations", "relief"], 20) if not ofa.empty else []
    if not nw.empty:
        rec = nw[nw["published"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=14)].sort_values("published", ascending=False)
        snap["newsweb_contracts"] = _records(rec[rec["contract"]], ["published", "issuer", "issuer_name", "title", "url"], 40)
        snap["newsweb_insider"] = _records(rec[rec["insider_trade"]], ["published", "issuer", "issuer_name", "title", "url"], 40)
    pm_top = pm[(pm["themes"] != "") & (pm["volume_24h"] >= 25_000) & ~pm["resolving_soon"]].copy() if not pm.empty else pd.DataFrame()
    if not pm_top.empty:
        pm_top["abs1w"] = pm_top["chg_1w"].abs()
        snap["polymarket_movers"] = _records(pm_top.sort_values("abs1w", ascending=False), ["question", "p_yes", "chg_1d", "chg_1w", "volume_24h", "themes", "url"], 20)
    if "fx" in nb:
        fx = nb["fx"].tail(30)
        snap["nok_fx"] = {"dates": [d.strftime("%Y-%m-%d") for d in fx.index], **{c: [_f(x) for x in fx[c]] for c in fx.columns}}
    snap["norgesbank_press"] = nb.get("press", [])
    snap["oil"] = oilx
    snap["late_filings"] = nt[:30]
    snap["dod_days"] = dod_days[:10]
    snap["dod_awards"] = _records(dodx.sort_values("amount", ascending=False) if not dodx.empty else dodx, ["day", "company", "amount", "ticker", "text", "url"], 25) if not dodx.empty else []
    snap["weekend"] = weekend_summary(heads, pm, ofa, themes_out) if date.today().weekday() >= 5 or (date.today().weekday() == 0 and datetime.now().hour < 9) else None
    snap["shorts"] = _records(sh.assign(absch=sh["chg_7d"].abs()).sort_values(["absch", "short_pct"], ascending=False) if not sh.empty else sh,
                              ["issuer", "ticker", "short_pct", "chg_7d", "chg_30d", "last_change", "top_holders"], 25)
    snap["macro"] = mac
    today_s = date.today().isoformat(); horizon = (date.today() + timedelta(days=14)).isoformat()
    cal = [dict(e, kind="makro") for e in mac.get("calendar", [])]
    cal += [dict(e, kind="sentralbank") for e in cb if e["date"] <= (date.today() + timedelta(days=45)).isoformat()]
    cal += [{"date": e["date"], "time": "", "source": "Yahoo", "title": f"Kvartalsrapport {e['ticker']}", "kind": "resultat"} for e in earn]
    snap["calendar"] = sorted(cal, key=lambda e: (e["date"], e.get("time") or ""))
    snap["status"] = status
    snap["runtime_s"] = round(time.time() - t0)
    (SNAP_DIR / f"{snap['date']}.json").write_text(json.dumps(snap, indent=1, default=str))
    (SNAP_DIR / "latest.json").write_text(json.dumps(snap, indent=1, default=str))
    return snap


def weekend_summary(heads, pm, ofa, themes_out) -> dict:
    """What happened since the US close on Friday (22:00 Oslo) - read before futures reopen Sunday 24:00 Oslo."""
    now = pd.Timestamp.now(tz="Europe/Oslo")
    fri = (now - pd.Timedelta(days=(now.weekday() - 4) % 7)).normalize() + pd.Timedelta(hours=22)
    if fri > now:
        fri -= pd.Timedelta(days=7)
    h = heads[heads["published"] >= fri.tz_convert("UTC")] if not heads.empty else heads
    counts = {}
    if not h.empty:
        for k in h["themes"].fillna("").str.split("|").explode():
            if k:
                counts[k] = counts.get(k, 0) + 1
    names = {t["key"]: t["name"] for t in themes_out}
    top_heads = {}
    for k in sorted(counts, key=counts.get, reverse=True)[:5]:
        hh = h[h["themes"].fillna("").str.contains(k, regex=False)].sort_values("published", ascending=False).head(4)
        top_heads[k] = _records(hh, ["source", "title", "link"])
    movers = []
    if not pm.empty:
        m = pm[(pm["themes"] != "") & (pm["volume_24h"] >= 25_000) & ~pm["resolving_soon"]].copy()
        m["a"] = m["chg_1d"].abs()
        movers = _records(m.sort_values("a", ascending=False), ["question", "p_yes", "chg_1d", "url"], 8)
    of = _records(ofa[ofa["date"] >= fri.tz_localize(None).normalize()], ["date", "title", "url"]) if not ofa.empty else []
    return {"since": fri.strftime("%Y-%m-%d %H:%M"), "futures_reopen": "søndag kl. 24:00 norsk tid (CME Globex 18:00 ET)",
            "theme_headline_counts": {names.get(k, k): v for k, v in sorted(counts.items(), key=lambda kv: -kv[1])},
            "top_headlines": {names.get(k, k): v for k, v in top_heads.items()}, "polymarket_1d_movers": movers, "ofac": of}


RISK_TEXT = {
    "insider_cluster": "Vår egen test (2022–2025, ~980 klynger) fant ingen meravkastning etter innsidekjøp-klynger – bruk som bekreftelse, ikke som signal alene.",
    "congress_buys": "Kongresshandler rapporteres med opptil 45 dagers forsinkelse; kan være rutine/rådgiverstyrt.",
    "ose_contracts": "Kontraktsverdi er ofte ikke oppgitt; sjekk størrelse mot selskapets omsetning.",
    "ose_insider_notices": "Meldepliktig handel kan være salg, opsjoner eller aksjelån – les meldingen.",
    "unusual_volume": "Høyt volum kan skyldes indeksendringer, emisjoner eller nyheter som allerede er priset.",
    "price_move": "Stor bevegelse kan bety at nyheten allerede er priset (du er sen).",
    "federal_award": "Store rammekontrakter utbetales over mange år og er ofte forventet av analytikere.",
    "theme_attention": "Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping.",
    "reddit_mentions": "Sosiale medier er støyende og kan være koordinert hype.",
    "dod_contract": "Mange DoD-kontrakter er modifikasjoner av eksisterende avtaler og allerede kjent for markedet.",
}
WHY_TEXT = {
    "insider_cluster": "Flere innsidere kjøper med egne penger samtidig – de kjenner selskapet best.",
    "congress_buys": "Medlem(mer) av Kongressen har kjøpt aksjen nylig.",
    "ose_contracts": "Selskapet har meldt nye kontrakter/ordre på Oslo Børs.",
    "ose_insider_notices": "Primærinnsidere har handlet (sjekk om det er kjøp).",
    "unusual_volume": "Handelsvolumet er uvanlig høyt – noen posisjonerer seg.",
    "price_move": "Kursen har beveget seg uvanlig mye den siste uka.",
    "federal_award": "Selskapet har fått en stor ny kontrakt fra amerikanske myndigheter.",
    "theme_attention": "Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet.",
    "reddit_mentions": "Aksjen diskuteres mer enn normalt på Reddit.",
    "dod_contract": "Selskapet fikk nylig kontrakt(er) fra det amerikanske forsvarsdepartementet (daglig kunngjøring).",
}


def explain(e: dict) -> tuple[str, str]:
    pts = sorted(e["points"].items(), key=lambda kv: kv[1], reverse=True)
    why = " ".join(WHY_TEXT[k] for k, v in pts if v > 0)
    for k in e["themes"][:1]:
        th = THEME_BY_KEY[k]
        why += f" Tema «{th.name}»: {th.escalation}"
    risks = " ".join(RISK_TEXT[k] for k, v in pts if v > 0)
    for k in e["themes"][:1]:
        risks += f" {THEME_BY_KEY[k].deescalation} {THEME_BY_KEY[k].risks}"
    return why.strip(), risks.strip()
