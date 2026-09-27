"""SEC EDGAR (free, no key; requires descriptive User-Agent; max 10 req/s).

* Form 4 insider transactions: discovered via EDGAR full-text search (efts.sec.gov), then each
  filing's XML is parsed for open-market purchases (transaction code 'P').
* 8-K keyword attention: weekly counts of 8-K filings mentioning theme phrases (full-text search).
* 13F: quarterly, filed up to 45 days after quarter end -> too slow for 'early' signals; not collected.
"""
from __future__ import annotations
import json, logging
import xml.etree.ElementTree as ET
from datetime import date, timedelta
import pandas as pd
from .. import http
from ..config import CACHE

log = logging.getLogger(__name__)
EFTS = "https://efts.sec.gov/LATEST/search-index"
F4_CACHE = CACHE / "form4"
F4_CACHE.mkdir(parents=True, exist_ok=True)

EIGHTK_PHRASES = {
    "conflict_defense": '"Ukraine"',
    "mideast_energy": '"Middle East"',
    "sanctions_energy": '"sanctions"',
    "shipping_chokepoints": '"Red Sea"',
    "tariffs_trade": '"tariffs"',
    "rare_earths_semis": '"rare earth"',
    "nordic_arctic": '"Norway"',
    "food_agri": '"fertilizer"',
    "risk_off_haven": '"geopolitical"',
}


def efts(q: str, forms: str, start: date, end: date, offset=0) -> dict:
    return http.get_json(EFTS, params={"q": q, "forms": forms, "dateRange": "custom",
                                       "startdt": start.isoformat(), "enddt": end.isoformat(), "from": offset})


def list_form4(start: date, end: date, cap=2500) -> list[dict]:
    hits, off = [], 0
    while off < cap:
        j = efts("", "4", start, end, off)
        page = j["hits"]["hits"]
        if not page:
            break
        hits += page
        off += len(page)
        if off >= j["hits"]["total"]["value"]:
            break
    return hits


def _txt(el, path):
    x = el.find(path)
    return x.text.strip() if x is not None and x.text else None


def parse_form4(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    issuer_cik = _txt(root, "issuer/issuerCik")
    issuer = _txt(root, "issuer/issuerName")
    sym = (_txt(root, "issuer/issuerTradingSymbol") or "").upper()
    owners = root.findall("reportingOwner")
    oname = _txt(owners[0], "reportingOwnerId/rptOwnerName") if owners else None
    rel = owners[0].find("reportingOwnerRelationship") if owners else None
    title = ""
    if rel is not None:
        bits = []
        if _txt(rel, "isDirector") in ("1", "true"): bits.append("Director")
        if _txt(rel, "isOfficer") in ("1", "true"): bits.append(_txt(rel, "officerTitle") or "Officer")
        if _txt(rel, "isTenPercentOwner") in ("1", "true"): bits.append("10% owner")
        title = ", ".join(bits)
    out = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _txt(t, "transactionCoding/transactionCode")
        sh = _txt(t, "transactionAmounts/transactionShares/value")
        px = _txt(t, "transactionAmounts/transactionPricePerShare/value")
        ad = _txt(t, "transactionAmounts/transactionAcquiredDisposedCode/value")
        out.append({"issuer_cik": issuer_cik, "issuer": issuer, "ticker": sym, "owner": oname, "role": title,
                    "code": code, "shares": float(sh) if sh else 0.0, "price": float(px) if px else 0.0,
                    "acq_disp": ad, "trans_date": _txt(t, "transactionDate/value")})
    return out


def fetch_form4_transactions(days=7, cap=2500) -> tuple[pd.DataFrame, str]:
    end = date.today(); start = end - timedelta(days=days)
    try:
        hits = list_form4(start, end, cap)
    except Exception as e:
        return pd.DataFrame(), f"FAILED listing: {e}"
    rows, errs = [], 0
    for h in hits:
        s = h["_source"]; adsh = s["adsh"]; fn = h["_id"].split(":", 1)[1]
        cp = F4_CACHE / f"{adsh}.json"
        if cp.exists():
            tx = json.loads(cp.read_text())
        else:
            cik = s["ciks"][-1].lstrip("0")
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{fn}"
            try:
                tx = parse_form4(http.get(url, retries=2).content)
                for t in tx:
                    t["url"] = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{adsh}-index.htm"
                cp.write_text(json.dumps(tx))
            except Exception as e:
                errs += 1; log.info("form4 %s: %s", url, e); continue
        for t in tx:
            t["file_date"] = s.get("file_date"); t["adsh"] = adsh
        rows += tx
    df = pd.DataFrame(rows)
    return df, f"ok ({len(hits)} Form 4 filings, {errs} parse errors)"


def insider_buy_clusters(tx: pd.DataFrame, min_insiders=2, min_value=50_000) -> pd.DataFrame:
    """Open-market purchases (code P) grouped by issuer; flag clusters of distinct buyers."""
    if tx.empty:
        return pd.DataFrame()
    p = tx[(tx["code"] == "P") & (tx["acq_disp"] == "A")].copy()
    if p.empty:
        return pd.DataFrame()
    p["value"] = p["shares"] * p["price"]
    g = p.groupby(["ticker", "issuer"]).agg(
        n_insiders=("owner", "nunique"), n_tx=("owner", "size"), total_value=("value", "sum"),
        owners=("owner", lambda s: "; ".join(sorted(set(map(str, s)))[:6])),
        roles=("role", lambda s: "; ".join(sorted(set(r for r in map(str, s) if r))[:4])),
        last_date=("file_date", "max"), url=("url", "last")).reset_index()
    g["cluster"] = (g["n_insiders"] >= min_insiders) & (g["total_value"] >= min_value)
    return g.sort_values(["cluster", "n_insiders", "total_value"], ascending=False)


def eightk_weekly_counts(weeks=13) -> tuple[pd.DataFrame, dict, str]:
    """Weekly counts of 8-Ks mentioning each theme phrase + the latest few filings as evidence."""
    end = date.today()
    rows, examples = {}, {}
    try:
        for k, q in EIGHTK_PHRASES.items():
            series = {}
            for w in range(weeks):
                e = end - timedelta(days=7 * w); s = e - timedelta(days=6)
                j = efts(q, "8-K", s, e)
                series[pd.Timestamp(e)] = j["hits"]["total"]["value"]
                if w == 0:
                    examples[k] = [{"company": (h["_source"].get("display_names") or ["?"])[0],
                                    "date": h["_source"].get("file_date"),
                                    "url": "https://www.sec.gov/Archives/edgar/data/{}/{}/{}-index.htm".format(
                                        h["_source"]["ciks"][0].lstrip("0"), h["_source"]["adsh"].replace("-", ""),
                                        h["_source"]["adsh"])} for h in j["hits"]["hits"][:4]]
            rows[k] = pd.Series(series).sort_index()
    except Exception as e:
        return pd.DataFrame(rows), examples, f"partial: {e}"
    return pd.DataFrame(rows), examples, f"ok ({len(rows)} phrases x {weeks} weeks)"


def forensic_late_filings(days=7) -> tuple[list[dict], str]:
    """NT 10-K / NT 10-Q notices (late filing) - a classic forensic red flag."""
    end = date.today(); start = end - timedelta(days=days)
    try:
        j = efts("", "NT 10-K,NT 10-Q", start, end)
    except Exception as e:
        return [], f"FAILED: {e}"
    out = []
    for h in j["hits"]["hits"]:
        s = h["_source"]
        out.append({"company": (s.get("display_names") or ["?"])[0], "form": s.get("form"), "date": s.get("file_date"),
                    "url": "https://www.sec.gov/Archives/edgar/data/{}/{}/{}-index.htm".format(
                        s["ciks"][0].lstrip("0"), s["adsh"].replace("-", ""), s["adsh"])})
    return out, f"ok ({j['hits']['total']['value']} late-filing notices in {days}d)"
