"""Konverter CSV fra datainnhentingen til flyt/noder.json og flyt/kanter.json.

Standard kildemappe: /workspace/flyt-nhy-2711/ (nodes.csv, edges.csv, scenarios.csv).
Skriver ingenting hvis CSV-ene mangler. Avviser fiktive data.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from .config import ROOT
from .flyt_schema import FlytError, assert_valid, GODKJENT_FIELDS, kant_id

DEFAULT_SRC = Path("/workspace/flyt-nhy-2711")
DEFAULT_DEST = ROOT / "site" / "flyt"

NODE_FIELDS = (
    "id", "lag", "navn", "hva_det_er", "type", "ticker", "verdi", "enhet", "år",
    "hs_kode", "kilde", "kilde_url", "status", "metode", "grunn",
)
EDGE_FIELDS = (
    "fra", "til", "lag", "verdi", "enhet", "år", "hs_kode", "kilde", "kilde_url",
    "status", "metode", "avvik", "grunn",
)


def _empty(v):
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    return False


def _num(v):
    if _empty(v):
        return None
    s = str(v).strip().replace(" ", "").replace(",", ".")
    try:
        f = float(s)
    except ValueError:
        return v
    return int(f) if f.is_integer() else f


def _year(v):
    if _empty(v):
        return None
    s = str(v).strip()
    if s.isdigit() and len(s) == 4:
        return int(s)
    return s


def _row(src: dict, fields: tuple[str, ...]) -> dict:
    out = {}
    for k in fields:
        if k not in src:
            continue
        v = src[k]
        if k in ("verdi",):
            v = _num(v)
        elif k == "år":
            v = _year(v)
        elif isinstance(v, str):
            v = v.strip()
            if v == "":
                v = None
        if v is not None:
            out[k] = v
        else:
            # kildefelt skal være til stede selv om de er tomme
            if k in ("kilde", "kilde_url", "år", "enhet", "status", "lag", "verdi"):
                out[k] = None if k in ("år", "verdi") else ""
    # alltid ha kildefeltene
    for k in ("kilde", "kilde_url", "år", "enhet", "status", "lag"):
        out.setdefault(k, "" if k not in ("år",) else None)
    if "verdi" in fields:
        out.setdefault("verdi", None)
    return out


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _scenarios(rows: list[dict]) -> list[dict]:
    """Flere rader med samme id = flere setninger."""
    order: list[str] = []
    out: dict[str, dict] = {}
    for r in rows:
        sid = (r.get("id") or "").strip()
        if not sid:
            continue
        if sid not in out:
            order.append(sid)
            noder = [x for x in (r.get("noder") or "").split("|") if x.strip()]
            kanter = [x for x in (r.get("kanter") or "").split("|") if x.strip()]
            out[sid] = {"id": sid, "navn": (r.get("navn") or "").strip(), "noder": noder, "kanter": kanter, "tekst": []}
        sett = (r.get("setning") or "").strip()
        if sett:
            t = {"setning": sett, "kilde_url": (r.get("kilde_url") or "").strip()}
            side = (r.get("side") or "").strip()
            if side:
                t["side"] = side
            out[sid]["tekst"].append(t)
    return [out[i] for i in order]


def convert(src: Path, dest: Path, *, validate: bool = True) -> dict:
    src, dest = Path(src), Path(dest)
    nodes_p, edges_p = src / "nodes.csv", src / "edges.csv"
    if not nodes_p.exists() or not edges_p.exists():
        raise FileNotFoundError(f"mangler {nodes_p.name} eller {edges_p.name} i {src}")
    noder = [_row(r, NODE_FIELDS) for r in _read_csv(nodes_p)]
    kanter = [_row(r, EDGE_FIELDS) for r in _read_csv(edges_p)]
    for e in kanter:
        # Byggesteget setter aldri publisert: true selv, heller ikke om CSV-en har kolonnen.
        e["publisert"] = False
        e.pop("godkjent_dato", None)
        e.pop("kontroll", None)
    scenarioer = _scenarios(_read_csv(src / "scenarios.csv")) if (src / "scenarios.csv").exists() else []
    pack_n = {"noder": noder}
    pack_k = {"kanter": kanter}
    pack_s = {"scenarioer": scenarioer}
    if validate:
        assert_valid(pack_n, pack_k, pack_s, allow_fictive=False)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "noder.json").write_text(json.dumps(pack_n, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dest / "kanter.json").write_text(json.dumps(pack_k, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dest / "scenarioer.json").write_text(json.dumps(pack_s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"noder": noder, "kanter": kanter, "scenarioer": scenarioer, "dest": dest}


def _godkjent_rows(path: Path) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8", newline="") as f:
        for i, r in enumerate(csv.DictReader(f), 1):
            row = {k: (r.get(k) or r.get(k.replace("-", "_")) or "").strip() for k in GODKJENT_FIELDS}
            # tillat kant_id som alias
            if not row["kant-id"]:
                row["kant-id"] = (r.get("kant_id") or r.get("id") or "").strip()
            row["_linje"] = i
            rows.append(row)
    return rows


def apply_godkjent(kanter: list, path: Path) -> list:
    """Sett publisert=true bare fra godkjent.csv (kant-id, lag, dato, kontroll).

    Alle kanter settes først til false, slik at fila er eneste kilde til true.
    Feiler hvis en rad mangler felt eller peker på en ukjent kant.
    """
    path = Path(path)
    rows = _godkjent_rows(path)
    out = []
    for e in kanter:
        n = dict(e)
        n["publisert"] = False
        n.pop("godkjent_dato", None)
        n.pop("kontroll", None)
        out.append(n)
    index: dict[tuple[str, str], list[dict]] = {}
    for e in out:
        index.setdefault((kant_id(e), e.get("lag") or ""), []).append(e)
    err: list[str] = []
    for r in rows:
        kid, lag, dato, kontroll = r["kant-id"], r["lag"], r["dato"], r["kontroll"]
        where = f"godkjent.csv:{r['_linje']}"
        if not kid or not lag or not dato or not kontroll:
            err.append(f"{where}: krever kant-id, lag, dato og kontroll")
            continue
        matches = index.get((kid, lag), [])
        if not matches:
            err.append(f"{where}: ukjent kant {kid} (lag {lag})")
            continue
        for e in matches:
            e["publisert"] = True
            e["godkjent_dato"] = dato
            e["kontroll"] = kontroll
    if err:
        raise FlytError(f"{len(err)} feil i godkjent.csv:\n" + "\n".join(err))
    return out


def apply_godkjent_file(dest: Path, godkjent: Path) -> int:
    dest, godkjent = Path(dest), Path(godkjent)
    pack = json.loads((dest / "kanter.json").read_text(encoding="utf-8"))
    kanter = pack["kanter"] if isinstance(pack, dict) else pack
    out = apply_godkjent(kanter, godkjent)
    if isinstance(pack, dict):
        pack["kanter"] = out
        payload = pack
    else:
        payload = out
    (dest / "kanter.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sum(1 for e in out if e.get("publisert") is True)


def maybe_convert(src: Path = DEFAULT_SRC, dest: Path = DEFAULT_DEST) -> bool:
    src = Path(src)
    if not (src / "nodes.csv").exists() or not (src / "edges.csv").exists():
        return False
    dest = Path(dest)
    convert(src, dest)
    godkjent = dest / "godkjent.csv"
    if not godkjent.exists():
        godkjent = src / "godkjent.csv"
    if godkjent.exists():
        apply_godkjent_file(dest, godkjent)
    return True


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    src = Path(argv[0]) if argv else DEFAULT_SRC
    dest = Path(argv[1]) if len(argv) > 1 else DEFAULT_DEST
    if not (src / "nodes.csv").exists() or not (src / "edges.csv").exists():
        print(f"ingen CSV i {src} – hopper over (ingen filer skrevet til {dest})")
        return 0
    try:
        info = convert(src, dest)
        godkjent = dest / "godkjent.csv"
        if not godkjent.exists():
            godkjent = src / "godkjent.csv"
        n_ok = 0
        if godkjent.exists():
            n_ok = apply_godkjent_file(dest, godkjent)
    except FlytError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"skrev {len(info['noder'])} noder, {len(info['kanter'])} kanter, {len(info['scenarioer'])} scenarioer til {dest}")
    if godkjent.exists():
        print(f"godkjent.csv: {n_ok} kanter publisert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
