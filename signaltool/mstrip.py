"""Markedsstripe øverst i Oversikt (UxBot 29.10): to felt, Brent og Bitcoin. Pris 20 px, «1d x % · 20d y %» 13 px med farge/fortegn,
kilde og dato 11 px grått. Ingen poengsum, signal eller vurderingsord. Dikter aldri opp en pris: mangler data -> «Ingen kursdata»."""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from html import escape as E

NO_DATA = "Ingen kursdata"
ROLL_TIP = "Kontraktsbytte i dag"
ROLL_TIP_20 = "Kontraktsbytte i perioden"   # AnalBot 29.10 (bindende): bytte innenfor 20d-vinduet -> «–»
FIELDS = (
    {"sym": "BZ=F", "title": "Brent-olje, futures (USD/fat)", "dec": 2,
     "tip": "Sluttkurs nærmeste future (BZ=F) · Yahoo · {dato}", "src": "Yahoo BZ=F · {dato}"},
    {"sym": "BTC-USD", "title": "Bitcoin (USD)", "dec": 0,
     "tip": "Dagskurs kl. 00:00 UTC · Yahoo · {dato}", "src": "Yahoo · {dato} kl. 00:00 UTC"},
)


def _num(x: float, dec: int) -> str:
    s = f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")
    return s.replace(" ", "\u00a0")


def _pct(x: float | None) -> tuple[str, str]:
    if x is None:
        return "–", "ms0"
    v = round(x * 100, 1)
    if v == 0:
        return "0,0\u00a0%", "ms0"
    return (f"+{v:.1f}" if v > 0 else f"−{abs(v):.1f}").replace(".", ",") + "\u00a0%", "msu" if v > 0 else "msd"


def _dm(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}"


def roll_day(prev: date, cur: date) -> bool:
    """ICE Brent: front-kontrakten utløper siste virkedag i måneden (to måneder før levering). BZ=F bytter da kontrakt,
    så første kurs i en ny måned er ny kontrakt; dagsendringen mot forrige kurs blander to kontrakter."""
    return (prev.year, prev.month) != (cur.year, cur.month)


def _easter(y: int) -> date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31
    return date(y, mo, (h + l - 7 * m + 114) % 31 + 1)


def _last_monday(y: int, m: int) -> date:
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=d.weekday())


def uk_holidays(y: int) -> set:
    """Engelske bank holidays (ICE Futures Europe følger London). Bare reglene som kan treffe siste virkedag i en måned
    eller ligge nær den: nyttår, langfredag, 2. påskedag, mai-helligdagene, august, jul/2. juledag (med erstatningsdager)."""
    ea = _easter(y)
    hs = {ea - timedelta(days=2), ea + timedelta(days=1), _last_monday(y, 5), _last_monday(y, 8)}
    d = date(y, 5, 1)
    hs.add(d + timedelta(days=(7 - d.weekday()) % 7))          # første mandag i mai
    ny = date(y, 1, 1)
    hs.add(ny + timedelta(days={5: 2, 6: 1}.get(ny.weekday(), 0)))
    x, b = date(y, 12, 25), date(y, 12, 26)
    if x.weekday() == 5:
        hs |= {date(y, 12, 27), date(y, 12, 28)}
    elif x.weekday() == 6:
        hs |= {b, date(y, 12, 27)}
    elif b.weekday() == 5:
        hs |= {x, date(y, 12, 28)}
    else:
        hs |= {x, b}
    return hs


def ice_expiry(y: int, m: int) -> date:
    """ICE Brent-regel: kontrakten utløper siste London-virkedag i måned m (andre måned før leveringsmåneden)."""
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    hs = uk_holidays(y)
    while d.weekday() >= 5 or d in hs:
        d -= timedelta(days=1)
    return d


def roll_dates(start: date, end: date) -> list:
    """Beregnede bytter (ICE-regel) med utløp i [start, end]: (utløpsdato = siste kurs gammel kontrakt, ny front-kontrakt)."""
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        e = ice_expiry(y, m)
        if start <= e <= end:
            dm = (m + 1) % 12 + 1                                 # leveringsmåned = m + 2
            out.append((e, f"{['F','G','H','J','K','M','N','Q','U','V','X','Z'][dm - 1]}{(y + (m + 2 - 1) // 12) % 100:02d}"))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def roll_in_window(d0: date, d1: date) -> bool:
    """Ligger et kontraktsbytte mellom d0 (startkurs) og d1 (siste kurs)? Utløpsdagen e er siste kurs i gammel kontrakt,
    så vinduet blander kontrakter hvis d0 <= e < d1."""
    return any(d0 <= e < d1 for e, _ in roll_dates(d0, d1))


ROLLS_CSV = "logs/brent_rolls.csv"


def write_rolls(path, start: date, end: date) -> None:
    """Logg beregnede byttedatoer (ICE-regel) for AnalBot. Deterministisk: samme innhold hver natt for samme periode."""
    from pathlib import Path
    rows = ["utlop_siste_handelsdag,ny_frontkontrakt_bz,regel"]
    for e, c in roll_dates(start, end):
        rows.append(f"{e.isoformat()},{c},siste London-virkedag i 2. måned før levering (ICE Brent)")
    Path(path).write_text("\n".join(rows) + "\n")


def last_session(now: datetime) -> date:
    """Siste handelsdag med sluttkurs for Brent (ICE stenger 19:30 London; vi bruker 23:00 UTC for Yahoo-oppdatering)."""
    n = now.astimezone(timezone.utc)
    d = n.date() if n.hour >= 23 else n.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def field(f: dict, data: dict | None, now: datetime) -> str:
    ser = (data or {}).get(f["sym"]) or {}
    ds, cs = ser.get("dates") or [], ser.get("close") or []
    pairs = [(date.fromisoformat(d[:10]), float(c)) for d, c in zip(ds, cs) if c is not None and c == c and float(c) > 0]
    t = f'<div class="ms-t">{E(f["title"])}</div>'
    if not pairs:
        return f'<div class="ms-f" data-sym="{E(f["sym"])}">{t}<div class="ms-p ms-na">{NO_DATA}</div></div>'
    d, last = pairs[-1]
    btc = f["sym"] == "BTC-USD"
    shown = d + timedelta(days=1) if btc else d          # BTC: dagsslutt = 00:00 UTC dagen etter Yahoo-datoen
    dato = _dm(shown)
    if len(pairs) >= 2 and not (not btc and roll_day(pairs[-2][0], d)):
        r1, c1 = _pct(last / pairs[-2][1] - 1)
        one = f'<span class="{c1}">1d {r1}</span>'
    elif len(pairs) >= 2:
        one = f'<span class="ms0">1d –</span>{ri(ROLL_TIP)}'
    else:
        one = '<span class="ms0">1d –</span>'
    r20, c20 = _pct(last / pairs[-21][1] - 1) if len(pairs) >= 21 else ("–", "ms0")
    roll20 = (not btc) and len(pairs) >= 21 and roll_in_window(pairs[-21][0], d)
    twenty = f'<span class="ms0">20d –</span>{ri(ROLL_TIP_20)}' if roll20 else f'<span class="{c20}">20d {r20}</span>'
    exp = (now.astimezone(timezone.utc).date() - timedelta(days=1)) if btc else last_session(now)
    stale = d < exp
    warn = (f'<span class="ms-w" aria-label="Kursen er fra {dato}, eldre enn {"i går" if btc else "siste handelsdag"}">⚠ eldre kurs</span>'
            if stale else "")
    return (f'<div class="ms-f" data-sym="{E(f["sym"])}">{t}'
            f'<div class="ms-p">{_num(last, f["dec"])}{ri(f["tip"].format(dato=dato))}</div>'
            f'<div class="ms-c">{one} · {twenty}</div>'
            f'<div class="ms-s">{E(f["src"].format(dato=dato))}{warn}</div></div>')


def ri(tip: str) -> str:
    return (f'<button type="button" class="ri ri-c sc-i" aria-expanded="false" aria-label="{E(tip)}">ⓘ'
            f'<span class="tip">{E(tip)}</span></button>')


def html(snap: dict, now: datetime | None = None) -> str:
    now = now or _now(snap)
    data = snap.get("mstrip")
    return '<div class="mstrip" aria-label="Markedsstripe">' + "".join(field(f, data, now) for f in FIELDS) + "</div>"


def _now(snap: dict) -> datetime:
    g = str(snap.get("generated") or "")
    try:
        from zoneinfo import ZoneInfo
        return datetime.strptime(g[:16], "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(snap.get("timezone") or "Europe/Oslo"))
    except Exception:
        return datetime.now(timezone.utc)


CSS = (".mstrip{display:flex;gap:8px;margin:4px 0 10px;justify-content:flex-start}"
       ".ms-f{box-sizing:border-box;width:200px;padding:6px 10px;border:1px solid var(--bd,#30363d);border-radius:8px;background:var(--card,#161b22)}"
       ".ms-t{font-size:11px;line-height:14px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
       ".ms-p{font-size:20px;line-height:24px;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap}.ms-p .sc-i{font-size:14px;font-weight:400;margin-left:4px;vertical-align:middle}"
       ".ms-na{font-size:14px;line-height:24px;font-weight:400;color:#94a3b8}"
       ".ms-c{font-size:13px;line-height:16px;white-space:nowrap;font-variant-numeric:tabular-nums}.ms-c .sc-i{font-size:14px;vertical-align:middle}"
       ".msu{color:#22c55e}.msd{color:#ef4444}.ms0{color:#94a3b8}"
       ".ms-s{font-size:11px;line-height:14px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ms-w{color:#f59e0b;margin-left:4px}"
       "@media(max-width:699px){.mstrip{gap:6px}.ms-f{flex:1 1 0;width:auto;min-width:0;padding:5px 8px}}")


if __name__ == "__main__":
    import sys
    a = sys.argv[1:]
    write_rolls(a[0] if a else ROLLS_CSV, date(2026, 1, 1), date(2027, 12, 31))
