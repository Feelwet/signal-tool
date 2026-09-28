"""Price universes for signal-validation backtests (cached in data/cache/universe/).

US: current S&P 500 members (Wikipedia list -> SURVIVORSHIP BIAS: today's members only) + SPDR sector ETFs + SPY.
Oslo: every issuer seen on Newsweb (as <sign>.OL) that yfinance has data for + OSEBX.OL.
"""
from __future__ import annotations
from .. import http as _http
import io, logging
import pandas as pd
import yfinance as yf
from .. import http
from ..config import CACHE

log = logging.getLogger(__name__)
DIR = CACHE / "universe"
DIR.mkdir(parents=True, exist_ok=True)
SECTOR_ETF = {"Information Technology": "XLK", "Health Care": "XLV", "Financials": "XLF", "Consumer Discretionary": "XLY",
              "Communication Services": "XLC", "Industrials": "XLI", "Consumer Staples": "XLP", "Energy": "XLE",
              "Utilities": "XLU", "Real Estate": "XLRE", "Materials": "XLB"}


def sp500_members() -> pd.DataFrame:
    p = DIR / "sp500.csv"
    if p.exists():
        return pd.read_csv(p)
    r = http.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers={"User-Agent": "Mozilla/5.0 signal-tool research"})
    t = pd.read_html(io.StringIO(r.text))[0][["Symbol", "Security", "GICS Sector"]]
    t["Symbol"] = t["Symbol"].str.replace(".", "-", regex=False)
    t.to_csv(p, index=False)
    return t


def _download(tickers, start, name) -> dict[str, pd.DataFrame]:
    p = DIR / f"{name}.pkl"
    from ..data_quality import clean_universe   # backtests use repaired prices too (spike-and-revert bars)
    if p.exists():
        return clean_universe(pd.read_pickle(p))[0]
    out = {}
    for i in range(0, len(tickers), 100):
        chunk = tickers[i:i + 100]
        try:
            d = _http.yf_download(chunk, start=start, progress=False, auto_adjust=True, group_by="ticker", threads=True)
        except Exception as e:
            log.warning("chunk failed: %s", e)
            continue
        for t in chunk:
            try:
                df = d[t][["Close", "Volume", "High", "Low"]].dropna(subset=["Close"])
                if len(df) > 250:
                    df.index = pd.to_datetime(df.index).tz_localize(None)
                    out[t] = df
            except KeyError:
                pass
    pd.to_pickle(out, p)
    return clean_universe(out)[0]


def us(start="2005-01-01"):
    m = sp500_members()
    tick = sorted(set(m["Symbol"]) | set(SECTOR_ETF.values()) | {"SPY"})
    return _download(tick, start, "us"), m


def oslo(start="2010-01-01"):
    p = DIR / "oslo_signs.csv"
    if p.exists():
        signs = pd.read_csv(p)["sign"].tolist()
    else:
        from datetime import date, timedelta
        signs = set()
        d = date.today() - timedelta(days=120)
        while d < date.today():
            try:
                j = http.get_json("https://api3.oslo.oslobors.no/v1/newsreader/list",
                                  params={"category": "", "issuer": "", "fromDate": d.isoformat(), "toDate": (d + timedelta(days=4)).isoformat(),
                                          "market": "", "messageTitle": ""}, cache_hours=48)
                signs |= {m.get("issuerSign") for m in j["data"]["messages"] if m.get("issuerSign")}
            except Exception as e:
                log.warning("newsweb: %s", e)
            d += timedelta(days=5)
        signs = sorted(s for s in signs if s.isalnum() or "-" in s)
        pd.DataFrame({"sign": signs}).to_csv(p, index=False)
    tick = sorted({f"{s}.OL" for s in signs} | {"OSEBX.OL"})
    return _download(tick, start, "oslo")
