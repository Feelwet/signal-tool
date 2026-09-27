"""IMF PortWatch – daily vessel transit counts through maritime chokepoints (AIS-based, free ArcGIS open data, no key).
https://portwatch.imf.org  (data lag ~ 4-8 days). We compute 7-day average transits (total and tankers) vs the
previous 90 days (robust z) and vs the same period last year."""
from __future__ import annotations
import pandas as pd
from .. import http
from ..anomaly import robust_z

URL = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query"
CHOKE = {"chokepoint6": "Hormuzstredet", "chokepoint4": "Bab el-Mandeb", "chokepoint1": "Suezkanalen", "chokepoint7": "Kapp det gode håp",
         "chokepoint2": "Panamakanalen", "chokepoint5": "Malakkastredet", "chokepoint11": "Taiwanstredet", "chokepoint3": "Bosporos"}
THEME = {"chokepoint6": "mideast_energy", "chokepoint4": "shipping_chokepoints", "chokepoint1": "shipping_chokepoints",
         "chokepoint7": "shipping_chokepoints", "chokepoint2": "shipping_chokepoints", "chokepoint5": "shipping_chokepoints",
         "chokepoint11": "shipping_chokepoints", "chokepoint3": "sanctions_energy"}


def history(portid: str, since="2019-01-01", cache_hours=12) -> pd.DataFrame:
    rows, off = [], 0
    while True:
        j = http.get_json(URL, params={"where": f"portid='{portid}' AND date >= DATE '{since}'", "outFields": "date,n_total,n_tanker,n_container,n_dry_bulk,capacity",
                                       "orderByFields": "date", "resultOffset": off, "resultRecordCount": 2000, "f": "json"},
                          cache_hours=cache_hours, timeout=60)
        feats = j.get("features", [])
        rows += [f["attributes"] for f in feats]
        if len(feats) < 2000 and not j.get("exceededTransferLimit"):
            break
        off += len(feats)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def collect() -> tuple[dict, str]:
    out, fails = {}, []
    for pid, name in CHOKE.items():
        try:
            h = history(pid, since=(pd.Timestamp.today() - pd.Timedelta(days=500)).strftime("%Y-%m-%d"))
            if h.empty:
                fails.append(name); continue
            r = {}
            for col, lab in (("n_total", "alle"), ("n_tanker", "tankskip")):
                s7 = h[col].rolling(7).mean().dropna()
                z, info = robust_z(s7.iloc[::-7][::-1], recent_n=1, baseline_n=13, min_baseline=8)  # weekly points, ~90 d baseline
                ly = s7[s7.index <= s7.index[-1] - pd.Timedelta(days=364)]
                med = info.get("baseline_median")
                r[lab] = {"last7": round(float(s7.iloc[-1]), 1), "z90": None if z != z else round(float(z), 2),
                          "vs90": None if not med else round(float(s7.iloc[-1] / med - 1), 3),
                          "yoy": None if ly.empty or not ly.iloc[-1] else round(float(s7.iloc[-1] / ly.iloc[-1] - 1), 3)}
            out[pid] = {"name": name, "theme": THEME[pid], "last_date": str(h.index[-1].date()), **r,
                        "spark": [round(float(x), 1) for x in h["n_total"].rolling(7).mean().dropna().iloc[-120::3]]}
        except Exception as e:
            fails.append(f"{name}: {e}")
    msg = f"ok ({len(out)}/{len(CHOKE)} stredet, data t.o.m. {max((v['last_date'] for v in out.values()), default='-')})" if out else "FAILED"
    return out, msg + (f"; feil: {fails}" if fails else "")
