"""Nyheter-samler 17.11: syntetiske feeder, eksakt dedup, 48 t / 300, status og latency."""
from __future__ import annotations

import csv, json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from signaltool import nyheter as N

NOW = datetime(2026, 11, 17, 14, 30, tzinfo=timezone.utc)
T0 = NOW - timedelta(hours=2)
T_OLD = NOW - timedelta(hours=60)
T_47 = NOW - timedelta(hours=47)


def _rss(entries: list[tuple[str, str, str]]) -> bytes:
    items = []
    for title, url, pub in entries:
        items.append(
            f"<item><title>{title}</title><link>{url}</link>"
            f"<pubDate>{pub}</pubDate><description>BODY MUST NOT LEAK {title}</description>"
            f"<content:encoded><![CDATA[<p>full article</p>]]></content:encoded></item>"
        )
    return (
        '<?xml version="1.0"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
        "<channel><title>Test</title>" + "".join(items) + "</channel></rss>"
    ).encode()


def _atom(entries: list[tuple[str, str, str]]) -> bytes:
    items = []
    for title, url, pub in entries:
        items.append(
            f'<entry><title>{title}</title><link href="{url}"/><updated>{pub}</updated>'
            f"<summary>ATOM SUMMARY</summary></entry>"
        )
    return (
        '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
        "<title>Atom</title>" + "".join(items) + "</feed>"
    ).encode()


def _rfc2822(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def _feed(fid="e24", source="E24", source_id="e24", section="Marked", paywall=True, url="https://example.test/e24.xml", kind="rss"):
    return {"id": fid, "source": source, "source_id": source_id, "section": section,
            "paywall": paywall, "url": url, "kind": kind, "enabled": True}


class _R:
    def __init__(self, content, status=200):
        self.content = content
        self.status_code = status
    def json(self):
        return json.loads(self.content)


def test_parse_rss_and_atom_keeps_only_headline_fields():
    rss = N.parse_feed(_rss([("Oljeprisen stiger", "https://e24.example/a", _rfc2822(T0))]), _feed())
    atom = N.parse_feed(_atom([("UK talks", "https://bbc.example/b", T0.strftime("%Y-%m-%dT%H:%M:%SZ"))]),
                        _feed("bbc-world", "BBC", "bbc", "Verden", False))
    assert rss[0]["title"] == "Oljeprisen stiger" and rss[0]["url"] == "https://e24.example/a"
    assert rss[0]["source"] == "E24" and rss[0]["section"] == "Marked" and rss[0]["paywall"] is True
    assert rss[0]["published_utc"] == N._iso(T0)
    assert atom[0]["section"] == "Verden" and atom[0]["paywall"] is False
    for it in rss + atom:
        assert set(it) <= set(N.ITEM_KEYS)
        blob = json.dumps(it)
        assert "BODY MUST NOT LEAK" not in blob and "full article" not in blob and "ATOM SUMMARY" not in blob
        assert "summary" not in it and "description" not in it and "content" not in it and "tema" not in it


def test_dedupe_exact_url_and_same_title_same_source_only():
    a = N._item("Same title", "https://x.test/1", "E24", "e24", T0, "Marked", True)
    b = N._item("Same title", "https://x.test/1?ref=1", "E24", "e24", T0, "Marked", True)  # different URL, same title+source
    c = N._item("Same title", "https://dn.test/1", "DN", "dn", T0, "Marked", True)  # same title, other source: keep
    d = N._item("Other", "https://x.test/1", "E24", "e24", T0, "Marked", True)  # same URL as a: drop
    out = N.dedupe([a, d, b, c])
    urls = [it["url"] for it in out]
    assert urls == ["https://x.test/1", "https://dn.test/1"]
    assert [it["source"] for it in out] == ["E24", "DN"]


def test_prune_48h_and_max_300_newest_first():
    items = [N._item(f"T{i}", f"https://x.test/{i}", "E24", "e24", NOW - timedelta(minutes=i), "Marked", False)
             for i in range(320)]
    items.append(N._item("Old", "https://x.test/old", "E24", "e24", T_OLD, "Marked", False))
    items.append(N._item("Keep47", "https://x.test/47", "E24", "e24", T_47, "Marked", False))
    out = N.prune(items, NOW, 48, 300)
    assert len(out) == 300
    assert out[0]["title"] == "T0" and out[1]["title"] == "T1"
    assert "Old" not in {it["title"] for it in out}
    # 47h item is newer than minute 320, but max 300 cuts the tail; still within window if we prune first
    kept_only = N.prune([items[-1], items[-2]], NOW, 48, 300)
    assert [it["title"] for it in kept_only] == ["Keep47"]


def test_first_seen_stable_and_latency_append(tmp_path):
    cfg = {"retention_hours": 48, "max_items": 300, "source_down_after_hours": 6,
           "feeds": [_feed()]}
    pub = _rfc2822(T0)
    body = _rss([("Ny sak", "https://e24.example/n1", pub)])
    data1, st1 = N.collect(cfg, now=NOW, get=lambda *a, **k: _R(body), state={})
    assert data1["items"][0]["first_seen_utc"] == N._iso(NOW)
    later = NOW + timedelta(minutes=10)
    data2, st2 = N.collect(cfg, now=later, get=lambda *a, **k: _R(body), state=st1)
    assert data2["items"][0]["first_seen_utc"] == N._iso(NOW)
    p = tmp_path / "lat.csv"
    assert N.append_latency(data1["items"], set(), p) == 1
    assert N.append_latency(data2["items"], {"https://e24.example/n1"}, p) == 0
    rows = list(csv.DictReader(p.open()))
    assert len(rows) == 1 and rows[0]["url"] == "https://e24.example/n1"
    assert int(rows[0]["lag_sec"]) == 2 * 3600


def test_source_down_after_6h_keeps_source_listed():
    feeds = [_feed()]
    items = [N._item("Sak", "https://e24.example/a", "E24", "e24", NOW - timedelta(hours=3), "Marked", True,
                     first_seen=NOW - timedelta(hours=3))]
    # last success 7h ago, this run failed
    prior = {"e24": N._iso(NOW - timedelta(hours=7))}
    results = {"e24": {"ok": False, "at": NOW, "error": "HTTPError: 502"}}
    rows = N.source_statuses(feeds, results, items, NOW, 6, prior)
    assert len(rows) == 1 and rows[0]["status"] == "kilde nede" and rows[0]["name"] == "E24"
    assert rows[0]["error"] and rows[0]["last_updated"] == "08:30"  # 07:30 UTC = 08:30 Oslo (CET)
    # successful fetch 10 min ago, no new item: still ok
    prior_ok = {"e24": N._iso(NOW - timedelta(minutes=10))}
    rows_ok = N.source_statuses(feeds, {"e24": {"ok": True, "at": NOW - timedelta(minutes=10)}}, [], NOW, 6, prior_ok)
    assert rows_ok[0]["status"] == "ok" and rows_ok[0]["last_updated"] == "15:20"


def test_failed_fetch_does_not_immediately_mark_down():
    cfg = {"retention_hours": 48, "max_items": 300, "source_down_after_hours": 6, "feeds": [_feed()]}
    body = _rss([("Sak", "https://e24.example/a", _rfc2822(T0))])
    _, st = N.collect(cfg, now=NOW, get=lambda *a, **k: _R(body), state={})
    def boom(*a, **k):
        raise RuntimeError("timeout")
    data, st2 = N.collect(cfg, now=NOW + timedelta(hours=1), get=boom, state=st)
    assert data["sources"][0]["status"] == "ok"
    data3, _ = N.collect(cfg, now=NOW + timedelta(hours=7), get=boom, state=st2)
    assert data3["sources"][0]["status"] == "kilde nede"
    assert data3["items"] and data3["items"][0]["title"] == "Sak"  # 48h window still kept


def test_newsweb_json_mapping_no_body():
    feed = _feed("newsweb", "Oslo Børs Newsweb", "newsweb", "Norge", False,
                 "https://api3.oslo.oslobors.no/v1/newsreader/list", "newsweb_json")
    payload = json.dumps({"data": {"messages": [
        {"messageId": 42, "title": "Mandatory notification of trade", "issuerSign": "EQNR",
         "publishedTime": "2026-11-17T14:16:47Z", "body": "SECRET BODY"},
        {"messageId": 43, "title": "EQNR: Quarterly report", "issuerSign": "EQNR",
         "publishedTime": "2026-11-17T10:00:00Z"},
    ]}}).encode()
    rows = N.fetch_newsweb(feed, lambda *a, **k: _R(payload), NOW)
    assert rows[0]["title"] == "EQNR: Mandatory notification of trade"
    assert rows[0]["url"] == "https://newsweb.oslobors.no/message/42"
    assert rows[0]["section"] == "Norge" and rows[0]["paywall"] is False
    assert rows[0]["published_utc"] == "2026-11-17T14:16:47Z"
    assert rows[1]["title"] == "EQNR: Quarterly report"  # issuer already in title
    assert all("SECRET" not in json.dumps(r) and "body" not in r for r in rows)


def test_collect_sections_and_no_theme_import(monkeypatch):
    cfg = {"retention_hours": 48, "max_items": 300, "feeds": [
        _feed(),
        _feed("nrk-siste", "NRK", "nrk", "Norge", False, "https://example.test/nrk.xml"),
    ]}
    bodies = {
        "https://example.test/e24.xml": _rss([("E24-sak", "https://e24.example/a", _rfc2822(T0))]),
        "https://example.test/nrk.xml": _rss([("NRK-sak", "https://nrk.example/a", _rfc2822(NOW - timedelta(hours=1)))]),
    }
    def get(url, **k):
        return _R(bodies[url])
    data, _ = N.collect(cfg, now=NOW, get=get, state={})
    assert data["n"] == 2
    assert [it["title"] for it in data["items"]] == ["NRK-sak", "E24-sak"]  # newest first (1 t vs 2 t)
    assert data["items"][0]["section"] == "Norge" and data["items"][1]["section"] == "Marked"
    assert "tema" not in data and all("tema" not in it and "score" not in it for it in data["items"])
    # module must not pull in the theme matcher
    import sys
    assert "signaltool.themes" not in sys.modules and "signaltool.tema_trend" not in sys.modules
    assert "signaltool.theme_maps" not in sys.modules and "signaltool.categories" not in sys.modules


def test_write_output_and_state(tmp_path, monkeypatch):
    cfg = {"retention_hours": 48, "max_items": 300, "feeds": [_feed()]}
    body = _rss([("Sak", "https://e24.example/a", _rfc2822(T0))])
    monkeypatch.setattr(N, "OUT_PATH", tmp_path / "nyheter.json")
    monkeypatch.setattr(N, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(N, "LATENCY_PATH", tmp_path / "lat.csv")
    site = tmp_path / "site" / "nyheter.json"
    monkeypatch.setattr(N, "SITE_PATH", site)
    N.collect(cfg, now=NOW, get=lambda *a, **k: _R(body), state={}, write=True)
    data = json.loads((tmp_path / "nyheter.json").read_text())
    assert data["n"] == 1 and site.exists()
    assert list(csv.DictReader((tmp_path / "lat.csv").open()))
