"""Nattlig kildekontroll (26.10): dekning per kilde/felt, simulert kildefeil -> siste gode + source_fallback=1,
holdes utenfor treffrater, GS-indeks og læring, «Data fra DD.MM» på siden. Pluss UxBots stjerne-CSS."""
import csv, json
import pandas as pd
from signaltool import source_health as SH, decision as D, site_sources as SS


def _t(t, close=10.0, sector="Energy"):
    return {"ticker": t, "stats": {"close": close, "sma50": close, "last_date": "2026-10-23"},
            "decision": {"sector": sector, "marketCap": 1e9, "trailingPE": 9.0, "numberOfAnalystOpinions": 3}}


def test_healthy_saves_lastgood(tmp_path):
    p = tmp_path / "lg.json"
    snap = {"date": "2026-10-23", "tickers": [_t("AAA.OL", 50.0), _t("BBB", 7.0)]}
    st = {}
    r = SH.check(snap, st, path=p, force=set())
    assert r["failed"] == [] and all(x["pct"] == 1.0 for f in r["before"].values() for x in f.values())
    assert json.loads(p.read_text())[SH.PRICE]["AAA.OL"]["vals"]["close"] == 50.0
    assert all(v.startswith("ok") for v in st.values())


def test_simulated_price_failure_uses_lastgood_and_flags(tmp_path, monkeypatch):
    p, side = tmp_path / "lg.json", tmp_path / "sf.csv"
    SH.check({"date": "2026-10-23", "tickers": [_t("AAA.OL", 50.0), _t("BBB", 7.0)]}, {}, path=p, force=set())
    snap = {"date": "2026-10-26", "tickers": [_t("AAA.OL", 51.0), _t("BBB", 7.5), _t("NEW", 3.0)]}
    st = {}
    r = SH.check(snap, st, path=p, force={SH.PRICE})          # simulert kildefeil
    assert r["failed"] == [SH.PRICE]
    assert r["before"][SH.PRICE]["close"]["pct"] == 0.0
    assert r["after"][SH.PRICE]["close"]["have"] == 2           # NEW har ingen siste gode -> forblir tom (ikke oppdiktet)
    a = snap["tickers"][0]
    assert a["stats"]["close"] == 50.0 and a["source_fallback"] == {"source": SH.PRICE, "date": "2026-10-23"}
    assert "close" not in snap["tickers"][2]["stats"] and not snap["tickers"][2].get("source_fallback")
    assert st[f"Kildekontroll: {SH.PRICE} (≥ 50 % per felt)"].startswith("FAILED")
    # siste gode ble ikke overskrevet av den feilende kjøringen
    assert json.loads(p.read_text())[SH.PRICE]["AAA.OL"]["date"] == "2026-10-23"
    # sidelogg med source_fallback=1, og «Data fra DD.MM» på siden
    assert SH.append_rows(snap, side) == 2
    assert SH.excluded(side) == {("2026-10-26", "AAA.OL"), ("2026-10-26", "BBB")}
    assert D.fb_text(a) == "Data fra 23.10 (Kurs (Yahoo) feilet i dag)"
    assert "Data fra 23.10" in SS.fb_line(a) and "Data fra 23.10" in SS.fb_dot(a)
    # treffrater: raden holdes utenfor
    monkeypatch.setattr(SH, "SIDELOG", side)
    from signaltool import categories as C
    df = pd.DataFrame([{"date": "2026-10-26", "ticker": "AAA.OL", "category": "kjop"}, {"date": "2026-10-26", "ticker": "CCC.OL", "category": "kjop"}])
    assert C.track_record(df, {})["n_log_rows"] == 1


def test_lastgood_too_old_not_used(tmp_path):
    p = tmp_path / "lg.json"
    SH.check({"date": "2026-10-01", "tickers": [_t("AAA.OL")]}, {}, path=p, force=set())
    snap = {"date": "2026-10-26", "tickers": [_t("AAA.OL", 51.0)]}
    SH.check(snap, {}, path=p, force={SH.PRICE})
    assert "close" not in snap["tickers"][0]["stats"] and not snap["tickers"][0].get("source_fallback")


def test_side_log_keeps_closed_dates(tmp_path):
    side = tmp_path / "sf.csv"
    side.write_text("date,ticker,source,fallback_date,source_fallback\n2026-10-22,OLD,Kurs (Yahoo),2026-10-21,1\n")
    before = side.read_text().splitlines()[1]
    snap = {"date": "2026-10-26", "tickers": [dict(_t("X"), source_fallback={"source": SH.PRICE, "date": "2026-10-23"})]}
    SH.append_rows(snap, side)
    SH.append_rows(snap, side)   # samme dag igjen: erstattes, ikke dobles
    lines = side.read_text().splitlines()
    assert lines[1] == before and len(lines) == 3


def test_gs_index_and_learning_exclude_fallback(tmp_path, monkeypatch):
    from signaltool import gs_index as G, learnloop as L
    cat = tmp_path / "c.csv"
    cat.write_text("date,ticker,category,price,price_date,benchmark,score,n_types,types,flags,rangert\n"
                   "2026-10-26,AAA.OL,kjop,1,2026-10-26,,1,1,,,1\n2026-10-26,BBB,hold,1,2026-10-26,,1,1,,,1\n")
    side = tmp_path / "sf.csv"
    side.write_text("date,ticker,source,fallback_date,source_fallback\n2026-10-26,AAA.OL,Kurs (Yahoo),2026-10-23,1\n")
    monkeypatch.setattr(SH, "SIDELOG", side)
    assert [r["ticker"] for r in G.load_rows(cat, None)] == ["BBB"]
    raw = tmp_path / "raw.csv"
    with raw.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=L.RAW_COLS)
        w.writeheader()
        for d in pd.bdate_range("2026-07-01", "2026-10-26"):
            w.writerow({"date": d.date().isoformat(), "ticker": "FB", "types": "x", "is_canonical": "true", "source_fallback": 1})
    assert L.completed_periods(raw) == (0, 0)


def test_star_css_present():
    from signaltool import site
    assert "#tf-table .card{padding-right:8px}" in site.STAR_CSS and "overflow-x:visible" in site.STAR_CSS
    assert "#tf-table td.mcol{text-align:center}" in site.STAR_CSS
