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
    assert 'href="../style.css"' in (out / "tema" / f"{snap['themes'][0]['key']}.html").read_text()


@pytest.mark.skipif(not SNAP.exists(), reason="no snapshot available")
def test_category_badges_and_disclaimer(tmp_path, monkeypatch):
    snap = json.loads(SNAP.read_text())
    e = snap["tickers"][0]
    e.update({"category": "kjop", "cat_reason": "test-grunn", "cat_rules": [["Regel", True, "ok"], ["Regel 2", False, "nei"]]})
    monkeypatch.setattr(site, "SITE", tmp_path / "site")
    site.build(snap)
    out = tmp_path / "site"
    idx = (out / "index.html").read_text()
    assert 'class="cat kjop"' in idx and "Hvorfor: test-grunn" in idx and "ikke bevist å slå markedet" in idx
    tp = (out / "ticker" / f"{site.slug(e['ticker'])}.html").read_text()
    assert "✔ oppfylt" in tp and "✘ ikke oppfylt" in tp and "ikke bevist å slå markedet" in tp
    tk = (out / "tickere.html").read_text()
    assert 'id="treffsikkerhet"' in tk
    assert "Kjøp-kandidat" in (out / "kilder.html").read_text()


def test_left_sidebar_layout():
    html = site.page("Oversikt", "<div class=\"card\"><h2>Test</h2><p>x</p></div>", 0, {"generated": "2026-10-05 12:00"})
    assert 'class="side"' in html and 'id="folds-open"' in html and 'id="folds-close"' in html
    assert 'class="on"' in html  # Oversikt marked active
    assert site.fold("Tittel", "<p>innhold</p>").startswith("<details class=\"fold\" open>")
