"""Central configuration: paths, polite User-Agent, per-host rate limits."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("SIGNAL_DATA", ROOT / "data"))
CACHE = DATA / "cache"
HISTORY = DATA / "history"
REPORTS = ROOT / "reports"
# Tracked (committed) logs that must survive cache loss, e.g. the Kjøp/Hold/Følg forward log. The nightly workflow
# commits changes here back to the repository.
LOGS = Path(os.environ.get("SIGNAL_LOGS", ROOT / "logs"))
for _p in (DATA, CACHE, HISTORY, REPORTS, LOGS):
    _p.mkdir(parents=True, exist_ok=True)

# SEC requires a descriptive User-Agent with contact info (https://www.sec.gov/os/accessing-edgar-data).
# Override with SIGNAL_UA="Your Name your@email" for real use.
USER_AGENT = os.environ.get("SIGNAL_UA", "signal-tool personal research (contact: bot@box.example)")

# Minimum seconds between requests per host (be polite / respect published limits).
RATE_LIMITS = {
    "api.gdeltproject.org": 6.0,        # GDELT asks for max 1 request / 5 s
    "data.gdeltproject.org": 0.2,
    "www.sec.gov": 0.15,                # SEC fair-access: max 10 req/s
    "efts.sec.gov": 0.15,
    "data.sec.gov": 0.15,
    "www.reddit.com": 7.0,
    "gamma-api.polymarket.com": 0.5,
    "clob.polymarket.com": 0.5,
    "api.elections.kalshi.com": 2.0,
    "api3.oslo.oslobors.no": 1.0,
    "ofac.treasury.gov": 2.0,
    "api.usaspending.gov": 1.0,
    "disclosures-clerk.house.gov": 1.0,
    "data.norges-bank.no": 1.0,
    "www.norges-bank.no": 1.0,
}
DEFAULT_RATE = 1.0

# AV (AnalBot 2026-10-25): live-regelen bruker faste grenser (15 % / 4 %), ikke den testede topp-20 %-rangeringen;
# faste grenser gir t 2,8 i 2016–26 og består ikke. Av til rangeringen er bygget og testet.
PEAD_TT_ENABLED = False
# Eksperimentell visning av rullerende topp/topp (⚗-linje, teller aldri mot Kjøp eller Signal-boka). Av til AnalBot har sjekket
# live-terskler (logs/pead_tt_thresholds.csv) mot testen.
PEAD_TT_EXPERIMENTAL = False
PEAD_TT_EXP_LINE = "⚗ Sterk rapport + reaksjon · snitt ca. +2 % vs S&P 500 over 60 d (median ca. +1 %)"
PEAD_TT_EXP_NOTE = "Bestod testen med minst mulig margin."
# PEAD topp/topp (topp 20 % på både EPS-overraskelse og kursreaksjon): AnalBots tall, reports/natt/pead_spread.md + pead_stretch.md
PEAD_TT_BADGE = "⚑ Sterk rapport + reaksjon · snitt +2,4 % vs S&P 500 over 60 d (median ca. +1 %)"
PEAD_TT_CAVEAT = "Bygger på ett signal. Testet på dagens S&P 500-medlemmer 2006–26, så snittet kan være for høyt."
