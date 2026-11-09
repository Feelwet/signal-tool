"""Hjelpere for mandagens læringsrapport (fremoverlogg -> 5/20/60 d meravkastning).

Rettet 09.11 (AnalBot):
1. «flags» leses fra kolonnen i logs/categories.csv (r["flags"]), ikke r.flags – på en pandas-rad er .flags
   DataFrame/Series-attributtet (et Flags-objekt), som havnet som «<Flags(allows_duplicate_labels=True)>» i hver rad.
2. Et vindu teller bare når sluttdagen har en ferdig sluttkurs på tickerens børs: samme stengetidstabell og slingring
   som kurs-bare-for-visning (displayprices.CLOSE/BUFFER_MIN). Ukjent børs -> ikke ferdig.
Endrer ingen kategoriregler, score eller sider.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone


def row_flags(r) -> str:
    """Flaggene som ren tekst («weak_px|high_vol»), tom streng når kolonnen mangler eller er tom."""
    try:
        v = r["flags"]
    except (KeyError, IndexError, TypeError):
        return ""
    if v is None or (isinstance(v, float) and v != v):
        return ""
    if isinstance(v, (list, tuple, set)):
        return "|".join(str(x) for x in v)
    return str(v).strip()


def day_closed(day, sym: str, now: datetime | None = None) -> bool:
    """True når handelsdagen `day` har ferdig sluttkurs på symbolets børs ved tidspunktet `now`."""
    from zoneinfo import ZoneInfo
    from .displayprices import exchange_close, BUFFER_MIN
    ex = exchange_close(sym)
    if ex is None:
        return False                      # ukjent børs: aldri regnet som ferdig
    now = now or datetime.now(timezone.utc)
    loc = now.astimezone(ZoneInfo(ex[0]))
    d = day
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    elif isinstance(d, datetime):          # også pd.Timestamp
        d = d.date()
    if d < loc.date():
        return True
    if d > loc.date():
        return False
    close = loc.replace(hour=ex[1], minute=ex[2], second=0, microsecond=0) + timedelta(minutes=BUFFER_MIN)
    return loc >= close


def window_complete(after_index, h: int, sym: str, now: datetime | None = None) -> bool:
    """`after_index` = handelsdagene etter inngangsdagen (fra kursserien). Vinduet på h handelsdager er komplett når det
    finnes minst h dager OG den h-te dagen har ferdig sluttkurs på børsen."""
    if len(after_index) < h:
        return False
    return day_closed(after_index[h - 1], sym, now)
