"""Backtest: do big daily moves in geopolitical prediction markets (Polymarket) lead sector ETFs?
Markets: high-volume (>= $2M) geopolitics/world markets, closed and open, daily price history (CLOB prices-history).
Direction by keywords: escalation (strike, war, invade, forces enter, attack, closes, blockade, military) = +1,
de-escalation (ceasefire, peace, deal, agreement, ends, talks, sanctions lifted) = -1. Event = |dp| >= 10 pp in a day
with p between 5 % and 95 % before the move; one event per (event group, day), largest move kept.
Target: sign-adjusted return of the theme ETF minus SPY. We measure the SAME day (coincident) and the NEXT 1 and 5
trading days AFTER the move day (tradable). Polymarket daily points are UTC ~00:00, so the move for day d is known before
the US open of day d+1 -> 'next' starts at close of d (conservative: we skip the rest of d)."""
from __future__ import annotations
import json, re
import numpy as np, pandas as pd, yfinance as yf
from .. import http
from .price_rules import hac_t

GAMMA = "https://gamma-api.polymarket.com/events"
ESC = re.compile(r"strike|war\b|invade|invasion|forces enter|attack|closes|blockade|military|troops|nuclear test|bomb|capture|seize|clash", re.I)
DEESC = re.compile(r"ceasefire|cease-fire|peace|deal|agreement|ends\b|talks|lifted|normaliz|truce|withdraw", re.I)
ETF = [(re.compile(r"iran|israel|hezbollah|hormuz|houthi|yemen|gaza|hamas|saudi|gulf|venezuela|oil|crude", re.I), "XLE"),
       (re.compile(r"russia|ukraine|putin|zelensk|nato|crimea|donbas|kyiv|moscow", re.I), "ITA"),
       (re.compile(r"china|taiwan|xi jinping|beijing", re.I), "SMH")]
TAIWAN_SIGN = {"SMH": -1}   # escalation around China/Taiwan is negative for semis


def markets(min_vol=2e6):
    out = []
    for tag in ("geopolitics", "world"):
        for closed in ("true", "false"):
            for off in range(0, 500, 100):
                try:
                    evs = http.get_json(GAMMA, params={"tag_slug": tag, "closed": closed, "limit": 100, "offset": off, "order": "volume", "ascending": "false"}, cache_hours=24)
                except Exception:
                    break
                if not evs:
                    break
                for e in evs:
                    for m in e.get("markets", []):
                        v = float(m.get("volumeNum") or m.get("volume") or 0)
                        q = (m.get("question") or "") + " " + (e.get("title") or "")
                        etf = next((t for rx, t in ETF if rx.search(q)), None)
                        esc, de = bool(ESC.search(q)), bool(DEESC.search(q))
                        if v < min_vol or etf is None or esc == de:
                            continue
                        try:
                            tok = json.loads(m["clobTokenIds"])[0]
                        except Exception:
                            continue
                        out.append({"group": e.get("title"), "question": m.get("question"), "token": tok, "etf": etf,
                                    "sign": (1 if esc else -1) * TAIWAN_SIGN.get(etf, 1), "volume": v})
    return pd.DataFrame(out).drop_duplicates("token")


def history(tok):
    j = http.get_json("https://clob.polymarket.com/prices-history", params={"market": tok, "interval": "max", "fidelity": 1440}, cache_hours=24 * 7)
    h = j.get("history", [])
    if not h:
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(x["t"], unit="s").normalize(): float(x["p"]) for x in h})
    return s[~s.index.duplicated(keep="last")].sort_index()


def run():
    M = markets()
    rows = []
    for m in M.itertuples():
        try:
            s = history(m.token)
        except Exception:
            continue
        if len(s) < 5:
            continue
        d = s.diff()
        prev = s.shift()
        for day, dp in d.items():
            if abs(dp) >= 0.10 and 0.05 <= prev.get(day, np.nan) <= 0.95:
                rows.append({"group": m.group, "day": day, "dp": dp, "sign": m.sign, "etf": m.etf, "q": m.question})
    E = pd.DataFrame(rows)
    if E.empty:
        return "Ingen hendelser."
    E["abs"] = E["dp"].abs()
    E = E.sort_values("abs", ascending=False).drop_duplicates(["group", "day"])
    px = yf.download(["XLE", "ITA", "SMH", "SPY"], start="2023-01-01", auto_adjust=True, progress=False)["Close"]
    idx = px.index
    res = []
    for r in E.itertuples():
        # Polymarket day label = UTC date of the price point (~00:00) -> the move happened during the previous UTC day
        move_day = r.day - pd.Timedelta(days=1)
        i = idx.searchsorted(move_day)
        if i >= len(idx) - 6 or i < 1:
            continue
        direction = np.sign(r.dp) * r.sign  # +1 = news points to ETF up
        def rel(a, b):
            return (px[r.etf].iloc[b] / px[r.etf].iloc[a] - 1) - (px["SPY"].iloc[b] / px["SPY"].iloc[a] - 1)
        same = rel(i - 1, i) if idx[i] == move_day else np.nan
        res.append({"day": r.day, "etf": r.etf, "dir": direction, "same": direction * same if same == same else np.nan,
                    "next1": direction * rel(i, i + 1), "next5": direction * rel(i, i + 5), "q": r.q, "dp": r.dp})
    R = pd.DataFrame(res)
    R["w"] = R["day"].dt.to_period("W")
    L = [f"## Polymarket-bevegelse → sektor-ETF (retningsjustert, minus SPY)",
         f"_{len(M)} markeder (volum ≥ $2M, geopolitikk/verden), {len(R)} hendelser (|endring| ≥ 10 pp på en dag) {R['day'].min():%Y-%m-%d}–{R['day'].max():%Y-%m-%d}. "
         "Positivt tall = ETF beveget seg i retningen nyheten tilsier. t = Newey-West på ukesnitt. Merk: perioden domineres av få episoder (særlig USA–Iran 2026)._", "",
         "| Mål | ETF | N | Snitt | Andel riktig retning | t |", "|---|---|---|---|---|---|"]
    for etf, g in list(R.groupby("etf")) + [("alle", R)]:
        for col, lab in (("same", "Samme dag (samtidig)"), ("next1", "Neste handelsdag"), ("next5", "Neste 5 handelsdager")):
            x = g[col].dropna()
            if len(x) < 5:
                continue
            wk = g.dropna(subset=[col]).groupby("w")[col].mean()
            L.append(f"| {lab} | {etf} | {len(x)} | {x.mean()*100:+.2f} % | {(x > 0).mean():.0%} | {hac_t(wk, 1):.1f} |")
    return "\n".join(L)


if __name__ == "__main__":
    print(run())
