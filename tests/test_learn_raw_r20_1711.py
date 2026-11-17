"""AnalBot 17.11: r20 i learn_raw = ret_20d i snapshot per ticker og NAV-dato (toleranse 1e-4).

Dekker NAV-dato 2026-11-17 med siste lukkede bar 16.11, for SCANA.OL og BONHR.OL i fiksturen
(SCANA: sluttkurs 16.11 1,420 mot 19.10 1,400 = +0,0143). Historiske snapshot-filer etter 28.09
ligger ikke i repoet (data/snapshots er gitignorert), så testen sammenligner ikke logs/learn_raw.csv
med arkiverte snapshot. Forventet r20 kommer fra collectors.markets.ticker_stats på samme kursramme
som snapshot, ikke fra learn_raw-loggen.
"""
import csv
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from signaltool import learnloop as L
from signaltool.collectors.markets import ticker_stats

OSLO = ZoneInfo("Europe/Oslo")
NAV = "2026-11-17"
LAST = "2026-11-16"
TOL = 1e-4


def at(y, m, d, h, mi):
    return dt.datetime(y, m, d, h, mi, tzinfo=OSLO)


def _frame(overrides: dict, last=LAST, n=70) -> pd.DataFrame:
    days = [str(d.date()) for d in pd.bdate_range(end=last, periods=n)]
    close = {d: 1.0 for d in days}
    close.update(overrides)
    idx = pd.to_datetime(days)
    return pd.DataFrame({"Close": [close[str(d.date())] for d in idx], "Volume": [10_000] * len(idx)}, index=idx)


def _scana_full():
    # AnalBot 17.11: snapshot 16.11 1,420 mot 19.10 1,400; etternøler-baren 13.11 1,415 mot 16.10 1,415.
    return _frame({"2026-10-16": 1.415, "2026-10-19": 1.400, "2026-11-13": 1.415, "2026-11-16": 1.420})


def _bonhr_full():
    return _frame({"2026-10-16": 294.0, "2026-10-19": 290.0, "2026-11-13": 294.0, "2026-11-16": 296.0})


def test_learn_raw_r20_matches_snapshot_per_ticker_and_nav_date(tmp_path, monkeypatch):
    frames = {"SCANA.OL": _scana_full(), "BONHR.OL": _bonhr_full()}
    expected = {t: float(ticker_stats(df)["ret_20d"]) for t, df in frames.items()}
    assert abs(expected["SCANA.OL"] - (1.420 / 1.400 - 1)) < 1e-9
    assert ticker_stats(frames["SCANA.OL"])["last_date"] == LAST

    # Etternøler-henting uten freshness/meta (slik _closes gjorde 17.11) ville stoppet på 13.11 og gitt r20=0 for SCANA.
    lagging = {t: {str(k.date()): float(v) for k, v in df.loc[: "2026-11-13", "Close"].items()} for t, df in frames.items()}
    monkeypatch.setattr(L, "_closes", lambda tickers, period="2y": {t: dict(lagging[t]) for t in tickers if t in lagging})
    for n in ("RAW", "EXITS", "DQ"):
        monkeypatch.setattr(L, n, tmp_path / f"{n}.csv")
    monkeypatch.setattr(L, "CAT_LOG", tmp_path / "c.csv")

    snap = {"date": NAV, "generated": "2026-11-17 08:03", "tickers": [
        {"ticker": "SCANA.OL", "score": 3.0, "points": {"ose_contracts": 3.0},
         "stats": {"close": 1.42, "last_date": LAST, "ret_20d": expected["SCANA.OL"]}},
        {"ticker": "BONHR.OL", "score": 2.0, "points": {"x": 1.0},
         "stats": {"close": 296.0, "last_date": LAST, "ret_20d": expected["BONHR.OL"]}},
    ]}
    L.record(snap, snap["tickers"], NAV, frames=frames, now=at(2026, 11, 17, 8, 3))
    raw = {r["ticker"]: r for r in csv.DictReader((tmp_path / "RAW.csv").open())}

    for t, exp in expected.items():
        row = raw[t]
        assert row["date"] == NAV and row["close_date"] == LAST, f"{t}: close_date={row['close_date']}"
        got = float(row["r20"])
        # forventet verdi fra snapshot-statistikk (ticker_stats), ikke fra learn_raw
        assert abs(got - exp) < TOL, f"{t}: learn_raw r20={got} snapshot ret_20d={exp}"
    assert raw["SCANA.OL"]["close"] == "1.42"
    assert abs(float(raw["SCANA.OL"]["r20"]) - 0.0143) < TOL

    src = Path("signaltool/learnloop.py").read_text()
    assert "frames=mdata" in Path("signaltool/pipeline.py").read_text()
    assert "markets.download" in src and "Historiske learn_raw-rader rettes ikke" in src
