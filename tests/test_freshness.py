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
        csv.writer(f).writerows([S.ENTRY_COLS, ["2026-10-27", "SPY", "watch", "760.0", "2026-10-24"]])
    snap = {"date": "2026-10-28", "tickers": [
        {"ticker": "SPY", "category": "watch", "stats": {"close": 769.66, "last_date": "2026-10-27"}},
        {"ticker": "EWZ", "category": "", "stats": {"close": 34.3, "last_date": "2026-10-27"}},
        {"ticker": "DNB.OL", "category": "watch", "stats": {"close": 324.9, "last_date": "2026-10-27"}},
        {"ticker": "ITA", "stats": {}}]}
    assert S.append_entries(snap, {"DNB.OL"}, p) == 2
    snap["tickers"][0]["stats"]["close"] = 770.0
    assert S.append_entries(snap, {"DNB.OL"}, p) == 2                     # ny kjøring samme dag erstatter dagens rader
    rows = list(csv.DictReader(p.open()))
    assert rows[0] == {"date": "2026-10-27", "ticker": "SPY", "category": "watch", "price": "760.0", "price_date": "2026-10-24"}
    assert [(r["date"], r["ticker"], r["price"]) for r in rows[1:]] == [("2026-10-28", "SPY", "770.0"), ("2026-10-28", "EWZ", "34.3")]
    log = tmp_path / "categories.csv"
    with log.open("w", newline="") as f:
        csv.writer(f).writerows([["date", "ticker", "category", "price", "price_date"], ["2026-10-28", "DNB.OL", "watch", "324.9", "2026-10-27"]])
    sin = S.compute(S.load(log, p), "2026-10-28")
    assert sin["EWZ"]["price"] == 34.3 and sin["EWZ"]["price_date"] == "2026-10-27" and sin["DNB.OL"]["price"] == 324.9
    assert S.load(log) == S._read(log)                                    # egen loggsti: ingen sidelogg blandes inn


def test_entry_sidelog_not_in_track_record():
    from signaltool import categories as C
    assert "entry_prices" not in C.LOG_PATH.name and C.LOG_PATH.name == "categories.csv"
