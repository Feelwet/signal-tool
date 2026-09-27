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