"""Central-bank meeting calendars scraped from official public pages (no key):
Federal Reserve FOMC and ECB Governing Council. Norges Bank's meeting page renders dates
client-side, so Norges Bank dates are not automated (see backlog)."""
from __future__ import annotations
import re
from datetime import date, datetime
from .. import http

MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                        "September", "October", "November", "December"], 1)}


def fomc(html: str) -> list[dict]:
    out = []
    for block in re.split(r'<a id="\d+">', html)[1:]:
        ym = re.match(r"(\d{4}) FOMC Meetings", block)
        if not ym:
            continue
        year = int(ym[1])
        for mon, days in re.findall(r'fomc-meeting__month[^>]*><strong>([A-Za-z/]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<', block, re.S):
            mon = mon.split("/")[-1]
            last = re.findall(r"\d+", days)
            if mon in MONTHS and last:
                out.append({"date": date(year, MONTHS[mon], int(last[-1])).isoformat(), "time": "20:00",
                            "source": "Federal Reserve", "title": "FOMC rentebeslutning" + (" + prognoser (SEP)" if "*" in days else "")})
    return out


def ecb(html: str) -> list[dict]:
    out = []
    for d, txt in re.findall(r"<dt>\s*(\d{2}/\d{2}/\d{4})\s*</dt>\s*<dd>\s*([^<]+)", html):
        if "monetary policy meeting" in txt and "non-monetary" not in txt and ("Day 2" in txt or "Day" not in txt):
            out.append({"date": datetime.strptime(d, "%d/%m/%Y").date().isoformat(), "time": "14:15",
                        "source": "ECB", "title": "ECB rentebeslutning og pressekonferanse"})
    return out


def collect() -> tuple[list[dict], dict]:
    ev, st = [], {}
    try:
        f = fomc(http.get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", cache_hours=24).text)
        ev += f; st["Fed FOMC calendar"] = f"ok ({len(f)} meetings)"
    except Exception as e:
        st["Fed FOMC calendar"] = f"FAILED: {e}"
    try:
        e_ = ecb(http.get("https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html", cache_hours=24).text)
        ev += e_; st["ECB meeting calendar"] = f"ok ({len(e_)} meetings)"
    except Exception as e:
        st["ECB meeting calendar"] = f"FAILED: {e}"
    st["Norges Bank meeting calendar"] = "not automated (dates rendered client-side); press releases RSS used"
    today = date.today().isoformat()
    return sorted([e for e in ev if e["date"] >= today], key=lambda e: e["date"]), st
