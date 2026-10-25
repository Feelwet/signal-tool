import re
from pathlib import Path
from signaltool import site_layout as L, evidens as EV, analyst as A

SITE = Path(__file__).resolve().parent.parent / "site"


def test_info_tip_shape():
    h = L.info_tip("Forklaring her", "Tittel")
    assert 'role="tooltip"' in h and 'aria-describedby="' in h and "title=" not in h
    tid = re.search(r'aria-describedby="([^"]+)"', h).group(1)
    assert f'id="{tid}"' in h and "<b>Tittel</b>" in h


def test_info_tip_empty_is_nothing():
    assert L.info_tip("") == ""


def test_ids_unique():
    a, b = L.info_tip("x"), L.info_tip("y")
    assert re.search(r'id="(\w+)"', a).group(1) != re.search(r'id="(\w+)"', b).group(1)


def test_badge_and_analyst_use_component():
    for h in (L.xbadge("X", "tekst"), EV.badge("two_plus")):
        assert 'class="ilink"' not in h and "title=" not in h.split('class="info"')[1].split(">")[0]
        assert 'class="tip"' in h


def test_css_box_spec():
    c = L.CSS
    tip = re.search(r"\.tip\{[^}]*\}", c).group(0)
    for k in ("padding:12px", "280px", "font-size:14px", "border:1px solid var(--acc", "border-radius", "100vw - 16px", "background:#1c2330"):
        assert k in tip
    assert "Escape" in L.TIP_JS and "pointerover" in L.TIP_JS and "focusin" in L.TIP_JS and "querySelectorAll" not in L.TIP_JS and "focus" in L.TIP_JS and "innerWidth" in L.TIP_JS


def test_built_pages_every_tip_nonempty():
    pages = list(SITE.rglob("*.html"))
    n = 0
    for p in pages:
        s = p.read_text(errors="ignore")
        assert 'class="ilink"' not in s, p
        for m in re.finditer(r'<button[^>]*class="info"[^>]*>', s):
            assert "title=" not in m.group(0), p
            tid = re.search(r'aria-describedby="([^"]+)"', m.group(0)).group(1)
            t = re.search(rf'<span role="tooltip" id="{re.escape(tid)}" class="tip" hidden>(.*?)</span>', s, re.S)
            assert t and re.sub("<[^>]+>", "", t.group(1)).strip(), (p, tid)
            n += 1
    if pages:
        assert n > 0
