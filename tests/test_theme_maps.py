"""Temakart (AI-kraft, Forsvar) and the experimental Tema-katalysator tag."""
import json
from datetime import date
import numpy as np
import pandas as pd
from signaltool import categories as C, site, theme_maps as TM
from tests.test_categories import cand, two_ctx, TWO, FRESH

TODAY = date(2026, 9, 28)


def _nw(rows):
    return pd.DataFrame([{"published": p, "issuer": i, "title": t, "category": "", "url": f"u{n}"} for n, (p, i, t) in enumerate(rows)])


def test_maps_have_three_orders_catalysts_and_dont():
    for k, M in TM.MAPS.items():
        assert [L["order"] for L in M["layers"]] == ["Første orden", "Andre orden", "Tredje orden"]
        assert M["catalysts"] and M["dont"] and k in TM.THEME_TERMS
    assert set(TM.oslo_tickers("ai_kraft")) >= {"NHY.OL", "ELK.OL", "SCATC.OL", "KIT.OL", "NOD.OL", "KOG.OL"}
    assert set(TM.oslo_tickers("forsvar")) >= {"KOG.OL", "KIT.OL", "NORBT.OL", "NTI.OL", "NUMND.OL"}
    assert TM.maps_for("KIT.OL") == ["ai_kraft", "forsvar"]


def test_theme_keyword_matching():
    nw = _nw([("2026-09-20T08:00:00Z", "KOG", "KONGSBERG signs NOK 4.7 bn order for Joint Strike Missile"),
              ("2026-09-21T08:00:00Z", "KIT", "Kitron hever utsiktene etter rekordresultater innen forsvar"),   # 'rekordresultater' is not 'ordre'
              ("2026-09-22T08:00:00Z", "KIT", "Kitron mottar forsvarskontrakt"),
              ("2026-09-22T08:00:00Z", "NHY", "Frivillig oppsigelse av kraftavtale med datasenter"),              # termination
              ("2026-09-22T08:00:00Z", "SCATC", "Scatec signs power purchase agreement with data center operator"),
              ("2026-08-01T08:00:00Z", "NTI", "Norsk Titanium awarded defense contract"),                          # > 20 days
              ("2026-09-22T08:00:00Z", "KOG", "Share award to employees under defence contract program")])        # share award
    assert [m["title"][:9] for m in TM.theme_announcements(nw, "KOG.OL", "forsvar", TODAY)] == ["KONGSBERG"]
    assert [m["title"] for m in TM.theme_announcements(nw, "KIT.OL", "forsvar", TODAY)] == ["Kitron mottar forsvarskontrakt"]
    assert TM.theme_announcements(nw, "KIT.OL", "ai_kraft", TODAY) == []          # theme terms are map-specific
    assert TM.theme_announcements(nw, "NHY.OL", "ai_kraft", TODAY) == []
    assert len(TM.theme_announcements(nw, "SCATC.OL", "ai_kraft", TODAY)) == 1
    assert TM.theme_announcements(nw, "NTI.OL", "forsvar", TODAY) == []


def test_rel_returns_vs_osebx():
    idx = pd.bdate_range("2026-05-01", periods=80)
    s = pd.Series(np.linspace(100, 110, 80), idx)
    b = pd.Series(np.linspace(100, 120, 80), idx)
    r = TM.rel_returns(s, b)
    assert abs(r["ret60"] - (s.iloc[-1] / s.iloc[-61] - 1)) < 1e-12 and r["rel60"] < 0
    assert TM.rel_returns(s.iloc[:30], b) == {}


def test_tema_catalyst_rules():
    m = [{"date": "2026-09-20", "title": "order", "url": "u"}]
    under = {"ret60": 0.01, "bench60": 0.05, "rel60": -0.04}
    ok, checks = TM.tema_catalyst(m, {"high_vol": "x"}, under)          # yellow flag does not block
    assert ok and all(c[1] for c in checks)
    assert not TM.tema_catalyst(m, {"neg_ebit": "x"}, under)[0]           # red flag blocks
    assert not TM.tema_catalyst(m, {}, {"ret60": 0.2, "bench60": 0.05, "rel60": 0.15})[0]   # already outperformed OSEBX
    assert not TM.tema_catalyst([], {}, under)[0]
    ok, checks = TM.tema_catalyst(m, {}, {})                              # no price data -> unknown, not granted
    assert not ok and checks[2][1] is None and "ingen kursdata" in checks[2][2]


def _prices():
    idx = pd.bdate_range("2025-06-01", periods=300)
    mk = lambda a, b: pd.DataFrame({"Close": np.linspace(a, b, 300), "Volume": 1e6, "High": np.linspace(a, b, 300)}, index=idx)
    return {"OSEBX.OL": mk(100, 130), "KOG.OL": mk(100, 110), "KIT.OL": mk(100, 200), "NHY.OL": mk(50, 55)}


def test_apply_logs_tag_without_counting_toward_kjop(tmp_path, monkeypatch):
    from signaltool import oslo_flags as O
    monkeypatch.setattr(O, "ebit_latest", lambda t, fetch=True, max_age_days=30: None)
    nw = _nw([("2026-09-20T08:00:00Z", "KOG", "KONGSBERG signs NASAMS contract"),
              ("2026-09-20T08:00:00Z", "KIT", "Kitron receives defence order")])
    s = {"date": TODAY.isoformat(), "tickers": [{"ticker": "KOG.OL", "category": "watch", "score": 1, "stats": {"close": 1, "last_date": "x"},
                                                  "cat_benchmark": "OSEBX.OL", "cat_types": {}, "cat_flag_keys": [], "cat_warnings": {}}]}
    TM.apply(s, nw=nw, fetch=False, prices=_prices())
    rows = {r["ticker"]: r for r in s["theme_maps"]["forsvar"]["rows"]}
    assert rows["KOG.OL"]["tema_kat"]                     # contract + no red flag + lagged OSEBX
    assert not rows["KIT.OL"]["tema_kat"]                 # doubled -> beat OSEBX
    assert not rows["NUMND.OL"]["has_data"] and not rows["NUMND.OL"]["tema_kat"]
    assert s["tickers"][0]["temakart"]["tema_kat"] and s["tickers"][0]["temakart"]["maps"] == ["ai_kraft", "forsvar"]
    df = C.append_log(s, tmp_path / "c.csv").set_index("ticker")
    assert df.at["KOG.OL", "types"] == "tema_kat" and df.at["KOG.OL", "n_types"] == 0 and df.at["KOG.OL", "category"] == "watch"
    assert df.at["KIT.OL", "category"] == "tema" and df.at["NHY.OL", "category"] == "tema"
    assert "NUMND.OL" not in df.index                     # no price data -> not logged
    tr = C.track_record(df.reset_index(), {})
    assert "tema" not in tr["cats"] and "tema_kat" in tr["types"]


def test_tag_never_changes_category():
    e = cand(points={"dod_contract": 1.5}, dates={"gov_contract": FRESH})
    base = C.classify(e, two_ctx())
    e["temakart"] = {"maps": ["forsvar"], "tema_kat": True, "checks": {}, "matches": []}
    r = C.classify(e, two_ctx())
    assert r["category"] == base["category"] and "tema_kat" not in r["types"]


def test_map_pages(tmp_path, monkeypatch):
    s = {"date": TODAY.isoformat(), "tickers": []}
    from signaltool import oslo_flags as O
    monkeypatch.setattr(O, "ebit_latest", lambda t, fetch=True, max_age_days=30: None)
    TM.apply(s, nw=_nw([("2026-09-20T08:00:00Z", "KOG", "KONGSBERG signs NASAMS contract")]), fetch=False, prices=_prices())
    s = json.loads(json.dumps(s, default=str))            # as stored in the snapshot
    h = TM.map_html("forsvar", s)
    for txt in ("Første orden", "Andre orden", "Tredje orden", "Katalysatorer å følge", "Hva vi bevisst ikke gjør", "ikke anbefalinger",
                "Tema alene gir aldri Kjøp", "Kontraktsmeldinger alene har tidligere ikke gitt meravkastning", "eksperimentell – testes framover",
                "ingen kursdata", "NUMND.OL", "Nammo", "OSEBX"):
        assert txt in h, txt
    a = TM.map_html("ai_kraft", s)
    assert "Green Mountain" in a and "NEX.PA" in a and "utenfor Oslo" in a and "Statnett" in a
    e = {"ticker": "KOG.OL", "temakart": {"maps": ["forsvar"], "tema_kat": True, "checks": {"forsvar": [["a", True, "x"]]}, "matches": []}}
    assert "eksperimentell – testes framover" in TM.ticker_html(e) and "kart_forsvar.html" in TM.ticker_html(e)
    assert "kart_forsvar.html" in TM.related_html("conflict_defense") and TM.related_html("food_agri") == ""
    assert "tema/kart_ai_kraft.html" in TM.cards_html()


def test_build_writes_map_pages(tmp_path, monkeypatch):
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "data" / "snapshots" / "latest.json"
    if not p.exists():
        return
    s = json.loads(p.read_text())
    monkeypatch.setattr(site, "SITE", tmp_path / "site")
    site.build(s)
    out = tmp_path / "site"
    for M in TM.MAPS.values():
        h = (out / "tema" / f"{M['file']}.html").read_text()
        assert f"Temakart: {M['name']}" in h and 'href="../style.css"' in h
    assert "kart_forsvar.html" in (out / "temaer.html").read_text()
    assert "kart_forsvar.html" in (out / "tema" / "conflict_defense.html").read_text()
