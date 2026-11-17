"""AnalBot 17.11: r20_close — Yahoo adj close på siste lukkede bar før kjøringens start (stengetid + 30 min).

r20 i logs/learn_raw.csv skal være byte-identisk med origin/master. Forventet r20_close
regnes fra en uavhengig kursramme i testen, ikke fra samme logg.
"""
from __future__ import annotations

import csv
import inspect
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from signaltool.displayprices import CLOSE, exchange_close, yahoo_alias
from signaltool.r20_close import STALE_FLAG, compute, last_closed, lookback
from signaltool import closedbars as CB
from signaltool import r20_close as R20

REPO = Path(__file__).resolve().parents[1]


def _bdays(end: str, n: int) -> list[str]:
    d = date.fromisoformat(end)
    xs: list[str] = []
    while len(xs) < n:
        if d.weekday() < 5:
            xs.append(str(d))
        d -= timedelta(days=1)
    return list(reversed(xs))


def _ser(end: str, n: int = 30, start: float = 100.0) -> dict:
    """Uavhengig kursramme: lineært stigende adj close. Ikke hentet fra learn_raw."""
    return {d: start + i for i, d in enumerate(_bdays(end, n))}


def _exp(ser: dict, last: str, n: int = 20) -> float:
    ks = [d for d in sorted(ser) if d <= last]
    return ks[-1] and (ser[ks[-1]] / ser[ks[-1 - n]] - 1)


def test_r20_close_never_uses_bar_before_close_plus_30():
    s = _ser("2026-11-16", 30)
    early = datetime(2026, 11, 16, 16, 54, tzinfo=ZoneInfo("Europe/Oslo"))
    late = datetime(2026, 11, 16, 16, 55, tzinfo=ZoneInfo("Europe/Oslo"))
    assert last_closed("SCANA.OL", s, early) == "2026-11-13"
    assert last_closed("SCANA.OL", s, late) == "2026-11-16"
    val_e, fl_e = compute("SCANA.OL", s, early)
    val_l, fl_l = compute("SCANA.OL", s, late)
    assert fl_e == fl_l == ""
    assert val_e == f"{_exp(s, '2026-11-13'):.6f}"
    assert val_l == f"{_exp(s, '2026-11-16'):.6f}"
    assert not CB.ok("SCANA.OL", "2026-11-16", early)
    assert CB.ok("SCANA.OL", "2026-11-16", late)


def test_utdatert_bar_empty_and_flag():
    s = _ser("2026-11-05", 30)
    cases = [
        datetime(2026, 11, 11, 13, 44, tzinfo=ZoneInfo("Europe/Oslo")),  # forventet 10.11
        datetime(2026, 11, 16, 14, 42, tzinfo=ZoneInfo("Europe/Oslo")),  # forventet 13.11
        datetime(2026, 11, 17, 7, 59, tzinfo=ZoneInfo("Europe/Oslo")),   # forventet 16.11
    ]
    for now in cases:
        val, flag = compute("CADLR.OL", s, now)
        assert val == "", f"{now}: {val!r}"
        assert flag == STALE_FLAG, f"{now}: {flag!r}"
    # kontroll: siste bar 11.11, kjøring 16.11 før stengetid (forventet 13.11) = 2 handelsdager, ikke utdatert
    ok_s = _ser("2026-11-11", 30)
    now = cases[1]
    val, flag = compute("SCANA.OL", ok_s, now)
    assert flag == ""
    assert val != ""
    assert val == f"{_exp(ok_s, '2026-11-11'):.6f}"


def test_brk_b_and_mog_a_mapped():
    assert yahoo_alias("BRK.B") == "BRK-B"
    assert yahoo_alias("MOG.A") == "MOG-A"
    assert yahoo_alias("AAPL") == "AAPL"
    assert exchange_close("BRK.B") == CLOSE[""]
    assert exchange_close("MOG.A") == CLOSE[""]
    s = _ser("2026-10-23", 30)
    now = datetime(2026, 10, 25, 21, 24, 47, tzinfo=timezone.utc)  # etter US stengetid + 30
    for t in ("BRK.B", "MOG.A"):
        assert last_closed(t, s, now) == "2026-10-23"
        val, flag = compute(t, s, now)
        assert flag == ""
        assert val == f"{_exp(s, '2026-10-23'):.6f}"
    fri_late = datetime(2026, 10, 23, 16, 30, tzinfo=ZoneInfo("America/New_York"))
    fri_early = datetime(2026, 10, 23, 16, 29, tzinfo=ZoneInfo("America/New_York"))
    assert CB.ok("BRK.B", "2026-10-23", fri_late)
    assert not CB.ok("BRK.B", "2026-10-23", fri_early)
    assert CB.ok("MOG.A", "2026-10-23", fri_late)
    assert not CB.ok("MOG.A", "2026-10-23", fri_early)


def test_r20_byte_identical_to_origin_master():
    """r20 (og alle andre opprinnelige felt) er byte-identiske med origin/master. r20_close er ny kolonne."""
    try:
        old = subprocess.check_output(
            ["git", "show", "origin/master:logs/learn_raw.csv"], text=True, stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as ex:
        raise AssertionError("origin/master:logs/learn_raw.csv er ikke tilgjengelig") from ex
    new = (REPO / "logs/learn_raw.csv").read_text()
    old_rows = list(csv.DictReader(old.splitlines()))
    new_rows = list(csv.DictReader(new.splitlines()))
    assert len(old_rows) == len(new_rows)
    orig = list(old_rows[0].keys())
    assert "r20" in orig
    old_r20 = "\n".join(r["r20"] for r in old_rows)
    new_r20 = "\n".join(r["r20"] for r in new_rows)
    assert old_r20 == new_r20
    assert old_r20.encode("utf-8") == new_r20.encode("utf-8")
    for a, b in zip(old_rows, new_rows):
        for k in orig:
            assert a[k] == b[k], f"{a['date']} {a['ticker']} {k}"
    assert "r20_close" in new_rows[0] and "r20_close_flag" in new_rows[0]


def test_expected_r20_close_not_from_learn_raw_log():
    """Forventet verdi kommer fra testens egen kursramme, ikke fra logs/learn_raw.csv."""
    s = _ser("2026-11-13", 30, start=40.0)
    now = datetime(2026, 11, 16, 15, 0, tzinfo=ZoneInfo("Europe/Oslo"))  # før Oslo-stengetid
    val, flag = compute("SCANA.OL", s, now)
    ks = [d for d in sorted(s) if d <= "2026-11-13"]
    exp = s[ks[-1]] / s[ks[-21]] - 1
    assert flag == ""
    assert val == f"{exp:.6f}"
    # r20_close-regelen leser ikke learn_raw-loggen (doc-strengen nevner den bare som advarsel)
    assert "learn_raw" not in inspect.getsource(R20.compute)
    assert "open(" not in inspect.getsource(R20.compute)


def test_unknown_exchange_empty_flag():
    s = _ser("2026-10-23", 30)
    now = datetime(2026, 10, 25, 21, 24, 47, tzinfo=timezone.utc)
    val, flag = compute("BA.L", s, now)
    assert val == "" and flag == "ukjent børs"
    val2, flag2 = compute("SAAB-B.ST", s, now)
    assert val2 == "" and flag2 == "ukjent børs"


def test_share_class_usa_after_market_suffix_change():
    """Etter market()/bors_of (suffiks alene): BRK.B og MOG.A er fortsatt USA med US-stengetid.
    .L og .ST er kjente suffiksbørser i market(), men r20_close har ingen stengetid (ukjent børs).
    """
    from signaltool.bors import bors_of
    from signaltool.risk import market
    assert market("BRK.B") == "US" and bors_of("BRK.B") == "USA"
    assert market("MOG.A") == "US" and bors_of("MOG.A") == "USA"
    assert exchange_close("BRK.B") == CLOSE[""]
    assert exchange_close("MOG.A") == CLOSE[""]
    assert yahoo_alias("BRK.B") == "BRK-B" and yahoo_alias("MOG.A") == "MOG-A"
    assert market("BA.L") == "Storbritannia" and market("SAAB-B.ST") == "Sverige"
    assert exchange_close("BA.L") is None and exchange_close("SAAB-B.ST") is None
    now = datetime(2026, 10, 25, 21, 24, 47, tzinfo=timezone.utc)
    s = _ser("2026-10-23", 30)
    assert compute("BA.L", s, now) == ("", "ukjent børs")
    assert compute("SAAB-B.ST", s, now) == ("", "ukjent børs")
    val, flag = compute("BRK.B", s, now)
    assert flag == "" and val == f"{_exp(s, '2026-10-23'):.6f}"
