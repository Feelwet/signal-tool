"""Temaer-trend 16.11 (AnalBot/UxBot): andel, 7d mot 21d, flagg, layout 390/1280."""
from __future__ import annotations

import csv
import math
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

from signaltool import tema_trend as TT
from signaltool import site as S


def _rows(days: dict[date, dict[str, int]], extra_other: int = 0):
    """days[date][theme] = antall treff. extra_other: ekstra unike overskrifter uten tema-treff (egne url-er, tema='')."""
    out = []
    for d, hits in days.items():
        i = 0
        for theme, n in hits.items():
            for _ in range(n):
                i += 1
                out.append({"dato": d.isoformat(), "url": f"https://ex/{d}/{theme}/{i}",
                            "tittel": f"{theme} {i}", "kilde": "ex", "tema": theme})
        for j in range(extra_other):
            i += 1
            out.append({"dato": d.isoformat(), "url": f"https://ex/{d}/other/{i}",
                        "tittel": f"other {i}", "kilde": "ex", "tema": "other"})
    return out


def _write(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["dato", "url", "tittel", "kilde", "tema", "matchede_ord"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "matchede_ord": r.get("matchede_ord", "x")})
    return path


def _const(start: date, n: int, theme: str, hits: int, total: int):
    days = {}
    for i in range(n):
        d = start + timedelta(days=i)
        days[d] = {theme: hits}
        # pad with filler so unique headlines = total
        if total > hits:
            days[d]["pad"] = total - hits
    return days


def test_share_uses_unique_headlines_not_raw_and_not_theme_score():
    src = Path(TT.__file__).read_text()
    assert TT.LOG.name == "tema_match_sjekk.csv"
    assert "logs/theme_score.csv" not in src.replace("ikke logs/theme_score.csv", "")
    d = date(2026, 11, 10)
    rows = _rows({d: {"a": 2, "b": 1}})  # 3 unique urls
    # same url twice with two themes still one headline in denominator
    rows.append({"dato": d.isoformat(), "url": "https://ex/2026-11-10/a/1", "tittel": "a 1",
                 "kilde": "ex", "tema": "b"})
    sh = TT.daily_shares(rows)
    assert sh[d]["n"] == 3
    assert sh[d]["share"]["a"] == pytest.approx(2 / 3)
    assert sh[d]["hits"]["b"] == 2
    assert sh[d]["share"]["b"] == pytest.approx(2 / 3)


def test_inactive_before_dec2_or_without_flag_is_only_grey_text(tmp_path):
    log = _write(tmp_path / "m.csv", _rows(_const(date(2026, 11, 4), 13, "a", 10, 100)))
    shares = TT.daily_shares(TT.load_rows(log))
    as_of = date(2026, 11, 16)
    today = date(2026, 11, 16)
    tr = TT.compute("a", shares, as_of, ok=False, today=today)
    assert tr["active"] is False and tr["thin"] is True and tr["label"] is None
    assert tr["text"] == "For lite data (12/28 dager)"
    # flag on, but før 02.12
    tr2 = TT.compute("a", shares, as_of, ok=True, today=today)
    assert tr2["active"] is False and tr2["text"] == "For lite data (12/28 dager)"
    # etter 02.12, flagg av
    days = _const(date(2026, 11, 5), 28, "a", 10, 100)
    log2 = _write(tmp_path / "m2.csv", _rows(days))
    shares2 = TT.daily_shares(TT.load_rows(log2))
    tr3 = TT.compute("a", shares2, date(2026, 12, 2), ok=False, today=date(2026, 12, 2))
    assert tr3["active"] is False and tr3["text"].startswith("For lite data")
    assert TT.temamatch_ok() is False


def test_labels_threshold_and_uendret(tmp_path):
    # 21 dager andel 0,10 (std 0), 7 dager 0,20 -> rel +100 %, |z| = inf
    start = date(2026, 11, 5)
    days = {}
    for i in range(21):
        days[start + timedelta(days=i)] = {"hot": 10, "pad": 90}
    for i in range(21, 28):
        days[start + timedelta(days=i)] = {"hot": 20, "pad": 80}
    shares = TT.daily_shares(_rows(days))
    as_of = date(2026, 12, 2)
    tr = TT.compute("hot", shares, as_of, ok=True)
    assert tr["active"] and not tr["thin"]
    assert tr["label"] == "Mer omtale"
    assert tr["rel"] == pytest.approx(1.0)
    assert math.isinf(tr["z"])

    # støyende 21d, samme +50 % relativt men |z| < 2 -> Uendret
    days2 = {}
    for i, s in enumerate([0.05, 0.20, 0.08, 0.18, 0.06, 0.19, 0.07, 0.21, 0.09, 0.17,
                           0.04, 0.22, 0.10, 0.16, 0.05, 0.23, 0.08, 0.18, 0.06, 0.20, 0.10]):
        hits = int(round(s * 100))
        days2[start + timedelta(days=i)] = {"x": hits, "pad": 100 - hits}
    for i in range(21, 28):
        days2[start + timedelta(days=i)] = {"x": 15, "pad": 85}  # 0.15 vs mean ~0.12
    shares2 = TT.daily_shares(_rows(days2))
    tr2 = TT.compute("x", shares2, as_of, ok=True)
    assert abs(tr2["rel"]) < 0.50 or abs(tr2["z"]) < 2
    assert tr2["label"] == "Uendret"
    assert tr2["thin"] is False

    # rel ≥50 % og |z|≥2 ned
    days3 = {}
    for i in range(21):
        days3[start + timedelta(days=i)] = {"c": 40, "pad": 60}
    for i in range(21, 28):
        days3[start + timedelta(days=i)] = {"c": 16, "pad": 84}
    tr3 = TT.compute("c", TT.daily_shares(_rows(days3)), as_of, ok=True)
    assert tr3["label"] == "Mindre omtale" and tr3["rel"] == pytest.approx(-0.6)


def test_few_hits_after_active_date(tmp_path):
    start = date(2026, 11, 5)
    days = _const(start, 28, "rare", 2, 100)  # 7*2 = 14 < 30
    tr = TT.compute("rare", TT.daily_shares(_rows(days)), date(2026, 12, 2), ok=True)
    assert tr["active"] and tr["thin"] and tr["label"] is None
    assert tr["text"] == "For få treff (n<30)"
    assert tr["sort"] is None


def test_missing_days_break_sparkline_not_filled():
    vals = [0.1, 0.1, None, None, 0.2, 0.2]
    svg = TT.spark_svg(vals, 120, 32, dashed=False)
    assert svg.count("<polyline") == 2
    assert "stroke-dasharray=\"4 4\"" not in svg  # linjen selv er hel; grunnlinjen er 2 2
    assert 'stroke-dasharray="2 2"' in svg
    assert 'r="2"' in svg  # 4 px prikk
    assert TT.NEUTRAL in svg and "#4ac26b" not in svg and "--up" not in svg
    thin = TT.spark_svg(vals, 96, 24, dashed=True, dot=False)
    assert 'stroke-dasharray="4 4"' in thin and 'class="tt-dot"' not in thin


def test_default_flag_off_and_config_exists():
    assert TT.CONFIG.exists()
    assert TT.temamatch_ok() is False
    assert "temamatch_ok: false" in TT.CONFIG.read_text()


def _themes():
    return [
        {"key": "hot", "name": "Et svært langt temanavn som skal kuttes med ellipsis i mobilraden",
         "score": 2.1, "headline_count_3d": 12, "tickers": [{"ticker": "A"}, {"ticker": "B"}]},
        {"key": "cold", "name": "Kort", "score": 0.4, "headline_count_3d": 3, "tickers": [{"ticker": "C"}]},
        {"key": "flat", "name": "Flatt tema", "score": 1.0, "headline_count_3d": 5, "tickers": [1, 2, 3, 4]},
    ]


def _full_log(tmp_path, mer="hot", minder="cold"):
    start = date(2026, 11, 5)
    days = {}
    for i in range(21):
        days[start + timedelta(days=i)] = {mer: 10, minder: 40, "flat": 10, "pad": 40}
    for i in range(21, 28):
        days[start + timedelta(days=i)] = {mer: 20, minder: 16, "flat": 11, "pad": 53}
    return _write(tmp_path / "log.csv", _rows(days))


def test_block_inactive_layout_contract(tmp_path):
    log = _write(tmp_path / "m.csv", _rows(_const(date(2026, 11, 4), 13, "hot", 10, 100)))
    html = TT.block(_themes(), {"date": "2026-11-16"}, score_badge=lambda *a, **k: "S",
                    log_path=log, ok=False, today=date(2026, 11, 16))
    assert "For lite data (12/28 dager)" in html
    assert "Mer omtale" not in html and "Mindre omtale" not in html and "Uendret" not in html
    assert "tt-spark" not in html and "stroke-dasharray" not in html
    assert 'class="tt-stripe"' not in html
    assert "sortable" not in html
    assert TT.NOTE in html and 'class="tt-note"' in html
    assert "Trend 7d mot 21d før" in html
    assert "2 tickere" in html and "1 ticker" in html
    assert 'href="tema/hot.html"' in html
    assert "theme_score" not in html
    # ingen grønn/rød
    assert "class=\"up\"" not in html and "class=\"down\"" not in html
    assert "#4ac26b" not in html and "#ff8078" not in TT.CSS and "--up" not in TT.CSS and "--down" not in TT.CSS
    assert "width:200px" in TT.CSS and "font-size:13px" in TT.CSS and "line-height:18px" in TT.CSS
    assert "margin:8px 0 0" in TT.CSS and "font-size:12px;line-height:16px;color:#94a3b8" in TT.CSS
    assert "min-height:44px" in TT.CSS and "outline:2px solid" in TT.CSS
    assert "@media(max-width:599px)" in TT.CSS
    assert ".tt-stripe{display:none!important}" in TT.CSS


def test_block_active_sort_stripe_and_labels(tmp_path):
    log = _full_log(tmp_path)
    html = TT.block(_themes(), {"date": "2026-12-02"}, score_badge=lambda *a, **k: "S",
                    log_path=log, ok=True)
    assert "Mer omtale" in html and "Mindre omtale" in html and "Uendret" in html
    assert "class=\"tt-stripe\"" in html
    assert "sortable" in html
    assert "tt-spark" in html
    assert ", 7d" in html and "% omtale" in html
    assert "▲" in html and "▼" in html
    # standard rekkefølge: størst andelsendring først, tynne sist (ingen tynne her)
    keys = [k.split('tema/', 1)[1].split('.html', 1)[0] for k in html.split('data-href="')[1:]]
    # first data-href is in rows; mer (hot) should be first
    assert keys[0] == "hot"
    assert "For få treff" not in html
    # Uendret har ikke pil foran etiketten
    u = html.split("Uendret", 1)[0][-80:]
    assert "▲" not in u and "▼" not in u
    # stripe-grupper
    assert html.index("Mer omtale") < html.index("tt-card")
    assert "theme_score" not in html
    # temaside-graf
    ch = TT.theme_chart({"key": "hot", "name": "Hot"}, {"date": "2026-12-02"}, log_path=log, ok=True)
    assert "tt-ch-card" in ch and "tt-ch-lab" in ch and "tt-hitbox" in ch
    assert "height:240px" in TT.CSS and "height:180px" in TT.CSS and "height:16px" in TT.CSS
    assert "width:12px" in TT.CSS and "max-width:240px" in TT.CSS
    assert TT.theme_chart({"key": "hot"}, {"date": "2026-11-16"}, log_path=log, ok=True) == ""


def test_stripe_hides_empty_group_and_caps_at_three(tmp_path):
    start = date(2026, 11, 5)
    themes = [{"key": f"t{i}", "name": f"T{i}", "score": 1, "headline_count_3d": 1, "tickers": []}
              for i in range(5)]
    days = {}
    for d_i in range(21):
        days[start + timedelta(days=d_i)] = {f"t{i}": 10 for i in range(5)}
        days[start + timedelta(days=d_i)]["pad"] = 50
    for d_i in range(21, 28):
        # alle fem mer omtale (20 mot 10)
        days[start + timedelta(days=d_i)] = {f"t{i}": 20 for i in range(5)}
    log = _write(tmp_path / "m.csv", _rows(days))
    html = TT.block(themes, {"date": "2026-12-02"}, score_badge=lambda *a, **k: "S",
                    log_path=log, ok=True)
    stripe = html.split('class="tt-stripe">', 1)[1].split("</div><div class=\"card", 1)[0]
    assert "Mindre omtale" not in stripe
    assert stripe.count('class="tt-si"') == 3
    assert "Mer omtale" in stripe


def test_site_build_includes_trend_css_and_footnote(tmp_path, monkeypatch):
    # lett sjekk av at site.py kobler inn CSS og block uten å kjøre hele build
    src = Path(S.__file__).read_text()
    assert "from . import tema_trend as TT" in src
    assert "+ U390.CSS + TT.CSS" in src
    assert "TT.block(" in src and "TT.theme_chart(" in src
    assert "+ CHG.CSS + U390.CSS" in src


@pytest.mark.skipif(not (shutil.which("google-chrome") or shutil.which("chromium")), reason="ingen headless Chrome")
def test_headless_390_rows_le_96_no_hscroll_focus_link(tmp_path):
    pw = pytest.importorskip("playwright.sync_api")
    log = _write(tmp_path / "m.csv", _rows(_const(date(2026, 11, 4), 13, "hot", 10, 100)))
    body = TT.block(_themes(), {"date": "2026-11-16"}, score_badge=lambda *a, **k: "S",
                    log_path=log, ok=False, today=date(2026, 11, 16))
    html = (f'<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<style>body{{margin:0;background:#0d1117;color:#e6edf3}}main{{padding:10px;max-width:1100px}}'
            f'.card{{padding:14px 16px;border:1px solid #2d333b}}{TT.CSS}</style></head>'
            f'<body><main>{body}</main></body></html>')
    f = tmp_path / "t.html"
    f.write_text(html)
    with pw.sync_playwright() as p:
        b = p.chromium.launch(channel="chrome" if shutil.which("google-chrome") else None)
        pg = b.new_page(viewport={"width": 390, "height": 900})
        pg.goto(f.as_uri())
        m = pg.evaluate("""()=>{
          const rows=[...document.querySelectorAll('tr.tt-row')];
          const links=[...document.querySelectorAll('a.tt-hit')];
          const de=document.documentElement;
          const cs=getComputedStyle(links[0]);
          links[0].focus();
          const ol=getComputedStyle(links[0]).outlineStyle;
          return {h:rows.map(r=>r.getBoundingClientRect().height),
                  sw:de.scrollWidth,cw:de.clientWidth,
                  minH:parseFloat(cs.minHeight),n:links.length,
                  outline:ol,
                  l2:links.map(a=>a.querySelector('.tt-l2')&&a.querySelector('.tt-l2').innerText),
                  spark:[...document.querySelectorAll('.tt-spark')].length};
        }""")
        # 1280: kolonne 200 px, teksten på én linje, ingen stripe
        pg2 = b.new_page(viewport={"width": 1280, "height": 900})
        pg2.goto(f.as_uri())
        d = pg2.evaluate("""()=>{
          const th=document.querySelector('th.tt-tr-h');
          const cell=document.querySelector('td.tt-tr .tt-thin');
          const stripe=document.querySelector('.tt-stripe');
          return {w:th.getBoundingClientRect().width,
                  lines:cell?Math.round(cell.getBoundingClientRect().height):null,
                  sortable:th.classList.contains('sortable'),
                  stripe:!!stripe};
        }""")
        b.close()
    assert m["n"] == 3
    assert max(m["h"]) <= 96, m["h"]
    assert min(m["h"]) >= 44, m["h"]
    assert m["sw"] == m["cw"], m
    assert m["minH"] >= 44
    assert m["spark"] == 0
    assert all("For lite data (12/28 dager)" in t for t in m["l2"])
    assert d["w"] == pytest.approx(200, abs=1)
    assert d["lines"] == 18  # 13/18 én linje
    assert d["sortable"] is False and d["stripe"] is False


def test_complete_days_in_current_log_are_12_on_16_nov():
    """AnalBot 16.11: telleren låses til 12 for dagens logg (04.11–15.11; 16.11 teller ikke)."""
    shares = TT.daily_shares(TT.load_rows())
    today = date(2026, 11, 16)
    days = sorted(d for d in shares if d < today)
    assert days[0] == date(2026, 11, 4) and days[-1] == date(2026, 11, 15)
    assert days == [date(2026, 11, 4) + timedelta(days=i) for i in range(12)]
    assert TT.complete_logged_days(shares, today) == 12
    assert TT.thin_text(shares, today=today) == "For lite data (12/28 dager)"
    assert today in shares  # pågående dag finnes, men teller ikke


def test_counter_ignores_stale_snapshot_date(tmp_path):
    """Feilen 16.11: as_of fra natt-snapshot 11.11 ga 8/28 og utelot 12.–15.11."""
    log = _write(tmp_path / "m.csv", _rows(_const(date(2026, 11, 4), 13, "hot", 10, 100)))
    # snapshot fortsatt 11.11, men loggen har 04.–16.11 og i dag er 16.11
    html = TT.block(_themes(), {"date": "2026-11-11"}, score_badge=lambda *a, **k: "S",
                    log_path=log, ok=False, today=date(2026, 11, 16))
    assert "For lite data (12/28 dager)" in html
    assert "For lite data (8/28 dager)" not in html
    shares = TT.daily_shares(TT.load_rows(log))
    assert TT.complete_logged_days(shares, date(2026, 11, 11)) == 7   # bare før 11.11, brukes ikke
    assert TT.logged_days(shares, date(2026, 11, 11)) == 8            # gammel (feil) telling


def test_counter_uses_oslo_today_in_hourly_site_build(monkeypatch):
    """Timesbygget kaller site.build -> TT.block uten egen dato; telleren skal følge oslo_today, ikke snap['date']."""
    src = Path(S.__file__).read_text()
    assert "TT.block(" in src and "python3 -m signaltool.verden --time" not in src
    from signaltool import verden as VN
    vsrc = Path(VN.__file__).read_text()
    assert "site.build(snap)" in vsrc
    seen = {}
    real = TT.oslo_today
    def fake():
        seen["called"] = True
        return date(2026, 11, 16)
    monkeypatch.setattr(TT, "oslo_today", fake)
    # block uten today= og med gammelt snap-dato
    log_dates = _const(date(2026, 11, 4), 13, "hot", 10, 100)
    import tempfile
    from pathlib import Path as P
    # use a temp file via existing helper would need tmp_path; write in-memory via monkeypatch load
    rows = _rows(log_dates)
    monkeypatch.setattr(TT, "load_rows", lambda path=None: rows)
    html = TT.block(_themes(), {"date": "2026-11-11"}, score_badge=lambda *a, **k: "S", ok=False)
    assert seen.get("called")
    assert "For lite data (12/28 dager)" in html

