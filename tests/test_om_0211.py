"""«Om siden» (UxBot/AnalBot 02.11): fire kort, roadmap fra site_config/roadmap.yaml, tellere fra loggene, ingen påstand om avkastning."""
import csv, re
from datetime import date
from signaltool import om_page as O
from signaltool import tabbar as TB


def _gs(p, n):
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, ["date", "gs_index", "benchmark", "n_members", "n_no_price", "n_invalid", "flag", "gs_with_tech"]); w.writeheader()
        for i in range(n):
            w.writerow({"date": f"2026-10-{i + 1:02d}", "gs_index": 100, "benchmark": 100, "gs_with_tech": 123.4})


def _rm(p, upd="2026-11-02"):
    p.write_text(f"""oppdatert: {upd}
jobbes_med:
  - {{tekst: GS-indeksen vises når den har 60 handelsdager, type: teller, kilde: gs_index}}
  - {{tekst: Testporteføljene får resultat ved 30 lukkede handler per bok, type: teller, kilde: papirboker}}
  - {{tekst: Sjekk av røde flagg, type: dato, dato: 2027-01-22}}
  - {{tekst: Sektortesten, type: dato, dato: 2027-01-25}}
paa_vei: [Kursgrafer med valg av tidsrom, Nøkkeltall på Sektorer, Privat side, "Brent 20d, når den har bestått testen"]
""")


def test_cards_counts_dates(tmp_path):
    _gs(tmp_path / "gs_index.csv", 26); _rm(tmp_path / "r.yaml")
    h = O.html({"generated": "2026-11-02 16:00"}, logs=tmp_path, roadmap=tmp_path / "r.yaml")
    t = re.sub("<[^>]+>", " ", h)
    for cid in ("om-hva", "om-slik", "om-jobbes", "om-vei"):
        assert f'id="{cid}"' in h
    assert h.index("om-hva") < h.index("om-slik") < h.index("om-jobbes") < h.index("om-vei")
    assert "Ikke finansiell rådgivning" in t and "Sist oppdatert 02.11" in t and "Metode →" in t
    assert "26 av 60" in t and "0 · 0 · 0 av 30" in t and "22.01" in t and "25.01" in t
    assert h.count('om-chip on">Pågår') == 4 and h.count('om-chip pl">Planlagt') == 4
    assert "Listen er ikke oppdatert" not in t
    assert "123" not in t                                                        # gs_with_tech aldri
    for bad in ("FLAG", "robust", "forutsier avkastning.", "treffrate", "slår markedet"):
        assert bad not in t or bad == "forutsier avkastning." and "ingenting her forutsier avkastning" in t
    assert "Bare risikonivået er testet, og bare for kurssvingninger." in t and t.count("Ikke testet.") == 2


def test_stale_roadmap_warning(tmp_path):
    _gs(tmp_path / "gs_index.csv", 1); _rm(tmp_path / "r.yaml", "2026-10-01")
    t = re.sub("<[^>]+>", " ", O.html({"generated": "2026-11-02 16:00"}, logs=tmp_path, roadmap=tmp_path / "r.yaml"))
    assert "Listen er ikke oppdatert siden 01.10" in t


def test_real_roadmap_only_agreed_items():
    rm = O.load_roadmap()
    assert len(rm["jobbes_med"]) <= 5 and len(rm["paa_vei"]) <= 5
    assert all("dato" not in str(x) for x in rm["paa_vei"])


def test_more_sheet_first_and_overview_link():
    assert TB.MORE[0] == ("om.html", "Om siden")
    src = open(__import__("signaltool.site", fromlist=["x"]).__file__).read()
    assert 'href="om.html"' in src and "Hva er dette? →" in src
