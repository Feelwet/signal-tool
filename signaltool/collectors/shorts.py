"""Finanstilsynet short-selling register (Oslo Børs net short positions >= 0.5%), public JSON (no key).
https://ssr.finanstilsynet.no/api/v2/instruments  - history of aggregate short % per issuer."""
from __future__ import annotations
import re
import pandas as pd
from .. import http

API = "https://ssr.finanstilsynet.no/api/v2/instruments"


def _norm(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    n = re.sub(r"\b(asa|as|ltd|limited|inc|plc|se|sa|ab|group|holding|holdings|the|co)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def collect() -> tuple[pd.DataFrame, str]:
    try:
        j = http.get_json(API, cache_hours=6, timeout=90)
    except Exception as e:
        return pd.DataFrame(), f"FAILED: {e}"
    rows = []
    now = pd.Timestamp.now().normalize()
    for ins in j:
        ev = sorted(ins.get("events", []), key=lambda e: e["date"])
        if not ev:
            continue
        s = pd.Series({pd.Timestamp(e["date"][:10]): e["shortPercent"] for e in ev})
        last = float(s.iloc[-1])
        def at(days):
            p = s[s.index <= now - pd.Timedelta(days=days)]
            return float(p.iloc[-1]) if len(p) else 0.0
        top = sorted(ev[-1].get("activePositions", []), key=lambda p: -p["shortPercent"])[:3]
        rows.append({"isin": ins["isin"], "issuer": ins["issuerName"], "norm": _norm(ins["issuerName"]),
                     "short_pct": last, "chg_7d": round(last - at(7), 2), "chg_30d": round(last - at(30), 2),
                     "last_change": s.index[-1].date().isoformat(),
                     "top_holders": "; ".join(f"{p['positionHolder']} {p['shortPercent']}%" for p in top)})
    df = pd.DataFrame(rows).sort_values("short_pct", ascending=False)
    return df, f"ok ({len(df)} issuers; {int((df['short_pct'] > 0).sum())} with reported shorts)"


def map_to_tickers(shorts: pd.DataFrame, newsweb_df: pd.DataFrame) -> pd.DataFrame:
    """Attach Oslo tickers by matching normalised issuer names against Newsweb issuers."""
    if shorts.empty or newsweb_df is None or newsweb_df.empty:
        return shorts.assign(ticker=None)
    m = newsweb_df.drop_duplicates("issuer")[["issuer", "issuer_name"]].copy()
    m["norm"] = m["issuer_name"].map(_norm)
    lut = dict(zip(m["norm"], m["issuer"]))
    return shorts.assign(ticker=shorts["norm"].map(lambda n: (lut.get(n) + ".OL") if lut.get(n) else None))
