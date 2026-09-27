# Nattens tester 2026-09-28 – hva leder faktisk kursene?

Alle tester bruker gratis data, fast inn-/utregel og **ut-av-utvalg-sjekk** (parametrene er valgt på første periode og bare
kontrollert på den andre). Vi regner en effekt som *robust* bare hvis den har samme fortegn i begge perioder **og** |t| ≥ ~3
(grov Bonferroni-korreksjon fordi vi tester mange ting). Kostnader: 0,2 % tur-retur USA, 0,4 % Oslo, der det står «netto».
Alle kurs-univers er dagens noterte selskaper → **overlevelsesskjevhet** (avnoterte taper-aksjer mangler), som typisk gjør
«kjøp»-resultater for gode.

## Oppsummering

| Signal | Resultat | Brukt i verktøyet? |
|---|---|---|
| **Sterk kvartalsrapport** (topp 20 % EPS-overraskelse OG topp 20 % kursreaksjon), USA | +1,48 pp (t 3,2) før 2016 og **+1,95 pp (t 3,3)** etter 2016 over 60 dager vs andre rapporter | **Ja** – ny signaltype i Kjøp-reglene + daglig skann av S&P 500 |
| **Svak 12-1-måneders momentum**, Oslo Børs (laveste 20 %) | −3,0 % (t −1,5) før 2018-07, **−3,3 % (t −3,2)** etter, 60 d vs alle; netto −3,8 % vs OSEBX | **Ja** – rødt flagg (hindrer Kjøp) for .OL |
| Kursbekreftelse (over 50d-snitt + slår indeks), USA | −0,9 pp (t −1,9) / −0,8 pp (t −3,2) vs alle, 60 d | Nei endring – ingen fordel funnet; beholdt som risikofilter, dokumentert |
| «Strukket» (Hold-lignende), USA | +2,8 pp (t 2,3) / +4,5 pp (t 3,2) | Nei – få aksjer (~10) og sterk overlevelsesskjevhet; til vurdering |
| Momentum 12-1 og sektorrelativ styrke, USA | positive, men ikke robuste (t < 3 i minst én periode) | Nei |
| Sundpassasjer (IMF PortWatch) → tankrederier/Brent | ingen signifikante (alle p > 0,1; 21–31 hendelser) | Kun kontekst/varsel |
| Oljelagre mot 5-årssnitt (EIA) → WTI/XLE | fortegnet skifter mellom perioder | Kun kontekst |
| Taiwan månedsomsetning → SMH/TSM/EWT | ingen robust sammenheng | Kun kontekst; minne→Micron følges (t 3,2 etter 2020, svak før) |
| Polymarket-bevegelse ≥ 10 pp → sektor-ETF | **samtidig** +0,57 % (t 3,4) for XLE, men **neste dag 0,00 %** og neste 5 d −0,17 % | Nei – bekreftelse, ikke forsprang |
| DoD-kontrakt i % av markedsverdi | ingen signifikante (største t 1,1) | Nei endring |
| Shortposisjoner Oslo (Finanstilsynet) | alle grupper negative (−1 til −4 %), t ≈ −1,8; historikk bare fra okt. 2024 | Beholdt som rødt flagg (økende short) |
| Innsidehandel Oslo (retning fra meldingstekst, 6 418 meldinger 2021–) | Ingen gruppe robust. Kjøp ≥ 1 mill. NOK: −5,2 % netto 60 d (t −2,7) i utvalget, +0,8 % (t 0,8) utenfor. Kjøpsklynger: −1,7 % (t −2,1) utenfor utvalget | Kun visning, ikke i Kjøp-reglene |
| Kontraktsmeldinger Oslo (4 899 titler 2019–) | Ingen robust drift etter publiseringsdagen. Alle 5 d: +0,78 pp (t 2,7) i utvalget, +0,29 pp (t 1,6) utenfor. «Største/rekord»: negativt i utvalget, positivt utenfor | Kun visning |


## 1. Drift etter kvartalsrapport (PEAD)

## Drift etter kvartalsrapport (PEAD) – USA
_Kode: signaltool/backtest/pead.py. 36,572 rapporter fra 499 av dagens S&P 500-selskaper (yfinance), 2006–. Inngang = sluttkurs dagen ETTER reaksjonsdagen (all info offentlig). Meravkastning mot SPY; netto = minus 0,2 % kostnad; t = HAC på kvartalssnitt._

| Gruppe | Horisont | Periode | Antall | Snitt (median) | Netto (t) |
|---|---|---|---|---|---|
| Overraskelse topp 20 % | 20 d | in-sample 2006–2015 | 3304 | +0.13 % (+0.09 %) | -0.07 % (-0.3) |
| Overraskelse topp 20 % | 60 d | in-sample 2006–2015 | 3304 | +1.64 % (+0.80 %) | +1.44 % (3.2) |
| Overraskelse bunn 20 % | 20 d | in-sample 2006–2015 | 3294 | +0.13 % (-0.16 %) | -0.07 % (0.1) |
| Overraskelse bunn 20 % | 60 d | in-sample 2006–2015 | 3294 | +1.63 % (+0.59 %) | +1.43 % (2.2) |
| Kursreaksjon topp 20 % | 20 d | in-sample 2006–2015 | 3305 | +0.54 % (+0.55 %) | +0.34 % (1.9) |
| Kursreaksjon topp 20 % | 60 d | in-sample 2006–2015 | 3305 | +1.68 % (+1.33 %) | +1.48 % (3.8) |
| Kursreaksjon bunn 20 % | 20 d | in-sample 2006–2015 | 3295 | +0.23 % (-0.07 %) | +0.03 % (0.3) |
| Kursreaksjon bunn 20 % | 60 d | in-sample 2006–2015 | 3295 | +1.71 % (+0.63 %) | +1.51 % (2.0) |
| Topp overraskelse OG topp reaksjon | 20 d | in-sample 2006–2015 | 1194 | +0.59 % (+0.65 %) | +0.39 % (1.6) |
| Topp overraskelse OG topp reaksjon | 60 d | in-sample 2006–2015 | 1194 | +2.56 % (+2.09 %) | +2.36 % (4.1) |
| Alle | 20 d | in-sample 2006–2015 | 16494 | +0.28 % (+0.17 %) | +0.08 % (0.8) |
| Alle | 60 d | in-sample 2006–2015 | 16494 | +1.23 % (+0.74 %) | +1.03 % (3.3) |
| Overraskelse topp 20 % | 20 d | out-of-sample 2016–2026 | 4023 | +0.74 % (+0.17 %) | +0.54 % (1.2) |
| Overraskelse topp 20 % | 60 d | out-of-sample 2016–2026 | 4023 | +1.82 % (+0.51 %) | +1.62 % (2.7) |
| Overraskelse bunn 20 % | 20 d | out-of-sample 2016–2026 | 4011 | +0.18 % (-0.42 %) | -0.02 % (-0.2) |
| Overraskelse bunn 20 % | 60 d | out-of-sample 2016–2026 | 4011 | -0.04 % (-0.62 %) | -0.24 % (-0.3) |
| Kursreaksjon topp 20 % | 20 d | out-of-sample 2016–2026 | 4022 | +0.62 % (+0.28 %) | +0.42 % (2.3) |
| Kursreaksjon topp 20 % | 60 d | out-of-sample 2016–2026 | 4022 | +1.35 % (+0.37 %) | +1.15 % (3.3) |
| Kursreaksjon bunn 20 % | 20 d | out-of-sample 2016–2026 | 4011 | +0.48 % (-0.17 %) | +0.28 % (0.9) |
| Kursreaksjon bunn 20 % | 60 d | out-of-sample 2016–2026 | 4011 | +0.77 % (-0.33 %) | +0.57 % (1.2) |
| Topp overraskelse OG topp reaksjon | 20 d | out-of-sample 2016–2026 | 1325 | +1.08 % (+0.47 %) | +0.88 % (2.2) |
| Topp overraskelse OG topp reaksjon | 60 d | out-of-sample 2016–2026 | 1325 | +2.59 % (+1.19 %) | +2.39 % (3.5) |
| Alle | 20 d | out-of-sample 2016–2026 | 20078 | +0.34 % (-0.02 %) | +0.14 % (0.7) |
| Alle | 60 d | out-of-sample 2016–2026 | 20078 | +0.41 % (-0.23 %) | +0.21 % (0.8) |


### Spread mot alle andre rapporter samme kvartal (kontrollerer for overlevelsesskjevhet som rammer alle grupper)

| Gruppe | Horisont | Periode | Spread vs alle rapporter (snitt kvartal) | HAC t | Andel kvartaler > 0 |
|---|---|---|---|---|---|
| Overraskelse topp 20 % | 20 d | IS 2006–2015 | -0.15 pp | -1.1 | 40% |
| Overraskelse topp 20 % | 60 d | IS 2006–2015 | +0.56 pp | 2.1 | 60% |
| Kursreaksjon topp 20 % | 20 d | IS 2006–2015 | +0.28 pp | 2.3 | 72% |
| Kursreaksjon topp 20 % | 60 d | IS 2006–2015 | +0.46 pp | 1.4 | 70% |
| Overraskelse bunn 20 % | 20 d | IS 2006–2015 | -0.07 pp | -0.5 | 45% |
| Overraskelse bunn 20 % | 60 d | IS 2006–2015 | +0.31 pp | 0.9 | 57% |
| Kursreaksjon bunn 20 % | 20 d | IS 2006–2015 | -0.02 pp | -0.1 | 52% |
| Kursreaksjon bunn 20 % | 60 d | IS 2006–2015 | +0.40 pp | 0.9 | 52% |
| Topp overraskelse OG topp reaksjon | 20 d | IS 2006–2015 | +0.32 pp | 1.4 | 57% |
| Topp overraskelse OG topp reaksjon | 60 d | IS 2006–2015 | +1.48 pp | 3.2 | 70% |
| Bunn overr. OG bunn reaksjon | 20 d | IS 2006–2015 | +0.08 pp | 0.3 | 50% |
| Bunn overr. OG bunn reaksjon | 60 d | IS 2006–2015 | +0.44 pp | 0.6 | 55% |
| Overraskelse topp 20 % | 20 d | OOS 2016–2026 | +0.29 pp | 1.2 | 57% |
| Overraskelse topp 20 % | 60 d | OOS 2016–2026 | +1.23 pp | 2.9 | 64% |
| Kursreaksjon topp 20 % | 20 d | OOS 2016–2026 | +0.30 pp | 2.0 | 60% |
| Kursreaksjon topp 20 % | 60 d | OOS 2016–2026 | +0.97 pp | 2.8 | 71% |
| Overraskelse bunn 20 % | 20 d | OOS 2016–2026 | -0.21 pp | -1.5 | 26% |
| Overraskelse bunn 20 % | 60 d | OOS 2016–2026 | -0.36 pp | -1.4 | 29% |
| Kursreaksjon bunn 20 % | 20 d | OOS 2016–2026 | +0.07 pp | 0.5 | 55% |
| Kursreaksjon bunn 20 % | 60 d | OOS 2016–2026 | +0.29 pp | 1.0 | 55% |
| Topp overraskelse OG topp reaksjon | 20 d | OOS 2016–2026 | +0.61 pp | 2.2 | 67% |
| Topp overraskelse OG topp reaksjon | 60 d | OOS 2016–2026 | +1.95 pp | 3.3 | 67% |
| Bunn overr. OG bunn reaksjon | 20 d | OOS 2016–2026 | -0.03 pp | -0.1 | 43% |
| Bunn overr. OG bunn reaksjon | 60 d | OOS 2016–2026 | +0.10 pp | 0.2 | 43% |


**Litteratur:** Brandt m.fl. (2008, «Earnings Announcements are Full of Surprises») fant at kursreaksjonen (EAR) gir sterkere og mer varig drift enn EPS-overraskelse alene, og at de to er uavhengige. Martineau (2022) fant at klassisk PEAD forsvant for store selskaper etter ca. 2006, mens en SHoF-studie (2025) finner fornyet drift etter 2020. Vårt funn (kombinasjonen virker, overraskelse alene er svak før 2016) er i tråd med dette.


## 2. Kursregler og momentum

## Kursregler, momentum og sektorrelativ styrke – stor test med ut-av-utvalg-sjekk
_Kode: signaltool/backtest/price_rules.py. USA: dagens S&P 500 (512 tickere m/ data, 2006–) – overlevelsesskjevhet. Oslo: 275 tickere fra Newsweb med yfinance-data (2011–). Formasjon hver 21. handelsdag, kun likvide aksjer (≥ ~$1M/dag, kurs ≥ ~$1)._

«Spread» = gruppens snitt minus snittet av alle aksjer samme dato (brutto). «Netto vs indeks» = gruppens meravkastning mot SPY/OSEBX etter handelskostnad (0,2 % USA / 0,4 % Oslo tur-retur). t = HAC t-verdi. Robust krever |t| ≥ 3,1 (Bonferroni for ~30 tester) OG samme fortegn i begge perioder.

### USA
| Gruppe | Horisont | Periode | Snitt antall aksjer | Spread vs alle (t) | Netto vs indeks (t) | Andel datoer spread > 0 |
|---|---|---|---|---|---|---|
| Kursbekreftelse (over 50d-snitt og 20d > indeks) | 20 d | in-sample 2006–2015 | 187 | -0.13 % (-1.0) | +0.17 % (0.9) | 52 % |
| Kursbekreftelse (over 50d-snitt og 20d > indeks) | 60 d | in-sample 2006–2015 | 187 | -0.51 % (-1.6) | +0.79 % (2.1) | 45 % |
| Kjøp-kursregler (kursbekr. + ikke strukket + ingen krasj) | 20 d | in-sample 2006–2015 | 175 | -0.47 % (-1.5) | -0.17 % (-0.5) | 49 % |
| Kjøp-kursregler (kursbekr. + ikke strukket + ingen krasj) | 60 d | in-sample 2006–2015 | 175 | -0.89 % (-1.9) | +0.41 % (0.9) | 44 % |
| Kursbekr. men strukket («Hold») | 20 d | in-sample 2006–2015 | 9 | +0.91 % (1.5) | +1.25 % (2.0) | 55 % |
| Kursbekr. men strukket («Hold») | 60 d | in-sample 2006–2015 | 9 | +2.81 % (2.3) | +4.17 % (3.4) | 60 % |
| Uten kursbekreftelse | 20 d | in-sample 2006–2015 | 236 | -0.04 % (-0.5) | +0.26 % (1.8) | 48 % |
| Uten kursbekreftelse | 60 d | in-sample 2006–2015 | 236 | +0.12 % (0.9) | +1.42 % (4.2) | 55 % |
| Krasj ≥ 20 % siste 20 d | 20 d | in-sample 2006–2015 | 33 | +0.20 % (0.3) | +0.54 % (0.8) | 48 % |
| Krasj ≥ 20 % siste 20 d | 60 d | in-sample 2006–2015 | 33 | +1.94 % (1.5) | +3.27 % (2.2) | 51 % |
| Momentum 12-1 mnd, topp 20 % | 20 d | in-sample 2006–2015 | 84 | -0.20 % (-0.9) | +0.11 % (0.5) | 50 % |
| Momentum 12-1 mnd, topp 20 % | 60 d | in-sample 2006–2015 | 84 | -0.58 % (-1.0) | +0.72 % (1.3) | 48 % |
| Momentum 12-1 mnd, bunn 20 % | 20 d | in-sample 2006–2015 | 83 | +0.26 % (0.8) | +0.56 % (1.5) | 46 % |
| Momentum 12-1 mnd, bunn 20 % | 60 d | in-sample 2006–2015 | 83 | +0.61 % (0.7) | +1.91 % (1.9) | 48 % |
| Sektorrelativ styrke 60 d, topp 20 % | 20 d | in-sample 2006–2015 | 76 | +0.22 % (1.6) | +0.52 % (3.4) | 59 % |
| Sektorrelativ styrke 60 d, topp 20 % | 60 d | in-sample 2006–2015 | 76 | +0.46 % (1.2) | +1.76 % (3.5) | 58 % |
| Sektorrelativ styrke 60 d, bunn 20 % | 20 d | in-sample 2006–2015 | 75 | +0.24 % (1.2) | +0.55 % (1.9) | 48 % |
| Sektorrelativ styrke 60 d, bunn 20 % | 60 d | in-sample 2006–2015 | 75 | +0.90 % (1.7) | +2.20 % (3.1) | 57 % |
| Kursbekreftelse (over 50d-snitt og 20d > indeks) | 20 d | out-of-sample 2016–2026 | 205 | +0.02 % (0.1) | +0.05 % (0.2) | 52 % |
| Kursbekreftelse (over 50d-snitt og 20d > indeks) | 60 d | out-of-sample 2016–2026 | 205 | -0.34 % (-1.3) | +0.17 % (0.4) | 47 % |
| Kjøp-kursregler (kursbekr. + ikke strukket + ingen krasj) | 20 d | out-of-sample 2016–2026 | 192 | -0.16 % (-1.3) | -0.13 % (-0.8) | 46 % |
| Kjøp-kursregler (kursbekr. + ikke strukket + ingen krasj) | 60 d | out-of-sample 2016–2026 | 192 | -0.78 % (-3.2) | -0.27 % (-0.7) | 42 % |
| Kursbekr. men strukket («Hold») | 20 d | out-of-sample 2016–2026 | 10 | +1.14 % (1.5) | +1.15 % (1.5) | 54 % |
| Kursbekr. men strukket («Hold») | 60 d | out-of-sample 2016–2026 | 10 | +4.49 % (3.2) | +4.84 % (3.5) | 62 % |
| Uten kursbekreftelse | 20 d | out-of-sample 2016–2026 | 279 | +0.01 % (0.1) | +0.04 % (0.2) | 48 % |
| Uten kursbekreftelse | 60 d | out-of-sample 2016–2026 | 279 | +0.05 % (0.3) | +0.56 % (1.8) | 53 % |
| Krasj ≥ 20 % siste 20 d | 20 d | out-of-sample 2016–2026 | 31 | +1.01 % (2.1) | +1.04 % (2.1) | 57 % |
| Krasj ≥ 20 % siste 20 d | 60 d | out-of-sample 2016–2026 | 31 | +4.27 % (2.7) | +4.78 % (3.1) | 66 % |
| Momentum 12-1 mnd, topp 20 % | 20 d | out-of-sample 2016–2026 | 97 | +0.21 % (1.1) | +0.24 % (1.3) | 55 % |
| Momentum 12-1 mnd, topp 20 % | 60 d | out-of-sample 2016–2026 | 97 | +0.99 % (2.0) | +1.50 % (2.9) | 59 % |
| Momentum 12-1 mnd, bunn 20 % | 20 d | out-of-sample 2016–2026 | 96 | +0.26 % (1.2) | +0.29 % (1.0) | 49 % |
| Momentum 12-1 mnd, bunn 20 % | 60 d | out-of-sample 2016–2026 | 96 | +0.64 % (1.1) | +1.15 % (1.6) | 49 % |
| Sektorrelativ styrke 60 d, topp 20 % | 20 d | out-of-sample 2016–2026 | 96 | +0.15 % (0.9) | +0.18 % (1.0) | 54 % |
| Sektorrelativ styrke 60 d, topp 20 % | 60 d | out-of-sample 2016–2026 | 96 | +0.61 % (1.6) | +1.12 % (2.2) | 59 % |
| Sektorrelativ styrke 60 d, bunn 20 % | 20 d | out-of-sample 2016–2026 | 95 | +0.17 % (1.1) | +0.20 % (0.9) | 52 % |
| Sektorrelativ styrke 60 d, bunn 20 % | 60 d | out-of-sample 2016–2026 | 95 | +0.60 % (1.7) | +1.12 % (2.6) | 57 % |

### Oslo Børs
| Gruppe | Horisont | Periode | Snitt antall aksjer | Spread vs alle (t) | Netto vs indeks (t) | Andel datoer spread > 0 |
|---|---|---|---|---|---|---|
| Kursbekreftelse (over 50d-snitt og 20d > indeks) | 20 d | in-sample 2014–2018 | 11 | +0.18 % (0.4) | -0.37 % (-0.7) | 56 % |
| Kursbekreftelse (over 50d-snitt og 20d > indeks) | 60 d | in-sample 2014–2018 | 11 | -0.74 % (-0.9) | -1.19 % (-1.2) | 54 % |
| Kjøp-kursregler (kursbekr. + ikke strukket + ingen krasj) | 20 d | in-sample 2014–2018 | 10 | +0.32 % (0.6) | -0.23 % (-0.4) | 62 % |
| Kjøp-kursregler (kursbekr. + ikke strukket + ingen krasj) | 60 d | in-sample 2014–2018 | 10 | -0.16 % (-0.2) | -0.61 % (-0.6) | 56 % |
| Kursbekr. men strukket («Hold») | 20 d | in-sample 2014–2018 | 2 | +0.53 % (0.2) | -0.43 % (-0.2) | 46 % |
| Kursbekr. men strukket («Hold») | 60 d | in-sample 2014–2018 | 2 | -3.44 % (-2.0) | -4.51 % (-1.9) | 25 % |
| Uten kursbekreftelse | 20 d | in-sample 2014–2018 | 14 | -0.19 % (-0.5) | -0.73 % (-1.6) | 44 % |
| Uten kursbekreftelse | 60 d | in-sample 2014–2018 | 14 | -0.00 % (-0.0) | -0.45 % (-0.4) | 46 % |
| Krasj ≥ 20 % siste 20 d | 20 d | in-sample 2014–2018 | 3 | -0.74 % (-0.4) | -1.49 % (-0.7) | 53 % |
| Krasj ≥ 20 % siste 20 d | 60 d | in-sample 2014–2018 | 3 | -5.51 % (-1.1) | -6.05 % (-1.1) | 31 % |
| Momentum 12-1 mnd, topp 20 % | 20 d | in-sample 2014–2018 | 5 | -0.28 % (-0.4) | -0.83 % (-1.2) | 44 % |
| Momentum 12-1 mnd, topp 20 % | 60 d | in-sample 2014–2018 | 5 | -1.79 % (-1.5) | -2.24 % (-1.3) | 42 % |
| Momentum 12-1 mnd, bunn 20 % | 20 d | in-sample 2014–2018 | 4 | -1.23 % (-1.2) | -1.78 % (-1.5) | 56 % |
| Momentum 12-1 mnd, bunn 20 % | 60 d | in-sample 2014–2018 | 4 | -3.03 % (-1.5) | -3.48 % (-1.3) | 35 % |
| Kursbekreftelse (over 50d-snitt og 20d > indeks) | 20 d | out-of-sample 2018–2026 | 19 | +0.13 % (0.3) | -0.33 % (-0.8) | 48 % |
| Kursbekreftelse (over 50d-snitt og 20d > indeks) | 60 d | out-of-sample 2018–2026 | 19 | -0.19 % (-0.3) | -0.74 % (-0.9) | 51 % |
| Kjøp-kursregler (kursbekr. + ikke strukket + ingen krasj) | 20 d | out-of-sample 2018–2026 | 16 | +0.78 % (2.2) | +0.27 % (0.7) | 55 % |
| Kjøp-kursregler (kursbekr. + ikke strukket + ingen krasj) | 60 d | out-of-sample 2018–2026 | 16 | +0.97 % (1.6) | +0.35 % (0.6) | 51 % |
| Kursbekr. men strukket («Hold») | 20 d | out-of-sample 2018–2026 | 3 | -2.29 % (-2.5) | -2.90 % (-2.9) | 35 % |
| Kursbekr. men strukket («Hold») | 60 d | out-of-sample 2018–2026 | 3 | -2.85 % (-1.2) | -3.71 % (-1.3) | 42 % |
| Uten kursbekreftelse | 20 d | out-of-sample 2018–2026 | 24 | -0.08 % (-0.4) | -0.55 % (-1.6) | 52 % |
| Uten kursbekreftelse | 60 d | out-of-sample 2018–2026 | 24 | -0.47 % (-1.3) | -1.02 % (-1.4) | 49 % |
| Krasj ≥ 20 % siste 20 d | 20 d | out-of-sample 2018–2026 | 6 | -1.53 % (-1.1) | -1.91 % (-1.3) | 44 % |
| Krasj ≥ 20 % siste 20 d | 60 d | out-of-sample 2018–2026 | 6 | -1.53 % (-0.7) | -1.82 % (-0.7) | 47 % |
| Momentum 12-1 mnd, topp 20 % | 20 d | out-of-sample 2018–2026 | 9 | +0.68 % (1.5) | +0.21 % (0.4) | 55 % |
| Momentum 12-1 mnd, topp 20 % | 60 d | out-of-sample 2018–2026 | 9 | +1.76 % (2.3) | +1.21 % (1.2) | 64 % |
| Momentum 12-1 mnd, bunn 20 % | 20 d | out-of-sample 2018–2026 | 8 | -1.06 % (-1.9) | -1.53 % (-2.2) | 41 % |
| Momentum 12-1 mnd, bunn 20 % | 60 d | out-of-sample 2018–2026 | 8 | -3.25 % (-3.2) | -3.80 % (-2.8) | 32 % |


## 3. Fysiske indikatorer

## Trafikkfall i sjøveis flaskehalser (IMF PortWatch) vs tankrederier og Brent
_Kode: signaltool/backtest/chokepoint.py. Hendelse = 7-dagers snitt av tankskip-passeringer ≥ 2 robuste z under foregående 60 dager (20 d karantene). Inngang 7 kalenderdager etter hendelsen (PortWatch publiseres med ca. en ukes forsinkelse). Meravkastning mot SPY. p = andel av 2000 tilfeldige like store utvalg av dager med minst like stort snitt._

| Flaskehals | Hendelser | Instrument | 20 d etter (snitt) | Alle dager 20 d | p | 60 d etter | Alle dager 60 d |
|---|---|---|---|---|---|---|---|
| Hormuzstredet | 31 | FRO | +0.66 % | +2.29 % | 0.49 | +4.02 % | +6.30 % |
| Hormuzstredet | 31 | DHT | +0.79 % | +1.53 % | 0.71 | +4.52 % | +3.95 % |
| Hormuzstredet | 31 | STNG | +2.07 % | +1.00 % | 0.69 | +3.36 % | +3.95 % |
| Hormuzstredet | 31 | BZ=F | -3.41 % | -0.25 % | 0.13 | -4.95 % | -0.78 % |
| Bab el-Mandeb | 30 | FRO | +2.40 % | +2.29 % | 0.97 | +8.81 % | +6.30 % |
| Bab el-Mandeb | 30 | DHT | +2.49 % | +1.53 % | 0.66 | +6.56 % | +3.95 % |
| Bab el-Mandeb | 30 | STNG | +1.05 % | +1.00 % | 0.99 | +7.47 % | +3.95 % |
| Bab el-Mandeb | 30 | BZ=F | +1.21 % | -0.25 % | 0.48 | +2.73 % | -0.78 % |
| Suezkanalen | 26 | FRO | +4.54 % | +2.29 % | 0.40 | +15.27 % | +6.30 % |
| Suezkanalen | 26 | DHT | +4.65 % | +1.53 % | 0.18 | +14.46 % | +3.95 % |
| Suezkanalen | 26 | STNG | +0.77 % | +1.00 % | 0.93 | +11.19 % | +3.95 % |
| Suezkanalen | 26 | BZ=F | -1.88 % | -0.25 % | 0.47 | -2.13 % | -0.78 % |
| Panamakanalen | 21 | FRO | -0.53 % | +2.29 % | 0.33 | +12.10 % | +6.30 % |
| Panamakanalen | 21 | DHT | -2.28 % | +1.53 % | 0.13 | +10.92 % | +3.95 % |
| Panamakanalen | 21 | STNG | -3.44 % | +1.00 % | 0.17 | +3.57 % | +3.95 % |
| Panamakanalen | 21 | BZ=F | +0.53 % | -0.25 % | 0.74 | +0.62 % | -0.78 % |

**Forbehold:** Svært få uavhengige hendelser (Rødehavskrisen 2023–24, Panama-tørken 2023, Hormuz 2025–26 dominerer); mange tester (4 flaskehalser × 4 instrumenter) → forvent noen lave p-verdier ved flaks. Ingen kostnader.


### Oljelagre mot 5-årssnitt
_Kode: signaltool/backtest/oil_stocks.py. EIA ukentlige lagre 1995–2026, inngang 5 dager etter ukeslutt, IS < 2015, OOS ≥ 2015. HAC t på kovarians._


| Serie | Signal | Mål | Horisont | Periode | N | Koeff. | HAC t | Treff (fall→opp) |
|---|---|---|---|---|---|---|---|---|
| WCESTUS1 | nivå vs 5-år | CL=F | 20d | IS <2015 | 782 | 0.088 | 1.07 | 50% |
| WCESTUS1 | nivå vs 5-år | CL=F | 20d | OOS ≥2015 | 608 | 0.041 | 0.77 | 44% |
| WCESTUS1 | nivå vs 5-år | CL=F | 60d | IS <2015 | 782 | 0.523 | 2.44 | 39% |
| WCESTUS1 | nivå vs 5-år | CL=F | 60d | OOS ≥2015 | 600 | 0.086 | 0.59 | 42% |
| WCESTUS1 | nivå vs 5-år | XLE vs SPY | 20d | IS <2015 | 782 | 0.161 | 3.12 | 46% |
| WCESTUS1 | nivå vs 5-år | XLE vs SPY | 20d | OOS ≥2015 | 608 | -0.044 | -1.48 | 54% |
| WCESTUS1 | nivå vs 5-år | XLE vs SPY | 60d | IS <2015 | 782 | 0.079 | 1.01 | 51% |
| WCESTUS1 | nivå vs 5-år | XLE vs SPY | 60d | OOS ≥2015 | 600 | -0.134 | -1.57 | 56% |
| WCESTUS1 | 4-ukers endring i avvik | CL=F | 20d | IS <2015 | 778 | -0.139 | -0.70 | 51% |
| WCESTUS1 | 4-ukers endring i avvik | CL=F | 20d | OOS ≥2015 | 608 | 0.599 | 0.93 | 50% |
| WCESTUS1 | 4-ukers endring i avvik | CL=F | 60d | IS <2015 | 778 | 0.237 | 0.54 | 49% |
| WCESTUS1 | 4-ukers endring i avvik | CL=F | 60d | OOS ≥2015 | 600 | 1.001 | 0.87 | 54% |
| WCESTUS1 | 4-ukers endring i avvik | XLE vs SPY | 20d | IS <2015 | 778 | 0.087 | 0.86 | 53% |
| WCESTUS1 | 4-ukers endring i avvik | XLE vs SPY | 20d | OOS ≥2015 | 608 | -0.030 | -0.19 | 49% |
| WCESTUS1 | 4-ukers endring i avvik | XLE vs SPY | 60d | IS <2015 | 778 | 0.185 | 1.09 | 47% |
| WCESTUS1 | 4-ukers endring i avvik | XLE vs SPY | 60d | OOS ≥2015 | 600 | -0.210 | -0.69 | 53% |
| WGTSTUS1 | nivå vs 5-år | CL=F | 20d | IS <2015 | 782 | 0.271 | 1.66 | 47% |
| WGTSTUS1 | nivå vs 5-år | CL=F | 20d | OOS ≥2015 | 608 | 0.409 | 1.53 | 45% |
| WGTSTUS1 | nivå vs 5-år | CL=F | 60d | IS <2015 | 782 | 0.778 | 1.97 | 44% |
| WGTSTUS1 | nivå vs 5-år | CL=F | 60d | OOS ≥2015 | 600 | 0.562 | 1.01 | 45% |
| WGTSTUS1 | nivå vs 5-år | XLE vs SPY | 20d | IS <2015 | 782 | 0.306 | 3.24 | 44% |
| WGTSTUS1 | nivå vs 5-år | XLE vs SPY | 20d | OOS ≥2015 | 608 | -0.104 | -1.06 | 55% |
| WGTSTUS1 | nivå vs 5-år | XLE vs SPY | 60d | IS <2015 | 782 | 0.238 | 1.46 | 53% |
| WGTSTUS1 | nivå vs 5-år | XLE vs SPY | 60d | OOS ≥2015 | 600 | -0.609 | -2.31 | 59% |
| WGTSTUS1 | 4-ukers endring i avvik | CL=F | 20d | IS <2015 | 778 | 0.176 | 0.77 | 48% |
| WGTSTUS1 | 4-ukers endring i avvik | CL=F | 20d | OOS ≥2015 | 608 | 1.424 | 1.97 | 44% |
| WGTSTUS1 | 4-ukers endring i avvik | CL=F | 60d | IS <2015 | 778 | 0.507 | 1.30 | 47% |
| WGTSTUS1 | 4-ukers endring i avvik | CL=F | 60d | OOS ≥2015 | 600 | 2.044 | 1.43 | 49% |
| WGTSTUS1 | 4-ukers endring i avvik | XLE vs SPY | 20d | IS <2015 | 778 | 0.046 | 0.43 | 49% |
| WGTSTUS1 | 4-ukers endring i avvik | XLE vs SPY | 20d | OOS ≥2015 | 608 | 0.577 | 3.27 | 41% |
| WGTSTUS1 | 4-ukers endring i avvik | XLE vs SPY | 60d | IS <2015 | 778 | 0.261 | 1.65 | 44% |
| WGTSTUS1 | 4-ukers endring i avvik | XLE vs SPY | 60d | OOS ≥2015 | 600 | 0.220 | 0.70 | 52% |
| WDISTUS1 | nivå vs 5-år | CL=F | 20d | IS <2015 | 782 | 0.108 | 2.31 | 50% |
| WDISTUS1 | nivå vs 5-år | CL=F | 20d | OOS ≥2015 | 608 | 0.104 | 1.73 | 49% |
| WDISTUS1 | nivå vs 5-år | CL=F | 60d | IS <2015 | 782 | 0.309 | 2.66 | 41% |
| WDISTUS1 | nivå vs 5-år | CL=F | 60d | OOS ≥2015 | 600 | 0.260 | 1.80 | 46% |
| WDISTUS1 | nivå vs 5-år | XLE vs SPY | 20d | IS <2015 | 782 | 0.076 | 3.39 | 42% |
| WDISTUS1 | nivå vs 5-år | XLE vs SPY | 20d | OOS ≥2015 | 608 | -0.058 | -1.30 | 48% |
| WDISTUS1 | nivå vs 5-år | XLE vs SPY | 60d | IS <2015 | 782 | 0.047 | 0.96 | 51% |
| WDISTUS1 | nivå vs 5-år | XLE vs SPY | 60d | OOS ≥2015 | 600 | -0.115 | -0.89 | 41% |
| WDISTUS1 | 4-ukers endring i avvik | CL=F | 20d | IS <2015 | 778 | 0.336 | 1.89 | 50% |
| WDISTUS1 | 4-ukers endring i avvik | CL=F | 20d | OOS ≥2015 | 608 | 0.522 | 1.07 | 49% |
| WDISTUS1 | 4-ukers endring i avvik | CL=F | 60d | IS <2015 | 778 | 0.720 | 1.83 | 50% |
| WDISTUS1 | 4-ukers endring i avvik | CL=F | 60d | OOS ≥2015 | 600 | 0.405 | 0.56 | 50% |
| WDISTUS1 | 4-ukers endring i avvik | XLE vs SPY | 20d | IS <2015 | 778 | 0.104 | 1.54 | 49% |
| WDISTUS1 | 4-ukers endring i avvik | XLE vs SPY | 20d | OOS ≥2015 | 608 | -0.158 | -1.54 | 52% |
| WDISTUS1 | 4-ukers endring i avvik | XLE vs SPY | 60d | IS <2015 | 778 | 0.118 | 1.19 | 51% |
| WDISTUS1 | 4-ukers endring i avvik | XLE vs SPY | 60d | OOS ≥2015 | 600 | -0.482 | -1.76 | 55% |


### Taiwan månedsomsetning
_Kode: signaltool/backtest/taiwan.py. MOPS 2012–2026 (176 måneder), inngang den 11. i påfølgende måned._


| Signal | Mål (vs SPY) | Horisont | Periode | N | Korrelasjon | HAC t | Øverste − nederste tredjedel |
|---|---|---|---|---|---|---|---|
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | SMH | 21 d | IS 2013–2019 | 93 | -0.08 | -0.70 | -1.6 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | SMH | 21 d | OOS 2020– | 79 | +0.04 | 0.39 | +1.1 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | SMH | 63 d | IS 2013–2019 | 93 | +0.06 | 0.52 | +0.6 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | SMH | 63 d | OOS 2020– | 77 | -0.10 | -1.03 | +0.0 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | TSM | 21 d | IS 2013–2019 | 93 | -0.20 | -2.01 | -4.1 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | TSM | 21 d | OOS 2020– | 79 | -0.13 | -1.06 | -1.8 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | TSM | 63 d | IS 2013–2019 | 93 | -0.02 | -0.12 | -1.6 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | TSM | 63 d | OOS 2020– | 77 | -0.02 | -0.16 | +2.4 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | EWT | 21 d | IS 2013–2019 | 93 | -0.24 | -2.33 | -2.5 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | EWT | 21 d | OOS 2020– | 79 | +0.01 | 0.05 | +0.8 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | EWT | 63 d | IS 2013–2019 | 93 | -0.04 | -0.44 | -1.2 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | EWT | 63 d | OOS 2020– | 77 | +0.08 | 0.83 | +2.2 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | MU | 21 d | IS 2013–2019 | 93 | -0.02 | -0.24 | -1.4 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | MU | 21 d | OOS 2020– | 79 | +0.12 | 1.22 | +5.6 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | MU | 63 d | IS 2013–2019 | 93 | +0.18 | 1.91 | +9.9 pp |
| Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før) | MU | 63 d | OOS 2020– | 77 | -0.07 | -0.60 | -2.1 pp |
| Kurv å/å nivå | SMH | 21 d | IS 2013–2019 | 96 | -0.08 | -0.85 | -0.7 pp |
| Kurv å/å nivå | SMH | 21 d | OOS 2020– | 79 | +0.02 | 0.17 | +0.9 pp |
| Kurv å/å nivå | SMH | 63 d | IS 2013–2019 | 96 | -0.13 | -1.11 | -1.8 pp |
| Kurv å/å nivå | SMH | 63 d | OOS 2020– | 77 | +0.04 | 0.22 | -0.2 pp |
| Kurv å/å nivå | TSM | 21 d | IS 2013–2019 | 96 | -0.09 | -1.04 | -1.2 pp |
| Kurv å/å nivå | TSM | 21 d | OOS 2020– | 79 | -0.09 | -0.83 | -1.0 pp |
| Kurv å/å nivå | TSM | 63 d | IS 2013–2019 | 96 | +0.01 | 0.07 | -0.2 pp |
| Kurv å/å nivå | TSM | 63 d | OOS 2020– | 77 | -0.04 | -0.27 | -0.8 pp |
| Kurv å/å nivå | EWT | 21 d | IS 2013–2019 | 96 | -0.18 | -1.83 | -1.1 pp |
| Kurv å/å nivå | EWT | 21 d | OOS 2020– | 79 | +0.12 | 0.98 | +0.8 pp |
| Kurv å/å nivå | EWT | 63 d | IS 2013–2019 | 96 | -0.04 | -0.46 | -1.5 pp |
| Kurv å/å nivå | EWT | 63 d | OOS 2020– | 77 | +0.31 | 1.39 | +4.3 pp |
| Kurv å/å nivå | MU | 21 d | IS 2013–2019 | 96 | -0.05 | -0.46 | -2.6 pp |
| Kurv å/å nivå | MU | 21 d | OOS 2020– | 79 | +0.22 | 1.43 | +5.9 pp |
| Kurv å/å nivå | MU | 63 d | IS 2013–2019 | 96 | -0.19 | -1.31 | -10.1 pp |
| Kurv å/å nivå | MU | 63 d | OOS 2020– | 77 | +0.25 | 1.19 | +17.0 pp |
| TSMC å/å akselerasjon | SMH | 21 d | IS 2013–2019 | 93 | +0.12 | 1.17 | +0.3 pp |
| TSMC å/å akselerasjon | SMH | 21 d | OOS 2020– | 79 | -0.12 | -0.97 | -2.1 pp |
| TSMC å/å akselerasjon | SMH | 63 d | IS 2013–2019 | 93 | +0.24 | 1.91 | +2.1 pp |
| TSMC å/å akselerasjon | SMH | 63 d | OOS 2020– | 77 | -0.07 | -0.79 | -3.8 pp |
| TSMC å/å akselerasjon | TSM | 21 d | IS 2013–2019 | 93 | -0.08 | -0.70 | -2.6 pp |
| TSMC å/å akselerasjon | TSM | 21 d | OOS 2020– | 79 | -0.14 | -1.49 | -3.5 pp |
| TSMC å/å akselerasjon | TSM | 63 d | IS 2013–2019 | 93 | +0.19 | 1.85 | +2.5 pp |
| TSMC å/å akselerasjon | TSM | 63 d | OOS 2020– | 77 | -0.16 | -1.35 | -7.7 pp |
| TSMC å/å akselerasjon | EWT | 21 d | IS 2013–2019 | 93 | +0.01 | 0.05 | -1.0 pp |
| TSMC å/å akselerasjon | EWT | 21 d | OOS 2020– | 79 | -0.06 | -0.74 | -0.8 pp |
| TSMC å/å akselerasjon | EWT | 63 d | IS 2013–2019 | 93 | +0.23 | 2.02 | +2.2 pp |
| TSMC å/å akselerasjon | EWT | 63 d | OOS 2020– | 77 | -0.05 | -0.40 | -2.8 pp |
| TSMC å/å akselerasjon | MU | 21 d | IS 2013–2019 | 93 | +0.12 | 1.21 | +3.6 pp |
| TSMC å/å akselerasjon | MU | 21 d | OOS 2020– | 79 | +0.06 | 0.62 | +2.5 pp |
| TSMC å/å akselerasjon | MU | 63 d | IS 2013–2019 | 93 | +0.16 | 1.31 | +7.3 pp |
| TSMC å/å akselerasjon | MU | 63 d | OOS 2020– | 77 | -0.08 | -0.75 | -10.5 pp |
| Minne å/å akselerasjon | MU | 21 d | IS 2013–2019 | 93 | +0.08 | 0.90 | +6.0 pp |
| Minne å/å akselerasjon | MU | 21 d | OOS 2020– | 79 | +0.28 | 3.18 | +11.7 pp |
| Minne å/å akselerasjon | MU | 63 d | IS 2013–2019 | 93 | +0.03 | 0.23 | +5.1 pp |
| Minne å/å akselerasjon | MU | 63 d | OOS 2020– | 77 | +0.41 | 1.88 | +36.3 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | SMH | 21 d | IS 2013–2019 | 93 | +0.08 | 0.77 | +0.4 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | SMH | 21 d | OOS 2020– | 79 | -0.06 | -0.57 | -0.3 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | SMH | 63 d | IS 2013–2019 | 93 | +0.03 | 0.31 | +0.0 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | SMH | 63 d | OOS 2020– | 77 | -0.03 | -0.24 | +1.6 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | TSM | 21 d | IS 2013–2019 | 93 | -0.02 | -0.25 | -1.0 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | TSM | 21 d | OOS 2020– | 79 | -0.08 | -0.72 | +0.2 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | TSM | 63 d | IS 2013–2019 | 93 | +0.15 | 1.45 | +2.0 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | TSM | 63 d | OOS 2020– | 77 | +0.03 | 0.27 | +5.6 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | EWT | 21 d | IS 2013–2019 | 93 | -0.05 | -0.48 | -0.3 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | EWT | 21 d | OOS 2020– | 79 | -0.05 | -0.50 | +0.3 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | EWT | 63 d | IS 2013–2019 | 93 | +0.05 | 0.46 | +0.6 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | EWT | 63 d | OOS 2020– | 77 | +0.10 | 1.01 | +3.2 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | MU | 21 d | IS 2013–2019 | 93 | +0.12 | 1.08 | +3.4 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | MU | 21 d | OOS 2020– | 79 | +0.11 | 1.06 | +4.2 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | MU | 63 d | IS 2013–2019 | 93 | +0.07 | 0.65 | +4.6 pp |
| Bredde (andel selskaper opp å/å) endring 3 mnd | MU | 63 d | OOS 2020– | 77 | +0.07 | 0.55 | +8.6 pp |


## 4. Prediksjonsmarkeder

## Polymarket-bevegelse → sektor-ETF (retningsjustert, minus SPY)
_311 markeder (volum ≥ $2M, geopolitikk/verden), 577 hendelser (|endring| ≥ 10 pp på en dag) 2024-08-17–2026-09-14. Positivt tall = ETF beveget seg i retningen nyheten tilsier. t = Newey-West på ukesnitt. Merk: perioden domineres av få episoder (særlig USA–Iran 2026)._

| Mål | ETF | N | Snitt | Andel riktig retning | t |
|---|---|---|---|---|---|
| Samme dag (samtidig) | ITA | 64 | -0.06 % | 41% | -1.2 |
| Neste handelsdag | ITA | 81 | +0.04 % | 56% | 0.5 |
| Neste 5 handelsdager | ITA | 81 | +0.29 % | 58% | 0.6 |
| Neste handelsdag | SMH | 5 | -0.05 % | 20% | nan |
| Neste 5 handelsdager | SMH | 5 | -0.96 % | 40% | nan |
| Samme dag (samtidig) | XLE | 336 | +0.57 % | 61% | 3.4 |
| Neste handelsdag | XLE | 491 | -0.00 % | 45% | -0.8 |
| Neste 5 handelsdager | XLE | 491 | -0.17 % | 51% | 0.1 |
| Samme dag (samtidig) | alle | 404 | +0.47 % | 58% | 3.4 |
| Neste handelsdag | alle | 577 | +0.00 % | 47% | -1.4 |
| Neste 5 handelsdager | alle | 577 | -0.12 % | 51% | -0.4 |


## 5. Offentlige kontrakter

## DoD-kontraktens størrelse i forhold til markedsverdi → meravkastning vs SPY
_335 kontrakter ≥ $100M (USAspending 2022–, 30 d karantene per selskap). Markedsverdi ≈ kurs × dagens aksjeantall (tilnærming). Inngang 2 handelsdager etter kontraktsdato. Ingen kostnader trukket (≈0,2 % tur-retur). t = Newey-West på månedssnitt._

| Gruppe | N | 20 d snitt (t) | 60 d snitt (t) | Andel > 0 (60 d) |
|---|---|---|---|---|
| Kontrakt ≥ 1 % av markedsverdi | 107 | +0.89 % (0.9) | +0.55 % (0.3) | 54% |
| 0,25–1 % | 109 | +1.28 % (1.1) | +0.34 % (0.0) | 48% |
| < 0,25 % | 119 | +0.55 % (0.3) | -1.19 % (-1.7) | 45% |
| Alle | 335 | +0.89 % (1.2) | -0.13 % (-0.3) | 49% |

Største relative kontrakter: HII 2023-08 (98.3 %), VVX 2022-03 (39.6 %), TXT 2022-12 (32.7 %), VVX 2023-06 (27.5 %), HII 2024-09 (21.4 %), VVX 2025-06 (20.9 %), VVX 2022-07 (16.1 %), HUM 2022-12 (16.0 %)


## 6. Oslo Børs: shortposisjoner

## Shortposisjoner Oslo Børs (Finanstilsynet) → senere avkastning
_477 månedlige observasjoner 2024-10–2026-09 (API-et har bare historikk fra da – derfor ingen in-sample-periode). Kurs-univers = dagens noterte selskaper (overlevelsesskjevhet); kolonnen «mot snitt av likvide aksjer» korrigerer delvis for dette._

| Gruppe | Horisont | Periode | N (aksjer) | Meravk. vs OSEBX | Netto (t) | Mot snitt av likvide aksjer (t) |
|---|---|---|---|---|---|---|
| Short redusert ≥ 0,5 pp på 30 d | 20 d | out-of-sample 2024-11–2026-08 | 112 (46) | -0.71 % | -1.11 % (-1.7) | -0.67 pp (-1.3) |
| Short økt ≥ 0,5 pp på 30 d | 20 d | out-of-sample 2024-10–2026-08 | 141 (51) | -1.55 % | -1.95 % (-1.8) | -1.22 pp (-1.0) |
| Short-nivå ≥ 3 % | 20 d | out-of-sample 2024-10–2026-08 | 87 (17) | -1.90 % | -2.30 % (-1.8) | -1.71 pp (-1.4) |
| Short redusert ≥ 0,5 pp på 30 d | 60 d | out-of-sample 2024-11–2026-06 | 99 (40) | -0.36 % | -0.76 % (-0.6) | -0.35 pp (-0.5) |
| Short økt ≥ 0,5 pp på 30 d | 60 d | out-of-sample 2024-10–2026-06 | 126 (50) | -1.94 % | -2.34 % (-1.2) | -1.46 pp (-0.9) |
| Short-nivå ≥ 3 % | 60 d | out-of-sample 2024-10–2026-06 | 77 (16) | -4.36 % | -4.76 % (-1.8) | -4.01 pp (-1.5) |

## 7. Oslo Børs: innsidehandel (kjøp/salg lest fra meldingen)

### Innsidehandel Oslo Børs (retning lest fra Newsweb-meldingen) → senere avkastning
_6,418 hendelser fra meldinger 2021– (klassifisert automatisk; kjøp/salg, ikke opsjoner/program). In-sample 2021–2023, out-of-sample 2024–. Inngang = sluttkurs dagen etter publisering._

| Gruppe | Horisont | Periode | N (aksjer) | Meravk. vs OSEBX | Netto (t) | Mot snitt av likvide aksjer (t) |
|---|---|---|---|---|---|---|
| Innsidekjøp (alle) | 20 d | in-sample 2021-01–2023-12 | 510 (79) | -0.18 % | -0.58 % (0.7) | +0.02 pp (1.5) |
| Innsidekjøp ≥ NOK 1 mill. | 20 d | in-sample 2021-01–2023-12 | 202 (52) | -0.54 % | -0.94 % (-0.1) | -0.12 pp (0.7) |
| Innsidekjøp-klynge (≥ 2 meldinger på 14 d) | 20 d | in-sample 2021-01–2023-12 | 154 (51) | -0.00 % | -0.40 % (0.7) | +0.41 pp (1.1) |
| Innsidesalg (alle) | 20 d | in-sample 2021-01–2023-12 | 199 (54) | +0.79 % | +0.39 % (0.3) | +1.30 pp (1.0) |
| Innsidekjøp (alle) | 20 d | out-of-sample 2024-01–2026-08 | 449 (78) | -0.45 % | -0.85 % (-1.6) | -0.01 pp (-0.8) |
| Innsidekjøp ≥ NOK 1 mill. | 20 d | out-of-sample 2024-01–2026-08 | 103 (34) | +0.38 % | -0.02 % (0.6) | +0.53 pp (1.5) |
| Innsidekjøp-klynge (≥ 2 meldinger på 14 d) | 20 d | out-of-sample 2024-01–2026-08 | 133 (50) | -0.88 % | -1.28 % (-2.2) | -0.26 pp (-1.6) |
| Innsidesalg (alle) | 20 d | out-of-sample 2024-01–2026-08 | 180 (59) | -0.58 % | -0.98 % (-0.4) | -0.20 pp (0.4) |
| Innsidekjøp (alle) | 60 d | in-sample 2021-01–2023-12 | 510 (79) | -1.80 % | -2.20 % (-0.7) | -0.75 pp (-0.1) |
| Innsidekjøp ≥ NOK 1 mill. | 60 d | in-sample 2021-01–2023-12 | 202 (52) | -4.78 % | -5.18 % (-2.7) | -2.82 pp (-2.1) |
| Innsidekjøp-klynge (≥ 2 meldinger på 14 d) | 60 d | in-sample 2021-01–2023-12 | 154 (51) | -0.37 % | -0.77 % (0.3) | +0.77 pp (0.9) |
| Innsidesalg (alle) | 60 d | in-sample 2021-01–2023-12 | 199 (54) | +0.15 % | -0.25 % (-0.0) | +0.81 pp (0.8) |
| Innsidekjøp (alle) | 60 d | out-of-sample 2024-01–2026-07 | 418 (77) | -0.38 % | -0.78 % (-0.7) | -0.14 pp (0.0) |
| Innsidekjøp ≥ NOK 1 mill. | 60 d | out-of-sample 2024-01–2026-06 | 97 (32) | +1.19 % | +0.79 % (0.8) | +0.87 pp (1.1) |
| Innsidekjøp-klynge (≥ 2 meldinger på 14 d) | 60 d | out-of-sample 2024-01–2026-07 | 121 (47) | -1.26 % | -1.66 % (-2.1) | -0.83 pp (-1.6) |
| Innsidesalg (alle) | 60 d | out-of-sample 2024-01–2026-06 | 171 (57) | +0.08 % | -0.32 % (-0.4) | +0.42 pp (0.1) |


**Tolkning:** Ingen gruppe har |t| ≥ 3,1 med samme fortegn i begge perioder. Store kjøp (≥ 1 mill. NOK) snur fortegn: klart negative i 2021–2023 og svakt positive fra 2024. Kjøpsklynger er negative utenfor utvalget. Dette stemmer med Eckbo & Smith (norske data, ingen langsiktig meravkastning). Masteroppgavene som finner +1–2 % måler reaksjonen på selve meldingsdagen, og den har allerede skjedd når vi kan handle (sluttkurs dagen etter). Kun ~1 300 av 6 418 hendelser er med i målingen: resten er illikvide selskaper eller mangler kurs hos Yahoo. t-verdien regnes på månedssnitt (hver måned veier likt), så fortegnet kan avvike fra snittet over alle hendelser. **Beslutning: innsidehandel i Oslo vises på siden, men gir ikke poeng i Kjøp-reglene.**

## 8. Oslo Børs: kontraktsmeldinger

### Kontraktsmeldinger Oslo Børs (Newsweb-titler) → senere avkastning
_4,899 hendelser 2019– (titler med kontrakt/ordre/rammeavtale/LOI, uten aksje-/opsjons-/rettssaksmeldinger). In-sample 2019–2022, out-of-sample 2023–. Inngang = sluttkurs dagen ETTER publisering (dagens reaksjon er da allerede tatt) – tester om det er drift etterpå._

| Gruppe | Horisont | Periode | N (aksjer) | Meravk. vs OSEBX | Netto (t) | Mot snitt av likvide aksjer (t) |
|---|---|---|---|---|---|---|
| Kontraktsmelding (alle) | 1 d | in-sample 2019-01–2022-12 | 545 (51) | +0.16 % | -0.24 % (-1.7) | +0.10 pp (0.4) |
| Kontraktsmelding med «største/betydelig/rekord» o.l. | 1 d | in-sample 2019-06–2022-12 | 45 (14) | -0.03 % | -0.43 % (-1.0) | -0.16 pp (-0.6) |
| Kontraktsmelding (alle) | 1 d | out-of-sample 2023-01–2026-09 | 629 (67) | +0.13 % | -0.27 % (-3.0) | +0.12 pp (2.0) |
| Kontraktsmelding med «største/betydelig/rekord» o.l. | 1 d | out-of-sample 2023-02–2026-08 | 72 (18) | +0.35 % | -0.05 % (-0.4) | +0.35 pp (1.0) |
| Kontraktsmelding (alle) | 5 d | in-sample 2019-01–2022-12 | 545 (51) | +0.90 % | +0.50 % (1.9) | +0.78 pp (2.7) |
| Kontraktsmelding med «største/betydelig/rekord» o.l. | 5 d | in-sample 2019-06–2022-12 | 45 (14) | -0.03 % | -0.43 % (-1.3) | +0.04 pp (-0.7) |
| Kontraktsmelding (alle) | 5 d | out-of-sample 2023-01–2026-09 | 628 (67) | +0.28 % | -0.12 % (-0.3) | +0.29 pp (1.6) |
| Kontraktsmelding med «største/betydelig/rekord» o.l. | 5 d | out-of-sample 2023-02–2026-08 | 72 (18) | +1.53 % | +1.13 % (1.8) | +1.53 pp (2.6) |
| Kontraktsmelding (alle) | 20 d | in-sample 2019-01–2022-12 | 545 (51) | +1.25 % | +0.85 % (1.6) | +1.13 pp (2.1) |
| Kontraktsmelding med «største/betydelig/rekord» o.l. | 20 d | in-sample 2019-06–2022-12 | 45 (14) | -1.61 % | -2.01 % (-0.7) | -1.45 pp (-0.7) |
| Kontraktsmelding (alle) | 20 d | out-of-sample 2023-01–2026-08 | 622 (66) | +0.49 % | +0.09 % (-0.2) | +0.59 pp (0.9) |
| Kontraktsmelding med «største/betydelig/rekord» o.l. | 20 d | out-of-sample 2023-02–2026-08 | 70 (17) | +2.96 % | +2.56 % (2.2) | +3.06 pp (2.3) |


**Tolkning:** Kontraktsmeldinger er som ventet en positiv hendelse, men når vi går inn på sluttkurs dagen etter, er det ingen robust drift igjen. Den eneste t-verdien over 2,5 (alle meldinger, 5 d, i utvalget) halveres utenfor utvalget. Undergruppen med «største/rekord» er liten (45–72 hendelser) og snur fortegn. **Beslutning: kontraktsmeldinger vises, men gir ikke ekstra poeng.**

