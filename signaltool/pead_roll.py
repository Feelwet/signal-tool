"""Rullerende topp/topp-terskel (AnalBots backtest/pead_rolling.py, kun bak PEAD_TT_ENABLED).
For en rapport på dag D: 80-persentilen av EPS-overraskelse og av kursreaksjon (aksje minus SPY på reaksjonsdagen)
blant S&P 500-rapporter i de 365 dagene strengt før D; krever minst 200 rapporter i vinduet, ellers ingen terskel.
Rapporter: data/cache/earn (Yahoo) + historikk i data/cache/universe/pead_events.pkl. Kurs: data/cache/universe/us.pkl."""
from __future__ import annotations
import csv, pickle
from datetime import date, datetime
import numpy as np
import pandas as pd
from .config import CACHE

EARN = CACHE / "earn"
MIN_N, Q, WIN = 200, 80, 365


def events() -> pd.DataFrame:
    from .backtest import universe
    rows = []
    try:
        data, _ = universe.us()
    except Exception:
        data = {}
    C = pd.DataFrame({t: v["Close"] for t, v in data.items()}).sort_index() if data else None
    if C is not None and "SPY" in C and EARN.exists():
        spy, idx = C["SPY"], C.index
        for p in EARN.glob("*.pkl"):
            t = p.stem
            if t not in C:
                continue
            d, _f = pickle.loads(p.read_bytes())
            if d is None or not len(d):
                continue
            d = d.dropna(subset=["Surprise(%)"])
            c = C[t]
            for ts, s in d["Surprise(%)"].items():
                ts = pd.Timestamp(ts)
                local = ts.tz_convert("America/New_York") if ts.tzinfo else ts
                day = pd.Timestamp(local.date())
                i = idx.searchsorted(day)
                if local.hour + local.minute / 60 >= 9.5 and i < len(idx) and idx[i] == day:
                    i += 1
                if i < 1 or i >= len(idx) or np.isnan(c.iloc[i]) or np.isnan(c.iloc[i - 1]):
                    continue
                ear = (c.iloc[i] / c.iloc[i - 1] - 1) - (spy.iloc[i] / spy.iloc[i - 1] - 1)
                rows.append({"ticker": t, "date": idx[i], "surprise": float(s), "ear": float(ear)})
    E = pd.DataFrame(rows, columns=["ticker", "date", "surprise", "ear"])
    hist = universe.DIR / "pead_events.pkl"
    if hist.exists():
        H = pd.read_pickle(hist)[["ticker", "date", "surprise", "ear"]]
        E = pd.concat([H, E], ignore_index=True)
    return E.dropna().drop_duplicates(["ticker", "date"], keep="last").sort_values("date").reset_index(drop=True)


_CACHE: dict = {}


def thresholds(on: date | None = None, E: pd.DataFrame | None = None) -> dict | None:
    on = pd.Timestamp(on or date.today())
    if E is None:
        E = _CACHE.get("E")
        if E is None:
            E = _CACHE["E"] = events()
    w = E[(E.date < on) & (E.date >= on - pd.Timedelta(days=WIN))]
    if len(w) < MIN_N:
        return None
    return {"date": on.date().isoformat(), "surprise": float(np.nanpercentile(w.surprise, Q)),
            "reaction": float(np.nanpercentile(w.ear, Q)), "n": int(len(w)),
            "last_report": w.date.max().date().isoformat()}


def log_today(path=None) -> dict | None:
    from .config import ROOT
    path = path or ROOT / "logs" / "pead_tt_thresholds.csv"
    th = thresholds()
    if not th:
        return None
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "surprise_p80_pct", "reaction_p80", "n_window", "grenser_per", "logged_at"])
        w.writerow([th["date"], round(th["surprise"], 3), round(th["reaction"], 5), th["n"], th["last_report"], datetime.now().isoformat(timespec="seconds")])
    return th
