"""Oslo Børs event studies with honest controls.
  * Short interest (Finanstilsynet register history, 2012-): monthly snapshots; groups by 30-day change / level.
  * Primary-insider trades classified from Newsweb message text (kjøp / salg), 2021-.
Returns: excess vs OSEBX from next-day close (no look-ahead: register/notice is public the same evening),
and vs the equal-weighted average of all liquid universe stocks on the same dates (cancels part of the survivorship bias:
our price universe = today's listed issuers). Costs 0.4 % round trip. t = Newey-West on monthly means.
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
from . import universe
from .price_rules import hac_t
from ..collectors import shorts as S
from ..collectors.newsweb_insider import classify, BODY_DIR
from ..config import CACHE

COST = 0.004
MIN_ADV_NOK = 5e6


def _prices():
    data = universe.oslo()
    C = pd.DataFrame({t: d["Close"] for t, d in data.items()}).sort_index().ffill(limit=3)
    V = pd.DataFrame({t: d["Volume"] for t, d in data.items()}).reindex(C.index)
    adv = (C * V).rolling(20).median()
    return C, adv


def fwd(C, h):
    return C.shift(-h - 1) / C.shift(-1) - 1   # entry next day close, hold h days


def evaluate(ev: pd.DataFrame, C, adv, split: str, label: str, horizons=(20, 60)) -> list[dict]:
    """ev: columns ticker, date (Timestamp, public on that date). One row per group label in ev['group']."""
    out = []
    bench = C["OSEBX.OL"]
    for h in horizons:
        F = fwd(C, h)
        fb = fwd(bench.to_frame(), h).iloc[:, 0]
        liq = adv >= MIN_ADV_NOK
        univ = F.where(liq).sub(fb, axis=0).mean(axis=1)   # equal-weight liquid universe excess on each date
        rows = []
        for r in ev.itertuples():
            if r.ticker not in C.columns:
                continue
            i = C.index.searchsorted(r.date)
            if i >= len(C) - h - 2:
                continue
            d = C.index[i]
            a = adv.at[d, r.ticker]
            if not (a >= MIN_ADV_NOK):
                continue
            x = F.at[d, r.ticker]
            if np.isnan(x) or np.isnan(fb.at[d]):
                continue
            rows.append({"group": r.group, "date": d, "ticker": r.ticker, "xs": x - fb.at[d], "vs_univ": x - fb.at[d] - univ.at[d]})
        R = pd.DataFrame(rows)
        if R.empty:
            continue
        R["m"] = R["date"].dt.to_period("M")
        for per, sub in (("in-sample", R[R["date"] < split]), ("out-of-sample", R[R["date"] >= split])):
            for g, gg in sub.groupby("group"):
                mm = gg.groupby("m")[["xs", "vs_univ"]].mean()
                out.append({"signal": label, "group": g, "h": h, "period": f"{per} {gg['date'].min():%Y-%m}–{gg['date'].max():%Y-%m}",
                            "n": len(gg), "n_tick": gg["ticker"].nunique(), "xs": gg["xs"].mean(), "net": gg["xs"].mean() - COST,
                            "t_net": hac_t(mm["xs"] - COST, 2), "vs_univ": gg["vs_univ"].mean(), "t_univ": hac_t(mm["vs_univ"], 2)})
    return out


def short_events(C) -> pd.DataFrame:
    import requests
    from .. import http
    j = http.get_json(S.API, cache_hours=24, timeout=120)
    L = pd.read_pickle(CACHE / "newsweb_insider_list.pkl")
    lut = {S._norm(n): s for s, n in zip(L["issuer"], L["issuer_name"])}
    dates = C.index[C.index >= "2013-01-01"][::21]
    rows = []
    for ins in j:
        t = lut.get(S._norm(ins["issuerName"]))
        if not t or f"{t}.OL" not in C.columns or not ins.get("events"):
            continue
        s = pd.Series({pd.Timestamp(e["date"][:10]): e["shortPercent"] for e in ins["events"]}).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        for d in dates:
            if d < s.index[0]:
                continue
            now = s[s.index <= d].iloc[-1]
            prev = s[s.index <= d - pd.Timedelta(days=30)]
            prev = prev.iloc[-1] if len(prev) else 0.0
            ch = now - prev
            g = []
            if ch >= 0.5: g.append("Short økt ≥ 0,5 pp på 30 d")
            if ch <= -0.5: g.append("Short redusert ≥ 0,5 pp på 30 d")
            if now >= 3: g.append("Short-nivå ≥ 3 %")
            for x in g:
                rows.append({"ticker": f"{t}.OL", "date": d, "group": x})
    return pd.DataFrame(rows)


def insider_events() -> pd.DataFrame:
    L = pd.read_pickle(CACHE / "newsweb_insider_list.pkl")
    rows = []
    for r in L.itertuples():
        p = BODY_DIR / f"{r.id}.json"
        if not p.exists():
            continue
        b = json.loads(p.read_text()).get("body", "")
        c = classify((r.title or "") + ". " + b)
        if c["kind"] not in ("kjøp", "salg"):
            continue
        ts = pd.Timestamp(r.published).tz_convert("Europe/Oslo")
        d = pd.Timestamp(ts.date()) + (pd.Timedelta(days=1) if ts.hour >= 16 else pd.Timedelta(0))  # after close -> next day
        rows.append({"ticker": f"{r.issuer}.OL", "date": d, "kind": c["kind"], "value": c["value_nok"], "id": r.id})
    E = pd.DataFrame(rows)
    if E.empty:
        return E
    out = [E[E.kind == "kjøp"].assign(group="Innsidekjøp (alle)"), E[E.kind == "salg"].assign(group="Innsidesalg (alle)")]
    big = E[(E.kind == "kjøp") & (E.value >= 1e6)]
    out.append(big.assign(group="Innsidekjøp ≥ NOK 1 mill."))
    # cluster: >= 2 separate buy notices in the same company within 14 days (event dated at the 2nd notice)
    b = E[E.kind == "kjøp"].sort_values("date")
    cl = []
    for t, g in b.groupby("ticker"):
        ds = g["date"].tolist()
        last = None
        for i in range(1, len(ds)):
            if (ds[i] - ds[i - 1]).days <= 14 and (last is None or (ds[i] - last).days > 30):
                cl.append({"ticker": t, "date": ds[i]}); last = ds[i]
    out.append(pd.DataFrame(cl).assign(group="Innsidekjøp-klynge (≥ 2 meldinger på 14 d)"))
    return pd.concat(out, ignore_index=True)[["ticker", "date", "group"]].drop_duplicates()


def table(res: list[dict], title: str, note: str) -> str:
    L = [f"## {title}", f"_{note}_", "", "| Gruppe | Horisont | Periode | N (aksjer) | Meravk. vs OSEBX | Netto (t) | Mot snitt av likvide aksjer (t) |", "|---|---|---|---|---|---|---|"]
    for r in res:
        L.append(f"| {r['group']} | {r['h']} d | {r['period']} | {r['n']} ({r['n_tick']}) | {r['xs']*100:+.2f} % | {r['net']*100:+.2f} % ({r['t_net']:.1f}) | {r['vs_univ']*100:+.2f} pp ({r['t_univ']:.1f}) |")
    return "\n".join(L)


def run(which=("short", "insider")) -> str:
    C, adv = _prices()
    parts = []
    if "short" in which:
        ev = short_events(C)
        parts.append(table(evaluate(ev, C, adv, "2019-01-01", "short"), "Shortposisjoner Oslo Børs (Finanstilsynet) → senere avkastning",
                           f"{len(ev):,} månedlige observasjoner {ev['date'].min():%Y-%m}–{ev['date'].max():%Y-%m} (API-et har bare historikk fra da – derfor ingen in-sample-periode). Kurs-univers = dagens noterte selskaper (overlevelsesskjevhet); "
                           "kolonnen «mot snitt av likvide aksjer» korrigerer delvis for dette."))
    if "insider" in which:
        ev = insider_events()
        if len(ev):
            parts.append(table(evaluate(ev, C, adv, "2024-01-01", "insider"), "Innsidehandel Oslo Børs (retning lest fra Newsweb-meldingen) → senere avkastning",
                               f"{len(ev):,} hendelser fra meldinger 2021– (klassifisert automatisk; kjøp/salg, ikke opsjoner/program). In-sample 2021–2023, out-of-sample 2024–. "
                               "Inngang = sluttkurs dagen etter publisering."))
    return "\n\n".join(parts)


if __name__ == "__main__":
    import sys
    print(run(tuple(sys.argv[1:]) or ("short", "insider")))
