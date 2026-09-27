"""Backtest: do GDELT attention spikes on a theme lead the related ETF/commodity?

Spike = robust z of the theme's daily article share (2-day mean vs previous 60 days) >= 2.5,
10-trading-day cooldown. Entry = close of the first trading day AFTER the spike day (no look-ahead:
the GDELT daily file for day D is published early on D+1). Compared with the unconditional
distribution of same-horizon returns over the whole period (bootstrap p-value, 5000 draws)."""
from __future__ import annotations
from datetime import date
import numpy as np
import pandas as pd
import yfinance as yf
from ..anomaly import robust_z
from ..collectors import gdelt_events
from .common import fwd_returns, summarize, fmt

PAIRS = [("mideast_energy", "BZ=F"), ("mideast_energy", "XLE"), ("conflict_defense", "ITA"),
         ("conflict_defense", "RHM.DE"), ("conflict_defense", "KOG.OL"), ("shipping_chokepoints", "BDRY"),
         ("risk_off_haven", "GLD"), ("sanctions_energy", "TTF=F")]


def spikes(s: pd.Series, thr=2.5, cooldown=10, recent_n=2, baseline_n=60):
    z = pd.Series(index=s.index, dtype=float)
    for i in range(baseline_n + recent_n, len(s)):
        z.iloc[i] = robust_z(s.iloc[: i + 1], recent_n=recent_n, baseline_n=baseline_n)[0]
    ev, last = [], None
    for d, v in z.items():
        if v >= thr and (last is None or (d - last).days > cooldown * 1.4):
            ev.append(d); last = d
    return ev, z


def boot_p(sample_mean, pool: np.ndarray, n: int, draws=5000, seed=1):
    rng = np.random.default_rng(seed)
    pool = pool[~np.isnan(pool)]
    if n == 0 or len(pool) == 0:
        return np.nan
    means = rng.choice(pool, size=(draws, n), replace=True).mean(axis=1)
    return float((np.abs(means - pool.mean()) >= abs(sample_mean - pool.mean())).mean())


def run(start=date(2022, 1, 1)) -> str:
    g = gdelt_events.load_theme_series(start, date.today())
    L = ["## GDELT-oppmerksomhetstopper vs. sektor-ETF/råvare – historisk test",
         f"Data: GDELT 1.0 daglige hendelsesfiler {g.index.min().date() if len(g) else '?'}–{g.index.max().date() if len(g) else '?'} ({len(g)} dager). "
         "Topp = robust z ≥ 2,5 for temaets artikkelandel (2-dagers snitt vs 60 foregående dager), 10 handelsdagers karantene. "
         "Inngang = sluttkurs første handelsdag etter toppdagen. Sammenlignet med alle dager (ubetinget) – p-verdi via bootstrap.", "",
         "| Tema → instrument | Topper | 5d etter topp | 20d etter topp | Ubetinget 5d / 20d | p (5d / 20d) | 5d FØR topp |",
         "|---|---|---|---|---|---|---|"]
    if g.empty:
        return "\n".join(L + ["Ingen GDELT-data."])
    tick = sorted({t for _, t in PAIRS})
    px = yf.download(tick, start=str(start), progress=False, auto_adjust=True)["Close"]
    cache = {}
    for theme, t in PAIRS:
        if theme not in cache:
            cache[theme] = spikes(g[f"{theme}_share"])
        ev, _ = cache[theme]
        c = px[t].dropna()
        fr = fwd_returns(c, [d + pd.Timedelta(days=1) for d in ev], (5, 20), entry_lag=1)
        allr = fwd_returns(c, c.index[70:], (5, 20), entry_lag=1)
        s5, s20, pr = summarize(fr.get("r5", pd.Series(dtype=float))), summarize(fr.get("r20", pd.Series(dtype=float))), summarize(fr.get("r_prior5", pd.Series(dtype=float)))
        u5, u20 = allr["r5"].mean(), allr["r20"].mean()
        p5 = boot_p(s5.get("mean", np.nan), allr["r5"].values, s5.get("n", 0)) if s5.get("n", 0) > 1 else np.nan
        p20 = boot_p(s20.get("mean", np.nan), allr["r20"].values, s20.get("n", 0)) if s20.get("n", 0) > 1 else np.nan
        m = lambda s: f"{s['mean']*100:+.2f}% (hit {s['hit']*100:.0f}%)" if s.get("n", 0) > 1 else "–"
        L.append(f"| {theme} → {t} | {len(fr)} | {m(s5)} | {m(s20)} | {u5*100:+.2f}% / {u20*100:+.2f}% | {p5:.2f} / {p20:.2f} | {m(pr)} |")
    L += ["", "**Tolkning:** p-verdi = andel tilfeldige utvalg av like mange dager med minst like stort avvik fra det ubetingede snittet. "
          "p > 0,1 betyr at vi ikke kan skille signalet fra tilfeldigheter. Kolonnen «5d FØR topp» viser om prisen allerede hadde beveget seg "
          "(dvs. om nyhetstoppen kom etter markedet).",
          "**Forbehold:** Få uavhengige hendelser; GDELT-dekning og kildeutvalg endres over tid; mange temaer og instrumenter testet "
          "(multippel testing – noen «signifikante» funn forventes ved flaks); ingen kostnader."]
    return "\n".join(L)
