"""om.html – «Om siden» (UxBot-layout og AnalBot-tekst 02.11).

Fire kort: Hva er dette · Slik virker det · Jobbes med nå · På vei. «Jobbes med» og «På vei» leses fra site_config/roadmap.yaml.
Tellere (GS-dager, lukkede handler per bok) leses fra loggene ved bygging; bare låste datoer vises som dato, ellers antallet.
Siden påstår ikke at noe forutsier avkastning. Bare risikonivået er testet (kurssvingninger)."""
from __future__ import annotations

from datetime import date
from html import escape as E
from pathlib import Path

from .config import LOGS

ROOT = Path(__file__).resolve().parent.parent
ROADMAP = ROOT / "site_config" / "roadmap.yaml"
PLANNED = ROOT / "config" / "planlagte_tester.json"   # låste testdatoer (AnalBot 02.11)
STALE_DAYS = 14

CSS = """
.om{max-width:760px;margin:0 auto;font-size:14px;line-height:1.5}
.om h1{font-size:24px;margin:0 0 2px}.om .om-meta{font-size:12px;color:#94a3b8;margin:0 0 6px}
.om .om-lead{font-size:15px;color:#cbd5e1;margin:0 0 12px}
.om-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:12px}
@media(min-width:900px){.om-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.om-c{background:#1c2430;border:1px solid #3b4757;border-top:3px solid #58a6ff;border-radius:12px;padding:16px;min-width:0;box-sizing:border-box}
.om-c h2{font-size:16px;margin:0 0 8px}.om-c p{margin:0 0 8px}
.om-steps{margin:0 0 8px;padding-left:20px}.om-steps li{margin:0 0 8px}.om-steps b{font-size:14px}.om-st{display:flex;align-items:baseline;gap:8px}.om-st .om-chip{margin-left:auto}.om-chip.ok{color:#22c55e;background:rgba(34,197,94,.15)}
.om-li{list-style:none;margin:0;padding:0}.om-li li{display:flex;align-items:baseline;gap:8px;padding:6px 0;border-top:1px solid #3b4757}
.om-li li:first-child{border-top:0}.om-li .tx{flex:1;min-width:0}
.om-chip{flex:none;font-size:12px;line-height:18px;padding:0 8px;border-radius:9px;border:1px solid currentColor}
.om-chip.on{color:#58a6ff}.om-chip.pl{color:#94a3b8}.om-li .dt{flex:none;font-size:12px;color:#94a3b8;margin-left:auto;white-space:nowrap}
.om-old{color:#fdba74;font-size:12px;margin:0 0 8px}
@media(max-width:599px){.om{padding:0 6px}}   /* main har 10 px; totalt 16 px */
"""


def load_roadmap(path: Path = ROADMAP) -> dict:
    import yaml
    try:
        return yaml.safe_load(Path(path).read_text()) or {}
    except Exception:
        return {}


def load_planned(path: Path = PLANNED) -> dict:
    import json
    try:
        return json.loads(Path(path).read_text()).get("tester", {})
    except Exception:
        return {}


def _dm(d) -> str:
    s = str(d or "")[:10]
    return f"{s[8:10]}.{s[5:7]}" if len(s) == 10 else "–"


def counters(logs: Path = LOGS) -> dict:
    """Antall fra loggene ved bygging."""
    from . import gs_index as G
    from . import portfolio as P
    from . import portfolio_books as B
    out = {"gs_days": len(G.read(logs / G.OUT.name)), "gs_need": G.MIN_DAYS_PUBLIC, "books": []}
    for book, tp in [("Kjøp-regler", logs / P.TRADES.name)] + [({"hoy_risiko_v1": "Høy risiko", "kontroll_tilfeldig_v1": "Kontroll"}[b],
                                                             B.paths(b, logs)[0]) for b in B.BOOKS]:
        out["books"].append((book, len(P.state(P._read(tp))["closed"])))
    out["need"] = P.RULES["min_closed_for_returns"]
    return out


STEP_CHIP = {"Temascore": ("pl", "Ikke testet"), "Signaler": ("pl", "Testet, ikke bestått"),
             "Test": ("ok", "Testet: kurssvingninger")}


def _chip(t: str) -> str:
    k, x = STEP_CHIP.get(t, ("", ""))
    return f'<span class="om-chip {k}">{E(x)}</span>' if x else ""


def _vei(x) -> str:
    """paa_vei-punkt: streng, eller {tekst, merknad}. Merknad bare der den er vedtatt (AnalBot 02.11)."""
    tx, m = (x.get("tekst", ""), x.get("merknad")) if isinstance(x, dict) else (str(x), None)
    r = f'<span class="dt">{E(str(m))}</span>' if m else ""
    return f'<li><span class="om-chip pl">Planlagt</span><span class="tx">{E(tx)}</span>{r}</li>'


def html(snap: dict | None = None, logs: Path = LOGS, roadmap: Path = ROADMAP, today: date | None = None,
         planned: Path = PLANNED) -> str:
    from .categories import CAT_NO, TYPE_NO
    from .site_sources import SRC
    rm, c, pt = load_roadmap(roadmap), counters(logs), load_planned(planned)
    built = str((snap or {}).get("generated") or (today or date.today()).isoformat())[:10]
    today = today or date.fromisoformat(built)
    cats = f'{CAT_NO["kjop"]}, {CAT_NO["hold"]} og {CAT_NO["watch"]}'
    sl = [SRC[k] for k in ("Prices (yfinance)", "Oslo Børs Newsweb", "News RSS", "SEC EDGAR Form 4", "Finanstilsynet short register",
                           "US DoD daily contracts (war.gov)")]
    srcs = ", ".join(sl[:-1]) + " og " + sl[-1]
    types = " og ".join(TYPE_NO[k].split(" (")[0] for k in ("ose_contract", "insider_cluster"))
    c1 = ('<div class="om-c" id="om-hva"><h2>Hva er dette</h2>'
          '<p>Et personlig verktøy som sorterer og logger signaler på aksjer i Oslo og USA. '
          'Papirbøkene bruker fiktive penger, og ingenting her forutsier avkastning. <b>Ikke finansiell rådgivning.</b></p></div>')
    steps = [("Kilder", f"Hver natt hentes data fra blant annet {srcs}."),
             ("Temascore", "Nyheter og hendelser samles til en score per tema. Ikke testet."),
             ("Signaler", f"Regler sorterer aksjene i {cats} ut fra signaltyper som {types}. Testet 25.10 uten at noen kategoriregel besto."),
             ("Test", "Bare risikonivået er testet, og bare for kurssvingninger. Testbøkene og GS-indeksen er under måling.")]
    c2 = ('<div class="om-c" id="om-slik"><h2>Slik virker det</h2><ol class="om-steps">'
          + "".join(f'<li><div class="om-st"><b>{E(t)}</b>{_chip(t)}</div>{E(x)}</li>' for t, x in steps) + '</ol><a href="metode.html">Metode →</a></div>')
    items = []
    for it in (rm.get("jobbes_med") or [])[:5]:
        if it.get("type") == "teller" and it.get("kilde") == "gs_index":
            right = f'{min(c["gs_days"], c["gs_need"])} av {c["gs_need"]}'
        elif it.get("type") == "teller" and it.get("kilde") == "papirboker":
            right = ""
        elif it.get("type") == "dato" and pt.get(it.get("test"), {}).get("dato"):
            right = _dm(pt[it["test"]]["dato"])
        else:
            continue
        tx = E(it["tekst"])
        if it.get("kilde") == "papirboker":
            tx += "<br>" + E(", ".join(f"{b} {k}" for b, k in c["books"]) + f' av {c["need"]} lukkede handler')
        items.append(f'<li><span class="om-chip on">Pågår</span><span class="tx">{tx}</span><span class="dt">{E(right)}</span></li>')
    upd = rm.get("oppdatert")
    old = ""
    if upd and (today - date.fromisoformat(str(upd))).days > STALE_DAYS:
        old = f'<p class="om-old">Listen er ikke oppdatert siden {E(_dm(upd))}</p>'
    c3 = f'<div class="om-c" id="om-jobbes"><h2>Jobbes med nå</h2>{old}<ul class="om-li">{"".join(items)}</ul></div>'
    c4 = ('<div class="om-c" id="om-vei"><h2>På vei</h2>' + old + '<ul class="om-li">'
          + "".join(_vei(x) for x in (rm.get("paa_vei") or [])[:5])
          + "</ul></div>")
    return (f'<style>{CSS}</style><div class="om"><h1>Om siden</h1><p class="om-meta">Sist oppdatert {E(_dm(built))}</p>'
            '<p class="om-lead">Signal-tool samler signaler fra åpne kilder og logger hvordan de går. '
            'Det meste er ikke testet ennå, og det står ved hvert punkt.</p>'
            f'<div class="om-grid">{c1}{c2}{c3}{c4}</div></div>')
