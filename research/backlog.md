# Backlog – prioritert (oppdatert 2026-09-28 etter nattens arbeid)

Prinsipp: bare signaler som har ledet kursene i test *utenfor utvalget* (etter kostnader og med |t| ≥ ~3 for mange tester) får poeng
i Kjøp-reglene. Resten vises som kontekst. Resultater: `reports/backtest_natt.md` (også på Kilder-siden, #natt).

## Ferdig (natt 2026-09-27/28)
- **Beslutningsgrunnlag per ticker**: priset inn (5/20/60 d mot indeks/sektor), P/E, EV/EBITDA, analytikere, estimatrevisjoner, short-andel,
  volatilitet/maks fall/beta/likviditet, neste rapport, ugyldiggjøring (50d-snitt / 2×ATR).
- **Scenarioer per tema** (bull/base/bear + nøkkelindikator), «Hva bør jeg se på i dag?», «Nytt siden i går», varsler.
- **Flaskehalsradar, del 1**: Taiwan MOPS månedsomsetning 2012– (kurv, AI-servere, minne, TSMC, bredde). Ingen robust ledende effekt på SMH/TSM/EWT.
- **Sundpassasjer**: IMF PortWatch daglig (7 d mot 90 d median og mot i fjor). Ikke signifikant som kurssignal; vises som fysisk bekreftelse.
- **Politikkvarsler**: Federal Register (BIS/ITA/OFAC/USTR) + EU-sanksjoner, daglig (ikke < 5 min).
- **Oljenowcast**: EIA ukentlige lagre mot 5-årssnitt. Fortegnet snur mellom periodene → kun kontekst.
- **Newsweb: kjøp/salg lest fra meldingsteksten** (20/20 i stikkprøve). Test på 6 418 meldinger 2021–: **ingen robust effekt** → kun visning.
- **Kontraktsmeldinger Oslo** (4 899 titler 2019–): ingen robust drift etter publiseringsdagen → kun visning. Filteret som fjerner rettssaker og aksjetildelinger brukes nå også live.
- **PEAD** (sterk kvartalsrapport): robust i begge perioder → **ny signaltype**. Skanner hele S&P 500.
- **Svak 12-1-momentum Oslo** → **nytt rødt flagg**.
- Testet uten effekt: kursbekreftelse (USA), Polymarket → XLE (samtidig, ikke ledende), størrelse på DoD-kontrakter, shortposisjoner Oslo (historikk kun fra 2024).

## P0 – neste
1. **Revurder reglene med svak støtte**: «ikke strukket» for USA (strukne aksjer gjorde det *bedre* i begge perioder, men få aksjer og overlevelsesskjevhet);
   gov-kontrakt som «høy pålitelighet» (ingen målt effekt av størrelse). Krever test med punkt-i-tid-univers før endring.
2. **Punkt-i-tid-univers for USA** (historiske S&P 500-medlemmer fra Wikipedia-endringslogg) for å fjerne overlevelsesskjevhet i alle tester.
3. **Minne → MU**: akselerasjon i Nanya/Winbond-omsetning ga t 3,2 utenfor utvalget, men svakt i utvalget. Følg videre og test på nytt med flere år.
4. **Oslo rapportkalender** (Newsweb-kategori «financial calendar») → hendelsesrisiko og PEAD for Oslo (Yahoo dekker .OL dårlig).
5. **Planlegger** (cron/systemd): lette kilder hvert 30.–60. min (politikk, Polymarket, Newsweb) + full kjøring 07:00; varsel ved nye 🔔.

## P1
6. **PEAD i Oslo**: bygg overraskelse fra Newsweb-rapporter + kursreaksjon (reaksjonen alene kan testes nå med kontrakts-/rapporttitlene).
7. **Estimatrevisjoner som signal**: vises nå (Yahoo eps_trend), men gratis historikk mangler → lagre daglig for egen test om 6–12 mnd.
8. **Innsidekjøp Oslo på selve meldingsdagen**: litteraturen finner +1–2 % samme dag; kun nyttig med intradag-varsling (se planlegger).
9. **Taiwan flaskehalsradar, del 2**: leverandør→kunde-kart (hånd-kuratert CSV), EDGAR fulltekst-fraser («sold out», «allocation», «lead times»).
10. **CFTC COT** (gratis ukentlig) for olje/gass/metaller; **Gassco UMM** (gratis) for norsk gass.
11. **Norges Bank møtedatoer** og regionalt nettverk.
12. **13D/13G** aktivister via EDGAR fulltekst.

## P2
13. GDELT GKG-temaer (mer presise enn URL-nøkkelord), 15-min-filer for intradag.
14. Stillingsannonser som vekstsignal (krever gratis kilde uten innlogging – ikke funnet ennå).
15. ENTSO-E (gratis token via e-post – krever registrering, derfor ikke gjort), Destatis (registrering).
16. Forward-only logg for X-kontoer (numerisk bruker-ID).
17. Hosting av siden (kun når brukeren ønsker det).

## Ikke aktuelt (betalt/innlogging)
Kortdata, geolokasjon, satellittbilder, betalte konsensusestimater, Bloomberg/Refinitiv.
