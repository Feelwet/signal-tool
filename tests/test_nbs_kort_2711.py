"""Forklaringskort for NBS industriprofitt (27.11): parsing, tallkontroll, knapp og layout."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from signaltool import nbs_industriprofitt as N
from signaltool import nyheter_page as P

FIX = Path(__file__).parent / "fixtures" / "nbs"
CN_URL = "https://www.stats.gov.cn/sj/zxfb/202611/t20261127_1965949.html"
IP_URL = "https://www.stats.gov.cn/sj/sjjd/202611/t20261127_1965950.html"
EN_URL = "https://www.stats.gov.cn/english/PressRelease/202610/t20261028_1965704.html"
CNBC = {
    "title": "China industrial profits growth surges to a 5-month high of 20.1% in October",
    "url": "https://www.cnbc.com/2026/11/27/china-industrial-profits-october.html",
}


def _html(name: str) -> str:
    return (FIX / name).read_text()


def _cn_card():
    rel = N.parse_bulletin(_html("cn_bulletin_2026_01_10.html"), url=CN_URL, lang="cn")
    ip = N.parse_interp(_html("cn_interp_2026_01_10.html"), IP_URL)
    return rel, ip, N.build_card(rel, ip)


def _collect_card():
    pages = {CN_URL: _html("cn_bulletin_2026_01_10.html"), IP_URL: _html("cn_interp_2026_01_10.html")}
    return N.collect(
        en_index_html=_html("en_index.html"),
        cn_index_html=_html("cn_zxfb.html"),
        interp_index_html=_html("cn_sjjd.html"),
        pages=pages,
    )


def test_parse_cn_bulletin_october_2026_figures_and_industries():
    rel, ip, card = _cn_card()
    assert rel is not None
    assert rel.year == 2026 and rel.start_month == 1 and rel.end_month == 10
    assert rel.yoy_month == 20.1 and rel.yoy_cum == 16.0
    assert rel.published is not None
    assert rel.published.strftime("%Y-%m-%d %H:%M") == "2026-11-27 09:30"
    assert str(rel.published.tzinfo) == "Asia/Shanghai" or rel.published.utcoffset().total_seconds() == 8 * 3600
    names = {i.name_no: i for i in rel.industries}
    assert len(rel.industries) == 15
    assert names["Elektronikk og kommunikasjon"].fold == 1.0
    assert names["Ikke-jernholdige metaller"].pct == 71.7
    assert names["Kull"].pct == 61.4
    assert names["Kjemikalier"].pct == 50.3
    assert names["Biler"].pct == -26.0
    assert names["Ikke-metalliske mineralprodukter"].pct == -46.7
    assert names["Jernholdige metaller"].pct == -14.2
    assert names["Kraft og varme"].pct == -18.4
    assert names["Olje- og kullforedling"].loss_to_profit is True
    assert "%" not in names["Olje- og kullforedling"].change_label()
    assert card["ok"] is True and card["hide"] is False and card["missing_numbers"] == []
    labels = [v["label"] for v in card["blocks"]["tallet"]["values"]]
    assert labels == ["+20,1 % okt.", "+16,0 % jan.–okt."]
    assert card["source"]["published_oslo"] == "27.11.2026"
    assert card["source"]["published_row"] == "Publisert 27.11"
    assert card["source"]["line"] == "NBS · 27.11.2026"
    assert card["source"]["url"] == CN_URL
    # 09:30 Beijing = 01:30 UTC = 02:30 Europe/Oslo (CET)
    assert card["source"]["published"] == "2026-11-27T01:30:00Z"


def test_parse_en_bulletin_september_2026():
    rel = N.parse_bulletin(_html("en_bulletin_2026_01_09.html"), url=EN_URL, lang="en")
    assert rel.year == 2026 and rel.end_month == 9
    assert rel.yoy_month == 14.4 and rel.yoy_cum == 15.5
    names = {i.name_no: i for i in rel.industries}
    assert names["Elektronikk og kommunikasjon"].pct == 103.8
    assert names["Biler"].pct == -22.8
    assert names["Olje- og kullforedling"].loss_to_profit is True
    assert rel.published.strftime("%Y-%m-%d %H:%M") == "2026-10-28 09:30"


def test_interp_cause_marked_ifolge_nbs_and_keeps_source_decimals():
    _, ip, card = _cn_card()
    assert ip["ok"] is True
    text = ip["cause"]
    assert "doblet profitten (+100 %)" in text and "9,7 prosentpoeng" in text
    assert "5,69 %" in text and "0,45 prosentpoeng" in text
    assert "71,7" in text and "4,6 prosentpoeng" in text
    assert "5,7 %" not in text  # must not round 5.69
    fk = card["blocks"]["forklaring"]
    assert fk["attribution"] == "ifølge NBS" and fk["missing"] is False
    assert fk["label"] == "ifølge NBS"
    assert "prognose" not in fk["text"].lower()
    assert "bra for" not in fk["text"].lower() and "dårlig for" not in fk["text"].lower()


def test_collect_prefers_latest_period_and_attaches_interp():
    card = _collect_card()
    assert card["id"] == "nbs-industriprofitt-2026-01-10"
    assert card["ok"] is True and card["hide"] is False
    assert card["period"] == {"year": 2026, "start_month": 1, "end_month": 10}
    assert CN_URL in card["source"]["urls"] and IP_URL in card["source"]["urls"]
    # English Jan–Sep exists on the index but is older than Chinese Jan–Oct
    assert card["blocks"]["tallet"]["values"][0]["raw"] == 20.1


def test_parse_failure_yields_no_card():
    assert N.parse_bulletin("<html><body>ingen tall her</body></html>") is None
    card = N.collect(en_index_html="<html></html>", cn_index_html="<html></html>",
                     interp_index_html="<html></html>", pages={})
    assert card is None


def test_every_displayed_number_is_in_source_or_card_hides():
    rel, ip, card = _cn_card()
    visible = " ".join(v["label"] for v in card["blocks"]["tallet"]["values"])
    visible += " " + " ".join(r["change"] for r in card["blocks"]["endring"]["up"] + card["blocks"]["endring"]["down"])
    visible += " " + card["blocks"]["forklaring"]["text"]
    visible += " " + " ".join(s["detail"] for s in card["blocks"]["nevnt"]["sectors"])
    ok, missing = N.source_has_numbers(visible, [card["source_text"]])
    assert ok is True and missing == []
    # 99,9 is a substring of 6299.9 in the source and must still fail
    ok, missing = N.source_has_numbers("+99,9 % okt.", [card["source_text"]])
    assert ok is False and "99,9" in missing
    sab = N.build_card(rel, ip)
    sab["blocks"]["tallet"]["values"] = [{"label": "+99,9 % okt.", "raw": 99.9}]
    vis = sab["blocks"]["tallet"]["values"][0]["label"]
    ok, missing = N.source_has_numbers(vis, [sab["source_text"]])
    assert ok is False
    sab["ok"] = False
    sab["hide"] = True
    assert N.item_matches_card(CNBC, sab) is False


def test_button_only_for_primary_or_key_figure_never_theme_alone():
    card = _collect_card()
    assert N.item_matches_card(CNBC, card) is True
    assert N.item_matches_card({"title": "x", "url": CN_URL}, card) is True
    assert N.item_matches_card({"title": "x", "url": IP_URL}, card) is True
    assert N.item_matches_card({"title": "En slapp og flau forestilling",
                                "url": "https://www.nettavisen.no/industridod"}, card) is False
    # Theme words without this release's figures: no button
    assert N.item_matches_card({"title": "Kina og makro: rentene i Asia", "url": "https://e24.no/x"}, card) is False
    assert N.item_matches_card({"title": "China industrial profits rose last year",
                                "url": "https://www.cnbc.com/old.html"}, card) is False
    # Other official NBS story (production, not this release)
    assert N.item_matches_card({
        "title": "Industrial Production Operation in October 2026",
        "url": "https://www.stats.gov.cn/english/PressRelease/202611/t20261117_1965883.html",
    }, card) is False


def test_endring_max_four_rows_arrow_and_text_not_color():
    _, _, card = _cn_card()
    up, down = card["blocks"]["endring"]["up"], card["blocks"]["endring"]["down"]
    assert len(up) == 4 and len(down) == 4
    assert up[0]["industry"] == "Elektronikk og kommunikasjon" and up[0]["change"] == "doblet (+100 %)"
    assert up[0]["arrow"] == "↑" and up[0]["dir_text"] == "opp"
    assert down[0]["industry"] == "Ikke-metalliske mineralprodukter" and down[0]["change"] == "−46,7 %"
    assert down[0]["arrow"] == "↓" and down[0]["dir_text"] == "ned"
    blob = json.dumps(card["blocks"])
    assert "color" not in blob and "#3fb950" not in blob and "green" not in blob.lower()


def test_nevnt_in_kilden_hides_when_empty_and_has_no_ticker_links():
    rel, ip, card = _cn_card()
    nv = card["blocks"]["nevnt"]
    assert nv["hidden"] is False
    assert len(nv["sectors"]) == 15
    assert any(s["name"] == "Biler" and "−26,0 %" in s["detail"] for s in nv["sectors"])
    assert nv["exposures"] == []
    empty = N.build_card(rel, ip)
    empty["blocks"]["nevnt"] = {"sectors": [], "exposures": [], "hidden": True}
    rel.industries = []
    card2 = N.build_card(rel, ip, exposures=[])
    assert card2["blocks"]["nevnt"]["hidden"] is True
    # Unverified exposure is dropped
    card3 = N.build_card(rel, ip, exposures=[{"ticker": "ELK.OL", "share": None}])
    assert card3["blocks"]["nevnt"]["exposures"] == []
    h, css = P.html(), P.PAGE_CSS
    assert "tickere.html?sektor=" not in h and "tickere.html?sektor=" not in css
    assert "bra for" not in h.lower() and "dårlig for" not in h.lower()
    assert "Hvem har tjent" not in h


def test_page_layout_390_and_1280_and_button_copy():
    h, css = P.html(), P.PAGE_CSS
    assert "Hva betyr dette?" in h
    assert 'id="ny-fk-sheet"' in h and 'id="ny-fk-slukk"' in h and 'aria-label="Lukk"' in h
    assert "Forklaring fra kildene, ikke en prognose" in h
    assert "data/nbs_industriprofitt.json" in h
    assert "logs/nbs_industriprofitt.json" in h
    btn = css[css.index(".ny-fkbtn{"): css.index(".ny-fkbtn{") + 280]
    assert "height:44px;min-height:44px" in btn
    sheet = css[css.index(".ny-fk-sheet{"): css.index(".ny-fk-sheet{") + 400]
    assert "max-width:390px" in sheet and "height:min(560px, calc(100dvh - 56px))" in sheet
    slukk = css[css.index(".ny-fk-slukk{"): css.index(".ny-fk-slukk{") + 200]
    assert "width:44px;height:44px;min-width:44px;min-height:44px" in slukk
    assert "fkBg.addEventListener('click',()=>closeForklaring())" in h
    assert "font:400 15px/22px" in css and "font:400 13px/18px" in css
    assert "font:600 24px/28px" in css
    assert "height:44px;min-height:44px;max-height:44px" in css
    assert ".ny-fk-nv{" in css and "height:56px;min-height:56px;max-height:56px" in css
    mq = css[css.index("@media(min-width:1280px)"):]
    assert ".ny-fkort{max-width:720px}" in mq or "max-width:720px" in css
    assert "itemMatchesKort" in h and "isWide()" in h
    assert "language model" not in h.lower() and "openai" not in h.lower()


def test_module_has_no_llm_and_no_theme_import():
    src = Path(N.__file__).read_text()
    for name in ("openai", "anthropic", "language_model", "signaltool.themes", "tema_trend", "theme_maps"):
        assert name not in src
    # Parser is deterministic regex, not a model call
    assert "re.search" in src and "parse_bulletin" in src


def test_write_output_and_copy_json(tmp_path, monkeypatch):
    card = _collect_card()
    out = tmp_path / "nbs.json"
    site = tmp_path / "site" / "data" / "nbs_industriprofitt.json"
    N.write_output(card, path=out, site_path=site)
    loaded = json.loads(out.read_text())
    assert loaded["ok"] is True and site.exists()
    monkeypatch.setattr(N, "OUT_PATH", out)
    from signaltool import nyheter as NY
    news = tmp_path / "nyheter.json"
    news.write_text('{"items":[]}\n')
    monkeypatch.setattr(NY, "OUT_PATH", news)
    dest = P.copy_json(tmp_path / "built", src=news)
    assert dest is not None
    assert (tmp_path / "built" / "data" / "nbs_industriprofitt.json").exists()


def test_existing_news_layout_strings_still_hold():
    """Do not break UxBot 17.11 metrics while adding the card."""
    h, css = P.html(), P.PAGE_CSS
    assert P.TABS == ("Alt", "Norge", "Marked", "Verden", "Børsmeldinger")
    assert 'id="ny-slukk"' in h and ">Lukk</button>" in h
    assert "iss!=='-'" in h
    assert "minmax(0,720px)" in css and "padding-bottom:calc(56px + env(safe-area-inset-bottom))" in css


def test_cn_bulletin_2711_ten_figures_and_industries():
    """Lagret kinesisk NBS-kunngjøring 27.11: ti tall parses til riktig verdi og bransje."""
    rel, ip, card = _cn_card()
    assert rel.yoy_month == 20.1
    assert rel.yoy_cum == 16.0
    by = {i.name_no: i for i in rel.industries}
    assert by["Elektronikk og kommunikasjon"].fold == 1.0
    assert by["Elektronikk og kommunikasjon"].orig == "增长1.0倍"
    assert by["Ikke-jernholdige metaller"].pct == 71.7
    assert by["Kull"].pct == 61.4
    assert by["Kjemikalier"].pct == 50.3
    assert by["Ikke-metalliske mineralprodukter"].pct == -46.7
    assert by["Biler"].pct == -26.0
    assert by["Foredling av landbruksvarer"].pct == -19.5
    assert by["Kraft og varme"].pct == -18.4
    up = {r["industry"]: r for r in card["blocks"]["endring"]["up"]}
    assert up["Elektronikk og kommunikasjon"]["change"] == "doblet (+100 %)"
    assert up["Elektronikk og kommunikasjon"]["source_orig"] == "增长1.0倍"


def test_fold_to_pct_is_the_only_allowed_conversion():
    """X倍 → X·100 % er den eneste dokumenterte omregningen. Andre tall utenom kilden feiler."""
    src = "电子行业利润同比增长1.0倍，有色金属冶炼和压延加工业增长71.7%。"
    ok, missing = N.source_has_numbers("doblet (+100 %)", [src], folds=[1.0])
    assert ok is True and missing == []
    ok, missing = N.source_has_numbers("+220 %", ["利润增长2.2倍"], folds=[2.2])
    assert ok is True and missing == []
    ok, missing = N.source_has_numbers("+99,9 %", [src], folds=[1.0])
    assert ok is False and "99,9" in missing
    ok, missing = N.source_has_numbers("doblet (+100 %)", [src], folds=[])
    assert ok is False and "100" in missing
    ok, missing = N.source_has_numbers("+71,7 %", [src], folds=[1.0])
    assert ok is True and missing == []


def test_analbot_test_line_is_verbatim_and_above_source():
    """AnalBots testlinje 27.11 er statisk, ordrett, og ligger nederst over kildelinja."""
    from signaltool import nyheter_page as P
    expected = (
        "Testet 27.11.2026: Å kjøpe bransjene med høyest profittvekst etter NBS-tallet ga ingen "
        "påviselig meravkastning 1–20 dager etter (106 publiseringer, 2017–2026). "
        "Kursene hadde i snitt steget før tallet kom."
    )
    assert P.TEST_LINE == expected
    h, css = P.html(), P.PAGE_CSS
    assert expected in h
    assert expected in Path(P.__file__).read_text()
    assert "ny-fk-test" in h and P.TEST_HREF in h
    assert P.TEST_HREF == "https://github.com/Feelwet/signal-tool/blob/master/tester/nbs_test_2711.md"
    start = h.find("const test=")
    chunk = h[start:start+180]
    assert "ny-fk-test" in chunk and "target=_blank" not in chunk
    block = css[css.index(".ny-fk-test{"): css.index(".ny-fk-test{") + 280]
    assert "min-height:44px" in block and "height:auto" in block
    assert "padding:12px 16px" in block
    assert "font:400 13px/18px" in block
    assert "border-left:3px solid var(--line" in block
    assert "+test+src" in h
    assert "Største økning" in h and "Største fall" in h


def test_forbidden_heading_word_absent_from_card_code_and_tests():
    # Ordet er sammensatt her så det ikke står skrevet i testfilen.
    banned = "bid" + "rag"
    root = Path(__file__).resolve().parents[1]
    files = [
        root / "signaltool" / "nbs_industriprofitt.py",
        root / "signaltool" / "nyheter_page.py",
        Path(__file__),
        root / "logs" / "nbs_industriprofitt.json",
    ]
    for f in files:
        if f.exists():
            blob = f.read_text().lower()
            assert banned not in blob, f"forbudt ord finnes i {f}"


def test_nbs_test_report_has_no_workspace_and_is_published():
    from signaltool.nbs_test_page import SRC, md_to_html
    md = SRC.read_text()
    assert "/workspace" not in md
    assert "FLAG" in md
    html = md_to_html(md)
    assert "/workspace" not in html
    assert "<table>" in html


def test_published_row_uses_nbs_date_from_card_not_build_or_fetch():
    """«Publisert dd.mm» er NBS sin egen dato i kortdataene, aldri bygge- eller hentedato."""
    rel, ip, card = _cn_card()
    assert card["source"]["published"] == "2026-11-27T01:30:00Z"
    assert card["source"]["published_row"] == "Publisert 27.11"
    assert N.published_row(rel.published) == "Publisert 27.11"
    en = N.parse_bulletin(_html("en_bulletin_2026_01_09.html"), url=EN_URL, lang="en")
    assert en.published is not None
    assert N.published_row(en.published) == "Publisert 28.10"
    en_card = N.build_card(en, {})
    assert en_card["source"]["published_row"] == "Publisert 28.10"
    src = Path(N.__file__).read_text()
    start = src.index("def published_row")
    body = src[start: src.index("\ndef ", start + 1)]
    assert "datetime.now" not in body and "generated_at" not in body
    h = P.html()
    # Datoen vises på inngangsraden i lista, ikke inne i kortet
    assert "kort.source.published_row" in h
    assert "ny-fk-inngang-dato" in h
    assert "ny-fk-pub" not in h and "pubRow" not in h
    chunk = h[h.index("function showInngang()"): h.index("function showInngang()") + 280]
    assert "generated_at" not in chunk and "Date.now" not in chunk and "new Date" not in chunk


def test_published_row_hidden_when_nbs_date_missing():
    """Mangler NBS-publiseringsdatoen, vises ikke den faste inngangsraden."""
    assert N.published_row(None) is None
    rel, ip, _ = _cn_card()
    rel.published = None
    ip = dict(ip)
    ip["published"] = None
    card = N.build_card(rel, ip)
    assert card["source"]["published"] is None
    assert card["source"]["published_oslo"] == ""
    assert card["source"]["published_row"] is None
    h = P.html()
    assert "kortOk(kort) && !!(kort.source&&kort.source.published_row)" in h


def test_sheet_390_height_is_min_560_or_100dvh_minus_56_sticky_close():
    css = P.PAGE_CSS
    block = css[css.index(".ny-fk-sheet{"): css.index(".ny-fk-sheet{") + 420]
    assert "bottom:0" in block and "position:fixed" in block
    assert "height:min(560px, calc(100dvh - 56px))" in block
    assert "overflow-y:auto" in block
    head = css[css.index(".ny-fk-head{"): css.index(".ny-fk-head{") + 200]
    assert "position:sticky;top:0" in head
    slukk = css[css.index(".ny-fk-slukk{"): css.index(".ny-fk-slukk{") + 200]
    assert "width:44px;height:44px" in slukk


def test_nevnt_in_kilden_shows_first_six_and_vis_alle_n():
    _, _, card = _cn_card()
    n = len(card["blocks"]["nevnt"]["sectors"]) + len(card["blocks"]["nevnt"]["exposures"])
    assert n > 6
    h, css = P.html(), P.PAGE_CSS
    assert "rows.slice(0,6)" in h and "rows.slice(6)" in h
    assert "Vis alle ('+rows.length+')" in h
    assert 'class="ny-fk-visalle"' in h
    btn = css[css.index(".ny-fk-visalle{"): css.index(".ny-fk-visalle{") + 280]
    assert "min-height:44px" in btn
    # resten er skjult til knappen trykkes
    assert 'class="ny-fk-nv-rest" hidden' in h


def test_forklaring_label_is_ifolge_nbs_and_old_wording_is_gone():
    _, _, card = _cn_card()
    assert card["blocks"]["forklaring"]["label"] == "ifølge NBS"
    h = P.html()
    assert "fk.label||'ifølge NBS'" in h
    banned = "Kildens egen " + "forklaring"
    root = Path(__file__).resolve().parents[1]
    files = [
        root / "signaltool" / "nbs_industriprofitt.py",
        root / "signaltool" / "nyheter_page.py",
        Path(__file__),
        root / "logs" / "nbs_industriprofitt.json",
    ]
    for f in files:
        blob = f.read_text()
        assert banned not in blob, f"forbudt formulering i {f}"
    assert "Kildens forklaring" in h  # overskriften står


def test_nbs_source_link_has_44px_tap_target():
    h, css = P.html(), P.PAGE_CSS
    assert 'class="ny-fk-srclink"' in h
    block = css[css.index(".ny-fk-srclink{"): css.index(".ny-fk-srclink{") + 220]
    assert "min-height:44px" in block
    assert "display:inline-flex" in block or "padding:" in block


def test_fixed_entry_row_on_marked_and_alt_not_inside_card():
    h, css = P.html(), P.PAGE_CSS
    assert P.INNGANG_TITLE == "Forklart: Kinas industriprofitt (NBS)"
    assert P.INNGANG_TITLE in h
    assert "function showInngang()" in h
    assert "tab==='Alt'||tab==='Marked'" in h
    assert "kort.source.published_row" in h
    # ikke inne i kortInner: inngangHtml kalles fra renderList
    inner_start = h.index("function kortInner")
    inner_end = h.index("function isWide()")
    inner = h[inner_start:inner_end]
    assert "ny-fk-inngang" not in inner
    assert "Publisert" not in inner or "published_row" not in inner.split("function kortInner")[-1][:50]
    assert "ny-fk-pub" not in inner
    block = css[css.index(".ny-fk-inngang{"): css.index(".ny-fk-inngang-tittel{")]
    assert "height:56px;min-height:56px;max-height:56px" in block
    assert "border-left:3px solid var(--line" in block
    assert "background:transparent" in block
    assert "#3fb950" not in block and "badge" not in block.lower()
    title = css[css.index(".ny-fk-inngang-tittel{"): css.index(".ny-fk-inngang-tittel{") + 180]
    dato = css[css.index(".ny-fk-inngang-dato{"): css.index(".ny-fk-inngang-dato{") + 180]
    assert "font:400 15px/20px" in title
    assert "font:400 13px/18px" in dato
    assert "bindForklaring" in h and ".ny-fk-inngang" in h
    # knappen og matcheregelen er uendret
    assert 'class="ny-fkbtn" aria-haspopup="dialog">Hva betyr dette?' in h
    assert "function itemMatchesKort" in h


def test_no_horizontal_scroll_rule_in_css():
    css = P.PAGE_CSS
    assert "body.pg-nyheter{overflow-x:hidden}" in css
    sheet = css[css.index(".ny-fk-sheet{"): css.index(".ny-fk-sheet{") + 420]
    assert "overflow-x:hidden" in sheet


def _fixture_nyheter_page(card, items):
    news = {
        "generated_at_utc": "2026-11-27T13:46:00Z",
        "generated_at_oslo": "2026-11-27 14:46 CET",
        "items": items,
        "sources": [{"id": "cnbc", "name": "CNBC", "status": "ok", "last_updated": "14:46"}],
    }
    html = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<style>html,body{{margin:0;overflow-x:hidden}}body{{background:#0d1117;color:#e6edf3}}{P.PAGE_CSS}</style>"
        f'</head><body class="pg-nyheter">{P.html()}</body></html>'
    )
    return html, news, card


def _route_json(pg, news, card):
    def handle(route):
        url = route.request.url
        if "nbs_industriprofitt.json" in url:
            return route.fulfill(status=200, content_type="application/json", body=__import__("json").dumps(card, ensure_ascii=False))
        if "nyheter.json" in url:
            return route.fulfill(status=200, content_type="application/json", body=__import__("json").dumps(news, ensure_ascii=False))
        return route.fallback()
    pg.route("**/*", handle)


@pytest.mark.skipif(
    not (__import__("shutil").which("google-chrome") or __import__("shutil").which("chromium")),
    reason="ingen headless Chrome",
)
def test_headless_scrollWidth_390_and_1280_with_card_and_sheet_open(tmp_path):
    """scrollWidth ≤ viewport ved 390 (ark åpent) og 1280 (kort åpent)."""
    import shutil
    pw = pytest.importorskip("playwright.sync_api")
    _, _, card = _cn_card()
    items = [
        {**CNBC, "source": "CNBC", "source_id": "cnbc", "published_utc": "2026-11-27T02:04:09Z", "section": "Marked", "paywall": False, "issuer": None, "pool": "editorial"},
        {"title": "Annen sak uten nøkkeltall", "url": "https://example.com/other", "source": "CNBC", "source_id": "cnbc", "published_utc": "2026-11-27T08:00:00Z", "section": "Norge", "paywall": False, "issuer": None, "pool": "editorial"},
    ]
    html, news, card = _fixture_nyheter_page(card, items)
    f = tmp_path / "nyheter.html"
    f.write_text(html)
    measured = {}
    with pw.sync_playwright() as p:
        b = p.chromium.launch(channel="chrome" if shutil.which("google-chrome") else None)
        for w, mode in ((390, "sheet"), (1280, "panel")):
            pg = b.new_page(viewport={"width": w, "height": 900})
            _route_json(pg, news, card)
            pg.goto(f.as_uri())
            pg.wait_for_selector(".ny-fk-inngang")
            ing = pg.locator(".ny-fk-inngang")
            box = ing.bounding_box()
            assert box and abs(box["height"] - 56) <= 1, box
            ing.click()
            if mode == "sheet":
                pg.wait_for_selector("#ny-fk-sheet:not([hidden])")
                visalle = pg.locator(".ny-fk-visalle")
                assert visalle.count() == 1
                assert "Vis alle (" in visalle.inner_text()
                assert pg.locator(".ny-fk-nv").locator("visible=true").count() == 6
                assert pg.locator(".ny-fk-nv-rest").get_attribute("hidden") is not None
                visalle.click()
                assert pg.locator(".ny-fk-nv").locator("visible=true").count() > 6
                # kildelenke 44 px
                link = pg.locator(".ny-fk-srclink").first
                lb = link.bounding_box()
                assert lb and lb["height"] >= 44, lb
                sh = pg.locator("#ny-fk-sheet")
                st = sh.evaluate("""e=>{const s=getComputedStyle(e);return {h:s.height,oy:s.overflowY,bottom:s.bottom,pos:s.position}}""")
                # 900-56=844, min(560,844)=560
                assert abs(float(st["h"].replace("px","")) - 560) <= 1, st
                assert st["oy"] == "auto" and st["pos"] == "fixed"
                head = pg.locator(".ny-fk-head").evaluate("e=>getComputedStyle(e).position")
                assert head == "sticky"
            else:
                pg.wait_for_selector(".ny-fkort.open")
            measured[w] = pg.evaluate("()=>{const de=document.documentElement;return {sw:de.scrollWidth,cw:de.clientWidth,iw:window.innerWidth}}")
            pg.close()
        b.close()
    for w, m in measured.items():
        assert m["sw"] <= m["iw"] and m["sw"] <= m["cw"], (w, m)
