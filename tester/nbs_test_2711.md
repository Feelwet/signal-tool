# Test: Predikerer NBS industriprofitt per bransje aksjeavkastning etter publisering?

Utført 27.11.2026 (Oslo-tid).

**Konklusjon: FLAG.** Ingen av 12 kombinasjoner av signal, horisont og ben består kriteriet: |t| ≥ 3 i hele utvalget OG samme fortegn med |t| ≥ 2 OOS. Høyeste |t| for hele utvalget er 2,64, og OOS er t = 0,89 for den. Profittveksten er derimot tydelig priset inn **før** publiseringen (rho = +0,25, t = 6,7). Dette er etterpåklokskapen: «det var åpenbart smart» gjelder kursene som allerede hadde steget før tallet kom, ikke handel på tallet.

## 1. Metode

**Data (NBS 规模以上工业企业利润, tabell over hovedbransjer, kumulativ YTD profittvekst %).**
- Kilder: stats.gov.cn/sj/zxfb (listesider 0–66, fra des. 2021) + Wayback Machine-kopier av gamle stats.gov.cn/tjsj/zxfb-URL-er (2017–2021).
- Innhentet: **107 publiseringer** fra 26.01.2017 (2016 helår) til 27.11.2026 (jan.–okt. 2026), 41 bransjer per publisering, 4 387 rader (`nbs_releases.csv`, med `source_url` per rad).
- **Hull (2):** jan.–aug. 2019 (publisert ca. 27.09.2019) og jan.–okt. 2020 (ca. 27.11.2020). Disse finnes ikke i Wayback-indeksen, og det gamle nettstedet er nede. Den engelske NBS-siden ga ikke treff via arkivet. Hullene er ikke fylt inn.
- 117 bransjeverdier er ikke tall, fordi NBS oppgir «(注)» når grunnlaget året før var et underskudd. De er utelatt og ikke fylt inn.
- Januar–februar publiseres samlet i mars. «增长X倍» er omregnet til X×100 %.
- Publiseringstid: 09:30 Beijing (02:30 Oslo-tid vintertid). Datoen er lest fra siden selv. For migrerte sider er datoen i URL-en 03.02.2023, ikke publiseringsdatoen.

**Datakontroll (før avkastningstesten):** 30 tilfeldige rader (seed 20261127) ble hentet på nytt med ny forespørsel og tolket med en uavhengig parser (pandas.read_html). Resultatet var **29/30 like**. Den ene avviker fordi Wayback-URL-en ga 404 ved ny henting (2020 helår, publisert 27.01.2021, 印刷业). Det er en hentefeil, ikke et verdiavvik. Kravet ≥ 29/30 er oppfylt. Detaljer: `verify_30.csv`.

**Forhåndsregistrering:** `mapping.csv` ble skrevet og committet (git bf583c6, 27.11.2026 14:17:05 +0100) **før** noen kursdata ble lastet ned. Den har 14 bransjer med likevektet kurv, og ingen proxy brukes to ganger:
elektronikk (SOXX, 005930.KS, MU), ikke-jernholdig smelting (COPX, FCX, NHY.OL, AA), kull (1088.HK, 1898.HK, BTU), olje/gass-utvinning (0883.HK, XLE, EQNR.OL), raffinering (0386.HK), kjemi (600309.SS, BAS.DE, YAR.OL), farmasi (600276.SS, 1093.HK), sement/glass (0914.HK, 3323.HK), stål (0347.HK, 600019.SS), bil (2238.HK, 1211.HK, 0175.HK), elektrisk utstyr/hvitevarer (000333.SZ, 000651.SZ), spesialmaskiner (600031.SS, 000157.SZ), drikke/sprit (600519.SS, 000858.SZ), kraft (0902.HK, 0836.HK). Referanseindekser: ACWI, sekundært MCHI.

**Signaler per publisering:** (a) nivå = YTD profittvekst, (b) akselerasjon = YTD-vekst minus YTD-vekst i forrige innhentede publisering for samme bransje. Merk to ting: jan.–feb. sammenlignes med helåret før, og over de to hullene strekker differansen seg over to måneder.

**Portefølje:** For hver publisering rangeres de 14 bransjene. Topp tredjedel (4) minus bunn tredjedel (4), likevektet (L/S). I tillegg vises topp tredjedel minus ACWI (long-ben).

**Avkastning:** Yahoo justert sluttkurs (dividender og splitt). Epoker er laget med datetime(…, tzinfo=UTC). Første dato er sjekket: alle starter 01.06.2016, unntatt BTU som starter 03.04.2017 (børsnotert på nytt etter konkurs), så den er utelatt fra kurven før dette. Inngang er første sluttkurs strengt etter publiseringsdagen i hvert marked, altså neste handelsdag for alle. Horisonter er 1, 5 og 20 handelsdager. Bare horisonter som er helt lukket er tatt med. Barer datert 27.11.2026 er fjernet. Benchmark måles med egen inngang og utgang.

**Statistikk:** én observasjon per publisering. Standardfeil er dermed klynget på publiseringsdato, og HAC er ikke brukt. 20d-horisonten overlapper nesten ikke, fordi publiseringene kommer omtrent hver 21. handelsdag. IS = publiseringer 2017–2021, OOS = 2022–2026.

## 2. Resultater

Kolonnene IS og OOS viser n / snitt / t. Kriterium: |t| ≥ 3 i hele utvalget og |t| ≥ 2 OOS med samme fortegn.

| Signal | Horisont | Ben | n | Snitt | Treff | t | IS | OOS | Status |
|---|---|---|---|---|---|---|---|---|---|
| nivå (YTD-vekst) | 1d | L/S topp−bunn | 106 | -0,10 % | 45 % | -0,70 | 53 / +0,26 % / +1,30 | 53 / -0,47 % / -2,35 | FLAG |
| nivå (YTD-vekst) | 1d | topp vs ACWI | 106 | +0,08 % | 49 % | +0,66 | 53 / +0,32 % / +1,74 | 53 / -0,15 % / -0,89 | FLAG |
| nivå (YTD-vekst) | 5d | L/S topp−bunn | 106 | +0,22 % | 59 % | +0,66 | 53 / +0,70 % / +1,29 | 53 / -0,26 % / -0,65 | FLAG |
| nivå (YTD-vekst) | 5d | topp vs ACWI | 106 | +0,50 % | 56 % | +1,75 | 53 / +1,05 % / +2,63 | 53 / -0,06 % / -0,15 | FLAG |
| nivå (YTD-vekst) | 20d | L/S topp−bunn | 106 | +0,79 % | 52 % | +1,28 | 53 / +0,92 % / +1,03 | 53 / +0,65 % / +0,77 | FLAG |
| nivå (YTD-vekst) | 20d | topp vs ACWI | 106 | +0,81 % | 55 % | +1,59 | 53 / +1,58 % / +2,36 | 53 / +0,05 % / +0,06 | FLAG |
| akselerasjon (ΔYTD) | 1d | L/S topp−bunn | 105 | -0,01 % | 49 % | -0,07 | 52 / -0,07 % / -0,42 | 53 / +0,06 % / +0,27 | FLAG |
| akselerasjon (ΔYTD) | 1d | topp vs ACWI | 105 | +0,11 % | 48 % | +0,82 | 52 / +0,11 % / +0,69 | 53 / +0,11 % / +0,50 | FLAG |
| akselerasjon (ΔYTD) | 5d | L/S topp−bunn | 105 | +0,35 % | 55 % | +1,21 | 52 / +0,63 % / +1,69 | 53 / +0,07 % / +0,16 | FLAG |
| akselerasjon (ΔYTD) | 5d | topp vs ACWI | 105 | +0,76 % | 61 % | +2,64 | 52 / +1,16 % / +2,90 | 53 / +0,37 % / +0,89 | FLAG |
| akselerasjon (ΔYTD) | 20d | L/S topp−bunn | 105 | +0,24 % | 51 % | +0,44 | 52 / +0,72 % / +1,13 | 53 / -0,24 % / -0,28 | FLAG |
| akselerasjon (ΔYTD) | 20d | topp vs ACWI | 105 | +0,65 % | 50 % | +1,20 | 52 / +1,43 % / +2,00 | 53 / -0,12 % / -0,15 | FLAG |

**Etterpåklokskap: hvor mye var priset før publisering?** Gjennomsnittlig tverrsnitts-Spearman per publisering mellom profittsignalet og kurvavkastningen:

| Test | n | Snitt rho | Andel > 0 | t |
|---|---|---|---|---|
| akselerasjon vs 20d ETTER | 105 | -0,011 | 51 % | -0,41 |
| akselerasjon vs kurs mellom publiseringer (før) | 106 | -0,017 | 46 % | -0,53 |
| nivå vs 20d ETTER | 105 | +0,050 | 53 % | +1,60 |
| nivå vs YTD-kurs før publisering | 106 | +0,247 | 73 % | +6,73 |

Tolkning: bransjer med høy YTD-profittvekst hadde allerede klart høyere aksjeavkastning i samme periode, **før** tallet ble publisert (rho ≈ +0,25, t ≈ 6,7). Etter publisering faller sammenhengen til rho ≈ +0,05 (t ≈ 1,6). Akselerasjonen viser ingen sammenheng, verken før eller etter.

## 3. Store bevegelser (≥ 40 % på 20d)

22 tilfeller. Alle er kontrollert mot Tencent (fremjustert, qfq) der tickeren finnes der. Avviket er 0,00 prosentpoeng i 20 av 20 kontrollerbare tilfeller. NHY.OL og 005930.KS finnes ikke hos Tencent og er ikke kontrollert. Ingen tickere er avnotert: alle har data til november 2026. Merk at Tencent ikke nødvendigvis er en helt uavhengig kilde.

| Ticker | Publisering | Inngang → utgang | Yahoo 20d | Tencent 20d |
|---|---|---|---|---|
| SOXX | 2026-03-27 | 2026-03-30 → 2026-04-28 | +41,62 % | +41,62 % |
| 005930.KS | 2026-04-27 | 2026-04-28 → 2026-05-29 | +42,79 % | ikke tilgjengelig |
| MU | 2025-12-27 | 2025-12-29 → 2026-01-28 | +47,87 % | +47,87 % |
| MU | 2026-03-27 | 2026-03-30 → 2026-04-28 | +56,71 % | +56,71 % |
| MU | 2026-04-27 | 2026-04-28 → 2026-05-27 | +84,10 % | +84,10 % |
| FCX | 2020-03-27 | 2020-03-30 → 2020-04-28 | +42,95 % | +42,95 % |
| NHY.OL | 2020-10-27 | 2020-10-28 → 2020-11-25 | +41,85 % | ikke tilgjengelig |
| AA | 2020-10-27 | 2020-10-28 → 2020-11-25 | +64,81 % | +64,81 % |
| 1898.HK | 2021-01-27 | 2021-01-28 → 2021-03-01 | +44,30 % | +44,30 % |
| BTU | 2020-09-27 | 2020-09-28 → 2020-10-26 | -50,96 % | -50,96 % |
| BTU | 2020-12-27 | 2020-12-28 → 2021-01-27 | +94,58 % | +94,58 % |
| BTU | 2021-03-26 | 2021-03-29 → 2021-04-27 | +53,04 % | +53,04 % |
| BTU | 2021-06-27 | 2021-06-28 → 2021-07-27 | +46,78 % | +46,78 % |
| BTU | 2022-01-27 | 2022-01-28 → 2022-02-28 | +54,41 % | +54,41 % |
| BTU | 2025-08-27 | 2025-08-28 → 2025-09-26 | +45,67 % | +45,67 % |
| XLE | 2020-10-27 | 2020-10-28 → 2020-11-25 | +42,08 % | +42,08 % |
| 0347.HK | 2025-06-27 | 2025-06-30 → 2025-07-29 | +49,09 % | +49,09 % |
| 1211.HK | 2020-09-27 | 2020-09-28 → 2020-10-30 | +46,90 % | +46,90 % |
| 0175.HK | 2020-10-27 | 2020-10-28 → 2020-11-25 | +44,03 % | +44,03 % |
| 0902.HK | 2021-07-27 | 2021-07-28 → 2021-08-25 | +57,20 % | +57,20 % |
| 0902.HK | 2021-11-26 | 2021-11-29 → 2021-12-28 | +50,72 % | +50,72 % |
| 0836.HK | 2021-07-27 | 2021-07-28 → 2021-08-25 | +54,75 % | +54,75 % |

## 4. Vurdering: FLAG

Følgende holdt ikke:
- **Ingen kombinasjon når |t| ≥ 3 i hele utvalget.**
- **Akselerasjon, topp vs ACWI, 5d** er nærmest: t = 2,64 for hele utvalget og 2,90 IS, men bare 0,89 OOS.
- **Nivå, topp vs ACWI, 5d og 20d** har IS t = 2,63 og 2,36, mens OOS er omtrent 0. Effekten forsvant etter 2021, som er typisk for utvalgsspesifikk støy eller et regime: råvaresyklusen 2020–2021.
- **Nivå, L/S, 1d** har OOS t = −2,35, altså motsatt fortegn av IS.
- Long-benet mot ACWI måler i stor grad Kina- og råvarebeta, ikke informasjon i NBS-tallet. L/S er det rene målet, og det har |t| ≤ 1,3 for alle horisonter.

**Hva siden kan si:** NBS-tallet beskriver hvilke bransjer som tjente penger. Kursene i disse bransjene hadde i stor grad steget allerede før publiseringen. Vi har ikke funnet bevis for at det lønner seg å kjøpe etter publiseringen. Tekster som «bra for kobber» eller «kjøp elektronikk» har ikke dekning i denne testen.

**Svakheter:** 107 publiseringer, med 2 hull. 14 bransjer og proxyer er valgt av oss: de fleste er kinesiske A/H-aksjer, men noen er globale (SOXX, MU, XLE). Det er ingen transaksjonskostnader. Proxy-utvalget er ikke validert mot bransjenes faktiske profittandel.

Filer: `nbs_releases.csv`, `verify_30.csv`, `mapping.csv` (+ sha256, git), `prices/`, `basket_returns.csv`, `results.csv`, `hindsight.csv`, `bigmoves_xcheck.csv`, `analyze.py`.
