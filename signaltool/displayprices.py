"""Kursdata bare for visning (bruker/AnalBot 09.11): 5d/20d for børsnoterte selskaper i verdikjeder og trender som ikke
finnes i signalutvalget. Samme gratis kilde som resten av siden (Yahoo Finance via yfinance, http.yf_download).

Skilt fra signalene: lagres i egen fil (data/display_prices.json), legges aldri inn i snapshot['tickers'], og leses bare
av aksjetabellene på Trender. Påvirker ikke kandidatutvalg, score, Kjøp, Signal-boka, kategorier eller GS-indeks
(test: tests/test_displayprices_0911.py bygger siden med og uten filen og sammenligner byte for byte).
Mangler kilden data for et symbol, vises «Ingen data» (aldri oppdiktede tall).
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)
SOURCE = "Yahoo Finance via yfinance (gratis, uoffisiell)"

# Børs i kildeloggen -> Yahoo-suffiks. Bare børser der kilden faktisk har kurser; ukjent børs -> ingen symbol («Ingen data»).
SUFFIX = {"TSE": ".T", "TPEX": ".TWO", "TWSE": ".TW", "EURONEXT PARIS": ".PA", "KRX": ".KS"}


def path() -> Path:
    from .config import DATA
    return DATA / "display_prices.json"


def yahoo_symbol(ticker: str | None, exchange: str | None) -> str | None:
    """«NOD»/«Oslo Børs» -> NOD.OL; NASDAQ/NYSE -> ticker; «4063»/«TSE» -> 4063.T; ukjent -> None."""
    if not ticker:
        return None
    ex = (exchange or "").upper()
    if "OSLO" in ex or ex in ("OSE",):
        return f"{ticker}.OL"
    if "NASDAQ" in ex or "NYSE" in ex:
        return ticker
    suf = SUFFIX.get(ex.strip())
    return f"{ticker}{suf}" if suf else None


def wanted() -> list[str]:
    """Alle børsnoterte selskaper i verdikjedene og trendene (Yahoo-symboler), i kildeloggens rekkefølge."""
    from . import verdikjeder as VK, trender as TR
    out = [r[5] for r in VK.stock_rows(VK.load()['links']) if len(r) > 5 and r[5]]
    try:
        out += [r[5] for t in TR.load()['trends'] for r in map(TR.trend_row, t['companies']) if r[5]]
    except Exception as ex:   # trender.json er kontrollert ved bygging; her bare et forsøk
        log.warning("display prices: trender: %s", ex)
    return list(dict.fromkeys(out))


def stats(close) -> dict | None:
    """Samme definisjon som collectors/markets.ticker_stats: pct_change(5)/(20) på sluttkurs, dato for siste kurs."""
    c = close.dropna()
    if len(c) < 21:
        return None
    r5, r20 = float(c.iloc[-1] / c.iloc[-6] - 1), float(c.iloc[-1] / c.iloc[-21] - 1)
    if r5 != r5 or r20 != r20:
        return None
    return {"last_date": str(c.index[-1].date()), "ret_5d": round(r5, 4), "ret_20d": round(r20, 4)}


# AnalBot 09.11: bare sluttkurs. Børsens lokale stengetid (+30 min slingring); dagens bar droppes før det.
# Offisielle handelstider (sjekket med curl 09.11.2026, HTTP 200 etter eventuell videresending):
#   TSE (Tokyo, .T):              https://www.jpx.co.jp/english/equities/trading/domestic/01.html
#   TWSE (Taiwan, .TW):           https://www.twse.com.tw/en/products/system/trading.html
#   TPEx (Taipei Exchange, .TWO): https://www.tpex.org.tw/en-us/mainboard/trading/rules/system.html
#   KRX (Seoul, .KS):             https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf
#   Euronext Paris (.PA) og Euronext Oslo/Oslo Børs (.OL): https://www.euronext.com/en/trading/trading-hours-holidays
#   NYSE (USA, uten suffiks; Nasdaq har samme stengetid 16:00 ET): https://www.nyse.com/trade/hours-calendars
CLOSE = {".T": ("Asia/Tokyo", 15, 30), ".TWO": ("Asia/Taipei", 13, 30), ".TW": ("Asia/Taipei", 13, 30),
         ".KS": ("Asia/Seoul", 15, 30), ".PA": ("Europe/Paris", 17, 35), ".OL": ("Europe/Oslo", 16, 25),
         "": ("America/New_York", 16, 0)}
BUFFER_MIN = 30


def exchange_close(sym: str):
    """(tidssone, time, minutt) for symbolets børs; None når børsen er ukjent (da droppes dagens bar alltid)."""
    if "." not in sym:
        return CLOSE[""]
    return CLOSE.get("." + sym.rsplit(".", 1)[1])


def completed(df, sym: str, now: datetime | None = None):
    """Fjerner baren for en handelsdag som ikke er avsluttet ennå (børsens lokale tid). Dato = siste avsluttede handelsdag."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    if df is None or not len(df):
        return df
    now = now or datetime.now(timezone.utc)
    ex = exchange_close(sym)
    tz = ZoneInfo(ex[0] if ex else "UTC")
    loc = now.astimezone(tz)
    last = df.index[-1].date()
    if last < loc.date():
        return df
    if ex is None:                       # ukjent børs: usikker -> dagens bar droppes
        return df.iloc[:-1]
    close = loc.replace(hour=ex[1], minute=ex[2], second=0, microsecond=0) + timedelta(minutes=BUFFER_MIN)
    return df if loc >= close else df.iloc[:-1]


RETRIES, BACKOFF_S = 2, (2.0, 5.0)


def _frame(d, s: str):
    """Én tickers sluttkurser fra en yfinance-ramme (gruppert eller enkel); None ved manglende data."""
    try:
        df = d[s] if s in getattr(d.columns, 'levels', [[]])[0] else d
        df = df.dropna(subset=["Close"])
    except Exception:
        return None
    return df if len(df) else None


def retry_one(s: str, sleep=None):
    """Henter ett symbol på nytt inntil RETRIES ganger med kort pause. None når kilden fortsatt er tom."""
    import time
    import yfinance as yf
    sleep = sleep or time.sleep
    for i in range(RETRIES):
        sleep(BACKOFF_S[min(i, len(BACKOFF_S) - 1)])
        try:
            d = yf.download(s, period="3mo", progress=False, auto_adjust=True, group_by="ticker", threads=False)
        except Exception as ex:
            log.info("display prices retry %s: %s", s, ex)
            continue
        if d is not None and len(d):
            df = _frame(d, s)
            if df is not None:
                return df
    return None


def fetch(symbols: list[str], now: datetime | None = None) -> dict[str, dict]:
    from . import http as _http
    from .data_quality import clean_universe
    if not symbols:
        return {}
    d = _http.yf_download(symbols, period="3mo", progress=False, auto_adjust=True, group_by="ticker", threads=True)
    frames = {}
    for s in symbols:
        df = _frame(d, s)
        if df is None or not len(df):
            df = retry_one(s)          # bruker 09.11: tom serie -> nytt forsøk per symbol (maks 2), ellers ærlig «Ingen data»
        if df is None:
            continue
        df = completed(df, s, now)
        if len(df):
            frames[s] = df
    frames, _ = clean_universe(frames)   # samme spike-reparasjon som tickersidene, uten å skrive i kvalitetsrapporten
    out = {}
    for s, df in frames.items():
        st = stats(df["Close"])
        if st:
            out[s] = st
    return out


def refresh() -> str:
    """Henter og skriver filen. Feiler hentingen, beholdes forrige fil (verdiene står med sin egen dato)."""
    syms = wanted()
    try:
        prices = fetch(syms)
    except Exception as ex:
        log.warning("display prices: %s", ex)
        return f"FAILED ({ex}); forrige fil beholdes"
    if not prices:
        return "FAILED (ingen data); forrige fil beholdes"
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": SOURCE,
                             "prices": prices}, indent=1, sort_keys=True))
    miss = [s for s in syms if s not in prices]
    return f"ok ({len(prices)}/{len(syms)})" + (f"; mangler {miss}" if miss else "")


def load(p: Path | None = None) -> dict[str, dict]:
    """{symbol: {last_date, ret_5d, ret_20d}}; tom ved manglende/ugyldig fil."""
    p = p or path()
    try:
        d = json.loads(p.read_text())
        return {k: v for k, v in (d.get("prices") or {}).items() if isinstance(v, dict)}
    except Exception:
        return {}


if __name__ == "__main__":
    print(refresh())
