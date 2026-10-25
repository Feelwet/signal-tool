"""Sektorchip på tickersiden: Yahoos sektor (aldri gjettet). Lenke til sektorsiden bare når sectors.py har en dokumentert kobling."""
from __future__ import annotations
from html import escape as E

SEC_NO = {"Technology": "Teknologi", "Energy": "Energi", "Financial Services": "Finans", "Healthcare": "Helse", "Industrials": "Industri",
          "Consumer Cyclical": "Syklisk forbruk", "Consumer Defensive": "Defensivt forbruk", "Basic Materials": "Råvarer", "Utilities": "Forsyning",
          "Real Estate": "Eiendom", "Communication Services": "Kommunikasjon"}


def chip(e: dict, pre: str = "../") -> str:
    from .datacov import is_etf
    from .sectors import key_for
    d = e.get("decision") or {}
    if is_etf(e):
        cat = d.get("category") or d.get("quoteType")
        lab = f"Fondstype: {cat}" if cat else "Fondstype: –"
        return f'<span class="sec-chip">{E(lab)}</span>'
    sec = d.get("sector")
    if not sec:
        return '<span class="sec-chip">Sektor: –</span>'
    lab = f"Sektor: {SEC_NO.get(sec, sec)}"   # UxBot 25.10: bare direkte 1:1-oversettelse av Yahoo-sektoren, aldri sektorsidenavn
    k = key_for(e["ticker"])
    return (f'<a class="sec-chip" href="{pre}sektorer.html#{k}">{E(lab)}</a>' if k else f'<span class="sec-chip">{E(lab)}</span>')


SRC = '<p class="sec-src">Sektor: Yahoo Finance</p>'
CSS = (".sec-chip{display:inline-flex;align-items:center;box-sizing:border-box;height:28px;padding:0 10px;margin-right:6px;border-radius:6px;font-size:13px;"
       "font-weight:600;white-space:nowrap;background:#21262d;color:#c9d1d9;border:1px solid #30363d;text-decoration:none;flex:none}"
       "a.sec-chip:hover{border-color:#8b949e}.sec-src{margin:0;font-size:11px;line-height:14px;color:#8b949e}"
       "p.since.rk-line.has-sec{flex-wrap:wrap;row-gap:4px}\n")
