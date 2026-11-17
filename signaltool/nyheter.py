"""Nyheter: automatisk oversiktsliste (kun overskrift, kilde, tid, lenke).

Aldri artikkeltekst, ingress, sammendrag eller AI-oppsummering. Ingen temanøkler,
rangering eller tickerlenker. Dedup i v1 er bare eksakt samme URL, eller samme
tittel fra samme kilde. Ingen sammenslåing på tvers av kilder.

Kjøres av .github/workflows/nyheter.yml hvert 10. minutt. Bruker signaltool.http
(per-vert-throttling). Tilstand og liste committes i logs/; siden bygges ikke her.
"""
from __future__ import annotations

import calendar, csv, json, logging
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from .config import LOGS, ROOT

log = logging.getLogger(__name__)
OSLO = ZoneInfo("Europe/Oslo")
FEEDS_PATH = ROOT / "config" / "nyheter_feeds.json"
STATE_PATH = LOGS / "nyheter_state.json"
OUT_PATH = LOGS / "nyheter.json"
LATENCY_PATH = LOGS / "nyheter_latency.csv"
SITE_PATH = ROOT / "site" / "data" / "nyheter.json"
RETENTION_H = 48
MAX_ITEMS = 300
DOWN_AFTER_H = 6
ITEM_KEYS = ("title", "url", "source", "source_id", "published_utc", "first_seen_utc", "section", "paywall")
LATENCY_FIELDS = ("first_seen_utc", "published_utc", "source", "url", "lag_sec")
SECTIONS = ("Alle", "Norge", "Marked", "Verden", "Tech", "Energi")


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(v) -> datetime | None:
    if v is None or v == "":
        return None
    if hasattr(v, "timetuple") and not isinstance(v, str):
        d = v.to_pydatetime() if hasattr(v, "to_pydatetime") else v
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    s = str(v)
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    from email.utils import parsedate_to_datetime
    try:
        d = parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _hhmm(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    return ts.astimezone(OSLO).strftime("%H:%M")


def load_config(path: Path | None = None) -> dict:
    path = path or FEEDS_PATH
    cfg = json.loads(path.read_text())
    cfg.setdefault("retention_hours", RETENTION_H)
    cfg.setdefault("max_items", MAX_ITEMS)
    cfg.setdefault("source_down_after_hours", DOWN_AFTER_H)
    return cfg


def enabled_feeds(cfg: dict) -> list[dict]:
    return [f for f in (cfg.get("feeds") or []) if f.get("enabled")]


def _norm_title(title: str) -> str:
    return " ".join(unescape(title or "").split())


def _norm_url(url: str) -> str:
    return (url or "").strip()


def _item(title, url, source, source_id, published, section, paywall, first_seen=None) -> dict:
    return {
        "title": _norm_title(title),
        "url": _norm_url(url),
        "source": source,
        "source_id": source_id,
        "published_utc": _iso(published) if isinstance(published, datetime) else published,
        "first_seen_utc": _iso(first_seen) if isinstance(first_seen, datetime) else first_seen,
        "section": section,
        "paywall": bool(paywall),
    }


def parse_feed(content: bytes, feed: dict) -> list[dict]:
    """Parse RSS/Atom. Only title, link and timestamp are kept."""
    import feedparser
    parsed = feedparser.parse(content)
    out = []
    for e in parsed.entries:
        ts = None
        for k in ("published_parsed", "updated_parsed"):
            if e.get(k):
                try:
                    ts = datetime.fromtimestamp(calendar.timegm(e[k]), tz=timezone.utc)
                    break
                except (OverflowError, ValueError, OSError):
                    pass
        if ts is None:
            ts = _parse_ts(e.get("published") or e.get("updated"))
        title, url = e.get("title") or "", e.get("link") or ""
        if not title or not url:
            continue
        out.append(_item(title, url, feed["source"], feed["source_id"], ts, feed["section"], feed.get("paywall", False)))
    return out


def fetch_rss(feed: dict, get) -> list[dict]:
    r = get(feed["url"], timeout=25, retries=2)
    return parse_feed(r.content, feed)


def fetch_newsweb(feed: dict, get, now: datetime, days: int = 2) -> list[dict]:
    """Oslo Børs Newsweb: offentlig JSON-API (ikke RSS). Bare tittel, lenke, tid."""
    end = now.astimezone(timezone.utc).date()
    start = end.fromordinal(end.toordinal() - max(1, days))
    r = get(feed["url"], params={
        "category": "", "issuer": "", "fromDate": start.isoformat(),
        "toDate": end.isoformat(), "market": "", "messageTitle": "",
    }, timeout=30, retries=2)
    data = r.json() if hasattr(r, "json") else json.loads(r.content)
    msgs = (data.get("data") or {}).get("messages") or []
    msg_url = feed.get("item_url") or "https://newsweb.oslobors.no/message/{}"
    out = []
    for m in msgs:
        title, mid = m.get("title") or "", m.get("messageId")
        if not title or mid is None:
            continue
        issuer = (m.get("issuerSign") or "").strip()
        if issuer and not title.lower().startswith(issuer.lower()):
            title = f"{issuer}: {title}"
        out.append(_item(title, msg_url.format(mid), feed["source"], feed["source_id"],
                         _parse_ts(m.get("publishedTime")), feed["section"], False))
    return out


def fetch_one(feed: dict, get, now: datetime) -> list[dict]:
    kind = feed.get("kind") or "rss"
    if kind == "newsweb_json":
        return fetch_newsweb(feed, get, now)
    return fetch_rss(feed, get)


def dedupe(items: list[dict]) -> list[dict]:
    """v1: drop exact same URL, or the same title from the same source. Cross-source kept."""
    seen_url, seen_ts, out = set(), set(), []
    for it in items:
        url, key = _norm_url(it.get("url") or ""), (it.get("source_id") or it.get("source"), _norm_title(it.get("title") or ""))
        if not url or not key[1] or url in seen_url or key in seen_ts:
            continue
        seen_url.add(url)
        seen_ts.add(key)
        out.append(it)
    return out


def merge_first_seen(items: list[dict], prev: list[dict], now: datetime) -> list[dict]:
    older = {_norm_url(it["url"]): it for it in prev if it.get("url")}
    now_s = _iso(now)
    out = []
    for it in items:
        old = older.get(_norm_url(it["url"]))
        seen = (old or {}).get("first_seen_utc") or it.get("first_seen_utc") or now_s
        it = {**it, "first_seen_utc": seen}
        out.append(it)
    return out


def prune(items: list[dict], now: datetime, retention_hours: int = RETENTION_H, max_items: int = MAX_ITEMS) -> list[dict]:
    cut = now - timedelta(hours=retention_hours)
    kept = []
    for it in items:
        ts = _parse_ts(it.get("published_utc"))
        if ts is None or ts >= cut:
            kept.append(it)
    kept.sort(key=lambda it: _parse_ts(it.get("published_utc")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return kept[:max_items]


def source_statuses(feeds: list[dict], results: dict, items: list[dict], now: datetime, down_after_hours: int = DOWN_AFTER_H, prior_ok: dict | None = None) -> list[dict]:
    """Per source: last updated hh:mm (Oslo). 'kilde nede' if no successful fetch in down_after_hours.

    A successful fetch within the window keeps the source listed as ok even if no new
    item arrived (slow sections like NYT Technology). last_new_item_utc is stored for AnalBot.
    """
    prev_ok = {k: _parse_ts(v) for k, v in (prior_ok or {}).items()}
    by_sid: dict[str, dict] = {}
    for f in feeds:
        sid = f["source_id"]
        row = by_sid.setdefault(sid, {
            "id": sid, "name": f["source"], "paywall": bool(f.get("paywall")),
            "feeds": [], "ok_at": [], "errors": [],
        })
        if prev_ok.get(sid):
            row["ok_at"].append(prev_ok[sid])
        # paywall if any feed of the source is paywalled
        row["paywall"] = row["paywall"] or bool(f.get("paywall"))
        rec = results.get(f["id"], {})
        row["feeds"].append(f["id"])
        if rec.get("ok"):
            at = rec.get("at") or now
            row["ok_at"].append(at if isinstance(at, datetime) else _parse_ts(at))
        if rec.get("error"):
            row["errors"].append(f"{f['id']}: {rec['error']}")
    # drop None stamps
    for row in by_sid.values():
        row["ok_at"] = [t for t in row["ok_at"] if t is not None]
    newest_item: dict[str, datetime] = {}
    for it in items:
        ts = _parse_ts(it.get("first_seen_utc")) or _parse_ts(it.get("published_utc"))
        sid = it.get("source_id")
        if sid and ts and (sid not in newest_item or ts > newest_item[sid]):
            newest_item[sid] = ts
    out = []
    limit = now - timedelta(hours=down_after_hours)
    for sid, row in by_sid.items():
        last_ok = max(row["ok_at"]) if row["ok_at"] else None
        last_new = newest_item.get(sid)
        down = last_ok is None or last_ok < limit
        status = "kilde nede" if down else "ok"
        out.append({
            "id": sid,
            "name": row["name"],
            "paywall": row["paywall"],
            "last_updated": _hhmm(last_ok),
            "last_updated_utc": _iso(last_ok) if last_ok else None,
            "last_new_item_utc": _iso(last_new) if last_new else None,
            "status": status,
            "error": "; ".join(row["errors"]) if row["errors"] else None,
        })
    out.sort(key=lambda r: r["name"].lower())
    return out


def load_state(path: Path | None = None) -> dict:
    path = path or STATE_PATH
    try:
        s = json.loads(path.read_text())
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def save_state(state: dict, path: Path | None = None) -> None:
    path = path or STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def write_output(data: dict, path: Path | None = None, site_path: Path | None = None) -> None:
    path = path or OUT_PATH
    if site_path is None:
        site_path = SITE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text)
    if site_path is not None:
        site_path.parent.mkdir(parents=True, exist_ok=True)
        site_path.write_text(text)


def append_latency(items: list[dict], prev_urls: set[str], path: Path | None = None) -> int:
    """Append-only latency log for items first seen in this run. AnalBot: median lag vs published."""
    path = path or LATENCY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    new = [it for it in items if _norm_url(it.get("url") or "") not in prev_urls and it.get("first_seen_utc") and it.get("published_utc")]
    if not new and path.exists():
        return 0
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LATENCY_FIELDS)
        if write_header:
            w.writeheader()
        for it in new:
            seen, pub = _parse_ts(it["first_seen_utc"]), _parse_ts(it["published_utc"])
            lag = None
            if seen and pub:
                lag = int((seen - pub).total_seconds())
            w.writerow({
                "first_seen_utc": it["first_seen_utc"],
                "published_utc": it["published_utc"],
                "source": it.get("source") or "",
                "url": it["url"],
                "lag_sec": lag if lag is not None else "",
            })
    return len(new)


def _http_get():
    from . import http
    return http.get


def collect(cfg: dict | None = None, now: datetime | None = None, get=None, state: dict | None = None,
            write: bool = False) -> tuple[dict, dict]:
    cfg = cfg or load_config()
    now = now or datetime.now(timezone.utc)
    get = get or _http_get()
    state = dict(state) if state is not None else load_state()
    feeds = enabled_feeds(cfg)
    prev_items = list(state.get("items") or [])
    prev_urls = {_norm_url(it.get("url") or "") for it in prev_items}
    got, results = [], {}
    for f in feeds:
        try:
            rows = fetch_one(f, get, now)
            results[f["id"]] = {"ok": True, "at": now, "n": len(rows)}
            got.extend(rows)
        except Exception as ex:
            log.warning("nyheter: %s feilet: %s", f.get("id"), ex)
            results[f["id"]] = {"ok": False, "at": now, "error": f"{type(ex).__name__}: {ex}"[:200], "n": 0}
    items = dedupe(got + prev_items)
    items = merge_first_seen(items, prev_items, now)
    items = prune(items, now, cfg.get("retention_hours", RETENTION_H), cfg.get("max_items", MAX_ITEMS))
    # drop any leftover non-schema fields (never persist summaries/bodies)
    items = [{k: it.get(k) for k in ITEM_KEYS} for it in items]
    # carry last successful fetch per source so a one-off failure is not 'kilde nede'
    prior_ok = dict(state.get("source_ok_at") or {})
    sources = source_statuses(feeds, results, items, now, cfg.get("source_down_after_hours", DOWN_AFTER_H), prior_ok)
    source_ok_at = {s["id"]: s["last_updated_utc"] for s in sources if s.get("last_updated_utc")}
    data = {
        "generated_at_utc": _iso(now),
        "generated_at_oslo": now.astimezone(OSLO).strftime("%Y-%m-%d %H:%M %Z"),
        "retention_hours": cfg.get("retention_hours", RETENTION_H),
        "max_items": cfg.get("max_items", MAX_ITEMS),
        "n": len(items),
        "items": items,
        "sources": sources,
    }
    new_state = {"items": items, "source_ok_at": source_ok_at, "results": {
        fid: {**rec, "at": _iso(rec["at"]) if isinstance(rec.get("at"), datetime) else rec.get("at")}
        for fid, rec in results.items()
    }}
    if write:
        n_new = append_latency(items, prev_urls)
        write_output(data)
        save_state(new_state)
        log.info("nyheter: %s saker, %s nye i latency-loggen", len(items), n_new)
    return data, new_state


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    collect(write=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
