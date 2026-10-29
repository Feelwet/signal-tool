"""AnalBot/UxBot 29.10: kurstabellen på tickersiden – kun format endres (norsk komma, ekte minus, «%» per prosentcelle, nowrap), aldri verdi."""
import copy, html, json, re
from pathlib import Path

import pytest

from signaltool import site, nokkeltall as NK

SNAP = Path(__file__).resolve().parents[1] / "data" / "snapshots" / "latest.json"
CELL = re.compile(r'<td data-k="([a-z0-9_]+)" data-d="(\d)"( data-p="1")?>(.*?)</td>', re.S)


def parse_no(txt: str):
    t = html.unescape(re.sub(r"<[^>]+>", "", txt)).replace("\u00a0", " ").strip()
    if t == "–":
        return None, t
    t2 = t.replace("\u2212", "-").replace(",", ".").replace("%", "").replace("x", "").strip()
    return float(t2), t


def check_cells(page_html: str, st: dict) -> int:
    cells = CELL.findall(page_html)
    assert len(cells) == 6, cells
    for k, d, p, raw in cells:
        v = st.get(k)
        got, txt = parse_no(raw)
        if v is None:
            assert got is None, (k, txt)
            continue
        want = v * 100 if p else v
        assert got == float(f"{want:.{d}f}"), (k, v, txt)                 # samme avrunding som før, innen vist presisjon
        assert ("\u2212" in txt) == f"{want:.{d}f}".startswith("-"), (k, v, txt)  # minustegnet forsvinner aldri
        assert "." not in txt and "-" not in txt, txt                      # norsk format
        if p:
            assert txt.endswith("\u00a0%") or txt.endswith(" %"), txt
        assert len(txt.split(",")[-1].rstrip(" %x\u00a0")) == int(d), txt  # ingen desimaler lagt til/fjernet
    return len(cells)


def test_format_helpers_keep_values():
    for x in (0.0112, -0.0198, 0.0, -0.00004, 0.14249, -0.2371, 1.0):
        got, txt = parse_no(site.pct_no(x))
        assert got == float(f"{x*100:+.1f}") and txt.endswith(" %")
        assert ("\u2212" in txt) == f"{x*100:+.1f}".startswith("-")
    for x, d in ((629.75, 2), (-1.25, 1), (3.1, 1), (2.04, 1), (-0.04, 1)):
        assert parse_no(site.num_no(x, d))[0] == float(f"{x:.{d}f}")
    assert site.num_no(None) == "–" and site.pct_no(None) == "–"
    assert site.pct_no(-0.0198) == '<span class="down">\u22122,0\u00a0%</span>'


def test_kt_title_both_cases():
    assert site.kt_title({"vol_ratio_5d": 2.0}) == site.KT_TITLE_VOL == "Kursutvikling og volum"
    assert site.kt_title({"vol_ratio_5d": None}) == site.kt_title({}) == site.KT_TITLE == "Kursutvikling"


APPROVED = {  # AnalBot 29.10, ordrett
    "Børsverdi": "Antall aksjer × siste sluttkurs.",
    "P/E": "Siste sluttkurs delt på resultat per aksje siste 12 mnd (faktisk, ikke estimat). «Negativ» betyr underskudd.",
    "Omsetning": "Salgsinntekter siste 12 mnd, i selskapets regnskapsvaluta.",
    "EBIT": "Driftsresultat, summen av de fire siste kvartalene.",
    "EPS": "Resultat per aksje siste 12 mnd (faktisk).",
    "Utbytte per aksje": "Faktisk utbetalt utbytte siste 12 mnd.",
    "Direkteavkastning": "Utbytte per aksje siste 12 mnd delt på siste sluttkurs. Historisk, ikke en lovnad om neste utbytte.",
    "P/B": "Siste sluttkurs delt på bokført egenkapital per aksje.",
    "P/S": "Børsverdi delt på omsetning siste 12 mnd.",
    "Neste rapport": "Dato for neste kvartalsrapport. «(anslått)» betyr at selskapet ikke har bekreftet datoen.",
}
APPROVED_KT = ["Kursendring siste 1, 5 og 20 handelsdager.",
               "Hvor uvanlig 5-dagersendringen er mot aksjens eget siste år. ±2 eller mer er sjelden.",
               "Snittvolum siste 5 dager delt på normalen (60 handelsdager som slutter for en uke siden). 3,8x betyr nesten fire ganger normalt."]


def test_nokkeltall_defs_verbatim_and_no_ebitda():
    lab = dict(NK.FIELDS)
    assert {lab[k]: v for k, v in NK.DEFS.items()} == APPROVED
    assert list(NK.KT_DEFS.values()) == APPROVED_KT
    fs = [{"key": k, "label": l, "value": "1"} for k, l in NK.FIELDS]
    h = NK.html({"fields": fs, "date": "2026-10-29"})
    for l, t in APPROVED.items():
        assert html.escape(f"{t} Yahoo · 29.10") in h, l
    ebit = re.search(r'<span class="l">EBIT <span class="ri ri-c nkd"[^>]*>ⓘ<span class="tip">(.*?)</span>', h).group(1)
    assert ebit.endswith("Yahoo · 29.10") and "EBITDA" not in ebit and "EBITDA" not in NK.DEFS["ebit"]
    assert NK.MISSING_INFO == "Tallet mangler hos kilden." and "Mangler fra kilden" not in h
    assert NK.html({"fields": [{"key": "pe", "label": "P/E", "value": None}], "date": None}).count("Tallet mangler hos kilden.") >= 1


@pytest.mark.skipif(not SNAP.exists(), reason="no snapshot available")
def test_every_ticker_page_cell_matches_data(tmp_path, monkeypatch):
    snap = json.loads(SNAP.read_text())
    no_vol = next(e for e in snap["tickers"] if e.get("stats"))
    no_vol["stats"] = dict(no_vol["stats"], vol_ratio_5d=None)
    monkeypatch.setattr(site, "SITE", tmp_path / "site")
    site.build(copy.deepcopy(snap))
    n = titles = 0
    for e in snap["tickers"]:
        f = tmp_path / "site" / "ticker" / f"{site.slug(e['ticker'])}.html"
        if not f.exists():
            continue
        h = f.read_text()
        if 'table class="kt"' not in h:
            continue
        st = e.get("stats") or {}
        n += check_cells(h, st)
        want = "Kursutvikling og volum" if st.get("vol_ratio_5d") is not None else "Kursutvikling"
        assert f'<h2 class="kt-h" style="margin-top:0">{want}</h2>' in h, e["ticker"]
        titles += 1
        for t in APPROVED_KT:
            assert html.escape(t) in h, (e["ticker"], t)
        if e is no_vol:
            assert '<h2 class="kt-h" style="margin-top:0">Kursutvikling</h2>' in h and 'data-k="vol_ratio_5d" data-d="1">–</td>' in h
    assert n >= 6 * 10 and titles >= 10
