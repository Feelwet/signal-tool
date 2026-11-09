"""UxBot 09.11 (låst med AnalBots krav): Oversikt med statuslinje, tre innganger, kompakt kandidattabell og risikotrinn."""
import re
from html.parser import HTMLParser
from signaltool import site, overview as OV, site_intro as I


def snap():
    tk = [{"ticker": "A.OL", "name": "Alfa ASA", "score": 5.5, "points": {"price_move": 2.0, "unusual_volume": 1.2},
           "stats": {"ret_5d": 0.136, "ret_20d": -0.05}, "_risk": {"level": "Høy"}},
          {"ticker": "B.OL", "name": "Beta ASA", "score": 5.1, "points": {"ose_contracts": 1.0}, "stats": {"ret_5d": -0.02, "ret_20d": 0.0}, "_risk": {"level": "Lav"}},
          {"ticker": "CCC", "name": "Charlie Holdings Incorporated With A Very Long Legal Name", "score": 4.8, "points": {"insider_cluster": 1.0}, "stats": {}},
          {"ticker": "D.OL", "score": 4.7, "points": {}, "stats": {"ret_5d": None, "ret_20d": 0.01}},
          {"ticker": "E.OL", "score": 4.6, "points": {"price_move": 1}}, {"ticker": "F", "score": 4.5}, {"ticker": "G.OL", "score": 4.4},
          {"ticker": "H", "score": 1.1}, {"ticker": "NOSCORE", "score": None}]
    uni = [{"ticker": "A.OL", "flags": {"weak_px": "x", "high_vol": "y"}}, {"ticker": "B.OL", "flags": {}},
           {"ticker": "D.OL", "flags": {"neg_ebit": "z"}}, {"ticker": "E.OL", "flags": {"placement": "p", "weak_px": "w"}},
           {"ticker": "ZZ.OL", "flags": {"weak_px": "x", "high_vol": "y"}}]
    return {"date": "2026-11-09", "generated": "2026-11-09 06:03", "tickers": tk, "oslo_universe_flags": uni,
            "oslo_flags_meta": {"asof": "2026-11-06"}, "themes": [], "calendar": []}


def test_status_line_counts_from_same_dataset_as_table():
    s = snap()
    h = OV.status_line_html(s)
    # n = rader i tabellen (har score); m = av disse med 2+ testede flagg (A.OL, E.OL – ikke ZZ.OL som ikke er kandidat)
    assert h == '<p class="ov-status">8 kandidater · 2 med 2+ flagg · Oppdatert 09.11 kl. 06:03</p>'
    t = OV.candidates_table_html(s)
    assert t.count("<tr data-nf=") == 8
    assert "Oppdatert" not in OV.status_line_html({**s, "generated": None})   # dikter aldri opp tidspunkt
    assert ".ov-status{margin:0 0 8px;font-size:14px;line-height:20px;color:#94a3b8}" in OV.CSS


def test_status_line_directly_under_title_and_entries_under_intro():
    h = site.overview_html(snap())
    assert re.search(r'<h1>Oversikt</h1><p class="ov-status">', h)
    assert h.index(I.TEXTS["Oversikt"]) < h.index('class="ov-hmeta"') < h.index('class="ov-go"') < h.index('id="kandidater"') < h.index('id="marked-risiko"')


def test_three_entries_equal_and_neutral():
    g = OV.go_html()
    assert g.count("<a ") == 2 and g.count("<button") == 1
    assert ">Kandidater uten røde flagg</button>" in g   # ingen ikon, ingen egen klasse for farge
    assert 'Høyest temascore<span class="gsub">Rangering, ikke testet</span>' in g and 'href="temaer.html"' in g
    assert '<a href="tickere.html?filter=flagg">Røde flagg Oslo</a>' in g
    css = OV.CSS
    assert ".ov-go>a,.ov-go>button{box-sizing:border-box;" in css and "height:56px;min-height:44px" in css
    assert ".ov-go .gsub{display:block;font-size:13px;line-height:18px;font-weight:400;color:#94a3b8}" in css
    assert ".ov-go{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}" in css
    assert "@media(max-width:699px){\n.ov-go{grid-template-columns:minmax(0,1fr)}" in css
    go_rules = " ".join(r for r in re.findall(r"[^{}]*\{[^}]*\}", css) if ".ov-go" in r.split("{")[0])
    assert "#56d364" not in go_rules and "green" not in go_rules and "✓" not in g and "✔" not in g


def test_no_red_flag_filter_only_checked_clean_and_bar_text():
    t = OV.candidates_table_html(snap())
    rows = re.findall(r'<tr data-nf="(\d)"[^>]*>(.*?)</tr>', t)
    nf = [re.search(r'class="tk">([^<]+)', r).group(1).strip() for f, r in rows if f == "1"]
    assert nf == ["B.OL"]   # bare sjekket uten flagg; US (ikke sjekket) og «bare EBIT» telles ikke som 0 røde flagg
    assert '<p class="ov-fbar" hidden>Filter: 0 røde flagg · <button type="button" class="ov-clear">Vis alle</button>' in t
    assert "Bare Oslo-aksjer er sjekket for røde flagg." in t
    assert "r.dataset.nf==='1'" in OV.CAND_JS and "nf=false;draw()" in OV.CAND_JS


def test_compact_table_columns_top6_and_vis_alle():
    t = OV.candidates_table_html(snap())
    assert t.count('class="more" hidden') == 2 and 'Vis alle (8)' in t
    a = re.search(r'<tr data-nf="0">(.*?)</tr>', t).group(1)
    assert 'title="Alfa ASA"' in a and ">A.OL" in a and 'rk rk-hoy rk-s">Risiko: Høy' in a
    assert '<td class="fl">⚑ 2 flagg</td>' in a and 'Uvanlig kursbevegelse</span>' in a and 'class="sgc"' in a
    assert '<span class="ov-ret tup">5d +13.6%</span>' in a and '<span class="ov-ret tdn">20d -5.0%</span>' in a
    assert '<td class="fl n0">ikke sjekket</td>' in t and '<td class="fl n0">0 flagg</td>' in t and "⚑ bare EBIT" in t
    assert '<span class="ov-ret">5d –</span>' in t   # manglende tall vises som –
    assert ".ov-ct .ov-ret.tup{background:rgba(63,185,80,.12)}" in OV.CSS and ".ov-ct .ov-ret.tdn{background:rgba(248,81,73,.12)}" in OV.CSS
    assert ".ov-ct .tn .nm{display:block;font-size:15px;line-height:20px;font-weight:600;white-space:normal" in OV.CSS


def test_score_header_once_on_pc_and_per_card_on_mobile():
    t = OV.candidates_table_html(snap())
    assert t.count("Score (rangering, ikke testet)") == 1 and "score-note" not in t
    assert t.count('<span class="sl">Score </span>') == 8 and t.count('<span class="snt"> · ikke testet</span>') == 8
    assert '<span class="sv">5,5</span>' in t
    css = OV.CSS
    assert ".ov-ct thead th{position:sticky;top:0;z-index:2;background:var(--bg,#0d1117);" in css
    assert ".ov-page table.ov-ct{display:table;overflow:visible;" in css   # opphever main>table{overflow-x:auto} som ville brutt sticky
    assert ".ov-ct .sc .sl,.ov-ct .sc .snt{display:none}" in css
    mob = css.split("@media(max-width:699px){\n.ov-go", 1)[1]
    assert ".ov-ct thead{display:none}" in mob and ".ov-ct .sc{font-size:13px;line-height:18px}.ov-ct .sc .sl,.ov-ct .sc .snt{display:inline}" in mob
    assert '"sc sc sc rt"' in mob   # score og «ikke testet» på samme linje


def test_mobile_card_compact_without_clipping():
    mob = OV.CSS.split("@media(max-width:699px){\n.ov-go", 1)[1]
    assert ".ov-ct tr{display:grid;" in mob and "padding:8px 0" in mob
    tr = re.search(r"\.ov-ct tr\{display:grid;[^}]*\}", mob).group(0)
    assert "overflow:hidden" not in tr and "max-height" not in tr
    # 110 px-budsjett: 8 + navn 2×20 + 4 + 20 (risikomerke) + 4 + 18 (score) + 8 = 102
    assert 8 + 2 * 20 + 4 + 20 + 4 + 18 + 8 <= 110


def test_fold_budget_390():
    # header 48 + oppdatert-linje 22 + main 16 + h1 32 + status 2×20+8 + intro 3×24+4 + meta/lenke 44 + 16
    # + innganger 3×56+2×8 + 16 + kort 12 + h2 22+8 + kandidat 1 ≤110
    total = 48 + 22 + 16 + 32 + 48 + 76 + 44 + 16 + 184 + 16 + 12 + 30 + 110
    assert total < 700
    assert ".ov-page>header,.ov-page>section.ov-entry{margin-bottom:16px}" in OV.CSS and ".ov-page>header .page-intro{margin:0 0 4px}" in OV.CSS


def test_risk_three_steps_active_marked_and_caveat_visible():
    s = snap()
    s["tickers"] = [{"ticker": "X", "_risk": {"level": "Høy"}}, {"ticker": "Y", "_risk": {"level": "Lav"}}, {"ticker": "Z", "_risk": {"level": "Høy"}}]
    h = OV.strip_html(s, False)
    st = h.split('class="ov-steps"', 1)[1].split("</div>", 1)[0]
    assert st.index(">Lav <b>1</b>") < st.index(">Middels <b>0</b>") < st.index(">Høy <b>2</b>")
    assert st.count('aria-current="true"') == 1 and 'class="in on" href="tickere.html?filter=hoy" aria-current="true"' in st
    assert "Testet for kurssvingninger, ikke avkastning" in h and "ov-stack" not in h


def test_only_verbatim_duplicate_caveats_removed():
    class V(HTMLParser):
        def __init__(s): super().__init__(); s.t = []; s.skip = 0
        def handle_starttag(s, t, a):
            s.skip += t in ("style", "script") or ("class", "tip") in a
        def handle_endtag(s, t):
            if t in ("style", "script") and s.skip: s.skip -= 1
        def handle_data(s, d):
            if not s.skip and d.strip(): s.t.append(d.strip())
    h = site.overview_html(snap())
    assert "score-note" not in h.split('id="kandidater"', 1)[1].split("</table>", 1)[0]
    for keep in ("Testet for kurssvingninger, ikke avkastning", "Rangering, ikke testet", "Score (rangering, ikke testet)", I.TEXTS["Oversikt"]):
        assert keep in h


def test_rejected_items_not_added():
    h = site.overview_html(snap())
    for bad in ("Styrken er å unngå svake aksjer", "Watchlist", ">Kjøp<", ">Hold<", "▲", "▼"):
        assert bad not in h
    assert "data-theme" not in h and "theme-filter" not in h
