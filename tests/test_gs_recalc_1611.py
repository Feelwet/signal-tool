"""AnalBot 16.11: GS-historikk 05.10–11.11 omregnet til sluttkurs; tynt omsatt flagges, tas ikke ut."""
import csv
import json
from pathlib import Path

import pytest

from signaltool import gs_index as G

ROOT = Path(__file__).resolve().parents[1]
DAYS = ["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01"]
IDX = {"OSEBX.OL": {d: 100.0 for d in DAYS}}
EX = {"A.OL": "oslo", "B.OL": "oslo", "ZAL.OL": "oslo"}


def row(t, flags=""):
    return {"ticker": t, "category": "watch", "flags": flags}


def test_thin_volume_flagged_but_not_removed():
    """Volum 9810 < 20 000: flagges i gs_invalid, men avkastningen telles (ZAL 05.10)."""
    lists = {"2026-09-27": {"A.OL": row("A.OL"), "ZAL.OL": row("ZAL.OL")}}
    yfp = {"A.OL": {d: 100.0 for d in DAYS},
           "ZAL.OL": {"2026-09-28": 99.4, "2026-09-29": 109.0, "2026-09-30": 109.0, "2026-10-01": 109.0}}
    vols = {"ZAL.OL": {"2026-09-29": 9810}, "A.OL": {"2026-09-29": 100_000}}
    inv = []
    r = G.compute(lists, DAYS, {}, yfp, EX, IDX, invalid_log=inv, volumes=vols)
    thin = [x for x in inv if x.get("type") == "thin_volume"]
    assert len(thin) == 1 and thin[0]["ticker"] == "ZAL.OL" and thin[0]["volume"] == 9810
    assert thin[0]["date"] == "2026-09-29"
    assert r[1]["n_invalid"] == 0
    # ZAL teller: indeksen stiger med om lag halve hoppet (ikke ute som ved |r|>30 %)
    assert r[1]["gs_index"] > 104.0


def test_volume_at_threshold_and_missing_not_flagged():
    lists = {"2026-09-27": {"A.OL": row("A.OL"), "B.OL": row("B.OL")}}
    yfp = {t: {d: 100.0 for d in DAYS} for t in ("A.OL", "B.OL")}
    vols = {"A.OL": {"2026-09-29": 20_000}, "B.OL": {}}  # lik grensen / mangler
    inv = []
    r = G.compute(lists, DAYS, {}, yfp, EX, IDX, invalid_log=inv, volumes=vols)
    assert [x for x in inv if x.get("type") == "thin_volume"] == []
    assert r[1]["n_invalid"] == 0


def test_closed_exchange_zero_volume_not_flagged():
    # 30.09 finnes ikke i OSEBX-serien = stengt børs; volum 0 skal ikke flagges
    lists = {"2026-09-27": {"A.OL": row("A.OL")}}
    days = DAYS
    idx = {"OSEBX.OL": {"2026-09-28": 100, "2026-09-29": 100, "2026-10-01": 100}}  # 30.09 stengt
    yfp = {"A.OL": {"2026-09-28": 100, "2026-09-29": 100, "2026-09-30": 100, "2026-10-01": 110}}
    vols = {"A.OL": {"2026-09-30": 0, "2026-10-01": 50_000}}
    inv = []
    r = G.compute(lists, days, {}, yfp, {"A.OL": "oslo"}, idx, invalid_log=inv, volumes=vols)
    thin = [x for x in inv if x.get("type") == "thin_volume"]
    assert thin == []
    assert r[2]["date"] == "2026-09-30" and r[2]["gs_index"] == pytest.approx(r[1]["gs_index"])  # 0 % da stengt


def test_history_0510_to_1111_is_rebuild_and_prefix_unchanged():
    rs = G.read(ROOT / "logs/gs_index.csv")
    by = {r["date"]: r for r in rs}
    assert [r["date"] for r in rs[:5]] == ["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02"]
    assert by["2026-10-02"]["gs_index"] == "99.9754" and by["2026-10-02"]["benchmark"] == "99.1570"
    assert by["2026-10-05"]["gs_index"] == "99.8638" and by["2026-10-05"]["gs_with_tech"] == "99.5969"
    assert by["2026-11-10"]["gs_index"] == "97.0249" and by["2026-11-10"]["benchmark"] == "100.3439"
    assert by["2026-11-11"]["gs_index"] == "98.7188" and by["2026-11-11"]["benchmark"] == "101.4824"
    assert by["2026-11-11"]["n_no_price"] == "0"
    assert rs[-1]["date"] == "2026-11-11"  # nye dager kjedes av nattkjøringen, ikke skrevet inn her


def test_gs_history_recalc_logged_once_with_1110_values():
    flags = [json.loads(l) for l in (ROOT / "logs/dq_flags.jsonl").read_text().splitlines()
             if l and json.loads(l).get("type") == "gs_history_recalc"]
    assert len(flags) == 1
    f = flags[0]
    assert f["date"] == "2026-11-10" and f["ticker"] == "GS"
    assert f["note"] == "omregnet til sluttkurs 16.11"
    assert (f["level"], f["rebuilt_level"]) == ("97.0456", "97.0249")
    assert (f["benchmark"], f["rebuilt_benchmark"]) == ("100.3439", "100.3439")


def test_chain_from_new_1111_level(tmp_path):
    p, dq = tmp_path / "gs_index.csv", tmp_path / "dq.jsonl"
    # siste fryste rad etter omregningen
    last = {"date": "2026-11-11", "gs_index": "98.7188", "benchmark": "101.4824", "n_members": 61,
            "n_no_price": 0, "n_invalid": 0, "flag": "", "gs_with_tech": "98.6907"}
    G.write_full(p, [last])
    before = p.read_bytes()
    new = [dict(last), {"date": "2026-11-12", "gs_index": "98.4821", "benchmark": "101.1723",
                        "n_members": 63, "n_no_price": 0, "n_invalid": 0, "flag": "", "gs_with_tech": "98.3292"}]
    assert G.append_only(p, new, dq) == 1
    assert p.read_bytes().startswith(before)
    rs = G.read(p)
    assert rs[0]["gs_index"] == "98.7188"  # fryst (nytt) 11.11-nivå uendret
    assert rs[1]["gs_index"] == f"{98.7188 * 98.4821 / 98.7188:.4f}"
    assert rs[1]["benchmark"] == f"{101.4824 * 101.1723 / 101.4824:.4f}"
    fl = [json.loads(l) for l in dq.read_text().splitlines()]
    assert fl[0]["type"] == "gs_chain" and fl[0]["level"] == "98.7188"


def test_zal_0510_thin_volume_in_log_and_tech_jumps_kept():
    with open(ROOT / "logs/gs_invalid.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    jumps = [r for r in rows if r["type"] == "invalid_jump"]
    assert {(r["date"], r["ticker"]) for r in jumps} == {("2026-09-29", "TECH.OL"), ("2026-10-09", "TECH.OL")}
    zal = [r for r in rows if r["ticker"] == "ZAL.OL" and r["date"] == "2026-10-05"]
    assert len(zal) == 1 and zal[0]["type"] == "thin_volume" and zal[0]["volume"] == "9810"
