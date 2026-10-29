"""Ferskhetsvarsel og «Ingen handel» per rad (godkjent plan 29.10, tiltak 7).

- Ferskhetsvarsel: siste sluttkurs er eldre enn siste handelsdag for børsen (freshness.expected_session, regnet fra
  kjøringstidspunktet snap["generated"], Oslo-tid). Helligdager er ikke med i kalenderen; ukjent børs gir ingen varsel.
- «Ingen handel»: bare når volumet for dagens bar (stats.vol_1d, Yahoo) er 0 og baren er siste handelsdag.
  Uendret kurs alene gir aldri merket. Mangler volumet, vises ingenting."""
from __future__ import annotations

from datetime import date, datetime
from html import escape as E
from zoneinfo import ZoneInfo

from . import freshness as F

NOW: list = [None]   # settes av site.build() fra snap["generated"]
NO_TRADE = "Ingen handel"
NO_TRADE_TIP = "Volum 0 på siste handelsdag: ingen handel, ikke uendret kurs."


def set_now(generated: str | None) -> None:
    try:
        NOW[0] = datetime.fromisoformat(str(generated)).replace(tzinfo=ZoneInfo("Europe/Oslo")) if generated else None
    except ValueError:
        NOW[0] = None


def _dm(d) -> str:
    d = str(d)[:10]
    return f"{d[8:10]}.{d[5:7]}"


def lag(e: dict, now: datetime | None = None) -> tuple[str, str] | None:
    """(kursdato, forventet handelsdag) når kursen er eldre enn siste handelsdag; ellers None."""
    st = e.get("stats") or {}
    last = str(st.get("last_date") or "")[:10]
    if not last or st.get("close") is None:
        return None
    exp = F.expected_session(e.get("ticker"), now or NOW[0]) if (now or NOW[0]) else None
    if exp is None:
        return None
    return (last, exp.isoformat()) if last < exp.isoformat() else None


def no_trade(e: dict, now: datetime | None = None) -> bool:
    st = e.get("stats") or {}
    v = st.get("vol_1d")
    if v is None or v != v:
        return False
    try:
        return float(v) == 0 and lag(e, now) is None
    except (TypeError, ValueError):
        return False


def stale_text(l: tuple[str, str]) -> str:
    return f"Kurs per {_dm(l[0])}, eldre enn siste handelsdag ({_dm(l[1])})."


def chips(e: dict) -> str:
    """Små merker på tickerlinjen i lista."""
    out = ""
    l = lag(e)
    if l:
        out += f'<span class="frs" title="{E(stale_text(l))}" aria-label="{E(stale_text(l))}">⚠ Kurs {_dm(l[0])}</span>'
    if no_trade(e):
        out += f'<span class="ntr" title="{E(NO_TRADE_TIP)}" aria-label="{E(NO_TRADE_TIP)}">{NO_TRADE}</span>'
    return out


def line(e: dict) -> str:
    """Linje på tickersiden."""
    parts = []
    l = lag(e)
    if l:
        parts.append(f'<p class="frs-line">⚠ {E(stale_text(l))}</p>')
    if no_trade(e):
        parts.append(f'<p class="frs-line ntr-line">{NO_TRADE}: {E(NO_TRADE_TIP)}</p>')
    return "".join(parts)


CSS = (".frs{display:inline-block;margin-left:6px;padding:0 6px;border-radius:9px;background:#3a2a0b;color:#f59e0b;border:1px solid #f59e0b66;font-size:.8em;white-space:nowrap}"
       ".ntr{display:inline-block;margin-left:6px;padding:0 6px;border-radius:9px;background:#21262d;color:#94a3b8;border:1px solid #30363d;font-size:.8em;white-space:nowrap}"
       ".frs-line{margin:2px 0 4px;font-size:12px;line-height:16px;color:#f59e0b}.frs-line.ntr-line{color:#94a3b8}"
       "@media(max-width:599px){#tf-table .tk .frs,#tf-table .tk .ntr{order:2;font-size:11px;line-height:14px;margin:0}}\n")
