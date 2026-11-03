"""«Verden nå» (UxBot/AnalBot 03.11): henting, kontroll før publisering og reserve."""
import csv, json, re
from datetime import datetime, timezone
import pandas as pd
from signaltool import verden as V

NOW = datetime(2026, 11, 4, 5, 30, tzinfo=timezone.utc)   # 06:30 Oslo
U1, U2, U3, U4 = (f"https://ex.org/a{i}" for i in range(1, 5))


def _data():
    fetch = {
        "GDELT": lambda: [
            {"tittel": "Russia launches drone attack on Ukraine grid", "url": U1, "kilde": "GDELT", "domene": "ex.org", "publisert": V._parse_ts("20261104T040000Z")},
            {"tittel": "NATO allies discuss Ukraine air defence", "url": U2, "kilde": "GDELT", "domene": "ex.org", "publisert": V._parse_ts("20261103T200000Z")},
            {"tittel": "Houthi attack in the Red Sea", "url": U3, "kilde": "GDELT", "domene": "ex.org", "publisert": V._parse_ts("20261103T180000Z")},
            {"tittel": "Old Ukraine story", "url": "https://ex.org/old", "kilde": "GDELT", "publisert": V._parse_ts("20261101T100000Z")},
            {"tittel": "Celebrity gossip", "url": "https://ex.org/x", "kilde": "GDELT", "publisert": V._parse_ts("20261104T010000Z")}],
        "ECB": lambda: [{"tittel": "ECB publishes account of meeting", "url": U4, "kilde": "ECB", "publisert": V._parse_ts("2026-11-03T15:00:00Z")}],
        "Federal Reserve": lambda: (_ for _ in ()).throw(RuntimeError("timeout")),
    }
    nw = pd.DataFrame([{"title": "Company X: Annual general meeting", "url": "https://newsweb.oslobors.no/message/1", "published": pd.Timestamp("2026-11-04T04:00Z")}])
    return V.collect(nw, [], now=NOW, fetch=fetch)


def test_collect_window_themes_order_no_body():
    d, st = _data()
    urls = [it["url"] for it in d["saker"]]
    assert set(urls) == {U1, U2, U3, U4}                               # >24 t, uten tema og Newsweb-rutinemelding utelatt
    assert d["temaer"][0] == {"tema": "conflict_defense", "antall": 2}  # mest omtalt først
    assert urls[:2] == [U1, U2]
    assert set(d["saker"][0]) <= {"tittel", "url", "kilde", "domene", "publisert", "tema", "temaer"}   # aldri artikkeltekst
    assert "Federal Reserve: FAILED" in st and d["dato"] == "2026-11-04"


def _text(written="2026-11-04T07:05:00+01:00", ingress=None, saker=None):
    return {"written_at": written, "newest_item": "2026-11-04", "kilder": ["GDELT"],
            "ingress": ingress if ingress is not None else [{"tekst": "Angrep på strømnettet i Ukraina preget døgnet.", "lenker": [U1]},
                                                             {"tekst": "Oljeprisen vil stige.", "lenker": [U1]}],
            "saker": saker if saker is not None else [
                {"tittel": "Droneangrep i Ukraina", "tema": "conflict_defense", "kilder": ["GDELT"],
                 "setninger": [{"tekst": "Russland angrep strømnettet.", "lenker": [U1]}, {"tekst": "Uten kilde.", "lenker": []}]},
                {"tittel": "Rødehavet", "tema": "shipping_chokepoints", "kilder": ["GDELT"],
                 "setninger": [{"tekst": "Nytt angrep meldt.", "lenker": ["https://ikke-hentet.org/z"]}]},
                {"tittel": "ECB", "tema": "sentralbanker", "kilder": ["ECB"], "setninger": [{"tekst": "ECB la fram referat.", "lenker": [U4]}]},
                {"tittel": "Kjøp forsvar nå", "tema": "conflict_defense", "setninger": [{"tekst": "NATO møttes.", "lenker": [U2]}]}]}


def test_validate_removes_and_logs_append_only(tmp_path):
    d, _ = _data(); log = tmp_path / "avvik.csv"
    clean, rem = V.validate(_text(), d, "2026-11-04", log)
    assert [s["tekst"] for s in clean["ingress"]] == ["Angrep på strømnettet i Ukraina preget døgnet."]
    assert [k["tittel"] for k in clean["saker"]] == ["Droneangrep i Ukraina", "ECB"]          # tom sak + forbudt tittel droppet
    assert clean["saker"][0]["setninger"] == [{"tekst": "Russland angrep strømnettet.", "lenker": [U1]}]   # ikke skrevet om
    rows = list(csv.DictReader(log.open()))
    assert len(rows) == 4 and {r["dato"] for r in rows} == {"2026-11-04"}
    assert any("vil stige" in r["grunn"] for r in rows) and any("mangler kildelenke" in r["grunn"] for r in rows)
    assert any("ikke-hentet.org" in r["grunn"] for r in rows)
    V.validate(_text(), d, "2026-11-04", log)                                                  # ny bygging samme dag
    assert len(list(csv.DictReader(log.open()))) == 4
    V.validate(_text(), d, "2026-11-05", log)
    assert len(list(csv.DictReader(log.open()))) == 8                                          # bare tillegg


def test_banned_wordlist():
    for s in ("Aksjen vil stige", "Kursen kan falle kraftig", "Prisen steg 3 %", "Bra for olje", "dårlig for rederiene",
              "Det er sikkert", "garantert avkastning", "Det ventes å komme", "kjøp", "Selg nå", "nytt kursmål"):
        assert V.banned(s), s
    for s in ("FNs sikkerhetsråd møttes.", "Russland angrep strømnettet.", "Oppkjøpet ble meldt.", "Snøfall i Oslo."):
        assert V.banned(s) is None, s


def _snap(d, gen="2026-11-04 06:40"):
    return {"verden": d, "generated": gen, "themes": [{"key": "conflict_defense", "score": 2.34}]}


def test_render_text(tmp_path):
    d, _ = _data(); p = tmp_path / "v.json"; p.write_text(json.dumps(_text()))
    h = V.html(_snap(d), text_path=p, log_path=tmp_path / "a.csv")
    t = re.sub("<[^>]+>", " ", h)
    assert "Automatisk oppsummering · skrevet 04.11 kl. 07:05 · nyeste sak 04.11 · kilder: ECB, GDELT" in h
    assert "m.fl." not in h and V.FOOTNOTE in h and V.RESERVE_LINE not in h and "Oppsummeringen er fra" not in h
    assert "vil stige" not in t and "Kjøp forsvar" not in t
    assert "score 2,3" in h and "Rangering, ikke testet" in h and "↗" in h
    for bad in ("FLAG", "robust"):
        assert bad not in h


def test_vis_alle_saker_after_three(tmp_path):
    d, _ = _data(); p = tmp_path / "v.json"
    saker = [{"tittel": f"Sak {i}", "tema": "conflict_defense", "setninger": [{"tekst": "Russland angrep strømnettet.", "lenker": [U1]}]} for i in range(7)]
    p.write_text(json.dumps(_text(saker=saker)))
    h = V.html(_snap(d), text_path=p, log_path=tmp_path / "a.csv")
    assert h.count('class="vn-sak"') == 7 and "Vis alle saker ↓" in h
    assert h.index("Sak 2") < h.index("Vis alle saker") < h.index("Sak 3")


def test_reserve_missing_file(tmp_path):
    d, _ = _data()
    h = V.html(_snap(d), text_path=tmp_path / "finnes_ikke.json", log_path=tmp_path / "a.csv")
    assert V.RESERVE_LINE in h and "#fdba74" in h and V.FOOTNOTE in h
    assert U1 in h and "Automatisk oppsummering" not in h
    assert h.index(U1) < h.index(U4)                                    # sortert etter hvor mye temaet er omtalt


def test_reserve_text_older_than_data(tmp_path):
    d, _ = _data(); p = tmp_path / "v.json"; p.write_text(json.dumps(_text(written="2026-11-03T07:05:00+01:00")))
    h = V.html(_snap(d), text_path=p, log_path=tmp_path / "a.csv")
    assert V.RESERVE_LINE in h and "Automatisk oppsummering" not in h


def test_reserve_when_all_saker_dropped(tmp_path):
    d, _ = _data(); p = tmp_path / "v.json"
    p.write_text(json.dumps(_text(saker=[{"tittel": "X", "setninger": [{"tekst": "Selg alt.", "lenker": [U1]}]}])))
    assert V.RESERVE_LINE in V.html(_snap(d), text_path=p, log_path=tmp_path / "a.csv")


def test_older_than_24h_line(tmp_path):
    d, _ = _data(); p = tmp_path / "v.json"; p.write_text(json.dumps(_text(written="2026-11-04T00:10:00+01:00")))
    h = V.html(_snap(d, gen="2026-11-05 01:00"), text_path=p, log_path=tmp_path / "a.csv")
    assert "Oppsummeringen er fra 04.11" in h and V.RESERVE_LINE not in h



# ---- 03.11 kveld: streng temamatching, sentralbank-vindu, GDELT-pauser, chip-title
def test_strict_themes_only_on_keyword_in_title():
    assert V._themes("ACG to Acquire 100% of Blue Moon Norway, Including the Construction-Stage Nussir Copper Mine") == []
    assert V._themes("Independent Valuation of Italian Solar Development Pipeline Rises to EUR 85.6 Million") == []
    assert V._themes("Performance Shipping Inc. repurchase and cancellation of share purchase warrants") == []
    assert V._themes("Star Wars premiere") == [] and V._themes("Gulf Keystone results") == []
    assert V._themes("Houthi attack in the Red Sea") == ["shipping_chokepoints"]
    assert V._themes("New US tariffs on EU steel") == ["tariffs_trade"]
    assert V._themes("Greenland approves security deal") == ["nordic_arctic"]


def test_central_banks_72h_window_and_date_marker():
    fetch = {"ECB": lambda: [{"tittel": "ECB speech", "url": "https://ecb.example/1", "kilde": "ECB", "publisert": V._parse_ts("2026-11-02T09:30:00Z")},
                             {"tittel": "ECB old", "url": "https://ecb.example/2", "kilde": "ECB", "publisert": V._parse_ts("2026-10-30T09:30:00Z")}]}
    d, _ = V.collect(None, None, now=NOW, fetch=fetch)
    assert [s["url"] for s in d["saker"]] == ["https://ecb.example/1"]
    h = V.html({"verden": d, "generated": "2026-11-04 06:40"}, text_path=__import__("pathlib").Path("/nonexistent.json"))
    assert "ECB speech (02.11) ↗" in h


def test_gdelt_doc_retries_with_pauses(monkeypatch):
    import requests
    calls, waits = [], []

    class R:
        def __init__(self, code, text): self.status_code, self.text = code, text
        def json(self): return json.loads(self.text)

    seq = [R(429, "Please limit requests to one every 5 seconds"), R(200, "Error"),
           R(200, json.dumps({"articles": [{"title": "Tariff talks", "url": "https://x.org/1", "domain": "x.org", "seendate": "20261104T040000Z"}]}))]
    monkeypatch.setattr(requests, "get", lambda *a, **k: calls.append(k) or seq[len(calls) - 1])
    monkeypatch.setattr("signaltool.http._throttle", lambda h: None)
    got = V._gdelt_doc(sleep=waits.append)
    assert len(calls) == 3 and waits == [10, 30] and got[0]["url"] == "https://x.org/1"
    assert all(k["headers"]["User-Agent"] for k in calls)


def test_gdelt_doc_gives_up(monkeypatch):
    import requests, pytest

    class R:
        status_code, text = 429, "Please limit requests"
    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    monkeypatch.setattr("signaltool.http._throttle", lambda h: None)
    with pytest.raises(RuntimeError, match="429"):
        V._gdelt_doc(sleep=lambda s: None)


def test_chip_score_has_visible_i_and_title():
    c = V._chip("conflict_defense", {"themes": [{"key": "conflict_defense", "score": 2.34}]})
    assert c.count('title="Rangering, ikke testet"') == 2 and "ⓘ" in c and '<span class="tip">Rangering, ikke testet</span>' in c
    assert "Rangering" not in V._chip("sentralbanker", {"themes": []})
