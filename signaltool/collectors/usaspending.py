"""USAspending.gov award search (free, no key). NOTE: DoD contract data is published with a
~90-day delay, so defence awards show up late; DoD's daily contract announcements
(defense.gov/News/Contracts) are the timelier source but are HTML-only (not automated here).
SAM.gov opportunities API requires a free API key (sign-up) -> not used."""
from __future__ import annotations
from datetime import date, timedelta
import pandas as pd
from .. import http
from ..themes import NAME_TO_TICKER

API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


def _ticker(name: str):
    n = (name or "").upper()
    for k, v in NAME_TO_TICKER.items():
        if k in n:
            return v
    return None


def collect(days=21, min_amount=25_000_000) -> tuple[pd.DataFrame, str]:
    body = {"filters": {"award_type_codes": ["A", "B", "C", "D"],
                        "time_period": [{"start_date": (date.today() - timedelta(days=days)).isoformat(),
                                         "end_date": date.today().isoformat(), "date_type": "new_awards_only"}],
                        "award_amounts": [{"lower_bound": min_amount}]},
            "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Start Date", "Description",
                       "generated_internal_id"],
            "sort": "Award Amount", "order": "desc", "limit": 100, "page": 1}
    try:
        j = http.get_json(API, method="POST", json_body=body, timeout=90)
    except Exception as e:
        return pd.DataFrame(), f"FAILED: {e}"
    df = pd.DataFrame(j.get("results", []))
    if df.empty:
        return df, "ok (0 awards)"
    df["ticker"] = df["Recipient Name"].map(_ticker)
    df["url"] = "https://www.usaspending.gov/award/" + df["generated_internal_id"].astype(str)
    return df, f"ok ({len(df)} new awards >= ${min_amount/1e6:.0f}M in {days}d)"
