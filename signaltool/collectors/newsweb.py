"""Oslo Børs Newsweb announcements via the public JSON API behind newsweb.oslobors.no (no key).
The list endpoint caps results (~600), so we query in 5-day windows. Rate: 1 req/s."""
from __future__ import annotations
import re
from datetime import date, timedelta
import pandas as pd
from .. import http

API = "https://api3.oslo.oslobors.no/v1/newsreader/list"
MSG_URL = "https://newsweb.oslobors.no/message/{}"
# same exclusions as the contract backtest (signaltool/backtest/oslo_events.py): share awards, legal disputes, calendars ...
NOT_CONTRACT = re.compile(r"share related|share award|aksje|option|opsjon|incentive|legal|proceeding|terminat|cancel|dispute|arbitrat|lawsuit|søksmål|"
                          r"financial calendar|presentation|webcast|invitation|buy-?back", re.I)
CONTRACT_WORDS = ["contract", "kontrakt", "order", "award", "framework agreement", "rammeavtale", "letter of intent"]


def collect(days=60) -> tuple[pd.DataFrame, str]:
    rows, end = [], date.today()
    try:
        s = end - timedelta(days=days)
        while s <= end:
            e = min(s + timedelta(days=4), end)
            j = http.get_json(API, params={"category": "", "issuer": "", "fromDate": s.isoformat(), "toDate": e.isoformat(),
                                           "market": "", "messageTitle": ""}, cache_hours=(0.5 if e >= end - timedelta(days=2) else 48))
            for m in j["data"]["messages"]:
                rows.append({"id": m["messageId"], "published": m["publishedTime"], "issuer": m.get("issuerSign"),
                             "issuer_name": m.get("issuerName"), "title": m.get("title"),
                             "category": (m.get("category") or [{}])[0].get("category_en", ""),
                             "url": MSG_URL.format(m["messageId"])})
            s = e + timedelta(days=1)
    except Exception as ex:
        if not rows:
            return pd.DataFrame(), f"FAILED: {ex}"
    df = pd.DataFrame(rows).drop_duplicates("id")
    df["published"] = pd.to_datetime(df["published"], utc=True)
    df["insider_trade"] = df["category"].str.contains("MANAGERS", case=False)
    t = df["title"].str.lower()
    df["contract"] = t.apply(lambda x: any(w in x for w in CONTRACT_WORDS) and not NOT_CONTRACT.search(x))
    return df, f"ok ({len(df)} announcements in {days}d)"
