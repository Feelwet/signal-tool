"""Reddit public RSS feeds (no key). The unauthenticated .json endpoints return 403 from this box
(Reddit now requires OAuth for API use), so we use the public .rss listings, which still work.
Rate: one request every 3 s."""
from __future__ import annotations
import calendar, re
from datetime import datetime, timezone
import feedparser
import pandas as pd
from .. import http
from ..config import HISTORY
from ..themes import match_themes

SUBS = ["worldnews", "geopolitics", "stocks", "wallstreetbets", "investing", "CredibleDefense", "aksjer"]
STORE = HISTORY / "reddit.csv"
CASHTAG = re.compile(r"\$([A-Z]{2,5})\b")


def collect() -> tuple[pd.DataFrame, str]:
    rows, fails = [], []
    for s in SUBS:
        for listing in ("hot",):
            if len(fails) >= 3:
                break
            try:
                r = http.get(f"https://www.reddit.com/r/{s}/{listing}.rss", params={"limit": 50}, retries=1)
                for e in feedparser.parse(r.content).entries:
                    ts = e.get("updated_parsed") or e.get("published_parsed")
                    title = e.get("title", "")
                    rows.append({"sub": s, "title": title, "link": e.get("link", ""),
                                 "published": datetime.fromtimestamp(calendar.timegm(ts), tz=timezone.utc) if ts else None,
                                 "themes": "|".join(match_themes(title)),
                                 "cashtags": "|".join(sorted(set(CASHTAG.findall(title))))})
            except Exception as ex:
                fails.append(f"{s}/{listing}: {ex}")
    df = pd.DataFrame(rows)
    if not df.empty:
        df["published"] = pd.to_datetime(df["published"], utc=True)
        if STORE.exists():
            old = pd.read_csv(STORE)
            old["published"] = pd.to_datetime(old["published"], utc=True, format="mixed")
            df = pd.concat([old, df]).drop_duplicates("link", keep="first")
        df.to_csv(STORE, index=False)
    status = f"ok ({len(rows)} posts from {len(SUBS)} subs)" if rows else "FAILED"
    if fails:
        status += f"; {len(fails)} feed errors"
    return df, status
