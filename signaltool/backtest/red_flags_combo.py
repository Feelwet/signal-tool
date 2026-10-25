""">=2 red flags vs exactly 1 vs all (Oslo), same setup as red_flags.py. Placement flag only counted from 2019-04 (Newsweb)."""
from __future__ import annotations
import json
import numpy as np, pandas as pd
from . import universe
from .price_rules import run_market, hac_t, COST
from ..config import CACHE
from ..oslo_flags import PLACEMENT, NOT_PLACEMENT

SPLIT = "2018-07-01"
NW_START = pd.Timestamp("2019-04-01")


def build():
    osl = universe.oslo()
    _, P = run_market("OSLO", osl, "OSEBX.OL", 0.095, SPLIT)
    P = P.copy(); P["ticker"] = P.index; P = P.reset_index(drop=True)
    C = pd.DataFrame({t: d["Close"] for t, d in osl.items()}).sort_index().ffill(limit=3)
    vol = np.log(C).diff().rolling(60, min_periods=50).std() * np.sqrt(252)
    P["vol60"] = [vol.at[d, t] for d, t in zip(P["date"], P["ticker"])]
    P["vol_top"] = P.groupby("date")["vol60"].rank(pct=True) >= 0.8
    nw = pd.read_pickle(CACHE / "newsweb_all_list.pkl")
    t_ = nw["title"].fillna("")
    pl = nw[t_.str.contains(PLACEMENT) & ~t_.str.contains(NOT_PLACEMENT)].copy()
    pub = pl["published"].dt.tz_convert("Europe/Oslo")
    pl["d0"] = [(p + pd.Timedelta(days=1)).normalize().tz_localize(None) if (p.hour, p.minute) >= (16, 20) else p.normalize().tz_localize(None) for p in pub]
    idx = C.index; ev = {}
    for r in pl.itertuples():
        ev.setdefault(r.issuer + ".OL", []).append(idx.searchsorted(r.d0))
    P["placement"] = [d >= NW_START and any(idx.get_loc(d) - 60 < j <= idx.get_loc(d) for j in ev.get(t, [])) for d, t in zip(P["date"], P["ticker"])]
    P["nflag"] = P["mom_bot"].astype(int) + P["vol_top"].astype(int) + P["placement"].astype(int)
    return P


def main():
    P = build()
    out = {}
    for per, mask in (("is", P["date"] < SPLIT), ("oos", P["date"] >= SPLIT)):
        S = P[mask]
        for h in (20, 60):
            lags = 0 if h == 20 else 3
            uni = S.groupby("date")[f"f{h}"].mean()
            g2 = S[S.nflag >= 2].groupby("date")[f"f{h}"].mean()
            g1 = S[S.nflag == 1].groupby("date")[f"f{h}"].mean()
            for name, g in (("ge2", g2), ("eq1", g1)):
                sp = (g - uni.reindex(g.index)).dropna()
                n = S[(S.nflag >= 2) if name == "ge2" else (S.nflag == 1)].groupby("date").size()
                out[f"{name}_{per}_{h}"] = {"n_dates": len(sp), "avg_n": float(n.mean()), "spread": float(sp.mean()), "t_spread": hac_t(sp, lags),
                                            "net": float(g.mean() - COST["OSLO"]), "t_net": hac_t(g - COST["OSLO"], lags)}
            d = (g2 - g1.reindex(g2.index)).dropna()
            out[f"ge2_vs_eq1_{per}_{h}"] = {"n_dates": len(d), "diff": float(d.mean()), "t": hac_t(d, lags)}
    pl_share = float(P[(P.date >= NW_START) & (P.nflag >= 2)]["placement"].mean())
    out["meta"] = {"placement_share_in_ge2_oos": pl_share}
    json.dump(out, open("logs/red_flags_combo_raw.json", "w"), indent=1)
    for k, v in out.items():
        print(k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()})


if __name__ == "__main__":
    main()
