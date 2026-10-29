"""29.10 runde 3: kortstil på modulene, nøkkeltall-ⓘ, navn for 8 tickere, Brent 20d «–» ved kontraktsbytte i perioden."""
import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import signaltool.mstrip as M
import signaltool.site as S
import signaltool.site_layout as L
from signaltool import names as NM

ROOT = Path(__file__).resolve().parent.parent


def _ser(last, n=25):
    ds, d = [], last
    while len(ds) < n:
        if d.weekday() < 5:
            ds.append(d)
        d -= timedelta(days=1)
    ds = ds[::-1]
    return {"dates": [x.isoformat() for x in ds], "close": [100.0 + i for i in range(n)]}


def test_mod_css_values():
    c = S.MOD_CSS
    for v in ("#1c2430", "1px solid #3b4757", "3px solid #58a6ff", "border-radius:12px", "padding:16px", "padding:12px", "#111821",
              "text-transform:uppercase", "font-size:20px", "font-weight:600", "#cbd5e1", "#fdba74"):
        assert v in c, v
    assert "#111821" not in S.MET_CSS and "3px solid #58a6ff" in S.MET_CSS


def test_kpi_info_only_on_modules():
    k = [("3", "Temaer", "totalt", "#")]
    assert 'class="ri ri-c sc-i"' in L.head("Temaer", "x", k) and "Temaer: totalt" in L.head("Temaer", "x", k)
    assert "sc-i" not in L.head("Metode", "x", k) and "sc-i" not in L.head("Kalender", "x", k)
    assert ">3<" in L.head("Temaer", "x", k)   # verdien uendret


def test_names_present():
    for t in "HII KIM LLY MRK NCLH TXT WEC WST".split():
        assert NM.name(t), t


def test_brent_rolls_ice_rule():
    assert M.ice_expiry(2026, 8) == date(2026, 8, 28)      # 31.08.2026 er bank holiday
    assert M.ice_expiry(2026, 10) == date(2026, 10, 30)
    assert M.roll_in_window(date(2026, 10, 1), date(2026, 10, 30)) is False   # utløpsdagen er siste kurs i gammel kontrakt
    assert M.roll_in_window(date(2026, 10, 1), date(2026, 11, 2)) is True
    rows = list(csv.DictReader((ROOT / "logs" / "brent_rolls.csv").open()))
    assert rows[0]["utlop_siste_handelsdag"] == "2026-01-30" and rows[0]["ny_frontkontrakt_bz"] == "H26" and len(rows) == 24


def test_brent_20d_dash_when_roll_in_window():
    now = datetime(2026, 11, 25, 6, 0, tzinfo=timezone.utc)
    h = M.field(M.FIELDS[0], {"BZ=F": _ser(date(2026, 11, 24))}, now)
    assert "20d –</span>" in h and "Kontraktsbytte i perioden" in h and "FLAG" not in h
    bt = M.field(M.FIELDS[1], {"BTC-USD": _ser(date(2026, 11, 24))}, now)
    assert "Kontraktsbytte" not in bt and "20d +" in bt
