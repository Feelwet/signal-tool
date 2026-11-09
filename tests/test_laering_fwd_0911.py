"""Mandagsrapporten: flaggkolonnen fra data (ikke pandas' Flags-attributt) og bare komplette vinduer (AnalBot 09.11)."""
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from signaltool import laering_fwd as L

UTC = timezone.utc


def test_flags_read_from_column_not_pandas_attribute():
    df = pd.DataFrame({'ticker': ['A', 'B', 'C'], 'flags': ['weak_px|high_vol', None, 'illiquid']}, dtype=str)
    rows = [r for _, r in df.iterrows()]
    assert '<Flags' in repr(rows[0].flags)                    # selve feilen: attributtet, ikke kolonnen
    out = [L.row_flags(r) for r in rows]
    assert out == ['weak_px|high_vol', '', 'illiquid']
    assert not any('<Flags' in x for x in out)
    assert L.row_flags(pd.Series({'ticker': 'X'})) == '' and L.row_flags({'flags': ['a', 'b']}) == 'a|b'


def test_flags_come_from_real_forward_log():
    p = Path('logs/categories.csv')
    df = pd.read_csv(p, dtype=str).head(400)
    out = [L.row_flags(r) for _, r in df.iterrows()]
    assert not any('<Flags' in x for x in out)
    assert out == [x if isinstance(x, str) else '' for x in df['flags']]


def _idx(last='2026-11-09', n=20):
    return pd.bdate_range(end=last, periods=n)


def test_20d_window_needs_finished_close_on_exchange():
    idx = _idx()                                               # 20. handelsdag = i dag 09.11
    oslo_1830 = datetime(2026, 11, 9, 17, 30, tzinfo=UTC)      # 18:30 norsk tid
    oslo_2231 = datetime(2026, 11, 9, 21, 31, tzinfo=UTC)      # 22:31 norsk tid = 16:31 New York (16:00 + 30 min)
    assert not L.window_complete(idx, 20, 'MP', oslo_1830)     # USA åpen -> utelates
    assert L.window_complete(idx, 20, 'MP', oslo_2231)         # etter NYSE-stengetid + slingring -> med
    assert not L.window_complete(idx, 20, 'MP', datetime(2026, 11, 9, 21, 29, tzinfo=UTC))   # 1 min før
    assert L.window_complete(idx, 20, 'NOD.OL', oslo_1830)     # Oslo stengt 16:25 + 30 min -> med
    assert not L.window_complete(idx, 20, 'X.ZZ', oslo_2231)   # ukjent børs -> aldri ferdig
    assert not L.window_complete(idx[:19], 20, 'NOD.OL', oslo_2231)   # for få handelsdager
    assert L.window_complete(_idx('2026-11-06'), 20, 'MP', oslo_1830)  # sluttdag fredag -> ferdig
    assert not L.window_complete(_idx('2026-11-10'), 20, 'NOD.OL', oslo_2231)   # sluttdag etter kjøringen


def test_mandag_script_uses_helpers():
    p = Path('reports/laering/mandag.py')
    if not p.exists():                                          # privat, ikke i repoet (CI)
        return
    s = p.read_text()
    assert 'r.flags' not in s and 'L.row_flags(r)' in s and 'L.window_complete(' in s
