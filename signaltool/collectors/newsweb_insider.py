"""Oslo Børs managers' transactions (Newsweb category 1102 'MELDEPLIKTIG HANDEL FOR PRIMÆRINNSIDERE'):
fetch the message body (public JSON, no key) and classify direction: kjøp / salg / tegning / annet / ukjent,
plus shares, price and NOK value when the text states them. Titles alone rarely say buy or sell.

Classification is rule-based (regex on English + Norwegian phrasing); 'annet' = options, RSU/LTIP, share lending,
share-savings programmes, exercise, pledges, allocations - i.e. not a discretionary open-market decision.
"""
from __future__ import annotations
import json, re
from datetime import date, timedelta
import pandas as pd
from .. import http
from ..config import CACHE

LIST_API = "https://api3.oslo.oslobors.no/v1/newsreader/list"
MSG_API = "https://api3.oslo.oslobors.no/v1/newsreader/message"
MSG_URL = "https://newsweb.oslobors.no/message/{}"
BODY_DIR = CACHE / "newsweb_msg"
BODY_DIR.mkdir(parents=True, exist_ok=True)
CATEGORY = "1102"

OTHER = re.compile(r"\b(option|opsjon|rsu|restricted stock|psu|performance share|ltip|incentive|share lending|aksjelån|lån av aksjer|"
                   r"securities lending|borrow|savings? (plan|programme|program)|spareprogram|aksjespare|exercise|utøv|pledge|pant|"
                   r"allocat|allok|tildel|lønnssubstitutt|buy-?back|tilbakekjøp|remuneration|godtgjørelse|vest(ing|ed)|transfer of shares|overføring|bonus shares|share award|matching shares|gift|gave|inheritance|arv|conversion|konverter)", re.I)
SELL = re.compile(r"\b(sold|sells|has sold|sale of|disposed|disposal|solgt|selger|salg av|avhendet)\b", re.I)
BUY = re.compile(r"\b(bought|buys|purchased|purchases|has acquired|acquired|acquisition of|kjøpt|kjøper|kjøp av|ervervet)\b", re.I)
SUBS = re.compile(r"\b(subscribed|subscription|tegnet|tegning|private placement|rettet emisjon|offering)\b", re.I)
NUM = r"(\d{1,3}(?:[ ,.\u00a0]\d{3})+|\d+)(?:[.,](\d+))?"
SHARES = re.compile(NUM + r"\s*(?:ordinary\s+)?(?:shares|aksjer)", re.I)
PNUM = r"(\d+)(?:[.,](\d+))?"  # share prices: '13.986' / '0,498' are decimals, not thousands
PRICE = re.compile(r"(?:price|kurs|pris)[^0-9]{0,40}?(?:(?:NOK|kr\.?)\s*)?" + PNUM + r"|(?:NOK|kr\.?)\s*" + PNUM + r"\s*(?:per|pr\.?)\s*(?:share|aksje)", re.I)


def _num(g_int, g_dec):
    s = re.sub(r"[ ,.\u00a0]", "", g_int)
    try:
        return float(s + ("." + g_dec if g_dec else ""))
    except ValueError:
        return None


def classify(text: str) -> dict:
    t = " ".join((text or "").split())
    head = t[:1200]
    other, sell, buy, subs = bool(OTHER.search(head)), bool(SELL.search(head)), bool(BUY.search(head)), bool(SUBS.search(head))
    if sell and not buy:
        kind = "salg"
    elif buy and not sell and not other:
        kind = "tegning" if subs else "kjøp"
    elif subs and not sell and not other:
        kind = "tegning"
    elif other:
        kind = "annet"
    elif buy and sell and not other:
        kind = "salg" if SELL.search(head).start() < BUY.search(head).start() else ("tegning" if subs else "kjøp")
    else:
        kind = "ukjent"
    sh = SHARES.search(head)
    shares = _num(sh.group(1), None) if sh else None
    pm = PRICE.search(head)
    price = None
    if pm:
        g = [x for x in pm.groups()]
        price = _num(g[0], g[1]) if g[0] else _num(g[2], g[3])
    value = shares * price if shares and price and price < 100000 else None
    if value is not None and value > 2e9:  # implausible -> parse error
        value = None
    return {"kind": kind, "shares": shares, "price_nok": price, "value_nok": value}


def list_messages(start: date, end: date, cache_hours=24 * 30) -> pd.DataFrame:
    rows, s = [], start
    while s <= end:
        e = min(s + timedelta(days=14), end)
        j = http.get_json(LIST_API, params={"category": CATEGORY, "issuer": "", "fromDate": s.isoformat(), "toDate": e.isoformat(),
                                            "market": "", "messageTitle": ""},
                          cache_hours=(1 if e >= date.today() - timedelta(days=2) else cache_hours))
        for m in j["data"]["messages"]:
            rows.append({"id": m["messageId"], "published": m["publishedTime"], "issuer": m.get("issuerSign"),
                         "issuer_name": m.get("issuerName"), "title": m.get("title")})
        s = e + timedelta(days=1)
    df = pd.DataFrame(rows).drop_duplicates("id") if rows else pd.DataFrame(columns=["id", "published", "issuer", "issuer_name", "title"])
    if len(df):
        df["published"] = pd.to_datetime(df["published"], utc=True)
    return df


def body(mid: int) -> str | None:
    p = BODY_DIR / f"{mid}.json"
    if p.exists():
        return json.loads(p.read_text()).get("body", "")
    try:
        j = http.get_json(MSG_API, params={"messageId": mid}, timeout=30, retries=2)
    except Exception:
        return None
    b = (j.get("data", {}).get("message", {}) or {}).get("body", "") or ""
    p.write_text(json.dumps({"body": b}))
    return b


def enrich(df: pd.DataFrame, max_fetch=400) -> pd.DataFrame:
    """Classify each message (title + body). Fetches at most `max_fetch` uncached bodies per call."""
    out, fetched = [], 0
    for r in df.sort_values("published", ascending=False).itertuples():
        cached = (BODY_DIR / f"{r.id}.json").exists()
        if not cached and fetched >= max_fetch:
            b = None
        else:
            b = body(r.id)
            fetched += 0 if cached else 1
        c = classify((r.title or "") + ". " + (b or "")) if b is not None else {"kind": "ikke hentet", "shares": None, "price_nok": None, "value_nok": None}
        out.append({**r._asdict(), **c, "url": MSG_URL.format(r.id)})
    return pd.DataFrame(out).drop(columns=["Index"], errors="ignore")


def collect(days=30) -> tuple[pd.DataFrame, str]:
    try:
        df = list_messages(date.today() - timedelta(days=days), date.today())
        if df.empty:
            return df, "ok (0 meldinger)"
        e = enrich(df)
    except Exception as ex:
        return pd.DataFrame(), f"FAILED: {ex}"
    k = e["kind"].value_counts().to_dict()
    return e, "ok (" + ", ".join(f"{n} {v}" for v, n in k.items()) + f" i {days} d)"
