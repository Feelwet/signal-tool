"""Backtest: Taiwan monthly revenue indicators -> forward sector returns.
Data for month m is public by the 10th of m+1; entry = close on first trading day on/after the 11th of m+1.
Targets: SMH vs SPY, TSM vs SPY, EWT vs SPY, MU vs SPY (memory). Split: in-sample 2013-2019, out-of-sample 2020-.
Stats: correlation + Newey-West t of cov(x,y) and top-vs-bottom tercile spread."""
from __future__ import annotations
import numpy as np, pandas as pd, yfinance as yf
from ..collectors import taiwan_revenue as tr
from .price_rules import hac_t


def run() -> str:
    ind = tr.indicators(pd.read_pickle(tr.HIST))
    ind.index = pd.PeriodIndex(ind.index, freq="M")
    sig = pd.DataFrame({
        "Kurv å/å akselerasjon (siste mnd − snitt 3 mnd før)": ind["basket"] - ind["basket"].shift(1).rolling(3).mean(),
        "Kurv å/å nivå": ind["basket"],
        "TSMC å/å akselerasjon": ind["tsmc"] - ind["tsmc"].shift(1).rolling(3).mean(),
        "Minne å/å akselerasjon": ind["memory"] - ind["memory"].shift(1).rolling(3).mean(),
        "Bredde (andel selskaper opp å/å) endring 3 mnd": ind["breadth"] - ind["breadth"].shift(3),
    })
    px = yf.download(["SMH", "TSM", "EWT", "MU", "SPY"], start="2012-06-01", auto_adjust=True, progress=False)["Close"]
    targets = {"SMH": "SMH", "TSM": "TSM", "EWT": "EWT", "MU": "MU"}
    L = ["| Signal | Mål (vs SPY) | Horisont | Periode | N | Korrelasjon | HAC t | Øverste − nederste tredjedel |", "|---|---|---|---|---|---|---|---|"]
    for sname, s in sig.items():
        for tname, tk in targets.items():
            if sname.startswith("Minne") and tk not in ("MU",):
                continue
            for h in (21, 63):
                rows = []
                for per, v in s.dropna().items():
                    entry = pd.Timestamp(per.year + (per.month == 12), per.month % 12 + 1, 11)
                    i = px.index.searchsorted(entry)
                    if i + h >= len(px):
                        continue
                    a = px[tk].iloc[i + h] / px[tk].iloc[i] - 1
                    b = px["SPY"].iloc[i + h] / px["SPY"].iloc[i] - 1
                    if np.isnan(a) or np.isnan(b):
                        continue
                    rows.append((per, v, a - b))
                df = pd.DataFrame(rows, columns=["m", "x", "y"]).set_index("m")
                for pn, sub in (("IS 2013–2019", df[df.index.year <= 2019]), ("OOS 2020–", df[df.index.year >= 2020])):
                    if len(sub) < 24:
                        continue
                    xc, yc = sub.x - sub.x.mean(), sub.y - sub.y.mean()
                    q = sub.x.quantile([1 / 3, 2 / 3])
                    spread = sub.y[sub.x >= q.iloc[1]].mean() - sub.y[sub.x <= q.iloc[0]].mean()
                    L.append(f"| {sname} | {tname} | {h} d | {pn} | {len(sub)} | {sub.x.corr(sub.y):+.2f} | {hac_t(xc * yc, h // 21 + 1):.2f} | {spread*100:+.1f} pp |")
    return "\n".join(L)


if __name__ == "__main__":
    print(run())
