"""Red-flag tests on Oslo Børs with the same setup as price_rules.py (formation every 21 trading days, liquid stocks,
h=20/60, spread vs all, net vs OSEBX after 0.4 %, HAC t, IS < 2018-07-01 <= OOS).
Flags: high 60d realised vol (top 20 %), private placement last 60 trading days (Newsweb titles, 2019- only),
negative TTM EBIT (NOT TESTABLE: repo only has latest annual EBIT, no point-in-time history)."""
from __future__ import annotations
import json
import numpy as np, pandas as pd
from . import universe
from .price_rules import run_market, hac_t, COST
from ..config import CACHE
from ..oslo_flags import PLACEMENT, NOT_PLACEMENT

SPLIT = "2018-07-01"


def stats(P, g):
    out = {}
    for per, mask in (("is", P["date"] < SPLIT), ("oos", P["date"] >= SPLIT)):
        S = P[mask]
        for h in (20, 60):
            uni = S.groupby("date")[f"f{h}"].mean()
            G = S[S[g] == True]
            grp = G.groupby("date")[f"f{h}"].mean()
            spread = (grp - uni.reindex(grp.index)).dropna()
            lags = 0 if h == 20 else 3
            out[(per, h)] = {"n_dates": len(spread), "avg_n": float(G.groupby("date").size().mean()) if len(grp) else 0.0,
                             "spread": float(spread.mean()) if len(spread) else np.nan, "t_spread": hac_t(spread, lags),
                             "net": float(grp.mean() - COST["OSLO"]) if len(grp) else np.nan, "t_net": hac_t(grp - COST["OSLO"], lags),
                             "from": str(S["date"].min().date()) if len(S) else "", "to": str(S["date"].max().date()) if len(S) else ""}
    return out


def main():
    osl = universe.oslo()
    _, P = run_market("OSLO", osl, "OSEBX.OL", 0.095, SPLIT)
    P = P.copy(); P["ticker"] = P.index; P = P.reset_index(drop=True)
    C = pd.DataFrame({t: d["Close"] for t, d in osl.items()}).sort_index().ffill(limit=3)
    vol = np.log(C).diff().rolling(60, min_periods=50).std() * np.sqrt(252)
    P["vol60"] = [vol.at[d, t] for d, t in zip(P["date"], P["ticker"])]
    P["vol_top"] = P.groupby("date")["vol60"].rank(pct=True) >= 0.8
    # placements (Newsweb list covers 2019-01-01 ->)
    nw = pd.read_pickle(CACHE / "newsweb_all_list.pkl")
    t_ = nw["title"].fillna("")
    pl = nw[t_.str.contains(PLACEMENT) & ~t_.str.contains(NOT_PLACEMENT)].copy()
    pub = pl["published"].dt.tz_convert("Europe/Oslo")
    pl["d0"] = [(p + pd.Timedelta(days=1)).normalize().tz_localize(None) if (p.hour, p.minute) >= (16, 20) else p.normalize().tz_localize(None) for p in pub]
    pl["ticker"] = pl["issuer"] + ".OL"
    idx = C.index
    ev = {}
    for r in pl.itertuples():
        ev.setdefault(r.ticker, []).append(idx.searchsorted(r.d0))
    nw_start = pd.Timestamp("2019-01-01") + pd.Timedelta(days=90)  # need full 60 trading-day lookback
    def plflag(d, t):
        i = idx.get_loc(d)
        return any(i - 60 < j <= i for j in ev.get(t, []))
    P["placement"] = [plflag(d, t) for d, t in zip(P["date"], P["ticker"])]
    Pp = P[P["date"] >= nw_start]
    res = {"vol_top": stats(P, "vol_top"), "placement": stats(Pp, "placement"), "mom_bot": stats(P, "mom_bot")}
    meta = {"n_placement_msgs": int(len(pl)), "n_placement_tickers_in_universe": int(len(set(pl["ticker"]) & set(C.columns))),
            "placement_sample": f"{Pp['date'].min().date()}–{Pp['date'].max().date()}", "n_dates_total": int(P["date"].nunique()),
            "avg_universe": float(P.groupby("date").size().mean())}
    json.dump({k: {f"{a}_{b}": v for (a, b), v in d.items()} for k, d in res.items()} | {"meta": meta},
              open("logs/red_flags_raw.json", "w"), indent=1, default=float)
    print(json.dumps(meta)); 
    for k, d in res.items():
        for (a, b), v in d.items():
            print(k, a, b, {x: (round(y, 4) if isinstance(y, float) else y) for x, y in v.items()})


if __name__ == "__main__":
    main()
