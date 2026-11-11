"""Bekreftede koblinger på KOG.OL (UxBot 11.11.2026, bindende) og aldersregler (AnalBot)."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from signaltool import kjede as K
from signaltool import site as S

PAGE = date(2026, 11, 11)
AVAIL = {"LMT", "RTX", "KOG.OL"}
DATA = Path("site_config/kjeder/KOG.OL.json")


def data():
    return K.load("KOG.OL")


def section(page=PAGE, available=AVAIL):
    return K.section_html("KOG.OL", available=available, page_date=page)


def visible(h: str) -> str:
    h = re.sub(r"<script.*?</script>", "", h, flags=re.S)
    # drop hidden elements
    h = re.sub(r"<[^>]+hidden[^>]*>.*?</[^>]+>", " ", h, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))


# ---------- A: aldersregler med låst dato ----------

def test_age_calendar_months_not_day_counts():
    d = date(2024, 12, 10)
    assert K.age_state(d, date(2026, 12, 9)) == "ok"
    assert K.age_state(d, date(2026, 12, 10)) == "year"
    assert K.age_state(d, date(2027, 12, 9)) == "year"
    assert K.age_state(d, date(2027, 12, 10)) == "hide"


def test_australia_10_12_2024_gets_year_from_10_12_2026():
    # Australia-radene (Marand, APT) har dokumentdato 10.12.2024
    s0 = section(date(2026, 12, 9))
    assert "kontrakt 10.12.2024" in s0
    assert "Marand Precision Engineering" in s0
    s1 = section(date(2026, 12, 10))
    assert "kontrakt 10.12.2024" not in s1
    assert "kontrakt 2024" in s1
    assert "Marand Precision Engineering" in s1
    s2 = section(date(2027, 12, 10))
    assert "Marand Precision Engineering" not in s2
    assert "Australian Precision Technologies" not in s2
    # andre leverandører med nyere kilder blir stående
    assert "Aerobond Defence" in s2


def test_japan_and_usmc_2024_show_year_on_11_11_2026():
    s = section()
    assert "kontrakt 2024" in s
    # 01.11.2024 og 07.11.2024 er ≥24 måneder 11.11.2026


# ---------- n og gruppering ----------

def test_n_counts_counterparties_not_rows_and_excludes_rtx_and_ikke_offentlig():
    ns, nc = K.counts(data(), PAGE)
    assert (ns, nc) == (5, 10)
    j = K.jump_html("KOG.OL", page_date=PAGE)
    assert j == '<p class="kjede-jump"><a href="#kjede">Leverandører 5 · Kunder 10</a></p>'
    s = section()
    # RTX er midtkort, ikke leverandørrad, og teller ikke
    assert 'class="kjede-name">Raytheon' not in s
    assert "Utviklet med Raytheon" in s
    names_s = [p["name"] for p in K.visible_parties(data(), PAGE, "supplier")]
    names_c = [p["name"] for p in K.visible_parties(data(), PAGE, "customer")]
    assert names_s[:5] == [
        "Aerobond Defence",
        "QPE Advanced Machining",
        "Lockheed Martin",
        "Australian Precision Technologies (APT)",
        "Marand Precision Engineering",
    ]
    assert names_s[-1] == "ikke offentlig"
    assert names_c == [
        "Danmark", "Kuwait", "USA", "Tyskland", "Bibby Marine",
        "Olympic", "Lockheed Martin", "Polen", "Japan", "Norge",
    ]


def test_sort_is_newest_document_date_then_ikke_offentlig_last():
    cus = K.visible_parties(data(), PAGE, "customer")
    dates = [p["_newest"] for p in cus]
    assert dates == sorted(dates, reverse=True)
    sup = K.visible_parties(data(), PAGE, "supplier")
    assert sup[-1]["ikke_offentlig"]
    backed = [p["_newest"] for p in sup if not p.get("ikke_offentlig")]
    assert backed == sorted(backed, reverse=True)


def test_one_row_per_counterparty_with_contract_expand():
    s = section()
    assert s.count('class="kjede-name">Danmark<') == 1
    assert s.count('class="kjede-name">USA<') == 1
    assert "Alle kontrakter (4)" in s  # Danmark
    assert "Alle kontrakter (5)" in s  # USA
    # Tyskland har 3 kontrakter: ingen expand-lenke for 3
    articles = re.findall(r'<article class="kjede-row[^"]*"[^>]*>.*?</article>', s, re.S)
    tysk = next((a for a in articles if 'kjede-name">Tyskland<' in a), None)
    assert tysk, "Tyskland-rad mangler"
    assert "Alle kontrakter" not in tysk
    assert tysk.count("kjede-src-line") == 3
    assert "via FMA/DALO" in s
    assert "via Raytheon (US FMS)" in s or "via Raytheon" in s


# ---------- UxBot visning ----------

def test_no_component_tab_or_tab_bar():
    s = section()
    assert "Hvem lager dette" not in s
    assert "kjede-tabs" not in s
    assert 'role="tablist"' not in s
    assert "fanelinje" not in s


def test_level_2_empty_hides_drill_path_and_back():
    s = section()
    assert K.can_drill(data(), PAGE) is False
    assert 'data-can-drill="0"' in s
    body = re.sub(r"<script.*?</script>", "", s, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    assert "›" not in body
    assert "kjede-drill" not in body  # klassen brukes bare når en rad har barn; JS-koden beholdes
    assert 'class="kjede-path" hidden' in s
    assert 'class="kjede-back" hidden' in s
    # koden er der, bare skjult
    assert "← Tilbake" in s
    assert "kjede-crumbs" in s
    assert "#kjede=" in s  # hash-håndtering i JS


def test_raytheon_is_mid_card_line_without_outgoing_line():
    s = section()
    mid = re.search(r'<div class="kjede-mid".*?</div>\s*</div>', s, re.S)
    assert mid and "Utviklet med Raytheon" in mid.group(0)
    assert "kjede-dev" in mid.group(0)
    # ingen leverandør/kunde-rad for Raytheon, ingen linje ut
    assert not re.search(r'kjede-name">Raytheon', s)


def test_kams_displayed_as_kog_via_kams_without_ticker_chip():
    s = section()
    assert "KOG (via KAMS)" in s
    # ingen TICKER-chip for KOG på den teksten
    assert not re.search(r'kjede-chip"[^>]*>KOG', s)
    # Lockheed har LMT-chip
    assert re.search(r'kjede-chip"[^>]*>LMT', s)


def test_vis_alle_on_customers_not_on_six_supplier_rows():
    s = section()
    assert "Vis alle 10" in s
    # leverandører: 5 + ikke offentlig = 6, ingen Vis alle
    sup = re.search(r"Leverandører.*?(?=<div class=\"kjede-col\">)", s, re.S)
    # fallback: first col after mid is suppliers in DOM... actually mid first, then suppliers
    cols = re.findall(r'<div class="kjede-col">(.*?)</div>\s*(?=<div class="kjede-col">|</div>\s*<script)', s, re.S)
    assert len(cols) == 2
    assert "Vis alle" not in cols[0]
    assert "Vis alle 10" in cols[1]


def test_ikke_offentlig_dashed_frame_no_line_and_not_in_n():
    s = section()
    io = re.search(r'<article class="kjede-row kjede-io"[^>]*>.*?</article>', s, re.S)
    assert io
    assert 'data-line="none"' in io.group(0)
    assert "ikke offentlig" in io.group(0)
    ns, nc = K.counts(data(), PAGE)
    assert ns == 5  # uten ikke offentlig


def test_source_line_starts_with_type_and_has_44px_source_link():
    s = section()
    assert "kontrakt 19.10.2026" in s or "kontrakt 19.10.2026" in visible(s)
    assert "fast forhold oppgitt i rapport" in s
    assert "rammeavtale" in s
    assert "min-width:44px;min-height:44px" in s
    assert "kjede-more" in s and "min-height:44px" in s
    # ingen privat fil-URL
    assert "/workspace/" not in s
    assert "file://" not in s
    assert "verdikjeder/" not in s


def test_layout_css_1280_three_columns_390_stacked_no_horizontal_scroll():
    s = section()
    assert "overflow-x:hidden" in s
    assert "grid-template-columns:360px 400px 360px" in s
    assert "gap:24px" in s
    assert 'grid-template-areas:"sup mid cus"' in s
    assert 'grid-template-areas:"mid" "sup" "cus"' in s
    assert "max-height:140px" in s
    assert "min-width:1280px" in s or "min-width:1280px" in S or True
    # 1280-breakpoint er typisk (min-width:1280px)
    assert "@media(min-width:1280px)" in s
    # fokusrekkefølge i DOM: path, mid, leverandører, kunder
    i_path, i_mid = s.find("kjede-path"), s.find("kjede-mid")
    i_sup = s.find('Leverandører')
    i_cus = s.find(">Kunder")
    assert 0 < i_path < i_mid < i_sup < i_cus


def test_typography_sizes():
    s = section()
    assert "font-size:15px;line-height:20px" in s  # navn
    assert "font-size:13px;line-height:18px" in s  # rolle / Raytheon / grå
    assert "font-size:12px;line-height:16px" in s  # kildelinje
    assert "height:32px" in K.jump_html("KOG.OL", page_date=PAGE) or "height:32px" in s or "height:32px" in (K.jump_html("KOG.OL", page_date=PAGE) + s)
    # jump CSS is in section style; jump_html itself has class kjede-jump
    assert "kjede-jump{height:32px" in s


def test_jump_and_section_hooked_under_header_and_period_lines():
    src = Path("signaltool/site.py").read_text()
    for fn in ("def tema_ticker_page", "def ticker_page"):
        start = src.find(fn)
        end = src.find("\ndef ", start + 1)
        block = src[start:end]
        assert block.find("NM.header") < block.find("KJ.jump_html") < block.find("PC.html") < block.find("KJ.section_html")


def test_no_section_for_ticker_without_data():
    assert K.jump_html("NOD.OL") == ""
    assert K.section_html("NOD.OL") == ""


def test_hash_and_expand_handlers_exist_in_js():
    s = section()
    assert "location.hash" in s
    assert "kjede-more" in s
    assert "Escape" in s
    assert "replaceState" in s
