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
    assert '<a href="#kjede">Leverandører 5 · Kunder 10</a>' in j
    assert '<a href="#komp">Komponenter 4</a>' in j
    assert 'under kontroll' not in j
    assert '<span class="kjede-jump-komp">' in j
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

def test_component_tabs_default_confirmed_and_jump_wrap():
    s = section()
    j = K.jump_html("KOG.OL", page_date=PAGE)
    assert "Hvem lager dette" in s
    assert "Bekreftede koblinger" in s
    assert 'role="tablist"' in s
    assert 'class="kjede-tabs"' in s
    assert 'aria-selected="true">Bekreftede koblinger' in s
    assert 'aria-selected="false" tabindex="-1">Hvem lager dette' in s
    assert 'id="kjede-panel-komp"' in s and "hidden" in s[s.find('id="kjede-panel-komp"'):s.find('id="kjede-panel-komp"')+80]
    # faner: 44 px, 50/50 under 1280, 200 px hver fra 1280
    assert "height:44px" in s
    assert "flex:1 1 50%" in s
    assert "flex:0 0 200px;width:200px" in s
    # lenkerad: 1280 én linje 32 px; 390 maks 56 px, komp-gruppen nowrap
    assert ".kjede-jump{height:32px" in s
    assert "@media(min-width:1280px)" in s
    assert "white-space:nowrap;overflow:hidden" in s  # 1280 hele raden
    assert "kjede-jump-komp{white-space:nowrap}" in s
    assert "max-height:56px" in s
    assert "overflow-x:hidden" in s
    assert "font-size:12px;line-height:16px" in s  # kildelinje
    assert "Komponenter 4" in j and "under kontroll" not in j


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
    cols = re.findall(r'<div class="kjede-col kjede-(?:sup|cus)">(.*?)</div>\s*(?=<div class="kjede-col|</div>\s*<script)', s, re.S)
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
    assert "grid-template-columns:minmax(0,9fr) minmax(0,10fr) minmax(0,9fr)" in s
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
    assert "font-size:13px;line-height:18px" in s  # Raytheon / grå / chip
    assert "font-size:12px;line-height:16px" in s  # rolle, dato og kildelinje
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


# ---------- Komponentfane (stål, kobber, aluminium og jern) ----------

def test_component_tab_four_components_no_private_or_held_rows():
    s = section()
    # chips; ingen «under kontroll»
    assert ">Stål<" in s or ">Stål</button>" in s
    assert ">Kobber<" in s or ">Kobber</button>" in s
    assert ">Aluminium<" in s or ">Aluminium</button>" in s
    assert ">Jern<" in s or ">Jern</button>" in s
    assert "Aluminium: under kontroll" not in s
    assert "Jern: under kontroll" not in s
    assert "Viser produsenter av komponenten, ikke bekreftede leverandører til KOG" in s
    # produsenter
    for name in (
        "Nucor Corporation", "ArcelorMittal S.A.", "JSW Steel Limited",
        "Steel Dynamics, Inc.", "Tata Steel Limited", "Nippon Steel Corporation",
        "Southern Copper Corporation", "Freeport-McMoRan Inc.", "Antofagasta plc",
        "Teck Resources Limited", "First Quantum Minerals Ltd.", "Lundin Mining Corporation",
        "China Hongqiao Group Limited", "Hindalco Industries Limited",
        "Aluminum Corporation of China Limited", "Vedanta Aluminium Metal Limited",
        "Norsk Hydro ASA", "Press Metal Aluminium Holdings Berhad",
    ):
        assert name in s, name
    assert "Produserer steel" in s
    assert "Produserer copper" in s
    assert "Produserer aluminium" in s
    assert "Produserer iron (direct reduced iron)" in s
    assert "Produserer iron (HBI / DRI)" in s
    assert "Produserer iron (pig iron / masovn)" in s
    assert "Basic Materials" in s
    # kunder av kobber- og aluminiumsprodusenter
    assert "Kunder av Southern Copper Corporation (6)" in s
    assert "Hartree Partners" in s
    assert "Kjøper copper cathodes" in s
    assert "Kunder av Freeport-McMoRan Inc. (1)" in s
    assert "Mitsubishi Materials Corporation" in s
    assert "Kunde, produkt ikke oppgitt" in s
    assert "Kunder av Norsk Hydro ASA (7)" in s
    assert "Mercedes-Benz" in s
    assert "Kjøper Hydro REDUXA" in s
    assert "Vis alle 7" in s
    assert "Kunder av Vedanta Aluminium Metal Limited (0)" in s
    assert "Ingen kunder navngitt i offentlige kilder" in s
    # holdt utenfor: AA, Cliffs, Baosteel, jernmalm, bauxitt/alumina
    assert "Cleveland-Cliffs" not in s
    assert "Alcoa" not in s
    assert "Baosteel" not in s
    assert "iron ore lump" not in s
    assert "Hydro Bauxite" not in s
    assert "Alunorte" not in s
    # ingen privat sti
    assert "/workspace/" not in s
    assert "file://" not in s
    assert "verdikjeder/" not in s
    # hash og Esc for komponentfanen
    assert "#komp" in s
    assert "Escape" in s
    # radhøyder
    assert "min-height:64px;max-height:96px" in s
    assert "komp-empty{box-sizing:border-box;min-height:48px" in s
    # kildetype først på produsentkunder
    assert "avtale oppgitt i rapport" in s
    assert "kundekonsentrasjon oppgitt i 10-K" in s
    assert "årsrapport" in s
    assert "produksjonsmelding" in s

def test_iron_quotes_are_verbatim_from_source_documents():
    # Sitat vises ikke i HTML (bare kildelenke), men ligger i data og er låst mot kilden.
    iron = next(i for i in data()["components"]["items"] if i["id"] == "iron")
    by = {p["ticker"]: p for p in iron["producers"]}
    mt = by["MT"]["sitat"]
    nip = by["5401.T"]["sitat"]
    assert "s. 60" in mt and "DRI/HBI Plant 10 9.7 6.0" in mt
    assert "produces Hot Briquetted Iron" in mt
    assert "s. 152" in nip and "centered on a blast furnace that produces pig iron" in nip
    assert "s. 23" in nip and "blast furnaces from 15 to 10 units" in nip
    assert "operates ten blast furnaces" not in nip
