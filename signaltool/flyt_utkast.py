"""Bygg og valider upublisert råvarelag (steg 0/runde 1).

Offisielle flyt/noder.json og flyt/kanter.json røres ikke.
Nye noder og kanter skrives til flyt/utkast_2811/. Alle nye kanter har
publisert=false. Ingen automatiske estimater.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import ROOT
from .flyt_schema import year_of

UTKAST_DIR = ROOT / "flyt" / "utkast_2811"
SSB_LAND = UTKAST_DIR / "kilder" / "ssb08801_eksport_2024_2025.json"
SSB_TOT = UTKAST_DIR / "kilder" / "ssb08801_eksport_total_2024_2025.json"
HS_MAP = ROOT / "flyt" / "hs_map.csv"
OFF_NODER = ROOT / "flyt" / "noder.json"
OFF_KANTER = ROOT / "flyt" / "kanter.json"
SSB_URL = "https://www.ssb.no/statbank/table/08801"
SSB_API = "https://data.ssb.no/api/v0/no/table/08801"
SSB_UPDATED = "2026-05-15T06:00:00Z"

# Varekoder som inngår i hver godkjente HS-rad (gjeldende SSB-koder).
HS_SSB_CODES = {
    "27090009": ["27090009_2001"],
    "27090001": ["27090001_2001"],
    "2711.11": ["27111100_1988"],
    "2711.21": ["27112100_1988"],
    "0302.14": ["03021411_2012", "03021419_2017", "03021490_2017"],
    "0303.13": ["03031311_2012", "03031319_2012", "03031390_2017"],
    "0304.41": ["03044100_2012"],
    "0304.81": ["03048100_2012"],
}

HS_TO_VARE = {
    "27090009": "vare:raaolje",
    "27090001": "vare:kondensat",
    "2711.11": "vare:naturgass",
    "2711.21": "vare:naturgass",
    "0302.14": "vare:laks_fersk_hel",
    "0303.13": "vare:laks_fryst_hel",
    "0304.41": "vare:laks_fersk_filet",
    "0304.81": "vare:laks_fryst_filet",
}

# Selskap -> vare, kun fra godkjent rapport med side. Ingen volum (ikke estimer).
# Runde 1 FLAG 3/4 (AnalBot 13:10): hver kant har egen hel setning med side som nevner varen.
# Kanter uten slik setning er tatt ut (se /workspace/flyt-alle-2811/endringer_flag1-4_2811.md).
SELSKAP_VARER = {
    "EQNR.OL": {
        "navn": "Equinor ASA",
        "url": "https://cdn.sanity.io/files/h61q9gi9/global/cdc5b3a5bc5c8e3bc2f730a8fb5294e1b1bb381f.pdf",
        "kilde": "Equinor årsrapport 2025 (norsk utgave)",
        "side": "12",
        "sitat": "Vi produserer om lag to millioner fat oljeekvivalenter daglig, hvorav to tredjedeler av vår egenproduksjon kommer fra norsk sokkel.",
        "varer": {
            "vare:raaolje": ("12", "Vi produserer om lag to millioner fat oljeekvivalenter daglig, hvorav to tredjedeler av vår egenproduksjon kommer fra norsk sokkel."),
            "vare:naturgass": ("12", "Vi raffinerer og selger råolje og naturgass, inkludert den norske stats andel på norsk sokkel, for eksport av produkter som bensin, diesel, gass og fyringsolje til kontinentale Europa, Storbritannia, Nord-Amerika, Asia og Afrika."),
        },
    },
    "AKRBP.OL": {
        "navn": "Aker BP ASA",
        "url": "https://akerbp.com/wp-content/uploads/2026/03/akerbp-annual-report-2025.pdf",
        "kilde": "Aker BP Annual report 2025",
        "side": "3",
        "sitat": "Aker BP ASA is a company engaged in exploration, field development and production of oil and gas on the Norwegian continental shelf (NCS).",
        "varer": {
            "vare:raaolje": ("3", "Aker BP ASA is a company engaged in exploration, field development and production of oil and gas on the Norwegian continental shelf (NCS)."),
            "vare:naturgass": ("3", "Aker BP ASA is a company engaged in exploration, field development and production of oil and gas on the Norwegian continental shelf (NCS)."),
        },
    },
    "VAR.OL": {
        "navn": "Vår Energi ASA",
        "url": "https://varenergi.no/wp-content/uploads/2026/10/Annual-Reports-2025.pdf",
        "kilde": "Vår Energi Annual Report 2025",
        "side": "6",
        "sitat": "Vår Energi ASA is a leading independent upstream oil and gas company on the highly attractive NCS.",
        "varer": {
            "vare:raaolje": ("6", "Vår Energi ASA is a leading independent upstream oil and gas company on the highly attractive NCS."),
            "vare:naturgass": ("6", "Vår Energi ASA is a leading independent upstream oil and gas company on the highly attractive NCS."),
        },
    },
    "MOWI.OL": {
        "navn": "Mowi ASA",
        "url": "https://mowi.com/wp-content/uploads/2025/05/Mowi-Annual-Report-2025.pdf",
        "kilde": "Mowi Integrated Annual Report 2025",
        "side": "6",
        "sitat": "Mowi is the world's largest producer of farm-raised salmon measured by both volume and turnover.",
        # vare:laks_fryst_hel er tatt ut: ingen hel setning nevner fryst hel laks.
        "varer": {
            "vare:laks_fersk_hel": ("21", "Fresh whole salmon (i.e. primary processed salmon) represented 52.4% of our total revenues in 2025, a slight increase from 50.7% in 2024."),
            "vare:laks_fersk_filet": ("242", "Our secondary processing operations turn the gutted fish into products such as fillets, steaks and other portions of fish - smoked, fresh and frozen."),
            "vare:laks_fryst_filet": ("242", "Our secondary processing operations turn the gutted fish into products such as fillets, steaks and other portions of fish - smoked, fresh and frozen."),
        },
    },
}

KUN_NORSK = "kun norsk rapportering"
SSB_KILDE = f"SSB tabell 08801 ({KUN_NORSK})"
YOY_GRENSE_PCT = 40.0

VARE_META = {
    "vare:raaolje": ("Råolje", "Jordolje og oljer utvunnet av bituminøse mineraler, unnt naturlige gasskondensater, rå (SSB 27090009).", "petroleum"),
    "vare:kondensat": ("Naturlige gasskondensater", "Naturlige gasskondensater (SSB 27090001).", "petroleum"),
    "vare:naturgass": ("Naturgass", "Naturgass, flytende (HS 2711.11) og i gassform (HS 2711.21).", "petroleum"),
    "vare:laks_fersk_hel": ("Laks, fersk, hel", "Atlanterhavslaks, fersk eller kjølt, hel (HS 0302.14).", "laks"),
    "vare:laks_fryst_hel": ("Laks, fryst, hel", "Atlanterhavslaks, fryst, hel (HS 0303.13).", "laks"),
    "vare:laks_fersk_filet": ("Laks, fersk filet", "Fileter av laks, fersk eller kjølt (HS 0304.41).", "laks"),
    "vare:laks_fryst_filet": ("Laks, fryst filet", "Fileter av laks, fryst (HS 0304.81).", "laks"),
}

OSLO = ZoneInfo("Europe/Oslo")


def decode_jsonstat(js: dict) -> list[dict]:
    ids = js["id"]
    dims = js["dimension"]
    sizes = js["size"]
    labels = {}
    for dim in ids:
        cat = dims[dim]["category"]
        index = cat.get("index")
        lab = cat.get("label") or {}
        if isinstance(index, dict):
            inv = {int(v): k for k, v in index.items()}
        elif isinstance(index, list):
            inv = {i: c for i, c in enumerate(index)}
        else:
            inv = {i: list(lab)[i] for i in range(len(lab))}
        labels[dim] = (inv, lab)
    values = js["value"]
    items = values.items() if isinstance(values, dict) else enumerate(values)

    def coords(flat: int):
        out = []
        for s in reversed(sizes):
            out.append(flat % s)
            flat //= s
        return list(reversed(out))

    rows = []
    for flat, val in items:
        if val is None:
            continue
        rec = {"verdi": val}
        for dim, pos in zip(ids, coords(int(flat))):
            inv, lab = labels[dim]
            code = inv[pos]
            rec[dim] = code
            rec[f"{dim}_lab"] = lab.get(code, code)
        rows.append(rec)
    return rows


def load_hs_godkjent(path: Path | None = None) -> list[dict]:
    path = Path(path or HS_MAP)
    rows = []
    with path.open(encoding="utf-8", newline="") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
        for r in csv.DictReader(lines):
            if (r.get("godkjent") or "").strip().lower() == "ja":
                rows.append(r)
    return rows


def official_node_ids(path: Path | None = None) -> set[str]:
    data = json.loads(Path(path or OFF_NODER).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("noder") or data
    return {n["id"] for n in data if isinstance(n, dict) and n.get("id")}


def official_land_names(path: Path | None = None) -> dict[str, str]:
    data = json.loads(Path(path or OFF_NODER).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("noder") or data
    out = {}
    for n in data:
        nid = n.get("id") or ""
        if nid.startswith("land:"):
            out[nid] = n.get("navn") or nid
    return out


def land_id(code: str) -> str:
    if code == "97":
        return "land:uspesifisert"
    return f"land:{code}"


def kg_to_tonn(kg: float) -> float:
    # FLAG 2: lagres alltid med desimaler (kg/1000, ingen avrunding). Scenen runder.
    return float(kg) / 1000.0


def ssb_by_hs_land_year(rows: list[dict]) -> dict:
    """(hs_kode, land, år) -> kg summert over underkoder."""
    code_to_hs = {}
    for hs, codes in HS_SSB_CODES.items():
        for c in codes:
            code_to_hs[c] = hs
    out = defaultdict(float)
    labels = {}
    for r in rows:
        hs = code_to_hs.get(r["Varekoder"])
        if not hs:
            continue
        key = (hs, r["Land"], r["Tid"])
        out[key] += float(r["verdi"])
        labels[(r["Land"], "navn")] = r.get("Land_lab") or r["Land"]
    return out, labels


def ssb_totals(rows: list[dict]) -> dict:
    code_to_hs = {}
    for hs, codes in HS_SSB_CODES.items():
        for c in codes:
            code_to_hs[c] = hs
    out = defaultdict(float)
    for r in rows:
        hs = code_to_hs.get(r["Varekoder"])
        if not hs:
            continue
        out[(hs, r["Tid"])] += float(r["verdi"])
    return out


def assert_sums_match(land_rows: list[dict], tot_rows: list[dict], year: str = "2025") -> list[str]:
    """Land summerer til offisiell landtotal i samme tabell; ingen negative."""
    err = []
    lands, _ = ssb_by_hs_land_year(land_rows)
    tots = ssb_totals(tot_rows)
    # per hs
    sum_l = defaultdict(float)
    for (hs, land, yr), kg in lands.items():
        if kg < 0:
            err.append(f"negativ verdi {hs} {land} {yr}: {kg}")
        if yr == year:
            sum_l[hs] += kg
    for (hs, yr), kg in tots.items():
        if yr != year:
            continue
        s = sum_l[hs]
        if abs(s - kg) > 1e-6:
            err.append(f"{hs} {year}: sum land {s} != tabelltotal {kg}")
    return err


def same_year(kanter: list, year: int = 2025) -> list[str]:
    err = []
    for e in kanter:
        y = year_of(e)
        if y is None:
            continue
        if int(y) != year:
            err.append(f"{e.get('id')}: år {y} != {year}")
    return err


def avpubliser_ved_endring(gammel: dict, ny: dict, *, grense_pct: float = 5.0, yoy_pct: float = 40.0, yoy_forrige=None) -> tuple[dict, str | None]:
    """Hvis en publisert verdi endres mer enn grense, eller YoY >= yoy, avpubliser og logg.

    Returnerer (oppdatert kant, logglinje eller None).
    """
    out = dict(ny)
    if gammel.get("publisert") is not True:
        return out, None
    old_v, new_v = gammel.get("verdi"), ny.get("verdi")
    reason = None
    if old_v not in (None, "") and new_v not in (None, ""):
        old_f, new_f = float(old_v), float(new_v)
        if old_f != 0 and abs(new_f - old_f) / abs(old_f) * 100 > grense_pct:
            reason = f"verdi endret mer enn {grense_pct} % (før {old_v}, etter {new_v})"
    if reason is None and yoy_forrige not in (None, "") and new_v not in (None, ""):
        prev = float(yoy_forrige)
        cur = float(new_v)
        if prev != 0 and abs(cur - prev) / abs(prev) * 100 >= yoy_pct:
            reason = f"år-over-år {abs(cur-prev)/abs(prev)*100:.1f} % >= {yoy_pct} % (før {prev}, etter {cur})"
    if reason:
        out["publisert"] = False
        out["merknad"] = ((out.get("merknad") or "") + f" Avpublisert: {reason}").strip()
        return out, f"{out.get('id')}: {reason}"
    return out, None


def _node(nid, lag, typ, navn, hva, status, kilde, url, side="", merknad="", materiale="", enhet="", ar="", verdi=None):
    n = {
        "id": nid,
        "lag": lag,
        "type": typ,
        "nivaa": 0 if typ == "ticker" else 1,
        "navn": navn,
        "hva_det_er": hva,
        "ticker": nid.split(":", 1)[1] if typ == "ticker" else "",
        "verdi": verdi,
        "enhet": enhet,
        "ar": ar,
        "år": ar,
        "kilde": kilde,
        "kilde_url": url,
        "side": side,
        "status": status,
        "metode": "",
        "merknad": merknad,
        "materiale": materiale,
        "publisert": False,
    }
    return n


def yoy_merke(kg_2025: float, kg_2024: float | None, grense: float = YOY_GRENSE_PCT) -> dict:
    """FLAG 1: merk ny i 2025 eller år-over-år >= 40 %. Endrer aldri publisert."""
    before = None if kg_2024 is None else float(kg_2024)
    after = float(kg_2025)
    out = {"verdi_2024": None if before is None else before / 1000.0, "yoy_pct": None, "yoy_merke": ""}
    if before is None or before == 0:
        out["yoy_merke"] = "ny_i_2025"
        return out
    pct = (after - before) / before * 100.0
    out["yoy_pct"] = round(pct, 1)
    if abs(pct) >= grense:
        out["yoy_merke"] = "yoy_ge_40"
    return out


def yoy_logg(kanter: list) -> list[dict]:
    rows = []
    for e in kanter:
        m = e.get("yoy_merke")
        if not m:
            continue
        rows.append({
            "kant_id": e["id"],
            "hs_kode": e.get("hs_kode", ""),
            "merke": m,
            "for_2024_tonn": "" if e.get("verdi_2024") is None else e["verdi_2024"],
            "etter_2025_tonn": e.get("verdi"),
            "yoy_pct": "" if e.get("yoy_pct") is None else e["yoy_pct"],
            "publisert_for": False,
            "publisert_etter": e.get("publisert"),
            "handling": "merket, forblir upublisert",
        })
    return rows


def build(hentet_tid: str | None = None) -> dict:
    hentet_tid = hentet_tid or datetime.now(OSLO).isoformat(timespec="seconds")
    land_js = json.loads(SSB_LAND.read_text(encoding="utf-8"))
    tot_js = json.loads(SSB_TOT.read_text(encoding="utf-8"))
    land_rows = decode_jsonstat(land_js)
    tot_rows = decode_jsonstat(tot_js)
    sum_err = assert_sums_match(land_rows, tot_rows, "2025")
    if sum_err:
        raise ValueError("SSB-sumavvik:\n" + "\n".join(sum_err))

    lands, land_labs = ssb_by_hs_land_year(land_rows)
    tots = ssb_totals(tot_rows)
    official_ids = official_node_ids()
    official_lands = official_land_names()

    noder = []
    kanter = []

    # vare-noder
    for vid, (navn, hva, mat) in VARE_META.items():
        # summer 2025-eksport for tilhørende HS som nodeverdi (kilde, ikke estimat)
        kg = 0.0
        hss = [hs for hs, v in HS_TO_VARE.items() if v == vid]
        for hs in hss:
            kg += tots.get((hs, "2025"), 0.0)
        noder.append(_node(
            vid, "råvare", "vare", navn, hva, "kilde",
            "SSB tabell 08801", SSB_URL, merknad=f"Norges eksport 2025, SSB 08801, oppdatert {SSB_UPDATED}.",
            materiale=mat, enhet="tonn", ar="2025", verdi=kg_to_tonn(kg),
        ))

    # selskapsnoder
    for ticker, meta in SELSKAP_VARER.items():
        nid = f"ticker:{ticker}"
        noder.append(_node(
            nid, "selskap", "ticker", meta["navn"],
            "Børsnotert selskap med godkjent rapportkilde for råvareknytning.",
            "kilde", meta["kilde"], meta["url"], side=meta["side"],
            merknad=f"Sitat s. {meta['side']}: «{meta['sitat']}»",
        ))
        for vare, (vside, vsitat) in meta["varer"].items():
            kanter.append({
                "id": f"selskap:{ticker}-{vare.split(':',1)[1]}-rapport",
                "fra": nid,
                "til": vare,
                "lag": "selskap",
                "verdi": None,
                "enhet": "",
                "ar": "2025",
                "år": "2025",
                "hs_kode": "",
                "kilde": meta["kilde"],
                "kilde_url": meta["url"],
                "side": vside,
                "status": "kilde",
                "metode": "Kobling kun fra selskapets egen rapport med sidetall. Ingen volum er lagt inn (rapporten gir ikke et tall som kan brukes uten estimat).",
                "avvik": "",
                "reporter": meta["navn"],
                "reporter_land": ticker,
                "merknad": f"«{vsitat}» (s. {vside}).",
                "sitat": vsitat,
                "materiale": VARE_META[vare][2],
                "publisert": False,
                "hentet_tid": hentet_tid,
                "råverdi": None,
            })

    # land-noder som mangler i offisielle data, der det finnes eksport > 0 i 2025
    needed = set()
    for (hs, code, yr), kg in lands.items():
        if yr == "2025" and kg > 0:
            needed.add(code)
    for code in sorted(needed):
        lid = land_id(code)
        if lid in official_ids:
            continue
        navn = land_labs.get((code, "navn"), code)
        noder.append(_node(
            lid, "råvare", "land", navn,
            f"Handelspartner i SSB 08801 (kode {code}).",
            "kilde", "SSB tabell 08801", SSB_URL,
            merknad="Noden er opprettet fordi Norge hadde eksport hit i 2025. Offisiell flyt/noder.json er ikke endret.",
            enhet="", ar="",
        ))

    # handelskanter: NO -> partner, og NO-total -> vare
    counts = defaultdict(int)
    for hs, vare in HS_TO_VARE.items():
        tot_kg = tots.get((hs, "2025"), 0.0)
        kanter.append({
            "id": f"handelsdata:NO-verden:{hs}:eksport:SSB",
            "fra": "land:NO",
            "til": vare,
            "lag": "råvare",
            "verdi": kg_to_tonn(tot_kg),
            "enhet": "tonn",
            "ar": "2025",
            "år": "2025",
            "hs_kode": hs,
            "kilde": SSB_KILDE,
            "kilde_url": SSB_URL,
            "side": "",
            "status": "kilde",
            "metode": f"SSB 08801, eksport 2025, mengde 1 (kg) for {', '.join(HS_SSB_CODES[hs])}, summert og omregnet til tonn, kun norsk rapportering. Offisiell totaltall uten landfordeling stemmer med sum av land (avvik 0).",
            "avvik": "",
            "reporter": "Norge",
            "reporter_land": "NO",
            "merknad": f"SSB oppdatert {SSB_UPDATED}. Eurostat/Comtrade ikke lagt inn i denne runden.",
            "materiale": VARE_META[vare][2],
            "publisert": False,
            "hentet_tid": hentet_tid,
            "råverdi": tot_kg,
            "råenhet": "kg",
        })
        counts[("total", hs)] += 1
        for (h, code, yr), kg in lands.items():
            if h != hs or yr != "2025" or kg <= 0:
                continue
            lid = land_id(code)
            yoy = lands.get((hs, code, "2024"))
            kanter.append({
                "id": f"handelsdata:NO-{code}:{hs}:eksport:SSB",
                "fra": "land:NO",
                "til": lid,
                "lag": "råvare",
                "verdi": kg_to_tonn(kg),
                "enhet": "tonn",
                "ar": "2025",
                "år": "2025",
                "hs_kode": hs,
                "kilde": SSB_KILDE,
                "kilde_url": SSB_URL,
                "side": "",
                "status": "kilde",
                "metode": f"SSB 08801, eksport 2025, mengde 1 (kg) for {', '.join(HS_SSB_CODES[hs])}, omregnet til tonn. Rapportør: Norge, kun norsk rapportering. Partnerstall fra Eurostat/Comtrade er ikke hentet (gratis nøkkel-fri spørring ikke fullført / Comtrade krever nøkkel).",
                "avvik": "",
                "reporter": "Norge",
                "reporter_land": "NO",
                "merknad": f"SSB oppdatert {SSB_UPDATED}. råverdi={kg} kg. 2024={yoy if yoy is not None else 'ingen'} kg.",
                **yoy_merke(kg, yoy),
                "materiale": VARE_META[vare][2],
                "publisert": False,
                "hentet_tid": hentet_tid,
                "råverdi": kg,
                "råenhet": "kg",
            })
            counts[(vare, hs)] += 1

    year_err = same_year(kanter, 2025)
    if year_err:
        raise ValueError("år-avvik:\n" + "\n".join(year_err))
    if any(e.get("publisert") is True for e in kanter):
        raise ValueError("nye kanter skal ha publisert=false")

    manifest = {
        "hentet_tid": hentet_tid,
        "ssb_oppdatert": SSB_UPDATED,
        "kilde_url": SSB_URL,
        "aar": 2025,
        "n_noder": len(noder),
        "n_kanter": len(kanter),
        "n_publisert_true": 0,
        "eurostat": "mangler: Comext-API er tilgjengelig uten nøkkel, men ufiltrert spørring ga 413 (for stor) og korrekt filtrert uttrekk ble ikke fullført i denne runden.",
        "comtrade": "mangler: klassisk API er pensjonert; comtradeapi.un.org krever nøkkel.",
        "avvik_mot_partner": "ingen tilfeller (partnerkilde ikke hentet). Støtte for to rader + metode er forberedt i skjema/tester.",
        "sum_sjekk": "land summerer til offisiell SSB-total for alle 8 HS-grupper i 2025, avvik 0 kg. Ingen negative verdier.",
        "kanter_per_vare_hs": {f"{k[0]}|{k[1]}": v for k, v in sorted(counts.items())},
        "jack_ol": "ekskludert fra selskapsdata",
        "kondensat_selskapskant": "ingen (ikke nevnt i godkjente sitater)",
        "yoy_regel": f"ny_i_2025 eller |endring| >= {YOY_GRENSE_PCT:.0f} % mot 2024; merket i yoy_merke og logget i yoy_logg.csv; publisert forblir false",
        "n_yoy_merket": sum(1 for e in kanter if e.get("yoy_merke")),
        "n_ny_i_2025": sum(1 for e in kanter if e.get("yoy_merke") == "ny_i_2025"),
        "n_yoy_ge_40": sum(1 for e in kanter if e.get("yoy_merke") == "yoy_ge_40"),
        "kildelinje": KUN_NORSK,
        "selskapskanter_tatt_ut": ["MOWI.OL -> vare:laks_fryst_hel (ingen hel setning om fryst hel laks)"],
    }
    return {"noder": noder, "kanter": kanter, "manifest": manifest, "sum_err": sum_err}


def write(dest: Path | None = None, hentet_tid: str | None = None) -> dict:
    dest = Path(dest or UTKAST_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    pack = build(hentet_tid=hentet_tid)
    (dest / "noder.json").write_text(json.dumps(pack["noder"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dest / "kanter.json").write_text(json.dumps(pack["kanter"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    import csv as _csv
    rows = yoy_logg(pack["kanter"])
    with (dest / "yoy_logg.csv").open("w", encoding="utf-8", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=["kant_id", "hs_kode", "merke", "for_2024_tonn", "etter_2025_tonn", "yoy_pct", "publisert_for", "publisert_etter", "handling"])
        w.writeheader()
        w.writerows(rows)
    (dest / "manifest.json").write_text(json.dumps(pack["manifest"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dest / "README.md").write_text(
        "Utkast til råvarelag, runde 1 (2026-11-28, Europe/Oslo).\n\n"
        "ALLE kanter har publisert: false. Denne mappa kopieres IKKE til site/flyt/ av\n"
        "publish_repo_flyt. Offisielle flyt/noder.json, flyt/kanter.json og\n"
        "flyt/scenarios.json skal forbli byte-uendret.\n",
        encoding="utf-8",
    )
    return pack


if __name__ == "__main__":
    pack = write()
    m = pack["manifest"]
    print("noder", m["n_noder"], "kanter", m["n_kanter"], "hentet", m["hentet_tid"])
