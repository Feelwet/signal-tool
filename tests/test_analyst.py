from datetime import date
from signaltool import analyst as A

H = "dato_publisert,kilde,ticker,selskap,anbefaling,kursmal,valuta,kurs_ved_anbefaling,lenke,type,verifisert\n"

def w(tmp_path, body, head=H):
    p = tmp_path / "r.csv"; p.write_text(head + body); return p

def test_only_verified_latest_and_match(tmp_path):
    p = w(tmp_path, "2026-10-01,D,ATEA.OL,A,kjop,180,NOK,1,u1,enkeltanbefaling,ja\n"
                    "2026-10-21,D,ATEA.OL,A,kjop,195,NOK,1,u2,enkeltanbefaling,ja\n"
                    "2026-10-22,D,ATEA.OL,A,selg,10,NOK,1,u3,enkeltanbefaling,usikker\n"
                    "2026-10-22,D,eric_b.st,E,kjop,133,SEK,1,u4,enkeltanbefaling,ja\n"
                    "2026-10-22,D,KOG.OL,K,kjop,,NOK,1,u5,ukeportefolje_inn,ja\n"
                    "2026-10-22,D,XXX.CO,X,kjop,5,DKK,1,u6,enkeltanbefaling,ja\n")
    r = A.load(p, universe=["ATEA.OL", "ERIC-B.ST", "KOG.OL"])
    assert set(r) == {"ATEA.OL", "ERIC-B.ST"} and r["ATEA.OL"]["kursmal"] == "195"

def test_no_column_shows_nothing(tmp_path):
    p = w(tmp_path, "2026-10-21,D,ATEA.OL,A,kjop,195,NOK,1,u,enkeltanbefaling\n", H.replace(",verifisert", ""))
    assert A.load(p, universe=["ATEA.OL"]) == {}

def test_line_format_and_old():
    r = {"dato_publisert": "2026-10-21", "anbefaling": "kjop", "kursmal": "195", "lenke": "https://x"}
    import pytest; mp = pytest.MonkeyPatch(); mp.setattr(A, "HIT_RATE_TEXT", None)
    h = A.line_html(r, 174.1, date(2026, 10, 25))
    assert "DNB Carnegie: Kjøp · kursmål 195 · +12 % fra dagens kurs · 21.10 <a" in h
    assert "Ekstern analytiker" in h and '>↗</a>' in h and h.count("<a ") == 1
    assert "◌ Bare oppmerksomhet" in h and "Treffrate under måling" in h and "eldre" not in h
    assert "%" not in h.split("title=")[1].split('"')[1]
    assert "eldre anbefaling" in A.line_html(r, 174.1, date(2027, 2, 1))
    mp.undo(); assert "40–44 %" in A.line_html(r, 174.1, date(2026, 10, 25))
    assert "DNB" in A.tag_html(r, 174.1, date(2026, 10, 25))


def test_red_badges_have_no_i():
    from signaltool import evidens as EV
    assert "ilink" not in EV.short_badge("weak_px")
