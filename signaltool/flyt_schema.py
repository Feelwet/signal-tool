"""Validering av flyt-data: noder, kanter og scenarioer.

To lag, «råvare» og «selskap», kontrolleres hver for seg.
Feiler hvis et påkrevd kildefelt mangler.
status «mangler» krever «grunn», men ikke kilde_url.
status «kontekst» gjelder noder uten tall.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

LAG = frozenset({"råvare", "selskap"})
STATUS = frozenset({"kilde", "estimat", "mangler", "kontekst"})
TYPER = frozenset({"selskap", "råvare", "land", "sluttbruk", "verk", "anlegg", "ticker", "vare", "energi"})
TYPE_ALIAS = {"anlegg": "verk", "ticker": "selskap", "vare": "råvare"}
VERK_TYPER = frozenset({"verk", "anlegg"})
OFFISIELL_MD5 = {
    "noder.json": "02ab5d48a26842392130afcecb7c72ba",
    "kanter.json": "9f6280057d24f7b869aee39eadd528a2",
}
MAX_LAND_PER_LAG = 6
TONN = frozenset({"tonn", "t", "tonnes", "metric tonnes", "metriske tonn", "mt"})

NODE_KEYS = ("id", "lag", "navn", "hva_det_er", "status", "kilde", "kilde_url", "år", "enhet")
EDGE_KEYS = ("fra", "til", "lag", "status", "kilde", "kilde_url", "år", "enhet", "verdi")
GODKJENT_FIELDS = ("kant-id", "lag", "dato", "kontroll")


def kant_id(e: dict) -> str:
    if e.get("id"):
        return str(e["id"])
    return f"{e.get('fra')}>{e.get('til')}"


def is_publisert(e: dict) -> bool:
    return e.get("publisert") is True


def published_only(kanter: list) -> list:
    return [e for e in kanter if isinstance(e, dict) and is_publisert(e)]


class FlytError(ValueError):
    pass


def _load(obj, key: str) -> list:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        if key in obj:
            return list(obj[key])
        # tillat entalls-/flertallsform
        alt = {"noder": "nodes", "kanter": "edges", "scenarioer": "scenarios"}
        if alt.get(key) in obj:
            return list(obj[alt[key]])
    raise FlytError(f"{key}: forventet liste eller objekt med nøkkel {key}")


def load_json(path: Path, key: str) -> tuple[dict | list, list]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw, _load(raw, key)


def _missing_keys(row: dict, keys: tuple[str, ...]) -> list[str]:
    return [k for k in keys if k not in row]


def _status_ok(row: dict, where: str, errors: list[str]) -> None:
    st = row.get("status")
    if st not in STATUS:
        errors.append(f"{where}: ugyldig status {st!r}")
        return
    if st == "mangler":
        if not str(row.get("grunn") or "").strip():
            errors.append(f"{where}: status mangler krever feltet grunn")
    else:
        if not str(row.get("kilde_url") or "").strip():
            errors.append(f"{where}: status {st} krever kilde_url")
        if not str(row.get("kilde") or "").strip():
            errors.append(f"{where}: status {st} krever kilde")
    if st == "estimat" and not str(row.get("metode") or "").strip():
        errors.append(f"{where}: status estimat krever metode i én linje")


def _lag_ok(row: dict, where: str, errors: list[str]) -> str | None:
    lag = row.get("lag")
    if lag not in LAG:
        errors.append(f"{where}: ugyldig lag {lag!r} (råvare|selskap)")
        return None
    return lag


def validate_nodes(noder: list, *, prefix: str = "node") -> list[str]:
    err: list[str] = []
    seen: set[str] = set()
    for i, n in enumerate(noder):
        if not isinstance(n, dict):
            err.append(f"{prefix}[{i}]: ikke et objekt")
            continue
        nid = n.get("id")
        where = f"{prefix}[{nid or i}]"
        miss = _missing_keys(n, NODE_KEYS)
        if miss:
            err.append(f"{where}: mangler kildefelt {', '.join(miss)}")
        if not nid or not str(nid).strip():
            err.append(f"{where}: mangler id")
        elif nid in seen:
            err.append(f"{where}: duplikat id")
        else:
            seen.add(nid)
        if not str(n.get("navn") or "").strip():
            err.append(f"{where}: mangler navn")
        _lag_ok(n, where, err)
        _status_ok(n, where, err)
        typ = n.get("type")
        if typ is not None and typ not in TYPER:
            err.append(f"{where}: ugyldig type {typ!r}")
        if n.get("status") == "kontekst":
            if n.get("verdi") not in (None, ""):
                err.append(f"{where}: status kontekst gjelder noder uten tall")
            tall = n.get("tall")
            if isinstance(tall, list) and any(isinstance(r, dict) and (
                r.get("verdi") not in (None, "") or str(r.get("tekst") or "").strip()
            ) for r in tall):
                err.append(f"{where}: status kontekst gjelder noder uten tall")
        if n.get("verdi") not in (None, "") and n.get("status") not in ("mangler", "kontekst"):
            if n.get("enhet") in (None, "") or n.get("år") in (None, ""):
                err.append(f"{where}: verdi krever enhet og år")
    return err


def validate_edges(kanter: list, node_ids: set[str] | None = None, *, prefix: str = "kant") -> list[str]:
    err: list[str] = []
    for i, e in enumerate(kanter):
        if not isinstance(e, dict):
            err.append(f"{prefix}[{i}]: ikke et objekt")
            continue
        where = f"{prefix}[{e.get('fra') or i}->{e.get('til')}]"
        miss = _missing_keys(e, EDGE_KEYS)
        if miss:
            err.append(f"{where}: mangler kildefelt {', '.join(miss)}")
        _lag_ok(e, where, err)
        _status_ok(e, where, err)
        for end in ("fra", "til"):
            if not e.get(end):
                err.append(f"{where}: mangler {end}")
            elif node_ids is not None and e.get(end) not in node_ids:
                err.append(f"{where}: {end}={e.get(end)!r} finnes ikke i noder")
        if e.get("status") != "mangler" and e.get("verdi") not in (None, ""):
            if e.get("enhet") in (None, "") or e.get("år") in (None, ""):
                err.append(f"{where}: verdi krever enhet og år")
        if "publisert" in e and e.get("publisert") not in (True, False):
            err.append(f"{where}: publisert må være true eller false")
    return err


def validate_scenarios(scenarioer: list, node_ids: set[str] | None = None,
                       edge_keys: set[tuple[str, str]] | None = None) -> list[str]:
    err: list[str] = []
    if not scenarioer:
        return err
    for i, s in enumerate(scenarioer):
        if not isinstance(s, dict):
            err.append(f"scenario[{i}]: ikke et objekt")
            continue
        sid = s.get("id") or i
        if not s.get("id") or not s.get("navn"):
            err.append(f"scenario[{sid}]: mangler id eller navn")
        for nid in s.get("noder") or []:
            if node_ids is not None and nid not in node_ids:
                err.append(f"scenario[{sid}]: ukjent node {nid}")
        for eid in s.get("kanter") or []:
            if isinstance(eid, (list, tuple)) and len(eid) == 2:
                key = (eid[0], eid[1])
            elif isinstance(eid, str) and ">" in eid:
                a, b = eid.split(">", 1)
                key = (a, b)
            else:
                err.append(f"scenario[{sid}]: ugyldig kant-id {eid!r}")
                continue
            if edge_keys is not None and key not in edge_keys:
                err.append(f"scenario[{sid}]: ukjent kant {key}")
        tekst = s.get("tekst") or []
        for j, t in enumerate(tekst):
            if not isinstance(t, dict) or not str(t.get("setning") or "").strip():
                err.append(f"scenario[{sid}].tekst[{j}]: mangler setning")
                continue
            if not str(t.get("kilde_url") or "").strip():
                err.append(f"scenario[{sid}].tekst[{j}]: hver setning krever kilde_url")
    return err


def _by_lag(rows: list, prefix: str) -> dict[str, list]:
    out = {k: [] for k in LAG}
    for r in rows:
        if isinstance(r, dict) and r.get("lag") in LAG:
            out[r["lag"]].append(r)
    return out


def validate(noder, kanter, scenarioer=None, *, allow_fictive: bool = False) -> list[str]:
    """Valider hele datasettet. Returnerer feilliste (tom = ok)."""
    raw_nodes, raw_edges = noder, kanter
    meta = {}
    if isinstance(noder, dict):
        meta.update(noder)
        noder = _load(noder, "noder")
    if isinstance(kanter, dict):
        meta.update(kanter)
        kanter = _load(kanter, "kanter")
    if isinstance(scenarioer, dict):
        meta.update(scenarioer)
        scenarioer = _load(scenarioer, "scenarioer")
    err: list[str] = []
    if meta.get("_fiktiv") and not allow_fictive:
        err.append("fiktive testdata skal ikke ligge i flyt/ eller publiseres")
    # To lag hver for seg
    for lag, rows in _by_lag(noder, "node").items():
        err += validate_nodes(rows, prefix=f"node.{lag}")
    ids = {n.get("id") for n in noder if isinstance(n, dict) and n.get("id")}
    # noder uten gyldig lag fanges i validate_nodes via full liste også
    leftover_n = [n for n in noder if not isinstance(n, dict) or n.get("lag") not in LAG]
    if leftover_n:
        err += validate_nodes(leftover_n, prefix="node")
    for lag, rows in _by_lag(kanter, "kant").items():
        err += validate_edges(rows, ids, prefix=f"kant.{lag}")
    leftover_e = [e for e in kanter if not isinstance(e, dict) or e.get("lag") not in LAG]
    if leftover_e:
        err += validate_edges(leftover_e, ids, prefix="kant")
    if scenarioer:
        edges = {(e.get("fra"), e.get("til")) for e in kanter if isinstance(e, dict)}
        err += validate_scenarios(scenarioer, ids, edges)
    _ = raw_nodes, raw_edges
    return err


def assert_valid(noder, kanter, scenarioer=None, *, allow_fictive: bool = False) -> None:
    err = validate(noder, kanter, scenarioer, allow_fictive=allow_fictive)
    if err:
        raise FlytError(f"{len(err)} feil i flyt-data:\n" + "\n".join(err))


def ticker_of(node: dict) -> str | None:
    t = node.get("ticker")
    if t:
        return str(t).strip()
    nid = str(node.get("id") or "")
    # selskapsnode med ticker-form som id
    if node.get("type") in ("selskap", "ticker") and nid:
        return nid if "." in nid or node.get("type") == "ticker" else nid
    # ticker:NHY.OL
    if nid.startswith("ticker:") and nid.split(":", 1)[1]:
        return nid.split(":", 1)[1]
    return None


def coverage(noder: list, kanter: list, universe: list[str]) -> dict:
    """Råvaredata/selskapsdata for tickere i universet.

    Bare kanter med publisert=true og status=kilde teller. En ticker uten
    publiserte kanter har ingen data for verdikjeden.
    """
    noder = _load(noder, "noder") if not isinstance(noder, list) else noder
    kanter = _load(kanter, "kanter") if not isinstance(kanter, list) else kanter
    by_id = {n["id"]: n for n in noder if isinstance(n, dict) and n.get("id")}
    ticker_ids: dict[str, str] = {}
    for n in noder:
        if not isinstance(n, dict):
            continue
        tck = ticker_of(n)
        if tck:
            ticker_ids[tck] = n["id"]
    adj: dict[str, list[tuple[str, dict]]] = {i: [] for i in by_id}
    for e in published_only(kanter):
        a, b = e.get("fra"), e.get("til")
        if a in adj and b in adj:
            adj[a].append((b, e))
            adj[b].append((a, e))

    def has_kilde(ticker: str, lag: str) -> bool:
        nid = ticker_ids.get(ticker)
        if not nid:
            return False
        seen = {nid}
        frontier = [nid]
        for _hop in range(2):
            nxt = []
            for u in frontier:
                for v, e in adj.get(u, []):
                    if e.get("lag") == lag and e.get("status") == "kilde":
                        return True
                    if v not in seen:
                        seen.add(v)
                        nxt.append(v)
            frontier = nxt
        return False

    uni = list(dict.fromkeys(universe)) if universe is not None else []

    def has_published(ticker: str, lag: str | None = None) -> bool:
        nid = ticker_ids.get(ticker)
        if not nid:
            return False
        seen = {nid}
        frontier = [nid]
        for _hop in range(2):
            nxt = []
            for u in frontier:
                for v, e in adj.get(u, []):
                    if lag is None or e.get("lag") == lag:
                        return True
                    if v not in seen:
                        seen.add(v)
                        nxt.append(v)
            frontier = nxt
        return False

    raw = [t for t in uni if has_published(t, "råvare") or has_kilde(t, "råvare")]
    sel = [t for t in uni if has_published(t, "selskap") or has_kilde(t, "selskap")]
    k = [t for t in uni if has_published(t)]
    return {
        "universe": uni,
        "n": len(uni),
        "k": len(k),
        "med_kant": k,
        "råvare": raw,
        "selskap": sel,
        "råvare_n": len(raw),
        "selskap_n": len(sel),
        "beregnet": True,
        "statuslinje": f"Råvaredata for {len(raw)} av {len(uni)} · Selskapsdata for {len(sel)} av {len(uni)}",
    }


def ticker_has_published(noder, kanter, ticker: str) -> bool:
    """True hvis tickeren har minst én publisert kant innen to hopp."""
    noder = _load(noder, "noder") if not isinstance(noder, list) else noder
    kanter = published_only(_load(kanter, "kanter") if not isinstance(kanter, list) else kanter)
    ids = {n["id"] for n in noder if isinstance(n, dict) and ticker_of(n) == ticker}
    if not ids:
        return False
    for e in kanter:
        if e.get("fra") in ids or e.get("til") in ids:
            return True
        # to hopp: naboens nabo via publiserte kanter
    # BFS 2 hops from company node(s)
    adj: dict[str, list[str]] = {}
    for e in kanter:
        a, b = e.get("fra"), e.get("til")
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen = set(ids)
    frontier = list(ids)
    for _ in range(2):
        nxt = []
        for u in frontier:
            for v in adj.get(u, []):
                if v not in seen:
                    seen.add(v)
                    nxt.append(v)
                    return True
        frontier = nxt
    return False


def universe_tickers(path: Path | None = None) -> list[str]:

    """Tickere i universet: siste dato i logs/list_members.csv."""
    if path is None:
        from .config import LOGS
        path = LOGS / "list_members.csv"
    path = Path(path)
    if not path.exists():
        return []
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    rows = [r for r in rows if r.get("date") and r.get("ticker")]
    if not rows:
        return []
    last = max(r["date"] for r in rows)
    return sorted({r["ticker"] for r in rows if r["date"] == last})


def is_tonn(enhet: str | None) -> bool:
    return str(enhet or "").strip().lower() in TONN


def canon_type(typ: str | None) -> str | None:
    if typ is None:
        return None
    return TYPE_ALIAS.get(typ, typ)


def year_of(row: dict):
    if not isinstance(row, dict):
        return None
    v = row.get("år")
    if v in (None, ""):
        v = row.get("ar")
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return v


def is_verk(node: dict) -> bool:
    return isinstance(node, dict) and node.get("type") in VERK_TYPER


def node_tall(node: dict) -> list[dict]:
    """Tallrader på en node. Flere rader slås aldri sammen."""
    if not isinstance(node, dict):
        return []
    rows = node.get("tall")
    if isinstance(rows, list) and rows:
        return [r for r in rows if isinstance(r, dict)]
    if node.get("verdi") not in (None, "") or node.get("tekst"):
        return [{k: node.get(k) for k in ("verdi", "enhet", "år", "tekst", "kilde", "kilde_url", "status", "metode", "side", "lag", "hs_kode", "grunn") if k in node or k in ("verdi", "enhet", "år", "kilde", "kilde_url", "status")}]
    return []


_IKKE_MEKANISME = frozenset({"kilden beskriver ikke dette", "mangler data"})


def _mekanisme_setning(setning: str, kilde_url: str) -> bool:
    s = str(setning or "").strip()
    u = str(kilde_url or "").strip()
    return bool(s and u and s.lower() not in _IKKE_MEKANISME)


def scenario_has_chip(s: dict) -> bool:
    """Chip vises bare når scenarioet har minst én kildebelagt mekanismesetning."""
    if not isinstance(s, dict):
        return False
    for t in s.get("tekst") or []:
        if isinstance(t, dict) and _mekanisme_setning(t.get("setning"), t.get("kilde_url")):
            return True
    if _mekanisme_setning(s.get("setning"), s.get("kilde_url")):
        return True
    return False


def scenario_chips(scenarioer) -> list[tuple[str, str]]:
    """Én chip per visningsnavn, hvis minst én rad har kildebelagt mekanismesetning."""
    if isinstance(scenarioer, dict):
        scenarioer = scenarioer.get("scenarioer") or scenarioer.get("scenarios") or []
    out = []
    seen = set()
    for s in scenarioer or []:
        navn = s.get("navn")
        if not navn or navn in seen:
            continue
        group = [x for x in scenarioer if x.get("navn") == navn]
        if any(scenario_has_chip(x) for x in group):
            sid = next((x.get("id") for x in group if scenario_has_chip(x) and x.get("id")), s.get("id"))
            if sid:
                out.append((sid, navn))
                seen.add(navn)
    return out


def land_tonn(node: dict, kanter=None) -> tuple[int, float] | None:
    if not isinstance(node, dict):
        return None
    y = year_of(node)
    if node.get("verdi") not in (None, "") and is_tonn(node.get("enhet")) and y is not None:
        try:
            return int(y), float(node["verdi"])
        except (TypeError, ValueError):
            pass
    if kanter is None:
        return None
    kanter = published_only(_load(kanter, "kanter") if not isinstance(kanter, list) else kanter)
    nid = node.get("id")
    by_year: dict[int, float] = {}
    for e in kanter:
        if e.get("status") != "kilde":
            continue
        if not is_tonn(e.get("enhet")) or e.get("verdi") in (None, ""):
            continue
        if e.get("fra") != nid and e.get("til") != nid:
            continue
        ey = year_of(e)
        if ey is None:
            continue
        try:
            by_year[int(ey)] = by_year.get(int(ey), 0.0) + float(e["verdi"])
        except (TypeError, ValueError):
            continue
    if not by_year:
        return None
    year = max(by_year, key=lambda y: (by_year[y], y))
    return year, by_year[year]


def land_for_lag(nodes: list, kanter=None) -> tuple[list, list]:
    """Maks 6 land per lag, sortert etter tonn innenfor samme år.

    Land uten tonn (og land i andre år enn det valgte) går i «+n andre» og rangeres ikke.
    Tonn kan stå på noden eller summeres fra publiserte kanter.
    """
    lands = [n for n in nodes if isinstance(n, dict) and n.get("type") == "land"]
    measured, unmeasured = [], []
    for n in lands:
        t = land_tonn(n, kanter)
        if t:
            measured.append((n, t[0], t[1]))
        else:
            unmeasured.append(n)
    if not measured:
        return [], unmeasured
    years: dict[int, int] = {}
    for _, y, _ in measured:
        years[y] = years.get(y, 0) + 1
    maxn = max(years.values())
    year = max(y for y, c in years.items() if c == maxn)
    ranked = sorted(((n, v) for n, y, v in measured if y == year), key=lambda x: -x[1])
    other_year = [n for n, y, _ in measured if y != year]
    visible = [n for n, _ in ranked[:MAX_LAND_PER_LAG]]
    andre = [n for n, _ in ranked[MAX_LAND_PER_LAG:]] + other_year + unmeasured
    return visible, andre


def verk_for(noder, kanter, company_id: str, *, only_published: bool = True) -> list:
    """Verk og anlegg knyttet til selskapet via (publiserte) kanter."""
    noder = _load(noder, "noder") if not isinstance(noder, list) else noder
    kanter = _load(kanter, "kanter") if not isinstance(kanter, list) else kanter
    if only_published:
        kanter = published_only(kanter)
    linked = set()
    for e in kanter:
        if e.get("fra") == company_id:
            linked.add(e.get("til"))
        elif e.get("til") == company_id:
            linked.add(e.get("fra"))
    out = [n for n in noder if is_verk(n) and n.get("id") in linked]
    focus = next((n for n in noder if n.get("id") == company_id), None)
    mat = focus.get("materiale") if isinstance(focus, dict) else None
    if mat:
        seen = {n["id"] for n in out}
        for n in noder:
            if is_verk(n) and n.get("materiale") == mat and n.get("id") not in seen:
                out.append(n)
                seen.add(n["id"])
    return out


def verk_label(verks: list) -> str:
    return f"Verk ({len(verks)})"


def is_selskap(node: dict) -> bool:
    return isinstance(node, dict) and canon_type(node.get("type")) == "selskap"


def selskap_count_label(n: int) -> str:
    """Samme entall/flertall-logikk som «1 ticker» / «n tickere»."""
    k = int(n or 0)
    return "1 selskap" if k == 1 else f"{k} selskaper"


def selskaper_paa_land(noder: list, kanter: list, land_id: str) -> list[str]:
    """Distinkte selskapsnoder med publisert kant lag=selskap til landet.

    Telles direkte, eller via selskapets eget verk/anlegg i landet
    (f.eks. NHY → Qatalum → Qatar). Teller ikke via råvarelaget.
    Returnerer selskapsnodenes id-er, sortert.
    """
    noder = _load(noder, "noder") if not isinstance(noder, list) else noder
    kanter = published_only(_load(kanter, "kanter") if not isinstance(kanter, list) else kanter)
    by_id = {n["id"]: n for n in noder if isinstance(n, dict) and n.get("id")}
    sel = [e for e in kanter if e.get("lag") == "selskap"]

    def other(e, nid):
        if e.get("fra") == nid:
            return e.get("til")
        if e.get("til") == nid:
            return e.get("fra")
        return None

    found: set[str] = set()
    plants_in_land: set[str] = set()
    for e in sel:
        o = other(e, land_id)
        if not o or o not in by_id:
            continue
        n = by_id[o]
        if is_selskap(n):
            found.add(n["id"])
        elif is_verk(n):
            plants_in_land.add(n["id"])
    for pid in plants_in_land:
        for e in sel:
            o = other(e, pid)
            if o and o in by_id and is_selskap(by_id[o]):
                found.add(o)
    return sorted(found)


def tickers_on_node(noder: list, kanter: list, node_id: str) -> list[str]:
    """Tickere koblet til en node via publiserte kanter (inntil to hopp)."""
    noder = _load(noder, "noder") if not isinstance(noder, list) else noder
    kanter = published_only(_load(kanter, "kanter") if not isinstance(kanter, list) else kanter)
    by_id = {n["id"]: n for n in noder if isinstance(n, dict) and n.get("id")}
    seen: set[str] = set()
    out: list[str] = []
    for e in kanter:
        other = e["til"] if e.get("fra") == node_id else (e["fra"] if e.get("til") == node_id else None)
        if not other:
            continue
        tck = ticker_of(by_id.get(other) or {})
        if tck and tck not in seen:
            seen.add(tck)
            out.append(tck)
    adj: dict[str, list[str]] = {}
    for e in kanter:
        a, b = e.get("fra"), e.get("til")
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    for n in noder:
        tck = ticker_of(n)
        if not tck or n.get("id") == node_id or tck in seen:
            continue
        seen_h = {n["id"]}
        fringe = [n["id"]]
        found = False
        for _ in range(2):
            nxt = []
            for u in fringe:
                for v in adj.get(u, []):
                    if v == node_id:
                        found = True
                        break
                    if v not in seen_h:
                        seen_h.add(v)
                        nxt.append(v)
                if found:
                    break
            if found:
                break
            fringe = nxt
        if found:
            seen.add(tck)
            out.append(tck)
    return out


def oversikt_varer_og_land(noder: list, kanter: list) -> dict:
    """Oversikten: venstre Varer (n), høyre topp 6 land etter selskapsantall + «+n andre».

    Land med 0 selskaper går alltid i +n andre og fyller ikke de 6 plassene.
    Varer telles fortsatt med tickers_on_node.
    """
    noder = _load(noder, "noder") if not isinstance(noder, list) else noder
    pub = published_only(_load(kanter, "kanter") if not isinstance(kanter, list) else kanter)
    connected = {e.get("fra") for e in pub} | {e.get("til") for e in pub}
    varer = [n for n in noder if isinstance(n, dict) and canon_type(n.get("type")) == "råvare" and n.get("id") in connected]
    varer = sorter_varer_etter_selskap(noder, pub, varer)
    lands = [n for n in noder if isinstance(n, dict) and n.get("type") == "land" and n.get("id") in connected]
    counts: dict[str, int] = {}
    deg: dict[str, int] = {}
    for n in varer:
        nid = n["id"]
        counts[nid] = len(set(tickers_on_node(noder, pub, nid)))
        deg[nid] = sum(1 for e in pub if e.get("fra") == nid or e.get("til") == nid)
    for n in lands:
        nid = n["id"]
        counts[nid] = len(selskaper_paa_land(noder, pub, nid))
        deg[nid] = sum(1 for e in pub if e.get("fra") == nid or e.get("til") == nid)
    with_t = [n for n in lands if counts.get(n["id"], 0) > 0]
    with_t.sort(key=lambda n: (-counts.get(n["id"], 0), -deg.get(n["id"], 0), str(n.get("navn") or n["id"])))
    visible = with_t[:MAX_LAND_PER_LAG]
    vis_ids = {n["id"] for n in visible}
    andre = [n for n in lands if n["id"] not in vis_ids]
    return {
        "varer": varer,
        "varer_n": len(varer),
        "varer_label": f"Varer ({len(varer)})",
        "land_n": len(lands),
        "land_label": f"Land ({len(lands)})",
        "land_synlige": visible,
        "andre": andre,
        "counts": counts,
    }


def round_tonn_scene(verdi) -> int:
    """Vanlig avrunding av tonn til heltall for scenen: 0,5 rundes opp."""
    import math
    return math.floor(float(verdi) + 0.5)



def selskaper_paa_vare(noder: list, kanter: list, vare_id: str) -> list[str]:
    """Distinkte selskapsnoder med publisert kant lag=selskap til varen fra egen rapport.

    Telles direkte (ticker/selskap → vare) eller via selskapets eget verk/anlegg
    (f.eks. NHY → Paragominas → Bauksitt, også når eierskapet vises gjennom
    verk_for / samme materiale, som i offisiell Hydro-graf).
    Teller ikke via handels-/råvarekanter.
    """
    noder = _load(noder, "noder") if not isinstance(noder, list) else noder
    raw_k = _load(kanter, "kanter") if not isinstance(kanter, list) else kanter
    kanter = published_only(raw_k)
    by_id = {n["id"]: n for n in noder if isinstance(n, dict) and n.get("id")}
    sel = [e for e in kanter if e.get("lag") == "selskap"]

    def other(e, nid):
        if e.get("fra") == nid:
            return e.get("til")
        if e.get("til") == nid:
            return e.get("fra")
        return None

    found: set[str] = set()
    plants: set[str] = set()
    for e in sel:
        o = other(e, vare_id)
        if not o or o not in by_id:
            continue
        n = by_id[o]
        if is_selskap(n):
            found.add(n["id"])
        elif is_verk(n):
            plants.add(n["id"])
    # eierkant plant ↔ selskap
    for pid in plants:
        for e in sel:
            o = other(e, pid)
            if o and o in by_id and is_selskap(by_id[o]):
                found.add(o)
    # offisiell Hydro: Paragominas/Alunorte har publisert produksjonskant til
    # varen, men ingen publisert eierkant til ticker:NHY.OL. Ta med selskap
    # der verket inngår i verk_for (koblet eller samme materiale).
    if plants:
        for n in noder:
            if not is_selskap(n):
                continue
            vset = {v["id"] for v in verk_for(noder, raw_k, n["id"], only_published=True)}
            if plants & vset:
                found.add(n["id"])
    return sorted(found)
def sorter_varer_etter_selskap(noder: list, kanter: list, varer: list) -> list:
    """Sorter varer etter antall distinkte selskapsnoder med publisert rapportkant.

    Lik telling beholder opprinnelig rekkefølge (stabilt), så offisiell NHY-rekkefølge
    ikke endres når alle fire varer har samme antall.
    """
    keyed = []
    for i, n in enumerate(varer):
        c = len(selskaper_paa_vare(noder, kanter, n["id"]))
        keyed.append(( -c, i, n))
    keyed.sort()
    return [n for _, _, n in keyed]


def ticker_har_publisert_flyt(ticker: str, noder: list, kanter: list) -> bool:
    """True hvis tickeren har minst én publisert kant (direkte på selskapsnoden)."""
    noder = _load(noder, "noder") if not isinstance(noder, list) else noder
    kanter = published_only(_load(kanter, "kanter") if not isinstance(kanter, list) else kanter)
    ids = {n["id"] for n in noder if isinstance(n, dict) and ticker_of(n) == ticker}
    if not ids:
        return False
    for e in kanter:
        if e.get("fra") in ids or e.get("til") in ids:
            return True
    return False


# Samme 11 navn som tickerlist.SEKTOR_NAV (offisiell norsk GICS på siden). Ikke finn på egne.
GICS11 = (
    "Energi",
    "Råvarer",
    "Industri",
    "Syklisk forbruk",
    "Defensivt forbruk",
    "Helse",
    "Finans",
    "Teknologi",
    "Kommunikasjon",
    "Forsyning",
    "Eiendom",
)
UKJENT_SEKTOR = "Ukjent sektor"


def liste_grupper(noder: list, sektor_av: dict[str, str] | None = None) -> list[tuple[str, list[dict]]]:
    """Liste gruppert etter de 11 GICS-navnene + «Ukjent sektor». Ukjent mapping → ukjent sektor."""
    sektor_av = sektor_av or {}
    noder = [n for n in noder if isinstance(n, dict) and is_selskap(n)]
    buckets = {n: [] for n in GICS11}
    buckets[UKJENT_SEKTOR] = []
    for n in noder:
        t = ticker_of(n) or n.get("id")
        s = sektor_av.get(t) or sektor_av.get(n.get("id")) or UKJENT_SEKTOR
        if s not in buckets:
            s = UKJENT_SEKTOR
        buckets[s].append(n)
    out = []
    for name in list(GICS11) + [UKJENT_SEKTOR]:
        if buckets[name]:
            out.append((name, buckets[name]))
    return out


def avvik_panel(rapportor: dict, partner: dict | None, *, grense: float = 20.0) -> dict | None:
    """Hvis avvik >20 % mot partner: to rader + metodelinje. Scenetykkelse fra rapportør."""
    if not partner or rapportor.get("verdi") in (None, "") or partner.get("verdi") in (None, ""):
        return None
    a, b = float(rapportor["verdi"]), float(partner["verdi"])
    if a == 0:
        return None
    pct = abs(b - a) / abs(a) * 100
    if pct <= grense:
        return None
    return {
        "avvik_pct": pct,
        "scenetykkelse_fra": "rapportor",
        "rader": [
            {"etikett": f"Rapportør ({rapportor.get('reporter_land') or rapportor.get('land') or ''}):", "verdi": rapportor["verdi"]},
            {"etikett": f"Partner ({partner.get('reporter_land') or partner.get('land') or ''}):", "verdi": partner["verdi"]},
        ],
        "metode": (rapportor.get("metode") or partner.get("metode") or "").strip(),
        "hoyde_px": (44, 44, "13/18"),
    }
