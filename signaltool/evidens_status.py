"""Evidensmerke per signaltype (godkjent plan 29.10, tiltak 4; UxBots farger og symboler).

Status, n og dato leses fra signaltool/evidens_signaltyper.json, som er kopiert ordrett fra AnalBots
reports/natt/evidens_signaltyper.md (29.10). Ingen tall beregnes her. DNB-delen er ikke med (DNB forblir ◌).

Visning: «{status} · n={n} · {dato}», der status er én av fire klasser (rekkefølge Bestått, For lav n, Ikke testet,
Ikke bestått). n og dato vises tegn for tegn som i tabellen. Bestått brukes bare for risikonivå."""
from __future__ import annotations

import json
from html import escape as E
from pathlib import Path

PATH = Path(__file__).with_name("evidens_signaltyper.json")
ORDER = ("Bestått", "For lav n", "Ikke testet", "Ikke bestått")
CLS = {"Bestått": "pass", "For lav n": "lown", "Ikke testet": "untested", "Ikke bestått": "fail"}
RISK_ROW = "Risikonivå Lav/Middels/Høy"
RISK_TIP = "Bestått for svingninger, ikke avkastning · n=763 tickere · 25.10"   # UxBot 29.10, ordrett
# Rader som ikke vises: den testede PEAD-rangeringen er ikke live (live-varianten er «Ikke bestått» og skjult), og
# UxBot: «Bestått» bare for risikonivå.
HIDE = ("PEAD topp/topp (testet: topp 20 % rangering, ikke live)",)
KEY_ROW = {
    "insider_cluster": "Innsidekjøp-klynge (US, Form 4)",
    "congress_buys": "Kongresskjøp",
    "ose_contracts": "Kontraktsmelding Oslo (Newsweb)",
    "ose_insider_notices": "Innsidemeldinger Oslo (Newsweb)",
    "federal_award": "Offentlig kontrakt (DoD/USAspending)",
    "dod_contract": "Offentlig kontrakt (DoD/USAspending)",
    "unusual_volume": "Uvanlig volum",
    "price_move": "Uvanlig kursbevegelse",
    "theme_attention": "Tema-oppmerksomhet / temascore",
    "reddit_mentions": "Reddit-omtale",
    "pead": "Sterk kvartalsrapport (PEAD, overraskelse topp 20 %)",
    "pead_tt": "PEAD topp/topp (live: faste 15 %/4 %)",
    "score": "Poengsum (score)",
    "risk": RISK_ROW,
}
_C: dict = {}


def rows() -> list[dict]:
    if "rows" not in _C:
        try:
            _C["rows"] = json.loads(PATH.read_text()).get("rader") or []
        except Exception:
            _C["rows"] = []
    return _C["rows"]


def by_name(name: str) -> dict | None:
    return next((r for r in rows() if r["signaltype"] == name), None)


def klass(status: str) -> str:
    """Rå status fra tabellen -> én av de fire klassene (første ord i statusfeltet)."""
    s = (status or "").strip()
    for k in ("For lav n", "Ikke testet", "Ikke bestått", "Bestått"):
        if s.startswith(k):
            return k
    return "Ikke testet"


def text(r: dict) -> str:
    return f'{klass(r["status"])} · n={r["n"]} · {r["dato"]}'


def chip(r: dict | None, short: bool = False) -> str:
    """Merket. short=True: bare symbol + status (status og n/dato ligger i aria-label og title)."""
    if not r:
        return ""
    k = klass(r["status"])
    t = text(r)
    lab = f"Evidens: {t}"
    body = E(k) if short else E(t)
    tip = ""
    if r["signaltype"] == RISK_ROW:
        from .site import score_info
        tip = score_info("Om risikonivåets evidens", RISK_TIP)
    return f'<span class="evs evs-{CLS[k]}" aria-label="{E(lab)}" title="{E(t)}"><i class="evd" aria-hidden="true"></i>{body}</span>{tip}'


def for_key(key: str, short: bool = False) -> str:
    return chip(by_name(KEY_ROW.get(key, "")), short)


def dot(key: str) -> tuple[str, str]:
    """(symbol-html, aria-tekst) for en signalbrikke i lista. Ukjent nøkkel: ingen symbol."""
    r = by_name(KEY_ROW.get(key, ""))
    if not r:
        return "", ""
    return f'<i class="evd evd-{CLS[klass(r["status"])]}" aria-hidden="true"></i>', f"Evidens: {text(r)}"


# AnalBots tabell: «Dato = siste commit av rapporten, eller filens endringsdato når den ikke er committet (merket *)»
STAR_T = "* dato = filens endringsdato (rapporten er ikke committet)"


def legend(dnb: bool = False) -> str:
    it = "".join(f'<span class="evs evs-{CLS[k]}"><i class="evd" aria-hidden="true"></i>{E(k)}</span>' for k in ORDER)
    d = '<span class="evs evs-dnb"><i class="evd" aria-hidden="true">◌</i>DNB-råd, teller ikke</span>' if dnb else ""
    st = (f'<span class="evs evs-ast">{STAR_T}</span>'
          if any("*" in str(r.get("dato") or "") for r in rows() if r["signaltype"] not in HIDE) else "")
    return f'<p class="evleg" aria-label="Forklaring evidensmerker">Evidens: {it}{d}{st}</p>'


def table_html() -> str:
    """Metode › Evidens per signaltype: alle rader (ikke DNB), sortert Bestått, For lav n, Ikke testet, Ikke bestått; ellers tabellens rekkefølge."""
    rs = [r for r in rows() if r["signaltype"] not in HIDE]
    rs = sorted(rs, key=lambda r: ORDER.index(klass(r["status"])))
    tr = "".join(f'<tr><td>{E(r["signaltype"])}</td><td>{chip(r)}</td><td class="mut">{E(r["rapport"])}</td></tr>' for r in rs)
    return (f'{legend()}'
            '<p class="mut">Status, n og dato er kopiert fra AnalBots oversikt (reports/natt/evidens_signaltyper.md, 29.10). '
            'Bare risikonivået har bestått, og bare for svingninger, ikke avkastning.</p>'
            f'<div class="tw"><table class="evtab"><tr><th>Signaltype</th><th>Evidens</th><th>Rapport</th></tr>{tr}</table></div>')


CSS = (".evs{display:inline-flex;align-items:center;gap:5px;font-size:12px;line-height:16px;color:#c9d1d9;white-space:normal;margin-right:6px}"
       ".evd{display:inline-block;flex:none;width:8px;height:8px;border-radius:50%;box-sizing:border-box;font-style:normal}"
       ".evs-pass .evd,.evd.evd-pass{background:#22c55e}"
       ".evs-fail{color:#94a3b8}.evs-fail .evd,.evd.evd-fail{border:1.5px solid #64748b;background:transparent}"
       ".evs-untested .evd,.evd.evd-untested{background:#94a3b8}"
       ".evs-lown .evd,.evd.evd-lown{border:1.5px solid #f59e0b;background:transparent}"
       ".evs-dnb .evd{width:auto;height:auto;border-radius:0;color:#94a3b8;font-size:12px;line-height:1}"
       ".evleg{font-size:12px;color:var(--mut);display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;margin:4px 0 8px}.evleg .evs{margin:0}"
       ".pill .evd{margin-right:4px;vertical-align:middle;position:relative;top:-1px}\n")
