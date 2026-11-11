"""UxBot/AnalBot 11.11: endringsstripe, «N dager på rad», ut-grunner (logs/list_exits.csv), perioder og graflinjer."""
import copy
import csv
import json
import re
from pathlib import Path

import pytest

from signaltool import ov_changes as C, overview as OV, pricechart as PC, site

LOG = Path("logs/categories.csv")
COLS = ["date", "ticker", "category", "price", "price_date", "benchmark", "score", "n_types", "types", "flags", "rangert"]


def _write(tmp_path, rows, name="categories.csv"):
    p = tmp_path / name
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for r in rows:
            d, t = r[0], r[1]
            cat = r[2] if len(r) > 2 else "watch"
            sc = r[3] if len(r) > 3 else "1.0"
            w.writerow([d, t, cat, "1", d, "", sc, "1", "", "", "1"])
    return p


def _exits(tmp_path, rows):
    p = tmp_path / "list_exits.csv"
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=C.EXIT_COLS)
        w.writeheader()
        w.writerows(rows)
    return p


def _real_sets():
    by = {}
    with LOG.open(newline="") as f:
        for r in csv.DictReader(f):
            if r["category"] != "tema":
                by.setdefault(r["date"], set()).add(r["ticker"])
    with Path("logs/entry_prices.csv").open(newline="") as f:   # ikke-loggbare kandidater (ETF-er o.l.) fra sideloggen
        for r in csv.DictReader(f):
            if r["date"] in by:
                by[r["date"]].add(r["ticker"])
    ds = sorted(by)
    return ds[-2], ds[-1], by[ds[-2]], by[ds[-1]]


# ---------------------------------------------------------------- stripe
def test_strip_counts_are_set_differences_of_real_log():
    prev, last, a, b = _real_sets()
    h = C.strip_html(None)
    m = re.search(r"<span class=\"chg-l\">Siden (\d\d\.\d\d): (\d+) inn · (\d+) ut · (\d+) står fortsatt</span>", h)
    assert m and m.group(1) == f"{prev[8:10]}.{prev[5:7]}"
    inn, ut, stay = map(int, m.group(2, 3, 4))
    assert (inn, ut, stay) == (len(b - a), len(a - b), len(a & b))
    assert inn + stay == len(b)            # inn + står fortsatt = dagens listelengde
    chips = re.findall(r'class="chg-t">([^<]+)<', h)
    assert sorted(chips) == sorted((b - a) | (a - b))


def test_strip_previous_run_includes_weekends_and_skips_tema(tmp_path):
    p = _write(tmp_path, [("2026-11-06", "A"), ("2026-11-06", "B"), ("2026-11-07", "B"), ("2026-11-07", "C"),
                          ("2026-11-08", "B"), ("2026-11-08", "D"), ("2026-11-08", "T.OL", "tema", "")])
    h = C.strip_html(None, path=p, exits_path=tmp_path / "none.csv")
    assert "Siden 07.11: 1 inn · 1 ut · 1 står fortsatt" in h        # lørdag 07.11 er forrige kjøring; tema-rad er ikke på lista
    assert "T.OL" not in h


def test_ut_chips_subtext_and_no_price_group(tmp_path):
    p = _write(tmp_path, [("2026-11-09", "A"), ("2026-11-09", "B"), ("2026-11-09", "C"), ("2026-11-09", "D"),
                          ("2026-11-10", "N")])
    ex = _exits(tmp_path, [{"date": "2026-11-10", "ticker": "B", "code": "below_threshold", "old_score": "3.14", "new_score": "-0.2"},
                           {"date": "2026-11-10", "ticker": "C", "code": "no_price", "old_score": "", "new_score": ""},
                           {"date": "2026-11-10", "ticker": "D", "code": "out_of_top60", "old_score": "2.0", "new_score": "2.44"}])
    h = C.strip_html({"tickers": [{"ticker": "N"}, {"ticker": "B"}]}, path=p, exits_path=ex)
    assert "Siden 09.11: 1 inn · 4 ut · 0 står fortsatt" in h
    assert '<span class="chg-why">Ut 10.11: grunn ikke logget</span>' in h                       # A: ingen kode
    assert '<span class="chg-why">Ut 10.11: Score under grensen (3,1 → −0,2)</span>' in h
    assert '<span class="chg-why">Ut 10.11: Ikke lenger blant de 60 høyeste (score 2,4)</span>' in h
    assert "<h3>Ut (3)</h3>" in h and "<h3>Ute pga. manglende kurs (1)</h3>" in h
    assert h.index("<h3>Ut (3)") < h.index("Ute pga. manglende kurs") < h.index('<span class="chg-why">Ut 10.11: Mangler kurs</span>')
    assert '<a class="chg-c" href="ticker/N.html">' in h and '<span class="chg-c chg-np"><span class="chg-g" aria-hidden="true">−</span><span class="chg-t">A</span>' in h
    inn = re.search(r"<h3>Inn \(1\)</h3>(.*?)</div></div>", h).group(1)
    assert "chg-why" not in inn
    assert "flagg" not in h.lower()


def test_only_four_reason_texts_and_suffix_hook(tmp_path, monkeypatch):
    rt = C.reason_text
    assert rt({"code": "below_threshold", "old_score": "3.1", "new_score": "1.8"}) == "Score under grensen (3,1 → 1,8)"
    assert rt({"code": "out_of_top60", "new_score": "2.4"}) == "Ikke lenger blant de 60 høyeste (score 2,4)"
    assert rt({"code": "no_price"}) == "Mangler kurs" and rt({"code": "delisted"}) == "Ikke børsnotert"
    assert rt({"code": ""}) == "" and rt({"code": "red_flag"}) == "" and rt(None) == "" and rt({"code": "below_threshold", "new_score": "1"}) == ""
    assert C.NO_REASON_SUFFIX == "" and C.no_reason(tmp_path / "x.csv") == "grunn ikke logget"
    ex = _exits(tmp_path, [{"date": "2026-11-12", "ticker": "A", "code": ""}, {"date": "2026-11-11", "ticker": "B", "code": ""}])
    monkeypatch.setattr(C, "NO_REASON_SUFFIX", " (før {dm})")
    assert C.no_reason(ex) == "grunn ikke logget (før 11.11)"       # dato fra første rad i list_exits.csv, ikke hardkodet
    assert "11.11" not in C.NO_REASON_SUFFIX


def test_strip_neutral_colors_and_44px_chips():
    rules = re.findall(r"[^{}]*\{[^}]*\}", C.CSS)
    chg = " ".join(r for r in rules if ".ov-chg" in r.split("{")[0] or ".dg" in r.split("{")[0] or ".lp-" in r.split("{")[0])
    for bad in ("#22c55e", "#56d364", "#3fb950", "#ef4444", "#f85149", "green", ":red", "var(--up)", "var(--down)", "rgba(63,185,80", "rgba(248,81,73"):
        assert bad not in chg
    h = C.strip_html(None)
    assert not re.search(r'class="[^"]*\b(rup|rdn|tup|tdn|fl-red)\b', h)
    chip = next(r for r in rules if r.strip().startswith(".ov-chg .chg-c{"))
    assert "min-width:44px" in chip and "min-height:44px" in chip and "box-sizing:border-box" in chip
    assert ".ov-chg .chg-cs{display:flex;flex-wrap:wrap" in C.CSS
    summ = next(r for r in rules if r.strip().startswith(".ov-chg>summary{"))
    assert "min-height:48px" in summ and "font-size:14px;line-height:19px" in summ and "padding:5px 12px" in summ   # 2 linjer à 19 + 10 = 48


def test_strip_directly_under_status_line():
    from tests.test_overview_0911 import snap
    h = site.overview_html(snap())
    assert re.search(r'<p class="ov-status">.*?</p><details class="ov-chg"', h)
    assert h.index('class="ov-chg"') < h.index('id="kandidater"')


# ---------------------------------------------------------------- dager
def test_days_counter_known_example(tmp_path):
    rows = [("2026-11-05", "A"), ("2026-11-06", "A"), ("2026-11-07", "A"), ("2026-11-08", "A"), ("2026-11-09", "A"), ("2026-11-10", "A"),
            ("2026-11-06", "B"), ("2026-11-07", "B"), ("2026-11-09", "B"), ("2026-11-10", "B"),   # mangler 08.11 -> rekken brytes
            ("2026-11-10", "N"), ("2026-11-09", "OUT"), ("2026-11-05", "Z")]
    dmap, full = C.days_ctx(_write(tmp_path, rows))
    assert dmap == {"A": 6, "B": 2, "N": 1} and full == {"A": "2026-11-05"}
    assert C.days_cell("A", dmap, full) == '<td class="dg"><span class="dgv">fra 05.11</span></td>'   # sammenhengende siden første loggdato
    assert C.days_cell("B", dmap, full) == '<td class="dg"><span class="dgv">2 dager på rad</span></td>'
    assert C.days_cell("N", dmap, full) == '<td class="dg"><span class="dgv">1 dag på rad</span><span class="dg-ny">Ny</span></td>'
    assert C.days_cell("OUT", dmap, full) == '<td class="dg"><span class="dgv">–</span></td>'


def test_side_log_tickers_are_on_list_from_side_start(tmp_path):
    from signaltool.since import SIDE_START
    p = _write(tmp_path, [("2026-09-27", "SPY"), ("2026-09-27", "A"), (SIDE_START, "A"), ("2026-11-10", "A")])
    ep = tmp_path / "entry.csv"
    ep.write_text("date,ticker,category,price,price_date\n2026-09-27,SPY,watch,1,2026-09-27\n"
                  f"{SIDE_START},SPY,watch,1,{SIDE_START}\n2026-11-10,SPY,watch,1,2026-11-10\n")
    by = C.by_date(p, ep)
    assert by["2026-11-10"] == {"A", "SPY"} and "SPY" not in by["2026-09-27"]   # hull før sideloggen er ikke «ut»
    assert C.periods(by)["SPY"] == [[SIDE_START, None]] and C.src_first(p, ep)["SPY"] == SIDE_START


def test_candidate_table_has_days_column(tmp_path, monkeypatch):
    p = _write(tmp_path, [("2026-11-08", "C.OL"), ("2026-11-09", "A.OL"), ("2026-11-09", "C.OL"), ("2026-11-10", "A.OL"), ("2026-11-10", "B.OL")])
    monkeypatch.setattr(C, "LOG", p)
    s = {"tickers": [{"ticker": "A.OL", "score": 5.0}, {"ticker": "B.OL", "score": 4.0}], "oslo_universe_flags": []}
    t = OV.candidates_table_html(s)
    assert '<th scope="col" class="dg-h">Dager på lista</th></tr></thead>' in t
    rows = re.findall(r"<tr data-nf=.*?</tr>", t)
    assert '<span class="dgv">2 dager på rad</span></td></tr>' in rows[0] and "dg-ny" not in rows[0]
    assert '<span class="dgv">1 dag på rad</span><span class="dg-ny">Ny</span></td></tr>' in rows[1]
    assert "sortable" not in t and "aria-sort" not in t
    assert ".ov-ct td.dg{font-size:14px;line-height:20px;color:#94a3b8" in C.CSS and ".ov-ct th.dg-h,.ov-ct td.dg{text-align:right" in C.CSS
    assert '"nm nm nm dg" "rk fl sg sg"' in OV.CSS and ".ov-ct td.dg{grid-area:dg;justify-self:end;" in C.CSS   # < 600: navnelinja


# ---------------------------------------------------------------- logging av ut-grunner
def _snap_rank(n_kept=60):
    tk = [{"ticker": "KEEP", "score": 4.0, "points": {"x": 4.0}}] + [{"ticker": f"K{i}", "score": 3.0} for i in range(n_kept - 1)]
    snap = {"date": "2026-11-10", "tickers": tk + [{"ticker": "UNR", "score": 1.0, "unranked": True}]}
    ranked = tk + [{"ticker": "CUT", "score": 2.44}, {"ticker": "LOW", "score": 0.0}, {"ticker": "THM", "score": 1.5}, {"ticker": "UNR", "score": 1.0}]
    return snap, ranked


def _exit_log(tmp_path):
    return _write(tmp_path, [("2026-11-09", "KEEP", "watch", "4.0"), ("2026-11-09", "CUT", "watch", "2.6"), ("2026-11-09", "LOW", "watch", "2.1"),
                             ("2026-11-09", "GONE", "watch", "1.2"), ("2026-11-09", "REC.OL", "watch", "1.0"), ("2026-11-09", "THM", "watch", "1.9"),
                             ("2026-11-10", "KEEP", "watch", "4.0"), ("2026-11-10", "THM", "tema", "")])


def test_exit_codes_only_when_run_decides(tmp_path):
    p = _exit_log(tmp_path)
    snap, ranked = _snap_rank()
    rows = {r["ticker"]: r for r in C.exit_rows(snap, ranked, p)}
    assert rows["CUT"]["code"] == "out_of_top60" and rows["CUT"]["new_score"] == 2.44      # taket biter: 60 rangerbare
    assert rows["LOW"]["code"] == "below_threshold" and rows["LOW"]["old_score"] == "2.1"
    assert C.reason_text(rows["LOW"]) == "Score under grensen (2,1 → 0,0)"
    assert rows["THM"]["code"] == "moved_to_theme" and C.reason_text(rows["THM"]) == "Flyttet til temakartet"
    assert rows["GONE"]["code"] == ""              # ikke kandidat i dag: kan ikke avgjøres -> ingen kode
    assert rows["REC.OL"]["code"] == "delisted"    # verdikjede-rettelse listed=false, strøket 25.06.2026
    assert set(rows) == {"CUT", "LOW", "GONE", "REC.OL", "THM"} and all(r["code"] in C.CODES + ("",) for r in rows.values())
    fr = copy.deepcopy(snap); fr["frozen_from"] = "2026-11-08"
    assert {r["ticker"]: r["code"] for r in C.exit_rows(fr, ranked, p)}["CUT"] == ""   # fryst liste: ingen kode
    out = tmp_path / "list_exits.csv"
    assert C.record_exits(snap, ranked, out, p) == 5 and C.record_exits(snap, ranked, out, p) == 5   # ny kjøring samme dag erstatter
    got = list(csv.DictReader(out.open()))
    assert len(got) == 5 and list(got[0]) == C.EXIT_COLS


def test_top60_code_never_when_cap_does_not_bite(tmp_path):
    p = _exit_log(tmp_path)
    snap, ranked = _snap_rank(n_kept=59)             # 59 rangerbare (+1 «Ikke rangert»): taket biter ikke
    assert {r["ticker"]: r["code"] for r in C.exit_rows(snap, ranked, p)}["CUT"] == ""
    assert C.TOP_CAP == 60 and "[:60]" in Path("signaltool/pipeline.py").read_text()


def test_every_exit_one_chip_and_chip_count_equals_strip(tmp_path):
    p = _exit_log(tmp_path)
    snap, ranked = _snap_rank()
    ex = tmp_path / "list_exits.csv"
    C.record_exits(snap, ranked, ex, p)
    h = C.strip_html(None, path=p, exits_path=ex)
    n_ut = int(re.search(r"(\d+) ut ·", h).group(1))
    why = re.findall(r'<span class="chg-why">Ut 10\.11: ([^<]+)</span>', h)
    assert len(why) == n_ut == 5
    allowed = {"grunn ikke logget", "Ikke børsnotert", "Flyttet til temakartet", "Mangler kurs"}
    assert all(w in allowed or w.startswith(("Score under grensen (", "Ikke lenger blant de 60 høyeste (score ")) for w in why)


def test_built_overview_strip_matches_candidate_table(tmp_path, monkeypatch):
    """inn + står fortsatt == antall kandidater i kandidattabellen samme dag, i bygget Oversikt-HTML."""
    p = _write(tmp_path, [("2026-11-09", "A.OL"), ("2026-11-09", "B.OL"), ("2026-11-10", "A.OL"), ("2026-11-10", "C.OL"),
                          ("2026-11-10", "T.OL", "tema", "")])
    ep = tmp_path / "entry.csv"
    ep.write_text("date,ticker,category,price,price_date\n2026-11-09,SPY,watch,1,2026-11-09\n2026-11-10,SPY,watch,1,2026-11-10\n")
    monkeypatch.setattr(C, "LOG", p)
    import signaltool.since as SN
    monkeypatch.setattr(SN, "ENTRY_LOG", ep)
    from tests.test_overview_0911 import snap as base
    s = {**base(), "date": "2026-11-10",
         "tickers": [{"ticker": t, "score": 5.0 - i} for i, t in enumerate(["A.OL", "C.OL", "SPY"])]}
    h = site.overview_html(s)
    m = re.search(r"Siden 09\.11: (\d+) inn · (\d+) ut · (\d+) står fortsatt", h)
    assert m and int(m.group(1)) + int(m.group(3)) == h.count("<tr data-nf=") == 3


def test_logging_does_not_touch_snapshot_or_candidates(tmp_path):
    p = _exit_log(tmp_path)
    snap, ranked = _snap_rank()
    a, b = json.dumps(snap, sort_keys=True), json.dumps(ranked, sort_keys=True)
    C.record_exits(snap, ranked, tmp_path / "e.csv", p)
    C.write_periods(tmp_path / "p.json", p)
    assert json.dumps(snap, sort_keys=True) == a and json.dumps(ranked, sort_keys=True) == b
    assert OV.candidates(snap) == OV.candidates(json.loads(a))


def test_pipeline_hook_after_categories_and_nightly_commits_log():
    src = Path("signaltool/pipeline.py").read_text()
    i = src.index("CHG.write_members(snap)")
    assert src.index("categories.apply(snap)") < i < src.index("CHG.record_exits(snap, ranked)") < src.index('(SNAP_DIR / "latest.json").write_text')
    wf = Path(".github/workflows/nightly.yml").read_text()
    assert "logs/list_exits.csv" in wf and "logs/list_members.csv" in wf


# ---------------------------------------------------------------- perioder + graf
def test_periods_all_runs_and_json(tmp_path):
    p = _write(tmp_path, [("2026-09-27", "A"), ("2026-09-28", "A"), ("2026-09-29", "B"), ("2026-09-30", "A"), ("2026-10-01", "A"), ("2026-10-01", "B")])
    ps = C.periods(C.by_date(p))
    assert ps == {"A": [["2026-09-27", "2026-09-29"], ["2026-09-30", None]], "B": [["2026-09-29", "2026-09-30"], ["2026-10-01", None]]}
    C.write_periods(tmp_path / "lp.json", p)
    j = json.loads((tmp_path / "lp.json").read_text())
    assert j["periods"] == ps and j["first"] == "2026-09-27"


def test_real_periods_consistent_with_strip():
    prev, last, a, b = _real_sets()
    ps = C.periods(C.by_date())
    assert {t for t, v in ps.items() if v[-1][1] is None} == b
    assert {t for t, v in ps.items() if v[-1][1] == last} == a - b


def test_ticker_period_lines(tmp_path):
    ex = _exits(tmp_path, [{"date": "2026-11-12", "ticker": "A", "code": "below_threshold", "old_score": "3.1", "new_score": "1.8"}])
    p2 = _write(tmp_path, [("2026-09-27", "A"), ("2026-11-03", "B"), ("2026-11-03", "A"), ("2026-11-05", "B"), ("2026-11-09", "A"),
                           ("2026-11-12", "B"), ("2026-11-14", "A")], "c2.csv")
    texts = [x["text"] for x in C.ticker_periods("A", p2, ex)]
    assert texts == ["på lista fra før 27.09 · Ut 05.11: grunn ikke logget",
                     "Inn 09.11 · Ut 12.11: Score under grensen (3,1 → 1,8)",
                     "Inn 14.11 · på lista nå"]
    h = C.periods_html(C.ticker_periods("A", p2, ex))
    assert h.startswith('<p class="lp-note">Grått felt = perioder på kandidatlista. Ikke kjøps- eller salgssignal.</p>')
    assert '<li><span class="lp-a">Inn 09.11 · Ut 12.11:</span> <span class="lp-r">Score under grensen (3,1 → 1,8)</span></li>' in h
    assert '<li><span class="lp-a">Inn 14.11 · på lista nå</span></li>' in h
    assert ".lp-note,.lp-list{font-size:13px;line-height:18px;color:#94a3b8}" in C.CSS
    assert "@media(max-width:599px){.lp-list li{max-height:40px}.lp-list .lp-r{display:block}" in C.CSS and "ellipsis" not in C.CSS.split(".lp-note")[1]
    assert C.ticker_periods("NEVER", p2, ex) == []


def test_chart_bands_with_hover(tmp_path):
    ser = [(f"2026-11-{d:02d}", 10.0 + d) for d in range(1, 21)]
    ps = [{"inn": "2026-11-03", "ut": "2026-11-06", "title": "Ut 06.11: Mangler kurs", "lead": "Inn 03.11 · Ut 06.11:", "why": "Mangler kurs"},
          {"inn": "2026-11-15", "ut": None, "title": "Inn 15.11 · på lista nå", "lead": "Inn 15.11 · på lista nå", "why": ""}]
    h = PC.html("A", ser, None, "2026-11-20", ps)
    assert h.count('<rect class="pcband"') == len([l for l, n in PC.PERIODS if len(ser[-n:]) >= 2]) * 2
    assert '<span class="tip">Ut 06.11: Mangler kurs</span>' in h and 'fill="#8b949e"' in h and "<title>" not in h
    assert '<p class="lp-note">' in h and h.index('class="lp-list"') < h.index('class="mut pcs"')
    assert "pcband" not in PC.html("A", ser, None, "2026-11-20") and "lp-note" not in PC.html("A", ser)


def test_empty_groups_hidden_but_zero_in_strip(tmp_path):
    p = _write(tmp_path, [("2026-11-09", "A"), ("2026-11-09", "B"), ("2026-11-10", "A")])
    h = C.strip_html(None, path=p, exits_path=tmp_path / "none.csv")
    assert "Siden 09.11: 0 inn · 1 ut · 1 står fortsatt" in h
    assert "<h3>Inn" not in h and "Ute pga. manglende kurs" not in h and "Ingen" not in h and "<h3>Ut (1)</h3>" in h
    p2 = _write(tmp_path, [("2026-11-09", "A"), ("2026-11-10", "A"), ("2026-11-10", "N")], "c2.csv")
    h2 = C.strip_html(None, path=p2, exits_path=tmp_path / "none.csv")
    assert "Siden 09.11: 1 inn · 0 ut · 1 står fortsatt" in h2 and "<h3>Ut" not in h2 and "<h3>Inn (1)</h3>" in h2
    assert h2.count('class="chg-grp"') == 1



# ---------------------------------------------------------------- AnalBot 11.11: list_members.csv, hull, verifisering
def test_a_row_without_close_is_logged_and_counted(tmp_path, monkeypatch):
    mp = tmp_path / "list_members.csv"
    snap = {"date": "2026-11-11", "tickers": [{"ticker": "A.OL", "score": 5.0, "stats": {"close": 10.0}},
                                              {"ticker": "NOPX", "score": 2.0, "stats": {}},            # ingen sluttkurs
                                              {"ticker": "NOSCORE", "score": None}]}
    assert C.write_members(snap, mp) == 2
    assert C.write_members(snap, mp) == 2   # ny kjøring samme dag erstatter
    assert list(csv.DictReader(mp.open())) == [{"date": "2026-11-11", "ticker": "A.OL"}, {"date": "2026-11-11", "ticker": "NOPX"}]
    p = _write(tmp_path, [("2026-11-10", "A.OL"), ("2026-11-11", "A.OL")])   # NOPX mangler i categories.csv (ingen kurs)
    by = C.by_date(p, None, mp)
    assert by["2026-11-11"] == {"A.OL", "NOPX"}
    assert "Siden 10.11: 1 inn · 0 ut · 1 står fortsatt" in C.strip_html(None, p, tmp_path / "x.csv", mp)


def test_b_gap_in_side_log_is_one_period_with_data_missing(tmp_path):
    p = _write(tmp_path, [("2026-10-29", "A"), ("2026-10-30", "A"), ("2026-10-31", "A"), ("2026-11-01", "A"), ("2026-11-02", "A"),
                          ("2026-11-03", "A")])
    ep = tmp_path / "entry.csv"
    ep.write_text("date,ticker,category,price,price_date\n" + "".join(f"{d},ETF,watch,1,{d}\n" for d in
                  ("2026-10-29", "2026-10-31", "2026-11-03")))   # mangler 30.10 og 01.–02.11
    by = C.by_date(p, ep, None)
    assert all("ETF" in by[d] for d in by)
    assert C.periods(by)["ETF"] == [["2026-10-29", None]]
    assert C.gaps(p, ep, None) == {"ETF": ["2026-10-30", "2026-11-01", "2026-11-02"]}
    assert C.gap_text(C.gaps(p, ep, None)["ETF"], sorted(by)) == "data mangler 30.10, 01.11–02.11"
    dmap, full = C.days_ctx(p, ep, None)
    assert dmap["ETF"] == 6 and full["ETF"] == "2026-10-29"       # hullet er ikke brudd
    snap = {"date": "2026-11-03", "tickers": [{"ticker": "A", "score": 1.0}, {"ticker": "ETF", "score": 1.0}]}
    assert C.exit_rows(snap, snap["tickers"], p, entry_path=ep, members_path=None) == []   # ingen utgang for hullet
    assert "ETF" not in C.strip_html(None, p, tmp_path / "x.csv", None)   # ingen Ut/Inn for hullet i stripen
    # tickerside: én periode med tilleggstekst
    import signaltool.since as SN
    old = SN.ENTRY_LOG
    try:
        SN.ENTRY_LOG = ep
        C_LOG = C.LOG
        C.LOG = p
        texts = [x["text"] for x in C.ticker_periods("ETF", None, tmp_path / "x.csv", None)]
    finally:
        SN.ENTRY_LOG, C.LOG = old, C_LOG
    assert texts == ["på lista fra før 29.10 · på lista nå · data mangler 30.10, 01.11–02.11"]   # hullet sist på raden
    # hull uten «etter» er en ekte utgang
    ep.write_text("date,ticker,category,price,price_date\n2026-10-29,ETF,watch,1,2026-10-29\n")
    assert C.periods(C.by_date(p, ep, None))["ETF"] == [["2026-10-29", "2026-10-30"]] and C.gaps(p, ep, None) == {}


def test_c_strip_uses_members_log_when_present(tmp_path):
    p = _write(tmp_path, [("2026-11-09", "A"), ("2026-11-10", "A"), ("2026-11-10", "B"), ("2026-11-11", "A")])
    mp = tmp_path / "list_members.csv"
    mp.write_text("date,ticker\n2026-11-11,A\n2026-11-11,C\n2026-11-11,NOPX\n")
    h = C.strip_html(None, p, tmp_path / "x.csv", mp)
    assert "Siden 10.11: 2 inn · 1 ut · 1 står fortsatt" in h      # 11.11 fra list_members (ikke categories: bare A)
    assert set(re.findall(r'class="chg-t">([^<]+)<', h)) == {"C", "NOPX", "B"}
    assert C.days_ctx(p, None, mp)[0] == {"A": 3, "C": 1, "NOPX": 1}


def test_d_verifier_green_when_price_missing_but_strip_matches_table(tmp_path, monkeypatch):
    p = _write(tmp_path, [("2026-11-10", "A.OL"), ("2026-11-10", "B.OL")])
    mp = tmp_path / "list_members.csv"
    monkeypatch.setattr(C, "LOG", p)
    monkeypatch.setattr(C, "MEMBERS", mp)
    import signaltool.since as SN
    monkeypatch.setattr(SN, "ENTRY_LOG", tmp_path / "none.csv")
    from tests.test_overview_0911 import snap as base
    s = {**base(), "date": "2026-11-11", "tickers": [{"ticker": "A.OL", "score": 5.0, "stats": {"close": 1.0}},
                                                      {"ticker": "NOPX", "score": 3.0, "stats": {}}]}   # NOPX uten kurs
    C.write_members(s, mp)
    h = site.overview_html(s)
    r = C.strip_check(h)
    assert r["ok"], r
    assert r["text"] == "Siden 10.11: 1 inn · 1 ut · 1 står fortsatt" and r["rows"] == 2
    bad = h.replace("1 inn · 1 ut · 1 står fortsatt", "1 inn · 1 ut · 2 står fortsatt")   # stripe fra annen kilde enn tabellen
    assert not C.strip_check(bad)["ok"]
    vf = Path("/workspace/page-explanations/verify-live-final.py")
    if vf.exists():
        src = vf.read_text()
        assert "CHG.strip_check(" in src and "kurs" not in src.split("CHG.strip_check(", 1)[1].split("\n", 1)[0]



# ---------------------------------------------------------------- UxBot 11.11: mobilrad, grafmarkører, verktøytips, hull i grafen
def _mobile_rule(css, sel):
    m = re.search(r"@media\(max-width:699px\)\{(.*)", css, re.S)
    return m.group(1)


def test_mobile_days_on_name_line_not_signal_row():
    areas = re.search(r'\.ov-ct tr\{display:grid;grid-template-columns:([^;]+);grid-template-areas:((?:"[^"]+" ?)+);', OV.CSS)
    rows = re.findall(r'"([^"]+)"', areas.group(2))
    assert rows[0].split() == ["nm", "nm", "nm", "dg"]            # «n dager på rad»/«Ny» på navnelinja, høyre
    assert "dg" not in rows[1].split() and rows[1].split()[-2:] == ["sg", "sg"]   # linje 2: risiko · flagg · signal, full bredde
    assert "minmax(0,1fr)" in areas.group(1)                       # navnet tar resten og brytes
    m = C.CSS.split("@media(max-width:699px){", 1)[1]
    assert ".ov-ct td.dg{grid-area:dg;justify-self:end;align-self:start;font-size:13px;line-height:18px;color:#94a3b8" in m
    assert ".ov-ct td.sgt .sgc{white-space:normal;overflow:visible;text-overflow:clip" in m
    t = OV.candidates_table_html({"tickers": [{"ticker": "NVDA", "score": 5.0, "points": {"price_move": 1.0}}], "oslo_universe_flags": []})
    row = re.search(r"<tr data-nf=.*?</tr>", t).group(0)
    assert re.search(r'<td class="sgt">.*?</td>', row) and 'class="dgv"' not in re.search(r'<td class="sgt">.*?</td>', row).group(0)


def _nvda_like():
    ser = []
    import datetime as dt
    d = dt.date(2026, 5, 1)
    while d <= dt.date(2026, 11, 10):
        if d.weekday() < 5:
            ser.append((d.isoformat(), 100.0 + d.toordinal() % 7))
        d += dt.timedelta(days=1)
    return ser


def test_chart_markers_for_all_events_in_window(tmp_path):
    p = _write(tmp_path, [(d, "NV") for d in ("2026-09-27", "2026-09-28", "2026-10-13", "2026-10-27", "2026-11-06", "2026-11-10")]
               + [(d, "X") for d in ("2026-09-27", "2026-09-28", "2026-10-12", "2026-10-13", "2026-10-18", "2026-10-27", "2026-10-29",
                                    "2026-11-06", "2026-11-07", "2026-11-10")])
    ps = C.ticker_periods("NV", p, tmp_path / "x.csv", None)
    assert len(ps) == 5
    ser = _nvda_like()
    h = PC.html("NV", ser, "2026-11-10", "2026-11-10", ps)
    panes = dict(re.findall(r'<div class="pcp" data-p="(\w+)"[^>]*>(.*?)</div></div>', h, re.S))
    for lab, n in PC.PERIODS:
        if lab not in panes:
            continue
        ev = PC.events(ser[-n:], ps)
        assert panes[lab].count('class="pcmk') == len(ev), lab
    six = PC.events(ser[-126:], ps)
    assert [k for k, _, _ in six].count("Inn") == 4 and [k for k, _, _ in six].count("Ut") == 4   # 6M: alle inn/ut, ikke bare «inn 09.11»
    assert ">Inn<br>13.10<" in panes["6M"] and ">Ut<br>12.10<" in panes["6M"]
    assert 'class="pcin' not in h                               # gammel blå «inn dd.mm» erstattet av Inn/Ut-markørene
    assert "innerWidth<600" in h and "<28" in h                 # 390: etikett bare med ≥ 28 px til neste markør


def test_tooltips_hover_and_focus_with_reason(tmp_path):
    p = _write(tmp_path, [("2026-11-01", "Q"), ("2026-11-03", "Q"), ("2026-11-03", "A"), ("2026-11-05", "A"), ("2026-11-06", "Q")])
    ex = _exits(tmp_path, [{"date": "2026-11-05", "ticker": "Q", "code": "no_price"}])
    ps = C.ticker_periods("Q", p, ex, None)
    ser = [(f"2026-11-{d:02d}", 10.0 + d) for d in range(1, 11)]
    h = PC.html("Q", ser, None, "2026-11-10", ps)
    assert re.search(r'<span class="pcmk[^"]*" data-k="Ut" tabindex="0"', h) and re.search(r'<span class="pcbd" tabindex="0"', h)
    assert '<span class="tip">På lista fra før 01.11 · Ut 05.11: Mangler kurs</span>' in h
    assert '<span class="tip">Inn 06.11 · på lista nå</span>' in h
    assert ".pcbd:hover .tip,.pcbd:focus .tip,.pcmk:hover .tip,.pcmk:focus .tip{display:block}" in PC.CSS


def test_gap_band_continuous_dashed_edge_and_texts(tmp_path):
    from signaltool.since import SIDE_START
    p = _write(tmp_path, [("2026-11-02", "A"), ("2026-11-03", "A"), ("2026-11-04", "A"), ("2026-11-05", "A")])
    ep = tmp_path / "entry.csv"
    ep.write_text("date,ticker,category,price,price_date\n2026-11-02,ETF,watch,1,2026-11-02\n2026-11-05,ETF,watch,1,2026-11-05\n")
    import signaltool.since as SN
    old, old_log = SN.ENTRY_LOG, C.LOG
    try:
        SN.ENTRY_LOG, C.LOG = ep, p
        ps = C.ticker_periods("ETF", None, tmp_path / "x.csv", None)
        h = C.strip_html(None, None, tmp_path / "x.csv", None)
    finally:
        SN.ENTRY_LOG, C.LOG = old, old_log
    assert len(ps) == 1 and ps[0]["text"].endswith("på lista nå · data mangler 03.11–04.11")
    assert ps[0]["tip"] == "På lista fra før 02.11 · på lista nå\ndata mangler 03.11–04.11"   # egen linje i verktøytipset
    assert "data mangler" not in h                                                           # stripen viser ikke hullet
    ser = [(f"2026-11-{d:02d}", 10.0 + d) for d in range(1, 11)]
    g = PC.html("ETF", ser, None, "2026-11-10", ps)
    pane = re.search(r'<div class="pcp" data-p="1M"[^>]*>(.*?)</div></div>', g, re.S).group(1)
    assert pane.count('<rect class="pcband"') == 1 and 'class="pcmk' not in pane              # ett bånd, ingen Ut/Inn i hullet
    assert pane.count('<line class="pcgap"') == 1 and 'stroke-dasharray="3 2"' in pane and 'stroke-width="1"' in pane
    assert 'fill="#8b949e" fill-opacity=".14"' in pane                                       # fyll uendret
    assert ".tip{display:none;position:absolute;top:32px;left:0;z-index:6;width:max-content;max-width:260px;white-space:pre-line" in PC.CSS
    li = C.periods_html(ps)
    assert '<span class="lp-g"> · data mangler 03.11–04.11</span></li>' in li
