"""Visningsregler for resultater (godkjent plan 29.10, tiltak 2; AnalBot har vetoretten).

- Ingen prosent uten n.
- n < 30: «For få handler (n=X)», ingen prosent. Ordet FLAG vises aldri.
- n ≥ 30: tallet mot indeks og kontroll, med 95 %-intervall.
- Under 5 handelsdager: grått, med ⓘ «Kort periode, mest tilfeldig svingning.»"""
from __future__ import annotations

MIN_N = 30
SHORT_TD = 5
SHORT_TIP = "Kort periode, mest tilfeldig svingning."


def few(n) -> str:
    return f"For få handler (n={int(n or 0)})"


def enough(n) -> bool:
    try:
        return int(n or 0) >= MIN_N
    except (TypeError, ValueError):
        return False


def short_period(td) -> bool:
    return td is not None and td < SHORT_TD


def _p(x: float, d: int = 1) -> str:
    return f"{x * 100:+.{d}f} %".replace(".", ",").replace("-", "−")


def control_text(nc: dict | None, h: int = 20) -> str:
    """Nullkontroll (tilfeldige trekk fra samme univers) fra fremoverloggen. Tom streng når n < 30 eller kontrollen mangler."""
    if not nc or not enough(nc.get("n")) or nc.get("real") is None or nc.get("null_mean") is None:
        return ""
    lo, hi = nc.get("null_p05"), nc.get("null_p95")
    rng = f" (5–95 % av trekkene: {_p(lo)} til {_p(hi)})" if lo is not None and hi is not None else ""
    return f"mot kontroll {h} d: {_p(nc['real'])} mot tilfeldig {_p(nc['null_mean'])}{rng}, n={int(nc['n'])}"
