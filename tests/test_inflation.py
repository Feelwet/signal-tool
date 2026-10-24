from datetime import date
from signaltool import inflation as INF

S = {k: [[f"2026-0{i}", 2.0 + i / 10] for i in range(1, 10)] for k in ("NO", "SE", "DK", "EA", "UK", "US")}
FC = {"US": {"points": [["2026", 3.7], ["2027", 2.3]], "measure": "PCE", "source": "Fed SEP (median)", "published": "2026-09-16"}}


def test_block_renders_chart_cards_labels():
    cal = [{"date": "2026-11-05", "time": "10:00", "source": "Norges Bank", "title": "Rentemøte", "kind": "sentralbank"}]
    h = INF.html_block({"series": S, "cards": S, "forecasts": FC, "rates": {"NO": {"rate": 4.5, "date": "2026-10-22", "source": "Norges Bank"}}}, cal, date(2026, 10, 24))
    assert h.count('class="infl-card"') == 6 and h.count('class="cchart"') == 6
    assert "KPI-U, ikke HICP" in h and "seriebrudd" in h and "Ingen fri kilde" in h and "polymarket" not in h.lower()
    assert "2026-11-05" in h and "4,50 %" in h and "HICP 2,9 %" in h and "KPI 2,9 %" in h
    assert "Prognose: Fed SEP (median) sept 2026, PCE" in h and h.count("Ingen prognose</div>") == 5 and "Utdatert" not in h.split("Fed SEP")[1][:80]
    assert h.split('class="infl-svg"')[1].split("</svg>")[0].count("stroke-dasharray=\"5 4\"") == 0   # ingen prognose i felles graf


def test_forecast_stale_after_6_months():
    h = INF.html_block({"series": S, "cards": S, "forecasts": FC}, [], date(2027, 6, 1))
    assert "⏱ Utdatert" in h


def test_block_without_data():
    assert "Mangler data" in INF.html_block(None, [])
