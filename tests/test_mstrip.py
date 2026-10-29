import re
from datetime import date, datetime, timedelta, timezone
import pandas as pd
import signaltool.mstrip as M
from signaltool.collectors import mstrip as C

NOW = datetime(2026, 10, 29, 6, 0, tzinfo=timezone.utc)


def _ser(last: date, n=25, start=100.0, step=1.0, weekdays=True):
    ds, d = [], last
    while len(ds) < n:
        if not weekdays or d.weekday() < 5:
            ds.append(d)
        d -= timedelta(days=1)
    ds = ds[::-1]
    return {"dates": [x.isoformat() for x in ds], "close": [start + i * step for i in range(n)]}


def test_no_data_never_invents_price():
    h = M.html({"mstrip": {}}, NOW)
    assert h.count("Ingen kursdata") == 2 and "%" not in h
    assert M.html({}, NOW).count("Ingen kursdata") == 2


def test_titles_tips_and_lines():
    snap = {"mstrip": {"BZ=F": _ser(date(2026, 10, 28)), "BTC-USD": _ser(date(2026, 10, 28), weekdays=False, start=80000, step=-100)}}
    h = M.html(snap, NOW)
    assert "Brent-olje, futures (USD/fat)" in h and "Bitcoin (USD)" in h
    assert "Sluttkurs nærmeste future (BZ=F) · Yahoo · 28.10" in h
    assert "Dagskurs kl. 00:00 UTC · Yahoo · 29.10" in h and "Yahoo · 29.10 kl. 00:00 UTC" in h
    assert re.search(r'class="msu">1d \+0,8\u00a0%', h) and re.search(r'class="msd">1d −0,1\u00a0%', h)
    assert "20d" in h and "eldre kurs" not in h
    for w in ("poeng", "Poeng", "signal", "Signal", "kjøp", "Kjøp", "selg", "sterk", "svak"):
        assert w not in re.sub(r"<[^>]+>", " ", h)


def test_brent_roll_day_shows_dash():
    s = _ser(date(2026, 11, 2), n=25)
    h = M.field(M.FIELDS[0], {"BZ=F": s}, datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc))
    assert '1d –</span>' in h and "Kontraktsbytte i dag" in h
    assert M.roll_day(date(2026, 10, 30), date(2026, 11, 2)) and not M.roll_day(date(2026, 10, 28), date(2026, 10, 29))


def test_freshness_warning():
    old = {"BZ=F": _ser(date(2026, 10, 26)), "BTC-USD": _ser(date(2026, 10, 26), weekdays=False)}
    h = M.html({"mstrip": old}, NOW)
    assert h.count("⚠ eldre kurs") == 2
    ok = {"BTC-USD": _ser(date(2026, 10, 28), weekdays=False)}
    assert "eldre kurs" not in M.field(M.FIELDS[1], ok, NOW)


def test_zero_change_grey():
    s = {"dates": ["2026-10-27", "2026-10-28"], "close": [50.0, 50.0]}
    h = M.field(M.FIELDS[0], {"BZ=F": s}, NOW)
    assert 'class="ms0">1d 0,0\u00a0%' in h and 'class="ms0">20d –' in h


def test_collector_drops_unfinished_bars(monkeypatch):
    idx = pd.to_datetime(["2026-10-27", "2026-10-28", "2026-10-29"])
    def fake(sym, **kw):
        return pd.DataFrame({"Close": [1.0, 2.0, 3.0]}, index=idx)
    monkeypatch.setattr(C._http, "yf_download", fake)
    d, st = C.collect(datetime(2026, 10, 29, 5, 17, tzinfo=timezone.utc))
    assert d["BTC-USD"]["dates"][-1] == "2026-10-28" and d["BZ=F"]["dates"][-1] == "2026-10-28"
    d2, _ = C.collect(datetime(2026, 10, 29, 23, 30, tzinfo=timezone.utc))
    assert d2["BZ=F"]["dates"][-1] == "2026-10-29" and d2["BTC-USD"]["dates"][-1] == "2026-10-28"


def test_collector_failure_gives_empty(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("yahoo nede")
    monkeypatch.setattr(C._http, "yf_download", boom)
    d, _ = C.collect(NOW)
    assert d["BZ=F"]["close"] == [] and M.html({"mstrip": d}, NOW).count("Ingen kursdata") == 2


def test_css_sizes():
    assert ".ms-p{font-size:20px" in M.CSS and ".ms-c{font-size:13px" in M.CSS and ".ms-s{font-size:11px" in M.CSS
    assert ".ms-f{box-sizing:border-box;width:200px" in M.CSS and ".msu{color:#22c55e}.msd{color:#ef4444}" in M.CSS
