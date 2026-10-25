from datetime import date
from signaltool import inflation as INF

S = {k: [[f"2026-0{i}", 2.0 + i / 10] for i in range(1, 10)] for k in ("NO", "SE", "DK", "EA", "UK", "US")}
FC = {"US": {"points": [["2026", 3.7], ["2027", 2.3]], "measure": "PCE", "source": "Fed SEP (median)", "published": "2026-09-16"}}


def test_block_renders_chart_cards_labels():
    cal = [{"date": "2026-11-05", "time": "10:00", "source": "Norges Bank", "title": "Rentemøte", "kind": "sentralbank"}]
    h = INF.html_block({"series": S, "cards": S, "forecasts": FC, "rates": {"NO": {"rate": 4.5, "date": "2026-10-22", "source": "Norges Bank"}}}, cal, date(2026, 10, 24))
    assert h.count('class="infl-card"') == 8 and h.count('class="cchart"') == 6
    assert "KPI-U, ikke HICP" in h and "seriebrudd" in h and "Ingen fri kilde" in h and "polymarket" not in h.lower()
    assert "2026-11-05" in h and "4,50 %" in h and "HICP 2,9 %" in h and "KPI 2,9 %" in h
    assert "Prognose: Fed SEP (median) sept 2026, PCE" in h and h.count("Ingen prognose</div>") == 7 and "Utdatert" not in h.split("Fed SEP")[1][:80]
    assert h.split('class="infl-svg"')[1].split("</svg>")[0].count("stroke-dasharray=\"5 4\"") == 0   # ingen prognose i felles graf


def test_forecast_stale_after_6_months():
    h = INF.html_block({"series": S, "cards": S, "forecasts": FC}, [], date(2027, 6, 1))
    assert "⏱ Utdatert" in h


def test_block_without_data():
    assert "Mangler data" in INF.html_block(None, [])


def test_forecast_file_has_provenance():
    fc = INF.load_forecasts()
    assert set(fc) >= {"NO", "SE", "EA", "DK", "UK"}
    for k, f in fc.items():
        assert f["url"].startswith("https://") and f["source"] and f["published"][:2] == "20" and f["measure"] and f["points"]
        assert all(isinstance(v, float) for _, v in f["points"])


def test_china_card_grey_imf_target_and_no_meetings():
    from datetime import date
    from signaltool import inflation as I
    hist = [[f"2025-{m:02d}", -0.5 + m * 0.1] for m in range(1, 13)]
    fc = {"source": "IMF WEO", "measure": "KPI årssnitt", "kind": "annual", "published": "2026-10-13",
          "url": "https://www.imf.org/x", "grey": True, "points": [["2026", 1.0], ["2027", 1.4]]}
    h = I.html_block({"series": {"CN": hist}, "cards": {"CN": hist}, "forecasts": {"CN": fc}, "rates": {}, "stale": ["CN"]}, [], date(2026, 10, 25))
    assert "KPI (NBS), ikke HICP" in h and "ikke sentralbank" in h and 'stroke="#8b949e" stroke-width="1.8" stroke-dasharray="5 4"' in h
    assert "regjeringens mål ~2 %" in h and "english.www.gov.cn" in h and "LPR settes den 20. hver måned" in h and "Rente: ingen fri kilde" in h and "⏱ Utdatert" in h
