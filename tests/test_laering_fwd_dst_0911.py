"""Stengetid regnes i børsens egen tidssone (zoneinfo), ikke som fast Oslo-klokkeslett.
2027: USA bytter til sommertid 14.03, Europa 28.03. I mellomrommet stenger NYSE 21:00 Oslo-tid."""
from datetime import datetime
from zoneinfo import ZoneInfo
from signaltool.laering_fwd import day_closed

OSLO = ZoneInfo("Europe/Oslo")


def t(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=OSLO)


def test_us_close_10_03_2027_before_us_dst():
    # 10.03.2027: begge på normaltid, NYSE 16:00 ET = 22:00 Oslo, +30 min slakk
    assert not day_closed("2027-03-10", "AMAT", t(2027, 3, 10, 22, 29))
    assert day_closed("2027-03-10", "AMAT", t(2027, 3, 10, 22, 31))


def test_us_close_17_03_2027_in_dst_gap():
    # 17.03.2027: USA sommertid, Europa ikke ennå -> 16:00 ET = 21:00 Oslo, +30 min
    assert not day_closed("2027-03-17", "AMAT", t(2027, 3, 17, 21, 29))
    assert day_closed("2027-03-17", "AMAT", t(2027, 3, 17, 21, 31))


def test_us_close_autumn_gap_2026():
    # 02.11.2026: Europa normaltid (25.10), USA sommertid til 01.11 -> her begge normaltid igjen, 22:00 Oslo
    assert not day_closed("2026-11-02", "AMAT", t(2026, 11, 2, 22, 29))
    # 28.10.2026: Europa normaltid, USA fortsatt sommertid -> 21:00 Oslo
    assert day_closed("2026-10-28", "AMAT", t(2026, 10, 28, 21, 31))
    assert not day_closed("2026-10-28", "AMAT", t(2026, 10, 28, 21, 29))
