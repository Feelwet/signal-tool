"""Kursgraf på tickersiden: daglige sluttkurser (Yahoo, ekte historikk) + stiplet 50-dagers snitt, markør på innkursdagen
(price_date). Ingen prognoser eller trendlinjer; hull i dataene blir hull i linja. Én farge (#58a6ff)."""
from __future__ import annotations
import json, math
from datetime import date
from html import escape as E

PERIODS = [("1M", 22), ("6M", 126), ("1Å", 252), ("5Å", 1260)]
DEFAULT = "6M"
COL = "#58a6ff"
_CACHE: dict = {}


def download(tickers: list[str]) -> dict:
    """{ticker: [(YYYY-MM-DD, close|None), ...]} for 5 år, ett samlet Yahoo-kall. Feil: tomt (grafen utelates)."""
    if "v" in _CACHE:
        return _CACHE["v"]
    out = {}
    try:
        import yfinance as yf
        d = yf.download(sorted(set(tickers)), period="5y", auto_adjust=False, progress=False, group_by="column")["Close"]
        if hasattr(d, "to_frame") and not hasattr(d, "columns"):
            d = d.to_frame(tickers[0])
        d = d.dropna(how="all")
        for t in d.columns:
            ser = d[t]
            first = ser.first_valid_index()
            if first is None:
                continue
            ser = ser.loc[first:]
            out[str(t)] = [(str(k.date()), None if v != v else round(float(v), 4)) for k, v in ser.items()]
    except Exception:
        out = {}
    _CACHE["v"] = out
    _CACHE["date"] = date.today().isoformat()
    return out


def _sma(vals, n=50):
    """50-dagers snitt over de siste 50 handelsdagene MED kurs (manglende dager hoppes over, ikke fylt inn)."""
    out, win = [], []
    for v in vals:
        if v is None:
            out.append(None)
            continue
        win.append(v)
        if len(win) > n:
            win.pop(0)
        out.append(sum(win) / n if len(win) == n else None)
    return out


def _path(xs, ys, fx, fy):
    d, pen = [], False
    for x, y in zip(xs, ys):
        if y is None:
            pen = False
            continue
        d.append(f'{"L" if pen else "M"}{fx(x):.1f},{fy(y):.1f}')
        pen = True
    return "".join(d)


def svg(series, n, mark_date=None, W=600, H=240):
    full = series
    sm = _sma([v for _, v in full])
    s, m = full[-n:], sm[-n:]
    vals = [v for _, v in s if v is not None] + [v for v in m if v is not None]
    if len([v for _, v in s if v is not None]) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1
    pad, L = 6, len(s)
    fx = lambda i: pad + i * (W - 2 * pad) / max(1, L - 1)
    fy = lambda v: pad + (hi - v) * (H - 2 * pad) / (hi - lo)
    xs = range(L)
    p1 = _path(xs, [v for _, v in s], fx, fy)
    p2 = _path(xs, m, fx, fy)
    mk = ""
    if mark_date:
        for i, (dd, v) in enumerate(s):
            if dd == mark_date and v is not None:
                mk = f'<circle cx="{fx(i):.1f}" cy="{fy(v):.1f}" r="4" fill="{COL}" stroke="#0d1117" stroke-width="1.5"><title>Registrert, sluttkurs {dd[8:10]}.{dd[5:7]}</title></circle>'
    fmt = lambda v: f"{v:,.2f}".replace(",", " ").replace(".", ",")
    okv = [v for _, v in s if v is not None]
    lab = f'<span class="hi">{fmt(max(okv))}</span><span class="lo">{fmt(min(okv))}</span>'
    return (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" aria-label="Sluttkurs siste {n} handelsdager">'
            f'<path d="{p2}" fill="none" stroke="{COL}" stroke-width="1.2" stroke-dasharray="4 3" opacity=".7" vector-effect="non-scaling-stroke"/>'
            f'<path d="{p1}" fill="none" stroke="{COL}" stroke-width="1.8" vector-effect="non-scaling-stroke"/>{mk}</svg>'
            f'<div class="pcl">{lab}</div>')


def html(ticker: str, series, mark_date=None, upd: str | None = None) -> str:
    if not series:
        return ""
    panes, btns = [], []
    for lab, n in PERIODS:
        g = svg(series, n, mark_date)
        if not g:
            continue
        on = lab == DEFAULT
        btns.append(f'<button type="button" class="pcb" aria-pressed="{"true" if on else "false"}" data-p="{lab}">{lab}</button>')
        panes.append(f'<div class="pcp" data-p="{lab}"{"" if on else " hidden"}>{g}</div>')
    if not panes:
        return ""
    if not any(b for b in btns if 'aria-pressed="true"' in b):
        btns[-1] = btns[-1].replace('aria-pressed="false"', 'aria-pressed="true"'); panes[-1] = panes[-1].replace(" hidden", "")
    u = f" · oppdatert {upd[8:10]}.{upd[5:7]}" if upd else ""
    return (f'<div class="card pc nofold" id="kursgraf"><div class="pcbs" role="group" aria-label="Periode">{"".join(btns)}</div>{"".join(panes)}'
            f'<p class="mut pcs">Kilde: Yahoo Finance{u}</p>'
            '<script>(()=>{const c=document.getElementById("kursgraf");c.querySelectorAll(".pcb").forEach(b=>b.addEventListener("click",()=>{'
            'c.querySelectorAll(".pcb").forEach(x=>x.setAttribute("aria-pressed",x===b?"true":"false"));'
            'c.querySelectorAll(".pcp").forEach(p=>p.hidden=p.dataset.p!==b.dataset.p)}))})()</script></div>')


CSS = """.pc{padding-top:8px;padding-bottom:8px}.pcbs{display:flex;gap:6px;margin-bottom:6px}.pcb{height:32px;min-width:44px;padding:0 10px;border:1px solid #30363d;border-radius:6px;background:none;color:inherit;font:inherit;cursor:pointer}
.pcb[aria-pressed=true]{border-color:#58a6ff;color:#58a6ff}.pcp{position:relative}.pcp svg{display:block;width:100%;height:240px}.pcl .hi,.pcl .lo{position:absolute;right:4px;font-size:11px;color:#8b949e;font-variant-numeric:tabular-nums}.pcl .hi{top:0}.pcl .lo{bottom:0}
.pcs{font-size:12px;margin:4px 0 0}@media(max-width:599px){.pcp svg{height:180px}.card.pc{padding:6px 10px;margin-bottom:8px}.pcbs{margin-bottom:4px}.pcs{margin-top:2px}}"""


def write_json(ticker, series, path, upd=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ticker": ticker, "source": "Yahoo Finance", "updated": upd, "close": series}, separators=(",", ":")))
