# signal-tool – geopolitical early-warning for stocks (v0.1)

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
cd /workspace/signal-tool
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # also needs poppler-utils (pdftotext) for US House PDFs
export SIGNAL_UA="Your Name your@email"   # SEC asks for a contact in the User-Agent
python -m signaltool run                  # full run (~10-20 min; first run backfills 75 days of GDELT)
python -m signaltool run --fast           # quicker: skips Google Trends/earnings, caps SEC Form 4 scan
python -m signaltool build-site           # rebuild site/ from the latest snapshot
python -m signaltool serve --port 8765    # view the site at http://localhost:8765/
python -m signaltool backtest all         # historical validation -> reports/backtest.md
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

Weighting follows the X-accounts research in `research/x_accounts/REPORT.md`: official policy signals (sanctions, DoD
contracts), physical oil data and shipping get relatively more weight; politician trades are low weight.

## Honest limitations
* No language model: keyword matching produces false hits and misses nuance (e.g. "ceasefire collapses" vs "ceasefire holds").
* Several baselines (RSS, Reddit) only become meaningful after ~1–2 weeks of daily runs.
* From this machine, GDELT's DOC API returns HTTP 429 (Kalshi intermittently) and NRK/Reddit JSON return 403 (see `research/sources.md`).
* Insider data lags up to 2 business days, congressional trades up to 45 days, DoD data in USAspending ~90 days.
* Backtests have survivorship bias, no trading costs, few independent events, and multiple-testing risk – see `reports/backtest.md`.

## Hosting the website (not done – nothing is published)
`site/` is plain static HTML/CSS (plus `data.json`), so it can be hosted for free on GitHub Pages (push `site/` to a
private repo's `gh-pages` branch or use a Pages Action; note that Pages on private repos requires a paid plan, public repos
are free – consider whether the content should be public), Netlify / Cloudflare Pages (drag-and-drop the folder, can be
password-protected on paid tiers or via Cloudflare Access free tier). A nightly GitHub Action can run `python -m signaltool run`
and publish. Pages include `<meta name="robots" content="noindex">`.

## Files
* `research/sources.md` – every source tested, with status, key requirements and reliability label
* `research/backlog.md` – prioritised next steps
* `reports/` – daily reports and `backtest.md`
* `screenshots/` – headless-browser screenshots of the site
