## Historisk sjekk av Kjøp-kandidat-reglene
_Beregnet 2026-09-27 fra nedlastede data (signaltool/backtest/categories_check.py). Ingen tall er satt inn manuelt._

Reglenes kursdel (kurs over 50-dagers snitt, 20d-avkastning bedre enn SPY, ikke strukket, ikke ≥ 20 % krasj, kurs ≥ $1) er brukt på historiske hendelser med data kjent på hendelsesdagen. Inngang = sluttkurs første handelsdag etter hendelsen. Meravkastning = aksje − SPY.

Hendelser: A) 2016 innsidekjøp-klynger (SEC 2022–2025, ledelse/styre), med kursdata: 918. B) 344 store DoD-kontrakter (USAspending ≥ $100M, 2022–, koblet til børsnoterte leverandører, 30 d karantene), med kursdata: 300. C) begge innen 30 dager for samme ticker («≥ 2 uavhengige signaltyper»): 3, med kursdata: 2.

### A) Innsidekjøp-klynger
| Gruppe | 20 handelsdager (meravkastning vs SPY) | 60 handelsdager |
|---|---|---|
| Alle hendelser | n=918, snitt +0.10%, median -1.20%, andel positive 44%, t=0.17 | n=918, snitt +1.49%, median -2.82%, andel positive 44%, t=1.14 |
| Oppfyller kurs-/flaggreglene for Kjøp (kursbekreftelse, ikke strukket, ingen krasj/penny) | n=117, snitt +0.91%, median -1.00%, andel positive 47%, t=0.89 | n=117, snitt +3.52%, median +1.60%, andel positive 56%, t=1.97 |
| «Hold-lignende» (kursbekreftelse, men strukket) | n=89, snitt +3.45%, median +0.22%, andel positive 52%, t=1.36 | n=89, snitt +11.26%, median +1.22%, andel positive 53%, t=2.10 |
| Oppfyller IKKE kursbekreftelse / har flagg | n=712, snitt -0.45%, median -1.71%, andel positive 43%, t=-0.66 | n=712, snitt -0.06%, median -4.07%, andel positive 41%, t=-0.04 |

### B) Store DoD-kontrakter
| Gruppe | 20 handelsdager (meravkastning vs SPY) | 60 handelsdager |
|---|---|---|
| Alle hendelser | n=300, snitt +0.70%, median +0.97%, andel positive 55%, t=1.39 | n=300, snitt -0.50%, median -0.57%, andel positive 48%, t=-0.58 |
| Oppfyller kurs-/flaggreglene for Kjøp (kursbekreftelse, ikke strukket, ingen krasj/penny) | n=101, snitt +0.94%, median +1.32%, andel positive 59%, t=1.16 | n=101, snitt -1.72%, median -0.22%, andel positive 50%, t=-1.08 |
| «Hold-lignende» (kursbekreftelse, men strukket) | n=9, snitt +1.41%, median +0.60%, andel positive 56%, t=0.28 | n=9, snitt +5.34%, median +0.13%, andel positive 56%, t=0.78 |
| Oppfyller IKKE kursbekreftelse / har flagg | n=190, snitt +0.53%, median +0.73%, andel positive 53%, t=0.85 | n=190, snitt -0.12%, median -0.81%, andel positive 47%, t=-0.12 |

### C) Kontrakt + innsideklynge (to uavhengige typer)
| Gruppe | 20 handelsdager (meravkastning vs SPY) | 60 handelsdager |
|---|---|---|
| Alle hendelser | n=2, snitt +7.26%, median +7.26%, andel positive 50%, t=0.96 | n=2, snitt +2.63%, median +2.63%, andel positive 50%, t=0.59 |
| Oppfyller kurs-/flaggreglene for Kjøp (kursbekreftelse, ikke strukket, ingen krasj/penny) | n=1 | n=1 |
| «Hold-lignende» (kursbekreftelse, men strukket) | n=0 | n=0 |
| Oppfyller IKKE kursbekreftelse / har flagg | n=1 | n=1 |

**Forbehold:** Newsweb-kontrakter, tema/olje-bekreftelse, shortdata og likviditet finnes ikke historisk her og er ikke testet. USAspending-dato (obligasjonsdato) er ikke alltid samme dag som offentlig kunngjøring. Overlevelsesskjevhet (avnoterte aksjer mangler), ingen kurtasje/spread, overlappende hendelser, og flere grupper sammenlignet (multippel testing). t-verdier under ca. 2 betyr at forskjellen ikke kan skilles fra tilfeldigheter.

## Tolkning (skrevet 2026-09-27 ut fra tabellene over)
- **Innsidekjøp-klynger:** klynger der kursreglene også var oppfylt gjorde det noe bedre enn klynger uten kursbekreftelse (60 d: snitt +3,5 % mot −0,1 %), men medianen på 20 d er fortsatt negativ, og t-verdiene ligger rundt 1–2. Ingen av gruppene er signifikante når man tar hensyn til at flere grupper er sammenlignet. «Hold-lignende» (strukket) klynger hadde høyest snitt, men det drives av få store vinnere (median +1,2 %). Dette ser mer ut som en generell momentumeffekt enn et forsprang fra selve signalet.
- **Store DoD-kontrakter:** omtrent ingen meravkastning (snitt +0,7 % på 20 d, −0,5 % på 60 d). Kursfilteret endrer lite.
- **To uavhengige typer (kontrakt + innsideklynge):** bare 3 tilfeller på 4+ år (2 med kursdata). Altfor få til å si noe. Det bekrefter at Kjøp-kandidater vil være sjeldne.
- **Konklusjon:** reglene er **ikke bevist å slå markedet**. Kursbekreftelsen ser ut til å luke bort noen av de svakeste tilfellene, men det kan være tilfeldig. Fremoverloggen («Treffsikkerhet») er den ærlige testen.
