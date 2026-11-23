"""Sjekk at «Oppdatert» ikke er eldre enn 26 timer på en Oslo-handelsdag (man–fre)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

OSLO = ZoneInfo("Europe/Oslo")
MAX_HOURS = 26


def is_oslo_trading_day(dt: datetime) -> bool:
    """Man–fre i Europe/Oslo. Helligdager er ikke med."""
    loc = dt.astimezone(OSLO) if dt.tzinfo else dt.replace(tzinfo=OSLO)
    return loc.weekday() < 5


def parse_updated(html: str, year: int | None = None) -> datetime | None:
    """Les tidspunktet fra data-generated (ISO med sone) eller «Oppdatert DD.MM kl. HH:MM»."""
    m = re.search(r'data-generated="([^"]+)"', html)
    if m:
        try:
            return datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
        except ValueError:
            pass
    m = re.search(r"Oppdatert (\d{2})\.(\d{2}) kl\. (\d{2}):(\d{2})", html)
    if not m:
        return None
    day, month, hh, mm = (int(x) for x in m.groups())
    now = datetime.now(OSLO)
    y = year if year is not None else now.year
    dt = datetime(y, month, day, hh, mm, tzinfo=OSLO)
    if year is None and dt > now + timedelta(days=1):
        dt = dt.replace(year=y - 1)
    return dt


def stale_updated(updated: datetime | None, now: datetime | None = None, hours: float = MAX_HOURS) -> bool:
    """True når sjekken skal feile: `now` er Oslo-handelsdag og Oppdatert er strengt eldre enn `hours` timer.

    Mangler tidspunkt på en handelsdag telles som utdatert. Helg (lør/søn i Oslo) gir alltid False.
    """
    now = now or datetime.now(OSLO)
    now = now.replace(tzinfo=OSLO) if now.tzinfo is None else now.astimezone(OSLO)
    if not is_oslo_trading_day(now):
        return False
    if updated is None:
        return True
    updated = updated.replace(tzinfo=OSLO) if updated.tzinfo is None else updated.astimezone(OSLO)
    return (now - updated) > timedelta(hours=hours)
