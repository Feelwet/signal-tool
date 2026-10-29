import re
"""Site generator: dark theme, relative links (works under https://<user>.github.io/<repo>/)."""
import json, re
from pathlib import Path
import pytest
from signaltool import site

SNAP = Path(__file__).resolve().parent.parent / "site" / "data.json"


def test_css_is_dark():
    assert "color-scheme:dark" in site.CSS
    bg = re.search(r"--bg:#([0-9a-f]{6})", site.CSS).group(1)
    assert sum(int(bg[i:i + 2], 16) for i in (0, 2, 4)) < 120


def test_rel_label_levels():
    assert 'rel hi' in site.rel_label("Offisiell statistikk – høy pålitelighet")
    assert 'rel mid' in site.rel_label("Offisiell, foreløpige tall – middels/høy")
    assert 'rel lo' in site.rel_label("Sosiale medier – lav")


@pytest.mark.skipif(not SNAP.exists(), reason="no snapshot available")
def test_build_uses_relative_links(tmp_path, monkeypatch):
    snap = json.loads(SNAP.read_text())
    monkeypatch.setattr(site, "SITE", tmp_path / "site")
    site.build(snap)
    out = tmp_path / "site"
    assert (out / "index.html").exists() and (out / "style.css").exists()
    for f in out.rglob("*.html"):
        txt = f.read_text()
        assert not re.search(r'(href|src)="/(?!/)', txt), f"absolute link in {f}"
        assert "localhost" not in txt and "/workspace" not in txt
    assert 'href="../style.css?v=' in (out / "tema" / f"{snap['themes'][0]['key']}.html").read_text()


@pytest.mark.skipif(not SNAP.exists(), reason="no snapshot available")
def test_category_badges_and_disclaimer(tmp_path, monkeypatch):
    snap = json.loads(SNAP.read_text())
    e = snap["tickers"][0]
    e.update({"category": "kjop", "cat_reason": "test-grunn", "cat_rules": [["Regel", True, "ok"], ["Regel 2", False, "nei"]]})
    monkeypatch.setattr(site, "SITE", tmp_path / "site")
    site.build(snap)
    out = tmp_path / "site"
    idx = (out / "index.html").read_text()
    tk = (out / "tickere.html").read_text()  # full kategoritekst på Tickere etter opprydding
    assert 'class="rk ' in tk and 'Risiko<span class="rkp-m"> · Poeng</span></th>' in tk and 'cat kjop' not in tk and "Treffrate fra fremoverloggen" in (tmp_path / "site" / "metode.html").read_text()
    tp = (out / "ticker" / f"{site.slug(e['ticker'])}.html").read_text()
    assert "Risiko:" in tp and "Risikonivå er testet på historiske data. Kategoriene er ikke bekreftet." in tp and "✔ oppfylt" not in tp
    tk = (out / "tickere.html").read_text()
    assert 'id="treffsikkerhet"' in tk
    assert "Kjøp-kandidat" in (out / "metode.html").read_text() and "metode.html" in (out / "kilder.html").read_text()


def test_left_sidebar_layout():
    html = site.page("Oversikt", "<div class=\"card\"><h2>Test</h2><p>x</p></div>", 0, {"generated": "2026-10-05 12:00"})
    assert 'class="side"' in html and 'id="folds-open"' in html and 'id="folds-close"' in html
    assert 'class="on"' in html  # Oversikt marked active
    assert site.fold("Tittel", "<p>innhold</p>").startswith("<details class=\"fold\" open>")


@pytest.mark.skipif(not SNAP.exists(), reason="no snapshot available")
def test_dashboard_overview(tmp_path, monkeypatch):
    snap = json.loads(SNAP.read_text())
    monkeypatch.setattr(site, "SITE", tmp_path / "site")
    site.build(snap)
    idx = (tmp_path / "site" / "index.html").read_text()
    assert "ov-strip" in idx and 'id="temascore"' in idx and "ov-2" in idx and "Risikonivå" in idx
    assert re.search(r'href="style\.css\?v=[0-9a-f]{10}"', idx) and "<style>" in idx and ".ov-strip{" in idx and '<a class="ov-tile"' not in idx
    assert "donut" not in idx and "Hva bør jeg se på" not in idx and "Newsweb-kontrakter" not in idx and 'metode.html#treffrate' in idx
    assert "tema/" in idx and "ticker/" in idx


def test_layout_staleness_and_watch_text():
    from datetime import date
    from signaltool import site_layout as L
    rows = [{"ts": f"2026-10-{d:02d}T03:00", "source": "S", "state": s} for d, s in ((1, "ok"), (2, "fail"), (3, "fail"), (4, "fail"))]
    st = L.staleness(rows, "S", date(2026, 10, 5))
    assert st["stale"] and not st["dead"] and st["last_ok"] == "2026-10-01"
    rows[2]["state"] = "partial"   # partial counts as ok
    assert not L.staleness(rows, "S", date(2026, 10, 5))["stale"]
    assert L.staleness(rows, "S", date(2026, 10, 30))["dead"]
    t = L.watch_text({"cats": {"watch": {"h5": {"n": 136, "hit": 0.537, "hit_ci": [0.453, 0.618]}}, "kjop": {"h5": {"n": 0}}}})
    assert "53,7 %" in t and "45–62 %" in t and "n=136" in t and "FLAG: ikke skilt fra tilfeldig" in t and "Kjøp: n=0, ikke målt ennå" in t and "0 %" not in t.replace("53,7 %", "")


def test_theme_score_log(tmp_path):
    from signaltool.pipeline import append_theme_scores
    th = [{"key": "a", "score": 1.5, "tickers": [{"ticker": "SPY", "role": "vinner", "close": 10}, {"ticker": "X", "role": "taper", "close": 99}]}]
    p = tmp_path / "t.csv"
    append_theme_scores(th, "2026-10-24", p); append_theme_scores(th, "2026-10-24", p); append_theme_scores(th, "2026-10-25", p)
    lines = p.read_text().splitlines()
    assert len(lines) == 3 and lines[0].split(",")[3] == "mean_close_candidates" and lines[1].startswith("2026-10-24,a,1.5,10.0,1,SPY,10")


@pytest.mark.skipif(not SNAP.exists(), reason="no snapshot available")
def test_every_page_has_css_version(tmp_path, monkeypatch):
    snap = json.loads(SNAP.read_text())
    monkeypatch.setattr(site, "SITE", tmp_path / "site")
    site.build(snap)
    v = site.CSS_V[0]
    assert re.fullmatch(r"[0-9a-f]{10}", v)
    pages = [p for p in (tmp_path / "site").rglob("*.html") if "http-equiv=\"refresh\"" not in p.read_text()]
    assert len(pages) > 20
    for p in pages:
        h = p.read_text()
        assert f'style.css?v={v}"' in h and 'style.css"' not in h, p.name
