import pandas as pd, yfinance as yf, time
from pathlib import Path
OUT = Path("/workspace/signal-tool/data/congress_hist")
d = pd.read_parquet(OUT / "transactions.parquet")
tk = sorted(set(d.ticker.dropna()) | {"SPY"})
frames, missing = [], []
for i in range(0, len(tk), 50):
    ch = tk[i:i+50]
    px = yf.download([t.replace(".", "-") for t in ch], start="2014-12-01", auto_adjust=True, progress=False, threads=True, group_by="ticker")
    for t in ch:
        y = t.replace(".", "-")
        try: s = px[y]["Close"].dropna() if len(ch) > 1 else px["Close"].dropna()
        except KeyError: s = pd.Series(dtype=float)
        if s.empty: missing.append(t)
        else: frames.append(pd.DataFrame({"ticker": t, "date": s.index, "adj_close": s.values}))
    time.sleep(2)
pd.concat(frames).to_parquet(OUT / "prices.parquet")
pd.Series(missing, name="ticker").to_csv(OUT / "tickers_no_prices.csv", index=False)
print("tickers", len(tk), "missing", len(missing))
