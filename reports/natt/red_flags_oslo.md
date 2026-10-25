## Røde flagg Oslo Børs – test med samme oppsett som price_rules.py

_Kode: signaltool/backtest/red_flags.py (ny fil). Formasjon hver 21. handelsdag, likvide aksjer (≥ ~$1M/dag, kurs ≥ ~$1), snitt ~37 aksjer per dato, 143 datoer. Inngang close t+1. Spread = gruppe minus alle samme dato; netto = gruppe vs OSEBX minus 0,4 %. HAC t (lag 0/3). IS 2014-01–2018-06, OOS 2018-07–2026-06. Robust = |t| ≥ 3,1 OG samme fortegn i begge perioder. Overlevelsesskjevhet: univers = dagens Newsweb-utstedere._

| Flagg | Horisont | Periode | Snitt n aksjer | Spread vs alle (t) | Netto vs OSEBX (t) |
|---|---|---|---|---|---|
| Svak momentum 12-1 (bunn 20 %) | 20 d | IS 2014-01–2018-06 | 4.4 | -1.23 % (-1.2) | -1.78 % (-1.5) |
| Svak momentum 12-1 (bunn 20 %) | 60 d | IS 2014-01–2018-06 | 4.4 | -3.03 % (-1.5) | -3.48 % (-1.3) |
| Svak momentum 12-1 (bunn 20 %) | 20 d | OOS 2018-07–2026-06 | 7.9 | -1.06 % (-1.9) | -1.53 % (-2.2) |
| Svak momentum 12-1 (bunn 20 %) | 60 d | OOS 2018-07–2026-06 | 7.9 | -3.26 % (-3.2) | -3.82 % (-2.8) |
| Høy vol 60d (topp 20 %) | 20 d | IS 2014-01–2018-06 | 5.5 | -0.85 % (-1.1) | -1.40 % (-1.5) |
| Høy vol 60d (topp 20 %) | 60 d | IS 2014-01–2018-06 | 5.5 | -2.65 % (-1.9) | -3.10 % (-1.6) |
| Høy vol 60d (topp 20 %) | 20 d | OOS 2018-07–2026-06 | 9.1 | -0.84 % (-1.2) | -1.31 % (-1.5) |
| Høy vol 60d (topp 20 %) | 60 d | OOS 2018-07–2026-06 | 9.1 | -2.36 % (-1.9) | -2.91 % (-1.7) |
| Rettet emisjon siste 60 d | 20 d | IS | – | ingen data (Newsweb fra 2019) | – |
| Rettet emisjon siste 60 d | 60 d | IS | – | ingen data (Newsweb fra 2019) | – |
| Rettet emisjon siste 60 d | 20 d | OOS 2019-04–2026-06 | 2.6 | -0.24 % (-0.2) | -0.87 % (-0.6) |
| Rettet emisjon siste 60 d | 60 d | OOS 2019-04–2026-06 | 2.6 | -3.41 % (-0.9) | -4.51 % (-1.1) |
| Negativ EBIT TTM | – | – | – | ikke testet: ingen point-in-time EBIT-historikk i repoet | – |

### Konklusjon
- **Ingen av flaggene er robuste.** Alle peker negativt, men bare svak momentum OOS 60d når |t| ≥ 3,1, og ikke i IS.
- Svak momentum: eksperimentell (IS t −1,5 / OOS t −3,2).
- Høy volatilitet: eksperimentell – konsistent negativ (~−2,5 % 60d) i begge perioder, t ≈ −1,9.
- Rettet emisjon: eksperimentell, kun OOS (Newsweb-data fra 2019), −3,4 % 60d men t −0,9, få aksjer per dato (~2,6). Ingen proxy brukt.
- Negativ EBIT: ikke testet. Krever kvartalsvis EBIT med rapportdato (eller 60 d lag) for hele Oslo Børs bakover; finnes ikke i repoet.

Maskinlesbart: logs/red_flag_evidence.json (rådata: logs/red_flags_raw.json).

## ≥2 røde flagg vs nøyaktig 1 flagg (Oslo)

_Kode: signaltool/backtest/red_flags_combo.py. Flagg: momentum bunn 20 % (12-1), høy vol topp 20 % (60d), rettet emisjon siste 60 d. Emisjon telles bare fra 2019-04 (Newsweb), så IS (2014–18) er i praksis «momentum + vol». I OOS har 26 % av ≥2-observasjonene fra 2019-04 et emisjonsflagg. Samme oppsett, HAC t, kostnad 0,4 %._

| Gruppe | Horisont | Periode | Snitt n/dato | Spread vs alle (t) | Netto vs OSEBX (t) | ≥2 minus 1 (t) |
|---|---|---|---|---|---|---|
| ≥2 flagg | 20 d | IS | 2.3 | -0.81 % (-0.6) | -1.21 % (-0.8) | -0.48 % (-0.3) |
| Nøyaktig 1 | 20 d | IS | 5.6 | -0.55 % (-0.9) | -1.10 % (-1.4) |  |
| ≥2 flagg | 60 d | IS | 2.3 | -2.36 % (-0.8) | -2.57 % (-0.8) | -0.73 % (-0.2) |
| Nøyaktig 1 | 60 d | IS | 5.6 | -1.94 % (-1.5) | -2.39 % (-1.2) |  |
| ≥2 flagg | 20 d | OOS | 3.7 | -2.08 % (-2.0) | -2.54 % (-2.1) | -2.17 % (-1.7) |
| Nøyaktig 1 | 20 d | OOS | 11.0 | +0.09 % (0.2) | -0.38 % (-0.6) |  |
| ≥2 flagg | 60 d | OOS | 3.7 | -6.85 % (-3.7) | -7.41 % (-3.4) | -8.08 % (-4.1) |
| Nøyaktig 1 | 60 d | OOS | 11.0 | +1.23 % (1.5) | +0.68 % (0.5) |  |

**Konklusjon:** ≥2 flagg er ikke robust. OOS 60d er sterk: −6,85 % mot alle (t −3,7), −7,41 % netto mot OSEBX (t −3,4) og −8,1 % mot 1 flagg (t −4,1). I IS har den samme fortegn, men t er bare −0,8 (mot 1 flagg −0,2), med ~2,3 aksjer per dato. Den er altså eksperimentell. Den er den sterkeste kandidaten vi har, men IS-testen er svak: den har få aksjer og ikke noe emisjonsflagg. Nøyaktig 1 flagg gir ingen målbar underavkastning OOS (+1,23 %, t 1,5).
