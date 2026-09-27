"""'Hva bør jeg se på i dag?' (3-5 prioritised items), 'Nytt siden i går' (diff vs the previous dated snapshot) and
alert flags. Pure functions over snapshot dicts -> easy to test; no network."""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path
from .config import DATA

SNAP_DIR = DATA / "snapshots"
CAT_NO = {"kjop": "Kjøp-kandidat", "hold": "Hold", "watch": "Watchlist"}
CAT_RANK = {"kjop": 2, "hold": 1, "watch": 0}


def previous_snapshot(snap: dict, snap_dir: Path = SNAP_DIR) -> dict | None:
    """Most recent dated snapshot strictly before this snapshot's date."""
    cur = snap.get("date", "")
    files = sorted(p for p in snap_dir.glob("20??-??-??.json") if p.stem < cur)
    for p in reversed(files):
        try:
            return json.loads(p.read_text())
        except Exception:
            continue
    return None


def _pct(x, d=0):
    return "–" if x is None else f"{x*100:+.{d}f} %"


def changes(snap: dict, prev: dict | None) -> dict:
    if not prev:
        return {"prev_date": None, "items": [], "note": "Første kjøring med lagret historikk – endringer vises fra neste dag."}
    items = []
    pt = {e["ticker"]: e for e in prev.get("tickers", [])}
    ct = {e["ticker"]: e for e in snap.get("tickers", [])}
    for t, e in ct.items():
        c, p = e.get("category"), (pt.get(t) or {}).get("category")
        if t not in pt:
            if c in ("kjop", "hold"):
                items.append({"kind": "ny", "level": "alert" if c == "kjop" else "info", "ticker": t,
                              "text": f"{t} er ny på listen som {CAT_NO[c]}", "why": e.get("cat_reason", "")})
        elif c != p and c and p:
            up = CAT_RANK.get(c, 0) > CAT_RANK.get(p, 0)
            items.append({"kind": "opp" if up else "ned", "level": "alert" if c == "kjop" or p == "kjop" else "info", "ticker": t,
                          "text": f"{t}: {CAT_NO.get(p, p)} → {CAT_NO.get(c, c)}", "why": e.get("cat_reason", "")})
    for t, e in pt.items():
        if t not in ct and e.get("category") in ("kjop", "hold"):
            items.append({"kind": "ut", "level": "info", "ticker": t, "text": f"{t} ({CAT_NO[e['category']]}) falt ut av listen", "why": "ingen aktive signaler lenger"})
    ps = {t["key"]: t for t in prev.get("themes", [])}
    for t in snap.get("themes", []):
        p = ps.get(t["key"])
        if p is None:
            continue
        d = (t.get("score") or 0) - (p.get("score") or 0)
        if abs(d) >= 0.5:
            items.append({"kind": "tema", "level": "alert" if d >= 1.0 and t["score"] >= 2 else "info", "theme": t["key"],
                          "text": f"Tema «{t['name']}»: score {p['score']:.2f} → {t['score']:.2f}", "why": "økt oppmerksomhet" if d > 0 else "roligere"})
    pd_ = prev.get("date", "")
    newpol = [a for a in snap.get("policy_alerts") or [] if a.get("hot") and a.get("date", "") > pd_]
    if newpol:
        items.append({"kind": "politikk", "level": "info", "text": f"{len(newpol)} nye relevante politikkdokumenter (eksportkontroll/sanksjoner/toll)",
                      "why": "; ".join(a["title"][:90] for a in newpol[:2])})
    order = {"alert": 0, "info": 1}
    items.sort(key=lambda x: (order.get(x["level"], 2), {"opp": 0, "ny": 1, "ned": 2, "ut": 3, "tema": 4, "politikk": 5}.get(x["kind"], 9)))
    return {"prev_date": prev.get("date"), "items": items, "note": "" if items else "Ingen vesentlige endringer siden forrige kjøring."}


def alerts(snap: dict) -> list[dict]:
    """Things worth a notification. Each: {level, title, why, link}."""
    out = []
    for e in snap.get("tickers", []):
        d, c, st = e.get("decision") or {}, e.get("category"), e.get("stats") or {}
        if c in ("kjop", "hold"):
            dte = d.get("days_to_earnings")
            if dte is not None and 0 <= dte <= 7:
                out.append({"level": "info", "title": f"{e['ticker']}: kvartalsrapport om {dte} d ({d.get('next_earnings')})",
                            "why": "hendelsesrisiko – kursen kan bevege seg kraftig", "link": f"ticker/{e['ticker']}"})
            close, stop = d.get("close") or st.get("close"), d.get("stop_atr")
            if close is not None and stop is not None and close < stop:
                out.append({"level": "alert", "title": f"{e['ticker']}: under ATR-stopp ({close:.2f} < {stop:.2f})", "why": "ugyldiggjøringsnivå brutt", "link": f"ticker/{e['ticker']}"})
    for k, v in (snap.get("chokepoints") or {}).items():
        a = v.get("alle") or {}
        new_drop = a.get("z90") is not None and a["z90"] <= -2 and (a.get("vs90") is None or a["vs90"] <= -0.15)
        persistent = a.get("yoy") is not None and a["yoy"] <= -0.5
        if new_drop or persistent:
            out.append({"level": "alert" if new_drop else "info",
                        "title": f"{v['name']}: {a.get('last7')} passeringer/dag (7d snitt), {_pct(a.get('yoy'))} vs i fjor",
                        "why": (f"nytt fall: {_pct(a.get('vs90'))} mot siste ~90 dager (z={a.get('z90')})" if new_drop else
                                f"vedvarende forstyrrelse (nivået mot siste ~90 dager: {_pct(a.get('vs90'))})") + f"; data t.o.m. {v.get('last_date')} (IMF PortWatch)",
                        "link": "makro.html#sund"})
    for k, v in (snap.get("oil_nowcast") or {}).items():
        if v.get("dev_pct") is not None and abs(v["dev_pct"]) >= 0.10:
            out.append({"level": "info", "title": f"{v['label']}: {_pct(v['dev_pct'])} vs 5-årssnitt for uke {v.get('week')}",
                        "why": "stramt" if v["dev_pct"] < 0 else "rikelig", "link": "makro.html#olje"})
    return out


def focus(snap: dict, chg: dict, al: list[dict], n=5) -> list[dict]:
    """3-5 prioritised items with a reason. Priority: Kjøp-kandidater > broken stops/category changes > physical alerts >
    hottest theme > Hold with near event risk."""
    items = []
    for e in snap.get("tickers", []):
        if e.get("category") == "kjop":
            d = e.get("decision") or {}
            extra = f" Ugyldig under {d['stop_atr']:.2f} (2×ATR)." if d.get("stop_atr") else ""
            items.append((0, {"title": f"Kjøp-kandidat: {e['ticker']}", "why": (e.get("cat_reason") or "") + extra, "link": f"ticker/{e['ticker']}", "level": "alert"}))
    for a in al:
        if a["level"] == "alert":
            items.append((1, a))
    for c in chg.get("items", []):
        if c["kind"] in ("opp", "ned", "ny") and c.get("ticker") and not any(c["ticker"] in i[1]["title"] for i in items):
            items.append((2, {"title": c["text"], "why": c.get("why", ""), "link": f"ticker/{c['ticker']}", "level": c["level"]}))
    th = sorted(snap.get("themes", []), key=lambda t: t.get("score") or 0, reverse=True)
    if th and (th[0].get("score") or 0) >= 1.0:
        t = th[0]
        comps = sorted(((v.get("score") or 0, v.get("label", k)) for k, v in (t.get("components") or {}).items()), reverse=True)[:2]
        items.append((3, {"title": f"Mest aktive tema: {t['name']} (score {t['score']:.2f})",
                          "why": "drevet av " + ", ".join(f"{l} (z={s:.1f})" for s, l in comps) if comps else "", "link": f"tema/{t['key']}", "level": "info"}))
    for e in snap.get("tickers", []):
        if e.get("category") == "hold":
            items.append((4, {"title": f"Hold: {e['ticker']}", "why": e.get("cat_reason", ""), "link": f"ticker/{e['ticker']}", "level": "info"}))
    for a in al:
        if a["level"] != "alert":
            items.append((5, a))
    seen, out = set(), []
    for _, it in sorted(items, key=lambda x: x[0]):
        key = it.get("link") if str(it.get("link", "")).startswith("ticker/") else it["title"]
        if key in seen or it["title"] in seen:
            continue
        seen.add(key); seen.add(it["title"]); out.append(it)
        if len(out) >= n:
            break
    return out


def apply(snap: dict, snap_dir: Path = SNAP_DIR) -> dict:
    prev = previous_snapshot(snap, snap_dir)
    chg = changes(snap, prev)
    al = alerts(snap)
    snap["briefing"] = {"changes": chg, "alerts": al, "focus": focus(snap, chg, al)}
    return snap
