"""AnalBot 11.11 (bindende): bare barer der børsens stengetid + 30 min har passert (børsens egen tidssone; stengetidstabellen
displayprices.CLOSE inkl. .CO/.DE; samme regel som laering_fwd.day_closed). Dagens bar før det er intradag og brukes ikke.
Ukjent børs: aldri gyldig. Brukes av papirbøkene, GS-indeksen, learn_raw og siste kurs i Siden-avkastningen."""
from __future__ import annotations

from datetime import datetime, timezone


def ok(sym: str, d, now: datetime | None = None) -> bool:
    """True når handelsdagen d har ferdig sluttkurs for sym ved `now` (UTC nå som standard)."""
    from .displayprices import exchange_close
    from .laering_fwd import day_closed
    if not d or exchange_close(sym) is None:
        return False
    return day_closed(str(d)[:10], sym, now or datetime.now(timezone.utc))


def series(ser: dict | None, sym: str, now: datetime | None = None) -> dict:
    """{dato: kurs} uten barer som ikke er lukket (i praksis dagens bar før stengetid + 30)."""
    now = now or datetime.now(timezone.utc)
    return {d: v for d, v in (ser or {}).items() if ok(sym, d, now)}


def last(ser, sym: str, now: datetime | None = None):
    """(kurs, dato) for siste lukkede bar. ser = {dato: kurs} eller [(dato, kurs), ...]. (None, None) når ingen."""
    items = ser.items() if isinstance(ser, dict) else (ser or [])
    now = now or datetime.now(timezone.utc)
    best = None
    for d, v in items:
        if v is None or v != v:
            continue
        if ok(sym, d, now) and (best is None or str(d) > best[1]):
            best = (float(v), str(d)[:10])
    return best or (None, None)


def gen_time(snap: dict):
    """Når snapshotets kurser ble hentet (snap['generated'], Oslo-tid). None = ukjent (da brukes aldri snapshotets kurs)."""
    from zoneinfo import ZoneInfo
    try:
        return datetime.strptime(str(snap.get("generated") or ""), "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Europe/Oslo"))
    except ValueError:
        return None
