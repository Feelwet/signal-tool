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
TYPER = frozenset({"selskap", "råvare", "land", "sluttbruk", "verk"})
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
    if node.get("type") == "selskap" and nid:
        return nid
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

    uni = list(dict.fromkeys(universe))
    raw = [t for t in uni if has_kilde(t, "råvare")]
    sel = [t for t in uni if has_kilde(t, "selskap")]
    return {
        "universe": uni,
        "n": len(uni),
        "råvare": raw,
        "selskap": sel,
        "råvare_n": len(raw),
        "selskap_n": len(sel),
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


def scenario_has_chip(s: dict) -> bool:
    """Chip vises bare når scenarioet har minst én setning med kilde_url."""
    if not isinstance(s, dict):
        return False
    for t in s.get("tekst") or []:
        if isinstance(t, dict) and str(t.get("setning") or "").strip() and str(t.get("kilde_url") or "").strip():
            return True
    return False


def scenario_chips(scenarioer) -> list[tuple[str, str]]:
    if isinstance(scenarioer, dict):
        scenarioer = scenarioer.get("scenarioer") or scenarioer.get("scenarios") or []
    out = []
    for s in scenarioer or []:
        if scenario_has_chip(s) and s.get("id") and s.get("navn"):
            out.append((s["id"], s["navn"]))
    return out


def land_tonn(node: dict) -> tuple[int, float] | None:
    if not isinstance(node, dict):
        return None
    if node.get("verdi") in (None, "") or not is_tonn(node.get("enhet")) or node.get("år") in (None, ""):
        return None
    try:
        return int(node["år"]), float(node["verdi"])
    except (TypeError, ValueError):
        return None


def land_for_lag(nodes: list) -> tuple[list, list]:
    """Maks 6 land per lag, sortert etter tonn innenfor samme år.

    Land uten tonn (og land i andre år enn det valgte) går i «+n andre» og rangeres ikke.
    """
    lands = [n for n in nodes if isinstance(n, dict) and n.get("type") == "land"]
    measured, unmeasured = [], []
    for n in lands:
        t = land_tonn(n)
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
    return [n for n in noder if n.get("type") == "verk" and n.get("id") in linked]


def verk_label(verks: list) -> str:
    return f"Verk ({len(verks)})"
