"""UxBot 11.11: Inn/Ut-etiketter i egen 16 px-rad øverst i kursgrafen; kollisjonsregel nyeste -> eldste (≥ 28 px, ingen overlapp)."""
import json
import re
import shutil
import subprocess

import pytest

from signaltool import pricechart as PC
from tests.test_ov_changes_1111 import _write, _nvda_like
from signaltool import ov_changes as C

NODE = shutil.which("node")


def _lay(ms, W):
    js = PC.LAY_JS + f";process.stdout.write(JSON.stringify(pcLay({json.dumps(ms)},{W})))"
    return json.loads(subprocess.check_output([NODE, "-e", js], text=True))


def _nv_html(tmp_path):
    p = _write(tmp_path, [(d, "NV") for d in ("2026-09-27", "2026-09-28", "2026-10-13", "2026-10-27", "2026-11-06", "2026-11-10")]
               + [(d, "X") for d in ("2026-09-27", "2026-09-28", "2026-10-12", "2026-10-13", "2026-10-18", "2026-10-27", "2026-10-29",
                                    "2026-11-06", "2026-11-07", "2026-11-10")])
    ps = C.ticker_periods("NV", p, tmp_path / "x.csv", None)
    return PC.html("NV", _nvda_like(), None, "2026-11-10", ps), ps


def test_label_row_above_plot_never_on_axis_numbers():
    css = PC.CSS
    assert ".pcp{position:relative;padding-top:16px;overflow-x:clip}.pcl{position:absolute;left:0;right:0;top:16px;bottom:0}" in css   # 16 px-rad over grafen
    assert ".pcl .hi{top:2px}" in css                                  # UxBot 11.11: 2 px luft under etikettraden (aksetall y ≥ 18 px)
    assert ".pcmk{position:absolute;top:-16px;bottom:0;" in css and ".pcml{position:absolute;top:0;left:9px;height:16px;font-size:11px;line-height:16px" in css
    assert 'border-left:1px solid #8b949e' in css and "top:16px;bottom:0;border-left" in css   # streken starter under etikettraden
    assert PC.LABEL_ROW == 16


@pytest.mark.skipif(not NODE, reason="node mangler")
@pytest.mark.parametrize("W", [370, 1216])   # grafbredde på 390 (kort med 10 px marg) og 1280
@pytest.mark.parametrize("lab", ["1M", "6M", "1Å"])
def test_shown_labels_do_not_overlap_each_other_or_axis(tmp_path, W, lab):
    h, ps = _nv_html(tmp_path)
    pane = re.search(r'<div class="pcp" data-p="' + lab + r'"[^>]*>(.*?)</div></div>', h, re.S).group(1)
    mk = re.findall(r'<span class="pcmk[^"]*" data-k="(Inn|Ut)"[^>]*style="left:([\d.]+)%"><span class="pcml">([^<]+)</span>', pane)
    assert mk
    ms = [{"x": float(x) * W / 100, "w": len(t) * 6.6 * 1.2} for _, x, t in mk]   # node: 6,6 px/tegn + 20 % margin (nettleseren måler)
    o = _lay(ms, W)
    shown = sorted([(ms[i]["x"], o[i]) for i in range(len(ms)) if o[i]["show"]], key=lambda z: z[0])
    assert shown and o[max(range(len(ms)), key=lambda i: ms[i]["x"])]["show"]          # nyeste vises alltid
    for (xa, a), (xb, b) in zip(shown, shown[1:]):
        assert xb - xa >= 28 and a["r"] + 28 <= b["l"]                                   # ≥ 28 px mellom streker OG mellom etikettbokser
    assert all(0 <= b["l"] and b["r"] <= W for _, b in shown)                           # innenfor grafen (aldri ut over kanten)
    # markør og bånd vises alltid, uansett etikett
    assert pane.count('class="pcmk') == len(PC.events(_nvda_like()[-dict(PC.PERIODS)[lab]:], ps))


@pytest.mark.skipif(not NODE, reason="node mangler")
def test_collision_rule_newest_first():
    o = _lay([{"x": 100, "w": 40}, {"x": 120, "w": 40}, {"x": 300, "w": 40}, {"x": 320, "w": 40}], 400)
    assert [z["show"] for z in o] == [False, True, False, True]   # 320 vises; 300 (20 px) skjules; 120 vises; 100 (20 px til 120) skjules
    e = _lay([{"x": 390, "w": 40}], 400)[0]
    assert e["show"] and e["rt"] and e["r"] <= 400                   # helt til høyre: etiketten flyttes til venstre for streken


def test_browser_measures_label_width_before_collision(tmp_path):
    """UxBot 11.11: bredden måles i nettleseren (getBoundingClientRect, ellers canvas measureText) før pcLay; 6,6 px/tegn bare i node."""
    h, _ = _nv_html(tmp_path)
    assert "function pcW(l)" in h and "getBoundingClientRect().width" in PC.MEASURE_JS and "measureText(l.textContent)" in PC.MEASURE_JS
    assert "w:pcW(ls[i])" in h and "6.6" not in PC.LAY_JS + PC.MEASURE_JS
    assert "const G=28" in PC.LAY_JS and "r+G<=b[0]||l>=b[1]+G" in PC.LAY_JS and PC.LAY_GAP == 28


@pytest.mark.skipif(not NODE, reason="node mangler")
def test_live_cases_now_hidden():
    """Live 58ae567: NVDA 6M 25,9 px mellom «Ut 18.10» og «Inn 10.11», 1Å 14,4 px mellom «Inn 28.09» og «Inn 10.11» -> eldste skjules."""
    w = lambda t: len(t) * 6.6 * 1.2
    a = {"x": 100, "w": w("Ut 18.10")}
    b = {"x": 100 + 3 + a["w"] + 25.9 - 3, "w": w("Inn 10.11")}    # 25,9 px luft mellom boksene
    o = _lay([a, b], 1216)
    assert o[1]["show"] and not o[0]["show"]
    c = {"x": 100, "w": w("Inn 28.09")}
    d = {"x": 100 + c["w"] + 14.4, "w": w("Inn 10.11")}
    assert [z["show"] for z in _lay([c, d], 1216)] == [False, True]


class _R:
    def __init__(self, l, w): self.left, self.width = l, w


def _tip_node(W, x, kind="pcmk", tw=240):
    """pcTip med falske DOM-objekter: grafboks [0, W], markør på x (12 px treffområde), tips med naturlig bredde tw."""
    js = PC.TIP_JS + f"""
const P={{getBoundingClientRect:()=>({{left:0,width:{W}}})}};
const t={{style:{{}},getBoundingClientRect:()=>({{width:Math.min({tw},parseFloat(t.style.maxWidth)||{tw})}})}};
const ew={12 if kind == "pcmk" else 80};
const el={{querySelector:()=>t,closest:()=>P,classList:{{contains:k=>k==="{kind}"}},getBoundingClientRect:()=>({{left:{x}-(ew===12?6:0),width:ew}})}};
pcTip({{currentTarget:el}});const L=({x}-(ew===12?6:0))+parseFloat(t.style.left),w=Math.min({tw},parseFloat(t.style.maxWidth));
process.stdout.write(JSON.stringify({{L:L,R:L+w,mw:t.style.maxWidth}}))"""
    return json.loads(subprocess.check_output([NODE, "-e", js], text=True))


@pytest.mark.skipif(not NODE, reason="node mangler")
@pytest.mark.parametrize("W", [370, 1216])
@pytest.mark.parametrize("frac", [0.0, 0.3, 0.85, 0.99, 1.0])
@pytest.mark.parametrize("kind", ["pcmk", "pcbd"])
def test_tooltip_never_outside_chart_box(W, frac, kind):
    """UxBot 11.11: tips maks 240 px; forbi høyrekanten -> til venstre for markøren; aldri utenfor grafboksen (ingen h-rulling)."""
    r = _tip_node(W, W * frac, kind)
    assert r["mw"] == f"{min(240, W)}px"
    assert 0 <= r["L"] and r["R"] <= W + 1e-6
    if kind == "pcmk" and W * frac + 240 > W and W * frac - 240 >= 0:
        assert abs(r["R"] - W * frac) < 1e-6     # lagt til venstre for markøren (høyre kant ved streken)


def test_tooltip_css_and_hit_area(tmp_path):
    css = PC.CSS
    assert "max-width:240px;white-space:pre-line;overflow-wrap:anywhere" in css           # maks 240 px, brytes
    assert ".pcmk{position:absolute;top:-16px;bottom:0;z-index:4;width:12px;margin-left:-6px;" in css   # 12 px usynlig treffområde rundt 1 px-streken
    assert "left:6px;top:16px;bottom:0;border-left:1px solid #8b949e;pointer-events:none" in css
    assert "z-index:1" in css.split(".pcbd{")[1].split("}")[0]                             # båndet under markøren (z 1 < 4)
    h, _ = _nv_html(tmp_path)
    assert 'addEventListener("pointerenter",pcTip)' in h and 'addEventListener("focus",pcTip)' in h
    assert ".pcp{position:relative;padding-top:16px;overflow-x:clip}" in css             # sikring: aldri horisontal rulling
