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
    dmap, first, n = C.days_ctx(_write(tmp_path, rows))
    assert dmap == {"A": 6, "B": 2, "N": 1} and first == "2026-11-05" and n == 6
    assert C.days_cell("A", dmap, first, n) == '<td class="dg"><span class="dgv">fra 05.11</span></td>'   # sammenhengende siden første loggdato
    assert C.days_cell("B", dmap, first, n) == '<td class="dg"><span class="dgv">2 dager på rad</span></td>'
    assert C.days_cell("N", dmap, first, n) == '<td class="dg"><span class="dgv">1 dag på rad</span><span class="dg-ny">Ny</span></td>'
    assert C.days_cell("OUT", dmap, first, n) == '<td class="dg"><span class="dgv">–</span></td>'


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
    assert '"rk fl sg dg"' in OV.CSS and ".ov-ct td.dg{grid-area:dg;justify-self:end}" in C.CSS   # 390: linje 2 i raden


# ---------------------------------------------------------------- logging av ut-grunner
def _snap_rank():
    snap = {"date": "2026-11-10", "tickers": [{"ticker": "KEEP", "score": 4.0, "points": {"x": 4.0}}]}
    ranked = [{"ticker": "KEEP", "score": 4.0}, {"ticker": "CUT", "score": 2.44}, {"ticker": "LOW", "score": 0.0}]
    return snap, ranked


def test_exit_codes_only_when_run_decides(tmp_path, monkeypatch):
    p = _write(tmp_path, [("2026-11-09", "KEEP", "watch", "4.0"), ("2026-11-09", "CUT", "watch", "2.6"), ("2026-11-09", "LOW", "watch", "3.1"),
                          ("2026-11-09", "GONE", "watch", "1.2"), ("2026-11-09", "REC.OL", "watch", "1.0"), ("2026-11-10", "KEEP", "watch", "4.0")])
    snap, ranked = _snap_rank()
    rows = {r["ticker"]: r for r in C.exit_rows(snap, ranked, p)}
    assert rows["CUT"]["code"] == "out_of_top60" and rows["CUT"]["new_score"] == 2.44
    assert rows["LOW"]["code"] == "below_threshold" and rows["LOW"]["old_score"] == "3.1"
    assert rows["GONE"]["code"] == ""              # ikke kandidat i dag: kan ikke avgjøres -> ingen kode
    assert rows["REC.OL"]["code"] == "delisted"    # verdikjede-rettelse listed=false, strøket 25.06.2026
    assert set(rows) == {"CUT", "LOW", "GONE", "REC.OL"} and all(r["code"] in C.CODES + ("",) for r in rows.values())
    fr = copy.deepcopy(snap); fr["frozen_from"] = "2026-11-08"
    assert {r["ticker"]: r["code"] for r in C.exit_rows(fr, ranked, p)}["CUT"] == ""   # fryst liste: ingen kode
    out = tmp_path / "list_exits.csv"
    assert C.record_exits(snap, ranked, out, p) == 4 and C.record_exits(snap, ranked, out, p) == 4   # ny kjøring samme dag erstatter
    got = list(csv.DictReader(out.open()))
    assert len(got) == 4 and list(got[0]) == C.EXIT_COLS


def test_logging_does_not_touch_snapshot_or_candidates(tmp_path):
    p = _write(tmp_path, [("2026-11-09", "KEEP"), ("2026-11-09", "CUT", "watch", "2.6"), ("2026-11-10", "KEEP")])
    snap, ranked = _snap_rank()
    a, b = json.dumps(snap, sort_keys=True), json.dumps(ranked, sort_keys=True)
    C.record_exits(snap, ranked, tmp_path / "e.csv", p)
    C.write_periods(tmp_path / "p.json", p)
    assert json.dumps(snap, sort_keys=True) == a and json.dumps(ranked, sort_keys=True) == b
    assert OV.candidates(snap) == OV.candidates(json.loads(a))


def test_pipeline_hook_after_categories_and_nightly_commits_log():
    src = Path("signaltool/pipeline.py").read_text()
    assert src.index("categories.apply(snap)") < src.index("CHG.record_exits(snap, ranked)") < src.index("from . import risk")
    assert "logs/list_exits.csv" in Path(".github/workflows/nightly.yml").read_text()


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
    assert "@media(max-width:599px){.lp-list li{max-height:40px}.lp-list .lp-r{display:block}}" in C.CSS and "ellipsis" not in C.CSS.split(".lp-note")[1]
    assert C.ticker_periods("NEVER", p2, ex) == []


def test_chart_bands_with_hover(tmp_path):
    ser = [(f"2026-11-{d:02d}", 10.0 + d) for d in range(1, 21)]
    ps = [{"inn": "2026-11-03", "ut": "2026-11-06", "title": "Ut 06.11: Mangler kurs", "lead": "Inn 03.11 · Ut 06.11:", "why": "Mangler kurs"},
          {"inn": "2026-11-15", "ut": None, "title": "Inn 15.11 · på lista nå", "lead": "Inn 15.11 · på lista nå", "why": ""}]
    h = PC.html("A", ser, None, "2026-11-20", ps)
    assert h.count('<rect class="pcband"') == len([l for l, n in PC.PERIODS if len(ser[-n:]) >= 2]) * 2
    assert "<title>Ut 06.11: Mangler kurs</title>" in h and 'fill="#8b949e"' in h
    assert '<p class="lp-note">' in h and h.index('class="lp-list"') < h.index('class="mut pcs"')
    assert "pcband" not in PC.html("A", ser, None, "2026-11-20") and "lp-note" not in PC.html("A", ser)
