"""UxBot 27.11: «På lista siden DD.MM» avledes fra loggens sammenhengende rekke, uten hardkodet dato."""
from signaltool import ov_changes as C
from signaltool import overview as OV


def test_since_date_comes_from_the_log_streak():
    by = C.by_date()
    dmap, since = C.days_ctx()
    ds = sorted(by)
    assert dmap and since and set(since) == set(dmap)
    for t, n in dmap.items():
        start = ds[-n]
        assert since[t] == start
        assert all(t in by[d] for d in ds[-n:])
        if n < len(ds):
            assert t not in by[ds[-n - 1]]
        html = C.days_cell(t, dmap, since)
        assert f"På lista siden {C._dm(start)}" in html
        assert "dager på rad" not in html and "fra " not in html
        if n == 1:
            assert 'class="dg-ny">Ny</span>' in html
        else:
            assert "dg-ny" not in html
    assert C.days_cell("__ikke_på_lista__", dmap, since) == '<td class="dg"><span class="dgv">–</span></td>'


def test_overview_header_is_kurs_5d_20d_tickere_unchanged():
    from signaltool import stockrow as SR
    t = OV.candidates_table_html({"tickers": [{"ticker": "A.OL", "score": 1.0, "stats": {"ret_5d": 0.01, "ret_20d": 0.02}}],
                                  "oslo_universe_flags": []})
    assert ">Kurs 5d / 20d<" in t
    # Tickere/sektor-raden beholder den gamle etiketten
    src = open("signaltool/stockrow.py", encoding="utf-8").read()
    assert "Kurs 5d / 20d" not in src
    assert "5d / 20d" in src
