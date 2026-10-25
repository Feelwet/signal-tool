"""«Signal-boka»: papirkonto etter rules_v1, append-only logg."""
import csv, subprocess
from pathlib import Path
import pytest
from signaltool import portfolio as P
from signaltool.portfolio_rules import RULES, RULES_VERSION

ROOT = Path(__file__).resolve().parent.parent


def tk(t, cat="kjop", close=100.0, d="2026-10-01", flags=None, score=1.0):
    return {"ticker": t, "category": cat, "score": score, "cat_flags": flags or {}, "stats": {"close": close, "last_date": d}}


def snap(day, *ts):
    return {"date": day, "tickers": list(ts)}


def run(tmp, day, *ts, usd=10.0, bench=None):
    return P.step(snap(day, *ts), usd, bench or {"osebx": 1000.0, "spx": 5000.0}, tmp / "t.csv", tmp / "n.csv")


def rows(tmp):
    return list(csv.DictReader((tmp / "t.csv").open()))


def test_rules_frozen():
    assert RULES_VERSION == "rules_v1" and RULES["version"] == "rules_v1"
    assert RULES["start_nok"] == 1_000_000 and RULES["position_pct"] == 0.05 and RULES["max_positions"] == 20
    assert RULES["cost_each_way"] == 0.002 and RULES["cost_each_way_illiquid"] == 0.005 and RULES["hold_trading_days"] == 60
    assert RULES["stop_loss"] is None and RULES["price_target"] is None and RULES["min_closed_for_returns"] == 30


def test_order_before_fill_then_next_close(tmp_path):
    run(tmp_path, "2026-10-02", tk("ABC.OL", close=100, d="2026-10-01"))
    r = rows(tmp_path)
    assert [x["event"] for x in r] == ["order"] and r[0]["price"] == "" and r[0]["rules_version"] == "rules_v1"
    run(tmp_path, "2026-10-03", tk("ABC.OL", close=110, d="2026-10-02"))
    f = rows(tmp_path)[1]
    assert f["event"] == "fill" and float(f["price"]) == 110 and f["order_id"] == r[0]["order_id"]
    assert abs(float(f["nok_value"]) - 50_000) < 1 and abs(float(f["cost_nok"]) - 100) < 0.01


def test_no_add_hold_not_sold_folg_sold(tmp_path):
    run(tmp_path, "2026-10-02", tk("ABC.OL", d="2026-10-01"))
    run(tmp_path, "2026-10-03", tk("ABC.OL", d="2026-10-02"))
    run(tmp_path, "2026-10-04", tk("ABC.OL", d="2026-10-03"))           # fortsatt Kjøp: ingen ny ordre
    assert [x["event"] for x in rows(tmp_path)] == ["order", "fill"]
    run(tmp_path, "2026-10-05", tk("ABC.OL", cat="hold", d="2026-10-04"))   # Hold: behold
    assert len(rows(tmp_path)) == 2
    run(tmp_path, "2026-10-06", tk("ABC.OL", cat="watch", d="2026-10-05"))  # Følg: selg
    assert rows(tmp_path)[-1]["side"] == "sell" and rows(tmp_path)[-1]["reason"].startswith("under Hold")


def test_red_flag_and_off_list_sell(tmp_path):
    run(tmp_path, "2026-10-02", tk("A.OL", d="2026-10-01"), tk("B.OL", d="2026-10-01"))
    run(tmp_path, "2026-10-03", tk("A.OL", d="2026-10-02"), tk("B.OL", d="2026-10-02"))
    run(tmp_path, "2026-10-04", tk("A.OL", cat="hold", flags={"crash": "x"}, d="2026-10-03"))
    sells = {x["ticker"]: x["reason"] for x in rows(tmp_path) if x["side"] == "sell"}
    assert sells == {"A.OL": "rødt flagg", "B.OL": "under Hold"}


def test_60_trading_days(tmp_path):
    run(tmp_path, "2026-01-02", tk("A.OL", d="2026-01-01"))
    run(tmp_path, "2026-01-03", tk("A.OL", d="2026-01-02"))
    run(tmp_path, "2026-03-26", tk("A.OL", cat="hold", d="2026-03-26"))  # 59 bankdager: behold
    assert rows(tmp_path)[-1]["event"] == "fill"
    run(tmp_path, "2026-03-27", tk("A.OL", cat="hold", d="2026-03-27"))  # 60 bankdager etter 2026-01-02
    assert rows(tmp_path)[-1]["reason"] == "60 handelsdager"


def test_usd_fx_effect_logged_separately(tmp_path):
    run(tmp_path, "2026-10-02", tk("ABC", d="2026-10-01"), usd=10.0)
    run(tmp_path, "2026-10-03", tk("ABC", close=100, d="2026-10-02"), usd=10.0)
    run(tmp_path, "2026-10-04", tk("ABC", cat="watch", close=100, d="2026-10-03"), usd=11.0)
    run(tmp_path, "2026-10-05", tk("ABC", cat="watch", close=100, d="2026-10-04"), usd=11.0)
    s = rows(tmp_path)[-1]
    assert s["event"] == "fill" and s["side"] == "sell" and float(s["fx_effect_nok"]) == pytest.approx(5000, rel=1e-3)


def test_max_20_positions(tmp_path):
    ts = [tk(f"T{i}.OL", d="2026-10-01") for i in range(25)]
    run(tmp_path, "2026-10-02", *ts)
    assert len([x for x in rows(tmp_path) if x["side"] == "buy"]) == 20


def test_illiquid_cost(tmp_path):
    run(tmp_path, "2026-10-02", tk("A.OL", d="2026-10-01", flags={}))
    assert P._cost_rate(True) == 0.005 and P._cost_rate(False) == 0.002


def test_returns_hidden_until_30_closed(tmp_path):
    run(tmp_path, "2026-10-02", tk("A.OL", d="2026-10-01"))
    s = P.summary(tmp_path / "t.csv", tmp_path / "n.csv")
    assert s["returns_visible"] is False and "returns" not in s and "30 lukkede" in s["returns_note"]


def test_append_only_rows_never_change(tmp_path):
    run(tmp_path, "2026-10-02", tk("A.OL", d="2026-10-01"))
    before = (tmp_path / "t.csv").read_text()
    run(tmp_path, "2026-10-03", tk("A.OL", d="2026-10-02"))
    assert (tmp_path / "t.csv").read_text().startswith(before)


@pytest.mark.parametrize("name", ["portfolio_trades.csv", "portfolio_nav.csv"])
def test_committed_log_rows_unchanged(name):
    """Feiler hvis en rad som allerede er committet i git er endret eller slettet."""
    p = ROOT / "logs" / name
    try:
        old = subprocess.run(["git", "show", f"HEAD:logs/{name}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception:
        pytest.skip("ingen committet logg ennå")
    assert p.exists() and p.read_text().startswith(old), f"{name}: eksisterende rader er endret"
    for r in csv.DictReader(p.open()):
        assert r["rules_version"]
