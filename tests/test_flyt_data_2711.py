"""AnalBot CLEAR runde 3: offentlige flyt-data er byte-like med godkjente filer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from signaltool.flyt_schema import (
    OFFISIELL_MD5,
    coverage,
    published_only,
    ticker_has_published,
    scenario_chips,
    universe_tickers,
    verk_for,
    verk_label,
)

ROOT = Path(__file__).resolve().parents[1]
FLYT = ROOT / "flyt"


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def test_official_json_md5_and_53_published():
    assert (FLYT / "noder.json").exists() and (FLYT / "kanter.json").exists()
    assert _md5(FLYT / "noder.json") == OFFISIELL_MD5["noder.json"]
    assert _md5(FLYT / "kanter.json") == OFFISIELL_MD5["kanter.json"]
    noder = json.loads((FLYT / "noder.json").read_text(encoding="utf-8"))
    kanter = json.loads((FLYT / "kanter.json").read_text(encoding="utf-8"))
    assert isinstance(noder, list) and isinstance(kanter, list)
    pub = published_only(kanter)
    assert len(pub) == 53
    assert all(e.get("publisert") is True for e in pub)
    # ingen fiktive fixtures i den offentlige mappa
    raw = (FLYT / "noder.json").read_text(encoding="utf-8") + (FLYT / "kanter.json").read_text(encoding="utf-8")
    assert "_fiktiv" not in raw and "example.test" not in raw


def test_official_nhy_tall_kraft_mangler_verk_13_and_chips():
    noder = json.loads((FLYT / "noder.json").read_text(encoding="utf-8"))
    kanter = json.loads((FLYT / "kanter.json").read_text(encoding="utf-8"))
    sc = json.loads((FLYT / "scenarios.json").read_text(encoding="utf-8"))
    nhy = next(n for n in noder if n["id"] == "ticker:NHY.OL")
    texts = [r["tekst"] for r in nhy["tall"]]
    assert any("9 543 GWh" in t for t in texts)
    assert any("2 065 000" in t for t in texts)
    assert all(str(r.get("side")) == "37" for r in nhy["tall"])
    kraft = next(n for n in noder if n["id"] == "energi:kraft-NO")
    assert kraft["status"] == "mangler"
    assert not kraft.get("tall")
    verks = verk_for(noder, kanter, "ticker:NHY.OL")
    assert verk_label(verks) == "Verk (13)"
    chips = scenario_chips(sc)
    assert [n for _, n in chips] == [
        "Energipris i Norge opp",
        "Import til EU ned",
        "Etterspørsel fra bil opp",
    ]
    uni = universe_tickers()
    cov = coverage(noder, kanter, uni)
    assert cov["n"] == len(uni)
    assert "NHY.OL" not in uni
    assert cov["k"] == sum(1 for tck in uni if ticker_has_published(noder, kanter, tck))
    # NHY telles ikke i k når den ikke er på Tickere
    assert cov["k"] == 0
    assert cov["statuslinje"] == (
        f"Råvaredata for {cov['råvare_n']} av {cov['n']} · "
        f"Selskapsdata for {cov['selskap_n']} av {cov['n']}"
    )


def test_site_flyt_is_byte_identical_when_present():
    site = ROOT / "site" / "flyt"
    if not (site / "noder.json").exists():
        return
    for fn, digest in OFFISIELL_MD5.items():
        assert hashlib.md5((site / fn).read_bytes()).hexdigest() == digest
    assert not (site / "aluminium.json").exists()
