"""AnalBot 16.11: SCANA-salget 2026-11-11-0099 på sluttkurs 12.11 (manuell, idempotent), hull 12.–16.11 som «ingen kjøring»,
«mot indeks siden dd.mm» = indeksparets faktiske startdato, «Data x/7» skjult strengt bare ved fullt."""
import csv
import shutil
from pathlib import Path

from signaltool import datacov as DC
from signaltool import portfolio as P
from signaltool import portfolio_books as B
from signaltool import since as SN
from signaltool import testbooks_page as TB

ROOT = Path(__file__).resolve().parents[1]
FILES = ["portfolio_kontroll_tilfeldig_v1_trades.csv", "portfolio_deviations.csv"]


def _logs(tmp_path, strip_fill=True):
    for f in FILES:
        shutil.copy(ROOT / "logs" / f, tmp_path / f)
    if strip_fill:   # tilstanden før føringen: fjern 0099-fill og 16.11-avvikene
        p = tmp_path / FILES[0]
        ls = p.read_text().splitlines(keepends=True)
        p.write_text("".join(l for l in ls if not l.startswith("kontroll_tilfeldig_v1,fill,2026-11-11-0099,")))
        p = tmp_path / FILES[1]
        ls = p.read_text().splitlines(keepends=True)
        p.write_text("".join(l for l in ls if not l.startswith("2026-11-16,")))
    return tmp_path


def test_scana_sell_filled_on_close_1211_once(tmp_path):
    logs = _logs(tmp_path)
    before = (logs / FILES[0]).read_bytes()
    out = B.apply_manual_fills(logs)
    assert len(out) == 1 and (logs / FILES[0]).read_bytes().startswith(before)
    r = out[0]
    assert (r["order_id"], r["side"], r["price_date"], r["price"], r["run_date"]) == ("2026-11-11-0099", "sell", "2026-11-12", 1.43, "2026-11-16")
    s = P.state(P._read(logs / FILES[0]))
    assert "SCANA.OL" not in s["open"] and "2026-11-11-0099" not in s["pending"]
    assert abs(r["nok_value"] - 33735.646259 * 1.43) < 0.01 and abs(r["cost_nok"] - r["nok_value"] * 0.002) < 0.01
    dev = list(csv.DictReader(open(logs / FILES[1])))
    sen = [d for d in dev if d["order_id"] == "2026-11-11-0099" and d["kind"] == "sen_fylling"]
    assert len(sen) == 1 and sen[0]["note"].startswith("sen fylling, nattkjøring feilet")
    hull = [d for d in dev if d["kind"] == "ingen_kjoring"]
    h12 = [d for d in hull if d["order_id"] == "runs-2026-11-12..2026-11-15"]
    h19 = [d for d in hull if d["order_id"] == "runs-2026-11-19..2026-11-22"]
    assert {d["book_id"] for d in h12} == {"rules_v1", "hoy_risiko_v1", "kontroll_tilfeldig_v1"}
    assert all(d["missed_runs"] == "2026-11-12|2026-11-13|2026-11-14|2026-11-15" for d in h12)
    # 19.–22.11 kan ligge i kopien (logg-dato 23.11, ikke strippet) og skrives idempotent
    assert {d["book_id"] for d in h19} == {"rules_v1", "hoy_risiko_v1", "kontroll_tilfeldig_v1"}
    assert all(d["missed_runs"] == "2026-11-19|2026-11-20|2026-11-21|2026-11-22" for d in h19)
    snap = [(logs / f).read_bytes() for f in FILES]
    assert B.apply_manual_fills(logs) == []                       # idempotent
    assert [(logs / f).read_bytes() for f in FILES] == snap


def test_committed_logs_already_have_the_fill():
    rows = P._read(ROOT / "logs" / FILES[0])
    f = [r for r in rows if r["event"] == "fill" and r["order_id"] == "2026-11-11-0099"]
    assert len(f) == 1 and f[0]["price_date"] == "2026-11-12"


def test_manual_fill_does_not_make_todays_run_skip(tmp_path):
    # en manuell fill med run_date = i dag skal ikke telle som «allerede kjørt i dag»
    assert ("kontroll_tilfeldig_v1", "2026-11-11-0099") in P.MANUAL_FILL_IDS
    import inspect
    assert "MANUAL_FILL_IDS" in inspect.getsource(P.step)


def test_books_show_ingen_kjoring_only_for_past_days_without_run():
    d = {"book": "kontroll_tilfeldig_v1", "dates": ["2026-11-11", "2026-11-16"], "start": "2026-10-27", "open": 1, "closed": 3,
         "pending": 0, "fills": 4, "universe_n": 10, "universe_date": "2026-11-11", "no_price": []}
    h = TB.book_card(d, ["2026-11-11", "2026-11-16"], today="2026-11-17")
    assert "Ingen kjøring 12.11, 13.11, 14.11, 15.11 (nattkjøringen feilet). Dagene fylles ikke inn i etterkant." in h
    d2 = dict(d, dates=["2026-11-11"])
    assert TB.no_run_dates(d2, "2026-11-16") == ["2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"]   # 16.11 kan komme
    assert TB.no_run_dates(d2, "2026-11-17")[-1] == "2026-11-16"
    assert "Mangler kjøring" not in h


def test_committed_logs_mark_19_to_22_as_no_run_without_backfill():
    """19.–22.11 er hull i avviksloggen; ingen NAV, fills eller innkurs er fylt inn bakover."""
    dev = list(csv.DictReader(open(ROOT / "logs/portfolio_deviations.csv")))
    h19 = [d for d in dev if d["kind"] == "ingen_kjoring" and d["order_id"] == "runs-2026-11-19..2026-11-22"]
    assert {d["book_id"] for d in h19} == {"rules_v1", "hoy_risiko_v1", "kontroll_tilfeldig_v1"}
    assert all(d["missed_runs"] == "2026-11-19|2026-11-20|2026-11-21|2026-11-22" for d in h19)
    gap = {"2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22"}
    for name in ("portfolio_nav.csv", "portfolio_hoy_risiko_v1_nav.csv", "portfolio_kontroll_tilfeldig_v1_nav.csv"):
        dates = {r["date"] for r in csv.DictReader(open(ROOT / "logs" / name))}
        assert not (dates & gap), (name, dates & gap)
    for name in ("portfolio_trades.csv", "portfolio_hoy_risiko_v1_trades.csv", "portfolio_kontroll_tilfeldig_v1_trades.csv"):
        pth = ROOT / "logs" / name
        if not pth.exists():
            continue
        days = {r.get("run_date") or "" for r in csv.DictReader(open(pth))}
        assert not (days & gap), (name, days & gap)
    ep = ROOT / "logs/entry_prices.csv"
    if ep.exists():
        cols = csv.DictReader(open(ep)).fieldnames or []
        dcol = "date" if "date" in cols else ("run_date" if "run_date" in cols else cols[0])
        days = {r[dcol][:10] for r in csv.DictReader(open(ep)) if r.get(dcol)}
        assert not (days & gap), ("entry_prices", days & gap)
    d = {"book": "kontroll_tilfeldig_v1", "dates": ["2026-11-11", "2026-11-17", "2026-11-18"],
         "start": "2026-10-27", "open": 20, "closed": 13, "pending": 0, "fills": 46,
         "universe_n": 10, "universe_date": "2026-11-18", "no_price": []}
    h = TB.book_card(d, d["dates"], today="2026-11-23")
    assert "19.11, 20.11, 21.11, 22.11" in h and "nattkjøringen feilet" in h
    assert "2026-11-18" not in TB.no_run_dates(d, "2026-11-23")
    assert TB.no_run_dates(d, "2026-11-23") == [
        "2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16",
        "2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22",
    ]


def test_mot_indeks_uses_index_start_date_not_list_date():
    h = SN.ret_inner({"r": 0.012, "ex": 0.004, "bench": "OSEBX", "last": "2026-11-13", "illiquid": False},
                     {"since": "2026-10-24", "price": 1.0, "price_date": "2026-10-23"})
    assert '<span class="rper"> mot indeks siden 23.10</span>' in h
    assert '<span class="rv rup">+1,2 %</span><span class="rper"> siden 23.10</span>' in h   # prosenten: samme innkursdato


def test_data_chip_hidden_only_when_complete():
    full = {"have": 7, "of": 7, "etf": False, "missing": []}
    six = {"have": 6, "of": 7, "etf": False, "missing": ["x"]}
    orig = DC.coverage
    try:
        DC.coverage = lambda e: full
        assert DC.chip({}) == ""
        DC.coverage = lambda e: six
        assert "Data 6/7" in DC.chip({})
    finally:
        DC.coverage = orig


def test_not_listed_dropped_from_list_and_members(tmp_path, monkeypatch):
    from signaltool import not_listed as NL
    from signaltool import ov_changes as CHG
    assert NL.NOT_LISTED == {"DIASH.OL", "ERUGA.OL", "FLOAT.OL", "NPRO.OL", "SEIL.OL", "SFLN.OL", "SWG.OL", "VEOFF.OL"}
    assert NL.drop([{"ticker": "SFLN.OL"}, {"ticker": "EQNR.OL"}]) == [{"ticker": "EQNR.OL"}]
    monkeypatch.setattr("signaltool.overview.candidates", lambda snap: [{"ticker": "SWG.OL"}, {"ticker": "EQNR.OL"}])
    p = tmp_path / "list_members.csv"
    assert CHG.write_members({"date": "2026-11-16"}, p) == 1
    assert "SWG.OL" not in p.read_text()
    lg = tmp_path / "ex.csv"
    assert NL.log_once(lg) == 8 and NL.log_once(lg) == 0
    rs = list(csv.DictReader(open(lg)))
    assert all(r["reason"] == "tatt ut: ikke notert" and "euronext.com" in r["source"] and "newsweb" in r["source"] for r in rs)


def test_pipeline_drops_not_listed_before_top60():
    src = (ROOT / "signaltool" / "pipeline.py").read_text()
    assert 'NL.drop(ranked)' in src
