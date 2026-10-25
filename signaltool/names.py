"""Selskapsnavn fra Yahoo Finance (yfinance longName/shortName + fullExchangeName), bufret i signaltool/names.json.
Aldri håndskrevne navn: mangler navnet, vises bare tickeren.  Oppdater: python3 -m signaltool.names TICKER ..."""
from __future__ import annotations

import json
import sys
import time
from html import escape as E
from pathlib import Path

PATH = Path(__file__).with_name("names.json")
_C: dict = {}


def _load() -> dict:
    if not _C:
        try:
            _C.update(json.loads(PATH.read_text()).get("names") or {})
        except Exception:
            pass
    return _C


def name(ticker: str, fallback: str | None = None) -> str | None:
    r = _load().get(ticker) or {}
    return r.get("name") or fallback or None


def exchange(ticker: str) -> str | None:
    return (_load().get(ticker) or {}).get("exchange") or None


CSS = """
.tn{display:inline-flex;flex-direction:column;min-width:0;white-space:normal;line-height:1.25}.tn .nm{font-weight:700;overflow-wrap:anywhere}
.tn .tk{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--mut)}.tn .tk a.tv{font-family:inherit}
.thead{margin:0 0 8px}.thead .nm1{font-size:24px;font-weight:700;line-height:1.2;margin:0;overflow-wrap:anywhere}
.thead .tk1{font:14px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--mut);display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.thead .chart{display:inline-flex;align-items:center;min-height:44px;padding:0 6px;font-family:system-ui,sans-serif}
@media(max-width:599px){.thead .nm1{font-size:20px}}
"""


def cell(ticker: str, href: str | None = None, fallback: str | None = None, extra: str = "") -> str:
    """Navn øverst (fet), ticker under i liten grå tekst med TradingView ↗ rett ved. Uten navn: bare tickeren."""
    from . import sectors as SEC
    n = name(ticker, fallback)
    tk = f'<a href="{E(href)}">{E(ticker)}</a>' if href else E(ticker)
    if not n:
        return f'<span class="tn"><span class="nm">{tk}</span><span class="tk">{SEC.tv_ext(ticker).strip()}{extra}</span></span>'
    nm = f'<a href="{E(href)}">{E(n)}</a>' if href else E(n)
    return f'<span class="tn"><span class="nm">{nm}</span><span class="tk">{E(ticker)}{SEC.tv_ext(ticker)}{extra}</span></span>'


def header(ticker: str, fallback: str | None = None, after: str = "") -> str:
    from . import sectors as SEC
    n = name(ticker, fallback)
    ex = exchange(ticker)
    url = SEC.tv_url(ticker)
    tk = E(ticker) + (f" · {E(ex)}" if ex else "")
    ch = f'<a class="chart" target="_blank" rel="noopener" href="{E(url)}">Chart ↗</a>' if url else ""
    return (f'<div class="thead"><h1 class="nm1">{E(n or ticker)}</h1>'
            f'<div class="tk1">{"<span>" + tk + "</span>" if n else ""}{ch}{after}</div></div>')


def refresh(tickers) -> list:
    import yfinance as yf
    d = json.loads(PATH.read_text()) if PATH.exists() else {"names": {}}
    miss = []
    for t in tickers:
        try:
            i = yf.Ticker(t).info or {}
        except Exception:
            i = {}
        n = i.get("longName") or i.get("shortName")
        if n:
            d["names"][t] = {"name": n, "exchange": i.get("fullExchangeName") or None}
        else:
            miss.append(t)
        time.sleep(0.3)
    d["source"] = "Yahoo Finance via yfinance (longName, ellers shortName; fullExchangeName)"
    d["fetched"] = time.strftime("%Y-%m-%d")
    PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True))
    _C.clear()
    return miss


if __name__ == "__main__":
    print("mangler:", refresh(sys.argv[1:]))
