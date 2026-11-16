"""AnalBot 16.11: tickere som ikke er notert som aksje på Euronext Oslo (Oslo Børs, Euronext Expand, Euronext Growth Oslo).
Kontrollert 16.11.2026 mot Euronext sin aksjeliste for XOSL/XOAS/MERK og Newsweb sin utstederliste. Alle åtte er aktive
Newsweb-utstedere (meldingspliktige, f.eks. obligasjoner), men har ingen aksje på Euronext Oslo. Kilde per ticker i SOURCES.
De tas ut av kandidatlista (og list_members) med «tatt ut: ikke notert». Historikken (categories.csv, gs_index.csv) endres ikke;
i GS-indeksen står de fortsatt som «uten kurs» (n_no_price). Riktige aksjetickere bytter vi ikke inn uten AnalBot (RELATED)."""
from __future__ import annotations

import csv
from pathlib import Path

from .config import LOGS

REASON = "tatt ut: ikke notert"
CHECKED = "2026-11-16"
EQ_LIST = "https://live.euronext.com/en/pd_es/data/stocks/download?mics=XOSL%2CMERK%2CXOAS"
ISSUERS = "https://api3.oslo.oslobors.no/v1/newsreader/issuers"
_ID = {"DIASH": 12676, "ERUGA": 13008, "FLOAT": 11215, "NPRO": 8191, "SEIL": 13055, "SFLN": 11225, "SWG": 13065, "VEOFF": 13048}
NOT_LISTED = frozenset(f"{k}.OL" for k in _ID)
SOURCES = {f"{k}.OL": f"{EQ_LIST} ; {ISSUERS} (issuerId {v}) ; https://newsweb.oslobors.no/search?issuer={v}" for k, v in _ID.items()}
# Aksjer i samme selskap/konsern, notert et annet sted (bare rapportert, ikke byttet inn)
RELATED = {"DIASH.OL": "DSX (NYSE)", "SFLN.OL": "SFL (NYSE)", "VEOFF.OL": "VTURA.OL (Ventura Offshore Holding Ltd., morselskap, Euronext Growth Oslo)"}
LOG = LOGS / "ticker_exclusions.csv"
COLS = ["date", "ticker", "reason", "source"]


def drop(rows: list, key=lambda e: e["ticker"]) -> list:
    return [e for e in rows if key(e) not in NOT_LISTED]


def log_once(path: Path | None = None) -> int:
    """Append-only: én rad per ticker (første gang)."""
    p = Path(path or LOG)
    have = set()
    if p.exists():
        with p.open(newline="") as f:
            have = {r["ticker"] for r in csv.DictReader(f)}
    new = [{"date": CHECKED, "ticker": t, "reason": REASON, "source": SOURCES[t]} for t in sorted(NOT_LISTED) if t not in have]
    if new:
        head = not p.exists() or p.stat().st_size == 0
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            if head:
                w.writeheader()
            w.writerows(new)
    return len(new)
