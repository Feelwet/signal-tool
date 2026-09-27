"""GDELT 1.0 daily event exports (free static files, no key, no rate-limited API).

http://data.gdeltproject.org/events/YYYYMMDD.export.CSV.zip  (~4 MB/day, ~70k events)
We reduce each day to a small aggregate table (country x CAMEO root code) plus counts of
theme keywords in source URLs, and cache it, so the raw files never need re-downloading.
"""
from __future__ import annotations
import io, logging, zipfile
from datetime import date, timedelta
import pandas as pd
from .. import http
from ..config import CACHE
from ..themes import THEMES

log = logging.getLogger(__name__)
AGG_DIR = CACHE / "gdelt_daily"
AGG_DIR.mkdir(parents=True, exist_ok=True)
URL = "http://data.gdeltproject.org/events/{d}.export.CSV.zip"
# column indexes in the 57/58-col GDELT 1.0 export
COL = {"EventRootCode": 28, "QuadClass": 29, "Goldstein": 30, "NumArticles": 33, "AvgTone": 34,
       "ActionGeo_CountryCode": 51, "SOURCEURL": 57}
URL_KWS = sorted({k for th in THEMES for k in th.url_keywords})


def _agg_path(d: date):
    return AGG_DIR / f"{d:%Y%m%d}_agg.csv.gz"


def _kw_path(d: date):
    return AGG_DIR / f"{d:%Y%m%d}_kw.csv"


def fetch_day(d: date, force=False) -> bool:
    """Download + aggregate one day. Returns True if data available."""
    if _agg_path(d).exists() and _kw_path(d).exists() and not force:
        return True
    try:
        r = http.get(URL.format(d=f"{d:%Y%m%d}"), timeout=120, retries=2)
    except Exception as e:  # 404 for days not yet published
        log.info("gdelt %s unavailable: %s", d, e)
        return False
    z = zipfile.ZipFile(io.BytesIO(r.content))
    with z.open(z.namelist()[0]) as f:
        df = pd.read_csv(f, sep="\t", header=None, usecols=list(COL.values()), dtype=str,
                         on_bad_lines="skip", quoting=3)
    df.columns = list(COL.keys())
    df["NumArticles"] = pd.to_numeric(df["NumArticles"], errors="coerce").fillna(1)
    df["AvgTone"] = pd.to_numeric(df["AvgTone"], errors="coerce").fillna(0)
    df["Goldstein"] = pd.to_numeric(df["Goldstein"], errors="coerce").fillna(0)
    df["tone_w"] = df["AvgTone"] * df["NumArticles"]
    df["ActionGeo_CountryCode"] = df["ActionGeo_CountryCode"].fillna("")
    agg = (df.groupby(["ActionGeo_CountryCode", "EventRootCode"], dropna=False)
             .agg(events=("NumArticles", "size"), articles=("NumArticles", "sum"),
                  tone_w=("tone_w", "sum"), goldstein=("Goldstein", "mean")).reset_index())
    agg.to_csv(_agg_path(d), index=False)
    urls = df["SOURCEURL"].dropna().drop_duplicates().str.lower()
    kw = {k: int(urls.str.contains(k, regex=False).sum()) for k in URL_KWS}
    kw["_total_urls"] = int(len(urls))
    pd.Series(kw).to_csv(_kw_path(d), header=["count"])
    return True


def backfill(start: date, end: date) -> int:
    n = 0
    d = start
    while d <= end:
        if fetch_day(d):
            n += 1
        d += timedelta(days=1)
    return n


def load_theme_series(start: date, end: date) -> pd.DataFrame:
    """Daily per-theme metrics from cached aggregates.

    Columns per theme: {key}_share (theme article share of all articles, in %),
    {key}_tone (article-weighted avg tone of theme events), {key}_url (share of source URLs with theme keywords, %).
    """
    rows = []
    d = start
    while d <= end:
        p, pk = _agg_path(d), _kw_path(d)
        if p.exists() and pk.exists():
            a = pd.read_csv(p, dtype={"ActionGeo_CountryCode": str, "EventRootCode": str}, keep_default_na=False)
            kw = pd.read_csv(pk, index_col=0)["count"]
            tot_art = a["articles"].sum()
            row = {"date": pd.Timestamp(d), "total_articles": tot_art}
            for th in THEMES:
                m = a["EventRootCode"].isin(th.gdelt_roots)
                if th.gdelt_countries:
                    m &= a["ActionGeo_CountryCode"].isin(th.gdelt_countries)
                sub = a[m]
                art = sub["articles"].sum()
                row[f"{th.key}_share"] = 100 * art / tot_art if tot_art else 0
                row[f"{th.key}_tone"] = sub["tone_w"].sum() / art if art else 0
                tot_u = kw.get("_total_urls", 0) or 1
                # a URL can match several keywords; this is an upper-bound share, fine for z-scores
                row[f"{th.key}_url"] = 100 * sum(kw.get(k, 0) for k in th.url_keywords) / tot_u
            rows.append(row)
        d += timedelta(days=1)
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def latest_available(max_back=4) -> date | None:
    d = date.today()
    for i in range(max_back + 1):
        dd = d - timedelta(days=i)
        if fetch_day(dd):
            return dd
    return None
