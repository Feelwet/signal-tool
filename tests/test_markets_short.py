import numpy as np
import pandas as pd
from signaltool.collectors import markets


def _df(n, start=10.0):
    idx = pd.bdate_range("2026-09-24", periods=n)
    return pd.DataFrame({"Close": np.linspace(start, start + 1, n), "Volume": [1000.0] * n}, index=idx)


def test_short_history_gets_close_only(monkeypatch):
    frames = {"NEW.OL": _df(3, 37.0), "OLD.OL": _df(80)}
    multi = pd.concat(frames, axis=1)
    monkeypatch.setattr(markets._http, "yf_download", lambda *a, **k: multi)
    stats, data, msg = markets.collect(["NEW.OL", "OLD.OL", "GONE.OL"])
    assert "NEW.OL" not in data and "OLD.OL" in data
    assert stats.loc["NEW.OL", "close"] == 38.0
    assert stats.loc["NEW.OL", "last_date"] == "2026-09-28"
    assert np.isnan(stats.loc["NEW.OL", "sma50"]) and np.isnan(stats.loc["NEW.OL", "ret_20d"])
    assert "GONE.OL" not in stats.index and "GONE.OL" in msg
