"""Faster policy alerts (free, no key):
  * US Federal Register API: BIS (export controls, Entity List), ITA (anti-dumping / countervailing duties),
    OFAC (sanctions regulations), USTR (Section 301 tariffs). Published daily 06:00 ET (~12:00 Oslo); documents are
    often on public inspection the day before.
  * EU: Council press releases RSS + EUR-Lex (Official Journal) feed, filtered on sanctions / restrictive measures.
Each item is tagged with a type and matched to our themes by keywords.
"""
from __future__ import annotations
import re
from datetime import date, timedelta
import feedparser
from .. import http
from ..themes import match_themes

FR = "https://www.federalregister.gov/api/v1/documents.json"
AGENCIES = {"industry-and-security-bureau": "Eksportkontroll (BIS)", "international-trade-administration": "Antidumping/toll (ITA)",
            "foreign-assets-control-office": "Sanksjoner (OFAC)", "trade-representative-office-of-united-states": "Toll (USTR)"}
EU_FEEDS = {"EU-rådet": "https://www.consilium.europa.eu/en/rss/pressreleases.ashx",
            "EUR-Lex (EU-tidende)": "https://eur-lex.europa.eu/EN/display-feed.rss?rssId=162"}
EU_RX = re.compile(r"sanction|restrictive measures|mesures restrictives|\(CFSP\)|\(PESC\)|export control|anti-dumping|countervailing", re.I)
HOT = re.compile(r"entity list|export control|semiconductor|advanced computing|rare earth|critical mineral|gallium|germanium|antimony|"
                 r"russia|iran|china|venezuela|oil|shipping|vessel|tanker|section 301|tariff|anti-dumping|countervailing", re.I)


def collect(days=10) -> tuple[list[dict], str]:
    out, errs = [], []
    since = (date.today() - timedelta(days=days)).isoformat()
    for slug, lab in AGENCIES.items():
        try:
            j = http.get_json(FR, params={"conditions[agencies][]": slug, "conditions[publication_date][gte]": since, "per_page": 100,
                                          "order": "newest", "fields[]": ["title", "type", "publication_date", "html_url", "abstract"]},
                              cache_hours=2, timeout=40)
            for r in j.get("results", []):
                txt = f"{r.get('title', '')} {r.get('abstract') or ''}"
                if r.get("type") == "Notice" and slug == "international-trade-administration" and not HOT.search(txt):
                    continue  # ITA publishes hundreds of routine notices; keep the relevant ones
                th = match_themes(txt)
                hot = bool(HOT.search(txt)) and (slug != "international-trade-administration" or bool(th))
                out.append({"date": r["publication_date"], "source": "Federal Register", "kind": lab, "doc_type": r.get("type"),
                            "title": r["title"], "url": r["html_url"], "themes": th, "hot": hot})
        except Exception as e:
            errs.append(f"{lab}: {e}")
    for lab, url in EU_FEEDS.items():
        try:
            f = feedparser.parse(http.get(url, timeout=30, cache_hours=2).content)
            for e in f.entries:
                t = e.get("title", "")
                if not EU_RX.search(t + " " + e.get("summary", "")[:300]) or re.search(r"rectificati|corrigendum", t, re.I):
                    continue
                d = e.get("published_parsed") or e.get("updated_parsed")
                ds = date(*d[:3]).isoformat() if d else ""
                if ds and ds < since:
                    continue
                out.append({"date": ds, "source": lab, "kind": "Sanksjoner (EU)", "doc_type": "", "title": t[:300], "url": e.get("link", ""),
                            "themes": match_themes(t), "hot": True})
        except Exception as e:
            errs.append(f"{lab}: {e}")
    out.sort(key=lambda x: x["date"], reverse=True)
    msg = f"ok ({len(out)} dokumenter siste {days} d)" + (f"; feil: {errs}" if errs else "")
    return out, msg if out or not errs else "FAILED: " + "; ".join(errs)
