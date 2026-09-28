"""Random-data control ("kontroll mot overtilpasning"): is a signal's historical result better than the same number of
RANDOM entries from the same universe? For each signal we draw N_DRAWS random samples (fixed seed) and report where the real
result falls in that null distribution (percentile and one-sided p-value).

  * PEAD / PEAD-S (USA): random quarterly reports from the same point-in-time S&P 500 event table, same number per year
    (controls for the earnings-announcement drift of any report and for the market period).
    Metric: mean 60-day excess return vs the equal-weighted point-in-time universe (and share > 0).
  * Svak kurs (Oslo, red flag): on each formation date (every 21 trading days) the same number of random liquid Oslo stocks
    as were flagged that day. Metric: mean 60-day excess vs OSEBX. A useful RED flag should be clearly WORSE than random.
  * Forward log (live categories): each independent entry is replaced by a random ticker the tool logged the same day in
    the same market; shown only once a category has >= min_n matured entries (categories.track_record).

The historical parts need the backtest caches (data/cache/universe, strategy-research event table), which are not in CI,
so they are computed locally/weekly with  python -m signaltool backtest kontroll  and stored in reports/kontroll.json
(tracked in git, read by the site). The forward-log part is cheap and runs daily.
"""
from __future__ import annotations
import json, logging
from datetime import date
import numpy as np
import pandas as pd
from .config import REPORTS

log = logging.getLogger(__name__)
OUT = REPORTS / "kontroll.json"
N_DRAWS, SEED = 500, 42


def compare(real: float, null: np.ndarray, higher_is_better: bool = True) -> dict:
    """Real value vs null draws: percentile (share of draws <= real) and one-sided p-value in the 'good' direction
    (with the +1 correction, so p is never 0)."""
    null = np.asarray(null, dtype=float)
    null = null[~np.isnan(null)]
    if not len(null) or real is None or np.isnan(real):
        return {"real": None, "n_draws": int(len(null))}
    k = int((null >= real).sum()) if higher_is_better else int((null <= real).sum())
    return {"real": float(real), "null_mean": float(null.mean()), "null_p05": float(np.percentile(null, 5)),
            "null_p95": float(np.percentile(null, 95)), "percentile": float((null <= real).mean() * 100),
            "p": float((k + 1) / (len(null) + 1)), "n_draws": int(len(null)), "better": "høyere" if higher_is_better else "lavere"}


def stratified_null(pool: pd.DataFrame, sig: pd.DataFrame, col: str, by: str, n_draws=N_DRAWS, seed=SEED) -> tuple[np.ndarray, np.ndarray]:
    """Mean and hit rate of `col` for n_draws random samples from `pool` with the same count per `by` value as `sig`."""
    rng = np.random.default_rng(seed)
    need = sig[by].value_counts()
    groups = {k: pool.loc[pool[by] == k, col].dropna().to_numpy() for k in need.index}
    means, hits = np.empty(n_draws), np.empty(n_draws)
    for i in range(n_draws):
        x = np.concatenate([rng.choice(groups[k], size=min(int(n), len(groups[k])), replace=len(groups[k]) < n) if len(groups[k]) else np.array([])
                            for k, n in need.items()])
        means[i], hits[i] = (x.mean(), (x > 0).mean()) if len(x) else (np.nan, np.nan)
    return means, hits


def _result(label: str, sig_x: pd.Series, means, hits, higher: bool, **meta) -> dict:
    x = pd.Series(sig_x, dtype=float).dropna()
    return {"label": label, "n": int(len(x)), "mean": compare(float(x.mean()), means, higher),
            "hit": compare(float((x > 0).mean()), hits, higher), **meta}


# ---------------------------------------------------------------- historical (local caches)
def pead(n_draws=N_DRAWS, seed=SEED) -> dict:
    from .backtest.base_rates import PIT_EVENTS
    if not PIT_EVENTS.exists():
        return {}
    E = pd.read_pickle(PIT_EVENTS)
    R = E[E["pit"]].dropna(subset=["x60"]).copy()
    site = (R["surprise"] >= 15) & (R["ear_spy"] >= 0.04)
    hv = R["q_vol"] > 0.5
    out = {}
    for key, lab, m in (("pead", "Sterk kvartalsrapport (PEAD, USA)", site), ("pead_s", "PEAD-S (USA)", site & hv)):
        S = R[m]
        means, hits = stratified_null(R, S, "x60", "qtr", n_draws, seed)
        out[key] = _result(lab, S["x60"], means, hits, True, horizon=60, period=f"{S['date'].min():%Y}–{S['date'].max():%Y}",
                           null="tilfeldige kvartalsrapporter fra samme punkt-i-tid S&P 500-univers, samme antall per kvartal",
                           bench="likevektet punkt-i-tid-univers")
    # stricter null for PEAD-S: random reports from equally volatile stocks (volatility above median) in the same quarter
    H = R[hv]
    S = R[site & hv]
    means, hits = stratified_null(H, S, "x60", "qtr", n_draws, seed)
    out["pead_s_vol"] = _result("PEAD-S mot tilfeldige rapporter i like volatile aksjer (USA)", S["x60"], means, hits, True, horizon=60,
                                period=f"{S['date'].min():%Y}–{S['date'].max():%Y}",
                                null="tilfeldige kvartalsrapporter fra aksjer med volatilitet over median, samme antall per kvartal",
                                bench="likevektet punkt-i-tid-univers")
    return out


def oslo_panel() -> pd.DataFrame:
    """(date, ticker, liquid, weak, x60) every 21 trading days for the Oslo universe (repaired prices, backtest cache)."""
    from .backtest import universe
    from .oslo_flags import MIN_ADV_NOK
    data = universe.oslo()
    if not data or "OSEBX.OL" not in data:
        return pd.DataFrame()
    C = pd.DataFrame({t: d["Close"] for t, d in data.items()}).sort_index().ffill(limit=3)
    V = pd.DataFrame({t: d["Volume"] for t, d in data.items()}).reindex(C.index)
    H = pd.DataFrame({t: d["High"] for t, d in data.items()}).reindex(C.index).ffill(limit=3)
    adv = (C * V).rolling(20, min_periods=10).median()
    mom = C.shift(21) / C.shift(252) - 1
    hmax = H.rolling(252, min_periods=240).max()
    hi52 = C / hmax
    F = C.shift(-61) / C.shift(-1) - 1
    X = F.sub(F["OSEBX.OL"], axis=0)
    rows = []
    for d in C.index[260::21]:
        if d > C.index[-62]:
            break
        cols = [t for t in C.columns if t != "OSEBX.OL"]
        df = pd.DataFrame({"adv": adv.loc[d, cols], "close": C.loc[d, cols], "mom": mom.loc[d, cols], "hi52": hi52.loc[d, cols], "x60": X.loc[d, cols]})
        df = df[(df["adv"] >= MIN_ADV_NOK) & (df["close"] >= 1.0)].dropna(subset=["x60"])
        if len(df) < 20:
            continue
        qm, qh = df["mom"].quantile(0.2), df["hi52"].quantile(0.2)
        df["weak"] = (df["mom"] <= qm) | (df["hi52"] <= qh)
        df["date"] = d
        rows.append(df.reset_index(names="ticker"))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def oslo_weak(n_draws=N_DRAWS, seed=SEED, panel: pd.DataFrame | None = None) -> dict:
    P = oslo_panel() if panel is None else panel
    if P.empty:
        return {}
    S = P[P["weak"]]
    means, hits = stratified_null(P, S, "x60", "date", n_draws, seed)
    return {"weak_px": _result("Svak kurs (Oslo, rødt flagg)", S["x60"], means, hits, False, horizon=60,
                               period=f"{S['date'].min():%Y}–{S['date'].max():%Y}", n_dates=int(S["date"].nunique()),
                               null="like mange tilfeldige likvide Oslo-aksjer på hver formasjonsdato (hver 21. handelsdag)",
                               bench="OSEBX")}


def build(n_draws=N_DRAWS, seed=SEED) -> dict:
    out = {"_meta": {"computed": date.today().isoformat(), "n_draws": n_draws, "seed": seed,
                     "what": "Faktisk resultat mot samme antall tilfeldige inngangspunkter fra samme univers (bootstrap)."}}
    for fn in (pead, oslo_weak):
        try:
            out.update(fn(n_draws, seed))
        except Exception as ex:
            log.warning("kontroll %s failed: %s", fn.__name__, ex)
    old = load()
    for k, v in old.items():        # keep earlier results for parts whose data is missing on this machine
        out.setdefault(k, v)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def load() -> dict:
    try:
        return json.loads(OUT.read_text())
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- forward log (daily, cheap)
def forward(logdf: pd.DataFrame, closes: dict, min_n: int, h: int = 20, n_draws: int = 300, seed: int = SEED) -> dict:
    """Live forward log: real mean h-day excess per category vs random tickers logged the same day in the same market."""
    from . import categories as C
    out = {"h": h, "min_n": min_n, "cats": {}}
    if logdf is None or logdf.empty or not closes:
        return out
    L = logdf[logdf["ticker"].map(C.loggable)].copy()
    L["bench"] = L["ticker"].map(C.benchmark_for)
    ent = C.entries(L)
    pool = {k: g["ticker"].unique() for k, g in L.groupby(["date", "bench"])}
    rng = np.random.default_rng(seed)
    for cat in C.CAT_NO:
        e = ent[ent["category"] == cat] if len(ent) else ent
        st = {"missing": set(), "stopped": set()}
        real = [v for _, v in C._outcomes(e, closes, h, st)] if len(e) else []
        r = {"n": len(real)}
        if len(real) >= min_n:
            means = np.empty(n_draws)
            for i in range(n_draws):
                fake = e.copy()
                fake["ticker"] = [rng.choice(pool[(d, b)]) for d, b in zip(fake["date"], fake["bench"])]
                o = [v for _, v in C._outcomes(fake, closes, h, {"missing": set(), "stopped": set()})]
                means[i] = np.mean(o) if o else np.nan
            r.update(compare(float(np.mean(real)), means, True))
        out["cats"][cat] = r
    return out
