

def test_cn_lpr_and_de_bundesbank_label():
    from datetime import date
    from signaltool import inflation as I
    import json, pathlib
    F = json.loads(pathlib.Path(I.__file__).with_name("inflation_forecasts.json").read_text())
    lab, pub, old = I._fc_label(F["DE"], date(2026, 10, 25))
    assert lab.startswith("Bundesbank juni 2026") and not old
    assert I._fc_label(F["DE"], date(2027, 1, 20))[2]  # >6 mnd -> Utdatert
    src = pathlib.Path(I.__file__).read_text()
    assert "LPR settes den 20. hver måned" in src and "<span class=mut>ingen fri kilde</span>" in src and "Rente: ingen fri kilde" not in src
    assert "ingen faste rentemøter" not in src


def test_cn_label_right_and_big_neutral():
    import pathlib
    from signaltool import inflation as I
    src = pathlib.Path(I.__file__).read_text()
    assert 'text-anchor="end">{_E(tlabel)}' in src
    assert '<div class="big" style="color' not in src


def test_combined_chart_lines_clickable():
    import pathlib
    from signaltool import inflation as I
    src = pathlib.Path(I.__file__).read_text()
    assert 'class="hit"' in src and 'stroke="transparent" stroke-width="14"' in src
    assert "pointer-events:stroke;cursor:pointer" in src
    assert "if(h)pick(h.dataset.c,e.shiftKey)" in src and "pick(c,e.shiftKey)" in src
    assert "Vis alle" in src and "searchParams.set('land'" in src and ">Bare</button>" in src and "'.15'" in src
