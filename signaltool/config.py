"""Central configuration: paths, polite User-Agent, per-host rate limits."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("SIGNAL_DATA", ROOT / "data"))
CACHE = DATA / "cache"
HISTORY = DATA / "history"
REPORTS = ROOT / "reports"
for _p in (DATA, CACHE, HISTORY, REPORTS):
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
