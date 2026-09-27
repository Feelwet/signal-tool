"""Norges Bank open data (SDMX API, no key) for NOK FX, plus press-release RSS."""
from __future__ import annotations
import feedparser
import pandas as pd
from .. import http

FX = "https://data.norges-bank.no/api/data/EXR/B.USD+EUR.NOK.SP"
RSS = "https://www.norges-bank.no/en/rss-feeds/Press-releases---Norges-Bank/"


def fx(last_n=90) -> pd.DataFrame:
    j = http.get_json(FX, params={"format": "sdmx-json", "lastNObservations": last_n, "locale": "en"})
    ds = j["data"]["dataSets"][0]["series"]
    dims = j["data"]["structure"]["dimensions"]
    times = [v["id"] for v in dims["observation"][0]["values"]]
    cur = [v["id"] for v in dims["series"][1]["values"]]
    out = {}
    for key, s in ds.items():
        c = cur[int(key.split(":")[1])]
        out[f"{c}NOK"] = {pd.Timestamp(times[int(i)]): float(v[0]) for i, v in s["observations"].items()}
    return pd.DataFrame(out).sort_index()


def collect() -> tuple[dict, str]:
    res, msgs = {}, []
    try:
        res["fx"] = fx(); msgs.append("fx ok")
    except Exception as e:
        msgs.append(f"fx FAILED: {e}")
    try:
        f = feedparser.parse(http.get(RSS).content)
        res["press"] = [{"title": e.get("title"), "link": e.get("link"), "published": e.get("published")} for e in f.entries[:10]]
        msgs.append(f"press rss ok ({len(f.entries)})")
    except Exception as e:
        msgs.append(f"press FAILED: {e}")
    return res, "; ".join(msgs)
