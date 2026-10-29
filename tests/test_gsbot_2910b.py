"""GSbot 29.10 runde 2: ⓘ 32×32, dempet Oversikt/tema, evidensmerker fra AnalBots tabell, resultatregler, ferskhet og «Ingen handel»."""
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from signaltool import evidens_status as ES
from signaltool import overview as OV
from signaltool import results as RS
from signaltool import rowfresh as RF
from signaltool import since as SN
from signaltool import site as S
from signaltool import site_layout as L
from signaltool import names as NM

MD = Path(__file__).resolve().parent.parent / "reports" / "natt" / "evidens_signaltyper.md"


# 1. ⓘ: ikon 14 px, trykkflate 32×32 via ::before
def test_score_info_hit_area_css():
    c = S.SCORE_CSS
    assert "width:14px;height:14px;font-size:14px" in c and "::before{content:\"\";position:absolute" in c and "width:32px;height:32px" in c
    assert S.SCORE_I_JS in S.page("X", "<p>x</p>")


# 2. F har navn fra Yahoo-cachen
def test_f_name_from_cache():
    assert NM.name("F") and NM.missing(["F"]) == []


# 3. Dempet Oversikt og temaer
def _snap():
    return {"date": "2026-10-29", "themes": [{"key": "a", "name": "A", "score": 2.5}, {"key": "b", "name": "B", "score": 1.0}],
            "tickers": [{"ticker": "VRT", "score": 3.98, "_risk": {"level": "Høy"}}]}


def test_overview_themes_muted_one_info():
    h = OV.themes_html(_snap(), wk={})
    head = h.split("</h2>")[0]
    assert head.count('class="ri ri-c sc-i"') == 1 and "Rangering, ikke testet" in head
    assert h.count("sc-i") == 1   # ingen ⓘ på stolpene
    assert h.count('class="sc sc-mu"') == 2 and h.count('<i class="mu"') == 2
    assert ".ov-bar .tr i.mu{background:#475569}" in S.SCORE_CSS and ".ov-bar .sc.sc-mu{font-size:14px;color:#94a3b8}" in S.SCORE_CSS


def test_overview_candidates_muted():
    h = OV.two_col_html(_snap())
    assert '<span class="sc-mu" title="Rangering, ikke testet">4,0 p</span>' in h and h.split("</h2>")[0].count("sc-i") == 1


# 4. Evidensmerker
def test_evidence_file_rows_and_no_dnb():
    rs = ES.rows()
    assert len(rs) == 35 and not any("DNB" in r["signaltype"] for r in rs)
    r = ES.by_name("Risikonivå Lav/Middels/Høy")
    assert r["status"] == "Bestått (på svingninger, IKKE avkastning)" and r["n"] == "US 499 tickere/1023 uker; Oslo 264/762" and r["dato"] == "25.10*"


@pytest.mark.skipif(not MD.exists(), reason="rapporten ligger ikke i repoet (reports/* committes ikke)")
def test_evidence_file_matches_report_verbatim():
    md, out, sec = MD.read_text(), [], None
    for line in md.splitlines():
        if line.startswith("## "):
            sec = line[3:]
            continue
        if line.startswith("|") and not line.startswith("|---") and not line.startswith("| Signaltype") and sec != "Ikke på offentlig side":
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            out.append((c[0].replace("**", ""), c[1].replace("**", ""), c[2], c[-1].replace("\\*", "*")))
    assert [(r["signaltype"], r["status"], r["n"], r["dato"]) for r in ES.rows()] == out


def test_klass_and_order():
    assert ES.klass("Bestått (på svingninger, IKKE avkastning)") == "Bestått"
    assert ES.klass("Ikke bestått, FLAG") == "Ikke bestått" and ES.klass("For lav n") == "For lav n" and ES.klass("Ikke testet") == "Ikke testet"
    assert ES.ORDER == ("Bestått", "For lav n", "Ikke testet", "Ikke bestått")
    t = ES.table_html()
    ks = [ES.klass(m) for m in re.findall(r'class="evs evs-\w+" aria-label="Evidens: ([^·]+?) ·', t)]
    assert ks == sorted(ks, key=ES.ORDER.index) and ks[0] == "Bestått" and ks.count("Bestått") == 1   # bare risikonivå
    assert "PEAD topp/topp (testet" not in t and "FLAG" not in t


def test_chip_text_aria_and_risk_tip():
    c = ES.for_key("congress_buys")
    assert ">Ikke bestått · n=5583 / 7533 (var. A) · 25.10*</span>" in c and 'aria-label="Evidens: Ikke bestått · n=5583 / 7533 (var. A) · 25.10*"' in c
    assert "evs-fail" in c
    r = ES.for_key("risk", short=True)
    assert "evs-pass" in r and ">Bestått</span>" in r and "Bestått for svingninger, ikke avkastning · n=763 tickere · 25.10" in r
    assert "evs-untested" in ES.for_key("price_move") and "evs-lown" in ES.chip(ES.by_name("Økende short (Oslo)"))


def test_evidence_colors():
    c = ES.CSS
    assert ".evs-pass .evd,.evd.evd-pass{background:#22c55e}" in c
    assert ".evs-fail{color:#94a3b8}.evs-fail .evd,.evd.evd-fail{border:1.5px solid #64748b;background:transparent}" in c
    assert ".evs-untested .evd,.evd.evd-untested{background:#94a3b8}" in c
    assert ".evs-lown .evd,.evd.evd-lown{border:1.5px solid #f59e0b;background:transparent}" in c


def test_legend_order():
    t = re.sub(r"<[^>]+>", " ", ES.legend())
    assert [x for x in t.split() if x] [1:9] == ["Bestått", "For", "lav", "n", "Ikke", "testet", "Ikke", "bestått"]


# 5. Resultatregler
def test_results_rules():
    assert RS.few(12) == "For få handler (n=12)" and not RS.enough(29) and RS.enough(30)
    assert RS.short_period(4) and not RS.short_period(5) and RS.SHORT_TIP == "Kort periode, mest tilfeldig svingning."
    assert RS.control_text({"n": 10, "real": 0.1, "null_mean": 0}) == ""
    ct = RS.control_text({"n": 85, "real": 0.0025, "null_mean": 0.0057, "null_p05": -0.026, "null_p95": 0.04})
    assert "mot kontroll 20 d" in ct and "n=85" in ct


def test_track_cells_few_and_enough():
    v = {"h5": {"n": 3}, "h20": {"n": 40, "mean": 0.01, "mean_ci": [-0.01, 0.03], "hit": 0.55, "hit_ci": [0.4, 0.7], "median": 0.0}, "h60": {"n": 0}}
    h = S._track_cells(v, 30, {"h": 20, "n": 40, "real": 0.01, "null_mean": 0.0, "null_p05": -0.02, "null_p95": 0.02})
    assert "For få handler (n=3)" in h and "For få handler (n=0)" in h and "95 %" in h and "mot kontroll 20 d" in h and "FLAG" not in h
    # n < 30 selv med snitt: ingen prosent
    assert "%" not in S._track_cells({"h5": {"n": 12, "mean": 0.5, "hit": 0.9, "hit_ci": [0, 1], "median": 0}}, 30).replace("For få", "")


def test_watch_text_no_flag():
    t = L.watch_text({"cats": {"watch": {"h5": {"n": 12, "hit": 0.6}}, "kjop": {"h5": {"n": 0}}}})
    assert "Følg: For få handler (n=12)" in t and "60 %" not in t and "FLAG" not in t


def test_short_period_return_coloured_with_label():
    r = SN.ret({"price": 100, "price_date": "2026-10-27", "list_days": 2}, 105, "2026-10-29", ticker="X")
    assert r["short"] and r["td"] == 2
    h = SN.ret_inner(r, {})
    assert 'class="rv rup"' in h and '<span class="rsh-t">kort periode</span>' in h
    assert 'aria-label="Kort periode, mest tilfeldig svingning."' in h and "rsh\"" not in h
    rd = SN.ret({"price": 100, "price_date": "2026-10-27", "list_days": 2}, 95, "2026-10-29", ticker="X")
    assert 'class="rv rdn"' in SN.ret_inner(rd, {})
    r2 = SN.ret({"price": 100, "price_date": "2026-10-20", "list_days": 9}, 105, "2026-10-29", ticker="X")
    assert not r2["short"] and "rsh-t" not in SN.ret_inner(r2, {}) and 'class="rv rup"' in SN.ret_inner(r2, {})
    ln = SN.line_rk({"since": "2026-10-27"}, "", r)
    assert 'class="rn rup"' in ln and "kort periode" in ln


def test_return_colours_css():
    import signaltool.since as m
    src = open(m.__file__, encoding="utf-8").read()
    assert "main .rv.rup,main .rn.rup{color:#22c55e}" in src and "main .rv.rdn,main .rn.rdn{color:#ef4444}" in src
    assert ".rsh-t{font-size:11px;font-weight:400;color:#94a3b8" in src and ".rv.rsh" not in src


def test_short_cell_compact_class():
    r = SN.ret({"price": 100, "price_date": "2026-10-27", "list_days": 2}, 105, "2026-10-29", ticker="X")
    h = SN.ret_inner(r, {})
    assert h.index('class="rv rup"') < h.index("Kort periode, mest tilfeldig") < h.index('class="rsh-t"')
    assert '<td class="ret-c rsh-c"' in SN.ret_cell(r, {})
    r2 = SN.ret({"price": 100, "price_date": "2026-10-20", "list_days": 9}, 105, "2026-10-29", ticker="X")
    assert '<td class="ret-c"' in SN.ret_cell(r2, {})


def test_legend_explains_star():
    assert "* dato = filens endringsdato" in ES.legend()


# 6. Ferskhet og «Ingen handel»
NOW = datetime(2026, 10, 29, 19, 0, tzinfo=ZoneInfo("Europe/Oslo"))


def test_stale_price_warning():
    e = {"ticker": "EQNR.OL", "stats": {"close": 1, "last_date": "2026-10-28"}}
    assert RF.lag(e, NOW) == ("2026-10-28", "2026-10-29")
    assert RF.lag({"ticker": "EQNR.OL", "stats": {"close": 1, "last_date": "2026-10-29"}}, NOW) is None
    assert RF.lag({"ticker": "AAPL", "stats": {"close": 1, "last_date": "2026-10-28"}}, NOW) == ("2026-10-28", "2026-10-28") or \
        RF.lag({"ticker": "AAPL", "stats": {"close": 1, "last_date": "2026-10-28"}}, NOW) is None   # US: 19.00 Oslo = før stengetid i NY
    assert RF.lag({"ticker": "NKT.CO", "stats": {"close": 1, "last_date": "2026-10-01"}}, NOW) is None   # ukjent børs: ingen varsel


def test_no_trade_only_on_zero_volume():
    base = {"ticker": "CAMBI.OL", "stats": {"close": 10, "last_date": "2026-10-29", "ret_1d": 0.0}}
    assert not RF.no_trade(base, NOW)                                          # uendret kurs alene: aldri
    assert not RF.no_trade({**base, "stats": {**base["stats"], "vol_1d": 1200.0}}, NOW)
    assert RF.no_trade({**base, "stats": {**base["stats"], "vol_1d": 0.0}}, NOW)
    assert not RF.no_trade({**base, "stats": {**base["stats"], "vol_1d": float("nan")}}, NOW)
    RF.NOW[0] = NOW
    try:
        assert "Ingen handel" in RF.chips({**base, "stats": {**base["stats"], "vol_1d": 0.0}}) and RF.chips(base) == ""
    finally:
        RF.NOW[0] = None


def test_vol_1d_in_ticker_stats():
    import numpy as np
    import pandas as pd
    from signaltool.collectors import markets as M
    idx = pd.date_range("2026-01-01", periods=120, freq="B")
    df = pd.DataFrame({"Close": np.linspace(10, 12, 120), "Volume": [1000.0] * 119 + [0.0]}, index=idx)
    assert M.ticker_stats(df)["vol_1d"] == 0.0
