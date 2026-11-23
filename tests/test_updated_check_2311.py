"""AnalBot 23.11: «Oppdatert» eldre enn 26 t på Oslo-handelsdag skal feile i live-sjekken."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from signaltool.updated_check import is_oslo_trading_day, parse_updated, stale_updated

OSLO = ZoneInfo("Europe/Oslo")


def test_parse_prefers_iso_then_oppdatert_text():
    iso = '<body data-generated="2026-11-18T00:57:00+01:00"><p>Oppdatert 18.11 kl. 00:57</p>'
    dt = parse_updated(iso)
    assert dt == datetime(2026, 11, 18, 0, 57, tzinfo=OSLO)
    text = '<p class="ov-when">Oppdatert 18.11 kl. 00:57 Oslo-tid</p>'
    dt = parse_updated(text, year=2026)
    assert dt == datetime(2026, 11, 18, 0, 57, tzinfo=OSLO)
    assert parse_updated("<p>ingen</p>") is None


def test_stale_on_trading_day_over_26h_not_on_weekend():
    upd = datetime(2026, 11, 18, 0, 57, tzinfo=OSLO)
    mon = datetime(2026, 11, 23, 18, 0, tzinfo=OSLO)   # mandag, langt over 26 t
    assert is_oslo_trading_day(mon) and stale_updated(upd, mon) is True
    # nøyaktig 26 t: ikke eldre enn
    exact = upd + timedelta(hours=26)
    assert exact.weekday() == 3  # torsdag
    assert stale_updated(upd, exact) is False
    assert stale_updated(upd, exact + timedelta(seconds=1)) is True
    # 25 t: ikke utdatert
    assert stale_updated(upd, upd + timedelta(hours=25)) is False
    # lørdag: ikke feile, selv om alderen er stor
    sat = datetime(2026, 11, 21, 12, 0, tzinfo=OSLO)
    assert not is_oslo_trading_day(sat)
    assert stale_updated(upd, sat) is False
    # mangler tidspunkt på handelsdag
    assert stale_updated(None, mon) is True
    assert stale_updated(None, sat) is False
