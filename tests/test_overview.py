import json
from pathlib import Path
from signaltool import overview as OV


def _snap(**kw):
    s = {"date": "2026-10-25", "themes": [{"key": f"t{i}", "name": f"Tema {i}", "score": 3 - i * 0.3} for i in range(8)],
         "tickers": [{"ticker": "A.OL", "category": "kjop", "score": 5}, {"ticker": "B", "category": "hold", "score": 4}, {"ticker": "C", "category": "watch", "score": 3}],
         "regime": {"OSEBX.OL": {"below": False, "risk_off": False}, "^GSPC": {"below": True, "risk_off": False}},
         "calendar": [{"date": "2026-10-20", "source": "X", "title": "gammel"}, {"date": "2026-10-26", "source": "Y", "title": "NUE"},
                      {"date": "2026-10-28", "source": "Y", "title": "DHT"}, {"date": "2026-10-29", "source": "Y", "title": "STNG"}, {"date": "2026-11-05", "source": "NB", "title": "NB"}],
         "track_record": {"cats": {"kjop": {"h5": {"n": 0}}}},
         "briefing": {"alerts": [{"level": "info", "title": "Hormuzstredet: x", "link": ""}, {"level": "info", "title": "Hormuzstredet: y", "link": ""}],
                      "changes": {"prev_date": "2026-10-24", "items": [{"text": f"endring {i}"} for i in range(9)]}}}
    s.update(kw)
    return s


def test_hit_line_uses_real_n_and_flags():
    assert OV.kjop_hit_line({"cats": {"kjop": {"h5": {"n": 0}}}}) == "Kjøp-treffrate: n=0, for lav (FLAG)"
    assert "n=12" in OV.kjop_hit_line({"cats": {"kjop": {"h5": {"n": 12, "hit": 0.9}}}})
    ok = OV.kjop_hit_line({"cats": {"kjop": {"h5": {"n": 40, "hit": 0.7, "hit_ci": [0.55, 0.8]}}}})
    assert "70 %" in ok and "FLAG" not in ok
    assert "FLAG" in OV.kjop_hit_line({"cats": {"kjop": {"h5": {"n": 40, "hit": 0.55, "hit_ci": [0.4, 0.7]}}}})


def test_strip_has_four_tiles_and_stacked_bar():
    h = OV.strip_html(_snap())
    assert h.count('class="ov-tile"') == 4 and "ov-stack" in h and "I morgen" in h and "NUE" in h
    assert 'class="ov-dot up"></span>OSEBX' in h and 'class="ov-dot dn"></span>S&amp;P' in h
    assert "for lav (FLAG)" in h


def test_week_change_none_without_history(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("date,theme,score\n2026-10-25,t0,3\n2026-10-24,t0,1\n")
    assert OV.week_change(p, "2026-10-25") == {}
    h = OV.themes_html(_snap(), {})
    assert "▲" not in h and "▼" not in h and h.count('class="ov-bar"') == 8 and "Alle temaer (8)" in h
    assert "Eksperimentelt" in h


def test_week_change_from_log(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("date,theme,score\n2026-10-25,t0,3\n2026-10-18,t0,2.5\n2026-10-25,t1,1\n2026-10-18,t1,1.4\n")
    wk = OV.week_change(p, "2026-10-25")
    assert round(wk["t0"][0], 2) == 0.5 and wk["t0"][1] == "2026-10-18"
    h = OV.themes_html(_snap(), wk)
    assert "▲0,5" in h and "▼0,4" in h


def test_changes_max5_dedup_and_calendar3():
    h = OV.changes_alerts_html(_snap())
    assert h.count("<li>") == 5 and h.count("Hormuzstredet") == 1
    c = OV.calendar_html(_snap())
    assert c.count("<li>") == 3 and "gammel" not in c and "NB" not in c.split("Hele")[0].replace("(NB)", "")



def test_change_text_arrows():
    h = OV.change_text("Tema «Valg»: score 1.48 → 2.65")
    assert "▲1,17" in h and "nå 2,65" in h and "→" not in h
    assert "▼0,50" in OV.change_text("Tema «X»: score 1.00 → 0.50")
    assert OV.change_text("5 nye dokumenter") == "5 nye dokumenter"


def test_mobile_bar_name_own_line():
    assert "@media(max-width:599px){.ov-bar{grid-template-columns:1fr auto auto" in OV.CSS and "grid-column:1/-1" in OV.CSS
