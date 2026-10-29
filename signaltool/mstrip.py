"""Markedsstripe øverst i Oversikt (UxBot 29.10): to felt, Brent og Bitcoin. Pris 20 px, «1d x % · 20d y %» 13 px med farge/fortegn,
kilde og dato 11 px grått. Ingen poengsum, signal eller vurderingsord. Dikter aldri opp en pris: mangler data -> «Ingen kursdata»."""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from html import escape as E

NO_DATA = "Ingen kursdata"
ROLL_TIP = "Kontraktsbytte i dag"
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
    exp = (now.astimezone(timezone.utc).date() - timedelta(days=1)) if btc else last_session(now)
    stale = d < exp
    warn = (f'<span class="ms-w" aria-label="Kursen er fra {dato}, eldre enn {"i går" if btc else "siste handelsdag"}">⚠ eldre kurs</span>'
            if stale else "")
    return (f'<div class="ms-f" data-sym="{E(f["sym"])}">{t}'
            f'<div class="ms-p">{_num(last, f["dec"])}{ri(f["tip"].format(dato=dato))}</div>'
            f'<div class="ms-c">{one} · <span class="{c20}">20d {r20}</span></div>'
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
