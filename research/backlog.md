# Backlog – prioritised for the coming daily sessions

Priority follows research/x_accounts/REPORT.md: signals that historically *preceded* moves
(supply-chain bottlenecks, chokepoints/shipping, official policy headlines, physical oil) come first;
politician trades, options flow and chart calls showed no edge and stay low-weight.

## P0 – highest value next
1. **Bottleneck radar** (research #1). Taiwan MOPS monthly revenue (free, mops.twse.com.tw – published by the 10th each month),
   Korean DART disclosures (free key), Japanese TDnet headlines; phrase flags ("sold out", "allocation", "price increase",
   "lead times extended", "capacity reservation") in 8-K/press releases via EDGAR full-text search; supplier→customer map
   (start with a hand-curated CSV for semis, uranium conversion, optical components, defence munitions).
2. **Chokepoint monitor** (research #2). Free options to test: IMF PortWatch (daily transit counts for Hormuz, Bab el-Mandeb,
   Suez, Malacca, Panama – ArcGIS open data), UNCTAD port calls; tanker equity basket (FRO, DHT, HAFNI.OL, BWLPG.OL, STNG) and
   BDRY/BWET as freight proxies; flag transit drops > 2σ vs 60-day baseline.
3. **Forward-only call ledger for verified X accounts**, tracked by *numeric user ID* (not handle) to avoid impersonators
   (TankerTrackers, HFI Research, Javier Blas, sentdefender, DeItaone, Burggraben, Serenity, Citrini, Culper). Log each cashtag
   call at first sight, score at 1/3/6 months vs SPY + sector ETF, show hit rate + median. Uses the fetchers in research/x_accounts.
4. **Policy-to-ticker mapper, faster**: poll OFAC recent actions, DoD contracts (17:00 ET), BIS export-control (Federal Register API,
   free, no key: `federalregister.gov/api/v1/documents.json?conditions[agencies][]=industry-and-security-bureau`),
   USITC/Commerce anti-dumping (Federal Register), EU Official Journal sanctions (EUR-Lex RSS), CHIPS Act awards (commerce.gov news).
   Target < 5 min latency → needs a scheduler (cron/systemd timer) rather than a daily run.
5. **Physical-oil nowcast**: EIA weekly stocks vs a seasonal 5-yr average (EIA historical CSVs), Brent/WTI timespreads
   (M1–M2, M1–M6 history built daily from yfinance contract symbols), diesel/gasoline cracks vs seasonal norms.

## P1
6. **Scheduler + alerts**: run every 30–60 min (lightweight sources) + full daily run 07:00 Oslo; push alert to e-mail/Telegram
   (free bot) when theme score > 2.5 or new insider cluster / DoD award on a watch ticker.
7. **Oslo Børs depth**: parse Newsweb attachments for managers' transactions (buy vs sell, amount) and contract values;
   Oslo Børs daily volume/turnover for all issuers (not just watchlist) to find unusual volume market-wide.
8. **Norges Bank meeting dates** (page renders client-side – find JSON endpoint or maintain yearly list from the
   published schedule) and **Norges Bank regional network** report text.
9. **Earnings calendar for Oslo** (Newsweb "financial calendar" category / issuer IR pages) – yfinance coverage of .OL is patchy.
10. **ENTSO-E** (free token by e-mail) – European gas/power flows, Norwegian export capacity; **Gassco** UMM outages (free, public).
11. **Senate eFD** automation (requires terms-acceptance session) – low priority given no measured edge.
12. **13D/13G activist and 5 % stakes** via EDGAR full text (confirmation signal, research #7).
13. **Forensic flag feed** extensions: auditor changes (8-K item 4.01), insider *selling* clusters, short-report publications.
14. **Short-squeeze monitor** for Oslo: combine Finanstilsynet short % with volume/price spikes.

## P2
15. GDELT 2.0 15-minute files for intraday theme spikes; GDELT GKG themes (more precise than URL keywords).
16. Better text classification without an LLM: curated phrase lists per theme + negation handling; dedupe near-identical headlines.
17. Destatis GENESIS (needs registration), China NBS (403 here – test from another network), BLS/BEA/EIA/FRED APIs with free keys
    for more series + official release calendars.
18. Commodity futures curves for gas (TTF), grains, metals; COT positioning (CFTC, free weekly CSV).
19. Defence budgets: NATO annual defence expenditure tables (PDF/XLSX), SIPRI (free, annual), EU EDIP/ASAP announcements.
20. Backtests: extend GDELT test to more themes/instruments with multiple-testing correction; test Polymarket moves vs ETFs
    using `clob.polymarket.com/prices-history`; test Oslo contract announcements vs next-day returns.
21. Host the static site (GitHub Pages via a private repo + Actions nightly build) once the user wants it public.
