# Data sources – what works, what doesn't (verified 2026-09-27 from this box)

All sources are free and were tested live from this machine. "Key" = whether an API key / sign-up is needed.
Reliability labels (also shown on the website):
**A** = official statistics / regulator (high, but may be revised) · **B** = official announcement or exchange data (high) ·
**C** = market data via unofficial access (high quality, fragile access) · **D** = news/aggregated media (medium) · **E** = social media (low).

## Geopolitics & news

| Source | Endpoint | Key | Status | Rel. | Notes |
|---|---|---|---|---|---|
| GDELT 1.0 daily event files | `http://data.gdeltproject.org/events/YYYYMMDD.export.CSV.zip` | No | ✅ works | D | ~4 MB/day, ~70k events. Aggregated to country × CAMEO root + URL keyword counts; cached. Backfilled 2022-01 → today for backtests. Published ~06:00 UTC for the previous day. |
| GDELT 2.0 15-min files | `data.gdeltproject.org/gdeltv2/lastupdate.txt` | No | ✅ works | D | Not used yet (backlog: intraday). |
| GDELT DOC 2.0 API | `api.gdeltproject.org/api/v2/doc/doc` | No | ❌ HTTP 429 on every call from this box (even first call, with 5 s spacing) | D | Likely shared/flagged egress IP. Code kept (`gdelt_doc.py`), falls back to daily files. Should work from a home connection (limit 1 req / 5 s). |
| News RSS (BBC World/Business, Al Jazeera, Guardian, CNBC, FT, NYT, NPR, DW, France24, MarketWatch, Defense News, Breaking Defense, gCaptain, OilPrice, E24, DN, Google News queries) | see `collectors/rss.py` | No | ✅ 20/20 | D | Headlines stored in `data/history/headlines.csv` so a baseline builds over time. |
| NRK RSS | `nrk.no/toppsaker.rss` | No | ❌ 403 | D | Blocked from this box. |
| Mining.com, Splash247 | RSS | No | ❌ 403 / empty | D | |
| Reddit JSON (`/r/x/hot.json`) | | No (OAuth required now) | ❌ 403 | E | |
| Reddit RSS (`/r/x/hot.rss`) | | No | ⚠️ works, but rate-limits quickly (429 after a few feeds) | E | 7 s spacing, 7 subreddits, hot only. Low weight. |
| Google Trends (pytrends) | unofficial | No | ✅ works (fragile; 429 risk) | D | 10 payloads/run, 8 s spacing; skipped with `--fast`. |

## Prediction markets

| Source | Endpoint | Key | Status | Rel. | Notes |
|---|---|---|---|---|---|
| Polymarket Gamma API | `gamma-api.polymarket.com/events?tag_slug=geopolitics` | No | ✅ | C | Probabilities + `oneDayPriceChange`/`oneWeekPriceChange`, volume. Price history: `clob.polymarket.com/prices-history` (works). Information only. |
| Kalshi | `api.elections.kalshi.com/trade-api/v2/events` | No (reads) | ⚠️ intermittent: HTTP 429 during early probes, worked in later runs (1,742 markets) | C | Collected and status-reported, not yet used in scoring (backlog: merge with Polymarket). |

## US filings, government & regulators

| Source | Endpoint | Key | Status | Rel. | Notes |
|---|---|---|---|---|---|
| SEC EDGAR full-text search | `efts.sec.gov/LATEST/search-index?q=&forms=4&dateRange=custom…` | No (User-Agent with contact required) | ✅ (occasional 500 → retried) | B | Used to list Form 4s, count 8-Ks by theme phrase per week, and NT 10-K/Q late filings. Max 10 req/s. |
| SEC Form 4 XML | `sec.gov/Archives/edgar/data/{cik}/{acc}/{file}.xml` | No | ✅ | B | Parsed for open-market purchases (code P). Cached per accession. |
| SEC submissions / company_tickers JSON | `data.sec.gov/submissions/CIK##########.json`, `sec.gov/files/company_tickers.json` | No | ✅ | B | Available; not yet needed. |
| SEC Insider Transactions Data Sets (quarterly) | `sec.gov/files/structureddata/data/insider-transactions-data-sets/2025q4_form345.zip` | No | ✅ (2026q2 lives under `/files/datastandardsinnovation/…`) | B | Used for the insider-cluster backtest (2022q1–2025q4). |
| 13F | EDGAR | No | ✅ available | B | Not collected: filed up to 45 days after quarter end → confirmation only, not early. |
| US House PTRs (STOCK Act) | `disclosures-clerk.house.gov/public_disc/financial-pdfs/2026FD.zip` + `ptr-pdfs/2026/{DocID}.pdf` | No | ✅ | B | Electronic PDFs parsed with `pdftotext`; scanned paper filings skipped. Low weight (no edge found in research/x_accounts). |
| House/Senate Stock Watcher S3 datasets | `house-stock-watcher-data.s3…` | No | ❌ 403 (gone) | – | |
| US Senate eFD | `efdsearch.senate.gov` | No, but interactive terms acceptance + CSRF | ⚠️ not automated | B | Backlog. |
| USAspending.gov | `api.usaspending.gov/api/v2/search/spending_by_award/` (POST) | No | ✅ | A | New awards ≥ $25M (21 days). DoD data has ~90-day publication delay. |
| DoD ("Department of War") daily contracts | RSS `war.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=945` + article pages | No | ✅ RSS; ✅ article pages with Python requests (curl got 403 from Akamai – fragile) | B | Contracts ≥ $7.5M published ~17:00 ET each business day. Names mapped to tickers with a lookup table. |
| SAM.gov opportunities API | `api.sam.gov` | **Free key (sign-up)** | not used | B | Documented only. |
| OFAC recent actions | `ofac.treasury.gov/recent-actions` (HTML, paginated) | No | ✅ | B | Parsed titles/dates; designations vs. removals. SDN CSV also downloadable (`sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV`). OFAC RSS URL returned 404. |
| Fed FOMC calendar | `federalreserve.gov/monetarypolicy/fomccalendars.htm` | No | ✅ (HTML scrape) | B | |
| ECB meeting calendar | `ecb.europa.eu/press/calendars/mgcgc/html/index.en.html` | No | ✅ (HTML scrape) | B | |
| BLS release calendar | `bls.gov/schedule/news_release/bls.ics` | No | ✅ | A | ICS; times converted to Oslo time. |
| BEA release calendar | `bea.gov/news/schedule/ics/online-calendar-subscription.ics` | No | ✅ | A | |

## Norway

| Source | Endpoint | Key | Status | Rel. | Notes |
|---|---|---|---|---|---|
| Oslo Børs Newsweb | `api3.oslo.oslobors.no/v1/newsreader/list?fromDate=…&toDate=…` | No | ✅ | B | JSON behind newsweb.oslobors.no. List capped (~600) → queried in 5-day windows. Category "MANAGERS' TRANSACTION" = primary-insider trades; contract/order keywords flagged. Message page `newsweb.oslobors.no/message/{id}`. |
| Finanstilsynet short register | `ssr.finanstilsynet.no/api/v2/instruments` | No | ✅ | B | Net short positions ≥ 0.5 % with history per issuer; mapped to tickers via Newsweb issuer names. |
| Norges Bank FX (SDMX) | `data.norges-bank.no/api/data/EXR/B.USD+EUR.NOK.SP?format=sdmx-json` | No | ✅ | A | |
| Norges Bank press releases RSS | `norges-bank.no/en/rss-feeds/Press-releases---Norges-Bank/` | No | ✅ | B | (The generic `/Press-releases/` URL 404s.) Meeting dates page renders client-side → not automated. |
| SSB PxWebApi v2 | `data.ssb.no/api/pxwebapi/v2/tables/{id}/data?lang=en&outputFormat=json-stat2&valueCodes[Tid]=top(n)` | No | ✅ | A | Tables used: 03024 (weekly salmon export price & volume), 08792 (monthly external trade: total, mainland), 14710 (CPI). Next-release dates estimated from cadence (no machine-readable calendar found). |

## Markets

| Source | Endpoint | Key | Status | Rel. | Notes |
|---|---|---|---|---|---|
| yfinance (Yahoo) | unofficial | No | ✅ all 83 watch symbols incl. `.OL`, `TTF=F`, FX | C | Prices/volumes, earnings dates (`Ticker.calendar`), specific futures contracts (e.g. `BZF27.NYM`) for curve shape; crack spread from RB/HO/CL. |
| Freight indices (Baltic Dry etc.) | | Paid | ❌ not free | – | Proxy: BDRY ETF, tanker/container equities. |

## Official statistics (macro)

| Source | Endpoint | Key | Status | Rel. | Notes |
|---|---|---|---|---|---|
| Eurostat | `ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}` (JSON-stat) | No | ✅ | A | `sts_inpr_m` (EA20 industrial production), `prc_hicp_minr` (EA HICP; `prc_hicp_manr` stopped at 2025-12). Update RSS `…/catalogue/rss/en/statistics-update.rss` works. |
| FRED graph CSV | `fred.stlouisfed.org/graph/fredgraph.csv?id=SERIES` | No | ✅ | A (via aggregator) | Brent, Henry Hub, INDPRO, CPI, imports from China. FRED JSON API needs a **free key** (not used). |
| BLS API | `api.bls.gov/publicAPI/v1` | v1 no key (25/day); v2 free key | ❌ v1 daily quota exhausted from this shared IP | A | BLS series via FRED CSV instead. |
| BEA API | | **Free key** | not used | A | Calendar ICS used. |
| EIA API v2 | `api.eia.gov/v2` | **Free key** | not used (403 without key) | A | |
| EIA Weekly Petroleum Status Report CSV | `ir.eia.gov/wpsr/table1.csv` | No | ✅ | A | Commercial crude stocks (this week, last week, year ago). |
| ONS | `ons.gov.uk/{topic}/timeseries/{cdid}/{dataset}/data`; `api.beta.ons.gov.uk/v1/search/releases` | No | ✅ | A | CPI (D7G7/MM23), industrial production (K222/DIOP); upcoming releases calendar. |
| Statistics Sweden (SCB) | `api.scb.se/OV0104/v1/doris/en/ssd/...` (PxWeb v1, POST json-stat2) | No | ✅ | A | Industrial production (seasonally adjusted). v2 API also responds. |
| Statistics Denmark (DST) | `api.statbank.dk/v1/data` (POST) | No | ✅ | A | PRIS113 CPI index – note: latest value in table was 2025-12 at test time (check table choice; PRIS111 is an alternative). |
| Destatis GENESIS | `www-genesis.destatis.de/genesisWS/rest/2020/...` | Registration/token (guest login returned HTML) | ❌ not automated | A | Backlog. Eurostat covers Germany (geo=DE) as a workaround. |
| China NBS | `data.stats.gov.cn/english/easyquery.htm` | No | ❌ 403 from this box | A | OECD CLI for China used as proxy. |
| OECD SDMX | `sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,4.1/USA.M.LI...AA...H` | No | ✅ (USA, CHN; NOR returned no records) | A | Composite leading indicators. |
| IMF DataMapper (WEO) | `imf.org/external/datamapper/api/v1/NGDP_RPCH/NOR/USA/...` | No | ✅ | A (forecast) | Growth forecasts – context only. IMF SDMX 3.0 (`api.imf.org/external/sdmx/3.0`) responds; not used yet. |
| World Bank | `api.worldbank.org/v2/country/NOR/indicator/NE.EXP.GNFS.ZS?format=json` | No | ✅ | A | Annual; context only. |
| ENTSO-E transparency | | **Free token (sign-up)** | not used | A | Backlog (European power/gas flows). |

## Politeness
Per-host minimum spacing in `signaltool/config.py` (GDELT API 6 s, SEC 0.15 s ≈ 6–7 req/s, Reddit 7 s, OFAC 2 s, …),
retries with exponential backoff on 429/5xx, and disk caching (`data/cache`). Set `SIGNAL_UA="Your Name you@email"` for SEC.
No trading, no paid services, no log-ins.
