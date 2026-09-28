# signal-tool – geopolitical early-warning for stocks (v0.1)

🌐 **Live site (Norwegian, dark theme, updated nightly):** https://&lt;user&gt;.github.io/&lt;repo&gt;/  <!-- replace after enabling Pages -->

**What it does, in plain English:** every day it reads a large number of free public sources – world news, the GDELT
global event database, prediction markets, US and Norwegian company filings, insider trades, short positions, sanctions,
defence contracts, oil futures and official statistics – and asks one question: *which geopolitical themes and which
stocks are getting unusually much attention or activity compared with their own normal level?* It then writes a daily
report (markdown) and builds a small website (in Norwegian) that ranks the top emerging themes and candidate tickers,
each with the evidence, links, a plain-language "why this could matter" and "what could go wrong".

> ⚠️ **Not financial advice.** This is an information tool. Signals can be wrong, late, or already priced in.
> It never trades and uses no paid services or API keys.

## Quick start
```bash
git clone https://github.com/<user>/<repo>.git signal-tool && cd signal-tool
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # also needs poppler-utils (pdftotext) for US House PDFs
export SIGNAL_UA="Your Name your@email"   # SEC asks for a contact in the User-Agent
python -m signaltool run                  # full run (~10-20 min; first run backfills 75 days of GDELT)
python -m signaltool run --fast           # quicker: skips Google Trends/earnings, caps SEC Form 4 scan
python -m signaltool build-site           # rebuild site/ from the latest snapshot
python -m signaltool serve --port 8765    # view the site at http://localhost:8765/
python -m signaltool categorize           # refresh prices + Kjøp/Hold/Watchlist on the latest snapshot, rebuild report/site
python -m signaltool backtest all         # historical validation -> reports/backtest.md (+ backtest_categories.md)
python -m pytest -q                       # tests
```
Outputs: `reports/report_YYYY-MM-DD.md` (+ `reports/latest.md`), `site/` (static website), `data/snapshots/*.json`.

## How it works
```
collectors/  (one module per source, each returns data + a status string; failures never crash the run)
   gdelt_events  GDELT daily event files -> per-theme share of articles, tone, URL-keyword share
   rss, reddit   news headlines / subreddit posts, keyword-matched to themes (history stored for baselines)
   polymarket    geopolitical event probabilities + 1-day/1-week moves      (kalshi: blocked here)
   sec           Form 4 insider purchases, 8-K theme mentions per week, late-filing (NT 10-K/Q) notices
   congress      US House periodic transaction reports (PDF parsing)       (low weight)
   dod           US DoD daily contract announcements -> tickers
   usaspending   new large federal awards;  ofac: sanctions actions
   markets, oil  yfinance prices/volumes, earnings dates, crack spread, Brent-WTI, futures curves
   newsweb       Oslo Børs announcements (contracts, managers' transactions)
   shorts        Finanstilsynet short register (Oslo)
   macro         SSB, Eurostat, FRED CSV, EIA weekly, ONS, SCB, DST, OECD, IMF, World Bank + BLS/BEA/ONS calendars
   calendar_cb   Fed & ECB meeting dates;  norgesbank: NOK FX + press releases
themes.py      10 geopolitical themes -> sectors, commodities, US + Oslo tickers, winners/losers, reasoning,
               escalation / de-escalation playbook, keywords, GDELT countries & CAMEO event codes
anomaly.py     robust z-score: (latest - median of baseline) / (1.4826 x MAD)
pipeline.py    runs collectors, scores themes and tickers, writes the JSON snapshot
report.py      markdown report;  site.py: static website (Norwegian UI)
backtest/      insider-cluster test (SEC data sets 2022-2025) and GDELT-spike vs ETF test (2022-today)
```
**Theme score (0–5)** = weighted average of the positive, capped z-scores of: GDELT events, GDELT news volume, GDELT tone,
RSS headlines, Google Trends, SEC 8-K mentions, prediction-market moves (biggest 1-week move in points / 5), price/volume
anomalies of the theme's tickers, OFAC designations and (for oil themes) physical-oil spreads. Weights are in
`pipeline.WEIGHTS`, and the website shows each component with the raw numbers behind it.

**Ticker points** add simple, documented contributions: insider-buy clusters, DoD contracts, Oslo contract announcements,
Oslo managers' transactions, US federal awards, unusual volume, unusual price move, theme attention, Reddit cashtags and
(low weight) congressional buys. Short-position changes on Oslo are shown as warning flags, not added to the score.

Weighting follows a separate X-accounts research study (kept private, not part of this repository): official policy signals (sanctions, DoD
contracts), physical oil data and shipping get relatively more weight; politician trades are low weight.

## Categories: «Kjøp» (kandidat), «Hold», «Watchlist»
Every candidate ticker gets a rule-based label (code and thresholds: `signaltool/categories.py`; shown as coloured
badges with a one-line "Hvorfor: …" on the dashboard, ticker list, theme and ticker pages; each ticker page lists every rule
as met / not met). **Our backtests found no proven edge, so these are conservative, transparent rules – not a forecast,
not personal financial advice, and not proven to beat the market.**

* **Kjøp-kandidat** – ALL of: ≥ 2 *independent* higher-reliability signal types (official US contract via DoD/USAspending
  [one type]; SEC insider-purchase cluster with officers/directors; Oslo Newsweb contract announcement; theme score ≥ 1 confirmed
  by the physical oil market z ≥ 1), at least one ≤ 7 days old; close above the 50-day average and 20-day return above the
  benchmark (OSEBX for `.OL`, S&P 500 otherwise); not stretched (5d < +10 %, 20d < +25 %, < 25 % above the 50-day average);
  no red flags (sharply rising Oslo short interest, ≥ 20 % crash within 20 sessions, turnover < ~USD 1M/day, price < ~USD 1,
  volume/price-only signal). Volume, price moves, Reddit, congress trades and Newsweb insider notices never count as signal types.
  Expect zero on most days.
* **Hold** – ≥ 1 higher-reliability signal type, price confirmation, no red flags, but the entry is late: stretched, signals
  older than 7 days, or a Kjøp-kandidat within the last 30 days without a new trigger ("if you own it, the signals still
  support it; don't chase").
* **Watchlist** – everything else with attention (single source, volume/theme only, falling price, red flags, no price data).

**Forward log / Treffsikkerhet:** each run appends `date, ticker, category, price, price_date, benchmark, score, n_types`
to `logs/categories.csv` (~60 rows/day, one set per day). This file is **tracked in git**: the nightly workflow commits and
pushes it after each run (as `GrokBot`, only if it changed, message tagged `[skip ci]`; the workflow only runs on
schedule/workflow_dispatch, so the bot push never re-triggers a deploy). It is also published at `site/historikk/kategorier.csv`.
Everything else in `data/` (GDELT, RSS/Reddit history, HTTP cache, snapshots) stays git-ignored and lives in the Actions cache.
The «Treffsikkerhet» section (Tickere page) shows excess return vs the benchmark after 5/20/60 trading days for *new*
entries into each category, once ≥ 10 entries have matured – before that it says «ikke nok data ennå».
Historical sanity check of the rules: `reports/backtest_categories.md` (`python -m signaltool backtest categories`).

## Honest limitations
* No language model: keyword matching produces false hits and misses nuance (e.g. "ceasefire collapses" vs "ceasefire holds").
* Several baselines (RSS, Reddit) only become meaningful after ~1–2 weeks of daily runs.
* From this machine, GDELT's DOC API returns HTTP 429 (Kalshi intermittently) and NRK/Reddit JSON return 403 (see `research/sources.md`).
* Insider data lags up to 2 business days, congressional trades up to 45 days, DoD data in USAspending ~90 days.
* Backtests have survivorship bias, no trading costs, few independent events, and multiple-testing risk – see `reports/backtest.md`.

## Publishing: GitHub Pages + nightly update
The site is plain static HTML/CSS (dark theme, all links relative, so it works under `https://<user>.github.io/<repo>/`).
`.github/workflows/nightly.yml` runs every night at **05:17 UTC** (07:17 Oslo summer time) and on demand (*Actions → Run workflow*):

1. installs Python 3.12 + `requirements.txt` + `poppler-utils`, runs the tests;
2. restores `data/` (GDELT daily aggregates, RSS/Reddit headline history = baselines, HTTP/Form 4 caches, snapshots)
   from **`actions/cache`**, runs `python -m signaltool run` (collect → score → report → build site), prunes old state and
   saves the cache again. Nothing is committed back, so the repository stays small and the workflow only needs read access;
3. deploys `site/` with the official `actions/configure-pages`, `actions/upload-pages-artifact` and `actions/deploy-pages`.

Robustness: every collector catches its own errors, so sources that block GitHub's IP ranges (e.g. Reddit, GDELT DOC API,
some statistics offices) just show up as `FAILED` on the «Kilder og metode» page. If the whole run crashes, the workflow
rebuilds the site from the last cached snapshot, or — if there is no cache — deploys the `site/` committed in the repo.
If the cache is evicted (GitHub drops caches unused for 7 days), the next run re-downloads 75 days of GDELT files
(a few minutes) and the RSS/Reddit baselines start over. GitHub also disables scheduled workflows in repos with no
activity for 60 days — re-enable under *Actions* if that happens.

One-time setup after pushing: *Settings → Pages → Source: GitHub Actions*; optionally *Settings → Secrets and variables →
Actions → Variables*: `SIGNAL_UA` = `"Your Name your@email"` (SEC EDGAR asks for a contact in the User-Agent; without it a
generic UA with the repo URL is used). No secrets or API keys are required.

Not in the repository (see `.gitignore`): `data/` (runtime state/caches, ~110 MB locally, regenerable), the private
`research/x_accounts/` workspace, virtualenvs and logs.

## Disclaimer
**Not financial advice.** This is an automated information tool built on free public data and simple, transparent rules.
Signals can be wrong, late, or already priced in; nothing here is a recommendation to buy or sell any security.
Do your own research. The authors accept no liability for decisions made using this tool. Third-party data belongs to
its respective providers (GDELT, SEC, Polymarket, Oslo Børs, Finanstilsynet, SSB, Eurostat, FRED, etc.).
*Ikke finansiell rådgivning.*

## Files
* `research/sources.md` – every source tested, with status, key requirements and reliability label
* `research/backlog.md` – prioritised next steps
* `reports/` – daily reports and `backtest.md`
* `screenshots/` – headless-browser screenshots of the site (dark theme)
* Pages carry `<meta name="robots" content="noindex">` (remove in `signaltool/site.py` if you want search engines to index the site).
* `site/` – last locally built copy of the website (the live site is rebuilt nightly by the workflow)
