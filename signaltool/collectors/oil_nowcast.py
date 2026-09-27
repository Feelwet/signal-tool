"""Physical-oil nowcast vs seasonal norms (EIA weekly history pages, free, no key):
US commercial crude (excl. SPR), gasoline and distillate stocks vs the 5-year average for the same week.
Tight = stocks below seasonal norm. (FRED no longer carries these weekly series -> 404, so we read EIA directly.)"""
from __future__ import annotations
import pandas as pd
import io
from .. import http

SERIES = {"WCESTUS1": "Råolje, kommersielle lagre USA (eks. SPR)", "WGTSTUS1": "Bensinlagre USA", "WDISTUS1": "Destillatlagre (diesel) USA"}


def eia_weekly(sid: str) -> pd.Series:
    """Parse EIA 'LeafHandler' weekly history table (Year-Month rows x Week1..5 End Date/Value). Values in thousand barrels."""
    r = http.get("https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx", params={"n": "PET", "s": sid, "f": "W"},
                 cache_hours=12, timeout=40)
    tabs = [t for t in pd.read_html(io.StringIO(r.text)) if t.shape[1] >= 11]
    t = max(tabs, key=len)
    rows = []
    for _, row in t.iterrows():
        ym = str(row.iloc[0]).strip()
        try:
            year = int(ym[:4])
        except ValueError:
            continue
        for k in range(5):
            d, v = row.iloc[1 + 2 * k], row.iloc[2 + 2 * k]
            if isinstance(d, str) and "/" in d and pd.notna(v):
                mm, dd = d.split("/")
                y = year + 1 if (ym.endswith("Dec") and mm == "01") else year
                rows.append((pd.Timestamp(y, int(mm), int(dd)), float(v) / 1000.0))
    return pd.Series(dict(rows)).sort_index()


def seasonal_dev(s: pd.Series, years=5) -> dict:
    s = s.dropna()
    last_d, last = s.index[-1], float(s.iloc[-1])
    wk = last_d.isocalendar().week
    hist = []
    for y in range(1, years + 1):
        target = last_d - pd.DateOffset(years=y)
        w = s[(s.index >= target - pd.Timedelta(days=4)) & (s.index <= target + pd.Timedelta(days=4))]
        if len(w):
            hist.append(float(w.iloc[0]))
    avg = sum(hist) / len(hist) if hist else None
    prev = float(s.iloc[-2]) if len(s) > 1 else None
    return {"date": str(last_d.date()), "last": round(last, 1), "avg5y": None if avg is None else round(avg, 1),
            "dev_pct": None if not avg else round(last / avg - 1, 4), "chg_w": None if prev is None else round(last - prev, 1),
            "min5y": round(min(hist), 1) if hist else None, "max5y": round(max(hist), 1) if hist else None, "week": int(wk),
            "spark": [round(float(x), 1) for x in s.iloc[-52:]]}


def collect() -> tuple[dict, str]:
    out, errs = {}, []
    for sid, lab in SERIES.items():
        try:
            s = eia_weekly(sid)
            s = s[s.index >= "2018-01-01"]
            out[sid] = {"label": lab, **seasonal_dev(s)}
        except Exception as e:
            errs.append(f"{sid}: {e}")
    tight = [v["label"] for v in out.values() if v.get("dev_pct") is not None and v["dev_pct"] <= -0.05]
    msg = f"ok ({len(out)}/3 serier" + (f"; under 5-årssnitt: {len(tight)}" if out else "") + ")"
    return out, msg if out else "FAILED: " + "; ".join(errs)
