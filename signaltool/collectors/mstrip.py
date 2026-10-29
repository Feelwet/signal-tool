"""Markedsstripe i Oversikt: Brent (Yahoo BZ=F, sluttkurs nærmeste future) og Bitcoin (Yahoo BTC-USD, dagsslutt 00:00 UTC).
Henter bare kurser; ingen poengsum, signal eller vurdering. Mangler data -> tom liste (siden viser «Ingen kursdata»)."""
from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd
from .. import http as _http

SYMS = ("BZ=F", "BTC-USD")


def _series(df: pd.DataFrame, sym: str) -> pd.Series:
    c = df["Close"]
    s = c[sym] if isinstance(c, pd.DataFrame) and sym in c.columns else c if isinstance(c, pd.Series) else pd.Series(dtype=float)
    return s.dropna()


def collect(now: datetime | None = None) -> tuple[dict, str]:
    now = now or datetime.now(timezone.utc)
    out = {}
    for sym in SYMS:
        try:
            df = _http.yf_download(sym, period="3mo", interval="1d", progress=False, auto_adjust=False)
            s = _series(df, sym)
        except Exception as e:
            out[sym] = {"dates": [], "close": [], "error": str(e)[:120]}
            continue
        if sym == "BTC-USD":
            # Yahoo-dagen D går 00:00–24:00 UTC; dagens bar er ikke ferdig før 00:00 UTC neste dag -> ta bare hele dager.
            s = s[[pd.Timestamp(d).date() < now.date() for d in s.index]]
        else:
            # Brent handles nesten døgnet rundt (ICE åpner 01:00 London): dagens bar er ikke sluttkurs før kvelden -> ta den bare etter 23:00 UTC.
            cut = now.astimezone(timezone.utc)
            s = s[[pd.Timestamp(d).date() < cut.date() or (pd.Timestamp(d).date() == cut.date() and cut.hour >= 23) for d in s.index]]
        s = s.tail(30)
        out[sym] = {"dates": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in s.index], "close": [round(float(x), 4) for x in s]}
    return out, "ok (" + ", ".join(f"{k} {len(v['close'])}" for k, v in out.items()) + ")"
