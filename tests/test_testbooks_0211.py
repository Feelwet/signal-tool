"""Bruker 02.11: «Testporteføljer (under måling)» på Signal-boka. Tall fra loggene, usikkerhet synlig, aldri FLAG/«robust»."""
import csv, re
from signaltool import testbooks_page as T
from signaltool import portfolio_books as B
from signaltool import portfolio as P

NCOLS = ["rules_version", "date", "nav", "cash", "n_open", "usdnok", "osebx", "spx", "w_ose", "w_us", "bench_index"]


def _nav(p, book, rows):
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, NCOLS); w.writeheader()
        for d, nav, bi in rows:
            w.writerow({"rules_version": book, "date": d, "nav": nav, "cash": nav, "n_open": 0, "bench_index": bi})


def _gs(p, n=3, flag="FLAG"):
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, ["date", "gs_index", "benchmark", "n_members", "n_no_price", "n_invalid", "flag", "gs_with_tech"]); w.writeheader()
        for i in range(n):
            w.writerow({"date": f"2026-10-0{i + 1}", "gs_index": 100 + i, "benchmark": 100 - i, "n_members": 50, "n_no_price": 1,
                        "n_invalid": 0, "flag": flag if i == 0 else "", "gs_with_tech": 100 + 2 * i})


def _setup(tmp_path):
    _nav(tmp_path / "portfolio_nav.csv", "rules_v1", [("2026-10-29", 1e6, 100), ("2026-10-30", 1e6, 100), ("2026-10-31", 1e6, 100)])
    _nav(tmp_path / "portfolio_hoy_risiko_v1_nav.csv", "hoy_risiko_v1", [("2026-10-29", 1e6, 100), ("2026-10-30", 999600.06, 100), ("2026-10-31", 999599.58, 100.0259)])
    _nav(tmp_path / "portfolio_kontroll_tilfeldig_v1_nav.csv", "kontroll_tilfeldig_v1", [("2026-10-29", 1e6, 100), ("2026-10-30", 999300.21, 100)])
    _gs(tmp_path / "gs.csv")


def _cands(tmp_path):
    P._append(tmp_path / "portfolio_candidates.csv", B.C_COLS, [
        {"date": "2026-10-31", "book_id": "hoy_risiko_v1", "seed": "", "universe_n": 35, "n": 10, "tickers": "A"},
        {"date": "2026-10-31", "book_id": "kontroll_tilfeldig_v1", "seed": 1, "universe_n": 35, "n": 10, "tickers": "B"}])


def test_section_no_charts_no_nav_numbers_0211(tmp_path):
    _setup(tmp_path); _cands(tmp_path)
    snap = {"date": "2026-10-31", "tickers": [{"ticker": "K.OL", "category": "kjop"}, {"ticker": "W.OL", "category": "watch"}]}
    h = T.section_html(tmp_path, tmp_path / "gs.csv", snap=snap)
    txt = re.sub("<[^>]+>", " ", h)
    assert "Testporteføljer (under måling)" in h
    assert "<svg" not in h and "polyline" not in h                               # ingen grafer
    for bad in ("99,96", "99,93", "100,03", "Portefølje", "Referanse 1", "102,00", "104,00", "98,00", "TECH.OL"):
        assert bad not in txt                                                    # ingen NAV-/referansetall, ingen gs_with_tech
    assert txt.count("0 av 30") == 6 and txt.count("0 av 30 lukkede handler, resultater sier ingenting før 30 lukkede.") == 3
    assert "Kjøringer" in txt and " 3 " in txt and " 2 " in txt                   # antall kjøringer fra NAV-loggene
    assert txt.count(" 35 ") == 2 and "Kjøp i dag" in txt                        # univers fra candidates / dagens Kjøp (1)
    assert "Mangler kjøring 31.10" in txt and "fylles ikke inn" in txt
    assert "Skjult til 60 handelsdager (3 av 60)." in txt
    assert "ⓘ" not in h and 'class="tip"' not in h
    for bad in ("FLAG", "robust", "Robust"):
        assert bad not in h


def test_gs_count_from_data_and_capped(tmp_path):
    _gs(tmp_path / "g.csv", n=7)
    assert "(7 av 60)" in T.gs_card(tmp_path / "g.csv")


def test_no_price_shown_in_card(tmp_path):
    _setup(tmp_path)
    P._append(tmp_path / "portfolio_price_missing.csv", P.M_COLS,
              [{"date": "2026-10-30", "book_id": "kontroll_tilfeldig_v1", "ticker": "TECH.OL", "status": "åpen", "valued_at": "", "valued_from": "x"}])
    d = T.book_data("kontroll_tilfeldig_v1", tmp_path)
    assert d["no_price"] == ["TECH.OL"]
    assert "Uten kurs siste kjøring: TECH.OL. Selges første dag det finnes kurs." in T.book_card(d, ["2026-10-29", "2026-10-30"])


def test_card_style_spec():
    c = T.CSS
    assert "background:#1c2430;border:1px solid #3b4757;border-top:3px solid #58a6ff;border-radius:12px" in c
    assert ".tb-k>div{background:#111821" in c


def test_rules_boxes_read_from_config(tmp_path):
    _setup(tmp_path)
    r = T.rules_html(tmp_path, tmp_path / "gs.csv")
    txt = re.sub("<[^>]+>", " ", r)
    H = B.BOOKS["hoy_risiko_v1"]
    assert f"topp {H['top_n']}" in txt and f"Salg etter {H['hold_trading_days']} handelsdager" in txt
    assert "5 % av kontoverdien" in txt and "maks 20 posisjoner" in txt and "0,2 % hver vei, 0,5 %" in txt
    assert "Salgsordre kanselleres aldri" in txt
    assert txt.count("Mangler sluttkurs for en åpen posisjon, står den som «uten kurs» og selges første dag kursen finnes, til den kursen. Innkurs brukes aldri som verdi.") == 2
    assert "Start: 29.10.2026" in txt and "Start: 100 på 01.10.2026" in txt
    assert "1 av 3 dager bygger på lister fra før rangeringsfeltet" in txt          # står i regelboksen
    assert "vises til sammenligning" not in txt and "gs_with_tech" not in r
    assert 'id="regler-hoy_risiko_v1"' in r and 'id="regler-kontroll_tilfeldig_v1"' in r and 'id="regler-gs"' in r
    assert "FLAG" not in r and "robust" not in r.lower()


def test_page_includes_section_and_rules():
    import signaltool.portfolio_page as PP
    src = open(PP.__file__).read()
    assert "TB.section_html(snap=snap)" in src and "TB.rules_html()" in src


def test_no_price_rule_verbatim_in_all_three_boxes():
    import json, signaltool.portfolio_page as PP
    from pathlib import Path
    snap = {"date": "2026-11-02", "tickers": []}
    h = PP.html(snap)
    rx = "Mangler sluttkurs for en åpen posisjon, står den som «uten kurs» og selges første dag kursen finnes, til den kursen. Innkurs brukes aldri som verdi."
    import html as H
    assert H.unescape(h).count(rx) == 3
    for x in PP.RULES_TEXT:                                                     # rules_v1-punktene uendret
        assert H.escape(x) in h
