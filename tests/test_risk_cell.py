from signaltool import site_risk as RK


def test_cell_shows_only_level():
    for lv in ("Høy", "Middels", "Lav"):
        h = RK.cell({"level": lv})
        assert f">{lv}</span>" in h and "Risiko:" not in h
    assert ">–</span>" in RK.cell(None) and "Risiko:" not in RK.cell(None)


def test_standalone_chip_keeps_word():
    assert "Risiko: Høy" in RK.chip({"level": "Høy"})
    assert "Risiko: –" in RK.chip(None)


def test_merged_risk_score_cell_390():
    """UxBot 29.10: 390 px slår sammen «Risiko» og «Poeng» (brikke over poengboks, 4 px, 68 px); 1280 uendret."""
    from signaltool import site as S
    sc = '<span class="score hot">6.30</span>'
    h = RK.cell({"level": "Lav"}, sc)
    assert h.index(">Lav</span>") < h.index('<span class="rkp-s">' + sc)
    assert '<span class="rkp-s">' in RK.cell(None, sc)
    assert "rkp-s" not in RK.cell({"level": "Lav"})
    assert '<span class="rkp-m"> · Poeng <button' in S.TICKER_HEAD and 'Risiko<span class="rk-ev">' in S.TICKER_HEAD and '<th class="pt-h">Poeng <button' in S.TICKER_HEAD and S.TICKER_HEAD.count("Rangering, ikke testet") == 2   # GSbot 29.10: ⓘ ved poengsum
    css = RK.CSS
    assert ".rkp-m,.rkp-s{display:none}" in css
    mob = css[css.index("@media(max-width:599px){#tf-table th.pt-h"):]
    assert "#tf-table th.pt-h,#tf-table td.pt-c{display:none}" in mob and "width:68px" in mob and "margin-top:4px" in mob


def test_hover_popover_fine_pointer_only():
    """Brukeren 29.10: ⓘ åpnes ved hover kun på (hover:hover) and (pointer:fine); tap-oppførselen er urørt."""
    js = RK.JS
    assert "matchMedia('(hover:hover) and (pointer:fine)')" in js and "pointerType==='mouse'" in js
    assert "pointerenter" in js and "pointerleave" in js and "'.ri,.rk-i,.rt-i'" in js
    assert js.count("window.__stHov") == 2
