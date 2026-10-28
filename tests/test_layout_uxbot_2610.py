"""UxBot 26.10: topplinje 48 px, filterknapper 36 px + fade, stjernekolonne 44 px, «Ingen kursdata»-chip."""
from signaltool import site as S, tickerlist as TL, since as SN


def test_gen_short():
    assert S.gen_short("2026-10-26 21:05") == "26.10 21:05"
    assert S.gen_short("2026-10-26T07:30:12") == "26.10 07:30"


def test_top_bar_single_row_48px():
    html = S.page("Tickere", "<p>x</p>", 0, {"generated": "2026-10-26 21:05"})
    assert '</header><p class="gen gen-line">Oppdatert 26.10 kl. 21:05</p>' in html     # UxBot 28.10: under toppbaren
    assert html.count('gen-line') == 1 and 'class="gen"' not in html                       # egen datolinje i sidemenyen er fjernet
    css = S.CSS
    assert "height:48px" in css and "width:40px;height:40px" in css
    assert "header.top .brand{font-weight:700;font-size:16px" in css
    assert "header.top .gen{color:#94a3b8;font-size:12px" in css
    assert "header.top{display:none" not in css                  # vises også på PC


def test_filter_buttons_and_fade():
    h = TL.filter_row({"tickers": []})
    assert h.startswith('<div class="tf-wrap"><div class="tf-row"') and "at-end" in h
    assert "height:36px" in TL.CSS and "padding:0 12px" in TL.CSS and "gap:8px" in TL.CSS
    assert "width:24px" in TL.CSS and "white-space:nowrap" in TL.CSS and ".tf-wrap.at-end::after{display:none}" in TL.CSS


def test_star_column_and_return_column():
    from signaltool import mine as M
    assert "td.mcol{width:44px" in M.CSS and "width:44px;height:44px" in M.CSS
    assert "#tf-table td.ret-c .rv{white-space:nowrap}" in SN.CSS and "width:72px;min-width:72px" not in SN.CSS


def test_nokurs_chip():
    assert TL.nokurs({"ticker": "DIASH.OL", "stats": {}}) == '<span class="nokurs">Ingen kursdata</span>'
    assert TL.nokurs({"ticker": "DIASH.OL"}) != ""
    assert TL.nokurs({"ticker": "EQNR.OL", "stats": {"close": 250.0}}) == ""
    assert ".nokurs{" in TL.CSS and "font-size:11px" in TL.CSS and "color:#64748b;background:#1e293b" in TL.CSS
