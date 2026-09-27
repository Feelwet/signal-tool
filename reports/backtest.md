# Backtest / historisk validering

_Alle tall er beregnet fra nedlastede data; ingen tall er manuelt satt inn. Resultater er ikke garanti for fremtiden._

## Innsidekjøp-klynger (USA, SEC Form 4) – historisk test
Data: SEC Insider Transactions Data Sets 2022q1–2025q4; 44,867 kjøpsmeldinger (kode P). Klynger funnet: 2016, med kursdata: 987. Enkeltkjøp (sammenligning, tilfeldig utvalg): 700, med kursdata: 186.
Inngang: sluttkurs første handelsdag etter innleveringsdato. Meravkastning = aksje − SPY. Aksjer under $1 utelatt.

| Horisont | Klynger (≥3 innsidere) meravkastning | Enkeltkjøp meravkastning |
|---|---|---|
| 5 handelsdager | n=984, snitt +0.09%, median -0.15%, andel positive 49%, t=0.30 | n=184, snitt +0.13%, median -0.05%, andel positive 49%, t=0.25 |
| 20 handelsdager | n=982, snitt -0.71%, median -1.47%, andel positive 44%, t=-1.37 | n=182, snitt -0.69%, median -1.23%, andel positive 41%, t=-0.76 |
| 60 handelsdager | n=977, snitt -0.54%, median -3.20%, andel positive 43%, t=-0.55 | n=180, snitt -3.30%, median -4.90%, andel positive 39%, t=-2.01 |

Per år (klynger, 20d meravkastning): 2022: n=261, snitt -1.28%, median -1.70%, andel positive 44%, t=-1.08; 2023: n=251, snitt +0.27%, median -0.78%, andel positive 46%, t=0.25; 2024: n=206, snitt -1.66%, median -2.35%, andel positive 38%, t=-1.76; 2025: n=264, snitt -0.33%, median -1.27%, andel positive 45%, t=-0.38

Winsorisert (1/99 %) snitt 20d, klynger: -0.80%

**Forbehold:** Overlevelsesskjevhet (yfinance mangler mange avnoterte aksjer – trolig skjevhet oppover), ingen handelskostnader/spread (viktig for småselskaper), overlappende hendelser gir for optimistiske t-verdier, ticker-endringer kan gi feil kobling. Snitt drives ofte av få ekstreme småselskaper – se median.

## GDELT-oppmerksomhetstopper vs. sektor-ETF/råvare – historisk test
Data: GDELT 1.0 daglige hendelsesfiler 2022-01-01–2026-09-26 (1710 dager). Topp = robust z ≥ 2,5 for temaets artikkelandel (2-dagers snitt vs 60 foregående dager), 10 handelsdagers karantene. Inngang = sluttkurs første handelsdag etter toppdagen. Sammenlignet med alle dager (ubetinget) – p-verdi via bootstrap.

| Tema → instrument | Topper | 5d etter topp | 20d etter topp | Ubetinget 5d / 20d | p (5d / 20d) | 5d FØR topp |
|---|---|---|---|---|---|---|
| mideast_energy → BZ=F | 49 | -0.88% (hit 45%) | -0.54% (hit 41%) | +0.10% / +0.35% | 0.20 / 0.54 | +0.21% (hit 45%) |
| mideast_energy → XLE | 49 | +0.38% (hit 63%) | +1.59% (hit 49%) | +0.33% / +1.41% | 0.92 / 0.85 | -0.11% (hit 53%) |
| conflict_defense → ITA | 35 | +0.45% (hit 60%) | +2.66% (hit 71%) | +0.35% / +1.55% | 0.83 / 0.24 | +0.80% (hit 60%) |
| conflict_defense → RHM.DE | 35 | +1.63% (hit 51%) | +6.41% (hit 68%) | +0.91% / +3.80% | 0.49 / 0.24 | +3.18% (hit 66%) |
| conflict_defense → KOG.OL | 35 | +0.73% (hit 69%) | +5.67% (hit 68%) | +0.83% / +3.31% | 0.90 / 0.20 | +2.31% (hit 74%) |
| shipping_chokepoints → BDRY | 50 | -0.96% (hit 44%) | +0.83% (hit 52%) | +0.15% / +0.91% | 0.31 / 0.97 | +0.08% (hit 50%) |
| risk_off_haven → GLD | 35 | -0.03% (hit 54%) | +1.01% (hit 66%) | +0.38% / +1.61% | 0.36 / 0.48 | +0.39% (hit 57%) |
| sanctions_energy → TTF=F | 41 | -0.84% (hit 48%) | -1.00% (hit 48%) | +0.45% / +2.02% | 0.46 / 0.42 | +3.21% (hit 44%) |

**Tolkning:** p-verdi = andel tilfeldige utvalg av like mange dager med minst like stort avvik fra det ubetingede snittet. p > 0,1 betyr at vi ikke kan skille signalet fra tilfeldigheter. Kolonnen «5d FØR topp» viser om prisen allerede hadde beveget seg (dvs. om nyhetstoppen kom etter markedet).
**Forbehold:** Få uavhengige hendelser; GDELT-dekning og kildeutvalg endres over tid; mange temaer og instrumenter testet (multippel testing – noen «signifikante» funn forventes ved flaks); ingen kostnader.
## Konklusjon (skrevet 2026-09-27 ut fra tabellene over)
- **Innsidekjøp-klynger:** ingen meravkastning mot SPY etter at klyngen ble offentlig (snitt og median ≈ 0 eller negativ, t-verdier nær 0). Signalet vektes derfor lavt i verktøyet og brukes som bekreftelse.
- **GDELT-topper:** ingen av de 8 tema→instrument-parene er statistisk signifikante (alle p > 0,1). Forsvar (ITA, Rheinmetall, Kongsberg) steg mer enn normalt 20 dager etter konflikttopper, men prisene hadde ofte allerede steget de 5 dagene *før* toppen – nyhetsvolumet kommer typisk samtidig med eller etter markedet. GDELT-topper er derfor et *oppmerksomhets*-signal, ikke et bevist forsprang.
- Det betyr at rapportens rangering må leses som «hva bør jeg se nærmere på», ikke som handelssignaler.
