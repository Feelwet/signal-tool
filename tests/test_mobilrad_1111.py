"""Rommet 11.11 (AnalBot/UxBot, bindende): 390-raden er én lenke (≥ 44 px, fokusring), «Data x/7» grå 12/16 etter tickeren,
periode rett etter hver prosent (grå 12/16, kuttes aldri), grå rader uten periode, ≤ 96 px og ingen horisontal scroll. 1280 uendret."""
import shutil

import pytest

from signaltool import datacov as DC
from signaltool import since as SN
from signaltool import site as S
from signaltool import ux390 as U
from tests.test_layout_390_1111 import _e, _page


def test_period_after_each_percentage_and_none_on_gray_rows():
    h = SN.ret_inner({"r": 0.012, "ex": -0.004, "bench": "OSEBX", "last": "2026-11-13", "illiquid": False},
                     {"since": "2026-11-10", "price": 1.0, "price_date": "2026-11-10"})
    assert '<span class="rv rup">+1,2 %</span><span class="rper"> siden 10.11</span>' in h
    assert '<span class="rex-m">−0,4 pp<span class="rper"> mot indeks siden 10.11</span></span>' in h   # samme periode som kolonnen ved 1280
    hold = SN.ret_inner(None, {"since": "2026-10-29", "price": None, "price_date": None, "entry_state": SN.HOLD})
    venter = SN.ret_inner({"new": True, "last": "2026-11-09"}, {"since": "2026-11-10", "price": 35.87, "price_date": "2026-11-09"})
    assert "rper" not in hold and "rper" not in venter


def test_css_link_focus_data_and_period_only_below_600():
    mob = U.CSS.split("@media(max-width:599px){", 1)[1].split("}@media(min-width:600px)", 1)[0]
    for need in ("a.row-a{position:absolute;top:0;left:0;bottom:0;right:44px;z-index:1",
                 "td.mcol .mstar{width:44px;height:44px;min-width:44px;min-height:44px",
                 "min-height:44px", "a.row-a:focus-visible",
                 ".tk .dci{display:inline!important", "color:#94a3b8!important;font-size:12px!important;line-height:16px!important",
                 ".rper{display:inline!important;font-size:12px!important;line-height:16px!important", ".rex:has(+.rex-m){display:none!important}"):
        assert need in mob, need
    assert U.CSS.rstrip().endswith(".rper,.rex-m{display:none}")


@pytest.mark.skipif(not (shutil.which("google-chrome") or shutil.which("chromium")), reason="ingen headless Chrome")
def test_headless_390_link_data_period_96px(tmp_path):
    pw = pytest.importorskip("playwright.sync_api")
    long = "Et svært langt selskapsnavn som må kuttes med ellipsis ASA"
    rows = "".join([S.ticker_row(_e()), S.ticker_row(_e("MAERSK-B.CO", long, 5)), S.ticker_row(_e("AKRBP.OL", "Aker BP ASA", 3,
                    ret={"r": -0.0123, "ex": -0.0441, "bench": "OSEBX", "last": "2026-11-13", "illiquid": False, "short": True})),
                    S.ticker_row(_e("TECH.OL", "Techstep", 1, ret={}, since={"since": "2026-10-29", "price": None, "price_date": None, "entry_state": SN.HOLD})),
                    S.ticker_row(_e("BEN", "Franklin Resources", 3, ret={"new": True, "last": "2026-11-09"}))])
    html = _page(rows).replace("</style>", DC.CSS + "</style>", 1)
    f = tmp_path / "t.html"
    f.write_text(html)
    js = """()=>{const rs=[...document.querySelectorAll('#tf-table tr.rowlink')];const de=document.documentElement;
      const vis=e=>!!e&&e.getClientRects().length>0&&getComputedStyle(e).display!=='none';
      return {h:rs.map(r=>r.getBoundingClientRect().height),sw:de.scrollWidth,cw:de.clientWidth,
        data:rs.map(r=>{const d=r.querySelector('.tk .dchip');if(!vis(d))return null;const b=d.getBoundingClientRect(),rb=r.getBoundingClientRect(),cs=getComputedStyle(d);
          return {fs:cs.fontSize,lh:cs.lineHeight,c:cs.color,inside:b.right<=rb.right-44+0.5&&b.width>0,top:b.top-rb.top}}),
        per:rs.map(r=>[...r.querySelectorAll('td.ret-c .rper')].filter(vis).map(p=>{const b=p.getBoundingClientRect(),cs=getComputedStyle(p),c=p.closest('td');
          return {t:p.textContent,fs:cs.fontSize,lh:cs.lineHeight,c:cs.color,cut:b.right>c.getBoundingClientRect().right+0.5||b.right>r.getBoundingClientRect().right+0.5}})),
        rexm:rs.map(r=>vis(r.querySelector('td.ret-c .rex-m'))),rex:rs.map(r=>vis(r.querySelector('td.ret-c .rex'))),
        hit:rs.map(r=>{const b=r.getBoundingClientRect(),x=b.left+b.width*0.45,y=b.top+b.height*0.75,e=document.elementFromPoint(x,y);const a=e&&e.closest('a.row-a');return !!(a&&a.getAttribute('href')===r.dataset.href)}),
        star:rs.map(r=>{const s=r.querySelector('td.mcol .mstar'),a=r.querySelector('a.row-a');if(!s||!a)return null;const sb=s.getBoundingClientRect(),ab=a.getBoundingClientRect(),cs=getComputedStyle(s);return {w:cs.width,h:cs.height,outside:!a.contains(s)&&sb.left>=ab.right-0.5};}),
        score:rs.map(r=>vis(r.querySelector('.rkp-s .score'))),
        nmEll:getComputedStyle(rs[1].querySelector('.tn .nm')).textOverflow}}"""
    with pw.sync_playwright() as p:
        b = p.chromium.launch(channel="chrome" if shutil.which("google-chrome") else None)
        res = {}
        for w in (390, 1280):
            pg = b.new_page(viewport={"width": w, "height": 900})
            pg.goto(f.as_uri())
            res[w] = pg.evaluate(js)
            if w == 390:
                pg.keyboard.press("Tab")
                for _ in range(8):
                    if pg.evaluate("()=>!!document.activeElement.closest('a.row-a')"):
                        break
                    pg.keyboard.press("Tab")
                res["ring"] = pg.evaluate("()=>{const a=document.activeElement.closest('a.row-a');const cs=getComputedStyle(a);return [cs.outlineStyle,cs.outlineWidth]}")
            pg.close()
        b.close()
    m = res[390]
    assert max(m["h"]) <= 96 and min(m["h"]) >= 44, m["h"]
    assert m["sw"] == m["cw"], (m["sw"], m["cw"])
    assert all(m["hit"]), m["hit"]                       # hele raden (også linje 2) er lenken til tickersiden
    assert all(s and s["w"] == "44px" and s["h"] == "44px" and s["outside"] for s in m["star"]), m["star"]
    assert res["ring"] == ["solid", "2px"], res["ring"]   # synlig fokusring på raden ved tastatur
    assert all(d and d["fs"] == "12px" and d["lh"] == "16px" and d["c"] == "rgb(148, 163, 184)" and d["inside"] and d["top"] < 30 for d in m["data"]), m["data"]
    assert all(m["score"]), "scoreboksen skal stå når «Data x/7» får plass"
    assert m["nmEll"] == "ellipsis"
    for i in (0, 1, 2):
        ts = [x["t"].strip() for x in m["per"][i]]
        assert ts[0] == "siden 21.10" and ts[1] == "mot indeks siden 21.10", ts   # AnalBot 16.11: indeksparets startdato (price_date)
        assert all(x["fs"] == "12px" and x["lh"] == "16px" and x["c"] == "rgb(148, 163, 184)" and not x["cut"] for x in m["per"][i]), m["per"][i]
        assert m["rexm"][i] and not m["rex"][i]
    assert m["per"][3] == [] and m["per"][4] == []        # grå rader: ingen periode
    assert m["rex"][3]                                     # TECH beholder grå «–» i mot indeks
    d = res[1280]
    assert all(not x for x in d["per"]) and not any(d["rexm"]) and all(d["rex"][:4])   # 1280 uendret: ingen periodetekst
