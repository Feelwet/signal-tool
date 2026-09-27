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
