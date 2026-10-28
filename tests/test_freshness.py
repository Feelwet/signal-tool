"""Ferskhet for sluttkurser (AnalBot 28.10): forventet handelsdag, etternølere hentes på nytt, cache-TTL for Oslo-universet,
«Kurs per DD.MM»-tooltip, skjult avkastning ved > 2 handelsdager gammel kurs, innkurs-sidelogg for ikke-loggbare tickere."""
import csv
from datetime import datetime, date
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from signaltool import freshness as F, since as S

OSLO = ZoneInfo("Europe/Oslo")


def _df(days):
    idx = pd.to_datetime(days)
    return pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": np.arange(1, len(days) + 1, dtype=float), "Volume": 100.0}, index=idx)


def test_expected_session_morning_vs_evening():
    morning = datetime(2026, 10, 28, 7, 1, tzinfo=OSLO)
    assert F.expected_session("DNB.OL", morning) == date(2026, 10, 27)
    assert F.expected_session("LMT", morning) == date(2026, 10, 27)          # NY 02:01 -> forrige dag
    assert F.expected_session("DNB.OL", datetime(2026, 10, 28, 17, 0, tzinfo=OSLO)) == date(2026, 10, 28)
    assert F.expected_session("LMT", datetime(2026, 10, 28, 17, 0, tzinfo=OSLO)) == date(2026, 10, 27)   # NY ikke stengt
    assert F.expected_session("DNB.OL", datetime(2026, 10, 26, 7, 0, tzinfo=OSLO)) == date(2026, 10, 23)  # mandag -> fredag
    assert F.expected_session("CL=F", morning) is None and F.expected_session("BA.L", morning) == date(2026, 10, 27)


def test_tdays_old_and_stale():
    assert F.tdays_old("2026-10-26", "2026-10-28") == 2 and not F.is_stale("2026-10-26", "2026-10-28")
    assert F.tdays_old("2026-10-23", "2026-10-28") == 3 and F.is_stale("2026-10-23", "2026-10-28")
    assert F.tdays_old("2026-10-23", "2026-10-26") == 1          # helg teller ikke
    assert F.tdays_old(None, "2026-10-28") is None and not F.is_stale(None, "2026-10-28")


def test_repair_lagging_refetch_adds_missing_day_only_for_laggers():
    now = datetime(2026, 10, 28, 7, 1, tzinfo=OSLO)
    frames = {"DNB.OL": _df(["2026-10-22", "2026-10-23", "2026-10-26"]), "LMT": _df(["2026-10-23", "2026-10-26", "2026-10-27"])}
    asked = {}

    def refetch(tickers, start, now_):
        asked["t"] = sorted(tickers)
        new = _df(["2026-10-26", "2026-10-27"]); new["Close"] = [3.0, 9.5]
        return {"DNB.OL": new}

    info = F.repair_lagging(frames, now, refetch=refetch, meta=lambda t: None)
    assert asked["t"] == ["DNB.OL"] and info["refetched"] == ["DNB.OL"] and not info["still"]
    c = frames["DNB.OL"]["Close"]
    assert str(c.index[-1].date()) == "2026-10-27" and c.iloc[-1] == 9.5 and c.iloc[-2] == 3.0 and len(c) == 4   # eksisterende rader urørt
    assert len(frames["LMT"]) == 3


def test_repair_lagging_meta_only_for_finished_session():
    now = datetime(2026, 10, 28, 7, 1, tzinfo=OSLO)
    frames = {"DNB.OL": _df(["2026-10-23", "2026-10-26"]), "NHY.OL": _df(["2026-10-23", "2026-10-26"])}
    meta = {"DNB.OL": (date(2026, 10, 27), 324.9), "NHY.OL": (date(2026, 10, 28), 80.0)}   # 28.10 er ikke ferdig kl. 07
    info = F.repair_lagging(frames, now, refetch=lambda *a: {}, meta=meta.get)
    assert info["meta"] == ["DNB.OL"] and info["still"] == {"NHY.OL": "2026-10-26"}
    assert frames["DNB.OL"]["Close"].iloc[-1] == 324.9 and str(frames["DNB.OL"].index[-1].date()) == "2026-10-27"
    assert len(frames["NHY.OL"]) == 2
    assert "1 fortsatt bak" in F.summary(info)


def test_markets_download_repairs_lagging(monkeypatch):
    from signaltool.collectors import markets
    from signaltool import http as H
    days = pd.bdate_range("2026-08-01", "2026-10-26")
    frame = pd.concat({"DNB.OL": _df(days)}, axis=1)
    monkeypatch.setattr(H, "yf_download", lambda *a, **k: frame)
    seen = {}

    def fake(frames, *a, **k):
        seen["t"] = sorted(frames)
        frames["DNB.OL"] = F._merge(frames["DNB.OL"], _df(["2026-10-27"]), date(2026, 10, 26))
        return {"lagging": 1, "refetched": ["DNB.OL"], "meta": [], "still": {}}

    monkeypatch.setattr(F, "repair_lagging", fake)
    out = markets.download(["DNB.OL"])
    assert seen["t"] == ["DNB.OL"] and str(out["DNB.OL"].index[-1].date()) == "2026-10-27"
    assert "1 hentet på nytt" in F.summary(markets.LAST_FRESH)


def test_oslo_universe_cache_must_reach_expected_session(monkeypatch, tmp_path):
    from signaltool import oslo_flags as O
    old = {"A.OL": _df(pd.bdate_range("2026-07-01", "2026-10-23"))}
    p = tmp_path / "oslo.pkl"; pd.to_pickle(old, p)
    monkeypatch.setattr(O, "RECENT", tmp_path / "recent.pkl")
    monkeypatch.setattr(F, "expected_session", lambda t, now=None: date(2026, 10, 27))
    calls = []
    fresh = pd.concat({"A.OL": _df(pd.bdate_range("2026-07-01", "2026-10-27"))[["Close", "Volume", "High"]]}, axis=1)
    monkeypatch.setattr(O._http, "yf_download", lambda *a, **k: calls.append(1) or fresh)
    monkeypatch.setattr(O, "universe_tickers", lambda: ["A.OL"])
    d = O._universe_prices(True, date(2026, 10, 28), p)       # 5 dager gammel cache godtas ikke lenger
    assert calls and str(d["A.OL"].index[-1].date()) == "2026-10-27"
    calls.clear()
    pd.to_pickle(d, p)
    d2 = O._universe_prices(True, date(2026, 10, 28), p)      # fersk cache brukes uten nytt kall
    assert not calls and str(d2["A.OL"].index[-1].date()) == "2026-10-27"
    monkeypatch.setattr(O._http, "yf_download", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("429")))
    pd.to_pickle(old, p); (tmp_path / "recent.pkl").unlink(missing_ok=True)
    d3 = O._universe_prices(True, date(2026, 10, 28), p)      # henting feiler: ferskeste cache, ikke tomt
    assert str(d3["A.OL"].index[-1].date()) == "2026-10-23"


S0 = {"since": "2026-10-01", "price": 10.0, "price_date": "2026-09-30", "list_days": 27, "illiquid": False}


def test_tooltip_kurs_per_and_stale_hidden():
    r = S.ret(S0, 11.0, "2026-10-27", {}, "DNB.OL", "2026-10-28")
    c = S.ret_cell(r, S0)
    assert "+10,0 %" in c and "Kurs per 27.10" in c and 'class="ri ri-c"' in c and "ⓘ" in c and 'data-v="0.100000"' in c
    r2 = S.ret(S0, 11.0, "2026-10-26", {}, "DNB.OL", "2026-10-28")       # 2 handelsdager: vises
    assert r2["r"] is not None and "Kurs per 26.10" in S.ret_cell(r2, S0)
    st = S.ret(S0, 11.0, "2026-10-23", {}, "DNB.OL", "2026-10-28")       # 3 handelsdager: skjules
    c = S.ret_cell(st, S0)
    assert st["stale"] and st["r"] is None and "+10,0" not in c and 'class="rv rst">–' in c and "Kurs mangler etter 23.10" in c
    assert 'data-v=""' in c and 'data-stale="1"' in c and "fb-dot" not in c
    assert "+10,0" not in S.line(S0, "", st) and "Kurs mangler etter 23.10" in S.line_rk(S0, "", st)
    assert "#64748b" in S.CSS


def test_no_entry_tooltip():
    c = S.ret_cell(None, {"since": "2026-10-28"})
    assert "–" in c and "Ingen innkurs ennå" in c
    assert "Ingen innkurs ennå" in S.ret_cell(None, None)
    assert "Ingen innkurs ennå" not in S.ret_cell(None, S0)               # innkurs finnes, men ingen sluttkurs


def test_ticker_page_tip_has_date():
    r = S.ret(S0, 11.0, "2026-10-27", {}, "DNB.OL", "2026-10-28")
    assert S.tip_html(S0, r).startswith('<p id="rt-tip" class="rk-tip" hidden>Kurs per 27.10. ')


def test_entry_sidelog_same_day_only(tmp_path):
    p = tmp_path / "entry_prices.csv"
    with p.open("w", newline="") as f:
        csv.writer(f).writerows([S.ENTRY_COLS, ["2026-10-30", "SPY", "watch", "760.0", "2026-10-29"]])
    snap = {"date": "2026-10-31", "tickers": [
        {"ticker": "SPY", "category": "watch", "stats": {"close": 769.66, "last_date": "2026-10-30"}},
        {"ticker": "EWZ", "category": "", "stats": {"close": 34.3, "last_date": "2026-10-30"}},
        {"ticker": "DNB.OL", "category": "watch", "stats": {"close": 324.9, "last_date": "2026-10-30"}},
        {"ticker": "ITA", "stats": {}}]}
    assert S.append_entries(snap, {"DNB.OL"}, p) == 2
    snap["tickers"][0]["stats"]["close"] = 770.0
    assert S.append_entries(snap, {"DNB.OL"}, p) == 2                     # ny kjøring samme dag erstatter dagens rader
    rows = list(csv.DictReader(p.open()))
    assert rows[0] == {"date": "2026-10-30", "ticker": "SPY", "category": "watch", "price": "760.0", "price_date": "2026-10-29"}
    assert [(r["date"], r["ticker"], r["price"]) for r in rows[1:]] == [("2026-10-31", "SPY", "770.0"), ("2026-10-31", "EWZ", "34.3")]
    log = tmp_path / "categories.csv"
    with log.open("w", newline="") as f:
        csv.writer(f).writerows([["date", "ticker", "category", "price", "price_date"], ["2026-10-31", "DNB.OL", "watch", "324.9", "2026-10-30"]])
    sin = S.compute(S.load(log, p), "2026-10-31")
    assert sin["EWZ"]["price"] == 34.3 and sin["EWZ"]["price_date"] == "2026-10-30" and sin["DNB.OL"]["price"] == 324.9
    assert S.load(log) == S._read(log)                                    # egen loggsti: ingen sidelogg blandes inn


def test_entry_sidelog_not_in_track_record():
    from signaltool import categories as C
    assert "entry_prices" not in C.LOG_PATH.name and C.LOG_PATH.name == "categories.csv"


def test_ny_i_dag_replaces_whole_cell_and_sorts_empty():
    s = dict(S0, price_date="2026-10-28")
    r = S.ret(s, 10.0, "2026-10-28", {"OSEBX.OL": {"2026-10-28": 1.0}}, "DNB.OL", "2026-10-28")
    c = S.ret_cell(r, s)
    assert r["new"] and 'data-v=""' in c and 'data-new="1"' in c
    assert '<span class="rnew">Ny i dag</span>' in c and "Avkastning vises fra neste handelsdag" in c and 'class="ri ri-c"' in c
    assert "+0,0" not in c and "rex" not in c and "vs " not in c and "pp" not in c
    assert "Ny i dag" in S.line(s, "", r) and "+0,0" not in S.line(s, "", r)
    assert "Ny i dag" in S.line_rk(s, "", r) and "+0,0" not in S.line_rk(s, "", r)
    assert ".rnew{font-size:11px;color:#94a3b8" in S.CSS
    old = S.ret(S0, 10.0, "2026-10-28", {}, "DNB.OL", "2026-10-28")       # innkurs 30.09: vanlig tall, også +0,0 %
    assert not old["new"] and "+0,0 %" in S.ret_cell(old, S0) and "Ny i dag" not in S.ret_cell(old, S0)


def test_rk_na_cell_tooltip():
    from signaltool import site_risk as RK
    c = RK.cell(None)
    assert ">–</span>" in c and 'title="Risikonivå mangler data"' in c and '<span class="tip">Risikonivå mangler data</span>' in c
    assert 'data-v=""' in c and "Risikonivå mangler data" not in RK.cell({"level": "Lav"})


def test_price_source_log_same_day_only(tmp_path):
    p = tmp_path / "price_source.csv"
    F.SOURCES.clear()
    now = datetime(2026, 10, 28, 7, 1, tzinfo=OSLO)
    fr = {"DNB.OL": _df(["2026-10-23", "2026-10-26"]), "NHY.OL": _df(["2026-10-23", "2026-10-26"]), "LMT": _df(["2026-10-26", "2026-10-27"])}
    F.repair_lagging(fr, now, refetch=lambda *a: {"NHY.OL": _df(["2026-10-27"])}, meta={"DNB.OL": (date(2026, 10, 27), 324.9)}.get)
    assert (F.source_of("DNB.OL"), F.source_of("NHY.OL"), F.source_of("LMT")) == ("meta", "refetch", "daily")
    assert F.source_of("DNB.OL", "universe") == "daily"
    F.write_price_source("2026-10-27", [{"ticker": "DNB.OL", "price_date": "2026-10-27", "close": 324.0, "source": "daily"}], p)
    rows = [{"ticker": t, "price_date": "2026-10-27", "close": 1.0, "source": F.source_of(t)} for t in ("DNB.OL", "NHY.OL")]
    F.write_price_source("2026-10-28", rows, p)
    F.write_price_source("2026-10-28", rows, p)                         # ny kjøring samme dag erstatter
    got = list(csv.DictReader(p.open()))
    assert [(r["date"], r["ticker"], r["source"]) for r in got] == [("2026-10-27", "DNB.OL", "daily"), ("2026-10-28", "DNB.OL", "meta"), ("2026-10-28", "NHY.OL", "refetch")]
    assert list(got[0]) == F.PS_COLS
    F.SOURCES.clear()


def test_workflow_commits_new_logs():
    from pathlib import Path
    wf = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "nightly.yml").read_text()
    files = [l for l in wf.splitlines() if l.strip().startswith("FILES=")][0]
    for f in ("logs/entry_prices.csv", "logs/price_source.csv", "logs/source_fallback.csv"):
        assert f in files


def test_filter_ny_i_dag_last_hidden_when_zero():
    from signaltool import tickerlist as TL
    assert 'data-f="ny"' not in TL.filter_row({"tickers": [{"ticker": "A", "_ret": {"new": False}}]})
    h = TL.filter_row({"tickers": [{"ticker": "A", "_ret": {"new": True}}, {"ticker": "B", "_ret": {"new": True}}, {"ticker": "C", "_ret": None}]})
    assert '<button type="button" data-f="ny" aria-pressed="false">Ny i dag (2)</button></div></div>' in h
    assert "f==='ny'?!!r.querySelector('td.ret-c[data-new]')" in TL.JS and "ny:'Ny i dag'" in TL.JS


def test_popover_trigger_wraps_text_and_name_clamp():
    from signaltool import names as NM
    s = dict(S0, price_date="2026-10-28")
    c = S.ret_cell(S.ret(s, 10.0, "2026-10-28", {}, "DNB.OL", "2026-10-28"), s)
    assert '<span class="ri ri-c" tabindex="0" aria-expanded="false" aria-label="Avkastning vises fra neste handelsdag"><span class="rnew">Ny i dag</span>ⓘ' in c
    st = S.ret_cell(S.ret(S0, 11.0, "2026-10-23", {}, "DNB.OL", "2026-10-28"), S0)
    assert 'aria-label="Kurs mangler etter 23.10"><span class="rv rst">–</span>ⓘ' in st
    assert "max-width:260px;font-size:13px" in S.CSS and "width:max(100%,32px);height:max(100%,32px)" in S.CSS and "riPos" in S.JS
    assert "-webkit-line-clamp:2" in NM.CSS and 'title="DNB Bank ASA"' in NM.cell("DNB.OL", "x.html", "DNB Bank ASA")


def test_data_chip_popover_and_hidden_when_complete(monkeypatch):
    from signaltool import datacov as DC
    monkeypatch.setattr(DC, "coverage", lambda e: {"have": 6, "of": 7, "missing": ["Neste rapport"]})
    h = DC.chip({})
    assert 'class="ri ri-c dci"' in h and "Data 6/7" in h and "6 av 7 grunnfelt finnes. Mangler: Neste rapport." in h
    monkeypatch.setattr(DC, "coverage", lambda e: {"have": 7, "of": 7, "missing": []})
    assert DC.chip({}) == ""


def test_type_sizes_and_updated_line():
    from signaltool import site as SITE
    assert "td.ret-c .rv,td.ret-c .ri.ri-c>.rv{font-size:15px;font-weight:600}" in S.CSS
    assert ".rex{display:block;color:#94a3b8;font-size:12px}" in S.CSS and "#tf-table .since-m{display:block;color:#94a3b8;font-size:12px}" in S.CSS
    html = SITE.page("Tickere", "<p>x</p>", 0, {"generated": "2026-10-28 21:13"})
    assert '<p class="gen gen-line">Oppdatert 28.10 kl. 21:13</p>' in html and ".gen-line{" in SITE.CSS and "font-size:12px" in SITE.CSS


def test_entry_line_shown_price_equals_return_basis():
    import re
    s = S.compute([{"date": "2026-10-28", "ticker": "A", "category": "watch", "price": "109.52", "price_date": "2026-10-27"}], "2026-10-28")["A"]
    s["price"] = 109.52 * 1.0                                            # samme objekt som ret() bruker
    r = S.ret(s, 120.0, "2026-10-28", {}, "A", "2026-10-28")
    m = S.mobile(s, r, "USD")
    shown = float(re.search(r"inn ([\d ]+,\d\d) USD", m).group(1).replace(" ", "").replace(",", "."))
    assert shown == round(s["price"], 2) and abs(r["r"] - (120.0 / shown - 1)) < 1e-4
    assert 'siden 28.10<span class=inn-m><span class="ri ri-c"' in m and "inn 109,52 USD (27.10)" in m and "Sluttkurs 27.10, brukt som innkurs" in m
    c = S.cell(s, "USD")
    assert c.startswith('<td class="since-c" data-v="2026-10-28" data-sort="2026-10-28">siden 28.10<span class=inn-d> · ') and "inn 109,52 USD (27.10)" in c
    assert "inn 109,52 (27.10)" in S.cell(s, "")                         # ukjent valuta: uten valuta
    assert "inn " not in S.cell({"since": "2026-10-28"}) and S.mobile({"since": "2026-10-28"}) == '<span class="since-m">siden 28.10</span>'
    assert "font-variant-numeric:tabular-nums" in S.CSS


def test_entry_deviation_warning():
    s = {"since": "2026-10-20", "price": 100.0, "price_date": "2026-10-17", "dev": 100.0 / 101.2 - 1, "yclose": 101.2}
    h = S.entry_html(s, "NOK")
    assert '<span class="inn-w">⚠</span>' in h and "Innkursen avviker 1,2 % fra Yahoos sluttkurs samme dag (101,20 NOK). Avkastningen er regnet fra den loggede kursen." in h
    assert "⚠" not in S.entry_html(dict(s, dev=0.004, yclose=100.4), "NOK") and "⚠" not in S.entry_html(dict(s, dev=None), "NOK")
    assert "color:#f59e0b;font-size:12px" in S.CSS


def test_entry_check_compares_with_yahoo_close(monkeypatch):
    from signaltool import site as SITE
    snap = {"tickers": [{"ticker": "X.OL", "_since": {"since": "2026-10-20", "price": 100.0, "price_date": "2026-10-17"}},
                        {"ticker": "Y.OL", "_since": {"since": "2026-10-20", "price": None, "price_date": None}}]}
    monkeypatch.setattr(SITE.PC, "download", lambda t: {"X.OL": [("2026-10-16", 99.0), ("2026-10-17", 102.0)]})
    SITE._entry_check(snap)
    s = snap["tickers"][0]["_since"]
    assert s["yclose"] == 102.0 and abs(s["dev"] - (100 / 102 - 1)) < 1e-12 and s["price"] == 100.0   # innkursen endres ikke
    assert "dev" not in snap["tickers"][1]["_since"]
    assert SITE._cur({"decision": {"currency": "GBp"}}) == "GBp" and SITE._cur({}) == ""


def test_log_gap_makes_entry_uncertain_not_new():
    """EWZ: categories 27.09, så ingen loggrad 28.09–27.10; sideloggens 28.10-rad er før SIDE_START og starter ikke periode."""
    rows = [{"date": d, "ticker": "X", "category": "watch", "price": "1", "price_date": d} for d in
            ["2026-09-27"] + [f"2026-{m:02d}-{x:02d}" for m, x in [(9, 28), (9, 29), (9, 30)] + [(10, i) for i in range(1, 29)]]]
    rows.append({"date": "2026-09-27", "ticker": "EWZ", "category": "watch", "price": "36.82", "price_date": "2026-09-25"})
    assert S.uncertain(rows, "EWZ", "2026-10-28") == ("2026-09-28", "2026-10-27")
    s = {"uncertain": ("2026-09-28", "2026-10-27")}
    assert S.ret(s, 33.62, "2026-10-28", {}, "EWZ", "2026-10-28") is None
    c = S.ret_cell(None, s)
    assert "Innkurs usikker, logg mangler 28.09–27.10" in c and "Ny i dag" not in c and 'data-v=""' in c and "Ingen innkurs" not in c
    assert S.cell(s) == '<td class="since-c" data-v="" data-sort="">–</td>' and S.mobile(s) == ""
    assert "Innkurs usikker, logg mangler 28.09–27.10" in S.line(s) and "Innkurs usikker" in S.line_rk(s, "")
    one = rows + [{"date": "2026-10-27", "ticker": "Y", "category": "watch", "price": "1", "price_date": "2026-10-27"}]
    assert S.uncertain(one, "Y", "2026-10-28") is None                    # ingen hull
    assert S.SIDE_START == "2026-10-29"


def test_sidelog_rows_before_side_start_ignored(tmp_path):
    p = tmp_path / "entry_prices.csv"
    with p.open("w", newline="") as f:
        csv.writer(f).writerows([S.ENTRY_COLS, ["2026-10-28", "EWZ", "watch", "33.62", "2026-10-28"], ["2026-10-29", "EWZ", "watch", "34.0", "2026-10-29"]])
    log = tmp_path / "categories.csv"
    with log.open("w", newline="") as f:
        csv.writer(f).writerows([["date", "ticker", "category", "price", "price_date"], ["2026-09-27", "EWZ", "watch", "36.82", "2026-09-25"]]
                                + [[d, "A", "watch", "1", d] for d in ("2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29")])
    rows = S.load(log, p)
    assert ("2026-10-28", "EWZ") not in {(r["date"], r["ticker"]) for r in rows}
    s = S.compute(rows, "2026-10-29")["EWZ"]
    assert s["since"] == "2026-10-29" and s["price"] == 34.0                # ny periode fra neste kjøring, ikke 27.09/36,82
