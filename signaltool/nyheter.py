"""Nyheter: automatisk oversiktsliste (kun overskrift, kilde, tid, lenke).

Aldri artikkeltekst, ingress, sammendrag eller AI-oppsummering. Ingen temanøkler,
rangering eller tickerlenker. Dedup i v1 er bare eksakt samme URL, eller samme
tittel fra samme kilde (Newsweb: tittel+kilde+utsteder). Ingen sammenslåing på tvers av kilder.

To puljer: redaksjonelt maks 300 / 48 t, Newsweb maks 150 / 48 t. Newsweb vises bare
i fanen Børsmeldinger, ikke i Alt eller Norge.

Kjøres av .github/workflows/nyheter.yml hvert 10. minutt. Bruker signaltool.http
(per-vert-throttling). Tilstand og liste committes i logs/; siden henter JSON ved lasting.
"""
from __future__ import annotations

import calendar, csv, json, logging
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
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
MAX_EDITORIAL = 300
MAX_NEWSWEB = 150
DOWN_AFTER_H = 6
FUTURE_SLACK_MIN = 5
ITEM_KEYS = ("title", "url", "source", "source_id", "published_utc", "first_seen_utc", "section", "paywall", "issuer")
LATENCY_FIELDS = ("first_seen_utc", "published_utc", "source", "url", "lag_sec", "flag")
SECTIONS = ("Alt", "Norge", "Marked", "Verden", "Børsmeldinger")
POOL_EDIT, POOL_NEWSWEB = "editorial", "newsweb"


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
    cfg.setdefault("max_items_editorial", MAX_EDITORIAL)
    cfg.setdefault("max_items_newsweb", MAX_NEWSWEB)
    cfg.setdefault("source_down_after_hours", DOWN_AFTER_H)
    return cfg


def enabled_feeds(cfg: dict) -> list[dict]:
    return [f for f in (cfg.get("feeds") or []) if f.get("enabled")]


def _norm_title(title: str) -> str:
    return " ".join(unescape(title or "").split())


def _norm_url(url: str) -> str:
    return (url or "").strip()


def is_newsweb(it: dict) -> bool:
    return (it.get("source_id") == "newsweb") or (it.get("section") == "Børsmeldinger") or (it.get("pool") == POOL_NEWSWEB)


def _item(title, url, source, source_id, published, section, paywall, first_seen=None, issuer=None) -> dict:
    return {
        "title": _norm_title(title),
        "url": _norm_url(url),
        "source": source,
        "source_id": source_id,
        "published_utc": _iso(published) if isinstance(published, datetime) else published,
        "first_seen_utc": _iso(first_seen) if isinstance(first_seen, datetime) else first_seen,
        "section": section,
        "paywall": bool(paywall),
        "issuer": (issuer or "").strip() or None,
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
    """Oslo Børs Newsweb: offentlig JSON-API (ikke RSS). Bare tittel, lenke, tid og utsteder."""
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
        out.append(_item(title, msg_url.format(mid), feed["source"], feed["source_id"],
                         _parse_ts(m.get("publishedTime")), "Børsmeldinger",
                         False, issuer=issuer or None))
    return out


def fetch_one(feed: dict, get, now: datetime) -> list[dict]:
    kind = feed.get("kind") or "rss"
    if kind == "newsweb_json":
        return fetch_newsweb(feed, get, now)
    return fetch_rss(feed, get)


def dedupe(items: list[dict]) -> list[dict]:
    """v1: drop exact same URL, or the same title from the same source. Cross-source kept.

    Newsweb uses title+source+issuer so two issuers with the same heading stay distinct.
    """
    seen_url, seen_ts, out = set(), set(), []
    for it in items:
        url = _norm_url(it.get("url") or "")
        sid = it.get("source_id") or it.get("source")
        title = _norm_title(it.get("title") or "")
        if is_newsweb(it):
            key = (sid, title, (it.get("issuer") or "").strip())
        else:
            key = (sid, title)
        if not url or not title or url in seen_url or key in seen_ts:
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
        if old and old.get("issuer") and not it.get("issuer"):
            it["issuer"] = old["issuer"]
        out.append(it)
    return out


def prune(items: list[dict], now: datetime, retention_hours: int = RETENTION_H, max_items: int = MAX_EDITORIAL) -> list[dict]:
    cut = now - timedelta(hours=retention_hours)
    kept = []
    for it in items:
        ts = _parse_ts(it.get("published_utc"))
        if ts is None or ts >= cut:
            kept.append(it)
    kept.sort(key=lambda it: _parse_ts(it.get("published_utc")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return kept[:max_items]



def in_tab(it: dict, tab: str) -> bool:
    """Newsweb / Børsmeldinger only in that tab — never in Alt or Norge."""
    if is_newsweb(it) or it.get("section") == "Børsmeldinger":
        return tab == "Børsmeldinger"
    if tab == "Alt":
        return True
    return it.get("section") == tab


def prune_pools(items: list[dict], now: datetime, retention_hours: int = RETENTION_H,
                max_editorial: int = MAX_EDITORIAL, max_newsweb: int = MAX_NEWSWEB) -> list[dict]:
    """Two independent 48h caps: editorial (max 300) and Newsweb (max 150). Combined list is time-sorted."""
    ed = prune([it for it in items if not is_newsweb(it)], now, retention_hours, max_editorial)
    nw = prune([it for it in items if is_newsweb(it)], now, retention_hours, max_newsweb)
    for it in ed:
        it["pool"] = POOL_EDIT
    for it in nw:
        it["pool"] = POOL_NEWSWEB
        it["section"] = "Børsmeldinger"
    out = ed + nw
    out.sort(key=lambda it: _parse_ts(it.get("published_utc")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return out


def source_statuses(feeds: list[dict], results: dict, items: list[dict], now: datetime, down_after_hours: int = DOWN_AFTER_H, prior_ok: dict | None = None) -> list[dict]:
    """Per source: last updated hh:mm (Oslo). 'kilde nede' if no successful fetch in down_after_hours.

    A successful fetch within the window keeps the source listed as ok even if no new item arrived.
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
        row["paywall"] = row["paywall"] or bool(f.get("paywall"))
        rec = results.get(f["id"], {})
        row["feeds"].append(f["id"])
        if rec.get("ok"):
            at = rec.get("at") or now
            row["ok_at"].append(at if isinstance(at, datetime) else _parse_ts(at))
        if rec.get("error"):
            row["errors"].append(f"{f['id']}: {rec['error']}")
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
        out.append({
            "id": sid,
            "name": row["name"],
            "paywall": row["paywall"],
            "last_updated": _hhmm(last_ok),
            "last_updated_utc": _iso(last_ok) if last_ok else None,
            "last_new_item_utc": _iso(last_new) if last_new else None,
            "status": "kilde nede" if down else "ok",
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


def _pub_flag(published, now: datetime) -> str:
    """pub_ugyldig if timestamp is missing or more than 5 minutes in the future."""
    pub = published if isinstance(published, datetime) else _parse_ts(published)
    if pub is None:
        return "pub_ugyldig"
    if pub - now > timedelta(minutes=FUTURE_SLACK_MIN):
        return "pub_ugyldig"
    return ""


def append_latency(items: list[dict], prev_urls: set[str], path: Path | None = None,
                   now: datetime | None = None) -> int:
    """Append-only latency log for items first seen in this run.

    Invalid published times (missing or >5 min in the future) are logged with flag
    pub_ugyldig and an empty lag_sec (never 0). Median calculation excludes those
    rows and anything published before first_run_utc.
    """
    path = path or LATENCY_PATH
    now = now or datetime.now(timezone.utc)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = [it for it in items if _norm_url(it.get("url") or "") not in prev_urls and it.get("first_seen_utc")]
    if not new and path.exists():
        return 0
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LATENCY_FIELDS, extrasaction="ignore")
        if write_header:
            w.writeheader()
        for it in new:
            seen, pub = _parse_ts(it.get("first_seen_utc")), _parse_ts(it.get("published_utc"))
            flag = _pub_flag(pub, now)
            lag = ""
            if not flag and seen and pub:
                lag = int((seen - pub).total_seconds())
            w.writerow({
                "first_seen_utc": it.get("first_seen_utc") or "",
                "published_utc": it.get("published_utc") or "",
                "source": it.get("source") or "",
                "url": it["url"],
                "lag_sec": lag,
                "flag": flag,
            })
    return len(new)


def _median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return float(s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2)


def latency_counts(rows: list[dict], first_run_utc, min_n: int = 30) -> dict:
    """Median lag per source. Only published_utc >= first_run_utc and not pub_ugyldig. FLAG when n<30."""
    start = _parse_ts(first_run_utc)
    by: dict[str, list[float]] = {}
    for r in rows:
        if (r.get("flag") or "").strip() == "pub_ugyldig":
            continue
        pub = _parse_ts(r.get("published_utc"))
        if pub is None or (start is not None and pub < start):
            continue
        lag = r.get("lag_sec")
        if lag is None or lag == "":
            continue
        try:
            by.setdefault(r.get("source") or "", []).append(float(lag))
        except (TypeError, ValueError):
            continue

    def pack(name, vals):
        n = len(vals)
        return {"source": name, "n": n, "median_sec": _median(vals), "flag": "FLAG" if n < min_n else ""}

    sources = [pack(k, v) for k, v in sorted(by.items(), key=lambda kv: kv[0].lower())]
    all_vals = [x for v in by.values() for x in v]
    return {"first_run_utc": _iso(start) if start else None, "sources": sources, "all": pack("alle", all_vals)}


def latency_report(path: Path | None = None, first_run_utc=None, min_n: int = 30, state: dict | None = None) -> dict:
    path = path or LATENCY_PATH
    if first_run_utc is None:
        first_run_utc = (state or load_state()).get("first_run_utc")
    if not path.exists():
        return latency_counts([], first_run_utc, min_n)
    with path.open() as f:
        rows = list(csv.DictReader(f))
    return latency_counts(rows, first_run_utc, min_n)


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
    items = prune_pools(items, now, cfg.get("retention_hours", RETENTION_H),
                        cfg.get("max_items_editorial", MAX_EDITORIAL),
                        cfg.get("max_items_newsweb", MAX_NEWSWEB))
    slim = []
    for it in items:
        row = {k: it.get(k) for k in ITEM_KEYS}
        row["pool"] = it.get("pool") or (POOL_NEWSWEB if is_newsweb(it) else POOL_EDIT)
        slim.append(row)
    items = slim
    first_run = state.get("first_run_utc") or _iso(now)
    prior_ok = dict(state.get("source_ok_at") or {})
    sources = source_statuses(feeds, results, items, now, cfg.get("source_down_after_hours", DOWN_AFTER_H), prior_ok)
    source_ok_at = {s["id"]: s["last_updated_utc"] for s in sources if s.get("last_updated_utc")}
    n_ed = sum(1 for it in items if it.get("pool") == POOL_EDIT)
    n_nw = sum(1 for it in items if it.get("pool") == POOL_NEWSWEB)
    data = {
        "generated_at_utc": _iso(now),
        "generated_at_oslo": now.astimezone(OSLO).strftime("%Y-%m-%d %H:%M %Z"),
        "retention_hours": cfg.get("retention_hours", RETENTION_H),
        "max_items_editorial": cfg.get("max_items_editorial", MAX_EDITORIAL),
        "max_items_newsweb": cfg.get("max_items_newsweb", MAX_NEWSWEB),
        "first_run_utc": first_run,
        "n": len(items),
        "n_editorial": n_ed,
        "n_newsweb": n_nw,
        "items": items,
        "sources": sources,
    }
    new_state = {"items": items, "source_ok_at": source_ok_at, "first_run_utc": first_run, "results": {
        fid: {**rec, "at": _iso(rec["at"]) if isinstance(rec.get("at"), datetime) else rec.get("at")}
        for fid, rec in results.items()
    }}
    if write:
        n_new = append_latency(items, prev_urls, now=now)
        write_output(data)
        save_state(new_state)
        log.info("nyheter: %s saker (%s redaksjonelt, %s newsweb), %s nye i latency-loggen", len(items), n_ed, n_nw, n_new)
    return data, new_state


def main(argv=None) -> int:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="nyheter")
    p.add_argument("--latency", action="store_true", help="Median lag per kilde (n, FLAG når n<30)")
    args = p.parse_args(argv)
    if args.latency:
        rep = latency_report()
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    collect(write=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
