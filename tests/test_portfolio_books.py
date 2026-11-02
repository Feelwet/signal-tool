"""Papirbok 2 (hoy_risiko_v1, eksperimentell) og 3 (kontroll_tilfeldig_v1) ved siden av Signal-boka (bok 1, uendret)."""
import csv
from signaltool import portfolio as P
from signaltool import portfolio_books as B
from signaltool.portfolio_rules import RULES, RULES_VERSION


def tk(t, cat="watch", score=1.0, r20=0.05, close=100.0, d="2026-10-01", flags=None, types=None, sector="Energy"):
    return {"ticker": t, "category": cat, "score": score, "cat_flags": flags or {}, "cat_types": types or {},
            "decision": {"sector": sector}, "stats": {"close": close, "last_date": d, "ret_20d": r20}}


def snap(day, *ts, theme_rows=()):
    s = {"date": day, "tickers": list(ts)}
    if theme_rows:
        s["theme_maps"] = {"x": {"rows": list(theme_rows)}}
    return s


def rows(p):
    return list(csv.DictReader(p.open())) if p.exists() else []


def test_rules_locked_spec():
    H, K = B.BOOKS["hoy_risiko_v1"], B.BOOKS["kontroll_tilfeldig_v1"]
    assert H["experimental"] is True and H["top_n"] == 10 and H["hold_trading_days"] == 20
    for R in (H, K):
        assert R["position_pct"] == 0.05 and R["max_positions"] == 20 and R["sell_on_red_flag"]
        assert R["cost_each_way"] == 0.002 and R["cost_each_way_illiquid"] == 0.005 and R["min_closed_for_returns"] == 30
        assert R["start_nok"] == RULES["start_nok"]
    assert K["hold_trading_days"] == 20 and K["version"] == "kontroll_tilfeldig_v1"


def test_book1_unchanged():
    assert RULES_VERSION == "rules_v1" and RULES["buy_category"] == "kjop" and RULES["hold_trading_days"] == 60
    assert RULES["sell_on_folg_or_lower"] is True and "experimental" not in RULES and "top_n" not in RULES


def test_candidates_top10_filter_and_categories():
    ts = [tk(f"W{i}.OL", score=float(i)) for i in range(15)]                     # 15 Følg, score 0..14
    ts += [tk("NEG.OL", score=99, r20=-0.01), tk("ZERO.OL", score=98, r20=0.0), tk("NONE.OL", score=97, r20=None)]
    ts += [tk("KJOP.OL", cat="kjop", score=100), tk("H.OL", cat="hold", score=50), tk("NOSCORE.OL", score=None)]
    c = B.hoy_candidates(B.universe(snap("2026-10-02", *ts)))
    got = [e["ticker"] for e in c]
    assert len(got) == 10 and got[0] == "H.OL" and got[1:] == [f"W{i}.OL" for i in range(14, 5, -1)]
    assert not {"NEG.OL", "ZERO.OL", "NONE.OL", "KJOP.OL", "NOSCORE.OL"} & set(got)


def test_same_universe_tema_excluded_in_both():
    tr = {"ticker": "TEMA.OL", "has_data": True, "close": 10.0, "asof": "2026-10-01", "flags": {}}
    ts = [tk("A.OL"), tk("K.OL", cat="kjop"), tk("H.OL", cat="hold"), tk("T2.OL", cat="tema", score=5),
          tk("NEG.OL", r20=-0.1), tk("NOS.OL", score=None)]
    s = snap("2026-10-02", *ts, theme_rows=[tr])
    u = B.universe(s)
    assert sorted((e["ticker"], e["category"]) for e in u) == [("A.OL", "watch"), ("H.OL", "hold")]
    h = B.hoy_candidates(u)
    c, _ = B.control_candidates(u, len(h), "2026-10-02")
    assert {e["ticker"] for e in c} == {e["ticker"] for e in h} == {"A.OL", "H.OL"}   # hele universet trukket når n = univers
    assert not {"TEMA.OL", "T2.OL", "K.OL"} & {e["ticker"] for e in h + c}


def test_control_draws_only_from_book2_universe():
    ts = [tk(f"T{i}.OL", score=float(i), r20=(0.1 if i % 2 else -0.1)) for i in range(60)]
    u = B.universe(snap("2026-10-02", *ts))
    assert len(u) == 30 and all(e["stats"]["ret_20d"] > 0 for e in u)
    for d in ("2026-10-02", "2026-10-03", "2026-10-04"):
        c, _ = B.control_candidates(u, 10, d)
        assert len(c) == 10 and {e["ticker"] for e in c} <= {e["ticker"] for e in u}


def test_control_same_n_same_universe_reproducible_seed():
    ts = [tk(f"T{i}.OL", score=float(i), r20=(0.1 if i % 2 else -0.1)) for i in range(40)]
    u = B.universe(snap("2026-10-02", *ts))
    n = len(B.hoy_candidates(u))
    a, sa = B.control_candidates(u, n, "2026-10-02")
    b, sb = B.control_candidates(list(reversed(u)), n, "2026-10-02")   # rekkefølge spiller ingen rolle
    c, sc = B.control_candidates(u, n, "2026-10-03")
    assert n == 10 and len(a) == n and sa == sb == B.seed_for("2026-10-02") and sc != sa
    assert [e["ticker"] for e in a] == [e["ticker"] for e in b] and {e["ticker"] for e in a} <= {e["ticker"] for e in u}
    assert [e["ticker"] for e in a] != [e["ticker"] for e in c] or sa != sc
    small, _ = B.control_candidates(u[:3], 10, "2026-10-02")
    assert len(small) == 3


def test_run_logs_both_books_with_reasons_and_bench(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "risk_levels", lambda: {"A.OL": {"level": "Høy", "date": "2026-09-30"}})
    ts = [tk("A.OL", score=5, types={"pead": 1, "volume": 1}), tk("B.OL", score=4, r20=-0.2), tk("C.OL", cat="hold", score=3)]
    st = {}
    B.run(snap("2026-10-02", *ts), st, 10.0, {"osebx": 1500.0, "spx": 6000.0}, logs=tmp_path)
    h = rows(tmp_path / "portfolio_hoy_risiko_v1_trades.csv")
    assert [(r["ticker"], r["event"], r["side"]) for r in h] == [("A.OL", "order", "buy"), ("C.OL", "order", "buy")]
    a = h[0]
    assert a["rules_version"] == "hoy_risiko_v1" and a["score"] == "5" and a["signal_types"] == "pead|volume"
    assert a["risk_level"] == "Høy" and a["risk_date"] == "2026-09-30" and h[1]["risk_date"] == "" and a["sector"] == "Energy" and a["category"] == "watch" and a["ret_20d"] == "0.05"
    assert a["bench"].startswith("OSEBX") and float(a["bench_signal"]) == 1500.0 and a["bench_entry"] == ""
    assert list(h[0])[:len(P.T_COLS)] == P.T_COLS
    k = rows(tmp_path / "portfolio_kontroll_tilfeldig_v1_trades.csv")
    assert len(k) == 2 and all(r["reason"] == f"tilfeldig seed={B.seed_for('2026-10-02')}" for r in k)
    cands = rows(tmp_path / "portfolio_candidates.csv")
    assert [(c["book_id"], c["n"]) for c in cands] == [("hoy_risiko_v1", "2"), ("kontroll_tilfeldig_v1", "2")]
    assert cands[1]["seed"] == str(B.seed_for("2026-10-02")) and cands[0]["universe_n"] == cands[1]["universe_n"] == "2"
    assert cands[0]["n"] == cands[1]["n"] and "B.OL" not in cands[1]["tickers"]
    assert len(rows(tmp_path / "portfolio_hoy_risiko_v1_nav.csv")) == 1
    # neste dag: fill med indeksnivå ved inngang; samme dag igjen: ingenting nytt
    ts2 = [tk("A.OL", score=5, close=110, d="2026-10-02"), tk("C.OL", cat="hold", score=3, close=50, d="2026-10-02")]
    B.run(snap("2026-10-03", *ts2), st, 10.0, {"osebx": 1510.0, "spx": 6010.0}, logs=tmp_path)
    f = [r for r in rows(tmp_path / "portfolio_hoy_risiko_v1_trades.csv") if r["event"] == "fill"]
    assert len(f) == 2 and float(f[0]["bench_entry"]) == 1510.0 and float(f[0]["bench_signal"]) == 1500.0 and f[0]["sector"] == "Energy"
    n = len(rows(tmp_path / "portfolio_hoy_risiko_v1_trades.csv"))
    B.run(snap("2026-10-03", *ts2), st, 10.0, {"osebx": 1510.0, "spx": 6010.0}, logs=tmp_path)
    assert len(rows(tmp_path / "portfolio_hoy_risiko_v1_trades.csv")) == n and len(rows(tmp_path / "portfolio_candidates.csv")) == 4


def test_hold_20_days_and_no_category_sell(tmp_path):
    tp, npth = tmp_path / "t.csv", tmp_path / "n.csv"
    R = B.BOOKS["hoy_risiko_v1"]
    go = lambda day, e, picks: P.step(snap(day, e), 10.0, {"osebx": 1.0, "spx": 1.0}, tp, npth, rules=R, picks=picks,
                                      cols=B.B_COLS, annotate=B.annotator({}))
    go("2026-10-02", tk("A.OL", d="2026-10-01"), [tk("A.OL", d="2026-10-01")])
    go("2026-10-03", tk("A.OL", d="2026-10-02"), [])
    go("2026-10-05", tk("A.OL", cat="watch", r20=-0.5, d="2026-10-05"), [])          # Følg/negativ: ingen salg i bok 2
    assert not [r for r in rows(tp) if r["side"] == "sell"]
    go("2026-10-31", tk("A.OL", d="2026-10-30"), [])                                 # 20 handelsdager etter 02.10
    s = [r for r in rows(tp) if r["side"] == "sell"]
    assert len(s) == 1 and s[0]["reason"] == "20 handelsdager"


def test_returns_hidden_and_experimental_flag(tmp_path):
    out = B.summaries(tmp_path)
    assert out["hoy_risiko_v1"]["experimental"] is True and out["hoy_risiko_v1"]["returns_visible"] is False
    assert "returns" not in out["kontroll_tilfeldig_v1"] and out["kontroll_tilfeldig_v1"]["closed_trades"] == 0


def test_book1_ignores_books(tmp_path):
    """Bok 1 (standard step) kjøper fortsatt bare Kjøp, selv med Følg/Hold-kandidater som bok 2 ville kjøpt."""
    P.step(snap("2026-10-02", tk("A.OL", score=9), tk("H.OL", cat="hold", score=8)), 10.0, {}, tmp_path / "t.csv", tmp_path / "n.csv")
    assert rows(tmp_path / "t.csv") == []
    P.step(snap("2026-10-03", tk("K.OL", cat="kjop")), 10.0, {}, tmp_path / "t.csv", tmp_path / "n.csv")
    r = rows(tmp_path / "t.csv")
    assert len(r) == 1 and r[0]["rules_version"] == "rules_v1" and list(r[0]) == P.T_COLS


def test_position_out_of_list_does_not_crash_0211(tmp_path):
    """02.11: kontroll_tilfeldig_v1 krasjet 31.10 og 01.11 (AttributeError i step) fordi en åpen posisjon hadde falt ut av lista
    (e = None). Nå: ingen krasj, NAV-rad skrives. Med hentet sluttkurs (AnalBot 02.11) telles holdetid mot kursdatoen."""
    tp, npth = tmp_path / "t.csv", tmp_path / "n.csv"
    R = B.BOOKS["kontroll_tilfeldig_v1"]
    go = lambda day, ts, picks, x=None: P.step(snap(day, *ts), 10.0, {"osebx": 1.0, "spx": 1.0}, tp, npth, rules=R, picks=picks,
                                               cols=B.B_COLS, annotate=B.annotator({}), px_extra=x)
    go("2026-10-02", [tk("A.OL", d="2026-10-01")], [tk("A.OL", d="2026-10-01")])
    go("2026-10-05", [tk("A.OL", d="2026-10-02")], [])                              # fylt
    go("2026-10-06", [tk("B.OL", d="2026-10-06")], [], {"A.OL": (101.0, "2026-10-06")})   # A.OL ute av lista, kurs hentet
    assert [r["date"] for r in rows(npth)] == ["2026-10-02", "2026-10-05", "2026-10-06"]
    assert not [r for r in rows(tp) if r["side"] == "sell"]
    go("2026-10-31", [tk("B.OL", d="2026-10-30")], [], {"A.OL": (99.0, "2026-10-30")})    # 20 handelsdager
    s = [r for r in rows(tp) if r["side"] == "sell"]
    assert len(s) == 1 and s[0]["ticker"] == "A.OL" and s[0]["reason"] == "20 handelsdager"


def _book(tmp_path, name="kontroll_tilfeldig_v1"):
    tp, npth = tmp_path / "t.csv", tmp_path / "n.csv"
    R = B.BOOKS[name] if name in B.BOOKS else RULES
    go = lambda day, ts, picks, x=None: P.step(snap(day, *ts), 10.0, {"osebx": 1.0, "spx": 1.0}, tp, npth, rules=R, picks=picks,
                                               cols=B.B_COLS if name in B.BOOKS else P.T_COLS,
                                               annotate=B.annotator({}) if name in B.BOOKS else None, px_extra=x)
    return tp, npth, go


def test_off_list_valued_at_fetched_close_not_entry_0211(tmp_path):
    tp, npth, go = _book(tmp_path)
    go("2026-10-02", [tk("A.OL", d="2026-10-01")], [tk("A.OL", d="2026-10-01")])
    go("2026-10-05", [tk("A.OL", close=100.0, d="2026-10-02")], [])              # kjøpt til 100
    go("2026-10-06", [tk("B.OL", d="2026-10-06")], [], {"A.OL": (120.0, "2026-10-06")})
    n = rows(npth)[-1]
    fill = [r for r in rows(tp) if r["event"] == "fill"][0]
    sh, cash = float(fill["shares"]), float(n["cash"])
    assert abs(float(n["nav"]) - (cash + sh * 120.0)) < 0.02                       # hentet sluttkurs, ikke innkurs 100
    c = rows(tmp_path / "portfolio_closes.csv")
    assert any(r["ticker"] == "A.OL" and r["source"] == "yahoo" and r["price_date"] == "2026-10-06" for r in c)
    assert not rows(tmp_path / "portfolio_price_missing.csv")


def test_no_price_marked_sold_first_price_never_cancelled_0211(tmp_path):
    tp, npth, go = _book(tmp_path)
    go("2026-10-02", [tk("A.OL", d="2026-10-01")], [tk("A.OL", d="2026-10-01")])
    go("2026-10-05", [tk("A.OL", close=100.0, d="2026-10-02")], [])              # kjøpt til 100, kurs 100 logget
    go("2026-10-06", [tk("B.OL", d="2026-10-06")], [], {"A.OL": (110.0, "2026-10-06")})   # siste kjente markedskurs 110
    days = ["2026-10-07", "2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15"]
    for d in days:                                                                 # ingen kurs i 7 kjøringer (> 5)
        go(d, [tk("B.OL", d=d)], [])
    t = rows(tp)
    sells = [r for r in t if r["side"] == "sell"]
    assert len(sells) == 1 and sells[0]["event"] == "order" and sells[0]["reason"] == "uten kurs"
    assert not [r for r in t if r["event"] == "cancel" and r["side"] == "sell"]     # aldri kansellert
    m = rows(tmp_path / "portfolio_price_missing.csv")
    assert [r["date"] for r in m] == days and all(r["ticker"] == "A.OL" for r in m)
    assert all(r["valued_from"] == "siste kjente 2026-10-06" and float(r["valued_at"]) == 110.0 for r in m)
    fill = [r for r in t if r["event"] == "fill"][0]
    for r in rows(npth)[-len(days):]:                                              # verdsatt til siste markedskurs, ikke innkurs
        assert abs(float(r["nav"]) - (float(r["cash"]) + float(fill["shares"]) * 110.0)) < 0.02
    go("2026-10-16", [tk("B.OL", d="2026-10-16")], [], {"A.OL": (90.0, "2026-10-16")})    # første dag med kurs: solgt til den
    f = [r for r in rows(tp) if r["event"] == "fill" and r["side"] == "sell"]
    assert len(f) == 1 and float(f[0]["price"]) == 90.0 and f[0]["price_date"] == "2026-10-16"


def test_no_price_ever_counts_zero_and_logged_0211(tmp_path):
    tp, npth, go = _book(tmp_path)
    go("2026-10-02", [tk("A.OL", d="2026-10-01")], [tk("A.OL", d="2026-10-01")])
    go("2026-10-05", [tk("A.OL", close=100.0, d="2026-10-02")], [])
    (tmp_path / "portfolio_closes.csv").unlink()                                  # ingen markedskurs etter fill kjent
    go("2026-10-06", [tk("B.OL", d="2026-10-06")], [])
    n = rows(npth)[-1]
    assert abs(float(n["nav"]) - float(n["cash"])) < 0.01                          # teller 0, aldri innkurs
    m = rows(tmp_path / "portfolio_price_missing.csv")
    assert m[-1]["valued_from"] == "ingen kurs: teller 0" and m[-1]["valued_at"] == ""


def test_pending_red_flag_sell_waits_for_price_0211(tmp_path):
    tp, npth, go = _book(tmp_path)
    go("2026-10-02", [tk("A.OL", d="2026-10-01")], [tk("A.OL", d="2026-10-01")])
    go("2026-10-05", [tk("A.OL", d="2026-10-02")], [])
    go("2026-10-06", [tk("A.OL", d="2026-10-06", flags={"x": "rødt"})], [])        # salgsordre, rødt flagg
    for d in ["2026-10-07", "2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14"]:
        go(d, [tk("B.OL", d=d)], [])                                               # ute av lista, ingen kurs
    t = rows(tp)
    assert not [r for r in t if r["event"] == "cancel"]
    assert len([r for r in t if r["side"] == "sell" and r["event"] == "order"]) == 1   # ingen ny «uten kurs»-ordre i tillegg
    go("2026-10-15", [tk("B.OL", d="2026-10-15")], [], {"A.OL": (95.0, "2026-10-15")})
    assert [float(r["price"]) for r in rows(tp) if r["event"] == "fill" and r["side"] == "sell"] == [95.0]


def test_buy_orders_still_expire_0211(tmp_path):
    tp, npth, go = _book(tmp_path)
    go("2026-10-02", [tk("A.OL", d="2026-10-01")], [tk("A.OL", d="2026-10-01")])
    for d in ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"]:
        go(d, [tk("B.OL", d=d)], [])
    assert [r["reason"] for r in rows(tp) if r["event"] == "cancel"] == ["ingen kurs"]


def test_book1_rules_and_categories_unchanged_0211():
    assert RULES["buy_category"] == "kjop" and RULES["sell_on_folg_or_lower"] is True and RULES["hold_trading_days"] == 60
    assert RULES["order_expiry_runs"] == 5


def test_late_fill_deviation_logged_not_backfilled_0211(tmp_path):
    def nav(book, dates):
        P._append(tmp_path / (f"portfolio_{book}_nav.csv" if book != "rules_v1" else "portfolio_nav.csv"), P.N_COLS,
                  [{"rules_version": book, "date": d, "nav": 1e6, "bench_index": 100} for d in dates])
    nav("rules_v1", ["2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"])
    nav("hoy_risiko_v1", ["2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"])
    nav("kontroll_tilfeldig_v1", ["2026-10-29", "2026-10-30", "2026-11-02"])
    tp = tmp_path / "portfolio_kontroll_tilfeldig_v1_trades.csv"
    P._append(tp, B.B_COLS, [
        {"rules_version": "kontroll_tilfeldig_v1", "event": "fill", "order_id": "2026-10-29-0001", "run_date": "2026-10-30", "signal_date": "2026-10-29", "ticker": "X.OL", "side": "buy"},
        {"rules_version": "kontroll_tilfeldig_v1", "event": "fill", "order_id": "2026-10-30-0022", "run_date": "2026-11-02", "signal_date": "2026-10-30", "ticker": "MRK", "side": "buy"}])
    new = B.log_late_fills(tmp_path)
    assert [(r["order_id"], r["n_missed"], r["missed_runs"]) for r in new] == [("2026-10-30-0022", 2, "2026-10-31|2026-11-01")]
    assert B.log_late_fills(tmp_path) == []                                        # idempotent
    assert [r["date"] for r in rows(tmp_path / "portfolio_kontroll_tilfeldig_v1_nav.csv")] == ["2026-10-29", "2026-10-30", "2026-11-02"]
