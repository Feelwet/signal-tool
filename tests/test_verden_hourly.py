"""04.11: timesjobb for «Verden nå» – dobbel ventetid ved 429, GKG først, inkrementell sammenslåing."""
from datetime import datetime, timedelta, timezone

import pytest

from signaltool import verden as V

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
T1 = "Russia Ukraine war ceasefire talks"   # to nøkkelord -> tema


def _it(title, url, h, kilde="GDELT"):
    return {"tittel": title, "url": url, "kilde": kilde, "publisert": NOW - timedelta(hours=h)}


class _R:
    def __init__(self, code, text="Too many"):
        self.status_code, self.text = code, text


def test_backoff_doubles_and_counts_429(monkeypatch):
    import requests
    from signaltool import http
    monkeypatch.setattr(http, "_throttle", lambda *_: None)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _R(429))
    waits = []
    before = V.GDELT_STATS["429"]
    with pytest.raises(RuntimeError):
        V._gdelt_doc(sleep=waits.append)
    assert waits == list(V.GDELT_WAITS)
    assert all(b == 2 * a for a, b in zip(waits, waits[1:])) and max(waits) <= 180
    assert V.GDELT_STATS["429"] - before == len(V.GDELT_WAITS) + 1


def test_gkg_first_doc_only_on_failure():
    calls = []
    assert V._gdelt(doc=lambda: calls.append("doc") or [], gkg=lambda: [1]) == [1] and calls == []
    def bad():
        raise RuntimeError("x")
    assert V._gdelt(doc=lambda: calls.append("doc") or [2], gkg=bad) == [2] and calls == ["doc"]


def test_gdelt_skipped_without_failing():
    def bad():
        raise RuntimeError("429")
    data, _ = V.collect(now=NOW, fetch={"GDELT": bad, "ECB": lambda: []}, state={})
    assert data["kilder_status"]["GDELT"].startswith("hoppet over")


def test_gkg_file_times_incremental():
    t0 = datetime(2026, 11, 4, 11, 45, tzinfo=timezone.utc)
    assert len(V.gkg_file_times(t0, None)) == V.GDELT_GKG_FILES
    assert V.gkg_file_times(t0, t0 - timedelta(hours=1)) == [t0 - timedelta(minutes=15 * k) for k in range(4)]
    assert V.gkg_file_times(t0, t0) == []
    assert len(V.gkg_file_times(t0, t0 - timedelta(hours=10))) == V.GDELT_GKG_FILES


def test_incremental_merge_keeps_old_drops_expired_dedups():
    state = {}
    V.collect(now=NOW, fetch={"GDELT": lambda: [_it(T1, "u1", 2), _it(T1 + " now", "u2", 23)]}, state=state)
    assert {s["url"] for s in state["saker"]} == {"u1", "u2"}
    later = NOW + timedelta(hours=2)
    data, _ = V.collect(now=later, fetch={"GDELT": lambda: [_it(T1 + " new", "u3", -1), _it(T1, "u1", 2)]}, state=state)
    urls = [s["url"] for s in data["saker"]]
    assert urls == ["u3", "u1"]          # u2 er nå eldre enn 24 t; u1 bare én gang
    assert [s["url"] for s in state["saker"]] == urls
    assert isinstance(state["saker"][0]["publisert"], str)


def test_state_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    assert V.load_state(p) == {}
    V.save_state({"saker": [], "gkg_siste_fil": "2026-11-04T11:45:00Z"}, p)
    assert V.load_state(p)["gkg_siste_fil"] == "2026-11-04T11:45:00Z"
