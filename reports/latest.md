# Signalrapport 2026-09-28
_Generert 2026-09-28 13:53 (norsk tid). GDELT-data til og med 2026-09-27. Kjøretid 431 s._

**Ikke finansiell rådgivning.** Dette er et automatisk informasjonsverktøy basert på offentlige data og enkle, transparente regler. Signaler kan være feil, forsinkede eller allerede priset inn. Gjør egne vurderinger.

## 1. Topp fremvoksende temaer

Score 0–5 = vektet snitt av positive avvik (robuste z-scorer) mot temaets egen historikk. Se metode nederst.

| # | Tema | Score | Sterkeste drivere |
|---|---|---|---|
| 1 | Valg og politisk ustabilitet | **1.46** | gdelt_events +2.3, prediction_mkts +2.0, gdelt_urls +1.6 |
| 2 | Midtøsten / Iran / Gulfen – risiko for oljeforsyning | **1.17** | physical_oil +4.3, prediction_mkts +2.3, gdelt_urls +1.7 |
| 3 | Sanksjoner, russisk energi og europeisk gass | **1.13** | physical_oil +4.3, prediction_mkts +2.0, gdelt_events +1.5 |
| 4 | Bred risikoaversjon / trygge havner | **0.54** | gdelt_urls +1.8, gdelt_tone +0.3, price_volume +0.1 |
| 5 | Europa/Russland-konflikt og forsvarsutgifter | **0.48** | prediction_mkts +2.2, gdelt_events +0.6, gdelt_tone +0.4 |
| 6 | Flaskehalser for skipsfart (Rødehavet, Suez, Taiwanstredet, Panama) | **0.21** | prediction_mkts +0.8, price_volume +0.4, gdelt_events +0.1 |
| 7 | Mat, korn og gjødsel – forsyningssjokk | **0.17** | price_volume +0.9, gdelt_events -0.2, sec_8k -0.7 |
| 8 | Kina/Taiwan-spenning, sjeldne jordarter og halvledere | **0.09** | gdelt_urls +0.2, prediction_mkts +0.2, price_volume -0.0 |
| 9 | Toll, handelskrig og eksportkontroll | **0.03** | gdelt_tone +0.1, price_volume +0.1, gdelt_urls -0.6 |
| 10 | Nordisk/arktisk sikkerhet og undersjøisk infrastruktur | **0.03** | gdelt_tone +0.2, gdelt_urls -0.0, price_volume -0.2 |

### Valg og politisk ustabilitet — score 1.46

**Hvorfor dette kan bety noe:** Valg, kupp og regjeringskriser endrer finans-, energi- og reguleringspolitikk. Effekten er landspesifikk: lands-ETFer, valuta og innenlandske banker er de mest direkte eksponeringene. Volatiliteten (VIX) stiger gjerne inn mot omstridte utfall.

- **Ved eskalering:** Lands-ETF/valuta svekkes ved ustabilitet; volatilitet opp.
- **Ved nedtrapping:** Klare utfall gir ofte lettelsesrally.
- **Hva kan gå galt:** Svært støyende; prediksjonsmarkeder priser som regel utfallet før nyhetsflyten topper seg.

| Komponent | Score (z) | Detalj |
|---|---|---|
| GDELT hendelser (andel konflikt-/tiltakshendelser i temaets land) | 2.27 | siste 2 dager 0.943% av alle GDELT-artikler vs median 0.637% (60 dager) |
| GDELT nyhetsvolum (andel artikler med tema-nøkkelord) | 1.61 | 2.22% av kilde-URLer vs median 1.70% |
| GDELT tone (mer negativ enn normalt) | -0.27 | tone -3.29 vs median -3.51 (lavere = mer negativ) |
| RSS-overskrifter fra store medier | – | 44 overskrifter i går; baseline bygges opp (trenger ≥7 dager lagret historikk) |
| Prediksjonsmarkeder (største 1-ukes bevegelse) | 2.00 | største 1-ukes endring 10.0 prosentpoeng blant 31 likvide markeder (score = pp/5) |
| Kurs/volum-avvik i temaets aksjer | 0.41 | snitt volum-z (5d) 0.26, snitt |5d avkastning-z| 0.57 over 8 instrumenter |

**Prediksjonsmarkeder (Polymarket, markedets sannsynlighet):**

- [Will the Republicans win the Maine Senate race in 2026?](https://polymarket.com/event/maine-senate-election-winner): 40% (1d 4.0 pp, 1u 10.0 pp, volum 24t $24,047)
- [Will Luiz Inácio Lula da Silva finish in second place in the first round of the 2026 Brazilian presidential election?](https://polymarket.com/event/brazil-presidential-election-first-round-2nd-place): 23% (1d -1.7 pp, 1u -7.2 pp, volum 24t $20,216)
- [Will Flávio Bolsonaro finish in second place in the first round of the 2026 Brazilian presidential election?](https://polymarket.com/event/brazil-presidential-election-first-round-2nd-place): 76% (1d 0.5 pp, 1u 6.5 pp, volum 24t $24,490)
- [Will Lula win the most votes in the first round of the 2026 Brazil presidential election?](https://polymarket.com/event/brazil-presidential-election-first-round-winner): 74% (1d 1.0 pp, 1u 6.5 pp, volum 24t $19,757)
- [Will Flavio Bolsonaro win the most votes in the first round of the 2026 Brazil presidential election?](https://polymarket.com/event/brazil-presidential-election-first-round-winner): 26% (1d 0.5 pp, 1u -6.0 pp, volum 24t $19,430)

| Ticker | Rolle | 1d | 5d | 20d | 5d-z | Volum-z (5d) |
|---|---|---|---|---|---|---|
| SPY | vinner ved eskalering | +0.5% | +1.3% | +0.3% | 0.5 | -0.0 |
| FEZ | vinner ved eskalering | +0.7% | +0.9% | -3.6% | 0.2 | 0.7 |
| EWZ | vinner ved eskalering | -0.2% | -1.9% | +3.0% | -0.7 | 0.7 |
| EWW | vinner ved eskalering | +1.1% | +0.0% | -5.0% | -0.1 | 0.1 |
| EWG | vinner ved eskalering | +0.9% | +0.3% | -5.2% | 0.1 | 0.5 |
| DNB.OL | vinner ved eskalering | +2.2% | +2.1% | +1.6% | 0.8 | -0.5 |
| USDNOK=X | råvare/FX | -0.1% | +1.1% | +1.6% | 0.9 | – |
| EURUSD=X | råvare/FX | -0.0% | -0.9% | -1.9% | -1.1 | – |

**Siste overskrifter:**

- [Le Pen hails 'victory' as French far right secures record 14 seats in Senate](https://www.france24.com/en/video/20260928-le-pen-hails-victory-as-french-far-right-secures-record-14-seats-in-senate) — _France24_
- [‘Counting window’ seen as high-risk time for Trump to cast doubt on midterm results / First Thing](https://www.theguardian.com/us-news/2026/sep/28/first-thing-counting-window-risk-trump-midterm-results) — _Guardian World_
- [Indian university suspends classes amid violent protests over alleged rape](https://www.aljazeera.com/news/2026/9/28/indian-university-suspends-classes-amid-violent-protests-over-alleged-rape?traffic_source=rss) — _Al Jazeera_
- [Serbia's populist President Vucic resigns to run for PM](https://www.france24.com/en/video/20260928-serbia-s-populist-president-vucic-resigns-to-run-for-pm) — _France24_
- [France’s far-right National Rally surges in partial Senate elections](https://www.theguardian.com/world/2026/sep/28/french-election-2026-far-right-senate-elections) — _Guardian World_
- [Tensions run high in Northern Ireland after march blocked from historic flashpoint](https://www.france24.com/en/video/20260928-tensions-run-high-in-northern-ireland-after-march-blocked-from-historic-flashpoint) — _France24_

### Midtøsten / Iran / Gulfen – risiko for oljeforsyning — score 1.17

**Hvorfor dette kan bety noe:** Omtrent en femdel av verdens olje og mye LNG går gjennom Hormuzstredet. Militær eskalering med Iran, Israel eller Gulf-statene gir en risikopremie i Brent, gagner produsenter utenfor regionen (Equinor, Aker BP, Vår Energi, amerikanske oljeselskaper) og tankrederier (lengre ruter, høyere rater), og rammer flyselskaper med høye drivstoffkostnader.

- **Ved eskalering:** Brent opp, tankrederier opp, europeiske E&P-selskaper opp, flyselskaper ned. Følg Polymarket-markedene om våpenhvile/blokade.
- **Ved nedtrapping:** Risikopremien forsvinner raskt: olje- og tankaksjer kan gi tilbake ukers gevinst på dager.
- **Hva kan gå galt:** OPECs ledige kapasitet og strategiske lagre demper topper; markedet kan allerede prise en stor premie.

| Komponent | Score (z) | Detalj |
|---|---|---|
| GDELT hendelser (andel konflikt-/tiltakshendelser i temaets land) | -0.56 | siste 2 dager 1.128% av alle GDELT-artikler vs median 1.416% (60 dager) |
| GDELT nyhetsvolum (andel artikler med tema-nøkkelord) | 1.73 | 6.02% av kilde-URLer vs median 4.44% |
| GDELT tone (mer negativ enn normalt) | -0.12 | tone -5.19 vs median -5.26 (lavere = mer negativ) |
| RSS-overskrifter fra store medier | – | 69 overskrifter i går; baseline bygges opp (trenger ≥7 dager lagret historikk) |
| Google Trends søkeinteresse | -1.20 | snitt siste 3 dager 6.1 vs median 8.8 (søk: Iran, Strait of Hormuz, oil price, OPEC) |
| SEC 8-K-meldinger som nevner temaet | -0.41 | 31 8-K siste uke vs median 46/uke (søk "Middle East") |
| Prediksjonsmarkeder (største 1-ukes bevegelse) | 2.32 | største 1-ukes endring 11.6 prosentpoeng blant 26 likvide markeder (score = pp/5) |
| Kurs/volum-avvik i temaets aksjer | 0.63 | snitt volum-z (5d) 0.43, snitt |5d avkastning-z| 0.83 over 12 instrumenter |
| OFAC-sanksjonsvedtak siste 14 dager | 0.00 | 2 relevante sanksjonsvedtak (designations) siste 14 dager |
| Fysisk oljemarked (crack spread, Brent–WTI, z mot 1 år) | 4.27 | 3-2-1 crack spread (USD/fat) – raffinerimargin: 60.45 (z=+0.9); Brent–WTI (USD/fat) – sjøbåren vs. amerikansk olje: 4.82 (z=+4.3) |

**Prediksjonsmarkeder (Polymarket, markedets sannsynlighet):**

- [US x Iran ceasefire continues through September 30?](https://polymarket.com/event/us-iran-ceasefire-continues-throughptptpt): 96% (1d 6.6 pp, 1u 11.6 pp, volum 24t $391,522)
- [Saudi Oil Pipeline (East-West) restarts by September 30?](https://polymarket.com/event/saudi-oil-pipeline-east-west-restarts-byptptpt): 22% (1d 4.0 pp, 1u -10.0 pp, volum 24t $48,481)
- [US announces end of Iranian blockade by October 31, 2026?](https://polymarket.com/event/us-announces-end-of-iranian-blockade-byptptpt-20260713152715080): 30% (1d 3.0 pp, 1u -8.0 pp, volum 24t $92,160)
- [US announces end of Iranian blockade by December 31, 2026?](https://polymarket.com/event/us-announces-end-of-iranian-blockade-byptptpt-20260713152715080): 57% (1d 0.7 pp, 1u -6.8 pp, volum 24t $55,489)
- [Will Iran target Kuwait by September 30, 2026?](https://polymarket.com/event/will-iran-target-kuwait-byptptpt-20260907): 14% (1d -5.5 pp, 1u -6.0 pp, volum 24t $18,252)

| Ticker | Rolle | 1d | 5d | 20d | 5d-z | Volum-z (5d) |
|---|---|---|---|---|---|---|
| XLE | vinner ved eskalering | -0.9% | -3.0% | +0.2% | -1.3 | 1.2 |
| XOM | vinner ved eskalering | -1.0% | -1.8% | +2.6% | -0.8 | -0.4 |
| CVX | vinner ved eskalering | -0.6% | -2.4% | +2.3% | -1.0 | 0.2 |
| FRO | vinner ved eskalering | -0.5% | -7.2% | +16.4% | -1.4 | 1.6 |
| DHT | vinner ved eskalering | +0.5% | -6.4% | +12.6% | -1.5 | 0.8 |
| STNG | vinner ved eskalering | +0.7% | -6.5% | +5.2% | -1.4 | 0.6 |
| EQNR.OL | vinner ved eskalering | +1.2% | +1.2% | +2.5% | -0.0 | -0.9 |
| AKRBP.OL | vinner ved eskalering | +1.1% | +0.2% | -1.4% | -0.2 | -0.8 |
| VAR.OL | vinner ved eskalering | +2.0% | +0.0% | +4.9% | -0.3 | -1.3 |
| HAFNI.OL | vinner ved eskalering | +3.3% | -8.3% | +10.7% | -1.9 | 3.1 |
| BZ=F | råvare/FX | -3.7% | +0.1% | +12.5% | -0.1 | 0.4 |
| CL=F | råvare/FX | +3.5% | -0.2% | +14.6% | -0.2 | 0.5 |
| JETS | taper | +1.8% | +2.7% | -1.3% | 0.5 | 1.3 |
| NAS.OL | taper | -0.8% | +0.3% | -5.8% | 0.1 | -0.4 |

**Siste overskrifter:**

- [Police 'investigate Iran link' to suspected bomb plot at UK air base used by U.S.](https://www.cnbc.com/2026/09/28/iran-war-trump-hormuz.html) — _CNBC World_
- [Tom Kean Jr. backs Trump on Iran and tariffs, if not local issues - Inquirer.com](https://news.google.com/rss/articles/CBMilAFBVV95cUxPLTdzMTNPWDkxZDE5eFdRcUEtZ2plaFZKWnNMbF9TMG81U01YM3BySFUzMk1PQ05vTXBKb3A0NTZLRHUxSndiUnFCcnJ3ZVRaQ3ZoejRvcTVPdVJ4WUZ0NTVaNVAzZG1XZTR5RmJQTUw0Ynk1WTFXWldBaDlxVUdjOVViSEVpVFBEWFBnWXJpeV9xMllr?oc=5) — _Google News: tariffs_
- [European Gas Prices Rally on U.S.-Iran Stalemate](https://oilprice.com/Latest-Energy-News/World-News/European-Gas-Prices-Rally-on-US-Iran-Stalemate.html) — _OilPrice_
- [Israel does not have right to close UK consulate in Jerusalem, Foreign Office advised](https://www.theguardian.com/politics/2026/sep/28/israel-no-right-close-jerusalem-uk-consulate-foreign-office-advised) — _Guardian World_
- [Bond sell-off deepens as oil rises above $108](https://www.ft.com/content/d751ad99-531d-4990-9a4c-ee89a9fc1b2d?syn-25a6b1a6=1) — _FT World_
- [Why Israel fears settlement sanctions are just the beginning - The Irish Times](https://news.google.com/rss/articles/CBMiuAFBVV95cUxQeWM5c05wNll5YkFHM1JzRWdfQ1Z2Mm5OVEVjeXZUS1RfQ09QaERScjVIeTRIU2FVdTl3WXZMX0hRUjltMzRybjJhYi1TZml2T1pwMHYzQ0lmbXJYOXVvbEpjYVA2QTlvUHpGT1VuTDM3dWllLS05TnF3NWtMUEMzenVabGdZMWd0b01NTG5mLWJtZmZ3ckc0ejN1QUJfRzA3Wk1OOTRUZlh4RnY3cUszVEp3cG9aQkdf?oc=5) — _Google News: sanctions_

**Siste 8-K som nevner temaet:** [Vertiv Holdings Co  (VRT)  (CIK 0001674101)](https://www.sec.gov/Archives/edgar/data/1674101/000162828026063311/0001628280-26-063311-index.htm); [LIGAND PHARMACEUTICALS INC  (LGND, LGNDZ, LGNXZ, LGNYZ, LGNZZ)  (CIK 0000886163)](https://www.sec.gov/Archives/edgar/data/886163/000088616326000050/0000886163-26-000050-index.htm); [Select Water Solutions, Inc.  (WTTR)  (CIK 0001693256)](https://www.sec.gov/Archives/edgar/data/1693256/000110465926110440/0001104659-26-110440-index.htm)

### Sanksjoner, russisk energi og europeisk gass — score 1.13

**Hvorfor dette kan bety noe:** Nye sanksjoner mot russisk olje/gass, håndheving av pristak mot «skyggeflåten» eller sekundærsanksjoner mot kjøpere strammer inn tilbudet og endrer handelsruter. Norge er Europas største leverandør av rørgass, så Equinor tjener på høyere europeiske gasspriser; seriøse tankrederier tjener på lengre seilaser.

- **Ved eskalering:** Europeisk gasspris og Equinor opp; produkttankere opp.
- **Ved nedtrapping:** Lettelser i sanksjonene (f.eks. fredsavtale) vil presse gasspris og Equinor ned.
- **Hva kan gå galt:** Sanksjoner håndheves ofte dårlig; milde vintre og fulle lagre dominerer gassprisen.

| Komponent | Score (z) | Detalj |
|---|---|---|
| GDELT hendelser (andel konflikt-/tiltakshendelser i temaets land) | 1.55 | siste 2 dager 0.428% av alle GDELT-artikler vs median 0.258% (60 dager) |
| GDELT nyhetsvolum (andel artikler med tema-nøkkelord) | -0.55 | 0.16% av kilde-URLer vs median 0.25% |
| GDELT tone (mer negativ enn normalt) | 0.55 | tone -5.39 vs median -4.90 (lavere = mer negativ) |
| RSS-overskrifter fra store medier | – | 89 overskrifter i går; baseline bygges opp (trenger ≥7 dager lagret historikk) |
| Google Trends søkeinteresse | -1.57 | snitt siste 3 dager 22.3 vs median 32.8 (søk: sanctions, gas price, shadow fleet) |
| SEC 8-K-meldinger som nevner temaet | -0.88 | 87 8-K siste uke vs median 127/uke (søk "sanctions") |
| Prediksjonsmarkeder (største 1-ukes bevegelse) | 2.00 | største 1-ukes endring 10.0 prosentpoeng blant 3 likvide markeder (score = pp/5) |
| Kurs/volum-avvik i temaets aksjer | 0.54 | snitt volum-z (5d) 0.35, snitt |5d avkastning-z| 0.73 over 10 instrumenter |
| OFAC-sanksjonsvedtak siste 14 dager | -2.02 | 2 relevante sanksjonsvedtak (designations) siste 14 dager |
| Fysisk oljemarked (crack spread, Brent–WTI, z mot 1 år) | 4.27 | 3-2-1 crack spread (USD/fat) – raffinerimargin: 60.45 (z=+0.9); Brent–WTI (USD/fat) – sjøbåren vs. amerikansk olje: 4.82 (z=+4.3) |

**Prediksjonsmarkeder (Polymarket, markedets sannsynlighet):**

- [Saudi Oil Pipeline (East-West) restarts by September 30?](https://polymarket.com/event/saudi-oil-pipeline-east-west-restarts-byptptpt): 22% (1d 4.0 pp, 1u -10.0 pp, volum 24t $48,481)
- [Saudi Oil Pipeline (East-West) restarts by October 31?](https://polymarket.com/event/saudi-oil-pipeline-east-west-restarts-byptptpt): 76% (1d 8.0 pp, 1u -0.5 pp, volum 24t $47,936)
- [Saudi Oil Pipeline (East-West) restarts by October 15?](https://polymarket.com/event/saudi-oil-pipeline-east-west-restarts-byptptpt): 56% (1d 11.0 pp, 1u 0.0 pp, volum 24t $45,013)

| Ticker | Rolle | 1d | 5d | 20d | 5d-z | Volum-z (5d) |
|---|---|---|---|---|---|---|
| LNG | vinner ved eskalering | -2.8% | +0.1% | -4.4% | -0.1 | 0.5 |
| FRO | vinner ved eskalering | -0.5% | -7.2% | +16.4% | -1.4 | 1.6 |
| DHT | vinner ved eskalering | +0.5% | -6.4% | +12.6% | -1.5 | 0.8 |
| EQNR.OL | vinner ved eskalering | +1.2% | +1.2% | +2.5% | -0.0 | -0.9 |
| OKEA.OL | vinner ved eskalering | +1.2% | +4.5% | +4.8% | 0.4 | -1.0 |
| HAFNI.OL | vinner ved eskalering | +3.3% | -8.3% | +10.7% | -1.9 | 3.1 |
| FRO.OL | vinner ved eskalering | +2.4% | -5.0% | +14.3% | -1.1 | 0.3 |
| TTF=F | råvare/FX | +2.5% | +0.8% | +10.3% | -0.1 | -0.3 |
| NG=F | råvare/FX | -2.1% | +10.3% | +8.3% | 0.6 | -0.9 |
| BZ=F | råvare/FX | -3.7% | +0.1% | +12.5% | -0.1 | 0.4 |

**Siste overskrifter:**

- [EU imposes sanctions against the head of Tatarstan - 1News.az](https://news.google.com/rss/articles/CBMimAFBVV95cUxNdm51RFdKOWJ6SS1mYmwySHhxVnhCSkZ4MjJ0b1U5MDVzV2JnRVdTb2xxTHpzdXNRbGhPVFhpME5ZWnFuOTJ5Vnh5RWtaSy1JUF9CZDJSUWJpRURCeldoRzlOd3FuMVdXMXI2cC00a3ppQTdndVhQc3BXRFBzWVplUFVBRU5LSGNHb05fekNxMGJCY0VTQmk2cQ?oc=5) — _Google News: sanctions_
- [Lithuania imposes national sanctions on Russian billionaires Usmanov, Fridman - LRT](https://news.google.com/rss/articles/CBMiwwFBVV95cUxNc0hKc2lsenhnaXpnMlBTZXd1czBrMUdjSWhGaW5YMDBrdVE0VHV1eFg1UEhlZlh4R0laeDQ1M21FTlRxM0t6YndoYm1RV3ZOazY0djZxQWI4Qzh6RW1XSzd0bzJEQVhONElvMTN2c3FOZjFSMmZpVk1UelBsV0xKOUFoSzFxQkVMRm1HVjFUNTdfYWR5Y0tCZTNWQUx0b3dRVUVXcGRRV25SRnFoY3ZBM0x6WXlYUmhTMXBjYURVRklFTUk?oc=5) — _Google News: sanctions_
- [EU sanctions 10 Russians over anti-war party ban - breakingthenews.net](https://news.google.com/rss/articles/CBMimAFBVV95cUxOMHluNVdxaXRUclhpNXVvaVJoUF9vb2tEZjVJbVRESW1uNTc0b0NDTEMtWmR4TU1XUVd3RFVpSGNIR1haajFGa0p2RktqREVQd2swSnIwblBQeTV6QzdSRlNLM3U2Y2x6VWlLcmxWOHB3Uk9YYnNtazMzeFBfODh6Mlc0MFhLLXYwOHBNcWMyUUQ1SFhLeUtGRw?oc=5) — _Google News: sanctions_
- [EU sanctions Tatarstan leader - todaypress.tv](https://news.google.com/rss/articles/CBMikAFBVV95cUxNdGNQaVlxek5McHJzUXE1STNoMF9jRGRTVDRKclJDMVJnby1ON19vaVJLZXFzNUJBZWUxVzNJam9EVjJ1X3V2T3AtdDRWZ1NXbEZhV21ueENuc0F6WFV4X1RGNzJmMGlNbDd2cXV6NkZxbUlVTFZmemtDWVFFTmFmbV8yUUxrSjEyXzliZWktUTc?oc=5) — _Google News: sanctions_
- [European Gas Prices Rally on U.S.-Iran Stalemate](https://oilprice.com/Latest-Energy-News/World-News/European-Gas-Prices-Rally-on-US-Iran-Stalemate.html) — _OilPrice_
- [Why Israel fears settlement sanctions are just the beginning - The Irish Times](https://news.google.com/rss/articles/CBMiuAFBVV95cUxQeWM5c05wNll5YkFHM1JzRWdfQ1Z2Mm5OVEVjeXZUS1RfQ09QaERScjVIeTRIU2FVdTl3WXZMX0hRUjltMzRybjJhYi1TZml2T1pwMHYzQ0lmbXJYOXVvbEpjYVA2QTlvUHpGT1VuTDM3dWllLS05TnF3NWtMUEMzenVabGdZMWd0b01NTG5mLWJtZmZ3ckc0ejN1QUJfRzA3Wk1OOTRUZlh4RnY3cUszVEp3cG9aQkdf?oc=5) — _Google News: sanctions_

**Siste 8-K som nevner temaet:** [GROUP 1 AUTOMOTIVE INC  (GPI)  (CIK 0001031203)](https://www.sec.gov/Archives/edgar/data/1031203/000119312526400088/0001193125-26-400088-index.htm); [VisionWave Holdings, Inc.  (VWAV, VWAVW)  (CIK 0002038439)](https://www.sec.gov/Archives/edgar/data/2038439/000173112226001278/0001731122-26-001278-index.htm); [Bravo Multinational Inc.  (BRVO)  (CIK 0001444839)](https://www.sec.gov/Archives/edgar/data/1444839/000109181826000148/0001091818-26-000148-index.htm)

### Bred risikoaversjon / trygge havner — score 0.54

**Hvorfor dette kan bety noe:** Når flere geopolitiske risikoer stiger samtidig, flyter penger typisk til gull, sveitserfranc, yen og amerikanske statsobligasjoner – og ut av små valutaer som NOK. Gullgruveaksjer er en giret eksponering mot gullprisen.

- **Ved eskalering:** Gull, CHF, JPY opp; NOK og småselskaper ned.
- **Ved nedtrapping:** Trygge havner gir tilbake gevinst; sykliske aksjer og NOK henter seg inn.
- **Hva kan gå galt:** Gull styres også av realrenter og sentralbankkjøp, uavhengig av overskrifter.

| Komponent | Score (z) | Detalj |
|---|---|---|
| GDELT hendelser (andel konflikt-/tiltakshendelser i temaets land) | -0.93 | siste 2 dager 6.982% av alle GDELT-artikler vs median 8.002% (60 dager) |
| GDELT nyhetsvolum (andel artikler med tema-nøkkelord) | 1.81 | 0.72% av kilde-URLer vs median 0.54% |
| GDELT tone (mer negativ enn normalt) | 0.31 | tone -5.35 vs median -5.25 (lavere = mer negativ) |
| RSS-overskrifter fra store medier | – | 35 overskrifter i går; baseline bygges opp (trenger ≥7 dager lagret historikk) |
| SEC 8-K-meldinger som nevner temaet | -1.35 | 42 8-K siste uke vs median 89/uke (søk "geopolitical") |
| Kurs/volum-avvik i temaets aksjer | 0.08 | snitt volum-z (5d) -0.54, snitt |5d avkastning-z| 0.70 over 8 instrumenter |

| Ticker | Rolle | 1d | 5d | 20d | 5d-z | Volum-z (5d) |
|---|---|---|---|---|---|---|
| GLD | vinner ved eskalering | +0.4% | -1.9% | -6.9% | -0.6 | -0.4 |
| GDX | vinner ved eskalering | +0.6% | -2.7% | -10.4% | -0.5 | -0.0 |
| NEM | vinner ved eskalering | +0.1% | -1.6% | -8.0% | -0.4 | -1.6 |
| GC=F | råvare/FX | -3.2% | -4.6% | -7.6% | -1.3 | -0.0 |
| USDCHF=X | råvare/FX | +0.5% | +1.2% | +2.9% | 1.1 | – |
| USDJPY=X | råvare/FX | -1.1% | -0.0% | -1.9% | -0.1 | – |
| USDNOK=X | råvare/FX | -0.1% | +1.1% | +1.6% | 0.9 | – |
| ^VIX | råvare/FX | +9.4% | +9.4% | +9.0% | 0.6 | – |

**Siste overskrifter:**

- [EU sanctions 10 Russians over anti-war party ban - breakingthenews.net](https://news.google.com/rss/articles/CBMimAFBVV95cUxOMHluNVdxaXRUclhpNXVvaVJoUF9vb2tEZjVJbVRESW1uNTc0b0NDTEMtWmR4TU1XUVd3RFVpSGNIR1haajFGa0p2RktqREVQd2swSnIwblBQeTV6QzdSRlNLM3U2Y2x6VWlLcmxWOHB3Uk9YYnNtazMzeFBfODh6Mlc0MFhLLXYwOHBNcWMyUUQ1SFhLeUtGRw?oc=5) — _Google News: sanctions_
- [As the US midterms approach, Trump’s boasts on the economy fall flat with voters](https://www.theguardian.com/business/2026/sep/28/trump-us-economy-midterm-elections) — _Guardian World_
- [EU adopts Russia sanctions over crackdown on anti-war party, abduction of Ukrainian children - The Kyiv Independent](https://news.google.com/rss/articles/CBMiugFBVV95cUxQNFFkSzlBb3J6UFdsVnUzNThOaXJFQUdxNmI2WHIxaDFyaDlTTl9uUVRpZS1DalN0UkdnTnZBVWNUd0I2YzE2bG5pWU50aEVoTDBBRndoTExDVVNWLUM1cEx6T3lpY3pSaVZTOTZ3LXM2U3pwMXhMeGRCS0tQUWNhZnlCRE1xYUg1VWdwQnFWcExWVEFHVkI1ZzNPQzk5S3FaSkhaN2lSaWZ4MjZqVGZXN3BqM1YtVGRsNFE?oc=5) — _Google News: sanctions_
- [UK diesel price hits all-time high, RAC says](https://www.bbc.co.uk/news/articles/c6n4k987k981o?at_medium=RSS&at_campaign=rss) — _BBC Business_
- [Oil prices surge after Trump rejects Iran’s plan to reopen Strait of Hormuz](https://www.aljazeera.com/economy/2026/9/28/oil-prices-surge-after-trump-rejects-irans-plan-to-reopen-strait-of-hormuz?traffic_source=rss) — _Al Jazeera_
- [Childminder facing 'severe financial burden' as heating oil costs rise](https://www.bbc.co.uk/news/articles/cq07ly2232pzo?at_medium=RSS&at_campaign=rss) — _BBC Business_

**Siste 8-K som nevner temaet:** [People Inc  (PPLI)  (CIK 0001800227)](https://www.sec.gov/Archives/edgar/data/1800227/000110465926110218/0001104659-26-110218-index.htm); [Northwest Natural Holding Co  (NWN)  (CIK 0001733998)](https://www.sec.gov/Archives/edgar/data/1733998/000173399826000145/0001733998-26-000145-index.htm); [Ispire Technology Inc.  (ISPR)  (CIK 0001948455)](https://www.sec.gov/Archives/edgar/data/1948455/000121390026102333/0001213900-26-102333-index.htm)

### Europa/Russland-konflikt og forsvarsutgifter — score 0.48

**Hvorfor dette kan bety noe:** Eskalering i Russland–Ukraina eller økt NATO-spenning øker sannsynligheten for høyere forsvarsbudsjetter og bestillinger av ammunisjon og luftvern. Forsvarsselskaper og europeiske leverandører (bl.a. Kongsberg Gruppen, som lager NASAMS og NSM-missiler) reprises ofte på innkjøpsnyheter. Ordrebøker reagerer med måneders forsinkelse – kursene reagerer på overskrifter.

- **Ved eskalering:** Forsvarsaksjer opp; europeisk forsvar er typisk mer følsomt enn amerikanske storselskaper. Kronen kan svekkes ved uro.
- **Ved nedtrapping:** Nyheter om våpenhvile har historisk gitt kraftige endagsfall i europeisk forsvar (gevinstsikring).
- **Hva kan gå galt:** Mye av opprustningshistorien er allerede priset inn (høye multipler); budsjetter tar år å bli til ordre.

| Komponent | Score (z) | Detalj |
|---|---|---|
| GDELT hendelser (andel konflikt-/tiltakshendelser i temaets land) | 0.56 | siste 2 dager 1.131% av alle GDELT-artikler vs median 0.871% (60 dager) |
| GDELT nyhetsvolum (andel artikler med tema-nøkkelord) | -0.31 | 3.29% av kilde-URLer vs median 3.48% |
| GDELT tone (mer negativ enn normalt) | 0.45 | tone -5.64 vs median -5.24 (lavere = mer negativ) |
| RSS-overskrifter fra store medier | – | 59 overskrifter i går; baseline bygges opp (trenger ≥7 dager lagret historikk) |
| Google Trends søkeinteresse | -0.99 | snitt siste 3 dager 5.9 vs median 7.8 (søk: NATO, Ukraine war, missile attack, defense stocks) |
| SEC 8-K-meldinger som nevner temaet | -0.51 | 53 8-K siste uke vs median 70/uke (søk "Ukraine") |
| Prediksjonsmarkeder (største 1-ukes bevegelse) | 2.20 | største 1-ukes endring 11.0 prosentpoeng blant 8 likvide markeder (score = pp/5) |
| Kurs/volum-avvik i temaets aksjer | 0.15 | snitt volum-z (5d) -0.35, snitt |5d avkastning-z| 0.65 over 11 instrumenter |
| OFAC-sanksjonsvedtak siste 14 dager | 0.00 | 1 relevante sanksjonsvedtak (designations) siste 14 dager |

**Prediksjonsmarkeder (Polymarket, markedets sannsynlighet):**

- [Will Russia enter Druzkhivka by December 31, 2026?](https://polymarket.com/event/which-cities-will-russia-enter-by-december-31): 34% (1d -7.0 pp, 1u -11.0 pp, volum 24t $15,625)
- [Russia-Ukraine peace talks by October 31, 2026?](https://polymarket.com/event/russia-x-ukraine-peace-talks-byptptpt-20260609012540716): 46% (1d -1.0 pp, 1u 4.0 pp, volum 24t $32,475)
- [Kanye West performs in Russia by October 31?](https://polymarket.com/event/kanye-west-performs-in-russia-by-october-31): 6% (1d -0.1 pp, 1u -2.2 pp, volum 24t $21,932)
- [NATO x Russia military clash by October 31, 2026?](https://polymarket.com/event/nato-x-russia-military-clash-in-2025): 14% (1d -1.0 pp, 1u -2.0 pp, volum 24t $15,237)
- [Putin out as President of Russia by December 31, 2026?](https://polymarket.com/event/putin-out-before-2027): 4% (1d -0.4 pp, 1u -0.8 pp, volum 24t $67,754)

| Ticker | Rolle | 1d | 5d | 20d | 5d-z | Volum-z (5d) |
|---|---|---|---|---|---|---|
| LMT | vinner ved eskalering | -0.8% | -2.6% | -7.6% | -0.7 | -0.0 |
| RTX | vinner ved eskalering | +0.4% | -2.4% | -10.7% | -0.7 | -0.5 |
| NOC | vinner ved eskalering | +0.3% | -3.2% | -5.9% | -0.8 | -0.1 |
| GD | vinner ved eskalering | +0.1% | -4.6% | -11.4% | -1.6 | 0.6 |
| LHX | vinner ved eskalering | -0.1% | -3.9% | -8.8% | -1.0 | 0.1 |
| ITA | vinner ved eskalering | +0.5% | -0.0% | -8.6% | -0.1 | 0.6 |
| KOG.OL | vinner ved eskalering | -0.2% | -3.0% | -1.7% | -0.5 | -0.6 |
| KIT.OL | vinner ved eskalering | -1.2% | -1.6% | +5.0% | -0.4 | -0.6 |
| RHM.DE | vinner ved eskalering | -1.1% | -3.9% | -12.5% | -0.4 | -0.9 |
| SAAB-B.ST | vinner ved eskalering | -0.9% | -0.5% | -2.5% | -0.1 | -1.3 |
| BA.L | vinner ved eskalering | -0.3% | -4.1% | -3.8% | -0.9 | -1.1 |

**Siste overskrifter:**

- [Lithuania imposes national sanctions on Russian billionaires Usmanov, Fridman - LRT](https://news.google.com/rss/articles/CBMiwwFBVV95cUxNc0hKc2lsenhnaXpnMlBTZXd1czBrMUdjSWhGaW5YMDBrdVE0VHV1eFg1UEhlZlh4R0laeDQ1M21FTlRxM0t6YndoYm1RV3ZOazY0djZxQWI4Qzh6RW1XSzd0bzJEQVhONElvMTN2c3FOZjFSMmZpVk1UelBsV0xKOUFoSzFxQkVMRm1HVjFUNTdfYWR5Y0tCZTNWQUx0b3dRVUVXcGRRV25SRnFoY3ZBM0x6WXlYUmhTMXBjYURVRklFTUk?oc=5) — _Google News: sanctions_
- [EU sanctions 10 Russians over anti-war party ban - breakingthenews.net](https://news.google.com/rss/articles/CBMimAFBVV95cUxOMHluNVdxaXRUclhpNXVvaVJoUF9vb2tEZjVJbVRESW1uNTc0b0NDTEMtWmR4TU1XUVd3RFVpSGNIR1haajFGa0p2RktqREVQd2swSnIwblBQeTV6QzdSRlNLM3U2Y2x6VWlLcmxWOHB3Uk9YYnNtazMzeFBfODh6Mlc0MFhLLXYwOHBNcWMyUUQ1SFhLeUtGRw?oc=5) — _Google News: sanctions_
- [The EU has imposed sanctions on those involved in the deportation of Ukrainian children to Russia - Українські Національні Новини (УНН)](https://news.google.com/rss/articles/CBMivAFBVV95cUxPYWJVNGFBRTVTTGc0YjdrWTBUY0IwOXVwSUt6dFpIZU9INVRKNU9NeVJYNk90ZlF6dWY1R0NaV0V4M2hUOEViRDJVNUdhSmxIOEEzcFkzMF9PZHhMRXlza2pVdmt4WW1DMEpsU2M4YmpXb3Z4RnBFZDBUaGRWOWMyRWRRZzJja1U2SF9ESjg5UlpXZjdRSFI1UERUWXBmRExteFIyaVJ1RXd4NlNHZG1CdVl2M0xzTmVuZWRSbdIBuwFBVV95cUxOampFVjhzOWR6NVJZOU1sMWdRbElHNlNWa1kxSUdDUzJfa1VpUndsZ1lOSThCYVcxMWZyWDJYVUl2TWZRVFpaV1gtbDVrT3QwcjRSYkU3MjBsMWF6WnBBWXlRczFpM20xODFnenhyWUd5dkJlazJ3WGExam5IbFdsQzVmRzBvU0p2ODI1eElPdnc1b2l3Nm5MQV9WYVJaNWdwV182bERjWXZINVNDTU9yT0ZNT2VoS240MFdJ?oc=5) — _Google News: sanctions_
- [DIU Exposes 14 Companies Helping Russia Circumvent Sanctions - Root-Nation.com](https://news.google.com/rss/articles/CBMihgFBVV95cUxOQ2haUm5kNkEySjhDR2JDX1g4ZmJyeThNTldHcUd1clY1YnVFUkJDcllNQ284WGJzbVRoYjVtUVhrQnZGMXpSUzl6YUVMLXJ2R2didWJwR2dyV0ZWVWZjQW1kMlQ2VENxYXQwaHA5Qi1tN3g5Z2doa0ZaMEw3WDI0UnB1d2l1QQ?oc=5) — _Google News: sanctions_
- [Sanctions pressure drives growth in Russia’s flag registry, CREA finds - safety4sea](https://news.google.com/rss/articles/CBMilwFBVV95cUxPWkhJOEQyWloxN0dKd3NyOFdpREJhWV9uRXR0anJfTy1IVE5aQk1WZWpwOTAwMld3WWdUdHBuQ2dRcmtHVjZaMjZudnk4M0ZTVFQzRFh2Ukl3SmgwRFVHdV9RWlNtaDBEM0JmU1FacUxySkVBelhpMF9qckhjVGxoMmxXYi0takVUa0owUzhfYzdsdFhXUXhn?oc=5) — _Google News: sanctions_
- [EU sanctions Tatarstan head over evacuation of children from Ukraine - Caliber.Az](https://news.google.com/rss/articles/CBMimwFBVV95cUxPSnFqWlpDM2N6QlM2WElzcFpFSjZ1Q0cwUUgwVUNSTGQ3RGJpNkdEQ21oTWR1VGl6QVhfaVc0bW1HVHRqWGpiU0dOYmRXUnRaR041Um1qVVFSOE9yUEtxcFlRTGZwT3VFR0R3dDBmbGxuSXRCYUdyWlVENnE3dEszcTZsVW1rY3h4OXF4czhDYlMySF82eWdVa0dNYw?oc=5) — _Google News: sanctions_

**Siste 8-K som nevner temaet:** [Quantum Cyber N.V.  (QUCY)  (CIK 0001874252)](https://www.sec.gov/Archives/edgar/data/1874252/000121390026103219/0001213900-26-103219-index.htm); [Quantum Cyber N.V.  (QUCY)  (CIK 0001874252)](https://www.sec.gov/Archives/edgar/data/1874252/000121390026103219/0001213900-26-103219-index.htm); [Haymaker Acquisition Corp V  (HYAC, HYAC-UN)  (CIK 0002111838)](https://www.sec.gov/Archives/edgar/data/2111838/000119312526401094/0001193125-26-401094-index.htm)

## 2. Kandidat-tickere

Poeng summeres fra: innsidekjøp-klynger, kongresskjøp, Oslo Børs-kontrakter/innsidemeldinger, føderale kontrakter, uvanlig volum/kurs, Reddit-omtale og temaets oppmerksomhet. Høy score = mer å undersøke, ikke et kjøpssignal.

**Kategorier i dag:** Kjøp-kandidat 0, Hold 3, Watchlist 57. _Regelbaserte kategorier – ikke personlig finansiell rådgivning, og ikke bevist å slå markedet._

- **Hold: HHH** – innsidekjøp-klynge (ledelse/styre) og positiv trend, men kursen har allerede steget (5d +14 %, 20d +5 %, +5 % over 50d-snitt) – ikke jag.
- **Hold: GME** – innsidekjøp-klynge (ledelse/styre) og positiv trend, men kursen har allerede steget (5d +3 %, 20d +28 %, +15 % over 50d-snitt) – ikke jag.
- **Hold: DELL** – sterk kvartalsrapport (eksperimentell, svak evidens) og positiv trend, men ingen ny utløser siste 7 dager (nyeste 2026-09-02).

### 2a. Koblet til geopolitiske temaer

#### HAFNI.OL – Hafnia Limited — 3.95 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: bare én uavhengig kildetype (tema med markedsbekreftelse)._

_Poeng: unusual_volume 2.6, theme_attention 0.9, ose_insider_notices 0.5. Kurs 86.85, 5d -8.3%, 20d +10.7%._

- [Uvanlig volum: snitt siste 5 dager 4.8x normalt (z=3.1)](https://finance.yahoo.com/quote/HAFNI.OL)
- [Newsweb innsidehandel (21 d, klassifisert fra meldingsteksten): 1 annet](https://newsweb.oslobors.no/message/682980)

**Hvorfor det kan bety noe:** Handelsvolumet er uvanlig høyt – noen posisjonerer seg. Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Primærinnsidere har handlet (sjekk om det er kjøp). Tema «Midtøsten / Iran / Gulfen – risiko for oljeforsyning»: Brent opp, tankrederier opp, europeiske E&P-selskaper opp, flyselskaper ned. Følg Polymarket-markedene om våpenhvile/blokade.

**Hva kan gå galt:** Høyt volum kan skyldes indeksendringer, emisjoner eller nyheter som allerede er priset. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Meldepliktig handel kan være salg, opsjoner eller aksjelån – les meldingen. Risikopremien forsvinner raskt: olje- og tankaksjer kan gi tilbake ukers gevinst på dager. OPECs ledige kapasitet og strategiske lagre demper topper; markedet kan allerede prise en stor premie.

#### KOG.OL – Kongsberg Gruppen ASA — 3.26 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: svakere enn OSEBX siste 20 d._

_Poeng: ose_contracts 1.5, dod_contract 1.4, theme_attention 0.4. Kurs 312.10, 5d -3.0%, 20d -1.7%._

- [Newsweb: 1 kontrakt-/ordremelding(er) siste 14 d, f.eks. «KONGSBERG signerer rammeavtale for NSM-utstyr til U.S. Marine Corps (USMC)»](https://newsweb.oslobors.no/message/683137)
- [DoD-kontrakt(er): 1 stk, totalt $404M (Contracts for Sept. 25, 2026)](https://www.war.gov/News/Contracts/Contract/Article/4612013/contracts-for-sept-25-2026/)

**Hvorfor det kan bety noe:** Selskapet har meldt nye kontrakter/ordre på Oslo Børs. Selskapet fikk nylig kontrakt(er) fra det amerikanske forsvarsdepartementet (daglig kunngjøring). Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Tema «Europa/Russland-konflikt og forsvarsutgifter»: Forsvarsaksjer opp; europeisk forsvar er typisk mer følsomt enn amerikanske storselskaper. Kronen kan svekkes ved uro.

**Hva kan gå galt:** Kontraktsverdi er ofte ikke oppgitt; sjekk størrelse mot selskapets omsetning. Mange DoD-kontrakter er modifikasjoner av eksisterende avtaler og allerede kjent for markedet. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Nyheter om våpenhvile har historisk gitt kraftige endagsfall i europeisk forsvar (gevinstsikring). Mye av opprustningshistorien er allerede priset inn (høye multipler); budsjetter tar år å bli til ordre.

#### GD  — 2.43 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: bare én uavhengig kildetype (offentlig kontrakt (DoD/USAspending)); kurs under 50-dagers snitt._

_Poeng: dod_contract 1.1, federal_award 1.0, theme_attention 0.4. Kurs 336.72, 5d -4.6%, 20d -11.4%._

- [USAspending: ny kontrakt $37M fra Department of the Interior](https://www.usaspending.gov/award/CONT_AWD_140D0426F0672_1406_140D0424D0001_1406)
- [DoD-kontrakt(er): 3 stk, totalt $72M (Contracts for Sept. 24, 2026)](https://www.war.gov/News/Contracts/Contract/Article/4611082/contracts-for-sept-24-2026/)

**Hvorfor det kan bety noe:** Selskapet fikk nylig kontrakt(er) fra det amerikanske forsvarsdepartementet (daglig kunngjøring). Selskapet har fått en stor ny kontrakt fra amerikanske myndigheter. Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Tema «Europa/Russland-konflikt og forsvarsutgifter»: Forsvarsaksjer opp; europeisk forsvar er typisk mer følsomt enn amerikanske storselskaper. Kronen kan svekkes ved uro.

**Hva kan gå galt:** Mange DoD-kontrakter er modifikasjoner av eksisterende avtaler og allerede kjent for markedet. Store rammekontrakter utbetales over mange år og er ofte forventet av analytikere. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Nyheter om våpenhvile har historisk gitt kraftige endagsfall i europeisk forsvar (gevinstsikring). Mye av opprustningshistorien er allerede priset inn (høye multipler); budsjetter tar år å bli til ordre.

#### LHX  — 2.24 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: bare én uavhengig kildetype (offentlig kontrakt (DoD/USAspending)); kurs under 50-dagers snitt._

_Poeng: dod_contract 1.9, theme_attention 0.4. Kurs 237.69, 5d -3.9%, 20d -8.8%._

- [DoD-kontrakt(er): 1 stk, totalt $876M (Contracts for Sept. 23, 2026)](https://www.war.gov/News/Contracts/Contract/Article/4609970/contracts-for-sept-23-2026/)

**Hvorfor det kan bety noe:** Selskapet fikk nylig kontrakt(er) fra det amerikanske forsvarsdepartementet (daglig kunngjøring). Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Tema «Europa/Russland-konflikt og forsvarsutgifter»: Forsvarsaksjer opp; europeisk forsvar er typisk mer følsomt enn amerikanske storselskaper. Kronen kan svekkes ved uro.

**Hva kan gå galt:** Mange DoD-kontrakter er modifikasjoner av eksisterende avtaler og allerede kjent for markedet. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Nyheter om våpenhvile har historisk gitt kraftige endagsfall i europeisk forsvar (gevinstsikring). Mye av opprustningshistorien er allerede priset inn (høye multipler); budsjetter tar år å bli til ordre.

#### SALM.OL – SalMar ASA — 2.08 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: ingen signaler fra kilder med høyere pålitelighet (bare ose_insider_notices, price_move)._

_Poeng: price_move 1.1, ose_insider_notices 1.0, theme_attention 0.0. Kurs 580.00, 5d +9.4%, 20d +1.9%._

- [Kursbevegelse 5d +9.4% (z=2.1 vs eget år)](https://finance.yahoo.com/quote/SALM.OL)
- [Newsweb innsidehandel (21 d, klassifisert fra meldingsteksten): 2 kjøp; kjøp for ca. NOK 2.3 mill.](https://newsweb.oslobors.no/message/683077)

**Hvorfor det kan bety noe:** Kursen har beveget seg uvanlig mye den siste uka. Primærinnsidere har handlet (sjekk om det er kjøp). Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Tema «Toll, handelskrig og eksportkontroll»: Beskyttede produsenter opp, rammede eksportører og bredt marked ned; USD ofte opp.

**Hva kan gå galt:** Stor bevegelse kan bety at nyheten allerede er priset (du er sen). Meldepliktig handel kan være salg, opsjoner eller aksjelån – les meldingen. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Handelsavtaler løfter eksportører og sykliske/fremvoksende markeder. Tollvarsler blir ofte utsatt, utvannet eller reversert; ekstremt mye støy i overskriftene.

#### SUBC.OL – Subsea 7 S.A. — 2.02 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: bare én uavhengig kildetype (kontraktsmelding (Newsweb)); svakere enn OSEBX siste 20 d._

_Poeng: ose_contracts 1.5, ose_insider_notices 0.5, theme_attention 0.0. Kurs 329.80, 5d +2.0%, 20d -4.3%._

- [Newsweb: 1 kontrakt-/ordremelding(er) siste 14 d, f.eks. «Subsea7 awarded contract extension offshore Türkiye»](https://newsweb.oslobors.no/message/682942)
- [Newsweb innsidehandel (21 d, klassifisert fra meldingsteksten): 1 annet](https://newsweb.oslobors.no/message/682944)

**Hvorfor det kan bety noe:** Selskapet har meldt nye kontrakter/ordre på Oslo Børs. Primærinnsidere har handlet (sjekk om det er kjøp). Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Tema «Nordisk/arktisk sikkerhet og undersjøisk infrastruktur»: Kongsberg/Kitron og gasspris opp.

**Hva kan gå galt:** Kontraktsverdi er ofte ikke oppgitt; sjekk størrelse mot selskapets omsetning. Meldepliktig handel kan være salg, opsjoner eller aksjelån – les meldingen. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Begrenset direkte nedside; mest et langsomt innkjøpstema. Hendelser er sjeldne og ofte uklare (ulykke vs. sabotasje); bevegelser forsvinner raskt.

#### FRO  — 2.00 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: bare én uavhengig kildetype (tema med markedsbekreftelse)._

_Poeng: unusual_volume 1.1, theme_attention 0.9. Kurs 47.73, 5d -7.2%, 20d +16.4%._

- [Uvanlig volum: snitt siste 5 dager 1.9x normalt (z=1.6)](https://finance.yahoo.com/quote/FRO)

**Hvorfor det kan bety noe:** Handelsvolumet er uvanlig høyt – noen posisjonerer seg. Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Tema «Midtøsten / Iran / Gulfen – risiko for oljeforsyning»: Brent opp, tankrederier opp, europeiske E&P-selskaper opp, flyselskaper ned. Følg Polymarket-markedene om våpenhvile/blokade.

**Hva kan gå galt:** Høyt volum kan skyldes indeksendringer, emisjoner eller nyheter som allerede er priset. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Risikopremien forsvinner raskt: olje- og tankaksjer kan gi tilbake ukers gevinst på dager. OPECs ledige kapasitet og strategiske lagre demper topper; markedet kan allerede prise en stor premie.

#### NOC  — 1.82 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: bare én uavhengig kildetype (offentlig kontrakt (DoD/USAspending)); kurs under 50-dagers snitt._

_Poeng: dod_contract 1.5, theme_attention 0.4. Kurs 510.52, 5d -3.2%, 20d -5.9%._

- [DoD-kontrakt(er): 7 stk, totalt $462M (Contracts for Sept. 24, 2026)](https://www.war.gov/News/Contracts/Contract/Article/4611082/contracts-for-sept-24-2026/)

**Hvorfor det kan bety noe:** Selskapet fikk nylig kontrakt(er) fra det amerikanske forsvarsdepartementet (daglig kunngjøring). Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Tema «Europa/Russland-konflikt og forsvarsutgifter»: Forsvarsaksjer opp; europeisk forsvar er typisk mer følsomt enn amerikanske storselskaper. Kronen kan svekkes ved uro.

**Hva kan gå galt:** Mange DoD-kontrakter er modifikasjoner av eksisterende avtaler og allerede kjent for markedet. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Nyheter om våpenhvile har historisk gitt kraftige endagsfall i europeisk forsvar (gevinstsikring). Mye av opprustningshistorien er allerede priset inn (høye multipler); budsjetter tar år å bli til ordre.

#### RTX  — 1.51 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: bare én uavhengig kildetype (offentlig kontrakt (DoD/USAspending)); kurs under 50-dagers snitt._

_Poeng: dod_contract 1.1, theme_attention 0.4. Kurs 189.40, 5d -2.4%, 20d -10.7%._

- [DoD-kontrakt(er): 5 stk, totalt $147M (Contracts for Sept. 24, 2026)](https://www.war.gov/News/Contracts/Contract/Article/4611082/contracts-for-sept-24-2026/)

**Hvorfor det kan bety noe:** Selskapet fikk nylig kontrakt(er) fra det amerikanske forsvarsdepartementet (daglig kunngjøring). Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Tema «Europa/Russland-konflikt og forsvarsutgifter»: Forsvarsaksjer opp; europeisk forsvar er typisk mer følsomt enn amerikanske storselskaper. Kronen kan svekkes ved uro.

**Hva kan gå galt:** Mange DoD-kontrakter er modifikasjoner av eksisterende avtaler og allerede kjent for markedet. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Nyheter om våpenhvile har historisk gitt kraftige endagsfall i europeisk forsvar (gevinstsikring). Mye av opprustningshistorien er allerede priset inn (høye multipler); budsjetter tar år å bli til ordre.

#### BA.L  — 1.39 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: bare én uavhengig kildetype (offentlig kontrakt (DoD/USAspending)); kurs under 50-dagers snitt._

_Poeng: dod_contract 1.0, theme_attention 0.4. Kurs 1966.00, 5d -4.1%, 20d -3.8%._

- [DoD-kontrakt(er): 2 stk, totalt $28M (Contracts for Sept. 25, 2026)](https://www.war.gov/News/Contracts/Contract/Article/4612013/contracts-for-sept-25-2026/)

**Hvorfor det kan bety noe:** Selskapet fikk nylig kontrakt(er) fra det amerikanske forsvarsdepartementet (daglig kunngjøring). Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Tema «Europa/Russland-konflikt og forsvarsutgifter»: Forsvarsaksjer opp; europeisk forsvar er typisk mer følsomt enn amerikanske storselskaper. Kronen kan svekkes ved uro.

**Hva kan gå galt:** Mange DoD-kontrakter er modifikasjoner av eksisterende avtaler og allerede kjent for markedet. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Nyheter om våpenhvile har historisk gitt kraftige endagsfall i europeisk forsvar (gevinstsikring). Mye av opprustningshistorien er allerede priset inn (høye multipler); budsjetter tar år å bli til ordre.

#### LMT  — 1.38 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: bare én uavhengig kildetype (offentlig kontrakt (DoD/USAspending)); kurs under 50-dagers snitt._

_Poeng: dod_contract 1.0, theme_attention 0.4. Kurs 519.56, 5d -2.6%, 20d -7.6%._

- [DoD-kontrakt(er): 1 stk, totalt $17M (Contracts for Sept. 25, 2026)](https://www.war.gov/News/Contracts/Contract/Article/4612013/contracts-for-sept-25-2026/)

**Hvorfor det kan bety noe:** Selskapet fikk nylig kontrakt(er) fra det amerikanske forsvarsdepartementet (daglig kunngjøring). Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Tema «Europa/Russland-konflikt og forsvarsutgifter»: Forsvarsaksjer opp; europeisk forsvar er typisk mer følsomt enn amerikanske storselskaper. Kronen kan svekkes ved uro.

**Hva kan gå galt:** Mange DoD-kontrakter er modifikasjoner av eksisterende avtaler og allerede kjent for markedet. Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Nyheter om våpenhvile har historisk gitt kraftige endagsfall i europeisk forsvar (gevinstsikring). Mye av opprustningshistorien er allerede priset inn (høye multipler); budsjetter tar år å bli til ordre.

#### AKRBP.OL – Aker BP ASA — 1.38 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: bare én uavhengig kildetype (tema med markedsbekreftelse); svakere enn OSEBX siste 20 d._

_Poeng: theme_attention 0.9, ose_insider_notices 0.5. Kurs 352.40, 5d +0.2%, 20d -1.4%._

- [Newsweb innsidehandel (21 d, klassifisert fra meldingsteksten): 1 tegning](https://newsweb.oslobors.no/message/683129)

**Hvorfor det kan bety noe:** Selskapet er eksponert mot et geopolitisk tema med økende oppmerksomhet. Primærinnsidere har handlet (sjekk om det er kjøp). Tema «Midtøsten / Iran / Gulfen – risiko for oljeforsyning»: Brent opp, tankrederier opp, europeiske E&P-selskaper opp, flyselskaper ned. Følg Polymarket-markedene om våpenhvile/blokade.

**Hva kan gå galt:** Oppmerksomhet ≠ lønnsomhet; temaet kan snu ved nedtrapping. Meldepliktig handel kan være salg, opsjoner eller aksjelån – les meldingen. Risikopremien forsvinner raskt: olje- og tankaksjer kan gi tilbake ukers gevinst på dager. OPECs ledige kapasitet og strategiske lagre demper topper; markedet kan allerede prise en stor premie.

### 2b. Annen uvanlig aktivitet (ikke koblet til tema)

#### HHH – Howard Hughes Holdings Inc. — 4.82 poeng — **Hold**
_Kategori: Hold. Hvorfor: innsidekjøp-klynge (ledelse/styre) og positiv trend, men kursen har allerede steget (5d +14 %, 20d +5 %, +5 % over 50d-snitt) – ikke jag._

_Poeng: price_move 2.0, unusual_volume 1.8, insider_cluster 1.0. Kurs 68.43, 5d +13.6%, 20d +5.4%._

- [SEC Form 4: 2 innsidere kjøpte i markedet for $1,667,428 (Davis Andrew D.; GRANDISSON MARC; Chief Operating Officer, HHC; Director, Executive Chairman, Vantage)](https://www.sec.gov/Archives/edgar/data/1981792/000110465926110504/0001104659-26-110504-index.htm)
- [Uvanlig volum: snitt siste 5 dager 2.1x normalt (z=2.3)](https://finance.yahoo.com/quote/HHH)
- [Kursbevegelse 5d +13.6% (z=3.3 vs eget år)](https://finance.yahoo.com/quote/HHH)

**Hvorfor det kan bety noe:** Kursen har beveget seg uvanlig mye den siste uka. Handelsvolumet er uvanlig høyt – noen posisjonerer seg. Flere innsidere kjøper med egne penger samtidig – de kjenner selskapet best.

**Hva kan gå galt:** Stor bevegelse kan bety at nyheten allerede er priset (du er sen). Høyt volum kan skyldes indeksendringer, emisjoner eller nyheter som allerede er priset. Vår egen test (2022–2025, ~980 klynger) fant ingen meravkastning etter innsidekjøp-klynger – bruk som bekreftelse, ikke som signal alene.

#### ONCIN.OL – Oncoinvent ASA — 4.43 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: rødt flagg: kursfall -41 % siste 20 handelsdager, lav likviditet (~$0.23M/dag), svak kurs: -42 % under 52-ukers topp (laveste 20 %, grense -28 %), rettet emisjon 2026-09-23 (siste 60 handelsdager), negativt driftsresultat i siste årsregnskap (2025: -155 mill.); ingen signaler fra kilder med høyere pålitelighet (bare ose_insider_notices, price_move, unusual_volume); kurs under 50-dagers snitt._

_Poeng: unusual_volume 1.7, price_move 1.7, ose_insider_notices 1.0. Kurs 84.00, 5d -27.6%, 20d -10.3%._

- [Uvanlig volum: snitt siste 5 dager 6.4x normalt (z=2.2)](https://finance.yahoo.com/quote/ONCIN.OL)
- [Kursbevegelse 5d -27.6% (z=-2.7 vs eget år)](https://finance.yahoo.com/quote/ONCIN.OL)
- [Newsweb innsidehandel (21 d, klassifisert fra meldingsteksten): 2 annet](https://newsweb.oslobors.no/message/682902)

**Hvorfor det kan bety noe:** Handelsvolumet er uvanlig høyt – noen posisjonerer seg. Kursen har beveget seg uvanlig mye den siste uka. Primærinnsidere har handlet (sjekk om det er kjøp).

**Hva kan gå galt:** Høyt volum kan skyldes indeksendringer, emisjoner eller nyheter som allerede er priset. Stor bevegelse kan bety at nyheten allerede er priset (du er sen). Meldepliktig handel kan være salg, opsjoner eller aksjelån – les meldingen.

#### EU – enCore Energy Corp. — 4.01 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: rødt flagg: kursfall -31 % siste 20 handelsdager; bare én uavhengig kildetype (innsidekjøp-klynge (ledelse/styre)); svakere enn S&P 500 siste 20 d._

_Poeng: price_move 2.0, unusual_volume 1.0, insider_cluster 1.0. Kurs 1.24, 5d +37.8%, 20d -10.8%._

- [SEC Form 4: 2 innsidere kjøpte i markedet for $111,850 (Little Richard H; SHERIFF WILLIAM M; Director, Chief Executive Officer; Director, Executive Chairman)](https://www.sec.gov/Archives/edgar/data/1500881/000119312526396060/0001193125-26-396060-index.htm)
- [Uvanlig volum: snitt siste 5 dager 2.4x normalt (z=1.5)](https://finance.yahoo.com/quote/EU)
- [Kursbevegelse 5d +37.8% (z=3.3 vs eget år)](https://finance.yahoo.com/quote/EU)

**Hvorfor det kan bety noe:** Kursen har beveget seg uvanlig mye den siste uka. Handelsvolumet er uvanlig høyt – noen posisjonerer seg. Flere innsidere kjøper med egne penger samtidig – de kjenner selskapet best.

**Hva kan gå galt:** Stor bevegelse kan bety at nyheten allerede er priset (du er sen). Høyt volum kan skyldes indeksendringer, emisjoner eller nyheter som allerede er priset. Vår egen test (2022–2025, ~980 klynger) fant ingen meravkastning etter innsidekjøp-klynger – bruk som bekreftelse, ikke som signal alene.

#### BFRG – BullFrog AI Holdings, Inc. — 4.00 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: rødt flagg: kursfall -30 % siste 20 handelsdager, lav likviditet (~$0.05M/dag), pennyaksje; bare én uavhengig kildetype (innsidekjøp-klynge (ledelse/styre))._

_Poeng: unusual_volume 3.0, insider_cluster 1.0. Kurs 0.67, 5d +43.5%, 20d +17.9%._

- [SEC Form 4: 2 innsidere kjøpte i markedet for $71,342 (Blacher Joshua; Singh Vininder; Chief Financial Officer; Director, Chief Executive Officer, 10% owner)](https://www.sec.gov/Archives/edgar/data/1829247/000162828026063054/0001628280-26-063054-index.htm)
- [Uvanlig volum: snitt siste 5 dager 73.4x normalt (z=9.2)](https://finance.yahoo.com/quote/BFRG)

**Hvorfor det kan bety noe:** Handelsvolumet er uvanlig høyt – noen posisjonerer seg. Flere innsidere kjøper med egne penger samtidig – de kjenner selskapet best.

**Hva kan gå galt:** Høyt volum kan skyldes indeksendringer, emisjoner eller nyheter som allerede er priset. Vår egen test (2022–2025, ~980 klynger) fant ingen meravkastning etter innsidekjøp-klynger – bruk som bekreftelse, ikke som signal alene.

#### GRAB – Grab Holdings Ltd — 3.77 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: rødt flagg: kursfall -23 % siste 20 handelsdager; bare én uavhengig kildetype (innsidekjøp-klynge (ledelse/styre)); kurs under 50-dagers snitt._

_Poeng: unusual_volume 1.5, price_move 1.3, insider_cluster 1.0. Kurs 3.13, 5d +12.0%, 20d -12.8%._

- [SEC Form 4: 2 innsidere kjøpte i markedet for $30,743,149 (Hungate Alexander Charles; Tan Anthony Ping Yeow; Director, Chief Executive Officer; Director, President and COO)](https://www.sec.gov/Archives/edgar/data/1855612/000189649726000009/0001896497-26-000009-index.htm)
- [Uvanlig volum: snitt siste 5 dager 2.2x normalt (z=2.0)](https://finance.yahoo.com/quote/GRAB)
- [Kursbevegelse 5d +12.0% (z=2.3 vs eget år)](https://finance.yahoo.com/quote/GRAB)

**Hvorfor det kan bety noe:** Handelsvolumet er uvanlig høyt – noen posisjonerer seg. Kursen har beveget seg uvanlig mye den siste uka. Flere innsidere kjøper med egne penger samtidig – de kjenner selskapet best.

**Hva kan gå galt:** Høyt volum kan skyldes indeksendringer, emisjoner eller nyheter som allerede er priset. Stor bevegelse kan bety at nyheten allerede er priset (du er sen). Vår egen test (2022–2025, ~980 klynger) fant ingen meravkastning etter innsidekjøp-klynger – bruk som bekreftelse, ikke som signal alene.

#### TECH.OL – Techstep ASA — 3.50 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: rødt flagg: kursfall -48 % siste 20 handelsdager, lav likviditet (~$0.17M/dag), pennyaksje, svak kurs: 12-1-momentum -87 % (laveste 20 %, grense -5 %) og -64 % under 52-ukers topp (laveste 20 %, grense -28 %), negativt driftsresultat i siste årsregnskap (2025: -88 mill.); bare én uavhengig kildetype (kontraktsmelding (Newsweb))._

_Poeng: price_move 2.0, ose_contracts 1.5. Kurs 5.60, 5d +114.6%, 20d +280.9%._

- [Newsweb: 1 kontrakt-/ordremelding(er) siste 14 d, f.eks. «Techstep ASA - Award of largest individual contract ever in Sweden»](https://newsweb.oslobors.no/message/683065)
- [Kursbevegelse 5d +114.6% (z=4.5 vs eget år)](https://finance.yahoo.com/quote/TECH.OL)

**Hvorfor det kan bety noe:** Kursen har beveget seg uvanlig mye den siste uka. Selskapet har meldt nye kontrakter/ordre på Oslo Børs.

**Hva kan gå galt:** Stor bevegelse kan bety at nyheten allerede er priset (du er sen). Kontraktsverdi er ofte ikke oppgitt; sjekk størrelse mot selskapets omsetning.

#### 2020.OL – 2020 Bulkers Ltd. — 3.44 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: rødt flagg: kursfall -53 % siste 20 handelsdager, lav likviditet (~$0.11M/dag), pennyaksje, svak kurs: 12-1-momentum -97 % (laveste 20 %, grense -5 %) og -95 % under 52-ukers topp (laveste 20 %, grense -28 %), rettet emisjon 2026-09-23 (siste 60 handelsdager); bare én uavhengig kildetype (kontraktsmelding (Newsweb))._

_Poeng: ose_contracts 1.5, unusual_volume 1.4, ose_insider_notices 0.5. Kurs 6.08, 5d +10.6%, 20d +47.0%._

- [Newsweb: 1 kontrakt-/ordremelding(er) siste 14 d, f.eks. «2020 Bulkers Ltd. (2020)   Announcement of a letter of intent to acquire up to 15x large AHTS vessels and intended financing of up to approximately USD 485 million»](https://newsweb.oslobors.no/message/682446)
- [Uvanlig volum: snitt siste 5 dager 6.3x normalt (z=1.9)](https://finance.yahoo.com/quote/2020.OL)
- [Newsweb innsidehandel (21 d, klassifisert fra meldingsteksten): 1 annet](https://newsweb.oslobors.no/message/683037)
- ⚠️ Short 1.09% av aksjene (endring 7d +1.09 pp, 30d +1.09 pp) – GSA CAPITAL PARTNERS LLP 1.09%

**Hvorfor det kan bety noe:** Selskapet har meldt nye kontrakter/ordre på Oslo Børs. Handelsvolumet er uvanlig høyt – noen posisjonerer seg. Primærinnsidere har handlet (sjekk om det er kjøp).

**Hva kan gå galt:** Kontraktsverdi er ofte ikke oppgitt; sjekk størrelse mot selskapets omsetning. Høyt volum kan skyldes indeksendringer, emisjoner eller nyheter som allerede er priset. Meldepliktig handel kan være salg, opsjoner eller aksjelån – les meldingen.

#### VTURA.OL – Ventura Offshore Holding Ltd. — 3.35 poeng — **Watchlist**
_Kategori: Watchlist. Hvorfor: Mangler bekreftelse: rødt flagg: lav likviditet (~$0.79M/dag); bare én uavhengig kildetype (kontraktsmelding (Newsweb))._

_Poeng: price_move 1.9, ose_contracts 1.5. Kurs 31.00, 5d -13.2%, 20d +3.3%._

- [Newsweb: 1 kontrakt-/ordremelding(er) siste 14 d, f.eks. «Ventura Offshore Holding Ltd.: SSV Catarina   Contract Amendment for Additional Well»](https://newsweb.oslobors.no/message/683041)
- [Kursbevegelse 5d -13.2% (z=-2.8 vs eget år)](https://finance.yahoo.com/quote/VTURA.OL)

**Hvorfor det kan bety noe:** Kursen har beveget seg uvanlig mye den siste uka. Selskapet har meldt nye kontrakter/ordre på Oslo Børs.

**Hva kan gå galt:** Stor bevegelse kan bety at nyheten allerede er priset (du er sen). Kontraktsverdi er ofte ikke oppgitt; sjekk størrelse mot selskapets omsetning.

## 3. Innsidekjøp i USA (SEC Form 4, siste 7 dager, kjøp i markedet)

| Ticker | Selskap | Innsidere | Verdi | Roller | Klynge |
|---|---|---|---|---|---|
| BBD | [BANK BRADESCO](https://www.sec.gov/Archives/edgar/data/1160330/000129281426004615/0001292814-26-004615-index.htm) | 21 | $26,953,225 | Director; Executive Officer | ja |
| GAM | [GENERAL AMERICAN INVESTORS CO INC](https://www.sec.gov/Archives/edgar/data/40417/000004041726000050/0000040417-26-000050-index.htm) | 3 | $387,410 | VP Administration; Vice-President | ja |
| RGCO | [RGC RESOURCES INC](https://www.sec.gov/Archives/edgar/data/1069533/000143774926031183/0001437749-26-031183-index.htm) | 3 | $85,088 | Director; Director, President & CEO | ja |
| ETRA | [Electra Therapeutics, Inc.](https://www.sec.gov/Archives/edgar/data/2088082/000094787126000880/0000947871-26-000880-index.htm) | 2 | $39,999,990 | Director, 10% owner | ja |
| GRAB | [Grab Holdings Ltd](https://www.sec.gov/Archives/edgar/data/1855612/000189649726000009/0001896497-26-000009-index.htm) | 2 | $30,743,149 | Director, Chief Executive Officer; Director, President and COO | ja |
| GME | [GameStop Corp.](https://www.sec.gov/Archives/edgar/data/1326380/000092189526002608/0000921895-26-002608-index.htm) | 2 | $26,795,680 | Director; Director, President, CEO and Chairman | ja |
| CV | [CapsoVision, Inc](https://www.sec.gov/Archives/edgar/data/1378325/000100916526000009/0001009165-26-000009-index.htm) | 2 | $14,999,995 | 10% owner | ja |
| NYAX | [Nayax Ltd.](https://www.sec.gov/Archives/edgar/data/1901279/000197640826000862/0001976408-26-000862-index.htm) | 2 | $4,752,698 | CEO, Co Founder & Chairman; Director, CTO and Co Founder | ja |
| HHH | [Howard Hughes Holdings Inc.](https://www.sec.gov/Archives/edgar/data/1981792/000110465926110504/0001104659-26-110504-index.htm) | 2 | $1,667,428 | Chief Operating Officer, HHC; Director, Executive Chairman, Vantage | ja |
| BCBP | [BCB BANCORP INC](https://www.sec.gov/Archives/edgar/data/1228454/000119312526397672/0001193125-26-397672-index.htm) | 2 | $1,317,500 | CHIEF FINANCIAL OFFICER; Director, CHIEF EXECUTIVE OFFICER | ja |
| DKS | [DICK'S SPORTING GOODS, INC.](https://www.sec.gov/Archives/edgar/data/1089063/000177240926000009/0001772409-26-000009-index.htm) | 2 | $1,244,889 | Director; EVP, Chief Financial Officer | ja |
| DFDV | [DeFi Development Corp.](https://www.sec.gov/Archives/edgar/data/1805526/000208792526000006/0002087925-26-000006-index.htm) | 2 | $181,751 | 10% owner; Chief Strategy Officer | ja |
| DUOT | [DUOS TECHNOLOGIES GROUP, INC.](https://www.sec.gov/Archives/edgar/data/1396536/000107997326001266/0001079973-26-001266-index.htm) | 2 | $133,844 | Director; Director, Chief Executive Officer | ja |
| VFF | [Village Farms International, Inc.](https://www.sec.gov/Archives/edgar/data/1584549/000119312526397230/0001193125-26-397230-index.htm) | 2 | $131,838 | Director; Director, Chief Executive Officer | ja |
| FLNC | [Fluence Energy, Inc.](https://www.sec.gov/Archives/edgar/data/1868941/000186894126000048/0001868941-26-000048-index.htm) | 2 | $125,120 | Director | ja |

## 3b. Fysisk oljemarked (futures)

- **3-2-1 crack spread (USD/fat) – raffinerimargin:** 60.45 (z mot 1 år +0.9)
- **Brent–WTI (USD/fat) – sjøbåren vs. amerikansk olje:** 4.82 (z mot 1 år +4.3)
- **Brent terminkurve: 1. vs 3. kontrakt (USD/fat, + = backwardation):** 11.09 – BZX26.NYM 107.84, BZZ26.NYM 100.46, BZF27.NYM 96.75, BZG27.NYM 91.78, BZH27.NYM 92.36
- **WTI terminkurve: 1. vs 3. kontrakt (USD/fat, + = backwardation):** 7.16 – CLX26.NYM 95.64, CLZ26.NYM 91.5, CLF27.NYM 88.48, CLG27.NYM 86.15, CLH27.NYM 84.28

## 3c. Amerikanske forsvarskontrakter (daglige DoD-kunngjøringer, største)

- Contracts for Sept. 23, 2026: **LATA-CTI JV LLC** $3,500.0M (PSN) — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4609970/contracts-for-sept-23-2026/)
- Contracts for Sept. 25, 2026: **Advanced Technology Construction Co.** $1,000.0M  — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4612013/contracts-for-sept-25-2026/)
- Contracts for Sept. 25, 2026: **Rio Tinto Services Inc.** $995.0M  — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4612013/contracts-for-sept-25-2026/)
- Contracts for Sept. 25, 2026: **Metallus Inc.** $995.0M (MTUS) — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4612013/contracts-for-sept-25-2026/)
- Contracts for Sept. 23, 2026: **L3Harris Technologies Inc.** $876.4M (LHX) — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4609970/contracts-for-sept-23-2026/)
- Contracts for Sept. 25, 2026: **Kongsberg Defence & Aerospace AS** $404.4M (KOG.OL) — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4612013/contracts-for-sept-25-2026/)
- Contracts for Sept. 25, 2026: **Defense Unicorns Inc.** $350.0M  — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4612013/contracts-for-sept-25-2026/)
- Contracts for Sept. 24, 2026: **GE Aviation Systems LLC** $199.7M  — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4611082/contracts-for-sept-24-2026/)
- Contracts for Sept. 23, 2026: **Walsh Construction Co. II LLC** $141.5M  — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4609970/contracts-for-sept-23-2026/)
- Contracts for Sept. 25, 2026: **J & J Contractors Inc.** $131.9M  — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4612013/contracts-for-sept-25-2026/)
- Contracts for Sept. 25, 2026: **National Industries for the Blind** $126.6M  — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4612013/contracts-for-sept-25-2026/)
- Contracts for Sept. 24, 2026: **Northrop Grumman Systems Corp.** $123.8M (NOC) — [kunngjøring](https://www.war.gov/News/Contracts/Contract/Article/4611082/contracts-for-sept-24-2026/)

## 4. Oslo Børs – kontrakts-/ordremeldinger (14 dager)

- 2026-09-28 **NRC**: [NRC Group ASA - Appointed to a civil contract in Norway - NOK 38 million](https://newsweb.oslobors.no/message/683145)
- 2026-09-28 **KOG**: [KONGSBERG signerer rammeavtale for NSM-utstyr til U.S. Marine Corps (USMC)](https://newsweb.oslobors.no/message/683137)
- 2026-09-28 **SWG**: [Shearwater awarded multi-year OBN contract offshore South America](https://newsweb.oslobors.no/message/683135)
- 2026-09-25 **TECH**: [Techstep ASA - Award of largest individual contract ever in Sweden](https://newsweb.oslobors.no/message/683065)
- 2026-09-25 **ELABS**: [Elliptic Labs signs contract expansion with existing smartphone customer](https://newsweb.oslobors.no/message/683057)
- 2026-09-24 **VTURA**: [Ventura Offshore Holding Ltd.: SSV Catarina   Contract Amendment for Additional Well](https://newsweb.oslobors.no/message/683041)
- 2026-09-24 **VEOFF**: [Ventura Offshore Midco Ltd.: SSV Catarina – Contract Amendment for Additional Well](https://newsweb.oslobors.no/message/683040)
- 2026-09-23 **SUBC**: [Subsea7 awarded contract extension offshore Türkiye](https://newsweb.oslobors.no/message/682942)
- 2026-09-22 **GOD**: [Goodtech awarded digital upgrade contract](https://newsweb.oslobors.no/message/682861)
- 2026-09-21 **DIASH**: [Diana Shipping Inc. Announces Time Charter Contract for m/v DSI Polaris with Dai An Ocean Shipping](https://newsweb.oslobors.no/message/682808)
- 2026-09-21 **PLT**: [poLight ASA Receives Follow-on Purchase Order for TWedge® Wobulation Technology Technical Samples for AR/MR Use from a Leading Consumer OEM](https://newsweb.oslobors.no/message/682779)
- 2026-09-16 **DIASH**: [Diana Shipping Inc. Announces Time Charter Contract for m/v Astarte with Aquavita](https://newsweb.oslobors.no/message/682499)
- 2026-09-16 **2020**: [2020 Bulkers Ltd. (2020)   Announcement of a letter of intent to acquire up to 15x large AHTS vessels and intended financing of up to approximately USD 485 million](https://newsweb.oslobors.no/message/682446)
- 2026-09-15 **BORR**: [Borr Drilling Limited - Operational and Contracting Updates](https://newsweb.oslobors.no/message/682398)
- 2026-09-15 **STECH**: [Soiltech awarded expanded scope on Deepsea Yantai](https://newsweb.oslobors.no/message/682338)

## 5. Shortposisjoner Oslo Børs (Finanstilsynet) – største endringer siste 7 dager

| Selskap | Ticker | Short % | Endr. 7d | Endr. 30d | Største |
|---|---|---|---|---|---|
| 2020 BULKERS | 2020.OL | 1.09 | +1.09 | +1.09 | GSA CAPITAL PARTNERS LLP 1.09% |
| HUNTER GROUP | HUNT.OL | 0.79 | +0.79 | +0.79 | CITADEL SECURITIES (EUROPE) LIMITED 0.79% |
| KITRON | KIT.OL | 1.12 | +0.62 | +1.12 | BLACKROCK FINANCIAL MANAGEMENT INC. 0.61%; Walleye Capital LLC 0.51% |
| MAGNORA | MGN.OL | 4.73 | -0.61 | +0.51 | ARROWSTREET CAPITAL, LIMITED PARTNERSHIP 1.83%; CITADEL ADVISORS LLC 1.46%; Actu |
| CIRCIO HOLDING ASA | CRNA.OL | 0.64 | -0.20 | +0.64 | CITADEL SECURITIES (EUROPE) LIMITED 0.64% |
| SED ENERGY HOLDINGS PLC | ENH.OL | 0.58 | -0.20 | -0.42 | ARROWSTREET CAPITAL, LIMITED PARTNERSHIP 0.58% |
| LINK MOBILITY GROUP HOLDING | LINK.OL | 7.20 | +0.18 | -0.78 | ARROWSTREET CAPITAL, LIMITED PARTNERSHIP 1.91%; JPMORGAN ASSET MANAGEMENT (UK) L |
| BORR DRILLING LIMITED | BORR.OL | 7.17 | +0.18 | +0.07 | ARROWSTREET CAPITAL, LIMITED PARTNERSHIP 3.3%; AQR CAPITAL MANAGEMENT, LLC 2.39% |
| CADELER A/S | CADLR.OL | 1.93 | +0.13 | +0.63 | ARROWSTREET CAPITAL, LIMITED PARTNERSHIP 0.8%; CAPITAL FUND MANAGEMENT 0.63%; CO |
| MOWI | MOWI.OL | 1.22 | +0.11 | +0.61 | JPMORGAN ASSET MANAGEMENT (UK) LIMITED 0.61%; TWO SIGMA INVESTMENTS, LP 0.61% |
| GRIEG SEAFOOD | GSF.OL | 0.98 | -0.11 | -1.07 | ARROWSTREET CAPITAL, LIMITED PARTNERSHIP 0.98% |
| ENVIPCO HOLDING N.V. | ENVIP.OL | 4.31 | -0.09 | +0.34 | JPMORGAN ASSET MANAGEMENT (UK) LIMITED 1.56%; CITADEL ADVISORS LLC 1.13%; ActusR |

## 7. Største bevegelser i geopolitiske prediksjonsmarkeder (1 uke)

- [US x Iran ceasefire continues through September 30?](https://polymarket.com/event/us-iran-ceasefire-continues-throughptptpt): 96% (1u 11.6 pp)
- [Saudi Oil Pipeline (East-West) restarts by September 30?](https://polymarket.com/event/saudi-oil-pipeline-east-west-restarts-byptptpt): 22% (1u -10.0 pp)
- [US announces end of Iranian blockade by October 31, 2026?](https://polymarket.com/event/us-announces-end-of-iranian-blockade-byptptpt-20260713152715080): 30% (1u -8.0 pp)
- [US announces end of Iranian blockade by December 31, 2026?](https://polymarket.com/event/us-announces-end-of-iranian-blockade-byptptpt-20260713152715080): 57% (1u -6.8 pp)
- [US announces end of Iranian blockade by September 30, 2026?](https://polymarket.com/event/us-announces-end-of-iranian-blockade-byptptpt-20260713152715080): 4% (1u -5.0 pp)
- [Russia-Ukraine peace talks by October 31, 2026?](https://polymarket.com/event/russia-x-ukraine-peace-talks-byptptpt-20260609012540716): 46% (1u 4.0 pp)
- [Strait of Hormuz traffic returns to normal by November 30?](https://polymarket.com/event/strait-of-hormuz-traffic-returns-to-normal-by-november-30-20260810151158765): 16% (1u 4.0 pp)
- [Will Flávio Bolsonaro win the 2026 Brazilian presidential election?](https://polymarket.com/event/brazil-presidential-election): 56% (1u -2.6 pp)
- [Israel x Iran ceasefire continues through September 30?](https://polymarket.com/event/israel-x-iran-ceasefire-continues-throughptptpt-20260716224448963): 98% (1u 2.4 pp)
- [Will David Lisnard win the 2027 French presidential election?](https://polymarket.com/event/next-french-presidential-election): 8% (1u 2.2 pp)

## 8. Makro (offisiell statistikk)

| Serie | Kilde | Periode | Siste | Endring | Overraskelse (z) | Pålitelighet |
|---|---|---|---|---|---|---|
| [Eksportpris fersk laks (NOK/kg, ukentlig)](https://www.ssb.no/statbank/table/03024) | SSB | 2026-09-16 | 71.41 | +1.75% | 0.8 | Offisiell statistikk – høy pålitelighet (kan revideres) |
| [Eksportvolum fersk laks (tonn, ukentlig)](https://www.ssb.no/statbank/table/03024) | SSB | 2026-09-16 | 31087.00 | +3.24% | 0.2 | Offisiell statistikk – høy pålitelighet (kan revideres) |
| [Vareeksport totalt (mill. NOK, måned)](https://www.ssb.no/statbank/table/08792) | SSB | 2026-08-01 | 190996.00 | +6.69% | 0.5 | Offisiell, foreløpige tall – middels/høy (revideres ofte) |
| [Fastlandseksport (mill. NOK, måned)](https://www.ssb.no/statbank/table/08792) | SSB | 2026-08-01 | 70627.00 | +4.84% | 0.2 | Offisiell, foreløpige tall – middels/høy (revideres ofte) |
| [KPI Norge (2025=100)](https://www.ssb.no/statbank/table/14710) | SSB | 2026-08-01 | 103.50 | -0.29% | -1.3 | Offisiell statistikk – høy pålitelighet (kan revideres) |
| [Industriproduksjon eurosonen (2021=100, sesongjustert)](https://ec.europa.eu/eurostat/databrowser/view/sts_inpr_m/default/table) | Eurostat | 2026-07-01 | 98.40 | +0.00% | -0.1 | Offisiell, foreløpige tall – middels/høy (revideres ofte) |
| [Inflasjon eurosonen (HICP, årlig %)](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_manr/default/table) | Eurostat | 2026-08-01 | 3.20 | +0.30 | 1.0 | Offisiell statistikk – høy pålitelighet (kan revideres) |
| [Brent spotpris (USD/fat, EIA via FRED)](https://fred.stlouisfed.org/series/DCOILBRENTEU) | FRED/EIA | 2026-09-22 | 114.89 | -1.08% | -0.8 | Offisielle tall via aggregator (FRED) – høy |
| [Henry Hub naturgass (USD/MMBtu, via FRED)](https://fred.stlouisfed.org/series/DHHNGSP) | FRED/EIA | 2026-09-22 | 2.90 | -1.02% | -0.3 | Offisielle tall via aggregator (FRED) – høy |
| [Industriproduksjon USA (Fed, indeks)](https://fred.stlouisfed.org/series/INDPRO) | FRED/Federal Reserve | 2026-08-01 | 103.07 | +0.02% | -0.1 | Offisielle tall via aggregator (FRED) – høy |
| [KPI USA (BLS, via FRED)](https://fred.stlouisfed.org/series/CPIAUCSL) | FRED/BLS | 2026-08-01 | 334.13 | +0.40% | 1.1 | Offisielle tall via aggregator (FRED) – høy |
| [USA import fra Kina (mill. USD, via FRED)](https://fred.stlouisfed.org/series/IMPCH) | FRED/Census | 2026-07-01 | 27070.65 | +7.64% | 0.9 | Offisielle tall via aggregator (FRED) – høy |
| [USA kommersielle råoljelagre (mill. fat, ukentlig)](https://www.eia.gov/petroleum/supply/weekly/) | EIA WPSR | 2026-09-18 | 426.40 | +2.97 | – | Offisiell, foreløpige tall – middels/høy (revideres ofte) |
| [Inflasjon UK (KPI årlig %)](https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23) | ONS | 2026-08-01 | 3.10 | +0.20 | 0.7 | Offisiell statistikk – høy pålitelighet (kan revideres) |
| [Industriproduksjon UK (indeks)](https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries/k222/diop) | ONS | 2026-07-01 | 98.50 | +0.20% | 0.4 | Offisiell, foreløpige tall – middels/høy (revideres ofte) |
| [Industriproduksjon Sverige (SCB, indeks)](https://www.statistikdatabasen.scb.se/pxweb/en/ssd/START__NV__NV0402__NV0402A/) | SCB | 2026-07-01 | 106.30 | -1.94% | -0.9 | Offisiell, foreløpige tall – middels/høy (revideres ofte) |
| [KPI Danmark (DST, indeks)](https://www.statbank.dk/PRIS113) | DST | 2025-12-01 | 121.20 | -0.41% | -0.8 | Offisiell statistikk – høy pålitelighet (kan revideres) |
| [OECD ledende indikator USA (CLI)](https://data-explorer.oecd.org/) | OECD | 2026-08-01 | 100.96 | +0.06 | -0.5 | Offisiell, foreløpige tall – middels/høy (revideres ofte) |
| [OECD ledende indikator Kina (CLI)](https://data-explorer.oecd.org/) | OECD | 2026-08-01 | 98.10 | -0.14 | -0.0 | Offisiell, foreløpige tall – middels/høy (revideres ofte) |

## 9. Kalender – kommende publiseringer og møter

- 2026-09-30 06:00 — **ONS**: GDP quarterly national accounts, UK: April to June 2026 time series
- 2026-09-30 06:00 — **ONS**: GDP quarterly national accounts, UK: April to June 2026
- 2026-09-30 08:00 — **SSB (estimert)**: Eksport av laks, ukentlig (tabell 03024)
- 2026-09-30 14:30 — **BEA**: GDP (Third Estimate), Industries, Corporate Profits, State GDP, and State Personal Income, 2nd Quarter 2026; State PCE, 2025
- 2026-09-30 16:00 — **BLS**: Metropolitan Area Employment and Unemployment (Monthly)
- 2026-09-30 16:30 — **EIA (estimert)**: Weekly Petroleum Status Report (råoljelagre)
- 2026-10-02 14:30 — **BLS**: Employment Situation
- 2026-10-06 14:30 — **BEA**: U.S. International Trade in Goods and Services, August 2026
- 2026-10-07 08:00 — **SSB (estimert)**: Eksport av laks, ukentlig (tabell 03024)
- 2026-10-07 16:30 — **EIA (estimert)**: Weekly Petroleum Status Report (råoljelagre)
- 2026-10-09 08:30 — **ONS**: UK trade development plan update: October 2026
- 2026-10-14  — **Yahoo**: Kvartalsrapport ASML
- 2026-10-15  — **Yahoo**: Kvartalsrapport AA
- 2026-10-15  — **Yahoo**: Kvartalsrapport TSM
- 2026-10-19  — **Yahoo**: Kvartalsrapport STLD
- 2026-10-19  — **Yahoo**: Kvartalsrapport CLF
- 2026-10-28 20:00 — **Federal Reserve**: FOMC rentebeslutning
- 2026-10-29 14:15 — **ECB**: ECB rentebeslutning og pressekonferanse

## 10. OFAC (amerikanske sanksjoner) – siste vedtak

- 2026-09-24: [Publication of Regulatory Amendments; Publication of Report for Licensing Activities Undertaken Pursuant to the Trade Sanctions Reform and Export Enhancement Act (TSRA)](https://ofac.treasury.gov/recent-actions/20260924)
- 2026-09-23: [Democratic Republic of the Congo-related Designations Removals](https://ofac.treasury.gov/recent-actions/20260923)
- 2026-09-18: [Expiration of Emergency With Respect to the Situation in Ethiopia; Ethiopia-related Designations Removals; Issuance of Amended Russia-related General License and Associated Frequently Asked Questions](https://ofac.treasury.gov/recent-actions/20260918)
- 2026-09-17: [Iran-related Designations; Cuba Designations; Belarus-related Designations Removals](https://ofac.treasury.gov/recent-actions/20260917)
- 2026-09-16: [Russia-related Designations Removals; Counter Narcotics Designation Removal; Issuance of Amended Venezuela General License and Frequently Asked Question](https://ofac.treasury.gov/recent-actions/20260916)
- 2026-09-14: [Iran-related Designation; Issuance of Amended Venezuela-related General License and Frequently Asked Question](https://ofac.treasury.gov/recent-actions/20260914)
- 2026-09-10: [Iran-related and Counter Terrorism Designations; Licensing Policy Update under Operation Economic Outcast; Settlement Agreement between OFAC and an Individual](https://ofac.treasury.gov/recent-actions/20260910)
- 2026-09-09: [Transnational Criminal Organizations Designations; Counter Terrorism Designation; Issuance of New and Amended Frequently Asked Questions](https://ofac.treasury.gov/recent-actions/20260909)

## 11. Kildestatus

| Kilde | Status |
|---|---|
| GDELT 1.0 daily events | ok (latest 2026-09-27, 76 days baseline) |
| GDELT DOC 2.0 API | FAILED after 0 queries: 429 for https://api.gdeltproject.org/api/v2/doc/doc -> using GDELT daily event files instead – ikke oppdatert (siste: ukjent) |
| News RSS | ok (20/20 feeds) |
| Prices (yfinance) | ok (83/84 tickers) |
| Google Trends (pytrends) | partial (5 themes) - rate limited: The request failed: Google returned a response with code 429 |
| SEC EDGAR 8-K full-text | ok (9 phrases x 13 weeks) |
| SEC EDGAR Form 4 | ok (1773 Form 4 filings, 0 parse errors) |
| SEC late-filing notices (NT 10-K/Q) | ok (3 late-filing notices in 7d) |
| US House PTR (congress trades) | FAILED index: 403 Client Error: Forbidden for url: https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2026FD.zip – ikke oppdatert (siste: ukjent) |
| US Senate eFD | not automated (requires interactive terms acceptance); see research/sources.md |
| USAspending awards | ok (55 new awards >= $25M in 21d) |
| SAM.gov | not used (API requires free key via sign-up) |
| OFAC recent actions | ok (120 actions since 2026-03-05) |
| Reddit (public RSS) | ok (50 posts from 7 subs); 3 feed errors |
| Polymarket (Gamma API) | ok (4182 open markets, 1596 matched to themes) |
| Kalshi | ok (1742 markets) |
| Oslo Børs Newsweb | ok (6128 announcements in 95d) |
| Norges Bank | fx ok; press rss ok (5) |
| Oil spreads & curves (yfinance futures) | ok (crack_321, brent_wti, bz_curve, cl_curve) |
| US DoD daily contracts (war.gov) | ok (15 daily announcements listed; 110 awards parsed) |
| Finanstilsynet short register | ok (99 issuers; 42 with reported shorts) |
| Makro: SSB | ok (5/5 serier) |
| Makro: Eurostat | ok (2/2 serier) |
| Makro: FRED/EIA | ok (2/2 serier) |
| Makro: FRED/Federal Reserve | ok (1/1 serier) |
| Makro: FRED/BLS | ok (1/1 serier) |
| Makro: FRED/Census | ok (1/1 serier) |
| Makro: EIA WPSR | ok (1/1 serier) |
| Makro: ONS | ok (2/2 serier) |
| Makro: SCB | ok (1/1 serier) |
| Makro: DST | ok (1/1 serier) |
| Makro: OECD | ok (2/2 serier) |
| Makro: IMF WEO (DataMapper) | ok |
| Makro: World Bank API | ok |
| Makro: Eurostat update RSS | ok (0 relevante oppdateringer) |
| BLS release calendar (ICS) | ok (313 events) |
| BEA release calendar (ICS) | ok (119 events) |
| ONS release calendar API | ok (25 upcoming) |
| Makro: Destatis GENESIS | not automated: GENESIS web service returned an HTML page for guest access (new API needs registration/token) |
| Makro: China NBS | FAILED: data.stats.gov.cn returned 403 from this box – ikke oppdatert (siste: ukjent) |
| Makro: BLS API v1 | not used: shared daily quota exhausted from this IP; BLS series taken via FRED CSV |
| Makro: EIA API v2 / FRED API / BEA API | need free API keys (sign-up) - not used; FRED graph CSV + EIA weekly CSV used instead |
| Fed FOMC calendar | ok (55 meetings) |
| ECB meeting calendar | ok (19 meetings) |
| Norges Bank meeting calendar | not automated (dates rendered client-side); press releases RSS used |
| Earnings calendar (yfinance) | ok (5 reports within 21d; 0 lookups failed) |
| Sterke kvartalsrapporter (S&P 500, Yahoo) | ok (53 rapporter siste 45 d; 5 oppfyller overraskelse ≥ 15 % og reaksjon ≥ +4 % mot SPY, 3 av dem PEAD-S) |
| Beslutningsdata (Yahoo: risiko, verdsettelse, stopp) | ok (57/60 tickere) |
| IMF PortWatch (sundpassasjer) | ok (8/8 stredet, data t.o.m. 2026-09-20) |
| Politikkvarsler (Federal Register / EU) | ok (41 dokumenter siste 10 d) |
| EIA lagre vs 5-årssnitt | ok (3/3 serier; under 5-årssnitt: 2) |
| Taiwan månedlig omsetning (MOPS) | ok (siste måned 2026-08, kurv +79.5 % å/å) |
| Newsweb innsidehandel: kjøp/salg (meldingstekst) | ok (52 kjøp, 24 annet, 11 ukjent, 9 tegning, 5 salg i 21 d) |
| Oslo-flagg (kurs, EBIT, emisjon, tilbakekjøp) | ok (29 Oslo-tickere, univers 121 likvide aksjer per 2026-09-25, EBIT for 25, Newsweb ok) |
| Temakart + Tema-katalysator (eksperimentell) | ok (11 Oslo-rader i 2 temakart, Tema-katalysator: 1, Newsweb ok) |
| Markedsregime (10-mnd snitt, volatilitet) | ok (S&P 500: over 10-mnd snitt, vol 11 %, OSEBX: over 10-mnd snitt, vol 8 %) |
| Kategorier (Kjøp/Hold/Watchlist) | ok (Kjøp: 0, Hold: 3, Watchlist: 57) |
| Datakvalitet (kurs) | ok (95 reparerte kurshopp, 41 tickere med uendret kurs ≥ 5 dager) |

## 12. Metode og validering

- Robust z-score: (siste verdi − median i basisperioden) / (1,4826 × MAD). Basis: 60 dager for GDELT, 12 uker for 8-K, 3 mnd for Google Trends.
- Temascore = vektet snitt av positive, avkortede (maks 5) komponentscorer. Vekter: gdelt_events 1.0, gdelt_urls 1.0, gdelt_tone 0.5, news_rss 0.75, google_trends 0.75, sec_8k 0.5, prediction_mkts 1.0, price_volume 0.75, ofac 1.0, physical_oil 1.0.
- Prediksjonsmarked-score = største 1-ukes sannsynlighetsendring i prosentpoeng / 5 blant markeder med ≥ $10k volum siste 24t.
- Historisk test av signalene: se [backtest.md](backtest.md).
