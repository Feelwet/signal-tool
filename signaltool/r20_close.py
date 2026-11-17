"""r20_close (AnalBot 17.11, CLEAR med to rettelser).

Yahoo adj close på siste lukkede bar før kjøringens start (stengetid + 30 min, displayprices.CLOSE /
closedbars), mot baren 20 handelsdager tidligere. Tomt felt med flagg når verdien ikke kan regnes.

r20 i logs/learn_raw.csv for 25.10–17.11 skal ikke brukes (ujustert og/eller én bar bak).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import closedbars as CB
from .displayprices import exchange_close
from .freshness import MAX_TD, tdays_old

STALE_FLAG = "utdatert bar"


def expected_closed(sym: str, now: datetime) -> str | None:
    """Siste dato (man–fre) der stengetid + 30 min har passert ved `now`. None ved ukjent børs."""
    if exchange_close(sym) is None:
        return None
    ex = exchange_close(sym)
    loc = now.astimezone(ZoneInfo(ex[0])).date()
    for _ in range(14):
        if loc.weekday() < 5 and CB.ok(sym, loc, now):
            return str(loc)
        loc -= timedelta(days=1)
    return None


def last_closed(sym: str, ser: dict, now: datetime) -> str | None:
    """Siste dato i `ser` som er en lukket bar ved `now`."""
    best = None
    for d in ser or {}:
        if CB.ok(sym, d, now) and (best is None or str(d) > best):
            best = str(d)[:10]
    return best


def lookback(ser: dict, last: str, n: int = 20):
    """(last, lookback_date, r20) fra adj-serien opp til `last`, eller None ved for kort historikk."""
    ks = [d for d in sorted(ser) if d <= last]
    if len(ks) <= n:
        return None
    a, b = ks[-1], ks[-1 - n]
    pa, pb = ser[a], ser[b]
    if not pb:
        return None
    return {"close_date": a, "lookback_date": b, "close": pa, "lookback": pb, "r20": pa / pb - 1}


def compute(sym: str, ser: dict | None, now: datetime | None = None) -> tuple[str, str]:
    """(r20_close, flagg). r20_close er tom streng når verdien ikke kan brukes.

    Flagg: «utdatert bar» når siste tilgjengelige bar er mer enn MAX_TD (2) handelsdager
    eldre enn forventet siste lukkede bar; ellers ukjent børs / ingen lukket bar /
    for kort historikk / tom serie.
    """
    now = now or datetime.now(timezone.utc)
    if exchange_close(sym) is None:
        return "", "ukjent børs"
    if not ser:
        return "", "mangler Yahoo-data"
    last = last_closed(sym, ser, now)
    exp = expected_closed(sym, now)
    if not last:
        return "", "ingen lukket bar"
    if exp is not None and tdays_old(last, exp) is not None and tdays_old(last, exp) > MAX_TD:
        return "", STALE_FLAG
    lb = lookback(ser, last, 20)
    if not lb:
        return "", "for kort historikk"
    return f"{lb['r20']:.6f}", ""
