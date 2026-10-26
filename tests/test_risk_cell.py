from signaltool import site_risk as RK


def test_cell_shows_only_level():
    for lv in ("Høy", "Middels", "Lav"):
        h = RK.cell({"level": lv})
        assert f">{lv}</span>" in h and "Risiko:" not in h
    assert ">–</span>" in RK.cell(None) and "Risiko:" not in RK.cell(None)


def test_standalone_chip_keeps_word():
    assert "Risiko: Høy" in RK.chip({"level": "Høy"})
    assert "Risiko: –" in RK.chip(None)
