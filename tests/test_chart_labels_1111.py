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
    assert ".pcp{position:relative;padding-top:16px}.pcl{position:absolute;left:0;right:0;top:16px;bottom:0}" in css   # 16 px-rad over grafen
    assert ".pcl .hi{top:0}" in css                                    # aksetall i grafflaten (y ≥ 16 px i panelet)
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
    ms = [{"x": float(x) * W / 100, "w": len(t) * 6.6} for _, x, t in mk]   # 11 px tekst, ~6,6 px per tegn (overslag, med margin)
    o = _lay(ms, W)
    shown = sorted([(ms[i]["x"], o[i]) for i in range(len(ms)) if o[i]["show"]], key=lambda z: z[0])
    assert shown and o[max(range(len(ms)), key=lambda i: ms[i]["x"])]["show"]          # nyeste vises alltid
    for (xa, a), (xb, b) in zip(shown, shown[1:]):
        assert xb - xa >= 28 and a["r"] + 4 <= b["l"]                                    # ≥ 28 px og ingen overlapp
    assert all(0 <= b["l"] and b["r"] <= W for _, b in shown)                           # innenfor grafen (aldri ut over kanten)
    # markør og bånd vises alltid, uansett etikett
    assert pane.count('class="pcmk') == len(PC.events(_nvda_like()[-dict(PC.PERIODS)[lab]:], ps))


@pytest.mark.skipif(not NODE, reason="node mangler")
def test_collision_rule_newest_first():
    o = _lay([{"x": 100, "w": 40}, {"x": 120, "w": 40}, {"x": 300, "w": 40}, {"x": 320, "w": 40}], 400)
    assert [z["show"] for z in o] == [False, True, False, True]   # 320 vises; 300 (20 px) skjules; 120 vises; 100 (20 px til 120) skjules
    e = _lay([{"x": 390, "w": 40}], 400)[0]
    assert e["show"] and e["rt"] and e["r"] <= 400                   # helt til høyre: etiketten flyttes til venstre for streken
