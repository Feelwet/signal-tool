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
    assert int(rows[0]["lag_sec"]) == 2 * 3600 and rows[0].get("flag", "") == ""
    assert data1["first_run_utc"] == N._iso(NOW) and data2["first_run_utc"] == N._iso(NOW)


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
    assert rows[0]["title"] == "Mandatory notification of trade"  # issuer is not prefixed into the title
    assert rows[0]["issuer"] == "EQNR"
    assert rows[0]["url"] == "https://newsweb.oslobors.no/message/42"
    assert rows[0]["section"] == "Børsmeldinger" and rows[0]["paywall"] is False
    assert rows[0]["published_utc"] == "2026-11-17T14:16:47Z"
    assert rows[1]["title"] == "EQNR: Quarterly report" and rows[1]["issuer"] == "EQNR"
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
    # samleren skal ikke trekke inn temamatcheren (sjekk kilden, ikke sys.modules — andre tester importerer site)
    src = Path(N.__file__).read_text()
    for name in ("signaltool.themes", "tema_trend", "theme_maps", "categories"):
        assert name not in src


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
    assert data["first_run_utc"] == N._iso(NOW) and data["n_editorial"] == 1 and data["n_newsweb"] == 0
    assert list(csv.DictReader((tmp_path / "lat.csv").open()))



def test_newsweb_same_title_different_issuers_kept():
    a = N._item("Mandatory notification of trade", "https://newsweb.oslobors.no/message/1",
                "Oslo Børs Newsweb", "newsweb", T0, "Børsmeldinger", False, issuer="EQNR")
    b = N._item("Mandatory notification of trade", "https://newsweb.oslobors.no/message/2",
                "Oslo Børs Newsweb", "newsweb", T0, "Børsmeldinger", False, issuer="DNB")
    c = N._item("Mandatory notification of trade", "https://newsweb.oslobors.no/message/3",
                "Oslo Børs Newsweb", "newsweb", T0, "Børsmeldinger", False, issuer="EQNR")
    out = N.dedupe([a, b, c])
    assert {(it["url"], it["issuer"]) for it in out} == {
        ("https://newsweb.oslobors.no/message/1", "EQNR"),
        ("https://newsweb.oslobors.no/message/2", "DNB"),
    }


def test_prune_pools_300_editorial_150_newsweb_and_tabs():
    ed = [N._item(f"E{i}", f"https://e24.example/{i}", "E24", "e24", NOW - timedelta(minutes=i), "Marked", True)
          for i in range(320)]
    no = [N._item(f"N{i}", f"https://nrk.example/{i}", "NRK", "nrk", NOW - timedelta(minutes=i, seconds=1), "Norge", False)
          for i in range(20)]
    nw = [N._item(f"W{i}", f"https://newsweb.oslobors.no/message/{i}", "Oslo Børs Newsweb", "newsweb",
                  NOW - timedelta(minutes=i, seconds=2), "Børsmeldinger", False, issuer=f"T{i}")
          for i in range(180)]
    nw.append(N._item("OldW", "https://newsweb.oslobors.no/message/old", "Oslo Børs Newsweb", "newsweb",
                      T_OLD, "Børsmeldinger", False, issuer="OLD"))
    out = N.prune_pools(ed + no + nw, NOW, 48, 300, 150)
    assert sum(1 for it in out if it["pool"] == "editorial") == 300
    assert sum(1 for it in out if it["pool"] == "newsweb") == 150
    assert "OldW" not in {it["title"] for it in out}
    assert all(it["section"] == "Børsmeldinger" for it in out if it["pool"] == "newsweb")
    alt = [it for it in out if N.in_tab(it, "Alt")]
    norge = [it for it in out if N.in_tab(it, "Norge")]
    bors = [it for it in out if N.in_tab(it, "Børsmeldinger")]
    assert all(not N.is_newsweb(it) for it in alt)
    assert all(it["section"] == "Norge" and not N.is_newsweb(it) for it in norge)
    assert all(N.is_newsweb(it) for it in bors) and len(bors) == 150
    assert len(alt) + len(bors) == len(out)


def test_first_run_not_overwritten_and_pub_ugyldig(tmp_path):
    p = tmp_path / "lat.csv"
    now = NOW
    ok = N._item("Ok", "https://e24.example/ok", "E24", "e24", now - timedelta(minutes=3), "Marked", False, first_seen=now)
    missing = N._item("Mangler", "https://e24.example/miss", "E24", "e24", None, "Marked", False, first_seen=now)
    missing["published_utc"] = None
    future = N._item("Fremtid", "https://e24.example/fut", "E24", "e24", now + timedelta(minutes=6), "Marked", False, first_seen=now)
    slight = N._item("Liten", "https://e24.example/sl", "E24", "e24", now + timedelta(minutes=2), "Marked", False, first_seen=now)
    n = N.append_latency([ok, missing, future, slight], set(), p, now=now)
    assert n == 4
    rows = list(csv.DictReader(p.open()))
    by = {r["url"].rsplit("/", 1)[-1]: r for r in rows}
    assert by["ok"]["flag"] == "" and int(by["ok"]["lag_sec"]) == 180
    assert by["miss"]["flag"] == "pub_ugyldig" and by["miss"]["lag_sec"] == ""
    assert by["fut"]["flag"] == "pub_ugyldig" and by["fut"]["lag_sec"] == ""
    assert by["sl"]["flag"] == ""  # <5 min future stays valid; lag may be negative
    assert int(by["sl"]["lag_sec"]) == -120
    # collect keeps first_run_utc
    cfg = {"retention_hours": 48, "feeds": [_feed()]}
    body = _rss([("Sak", "https://e24.example/a", _rfc2822(T0))])
    d1, st = N.collect(cfg, now=NOW, get=lambda *a, **k: _R(body), state={})
    d2, _ = N.collect(cfg, now=NOW + timedelta(hours=3), get=lambda *a, **k: _R(body), state=st)
    assert d1["first_run_utc"] == N._iso(NOW) == d2["first_run_utc"] == st["first_run_utc"]


def test_latency_report_median_flag_n_lt_30_and_first_run_cutoff(tmp_path):
    first = NOW
    rows = []
    # 10 backfill rows published before first_run — excluded
    for i in range(10):
        rows.append({"source": "E24", "published_utc": N._iso(first - timedelta(hours=2, minutes=i)),
                     "lag_sec": "9999", "flag": ""})
    # 29 valid E24 after first_run, lags 10,20,...,290
    for i in range(29):
        rows.append({"source": "E24", "published_utc": N._iso(first + timedelta(minutes=i)),
                     "lag_sec": str((i + 1) * 10), "flag": ""})
    # invalid — never as 0, excluded
    rows.append({"source": "E24", "published_utc": "", "lag_sec": "0", "flag": "pub_ugyldig"})
    rows.append({"source": "E24", "published_utc": N._iso(first + timedelta(minutes=40)),
                 "lag_sec": "", "flag": "pub_ugyldig"})
    # BBC: 30 valid (no FLAG), lags 1..30 median 15.5
    for i in range(30):
        rows.append({"source": "BBC", "published_utc": N._iso(first + timedelta(minutes=i)),
                     "lag_sec": str(i + 1), "flag": ""})
    p = tmp_path / "lat.csv"
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=N.LATENCY_FIELDS)
        w.writeheader(); w.writerows(rows)
    rep = N.latency_report(p, first_run_utc=N._iso(first), min_n=30)
    by = {s["source"]: s for s in rep["sources"]}
    assert by["E24"]["n"] == 29 and by["E24"]["flag"] == "FLAG"
    assert by["E24"]["median_sec"] == 150  # 10..290, 29 values, middle is 150
    assert by["BBC"]["n"] == 30 and by["BBC"]["flag"] == ""
    assert by["BBC"]["median_sec"] == 15.5
    assert rep["all"]["n"] == 59 and rep["all"]["flag"] == ""
    # script entry
    assert N.latency_counts([], first)["all"]["flag"] == "FLAG" and N.latency_counts([], first)["all"]["n"] == 0


def test_page_layout_tabs_raw_url_and_ft_credit():
    from signaltool import nyheter_page as P
    from signaltool import site as S
    h = P.html()
    css = P.PAGE_CSS
    assert P.TABS == ("Alt", "Norge", "Marked", "Verden", "Børsmeldinger")
    for t in P.TABS:
        assert f'data-tab="{t}"' in h
    assert "Tech" not in h and "Energi" not in h and "data-tab=\"Alle\"" not in h
    assert "https://raw.githubusercontent.com/Feelwet/signal-tool/master/logs/nyheter.json" in h
    assert "data/nyheter.json" in h
    assert "© The Financial Times Limited 2026" in h
    # 390 px metrics
    assert "height:56px" in css and "font:600 17px/24px" in css and "font:400 12px/16px" in css
    assert ".ny-tabs{height:44px" in css.replace(" ", "") or "ny-tabs{height:44px" in css
    assert "min-height:56px" in css and "max-height:72px" in css
    assert "flex:0 0 44px" in css and "15px/20px" in css and "-webkit-line-clamp:2" in css
    assert "width:720px" in css and "width:320px" in css and "gap:24px" in css and "width:1064px" in css
    assert "height:48px" in css and "Ingen saker matcher" in h and "Ingen kilder svarer nå" in h
    assert "ny-chip" in css and "issuer" in h
    page = S.page("Nyheter", h, 0, {"generated": "2026-11-17 15:00"})
    assert 'class="pg-nyheter"' in page or "pg-nyheter" in page
    assert "nyheter.html" in page
    assert "Børsmeldinger" in page
