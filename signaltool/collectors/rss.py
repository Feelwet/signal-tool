"""Major-outlet news RSS feeds (free, no key). Headlines are stored so a baseline builds up."""
from __future__ import annotations
import calendar, logging
from datetime import datetime, timezone
import feedparser
import pandas as pd
from .. import http
from ..config import HISTORY
from ..themes import match_themes

log = logging.getLogger(__name__)
FEEDS = {
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "Guardian World": "https://www.theguardian.com/world/rss",
    "CNBC World": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
    "FT World": "https://www.ft.com/world?format=rss",
    "NYT World": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "NPR World": "https://feeds.npr.org/1004/rss.xml",
    "DW": "https://rss.dw.com/rdf/rss-en-all",
    "France24": "https://www.france24.com/en/rss",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Defense News": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
    "Breaking Defense": "https://breakingdefense.com/feed/",
    "gCaptain (shipping)": "https://gcaptain.com/feed/",
    "OilPrice": "https://oilprice.com/rss/main",
    "E24 (NO)": "https://e24.no/rss2/",
    "DN (NO)": "https://services.dn.no/api/feed/rss/",
    "Google News: geopolitics": "https://news.google.com/rss/search?q=geopolitics+when:2d&hl=en-US&gl=US&ceid=US:en",
    "Google News: sanctions": "https://news.google.com/rss/search?q=sanctions+when:2d&hl=en-US&gl=US&ceid=US:en",
    "Google News: tariffs": "https://news.google.com/rss/search?q=tariffs+when:2d&hl=en-US&gl=US&ceid=US:en",
}
STORE = HISTORY / "headlines.csv"
RUNS = HISTORY / "rss_run_days.txt"
KEEP_DAYS = 180


def collection_days() -> int:
    """Number of distinct days the RSS collector has run (baseline quality)."""
    return len(set(RUNS.read_text().split())) if RUNS.exists() else 0


def _ts(entry) -> pd.Timestamp | None:
    for k in ("published_parsed", "updated_parsed"):
        v = entry.get(k)
        if v:
            return pd.Timestamp(datetime.fromtimestamp(calendar.timegm(v), tz=timezone.utc))
    return None


def collect() -> tuple[pd.DataFrame, dict]:
    rows, status = [], {}
    for name, url in FEEDS.items():
        try:
            r = http.get(url, timeout=25, retries=2)
            f = feedparser.parse(r.content)
            status[name] = f"ok ({len(f.entries)} items)"
            for e in f.entries:
                title = e.get("title", "")
                summ = e.get("summary", "")[:400]
                rows.append({"source": name, "title": title, "link": e.get("link", ""),
                             "published": _ts(e), "themes": "|".join(match_themes(title + " " + summ))})
        except Exception as ex:
            status[name] = f"FAILED: {ex}"
    df = pd.DataFrame(rows)
    if not df.empty:
        df["published"] = pd.to_datetime(df["published"], utc=True)
        if STORE.exists():
            old = pd.read_csv(STORE, parse_dates=["published"])
            old["published"] = pd.to_datetime(old["published"], utc=True, format="mixed")
            df = pd.concat([old, df]).drop_duplicates("link", keep="first")
        # keep the stored history bounded (it is carried between CI runs in a cache)
        df = df[df["published"].isna() | (df["published"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=KEEP_DAYS))]
        df.to_csv(STORE, index=False)
        with RUNS.open("a") as f:
            f.write(datetime.now().strftime("%Y-%m-%d") + "\n")
    return df, status


def theme_daily_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Daily count of headlines per theme (UTC days)."""
    if df.empty:
        return pd.DataFrame()
    d = df.dropna(subset=["published"]).copy()
    d["themes"] = d["themes"].fillna("").astype(str)
    d["day"] = d["published"].dt.tz_convert("UTC").dt.floor("D").dt.tz_localize(None)
    d = d.assign(theme=d["themes"].str.split("|")).explode("theme")
    d = d[d["theme"] != ""]
    return d.groupby(["day", "theme"]).size().unstack(fill_value=0)
