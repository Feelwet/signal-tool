"""US Department of Defense (now 'Department of War', war.gov) daily contract announcements (>= $7.5M).
The RSS index works from this box; the article pages return HTTP 403 (Akamai) from this box, so the
full text is parsed only when accessible (it normally is from residential connections)."""
from __future__ import annotations
import html, re
import feedparser
import pandas as pd
from .. import http
from ..themes import NAME_TO_TICKER

RSS = "https://www.war.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=945&max=15"
AMT = re.compile(r"\$([\d,]{7,})")


def parse_article(text: str) -> list[dict]:
    plain = html.unescape(re.sub(r"<[^>]+>", "\n", text))
    out = []
    for para in re.split(r"\n\s*\n", plain):
        p = " ".join(para.split())
        m = AMT.search(p)
        if not m or "awarded" not in p and "has been" not in p:
            continue
        up = p.upper()
        tick = next((v for k, v in NAME_TO_TICKER.items() if v and k in up), None)
        out.append({"company": p.split(",")[0][:80], "amount": float(m.group(1).replace(",", "")), "ticker": tick, "text": p[:300]})
    return out


def collect(parse_days=3) -> tuple[pd.DataFrame, list[dict], str]:
    try:
        r = http.get(RSS, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) signal-tool personal research"})
        f = feedparser.parse(r.content)
    except Exception as e:
        return pd.DataFrame(), [], f"FAILED: {e}"
    days = [{"title": e.get("title"), "link": e.get("link"), "published": e.get("published")} for e in f.entries]
    rows, blocked = [], 0
    for d in days[:parse_days]:
        try:
            a = http.get(d["link"], retries=1, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) signal-tool personal research"})
            for x in parse_article(a.text):
                rows.append({**x, "day": d["title"], "url": d["link"]})
        except Exception:
            blocked += 1
    msg = f"ok ({len(days)} daily announcements listed"
    msg += f"; article text blocked (403) for {blocked}/{min(parse_days, len(days))} – links only)" if blocked else f"; {len(rows)} awards parsed)"
    return pd.DataFrame(rows), days, msg
