"""Supply-chain bottleneck radar: Taiwan listed companies' monthly revenue (MOPS, free, no key).
Taiwanese firms must publish last month's revenue by the 10th - one of the fastest hard datapoints on AI/semiconductor
and electronics demand (weeks before US quarterly reports). Source: https://mopsov.twse.com.tw (monthly summary pages).
We track a fixed basket of AI/semiconductor supply-chain names plus breadth across all ~1000 listed companies."""
from __future__ import annotations
import io, logging
from datetime import date
import pandas as pd
from .. import http
from ..config import CACHE

log = logging.getLogger(__name__)
URL = "https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{roc}_{m}_0.html"
HIST = CACHE / "taiwan_revenue.pkl"
BASKET = {"2330": "TSMC", "2317": "Hon Hai (Foxconn)", "2454": "MediaTek", "2382": "Quanta (AI-servere)", "3231": "Wistron",
          "2308": "Delta Electronics (strøm/kjøling)", "3711": "ASE (pakking/testing)", "6669": "Wiwynn (AI-servere)",
          "3037": "Unimicron (substrat)", "2345": "Accton (nettverk)", "2408": "Nanya (DRAM)", "2344": "Winbond (minne)"}
AI_SERVER = ["2382", "3231", "6669", "2317"]
MEMORY = ["2408", "2344"]


def month_table(y: int, m: int) -> pd.DataFrame:
    """All listed companies' revenue for calendar month y-m (thousand TWD). Empty if not yet published."""
    old = (date.today().year * 12 + date.today().month) - (y * 12 + m) > 2
    r = http.get(URL.format(roc=y - 1911, m=m), cache_hours=24 * 365 if old else 12, timeout=40)
    txt = r.content.decode("big5", errors="replace")
    rows = []
    for t in pd.read_html(io.StringIO(txt)):
        if t.shape[1] < 10:
            continue
        t = t.iloc[:, :7]
        t.columns = ["code", "name", "rev", "rev_prev_m", "rev_ly", "mom_pct", "yoy_pct"]
        rows.append(t)
    if not rows:
        return pd.DataFrame()
    df = pd.concat(rows)
    df = df[df["code"].astype(str).str.fullmatch(r"\d{4}")]
    for c in ["rev", "rev_prev_m", "rev_ly", "mom_pct", "yoy_pct"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["code"] = df["code"].astype(str)
    return df.drop_duplicates("code").set_index("code")


def history(start=(2014, 1)) -> pd.DataFrame:
    """Long table (month, code, rev, rev_ly). Cached; only new months are fetched."""
    have = pd.read_pickle(HIST) if HIST.exists() else pd.DataFrame()
    y, m = start
    today = date.today()
    frames = [have] if len(have) else []
    done = set(have["month"].unique()) if len(have) else set()
    while (y, m) < (today.year, today.month):
        key = f"{y}-{m:02d}"
        recent = (today.year * 12 + today.month) - (y * 12 + m) <= 2
        if key not in done or recent:
            try:
                t = month_table(y, m)
                if len(t):
                    t = t.reset_index()[["code", "name", "rev", "rev_ly", "yoy_pct"]].assign(month=key)
                    frames = [f[f["month"] != key] if len(f) else f for f in frames] + [t]
            except Exception as ex:
                log.info("taiwan %s: %s", key, ex)
        m += 1
        if m > 12:
            y, m = y + 1, 1
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(df):
        df.to_pickle(HIST)
    return df


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly indicators: basket YoY (sum of revenue vs same month last year), AI-server, memory, breadth (% with YoY>0)."""
    out = {}
    for mth, g in df.groupby("month"):
        g = g.set_index("code")
        row = {}
        for lab, codes in (("basket", list(BASKET)), ("ai_server", AI_SERVER), ("memory", MEMORY), ("tsmc", ["2330"])):
            s = g.reindex(codes).dropna(subset=["rev", "rev_ly"])
            s = s[s["rev_ly"] > 0]
            row[lab] = float(s["rev"].sum() / s["rev_ly"].sum() - 1) if len(s) >= max(1, len(codes) // 2) else None
        v = g[(g["rev_ly"] > 0) & g["rev"].notna()]
        row["breadth"] = float((v["rev"] > v["rev_ly"]).mean()) if len(v) > 100 else None
        row["n"] = len(v)
        out[mth] = row
    return pd.DataFrame(out).T.sort_index()


def collect() -> tuple[dict, str]:
    try:
        df = history(start=(2023, 1))
        ind = indicators(df)
    except Exception as ex:
        return {}, f"FAILED: {ex}"
    if ind.empty:
        return {}, "FAILED: ingen data"
    last = ind.index[-1]
    g = df[df["month"] == last].set_index("code")
    firms = []
    for c, n in BASKET.items():
        if c in g.index:
            r = g.loc[c]
            firms.append({"code": c, "name": n, "rev_bn_twd": round(float(r["rev"]) / 1e6, 2), "yoy": None if pd.isna(r["yoy_pct"]) else round(float(r["yoy_pct"]) / 100, 4)})
    series = {k: [None if pd.isna(x) else round(float(x), 4) for x in ind[k].iloc[-24:]] for k in ("basket", "ai_server", "memory", "tsmc", "breadth")}
    ai = ind["basket"].dropna()
    accel = float(ai.iloc[-3:].mean() - ai.iloc[-6:-3].mean()) if len(ai) >= 6 else None
    out = {"month": last, "months": list(ind.index[-24:]), "series": series, "firms": firms, "accel_3m": None if accel is None else round(accel, 4),
           "latest": {k: None if pd.isna(ind[k].iloc[-1]) else round(float(ind[k].iloc[-1]), 4) for k in ("basket", "ai_server", "memory", "tsmc", "breadth")}}
    return out, f"ok (siste måned {last}, kurv {out['latest']['basket']*100:+.1f} % å/å)" if out["latest"]["basket"] is not None else f"ok (siste måned {last})"
