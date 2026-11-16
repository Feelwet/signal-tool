"""AnalBot 16.11: logs/gs_index.csv er append-only. Eksisterende historikk endres aldri automatisk."""
from pathlib import Path

from signaltool import gs_index as G

ROOT = Path(__file__).resolve().parents[1]


def _row(d, g, b, t=None):
    return {"date": d, "gs_index": f"{g:.4f}", "benchmark": f"{b:.4f}", "n_members": 10, "n_no_price": 0,
            "n_invalid": 0, "flag": "", "gs_with_tech": f"{(t or g):.4f}"}


def test_existing_rows_never_change_and_new_rows_chain(tmp_path):
    p = tmp_path / "gs_index.csv"
    G.write_full(p, [_row("2026-11-10", 97.025, 100.336), _row("2026-11-11", 97.4686, 100.7903)])
    before = p.read_bytes()
    # ny omregning med avvikende historikk (hull i hentingen) + én ny dag
    new = [_row("2026-11-10", 96.9491, 100.4059), _row("2026-11-11", 97.0, 100.5), _row("2026-11-12", 98.94, 100.0)]
    assert G.append_only(p, new) == 1
    after = p.read_bytes()
    assert after.startswith(before)
    rs = G.read(p)
    assert [r["date"] for r in rs] == ["2026-11-10", "2026-11-11", "2026-11-12"]
    assert rs[1]["gs_index"] == "97.4686"                      # fryst
    assert rs[2]["gs_index"] == f"{97.4686 * 98.94 / 97.0:.4f}"  # kjedet fra fryst nivå, ikke rå omregning


def test_no_new_rows_leaves_file_byte_identical(tmp_path):
    p = tmp_path / "gs_index.csv"
    G.write_full(p, [_row("2026-11-10", 97.025, 100.336), _row("2026-11-11", 97.4686, 100.7903)])
    before = p.read_bytes()
    assert G.append_only(p, [_row("2026-11-10", 1.0, 1.0), _row("2026-11-11", 2.0, 2.0)]) == 0
    assert p.read_bytes() == before


def test_missing_base_date_appends_nothing(tmp_path):
    p = tmp_path / "gs_index.csv"
    G.write_full(p, [_row("2026-11-11", 97.4686, 100.7903)])
    before = p.read_bytes()
    assert G.append_only(p, [_row("2026-11-12", 99.0, 100.0)]) == 0
    assert p.read_bytes() == before


def test_build_default_is_append_only():
    import inspect
    sig = inspect.signature(G.build)
    assert sig.parameters["rewrite"].default is False
    src = inspect.getsource(G.run)
    assert "rewrite=True" not in src


def test_nightly_commit_keeps_origin_gs_index_unless_pure_append():
    y = (ROOT / ".github/workflows/nightly.yml").read_text()
    assert '"$f" = logs/gs_index.csv ] && ! python3 -c' in y
