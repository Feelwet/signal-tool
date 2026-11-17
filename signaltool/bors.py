"""Børs fra tickersuffiks alene. Aldri gjett, og aldri bruk market i risk_levels.csv.

Share-class (BRK.B, MOG.A) er USA: ett bokstavsuffiks som ikke er en kjent børs.
Bare Oslo og USA rangeres for risikonivå; andre børser får ikke nivå.
"""
from __future__ import annotations

import re
import unicodedata

# Kjente børssuffiks i data eller eksplisitt nevnt (AnalBot: .T, .TWO).
# Ikke utvid med børser vi ikke har dekning for.
EXCHANGE = {
    "OL": "Oslo",
    "DE": "Tyskland",
    "CO": "Danmark",
    "ST": "Sverige",
    "L": "Storbritannia",
    "T": "Japan",
    "TWO": "Taiwan",
    "TW": "Taiwan",
}
UKJENT_BORS = "Ukjent børs"
# Markeder som får risikonivå (rangert innen hver børs).
RANKED = frozenset({"Oslo", "USA"})


def _slug(s: str) -> str:
    t = (s or "").strip().lower().replace("æ", "ae").replace("ø", "o").replace("å", "a")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def bors_of(ticker: str) -> str:
    """Børs/land fra suffiks. Ukjent suffiks → «Ukjent børs». Aldri gjett."""
    t = (ticker or "").strip()
    if not t:
        return UKJENT_BORS
    if "." not in t:
        return "USA"
    suf = t.rsplit(".", 1)[-1]
    if suf in EXCHANGE:
        return EXCHANGE[suf]
    # Ett bokstavsuffiks som ikke er kjent børs (.A, .B, .C, …) = share-class, USA.
    if len(suf) == 1 and suf.isalpha():
        return "USA"
    return UKJENT_BORS


def bors_slug(ticker: str) -> str:
    return _slug(bors_of(ticker))


def suffix_of(ticker: str) -> str:
    t = (ticker or "").strip()
    if "." not in t:
        return ""
    return t.rsplit(".", 1)[-1]
