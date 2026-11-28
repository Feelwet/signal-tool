"""Oversiktsaggregat og per-fokus JSON. Skrives til site/flyt/ uten å røre offisielle md5-filer."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .flyt_schema import (
    GICS11,
    UKJENT_SEKTOR,
    canon_type,
    is_selskap,
    is_verk,
    published_only,
    selskaper_paa_land,
    selskaper_paa_vare,
    sorter_varer_etter_selskap,
    ticker_har_publisert_flyt,
    ticker_of,
    year_of,
)

MAX_NODES = 40
MAX_LAND = 6
MAX_SELSKAP = 8
OFFICIAL_ONLY = ("noder.json", "kanter.json", "scenarios.json")


def fokus_filnavn(node_id: str) -> str:
    return re.sub(r"[:/\\\\]", "-", str(node_id)) + ".json"


def _as_list(obj, *keys):
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in keys:
            if isinstance(obj.get(k), list):
                return obj[k]
    return []


def _load_lists(noder, kanter):
    noder = _as_list(noder, "noder", "nodes")
    kanter = _as_list(kanter, "kanter", "edges")
    return noder, kanter


def _pub_count(nid: str, kanter: list) -> int:
    return sum(1 for e in kanter if e.get("fra") == nid or e.get("til") == nid)


def overview_selskaper(noder, kanter) -> list[dict]:
    """Selskapsnoder med minst én publisert kant, sortert flest kanter deretter alfabetisk."""
    noder, kanter = _load_lists(noder, kanter)
    pub = published_only(kanter)
    connected = {e.get("fra") for e in pub} | {e.get("til") for e in pub}
    sels = [n for n in noder if is_selskap(n) and n.get("id") in connected]
    sels.sort(key=lambda n: (-_pub_count(n["id"], pub), str(ticker_of(n) or n.get("navn") or n["id"])))
    return sels


def build_oversikt(noder, kanter, *, universe: list[str] | None = None,
                   sektor_av: dict[str, str] | None = None, navn_av: dict[str, str] | None = None) -> dict:
    noder, kanter = _load_lists(noder, kanter)
    pub = published_only(kanter)
    connected = {e.get("fra") for e in pub} | {e.get("til") for e in pub}
    varer = [n for n in noder if isinstance(n, dict) and canon_type(n.get("type")) == "råvare" and n.get("id") in connected]
    varer = sorter_varer_etter_selskap(noder, pub, varer)
    lands = [n for n in noder if isinstance(n, dict) and n.get("type") == "land" and n.get("id") in connected]
    sels = overview_selskaper(noder, pub)
    counts = {n["id"]: len(selskaper_paa_land(noder, pub, n["id"])) for n in lands}
    deg = {n["id"]: _pub_count(n["id"], pub) for n in lands}
    land_synlige = [n for n in lands if counts.get(n["id"], 0) > 0]
    land_synlige.sort(key=lambda n: (-counts.get(n["id"], 0), -deg.get(n["id"], 0), str(n.get("navn") or n["id"])))
    land_synlige = land_synlige[:MAX_LAND]
    vis_ids = {n["id"] for n in land_synlige}
    andre = [n for n in lands if n["id"] not in vis_ids]
    sel_synlige = sels[:MAX_SELSKAP]
    sel_andre = sels[MAX_SELSKAP:]
    # Aggregat: bare noder som oversikten/Listen trenger, ikke hele grafen.
    keep = varer + land_synlige + sel_synlige
    if andre:
        keep.append({
            "id": "andre:oversikt",
            "type": "andre",
            "navn": f"+{len(andre)} andre",
            "hva_det_er": "Øvrige land, inkludert land uten selskaper.",
            "medlemmer": [{"id": n["id"], "navn": n.get("navn"), "type": "land"} for n in andre],
            "filter": "land",
            "lag": "land",
            "status": "kontekst",
        })
    if sel_andre:
        keep.append({
            "id": "andre:selskaper",
            "type": "andre",
            "navn": f"+{len(sel_andre)} andre",
            "hva_det_er": "Øvrige selskaper med publisert kant.",
            "medlemmer": [{"id": n["id"], "navn": n.get("navn"), "ticker": ticker_of(n), "type": n.get("type")} for n in sel_andre],
            "filter": "selskaper",
            "lag": "selskap",
            "status": "kontekst",
        })
    sektor_av = sektor_av or {}
    navn_av = navn_av or {}
    uni = list(universe or [])
    liste = []
    seen = set()
    by_tick = {ticker_of(n): n for n in noder if ticker_of(n)}
    for t in uni:
        if not t or t in seen:
            continue
        seen.add(t)
        n = by_tick.get(t) or {}
        liste.append({
            "ticker": t,
            "navn": navn_av.get(t) or n.get("navn") or t,
            "id": n.get("id") or f"ticker:{t}",
            "sektor": sektor_av.get(t) or n.get("sektor") or UKJENT_SEKTOR,
            "publisert": ticker_har_publisert_flyt(t, noder, kanter),
        })
    # selskaper i grafen som ikke er i universet (f.eks. NHY) tas med i Liste-indeksen uten å bli univers-k
    for n in noder:
        if not is_selskap(n):
            continue
        t = ticker_of(n)
        if not t or t in seen:
            continue
        seen.add(t)
        liste.append({
            "ticker": t,
            "navn": n.get("navn") or t,
            "id": n["id"],
            "sektor": sektor_av.get(t) or n.get("sektor") or UKJENT_SEKTOR,
            "publisert": ticker_har_publisert_flyt(t, noder, kanter),
            "utenfor_univers": True,
        })
    fokus_index = {}
    for n in noder:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        if n["id"] in connected or is_selskap(n) or n.get("type") in {"land", "vare", "råvare", "energi", "ticker", "selskap"}:
            if n["id"] in connected:
                fokus_index[n["id"]] = "fokus/" + fokus_filnavn(n["id"])
                t = ticker_of(n)
                if t:
                    fokus_index[t] = "fokus/" + fokus_filnavn(n["id"])
    pub_ids = {e.get("fra") for e in pub} | {e.get("til") for e in pub}
    graf_noder = [n for n in noder if isinstance(n, dict) and n.get("id") in pub_ids]
    return {
        "aggregat": True,
        "noder": keep,
        "kanter": [],
        "graf": {"noder": graf_noder, "kanter": pub},
        "counts": counts,
        "varer_n": len(varer),
        "varer_label": f"Varer ({len(varer)})",
        "land_n": len(lands),
        "land_label": f"Land ({len(lands)})",
        "selskaper_n": len(sels),
        "selskaper_label": f"Selskaper ({len(sels)})",
        "selskaper": [{"id": n["id"], "navn": n.get("navn"), "ticker": ticker_of(n), "kanter": _pub_count(n["id"], pub)} for n in sels],
        "liste": liste,
        "fokus_filer": fokus_index,
        "gics": list(GICS11) + [UKJENT_SEKTOR],
        "maks_noder": MAX_NODES,
        "maks_land": MAX_LAND,
        "maks_selskap": MAX_SELSKAP,
    }


def build_fokus(noder, kanter, focus_id: str) -> dict | None:
    noder, kanter = _load_lists(noder, kanter)
    by_id = {n["id"]: n for n in noder if isinstance(n, dict) and n.get("id")}
    focus = by_id.get(focus_id)
    if not focus:
        focus = next((n for n in noder if ticker_of(n) == focus_id), None)
    if not focus:
        return None
    pub = published_only(kanter)
    ids = {focus["id"]}
    fringe = [focus["id"]]
    for _ in range(2):
        nxt = []
        for u in fringe:
            for e in pub:
                v = e["til"] if e.get("fra") == u else (e["fra"] if e.get("til") == u else None)
                if v and v not in ids:
                    ids.add(v)
                    nxt.append(v)
        fringe = nxt
    # Ta med verk med samme materiale som fokusselskapet
    if is_selskap(focus) and focus.get("materiale"):
        for n in noder:
            if is_verk(n) and n.get("materiale") == focus.get("materiale"):
                ids.add(n["id"])
    pack_n = [by_id[i] for i in ids if i in by_id]
    pack_e = [e for e in kanter if e.get("fra") in ids and e.get("til") in ids]
    if len(pack_n) > MAX_NODES * 3:
        # behold nok til at klienten kan pakke; scenen kappes til 40
        pack_n = pack_n[: MAX_NODES * 3]
        keep = {n["id"] for n in pack_n}
        pack_e = [e for e in pack_e if e.get("fra") in keep and e.get("til") in keep]
    return {
        "fokus": focus["id"],
        "noder": pack_n,
        "kanter": pack_e,
        "maks_noder": MAX_NODES,
    }


def write_aggregates(dest: Path, noder, kanter, *, universe: list[str] | None = None,
                     sektor_av: dict[str, str] | None = None, navn_av: dict[str, str] | None = None) -> dict:
    """Skriv oversikt.json og fokus/*.json til dest. Rører ikke de tre offisielle filene."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    noder, kanter = _load_lists(noder, kanter)
    ov = build_oversikt(noder, kanter, universe=universe, sektor_av=sektor_av, navn_av=navn_av)
    (dest / "oversikt.json").write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fdir = dest / "fokus"
    if fdir.exists():
        for p in fdir.glob("*.json"):
            p.unlink()
    fdir.mkdir(exist_ok=True)
    written = []
    seen = set()
    pub = published_only(kanter)
    connected = {e.get("fra") for e in pub} | {e.get("til") for e in pub}
    for nid in connected:
        if not nid or nid in seen:
            continue
        pack = build_fokus(noder, kanter, nid)
        if not pack:
            continue
        seen.add(pack["fokus"])
        fn = fdir / fokus_filnavn(pack["fokus"])
        fn.write_text(json.dumps(pack, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(fn.name)
    return {"oversikt": "oversikt.json", "fokus": written, "n_fokus": len(written)}
