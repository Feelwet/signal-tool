"""GSbot 29.10 (godkjent plan, rask runde): «i dag»/«i morgen», Marked-lenke, firmanavn, maks 3 signalbrikker + «+N», dempet poengsum."""
import json
import re

from signaltool import briefing as BR
from signaltool import names as NM
from signaltool import overview as OV
from signaltool import site as S


def test_when_days():
    assert BR.when_days(0) == "i dag" and BR.when_days(1) == "i morgen" and BR.when_days(5) == "om 5 d"
    assert BR.when_days(3, "dager") == "om 3 dager" and BR.when_days("x") == "om x d"


def test_fix_days_text_old_snapshots():
    assert BR.fix_days_text("VRT: kvartalsrapport om 0 d (2026-10-29)") == "VRT: kvartalsrapport i dag (2026-10-29)"
    assert BR.fix_days_text("X: kvartalsrapport om 1 d (2026-10-30)") == "X: kvartalsrapport i morgen (2026-10-30)"
    assert BR.fix_days_text("X: kvartalsrapport om 10 d") == "X: kvartalsrapport om 10 d"


def test_alert_title_no_om_0_d():
    snap = {"tickers": [{"ticker": "VRT", "category": "hold", "stats": {}, "decision": {"days_to_earnings": 0, "next_earnings": "2026-10-29"}},
                        {"ticker": "EQIX", "category": "kjop", "stats": {}, "decision": {"days_to_earnings": 1, "next_earnings": "2026-10-30"}}]}
    t = [a["title"] for a in BR.alerts(snap)]
    assert "VRT: kvartalsrapport i dag (2026-10-29)" in t and "EQIX: kvartalsrapport i morgen (2026-10-30)" in t
    assert not any("om 0 d" in x or "om 1 d" in x for x in t)


def test_changes_alerts_rewrites_stale_titles():
    snap = {"briefing": {"alerts": [{"level": "info", "title": "VRT: kvartalsrapport om 0 d (2026-10-29)", "link": "ticker/VRT"}]}}
    h = OV.changes_alerts_html(snap)
    assert "kvartalsrapport i dag" in h and "om 0 d" not in h


def test_market_tile_links_to_regime():
    h = OV.strip_html({"regime": {"^GSPC": {"risk_off": False, "below": False}}, "date": "2026-10-29"})
    assert 'href="metode.html#regime">Marked →' in h and "#regler" not in h


def test_names_for_candidates_from_yahoo_cache():
    d = json.loads(NM.PATH.read_text())
    assert d["names"]["VRT"]["name"] and d["names"]["EQIX"]["name"]   # hentet med python3 -m signaltool.names, ikke håndskrevet
    assert NM.missing(["VRT", "EQIX"]) == []
    assert NM.missing(["ZZZZ_FINNES_IKKE"]) == ["ZZZZ_FINNES_IKKE"] and NM.missing(["ZZZZ_FINNES_IKKE"], {"ZZZZ_FINNES_IKKE": "Navn"}) == []


def _pill(t):
    return f'<span class="pill">{t}</span>'


def test_chips_max3_plus_n_in_order():
    assert S.chips_html([_pill("a"), _pill("b"), _pill("c")]) == " ".join(_pill(x) for x in "abc")
    h = S.chips_html([_pill(x) for x in "abcde"])
    vis = re.findall(r'<span class="pill">(\w)</span>', h.split('class="tip"')[0])
    assert vis == ["a", "b", "c"]
    assert re.findall(r'<span class="pill px">(\w)</span>', h) == ["d", "e"]   # vises bare under 700 px (mobil uendret)
    assert 'class="ri ri-c pill pmore"' in h and ">+2<" in h
    tip = h.split('class="tip">')[1]
    assert re.findall(r'<span class="pill">(\w)</span>', tip) == ["d", "e"]


def test_chip_css_pc_only():
    c = S.CHIP_CSS
    assert "#tf-table .pmore{display:none}" in c and "@media(min-width:700px){" in c and "#tf-table .pill.px{display:none}" in c.split("@media(min-width:700px){#tf-table td.sg-c")[1]


def test_score_muted_value_unchanged():
    m, n = S.score_badge(4.0, 4, 2, muted=True), S.score_badge(4.0, 4, 2)
    assert re.sub(r"<[^>]+>", "", m) == re.sub(r"<[^>]+>", "", n) == "4.00"   # sortering leser textContent -> samme tall
    assert 'class="score mu"' in m and 'title="Rangering, ikke testet"' in m and "hot" not in m
    assert n == '<span class="score hot">4.00</span>'   # tema-poeng (ikke dempet) uendret
    assert ".score.mu .sv{font-size:14px" in S.SCORE_CSS and "color:#94a3b8" in S.SCORE_CSS
    assert "Rangering, ikke testet" in S.score_info() and "<script>" not in S.score_info() and "window.__scI" in S.SCORE_I_JS
