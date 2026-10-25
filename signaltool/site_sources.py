"""«Kilder for denne aksjen: X/Y ok · mangler: …» – bare kildene som faktisk mater tickeren (fra marked og signaltyper)."""
from __future__ import annotations
from html import escape as E

SRC = {  # statusnøkkel -> kort navn
    "Prices (yfinance)": "Kurs (Yahoo)", "GDELT 1.0 daily events": "GDELT", "GDELT DOC 2.0 API": "GDELT DOC", "News RSS": "Nyheter (RSS)",
    "SEC EDGAR 8-K full-text": "SEC 8-K", "SEC EDGAR Form 4": "SEC Form 4", "US House PTR (congress trades)": "Kongress (House PTR)",
    "Oslo Børs Newsweb": "Newsweb", "Finanstilsynet short register": "Shortregister", "US DoD daily contracts (war.gov)": "DoD-kontrakter",
    "USAspending awards": "USAspending", "Reddit (public RSS)": "Reddit"}


def keys_for(e: dict) -> list[str]:
    t, pts = e["ticker"], {k for k, v in (e.get("points") or {}).items() if (v or 0) > 0}
    k = ["Prices (yfinance)"]
    if e.get("themes"):
        k += ["GDELT 1.0 daily events", "GDELT DOC 2.0 API", "News RSS", "SEC EDGAR 8-K full-text"]
    if t.endswith(".OL"):
        k += ["Oslo Børs Newsweb", "Finanstilsynet short register"]
    elif "." not in t:   # amerikanske aksjer: innsidekjøp (Form 4) og kongresshandler gjelder alle
        k += ["SEC EDGAR Form 4", "US House PTR (congress trades)"]
        if pts & {"dod_contract", "federal_award"}:
            k += ["US DoD daily contracts (war.gov)", "USAspending awards"]
    if "reddit_mentions" in pts:
        k += ["Reddit (public RSS)"]
    return list(dict.fromkeys(k))


def check(e: dict, status: dict) -> tuple[int, int, list[str]]:
    from .site_extra import source_state
    ks = [k for k in keys_for(e) if k in status and source_state(status[k]) != "skip"]
    bad = [SRC[k] for k in ks if source_state(status[k]) == "fail"]
    if "Prices (yfinance)" in ks and not (e.get("stats") or {}).get("close") and "Kurs (Yahoo)" not in bad:
        bad.insert(0, "Kurs (Yahoo)")
    return len(ks) - len(bad), len(ks), bad


def form4_failed(status: dict) -> bool:
    from .site_extra import source_state
    return "SEC EDGAR Form 4" in status and source_state(status["SEC EDGAR Form 4"]) == "fail"


def line(e: dict, status: dict) -> str:
    ok, n, bad = check(e, status)
    if not n:
        return ""
    txt = f"Kilder for denne aksjen: {ok}/{n} ok · mangler: {', '.join(bad)}" if bad else f"Kilder for denne aksjen: alle kilder ok ({n}/{n})"
    return f'<p class="src-line{" src-bad" if bad else ""}">{E(txt)}</p>'


CSS = ".src-line{margin:0 0 4px;font-size:11px;line-height:14px;color:#8b949e}.src-line.src-bad{color:#92400E}\n"
