"""Runde 1 (2026-11-28): råvarelag-utkast, hs_map, kilder, tester uten å røre offisielle md5."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from signaltool.config import ROOT
from signaltool.flyt_schema import (
    OFFISIELL_MD5,
    avvik_panel,
    liste_grupper,
    oversikt_varer_og_land,
    selskaper_paa_vare,
    sorter_varer_etter_selskap,
    ticker_har_publisert_flyt,
    validate_edges,
    year_of,
    GICS11,
    UKJENT_SEKTOR,
)
from signaltool.flyt_page import link as flyt_link
from signaltool.flyt_utkast import UTKAST_DIR as UTKAST, avpubliser_ved_endring

OFF_MD5 = {
    "noder.json": "02ab5d48a26842392130afcecb7c72ba",
    "kanter.json": "9f6280057d24f7b869aee39eadd528a2",
    "scenarios.json": "bc2a39146e088416e362a8c46cf16f97",
}

TESTDATA = ROOT / "tests" / "fixtures" / "flyt" / "testdata_60_tickere.json"
HS_MAP = ROOT / "flyt" / "hs_map.csv"
KILDER = ROOT / "flyt" / "tickere_rapportkilde.csv"

HS_TIL_VARE = {
    "0302.14": "vare:laks_fersk_hel",
    "0303.13": "vare:laks_fryst_hel",
    "0304.41": "vare:laks_fersk_filet",
    "0304.81": "vare:laks_fryst_filet",
    "27090001": "vare:kondensat",
    "27090009": "vare:raaolje",
    "2711.11": "vare:naturgass",
    "2711.21": "vare:naturgass",
}


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _utkast():
    n = json.loads((UTKAST / "noder.json").read_text(encoding="utf-8"))
    k = json.loads((UTKAST / "kanter.json").read_text(encoding="utf-8"))
    if isinstance(n, dict):
        n = n.get("noder") or n
    if isinstance(k, dict):
        k = k.get("kanter") or k
    return n, k


def _off():
    n = json.loads(((ROOT / "flyt") / "noder.json").read_text(encoding="utf-8"))
    k = json.loads(((ROOT / "flyt") / "kanter.json").read_text(encoding="utf-8"))
    if isinstance(n, dict):
        n = n.get("noder") or n
    if isinstance(k, dict):
        k = k.get("kanter") or k
    return n, k


def _hs_rows():
    lines = [ln for ln in HS_MAP.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")]
    return list(csv.DictReader(lines))


def test_offisielle_md5_urort():
    for name, expected in OFF_MD5.items():
        got = _md5((ROOT / "flyt") / name)
        assert got == expected, f"offisiell {name} md5 {got} != {expected}"
        site = ROOT / "site" / "flyt" / name
        if site.exists():
            assert _md5(site) == expected, f"site/flyt/{name} avviker fra offisiell md5"


def test_ingen_testdata_id_i_offisielt_eller_site():
    paths = list((ROOT / "flyt").glob("*.json"))
    site = ROOT / "site" / "flyt"
    if site.exists():
        paths += list(site.glob("*.json"))
    paths = [p for p in paths if "utkast" not in p.parts and "testdata" not in p.name]
    bad = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        if "testdata:" in text or '"testdata": true' in text.lower() or '"testdata":true' in text.lower():
            bad.append(str(p))
    assert not bad, f"testdata-id funnet i live/offisielle JSON: {bad}"


def test_testdata_fil_er_merket():
    pack = json.loads(TESTDATA.read_text(encoding="utf-8"))
    assert pack.get("testdata") is True
    assert pack.get("_fiktiv") is True
    noder, kanter = pack["noder"], pack["kanter"]
    tickers = [n for n in noder if str(n.get("id", "")).startswith("testdata:ticker:")]
    assert len(tickers) == 60
    for n in noder:
        assert str(n["id"]).startswith("testdata:")
        assert n.get("testdata") is True
    for e in kanter:
        assert str(e["id"]).startswith("testdata:")
        assert e.get("testdata") is True


def test_alle_utkast_kanter_publisert_false():
    _, k = _utkast()
    assert k, "utkast kanter mangler"
    assert all(e.get("publisert") is False for e in k)


def test_utkast_validerer_mot_sammenslatte_ider():
    on, _ = _off()
    un, uk = _utkast()
    ids = {n["id"] for n in on} | {n["id"] for n in un}
    errors = validate_edges(uk, ids)
    assert errors == []


def test_ingen_negative_verdier_og_samme_aar():
    _, k = _utkast()
    years = {year_of(e) for e in k if year_of(e) not in (None, "")}
    assert years <= {2025, "2025"}
    for e in k:
        v = e.get("verdi")
        if v is not None and v != "":
            assert float(v) >= 0, e.get("id")
        rv = e.get("råverdi")
        if rv is not None and rv != "":
            assert float(rv) >= 0, e.get("id")


def test_land_summerer_til_tabelltotal():
    _, k = _utkast()
    land_kg = defaultdict(float)
    totals = {}
    for e in k:
        if e.get("lag") == "selskap":
            continue
        hs = e.get("hs_kode")
        rv = e.get("råverdi")
        if not hs or rv in (None, ""):
            continue
        if e.get("fra") == "land:NO" and str(e.get("til", "")).startswith("vare:"):
            totals[hs] = float(rv)
        elif e.get("fra") == "land:NO" and str(e.get("til", "")).startswith("land:"):
            land_kg[hs] += float(rv)
    assert totals, "mangler totalkanter land:NO → vare"
    assert land_kg, "mangler landkanter"
    for hs, tot in totals.items():
        assert land_kg[hs] == tot, f"{hs}: landsum {land_kg[hs]} != total {tot}"


def test_hs_map_godkjent_og_innhold():
    rows = _hs_rows()
    koder = {(r.get("hs_kode") or "").strip() for r in rows}
    assert not any(k.startswith("7609") or k.startswith("761") for k in koder)
    assert "2709" not in koder
    assert "27090009" in koder
    assert "27090001" in koder
    keep = {"2606", "2818.20", "7601", "7604", "7605", "7606", "7607", "7608", "2711.11", "2711.21", "0302.14", "0303.13", "0304.41", "0304.81"}
    assert keep <= koder
    for r in rows:
        assert (r.get("godkjent") or "").strip().lower() == "ja", r.get("hs_kode")
    laks = next(r for r in rows if r["hs_kode"] == "0302.14")
    assert laks["vare_navn"] == "Laks, fersk, hel"
    raa = next(r for r in rows if r["hs_kode"] == "27090009")
    assert raa["vare_navn"] == "Råolje"
    kon = next(r for r in rows if r["hs_kode"] == "27090001")
    assert kon["vare_navn"] == "Naturlige gasskondensater"
    assert len(rows) == 16


def test_kilder_eqnr_mowi_spol_jack():
    rows = list(csv.DictReader(KILDER.open(encoding="utf-8")))
    by = {r["ticker"]: r for r in rows}
    eq = by["EQNR.OL"]
    assert (
        "Vi produserer om lag to millioner fat oljeekvivalenter daglig, "
        "hvorav to tredjedeler av vår egenproduksjon kommer fra norsk sokkel."
        in eq["varer_nevnt"]
    )
    mo = by["MOWI.OL"]
    assert "Mowi is the world's largest producer of farm-raised salmon measured by both volume and turnover." in mo["varer_nevnt"]
    spol = by["SPOL.OL"]
    assert spol["fortsatt_notert"].lower().startswith("ja")
    assert "XOSL" in spol["fortsatt_notert"]
    jack = by["JACK.OL"]
    assert "tvangsinnløsning" in jack["fortsatt_notert"].lower()
    assert "ekskludert" in (jack["fortsatt_notert"] + jack.get("status", "")).lower()


def test_ingen_jack_i_selskapsdata():
    n, k = _utkast()
    blob = " ".join(str(x.get("id")) + " " + str(x.get("ticker") or "") for x in n + k)
    assert "JACK" not in blob


def test_kun_godkjente_selskaper_har_varekant():
    n, k = _utkast()
    sel = [e for e in k if e.get("lag") == "selskap"]
    fra = {e["fra"] for e in sel}
    ok = {"EQNR.OL", "AKRBP.OL", "VAR.OL", "MOWI.OL"}
    tick = {x.get("ticker") for x in n if x.get("id") in fra}
    assert tick <= ok
    assert "AKSO.OL" not in tick and "KOG.OL" not in tick
    assert tick == ok


def test_handelskanter_har_kilde_felt():
    _, k = _utkast()
    trade = [e for e in k if e.get("lag") != "selskap"]
    assert trade
    for e in trade:
        assert e.get("kilde_url")
        assert year_of(e) in (2025, "2025")
        assert e.get("enhet")
        assert e.get("hs_kode")
        assert e.get("hentet_tid")
        assert e.get("råverdi") is not None


def test_avpubliser_ved_endring():
    gammel = {"id": "x", "verdi": 100, "publisert": True, "år": 2024}
    out, log = avpubliser_ved_endring(gammel, dict(gammel, verdi=106))
    assert out["publisert"] is False and log and "før 100" in log and "etter 106" in log
    out2, log2 = avpubliser_ved_endring(gammel, dict(gammel, verdi=103))
    assert out2["publisert"] is True and log2 is None
    # YoY >= 40 % uten at 5 %-regelen utløses (gammel=ny=140, forrige år 100)
    cur = {"id": "x", "verdi": 140, "publisert": True, "år": 2025}
    out3, log3 = avpubliser_ved_endring(cur, cur, yoy_forrige=100)
    assert out3["publisert"] is False and log3 and "år-over-år" in log3


def test_selskaper_paa_vare_offisiell_nhy():
    n, k = _off()
    for vid in ("vare:bauksitt", "vare:alumina", "vare:raaaluminium", "vare:halvfabrikata"):
        s = selskaper_paa_vare(n, k, vid)
        assert any("NHY" in x for x in s), (vid, s)
        assert len(s) == 1


def test_vare_sort_stabil_naar_like():
    n, k = _off()
    ov = oversikt_varer_og_land(n, k)
    ids = [v["id"] for v in ov["varer"]]
    again = sorter_varer_etter_selskap(n, k, list(ov["varer"]))
    assert [v["id"] for v in again] == ids
    # upubliserte utkastkanter skal ikke endre offisiell rekkefølge
    un, uk = _utkast()
    merged_n, merged_k = n + un, k + uk
    ov2 = oversikt_varer_og_land(merged_n, merged_k)
    # bare publiserte teller; NHY-varer uendret
    assert [v["id"] for v in ov2["varer"] if v["id"] in ids] == ids


def test_flyt_lenke_bare_ved_publisert_kant():
    n, k = _off()
    assert ticker_har_publisert_flyt("NHY.OL", n, k) is True
    assert ticker_har_publisert_flyt("EQNR.OL", n, k) is False
    assert ticker_har_publisert_flyt("MOWI.OL", n, k) is False
    assert flyt_link("EQNR.OL", noder=n, kanter=k) == ""
    html_nhy = flyt_link("NHY.OL", noder=n, kanter=k)
    assert "Flyt" in html_nhy and "fokus=NHY.OL" in html_nhy


def test_liste_gics_pluss_ukjent():
    noder = [
        {"id": "t:a", "type": "ticker", "ticker": "A.OL", "navn": "A"},
        {"id": "t:b", "type": "ticker", "ticker": "B.OL", "navn": "B"},
    ]
    groups = liste_grupper(noder, {"A.OL": "Energi"})
    names = [g[0] for g in groups]
    assert names[0] == "Energi"
    assert names[-1] == UKJENT_SEKTOR
    assert set(names) <= set(GICS11) | {UKJENT_SEKTOR}


def test_avvik_panel_over_20():
    r = {"verdi": 100, "reporter_land": "NO", "metode": "SSB 08801, rapportør som basis"}
    p = {"verdi": 130, "reporter_land": "DE"}
    out = avvik_panel(r, p)
    assert out is not None
    assert out["scenetykkelse_fra"] == "rapportor"
    assert len(out["rader"]) == 2
    assert out["hoyde_px"][0] == 44
    assert "SSB" in out["metode"]
    assert avvik_panel(r, {"verdi": 110, "reporter_land": "DE"}) is None


def test_manifest_eurostat_mangler_ingen_avvikstilfeller():
    m = json.loads((UTKAST / "manifest.json").read_text(encoding="utf-8"))
    assert "mangler" in str(m.get("eurostat")).lower()
    assert "mangler" in str(m.get("comtrade")).lower() or "nøkkel" in str(m.get("comtrade")).lower()
    assert "ingen tilfeller" in str(m.get("avvik_mot_partner")).lower()
    assert m.get("n_publisert_true") == 0
