"""Google Trends via pytrends (unofficial, free, no key; heavily rate limited -> slow + optional)."""
from __future__ import annotations
import logging, time
import pandas as pd

log = logging.getLogger(__name__)


def collect(term_sets: dict[str, list[str]], pause=8.0) -> tuple[dict[str, pd.DataFrame], str]:
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return {}, "FAILED: pytrends not installed"
    p = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
    out, fails = {}, 0
    for k, terms in term_sets.items():
        if not terms:
            continue
        try:
            p.build_payload(terms[:5], timeframe="today 3-m")
            df = p.interest_over_time()
            if not df.empty:
                out[k] = df.drop(columns=[c for c in ["isPartial"] if c in df.columns])
        except Exception as e:
            fails += 1
            log.info("trends %s failed: %s", k, e)
            if fails >= 2:
                return out, f"partial ({len(out)} themes) - rate limited: {e}"
        time.sleep(pause)
    return out, f"ok ({len(out)} themes)"
