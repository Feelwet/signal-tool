"""Scan S&P 500 members for the validated 'strong earnings report' signal (EPS surprise >= 15 % AND reaction-day
return >= +4 % vs S&P 500, report <= 45 days old). Yahoo earnings dates via yfinance (free, unofficial).
Cache per ticker; a ticker is re-queried only when its next scheduled report date has passed (or cache > 20 days),
so after the first run only companies that just reported cost a request."""
from __future__ import annotations
import logging, pickle, time
from datetime import date, datetime, timedelta
import pandas as pd
import yfinance as yf
from ..config import CACHE
from ..decision import PEAD_SURPRISE, PEAD_REACTION, PEAD_MAX_AGE

log = logging.getLogger(__name__)
DIR = CACHE / "earn"
DIR.mkdir(parents=True, exist_ok=True)
SP500 = CACHE / "universe" / "sp500.csv"


def _dates(t: str) -> pd.DataFrame | None:
    p = DIR / f"{t}.pkl"
    if p.exists():
        d, fetched = pickle.loads(p.read_bytes())
        nxt = [x for x in d.index if pd.isna(d.at[x, "Reported EPS"]) and x.date() >= fetched.date()] if d is not None and len(d) else []
        stale = (datetime.now() - fetched).days > 20
        due = any(x.date() <= date.today() for x in nxt) or not nxt
        if not stale and not due:
            return d
        if not stale and (datetime.now() - fetched).total_seconds() < 12 * 3600:
            return d
    try:
        d = yf.Ticker(t).get_earnings_dates(limit=6)
    except Exception as ex:
        log.info("earn %s: %s", t, ex)
        d = None
    if d is not None:
        d = d[~d.index.duplicated()]
    p.write_bytes(pickle.dumps((d, datetime.now())))
    time.sleep(0.15)
    return d


def scan(tickers: list[str] | None = None, max_age=PEAD_MAX_AGE) -> tuple[list[dict], str]:
    if tickers is None:
        if not SP500.exists():
            return [], "skipped (S&P 500-liste mangler – kjør backtest-universet)"
        tickers = pd.read_csv(SP500)["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()
    recent = []
    for t in tickers:
        d = _dates(t)
        if d is None or d.empty:
            continue
        d = d.dropna(subset=["Surprise(%)"])
        if d.empty:
            continue
        ts = d.index.max()
        if (date.today() - ts.date()).days <= max_age + 3:
            recent.append((t, ts, float(d.loc[ts, "Surprise(%)"])))
    cand = [(t, ts, s) for t, ts, s in recent if s >= PEAD_SURPRISE]
    if not cand:
        return [], f"ok ({len(recent)} rapporter siste {max_age} d, ingen med overraskelse ≥ {PEAD_SURPRISE:.0f} %)"
    px = yf.download([c[0] for c in cand], period="4mo", auto_adjust=True, progress=False)["Close"]
    if isinstance(px, pd.Series):
        px = px.to_frame(cand[0][0])
    b = None
    for bt in ("^GSPC", "SPY", "^GSPC"):
        try:
            bs = yf.download(bt, period="4mo", auto_adjust=True, progress=False)["Close"]
            bs = (bs.iloc[:, 0] if isinstance(bs, pd.DataFrame) else bs).dropna()
            if len(bs) > 20:
                b = bs
                break
        except Exception:
            pass
    if b is None:
        raise RuntimeError("fant ikke referanseindeks (^GSPC/SPY) hos Yahoo")
    out = []
    for t, ts, s in cand:
        if t not in px:
            continue
        c = px[t].dropna()
        local = ts.tz_convert("America/New_York") if ts.tzinfo else ts
        day = pd.Timestamp(local.date())
        p = c.index.searchsorted(day)
        if local.hour + local.minute / 60 >= 9.5 and p < len(c) and c.index[p] == day:
            p += 1
        if p < 1 or p >= len(c):
            continue
        bb = b.reindex(c.index).ffill()
        ear = (c.iloc[p] / c.iloc[p - 1] - 1) - (bb.iloc[p] / bb.iloc[p - 1] - 1)
        age = (date.today() - c.index[p].date()).days
        if ear >= PEAD_REACTION and age <= max_age:
            out.append({"ticker": t, "date": str(c.index[p].date()), "surprise": round(s, 1), "reaction": round(float(ear), 4), "age": age,
                        "since": round(float(c.iloc[-1] / c.iloc[p] - 1), 4)})
    out.sort(key=lambda x: x["age"])
    return out, f"ok ({len(recent)} rapporter siste {max_age} d; {len(out)} oppfyller overraskelse ≥ {PEAD_SURPRISE:.0f} % og reaksjon ≥ +{PEAD_REACTION*100:.0f} %)"
