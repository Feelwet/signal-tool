"""«Data X/7»-chip og «Ikke tilgjengelig ennå»/«Ikke relevant» på tickersiden."""
from signaltool import datacov as DC

FULL = {"ticker": "ABC", "stats": {"close": 10.0, "sma50": 9.0},
        "decision": {"sector": "Energy", "marketCap": 2e9, "trailingPE": 12.0, "next_earnings": "2026-11-05", "numberOfAnalystOpinions": 7}}


def test_full_has_no_chip():
    assert DC.coverage(FULL) == {"etf": False, "have": 7, "of": 7, "missing": []}
    assert DC.chip(FULL) == ""


def test_missing_fields_chip_and_tooltip():
    e = {**FULL, "decision": {"sector": "Energy", "marketCap": 2e9}}
    c = DC.coverage(e)
    assert (c["have"], c["of"]) == (4, 7) and c["missing"] == ["P/E", "Neste rapport", "Analytikere"]
    h = DC.chip(e)
    assert "Data 4/7" in h and 'class="dchip"' in h and "Mangler: P/E, Neste rapport, Analytikere" in h


def test_etf_measured_out_of_two():
    e = {"ticker": "SPY", "stats": {"close": 600.0, "sma50": 590.0}, "decision": {}}
    assert DC.coverage(e)["of"] == 2 and DC.chip(e) == ""
    e2 = {"ticker": "SPY", "stats": {"close": 600.0}, "decision": {}}
    assert "Data 1/2" in DC.chip(e2)
    card = DC.card(e)
    assert card.count(DC.NOT_REL) == 5 and DC.NA not in card


def test_card_never_zero_or_empty():
    e = {"ticker": "X", "stats": {}, "decision": {"trailingPE": float("nan"), "sector": " "}}
    card = DC.card(e)
    assert card.count(DC.NA) == 7 and "<td></td>" not in card and ">0<" not in card
    assert DC.coverage(e)["have"] == 0
