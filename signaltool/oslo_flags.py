"""Oslo Børs red / yellow flags and info tags (research: /workspace/strategy-research RAPPORT.md and RAPPORT_2_monstre.md).

Price flags are RANKED among a broad liquid Oslo universe (median turnover last 20 days >= ~2 MNOK, price >= 1 NOK), exactly as
in the research (xsec_price.py): 12-1 momentum = close 21 sessions ago / close 252 sessions ago - 1; proximity to the 52-week
high = close / max(high, 252 sessions); volatility = std of daily returns over 252 sessions.

  weak_px    (red, blocks Kjøp)  bottom 20 % 12-1 momentum OR bottom 20 % proximity to the 52-week high
  high_vol   (yellow, warning)   top 20 % 1-year volatility  -> half position size in the example plan
  december   (note)              1 Dec - 20 Jan: small loser = bottom 20 % 12-month return among liquid stocks with turnover
                                 below the median (research H24)
  neg_ebit   (red, blocks Kjøp)  EBIT (fallback operating income) < 0 in the latest annual statement (yfinance). Tested 2022-26 only.
  placement  (red, blocks Kjøp)  Newsweb title "private placement / rettet emisjon" (not a trade notification) in the last
                                 60 trading days (research H29)
  buyback    (info tag)          Newsweb category "ACQUISITION OR DISPOSAL OF AN ISSUER'S OWN SHARES" in the last 20 trading days
                                 (research H30b) - NOT a buy signal

Every flag carries its evidence level (FLAG_INFO). Numbers there are copied from the research reports, not computed here.
"""
from __future__ import annotations
import json, logging, re, time
from datetime import date, datetime, timedelta
import numpy as np
import pandas as pd
from .config import CACHE

log = logging.getLogger(__name__)
MIN_ADV_NOK = 2_000_000
FUND_DIR = CACHE / "fund_ol"
RECENT = CACHE / "universe" / "oslo_recent.pkl"
PLACEMENT = re.compile(r"private placement|rettet emisjon", re.I)
NOT_PLACEMENT = re.compile(r"notification of trade|mandatory notification|primary insider", re.I)
BUYBACK_CAT = "ACQUISITION OR DISPOSAL OF AN ISSUER"
PLACEMENT_DAYS, BUYBACK_DAYS = 60, 20   # trading days
LAST_NW: pd.DataFrame | None = None

# key -> (short label, kind, evidence level, evidence text). kind: red = blocks Kjøp, yellow = warning, note, info
FLAG_INFO = {
    "weak_px": ("Svak kurs (Oslo)", "red", "sterk",
                "Laveste 20 % på 12-1-momentum eller avstand til 52-ukers topp blant likvide Oslo-aksjer (≥ ~2 MNOK/dag): "
                "−3,7 % (t −3,5) i 2013–18 og −3,5 % (t −4,2) i 2018–26 over 60 dager mot snittaksjen. Samme fortegn i begge perioder; "
                "overlevelsesskjevhet trekker mot funnet. Ødegaards OSE-momentum (UMD) +15 %/år 1981–2024 (t 4,7)."),
    "neg_ebit": ("Negativt driftsresultat (Oslo)", "red", "moderat – kun testet 2022–26",
                 "Negativ EBIT i siste årsregnskap: −7,6 % (t −5,2) over 60 dager, −5,0 % (t −4,7) også uten kursflagg. "
                 "Bare én kort periode (2022–26, etter grønn-tek-boblen), og regnskapstallene fra Yahoo er ikke punkt-i-tid."),
    "placement": ("Rettet emisjon siste 60 d", "red", "moderat",
                  "Etter første melding om rettet emisjon: −2,0 % (t −2,8) / −1,6 % (t −2,7) første 5 dager og −3,4 % (t −2,6) / −5,6 % (t −2,1) "
                  "over 60 dager mot snittaksjen (2019–22 / 2023–26, n = 95 / 70). Samme fortegn, men |t| < 3 og få hendelser."),
    "high_vol": ("Høy volatilitet (Oslo)", "yellow", "moderat",
                 "Høyeste 20 % på 1-års volatilitet: −4,0 % (t −2,6) / −3,5 % (t −3,3) over 60 dager. Overlapper mye med kursflagget. "
                 "Gult flagg: blokkerer ikke, men halver posisjonsstørrelsen."),
    "december": ("Desember-taper", "note", "svak–moderat",
                 "Små taperaksjer (laveste 20 % på 12 mnd, omsetning under median) gjorde det −6,1 % (t −3,4) dårligere enn snittet fra ~20. des "
                 "til ~20. jan (2013–26). Én av 12 testede måneder, ingen januar-rekyl. Tillegg til kursflagget, ikke eget signal."),
    "buyback": ("Aktivt tilbakekjøp", "info", "svak",
                "Egne-aksjer-melding siste 20 handelsdager: +2,4 % (t 2,1) / +1,7 % (t 1,9) over 60 dager (2019–22 / 2023–26). "
                "Kategorien inkluderer også salg av egne aksjer. Informasjon – ikke kjøpssignal."),
}


# ---------------------------------------------------------------- prices
def universe_prices(fetch: bool = True, today: date | None = None) -> dict[str, pd.DataFrame]:
    """Broad Oslo universe (Close/Volume/High). Uses the backtest cache if it is at most 5 days old; otherwise a
    14-month refresh cached for ~20 hours (one batched yfinance call for ~275 tickers)."""
    from .backtest import universe
    today = today or date.today()
    p = universe.DIR / "oslo.pkl"
    for path in (p, RECENT):
        if path.exists():
            try:
                d = pd.read_pickle(path)
                last = max(v.index[-1] for v in d.values())
                if (today - last.date()).days <= 5 or (path == RECENT and time.time() - path.stat().st_mtime < 20 * 3600):
                    return d
            except Exception as ex:
                log.info("oslo cache %s: %s", path, ex)
    if not fetch:
        return {}
    signs = pd.read_csv(universe.DIR / "oslo_signs.csv")["sign"].tolist() if (universe.DIR / "oslo_signs.csv").exists() else []
    if not signs:
        return {}
    import yfinance as yf
    tick = sorted({f"{s}.OL" for s in signs})
    d = yf.download(tick, period="14mo", progress=False, auto_adjust=True, group_by="ticker", threads=True)
    out = {}
    for t in tick:
        try:
            df = d[t][["Close", "Volume", "High"]].dropna(subset=["Close"])
            if len(df) > 60:
                df.index = pd.to_datetime(df.index).tz_localize(None)
                out[t] = df
        except KeyError:
            pass
    pd.to_pickle(out, RECENT)
    return out


def price_ranks(data: dict[str, pd.DataFrame]) -> tuple[dict, pd.DataFrame]:
    """Latest metrics per ticker + cut-offs computed on the liquid universe. Returns (meta, metrics)."""
    if not data:
        return {}, pd.DataFrame()
    C = pd.DataFrame({t: x["Close"] for t, x in data.items() if not t.startswith("OSEBX")}).sort_index().ffill(limit=3)
    V = pd.DataFrame({t: x["Volume"] for t, x in data.items() if t in C.columns}).reindex(C.index)
    H = pd.DataFrame({t: x["High"] for t, x in data.items() if t in C.columns}).reindex(C.index).ffill(limit=3)
    C = C.iloc[-300:]; V = V.iloc[-300:]; H = H.iloc[-300:]
    last = C.index[-1]
    fresh = C.apply(lambda s: s.last_valid_index()) >= last - pd.Timedelta(days=7)
    m = pd.DataFrame(index=C.columns)
    m["close"] = C.iloc[-1]
    m["adv"] = (C * V).iloc[-20:].median()
    m["mom12_1"] = C.iloc[-22] / C.iloc[-253] - 1 if len(C) >= 253 else np.nan
    hmax = H.iloc[-252:].max().where(H.iloc[-252:].count() >= 240)
    m["hi52"] = C.iloc[-1] / hmax
    r = C.pct_change(fill_method=None).iloc[-252:]
    m["vol252"] = r.std().where(r.count() >= 200)
    m["ret12"] = C.iloc[-1] / C.iloc[-251] - 1 if len(C) >= 251 else np.nan
    liq = (m["adv"] >= MIN_ADV_NOK) & (m["close"] >= 1.0) & fresh
    L = m[liq]
    meta = {"asof": str(last.date()), "n_liquid": int(liq.sum()), "min_adv_nok": MIN_ADV_NOK,
            "mom_q20": _q(L["mom12_1"], .2), "hi52_q20": _q(L["hi52"], .2), "vol_q80": _q(L["vol252"], .8),
            "ret12_q20": _q(L["ret12"], .2), "adv_median": _q(L["adv"], .5)}
    m["liquid"] = liq
    return meta, m


def _q(s, q):
    s = pd.Series(s, dtype=float).dropna()
    return float(s.quantile(q)) if len(s) >= 20 else None


def price_flags(t: str, m: pd.DataFrame, meta: dict, today: date) -> dict:
    """{'metrics':..., 'flags': {key: text}} for one Oslo ticker, using the liquid-universe cut-offs."""
    if m is None or t not in m.index or not meta:
        return {}
    row = m.loc[t]
    val = lambda k: None if pd.isna(row.get(k)) else float(row[k])
    mom, hi, vol, r12, adv = val("mom12_1"), val("hi52"), val("vol252"), val("ret12"), val("adv")
    out = {"mom12_1": mom, "hi52": hi, "vol252": vol, "ret12": r12, "adv": adv, "liquid": bool(row["liquid"]), "flags": {}}
    f = out["flags"]
    weak = []
    if mom is not None and meta.get("mom_q20") is not None and mom <= meta["mom_q20"]:
        weak.append(f"12-1-momentum {mom*100:+.0f} % (laveste 20 %, grense {meta['mom_q20']*100:+.0f} %)")
    if hi is not None and meta.get("hi52_q20") is not None and hi <= meta["hi52_q20"]:
        weak.append(f"{(hi-1)*100:.0f} % under 52-ukers topp (laveste 20 %, grense {(meta['hi52_q20']-1)*100:.0f} %)")
    if weak:
        f["weak_px"] = "svak kurs: " + " og ".join(weak)
    if vol is not None and meta.get("vol_q80") is not None and vol >= meta["vol_q80"]:
        f["high_vol"] = f"høy volatilitet ({vol*np.sqrt(252)*100:.0f} % årlig, høyeste 20 % på Oslo Børs)"
    if in_december_window(today) and r12 is not None and meta.get("ret12_q20") is not None and r12 <= meta["ret12_q20"] \
            and adv is not None and meta.get("adv_median") is not None and adv <= meta["adv_median"]:
        f["december"] = f"desember-taper (12 mnd {r12*100:+.0f} %, liten omsetning) – historisk ekstra svak fram til ~20. januar"
    return out


def decision_fallback(e: dict, meta: dict) -> dict:
    """Ticker missing from the universe cache: use the per-ticker decision data (12-1 momentum, distance to 52-week high
    from closes) against the same cut-offs. No volatility flag (decision data only has 60-day volatility)."""
    d = e.get("decision") or {}
    if not meta or (d.get("mom12_1") is None and d.get("pct_from_hi52") is None):
        return {}
    mom = d.get("mom12_1")
    hi = None if d.get("pct_from_hi52") is None else 1 + d["pct_from_hi52"]
    out = {"mom12_1": mom, "hi52": hi, "liquid": None, "source": "tickerdata", "flags": {}}
    weak = []
    if mom is not None and meta.get("mom_q20") is not None and mom <= meta["mom_q20"]:
        weak.append(f"12-1-momentum {mom*100:+.0f} % (laveste 20 %, grense {meta['mom_q20']*100:+.0f} %)")
    if hi is not None and meta.get("hi52_q20") is not None and hi <= meta["hi52_q20"]:
        weak.append(f"{(hi-1)*100:.0f} % under 52-ukers topp (laveste 20 %, grense {(meta['hi52_q20']-1)*100:.0f} %)")
    if weak:
        out["flags"]["weak_px"] = "svak kurs: " + " og ".join(weak)
    return out


def in_december_window(d: date) -> bool:
    return (d.month == 12) or (d.month == 1 and d.day <= 20)


# ---------------------------------------------------------------- Newsweb events
def _tdays(a: date, b: date) -> int:
    """Trading days (Mon-Fri) from a to b."""
    return int(np.busday_count(a, b))


def newsweb_events(nw: pd.DataFrame, today: date) -> dict[str, dict]:
    """{'<ISSUER>.OL': {'placement': (date, title, url) | None, 'buyback': (date, title, url) | None}} from Newsweb titles/categories."""
    out: dict[str, dict] = {}
    if nw is None or nw.empty:
        return out
    df = nw.copy()
    pub = pd.to_datetime(df["published"], utc=True).dt.tz_convert("Europe/Oslo")
    # after 16:20 Oslo time -> known the next day (research convention)
    df["d0"] = [(p + pd.Timedelta(days=1)).date() if (p.hour, p.minute) >= (16, 20) else p.date() for p in pub]
    title = df["title"].fillna("")
    pl = df[title.str.contains(PLACEMENT) & ~title.str.contains(NOT_PLACEMENT)]
    bb = df[df["category"].fillna("").str.upper().str.startswith(BUYBACK_CAT)]
    for kind, sub, win in (("placement", pl, PLACEMENT_DAYS), ("buyback", bb, BUYBACK_DAYS)):
        for r in sub.sort_values("d0").itertuples():
            if r.d0 > today or _tdays(r.d0, today) > win:
                continue
            t = f"{r.issuer}.OL"
            cur = out.setdefault(t, {}).get(kind)
            if kind == "placement" and cur:     # keep the FIRST message in the window (flag runs 60 d from it)
                continue
            out[t][kind] = {"date": r.d0.isoformat(), "title": r.title, "url": r.url}
    return out


# ---------------------------------------------------------------- EBIT (latest annual statement)
def ebit_latest(t: str, fetch: bool = True, max_age_days: int = 30) -> dict | None:
    """{'fye', 'ebit', 'source'} from a 30-day disk cache, refreshed from yfinance income_stmt."""
    FUND_DIR.mkdir(parents=True, exist_ok=True)
    p = FUND_DIR / f"{t}.json"
    if p.exists():
        try:
            j = json.loads(p.read_text())
            if (datetime.now() - datetime.fromisoformat(j["fetched"])).days <= max_age_days or not fetch:
                return j.get("value")
        except Exception:
            pass
    if not fetch:
        return None
    try:
        import yfinance as yf
        val = ebit_from_statement(yf.Ticker(t).income_stmt)
    except Exception as ex:
        log.info("ebit %s: %s", t, ex)
        return None
    p.write_text(json.dumps({"fetched": datetime.now().isoformat(timespec="seconds"), "value": val}))
    return val


def ebit_from_statement(fin: pd.DataFrame | None) -> dict | None:
    if fin is None or getattr(fin, "empty", True):
        return None
    for col in sorted(fin.columns, reverse=True):
        for name in ("EBIT", "Operating Income"):
            if name in fin.index and pd.notna(fin.at[name, col]):
                return {"fye": str(pd.Timestamp(col).date()), "ebit": float(fin.at[name, col]), "item": name}
    return None


def seed_ebit_cache(fund_pkl: str) -> int:
    """One-off: fill the EBIT cache from an already-downloaded fundamentals pickle ({ticker: {'fin': DataFrame}})."""
    FUND_DIR.mkdir(parents=True, exist_ok=True)
    F = pd.read_pickle(fund_pkl)
    n = 0
    for t, v in F.items():
        if not t.endswith(".OL") or not isinstance(v, dict):
            continue
        val = ebit_from_statement(v.get("fin"))
        (FUND_DIR / f"{t}.json").write_text(json.dumps({"fetched": datetime.fromtimestamp(__import__("os").path.getmtime(fund_pkl)).isoformat(timespec="seconds"), "value": val}))
        n += 1
    return n


# ---------------------------------------------------------------- orchestration
def ticker_flags(t: str, m: pd.DataFrame, meta: dict, ev: dict, today: date, fetch: bool = True, e: dict | None = None) -> dict:
    """All Oslo flags for one ticker: price ranks (fallback: per-ticker decision data), Newsweb placement/buyback, EBIT."""
    o = price_flags(t, m, meta, today) or (decision_fallback(e, meta) if e else {}) or {"flags": {}}
    o.update(ev.get(t, {}))
    if o.get("placement"):
        o["flags"]["placement"] = f"rettet emisjon {o['placement']['date']} (siste {PLACEMENT_DAYS} handelsdager)"
    eb = ebit_latest(t, fetch=fetch)
    if eb:
        o["ebit"] = eb
        if eb["ebit"] < 0:
            o["flags"]["neg_ebit"] = f"negativt driftsresultat i siste årsregnskap ({eb['fye'][:4]}: {eb['ebit']/1e6:,.0f} mill.)".replace(",", " ")
    if o.get("buyback"):
        o["info"] = {"buyback": f"aktivt tilbakekjøp (egne-aksjer-melding {o['buyback']['date']})"}
    return o


def apply(snap: dict, nw: pd.DataFrame | None = None, fetch: bool = True) -> str:
    """Adds e['oslo'] = {metrics..., 'flags': {key: text}, 'placement', 'buyback', 'ebit'} for every .OL ticker."""
    from .categories import _d
    today = _d(snap.get("date")) or date.today()
    ol = [e for e in snap.get("tickers", []) if e["ticker"].endswith(".OL")]
    if not ol:
        return "ok (ingen Oslo-tickere)"
    meta, m = price_ranks(universe_prices(fetch=fetch, today=today))
    if nw is None and fetch:
        try:
            from .collectors import newsweb
            nw, _ = newsweb.collect(days=95)
        except Exception as ex:
            log.warning("newsweb for flags: %s", ex)
    global LAST_NW
    LAST_NW = nw            # reused by theme_maps.apply (same run) to avoid a second Newsweb pass
    ev = newsweb_events(nw, today) if nw is not None else {}
    n_ebit = 0
    for e in ol:
        o = ticker_flags(e["ticker"], m, meta, ev, today, fetch=fetch, e=e)
        n_ebit += bool(o.get("ebit"))
        e["oslo"] = o
    snap["oslo_flags_meta"] = {**meta, "newsweb_days": None if nw is None else 95, "n_ebit": n_ebit}
    return (f"ok ({len(ol)} Oslo-tickere, univers {meta.get('n_liquid', 0)} likvide aksjer per {meta.get('asof')}, "
            f"EBIT for {n_ebit}, Newsweb {'ok' if nw is not None and len(nw) else 'mangler'})")
