"""Decision support per ticker: testable thesis, historical base rates and an example entry/exit/sizing plan.
All numbers come from the snapshot (e['decision'], e['stats'], signal types) and data/base_rates.json (our own backtests).
Rule-based templates only - nothing is invented; missing inputs -> the item says so or is left out."""
from __future__ import annotations
import json
from functools import lru_cache
from .config import DATA
from .categories import TYPE_NO, fx_usd, RULES

BR_FILE = DATA / "base_rates.json"
BR_LABEL = {"pead": "Sterk kvartalsrapport (USA, eksperimentell – punkt-i-tid)", "pead_s": "PEAD-S: sterk rapport + volatilitet over median (USA, eksperimentell)", "insider_cluster": "Innsidekjøp-klynge ≥ 3 ledere (USA)", "gov_contract": "Stor DoD-kontrakt (USA)",
            "ose_contract": "Kontraktsmelding (Oslo)", "ose_insider_buy": "Innsidekjøp (Oslo)", "unusual_volume": "Uvanlig volum (USA)",
            "unusual_volume_ose": "Uvanlig volum (Oslo)", "theme_market": "Tema med markedsbekreftelse (olje/prediksjonsmarked)",
            "rule_kjop": "Kjøp-kursregler oppfylt (på innside-/kontrakthendelser)", "rule_hold": "«Hold-lignende»: signal + strukket kurs",
            "baseline_us": "Til sammenligning: tilfeldig likvid S&P 500-aksje", "baseline_ose": "Til sammenligning: tilfeldig likvid Oslo-aksje"}
BR_ORDER = ["pead", "pead_s", "insider_cluster", "gov_contract", "ose_contract", "ose_insider_buy", "unusual_volume", "unusual_volume_ose", "theme_market",
            "rule_kjop", "rule_hold", "baseline_us", "baseline_ose"]
RISK_PER_TRADE = 0.01      # 1 % of the portfolio at risk per trade
MAX_POSITION = 0.05        # max 5 % per position: no signal here has t >= 3 (Kelly with mu ~1 pp, sigma ~17 pp / 60 d, <= 1/4 Kelly)
HIGH_VOL = 0.50            # annualised 60 d volatility above this (or Oslo top-20 % 1-year volatility) -> half size
MIN_POSITIONS, MAX_SECTOR = (10, 15), 0.30
CONF_MAX_DIST = 0.10       # a confirmation level more than 10 % above today's close is not a useful near-term trigger
TAX = 0.3784               # 22 % x 1.72 on realised gains/dividends outside ASK (2026)
COST_US, COST_OSE = (0.005, 0.010), (0.003, 0.005)   # round trip for a Norwegian retail client
LOW_ADV_USD = 5e6          # median daily turnover below this (USD) -> half size
EXAMPLE_PORTFOLIO = 100_000


@lru_cache(maxsize=1)
def _load(path: str) -> dict:
    try:
        return json.loads(open(path).read())
    except (OSError, ValueError):
        return {}


def base_rates() -> dict:
    return _load(str(BR_FILE))


def signal_keys(e: dict) -> list[str]:
    """Base-rate keys relevant for this ticker (its signal types + category rule + yardstick)."""
    oslo = e["ticker"].endswith(".OL")
    keys = [k for k in (e.get("cat_types") or {}) if k in BR_LABEL]
    if "pead" in keys and (e.get("decision") or {}).get("pead_s"):
        keys.insert(keys.index("pead") + 1, "pead_s")
    pts = e.get("points") or {}
    if pts.get("unusual_volume", 0) > 0:
        keys.append("unusual_volume_ose" if oslo else "unusual_volume")
    if ((e.get("insider_oslo") or {}).get("counts") or {}).get("kjøp"):
        keys.append("ose_insider_buy")
    if pts.get("ose_contracts", 0) > 0 and "ose_contract" not in keys:
        keys.append("ose_contract")
    if e.get("category") == "kjop":
        keys.append("rule_kjop")
    elif e.get("category") == "hold":
        keys.append("rule_hold")
    keys.append("baseline_ose" if oslo else "baseline_us")
    return list(dict.fromkeys(keys))


def _p(x, d=1):
    return "–" if x is None else f"{x*100:+.{d}f} %"


def _lvl(x):
    return "–" if x is None else (f"{x:,.2f}".replace(",", " "))


def levels(e: dict) -> dict:
    """Entry zone, stop (stricter of 50d average / 2xATR, must lie below entry), targets, size. None if inputs are missing."""
    d = e.get("decision") or {}
    close, atr, sma50, sma20, stop_atr = d.get("close"), d.get("atr14"), d.get("sma50"), d.get("sma20"), d.get("stop_atr")
    if not close or not atr:
        return {}
    st = e.get("stats") or {}
    r5, r20 = st.get("ret_5d") or d.get("ret_5d"), st.get("ret_20d") or d.get("ret_20d")
    stretched = ((r5 or 0) >= RULES["stretch_5d"] or (r20 or 0) >= RULES["stretch_20d"]
                 or (sma50 and close / sma50 - 1 >= RULES["stretch_sma"]) or e.get("category") == "hold")
    if stretched and sma20 and sma20 < close:
        lo, hi = sma20 - 0.25 * atr, sma20 + 0.25 * atr
        entry, how = sma20, "vent på tilbakefall mot 20-dagers snitt"
    else:
        lo, hi = close, close + 0.5 * atr
        entry, how = close, "fra dagens kurs opp til +0,5×ATR"
    cands = [(v, n) for v, n in ((sma50, "50-dagers snitt"), (stop_atr if not stretched else entry - 2 * atr, "2×ATR")) if v and v < lo and entry - v >= atr]  # >= 1 ATR away, else inside daily noise
    if not cands:
        return {"entry_lo": lo, "entry_hi": hi, "entry_how": how, "stop": None}
    stop, stop_name = max(cands)                     # the stricter (closest) level below the entry zone
    risk = entry - stop
    dist = risk / entry
    size = min(MAX_POSITION, RISK_PER_TRADE / dist) if dist > 0 else None
    reasons = []
    vol, adv = d.get("vol60"), (st.get("adv20") or 0) * fx_usd(e["ticker"])
    oslo_hv = "high_vol" in (e.get("cat_warnings") or {})
    if size is not None and ((vol and vol > HIGH_VOL) or oslo_hv):
        size /= 2; reasons.append("halvert: høy volatilitet (" + (f"{vol*100:.0f} % årlig" if vol else "") +
                                  (", høyeste 20 % på Oslo Børs" if oslo_hv else "") + ")")
    if size is not None and adv and adv < LOW_ADV_USD:
        size /= 2; reasons.append(f"halvert: lav likviditet (≈ ${adv/1e6:.1f} mill./dag)")
    reg = e.get("_regime") or {}
    if size is not None and reg.get("risk_off"):
        why = [f"{reg.get('name')} under 10-mnd snitt"] if reg.get("below") else []
        if reg.get("high_vol"):
            why.append(f"{reg.get('name')} volatilitet {reg['vol1m']*100:.0f} % > 25 %")
        size /= 2; reasons.append("halvert: markedsregime (" + ", ".join(why) + ")")
    return {"entry_lo": lo, "entry_hi": hi, "entry": entry, "entry_how": how, "stretched": bool(stretched), "stop": stop, "stop_name": stop_name,
            "stop_dist": dist, "target_rr": entry + 2 * risk, "size": size, "size_reasons": reasons}


def _primary(e: dict) -> str | None:
    br = base_rates()
    ks = [k for k in signal_keys(e) if not k.startswith(("baseline", "rule_")) and (br.get(k) or {}).get("n")]
    if "pead_s" in ks:
        return "pead_s"
    return ks[0] if ks else None


def thesis(e: dict, themes: dict | None = None) -> dict:
    """{'tese','bekreftes','avkreftes'} built from the ticker's actual signals and levels."""
    d, t = e.get("decision") or {}, e["ticker"]
    themes = themes or {}
    bn = "OSEBX" if t.endswith(".OL") else "S&P 500"
    types = e.get("cat_types") or {}
    parts = [f"{TYPE_NO.get(k, k)} ({v})" if isinstance(v, str) and v else TYPE_NO.get(k, k) for k, v in types.items()]
    if not parts:
        pts = sorted((e.get("points") or {}).items(), key=lambda kv: -kv[1])
        from .site import POINT_NO  # late import (site imports this module)
        parts = [POINT_NO.get(k, k).lower() for k, v in pts[:2] if v > 0]
    th = [themes[k] for k in e.get("themes", []) if k in themes]
    th_txt = f" innenfor temaet «{th[0]['name']}»" if th else ""
    br, pk = base_rates(), _primary(e)
    hist = ""
    if pk and (br[pk].get("med60") is not None):
        b = br[pk]
        scope = " (målt på klynger med ≥ 3 ledere)" if pk == "insider_cluster" else ""
        hist = f" Historisk slo slike tilfeller{scope} {bn if not pk.startswith('pead') else 'snittaksjen'} i {b['hit60']*100:.0f} % av tilfellene over 60 d (median {_p(b['med60'])})."
        if b.get("net60") is not None:
            hist += f" Snitt {_p(b['mean60'])} brutto, {_p(b['net60'])} etter {b.get('cost', 0)*100:.2f} % kurtasje/valuta – eksperimentelt, svak evidens."
    tese = (f"{t} kan stige fordi: {', '.join(parts)}{th_txt}." if parts else f"{t} har ingen tydelig signaltype i dag.") + hist
    # confirmation: one measurable level
    hi20, hi52, rel20 = d.get("hi20"), d.get("hi52"), d.get("rel_bench_20d")
    if "pead" in types:
        conf = f"kursen holder seg over 20-dagers snitt ({_lvl(d.get('sma20'))}) og analytikerne fortsetter å oppjustere (estimat 30 d i dag {_p(d.get('eps_rev30'))})."
    elif "theme_market" in types and th:
        conf = f"tema-scoren for «{th[0]['name']}» holder seg over 1,5 (i dag {th[0].get('score', 0):.2f})."
    elif near_level(hi20, d.get("close")):
        conf = f"sluttkurs over 20-dagers toppen {_lvl(hi20)} (i dag {_lvl(d['close'])})."
    elif near_level(hi52, d.get("close")):
        conf = f"sluttkurs over 52-ukers toppen {_lvl(hi52)} (i dag {_lvl(d['close'])}, {_p(d['close']/hi52-1)} under)."
    elif d.get("sma20"):
        conf = f"kursen holder seg over 20-dagers snitt ({_lvl(d['sma20'])}) og slår fortsatt {bn} over 20 d (i dag {_p(rel20)})."
    else:
        conf = f"aksjen fortsetter å slå {bn} de neste 20 dagene (siste 20 d: {_p(rel20)})."
    lv = levels(e)
    inv = []
    if lv.get("stop"):
        inv.append(f"sluttkurs under {_lvl(lv['stop'])} ({lv['stop_name']})")
    if d.get("next_earnings") and d.get("days_to_earnings") is not None and 0 <= d["days_to_earnings"] <= 90:
        inv.append(f"neste rapport {d['next_earnings']} skuffer (kursfall på rapportdagen)")
    if th and not inv:
        inv.append(f"tema-scoren faller under 1 (i dag {th[0].get('score', 0):.2f})")
    if not inv:
        inv.append("signalet blir ikke fulgt opp med nye bekreftelser innen 20 handelsdager")
    return {"tese": tese, "bekreftes": conf, "avkreftes": " – eller ".join(inv[:2]) + "."}


def near_level(level, close, max_dist: float = CONF_MAX_DIST) -> bool:
    """A confirmation level must lie ABOVE today's close but at most max_dist (10 %) above it; far targets (e.g. a 52-week
    high 24 % away) are hidden and the rule falls back to the 20-day average / relative strength."""
    try:
        return bool(level and close and close < level and level / close - 1 <= max_dist)
    except TypeError:
        return False


def net_note(e: dict) -> str:
    """Plain note on net result after costs and tax per account type (arithmetic from the research assumptions)."""
    oslo = e["ticker"].endswith(".OL")
    if oslo:
        return (f"Oslo-aksje: kan normalt ligge på aksjesparekonto (ASK) hvis selskapet er hjemmehørende i EØS – da utsettes skatten til uttak. "
                f"Kurtasje ca. {COST_OSE[0]*100:.1f}–{COST_OSE[1]*100:.1f} % tur-retur, spread kommer i tillegg (ofte 0,5–2 % under 5 MNOK dagsomsetning).")
    return (f"US-aksje: kan <b>ikke</b> ligge på ASK – må handles på vanlig aksjekonto, der hver realisert gevinst skattes med {TAX*100:.2f} % "
            f"(22 % × 1,72, etter skjermingsfradrag). Kurtasje + valuta ca. {COST_US[0]*100:.1f}–{COST_US[1]*100:.1f} % tur-retur for små ordre. "
            f"Eksempel: +1,0 pp brutto (beste PEAD-variant) − 0,75 % kostnad ≈ +0,25 pp; etter skatt ≈ +0,16 pp per 60 dager.")


def one_liner(e: dict, themes: dict | None = None) -> str:
    th = thesis(e, themes)
    return f"Bekreftes hvis {th['bekreftes']} Avkreftes hvis {th['avkreftes']}"
