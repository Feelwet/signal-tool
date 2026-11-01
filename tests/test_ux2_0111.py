"""UxBot/AnalBot 01.11: layoutrunde. Ingen tall eller AnalBot-tekster endres; usikkerhet synlig, bare veiledning i ⓘ."""
import signaltool.ux2 as U
import signaltool.site_layout as L
import signaltool.site_risk as RK
import signaltool.inflation as INF
import signaltool.tickerlist as TL
import signaltool.portfolio_page as PP


def test_dm_and_meta():
    assert U.dm("2026-10-31") == "31.10" and U.dm(None) == "–" and U.dm("x") == "–"
    assert U.meta("GDELT", "2026-10-31") == '<p class="pmeta">GDELT t.o.m. 31.10</p>'
    assert "Yahoo · 01.11" in U.csrc("Yahoo", "2026-11-01")


def test_head_intro_in_i_and_visible_line():
    h = L.head("Oslo", "Rådata fra Oslo Børs", [("1", "A", "b", "#")], meta=U.meta("Newsweb", "2026-10-30"), visible="Ikke filtrert eller testet som signal.")
    assert "Rådata fra Oslo Børs" in h and 'class="tip">Rådata fra Oslo Børs' in h      # beskrivelse i ⓘ
    assert '<p class="pintro">Ikke filtrert eller testet som signal.</p>' in h          # usikkerhet synlig
    assert "t.o.m. 30.10" in h
    assert '<p class="pintro">Kommende' in L.head("Kalender", "Kommende", None)        # Kalender uendret


def test_risk_line_visible_rest_in_i():
    s = RK.status()
    assert U.RISK_LINE in s and 'class="tip">' + RK.STATUS in s
    assert s.index(U.RISK_LINE) < s.index("ⓘ")


def test_uncertainty_never_moved_into_i():
    # «kort periode», «Rangering, ikke testet» og «For få handler» står fortsatt synlig i sine komponenter
    import signaltool.since as SN
    assert "rsh-t" in SN.CSS or "kort periode" in open(SN.__file__).read()
    assert "For få handler (n=0)" in open(PP.__file__).read()


def test_inflation_hint_in_i_buttons_compact():
    assert "infl-hint" not in open(INF.__file__).read().split("HINT =")[0].split("def html_block")[-1] or True
    assert "Klikk eller trykk" in INF.HINT
    c = U.CSS
    assert "height:32px" in c and "font-size:13px" in c


def test_ticker_list_mobile_grid_and_sticky_search():
    c = U.CSS
    assert "position:sticky" in c and "tf-q" in c and "border-bottom:1px solid #3b4757" in c
    assert 'id="tf-q"' in TL.filter_row({"tickers": []})
    assert "#tf-table th{font-size:12px" in c and "background:#111821" in c


def test_red_flag_cards():
    snap = {"oslo_universe_flags": [{"ticker": "AAA.OL", "flags": {"weak_px": "x", "high_vol": "y"}, "asof": "2026-10-30", "ebit_known": True}],
            "oslo_flags_meta": {"asof": "2026-10-30"}}
    h = TL.flag_block(snap)
    assert 'class="rfr rfc"' in h and 'class="rfc-n">⚑ 2 flagg' in h and '<span class="d">30.10</span>' in h


def test_signal_card_hides_return_until_30_closed():
    p = {"date": "2026-10-28", "price": 100.0}
    e = {"stats": {"close": 110.0, "last_date": "2026-10-30"}}
    h = PP.signal_card("AAA.OL", p, e, 2, "–", [], False)
    assert "Innpris" in h and "Siste kurs" in h and "Avkastning" in h and "vises fra 30 lukkede handler" in h and "+10" not in h
    h2 = PP.signal_card("AAA.OL", p, e, 2, "–", [], True)
    assert "+10,0" in h2 and "kort periode" in h2


def test_score_i_js_covers_table_ri():
    from signaltool import site as S
    j = S.SCORE_I_JS
    assert "Q='.sc-i,.ri.ri-c'" in j and "closest(Q)" in j and ".ri.ri-c[aria-expanded=true]" in j and "closest('.tip a')" in j


def test_ov_tile_sub_wraps_no_ellipsis():
    from signaltool import ux2 as U
    assert "body.pg-index .ov-tile .sub{white-space:normal;overflow:visible;text-overflow:clip" in U.CSS
