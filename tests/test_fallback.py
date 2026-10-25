"""Runde 21: Yahoo-vakt (> 50 % feil = kildefeil), Ikke rangert for erstattere, delt beløpsspenn, sektor 1:1."""
import json
from signaltool import decision as D, site_sources as SS, site_sector as SC
from signaltool.collectors import congress


def _snap(ts):
    return {"tickers": [{"ticker": t} for t in ts]}


def test_fallback_triggers_and_reuses(tmp_path):
    p = tmp_path / "lg.json"
    p.write_text(json.dumps({"AAA": {"date": "2026-10-21", "fund": {"sector": "Industrials", "marketCap": 1e9}},
                             "BBB": {"date": "2026-10-01", "fund": {"sector": "Energy"}}}))
    D._RUN["fail"] = False
    snap = _snap(["AAA", "BBB", "CCC"])
    dec = {"CCC": {"sector": "Technology"}}
    fb = D.fallback(snap, dec, today="2026-10-26", path=p)
    assert fb["source_fail"] and fb["used"] == ["AAA"]          # 3 handelsdager: gjenbrukt; BBB > 5 handelsdager: 4/7-regel
    assert dec["AAA"]["marketCap"] == 1e9 and "BBB" not in dec
    e = {"ticker": "AAA", "decision": dec["AAA"]}
    assert D.fb_text(e) == "Fundamentaldata fra 21.10 (Yahoo feilet i dag)"
    assert '<p class="fb-line">Fundamentaldata fra 21.10 (Yahoo feilet i dag)</p>' == SS.fb_line(e)
    assert 'title="Fundamentaldata fra 21.10 (Yahoo feilet i dag)"' in SS.fb_dot(e)
    D._RUN["fail"] = False


def test_no_fallback_saves_lastgood(tmp_path):
    p = tmp_path / "lg.json"
    D._RUN["fail"] = False
    dec = {"AAA": {"sector": "Energy"}, "BBB": {"marketCap": 5.0}}
    fb = D.fallback(_snap(["AAA", "BBB", "CCC"]), dec, today="2026-10-26", path=p)
    assert not fb["source_fail"] and fb["used"] == []
    assert json.loads(p.read_text())["AAA"]["date"] == "2026-10-26"
    assert SS.fb_line({"ticker": "AAA", "decision": dec["AAA"]}) == ""


def test_split_amount_joined():
    txt = ("JT    Lockheed Martin Corporation           S (partial)   09/17/2026 10/02/2026   $15,001 -\n"
           "      Common Stock (LMT) [ST]                                                     $50,000\n"
           "      F       S    : New\n\n\n"
           "      Foo Inc (FOO) [ST]   P   09/17/2026 10/02/2026   $1,001 - $15,000\n\n\n"
           "      Bar Inc (BAR) [ST]   P   09/17/2026 10/02/2026\n")
    r = congress.parse_ptr_text(txt)
    assert [x["amount"] for x in r] == ["$15,001 - $50,000", "$1,001 - $15,000", ""]
    assert r[0]["ticker"] == "LMT"


def test_sector_direct_translation():
    assert SC.SEC_NO["Utilities"] == "Forsyning" and SC.SEC_NO["Industrials"] == "Industri"
    assert "Sektor: Yahoo Finance" in SC.SRC


def test_replacement_low_goes_unranked(monkeypatch):
    from signaltool import pipeline, decision as dec
    monkeypatch.setattr(dec, "apply", lambda s: s)
    good = {"stats": {"close": 1, "sma50": 1}, "decision": {"sector": "x", "marketCap": 1}}
    pos = [{"ticker": f"T{i}", **good} for i in range(59)] + [{"ticker": "LOW1"}] + [{"ticker": "LHX"}] + [{"ticker": "T99", **good}]
    snap = {"tickers": pos[:60]}
    st = {}
    pipeline._coverage_cut(snap, pos, st)
    unr = [e["ticker"] for e in snap["tickers"] if e.get("unranked")]
    assert unr == ["LOW1", "LHX"] and sum(1 for e in snap["tickers"] if not e.get("unranked")) == 60
