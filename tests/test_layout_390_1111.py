"""UxBot 11.11 (bindende): PRICE_HOLD i tabellen som «Venter», ingen inn-prikk før innkursen finnes, og 390-raden i to linjer."""
import re
import shutil

import pytest

from signaltool import since as SN
from signaltool import site as S
from signaltool import ux390 as U


def _e(t="KOG.OL", name="Kongsberg Gruppen ASA", n_pts=4, ret=None, since=None):
    keys = ["unusual_volume", "unusual_move", "theme_attention", "insider", "contract"][:n_pts]
    return {"ticker": t, "name": name, "score": 6.2, "points": {k: 3.0 - i * 0.5 for i, k in enumerate(keys)},
            "stats": {"ret_5d": 0.01, "ret_20d": 0.02, "close": 355, "last_date": "2026-11-10"}, "_risk": {"level": "Høy"},
            "_since": since or {"since": "2026-10-23", "price": 308.8, "price_date": "2026-10-21", "category": "buy", "days": 19, "list_days": 19},
            "_ret": ret if ret is not None else {"r": 0.138, "ex": 0.152, "bench": "OSEBX", "last": "2026-11-10", "illiquid": False},
            "themes": [], "evidence": [], "flags": []}


# 1) PRICE_HOLD
def test_hold_cell_like_venter_gray_13_18_and_gray_dash_vs_index():
    s = {"since": "2026-10-29", "price": None, "price_date": None, "entry_state": SN.HOLD}
    c = SN.ret_cell(None, s)
    assert '<span class="rtx">– kurs under kontroll</span><span class="rex">–</span>' in c
    assert "rv rna" not in c and 'data-v=""' in c
    assert re.search(r"\.rtx\{font-size:13px;line-height:18px;font-weight:400;color:#94a3b8", SN.CSS)
    assert "td.ret-c .rtx+.rex{color:#94a3b8}" in SN.CSS
    assert SN.ret_inner(None, s) == SN.rtx("– " + SN.HOLD_T)


# 2) Graf
def test_no_entry_dot_while_waiting_even_with_known_entry():
    s = {"since": "2026-11-10", "price": 35.87, "price_date": "2026-11-09"}
    assert SN.dot_date(s, {"new": True, "last": "2026-11-09"}) is None          # BEN: «Venter på første sluttkurs»
    assert SN.dot_date(s, {"r": 0.01, "last": "2026-11-11"}) == "2026-11-09"     # innkursen finnes -> prikk
    assert SN.dot_date(s) == "2026-11-09"
    assert SN.dot_date({**s, "price": None, "entry_state": SN.HOLD}) is None


def test_ticker_page_passes_return_to_dot_date():
    src = open(S.__file__).read()
    assert src.count('SN.dot_date(e.get("_since"), e.get("_ret"))') == 1


# 3) 390-tabellen
def test_mobile_plus_n_counts_all_but_first_chip():
    assert 'data-m="3"' in S.ticker_row(_e(n_pts=4))
    assert 'data-m="1"' in S.ticker_row(_e(n_pts=2))
    assert "data-m=" not in S.ticker_row(_e(n_pts=1))


def test_css_rules_only_below_600_and_loaded_last():
    css = U.CSS
    body = css.split("@media(max-width:599px){", 1)[1]
    assert css.startswith("@media(max-width:599px){")
    rest = css.rsplit("}@media(min-width:600px)", 1)[1]
    assert rest.strip() == "{#tf-table td.sg-c::after{content:none}}"
    for need in ("grid-template-columns:auto minmax(0,1fr) 44px", "max-height:96px", "font-size:15px!important;line-height:20px!important",
                 "text-overflow:ellipsis", "min-width:0!important", "font-size:12px!important;line-height:16px!important",
                 "font-size:13px!important;line-height:18px!important", "text-align:right!important", "width:44px!important",
                 "flex-wrap:wrap!important", "content:'+' attr(data-m)"):
        assert need in body, need
    src = open(S.__file__).read()
    assert "+ CHG.CSS + U390.CSS" in src


def _page(rows):
    css = "".join([S.CHIP_CSS, SN.CSS, U.CSS])
    try:
        from signaltool import ux2, usability
        css = ux2.CSS + usability.CSS + css + U.CSS
    except Exception:
        pass
    return (f'<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{{margin:0;padding:0 10px;font-family:sans-serif}}{css}</style></head>'
            f'<body><div id="tf-table"><div class="card"><p class="evleg">Evidens: <span class="evs">● Bestått</span> <span class="evs">○ For lav n</span> '
            f'<span class="evs">● Ikke testet</span> <span class="evs">○ Ikke bestått</span> <span class="evs">◌ DNB</span></p><div class="tw"><table><tbody>'
            f'<tr><th class="rk-h sortable">Risiko</th><th class="ret-h">Avkastning</th></tr>{rows}</tbody></table></div></div></div></body></html>')


@pytest.mark.skipif(not (shutil.which("google-chrome") or shutil.which("chromium")), reason="ingen headless Chrome")
def test_headless_390_rows_le_96_and_no_horizontal_scroll(tmp_path):
    pw = pytest.importorskip("playwright.sync_api")
    long = "Et svært langt selskapsnavn som må kuttes med ellipsis ASA"
    rows = "".join([S.ticker_row(_e()), S.ticker_row(_e("MAERSK-B.CO", long, 5)), S.ticker_row(_e("TECH.OL", "Techstep", 1, ret={},
                    since={"since": "2026-10-29", "price": None, "price_date": None, "entry_state": SN.HOLD})),
                    S.ticker_row(_e("BEN", "Franklin Resources", 3, ret={"new": True, "last": "2026-11-09"}))])
    f = tmp_path / "t.html"
    f.write_text(_page(rows))
    with pw.sync_playwright() as p:
        b = p.chromium.launch(channel="chrome" if shutil.which("google-chrome") else None)
        res = {}
        for w in (390, 1280):
            pg = b.new_page(viewport={"width": w, "height": 900})
            pg.goto(f.as_uri())
            res[w] = pg.evaluate("""()=>{const rs=[...document.querySelectorAll('#tf-table tr.rowlink')];
              const R=e=>e&&e.offsetParent!==null?e.getBoundingClientRect():null,ov=(a,b)=>a&&b&&a.left<b.right-0.5&&b.left<a.right-0.5&&a.top<b.bottom-0.5&&b.top<a.bottom-0.5;
              const bad=[];rs.forEach(r=>{const q=s=>R(r.querySelector(s));const el=[q('.tn .nm'),q('.tn .tk'),q('td.ret-c'),q('td.mcol .mstar'),q('.rkp-s .score'),q('.rk'),q('td.sg-c')];
                for(let i=0;i<el.length;i++)for(let j=i+1;j<el.length;j++)if(ov(el[i],el[j]))bad.push(r.dataset.t+i+'/'+j)});
              const de=document.documentElement;return {h:rs.map(r=>r.getBoundingClientRect().height),sw:de.scrollWidth,cw:de.clientWidth,bad,
                score:R(rs[0].querySelector('.rkp-s .score')).width,vis:[...rs[0].querySelectorAll('td.sg-c .pill')].filter(e=>e.offsetParent).length,
                plus:getComputedStyle(rs[0].querySelector('td.sg-c'),'::after').content}}""")
            pg.close()
        b.close()
    m = res[390]
    assert max(m["h"]) <= 96, m["h"]
    assert m["sw"] == m["cw"], m
    assert not m["bad"], m["bad"]
    assert m["score"] == 44 and m["vis"] == 1 and m["plus"] == '"+3"'
    assert res[1280]["plus"] in ("none", "normal")
