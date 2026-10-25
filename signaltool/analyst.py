"""Analyst recommendations (facts only) as an attention line. Never affects score or category."""
import csv, html, logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)
CSV = Path(__file__).resolve().parent.parent / "logs" / "analyst_recs.csv"
RATING = {"kjop": "Kjøp", "hold": "Hold", "selg": "Selg"}
FIRM = "DNB Carnegie"
# Hook: AnalBot's verified re-run of reports/dnb_eval_2026.md sets this text later. No numbers hardcoded.
HIT_RATE_TEXT = None
OLD_DAYS = 90


def norm(t):
    t = (t or "").strip().upper()
    return t.replace("_", "-")


def load(path=CSV, universe=None):
    """Latest verified single recommendation per ticker. Unmatched rows are logged."""
    out, unmatched = {}, []
    try:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
    except FileNotFoundError:
        return {}
    if rows and "verifisert" not in rows[0]:
        return {}
    uni = {norm(u): u for u in universe} if universe is not None else None
    for r in rows:
        if (r.get("verifisert") or "").strip().lower() != "ja":
            continue
        if (r.get("type") or "enkeltanbefaling") != "enkeltanbefaling" or r.get("anbefaling") not in RATING:
            continue
        t = norm(r.get("ticker"))
        if uni is not None:
            if t not in uni:
                unmatched.append(t)
                continue
            t = uni[t]
        if t not in out or r["dato_publisert"] >= out[t]["dato_publisert"]:
            out[t] = r
    if unmatched:
        log.info("analyst_recs: %d verified rows without ticker on site: %s", len(unmatched), ", ".join(sorted(set(unmatched))))
    return out


def _fmt(x):
    return f"{x:,.2f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",")


def _parts(r, close, today):
    d = date.fromisoformat(r["dato_publisert"])
    km = float(r["kursmal"]) if r.get("kursmal") else None
    up = f"{(km / close - 1) * 100:+.0f} % fra dagens kurs" if km and close else None
    return d, km, up, (today - d).days > OLD_DAYS


def line_html(r, close, today=None):
    if not r:
        return ""
    today = today or date.today()
    d, km, up, old = _parts(r, close, today)
    bits = [RATING[r["anbefaling"]]] + ([f"kursmål {_fmt(km)}"] if km else []) + ([up] if up else []) + [d.strftime("%d.%m")]
    info = HIT_RATE_TEXT or "Treffrate under måling"
    tip = f"{info}. Teller ikke i poengsum eller kategori."
    link = html.escape(r.get("lenke") or "")
    txt = html.escape(f"{FIRM}: " + " · ".join(bits))
    a = f'<a href="{link}" rel="noopener">{txt} ↗</a>' if link else txt
    style = ' style="opacity:.55"' if old else ""
    oldtag = ' <span class="pill">eldre anbefaling</span>' if old else ""
    return (f'<p class="analyst mut"{style}>{a} <span class="pill">◌ Bare oppmerksomhet</span>{oldtag} '
            f'<span class="info" title="{html.escape(tip)}" tabindex="0">ⓘ</span></p>')


def tag_html(r, close, today=None):
    if not r:
        return ""
    d, km, up, old = _parts(r, close, today or date.today())
    tip = f"{FIRM}: {RATING[r['anbefaling']]}" + (f", kursmål {_fmt(km)}" if km else "") + f" ({d.strftime('%d.%m')}). Teller ikke i poengsum."
    return f' <span class="pill" title="{html.escape(tip)}" tabindex="0"{" style=\"opacity:.55\"" if old else ""}>DNB</span>'
