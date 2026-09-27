"""Official statistics (macro) collectors: SSB, Eurostat, FRED (CSV, no key), EIA (weekly CSV, no key),
ONS, SCB, DST, OECD, IMF, World Bank + release calendars (BLS/BEA ICS, ONS release API).

Every series gets a reliability label and a 'surprise vs trend' score:
    surprise_z = robust z of the latest period-on-period change vs the previous 24 changes.
Only real downloaded values are used; failed sources are reported as failed.
"""
from __future__ import annotations
import io, logging, re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable
import pandas as pd
from .. import http
from ..anomaly import robust_z

log = logging.getLogger(__name__)

REL_OFFICIAL = "Offisiell statistikk – høy pålitelighet (kan revideres)"
REL_OFFICIAL_PRELIM = "Offisiell, foreløpige tall – middels/høy (revideres ofte)"
REL_FORECAST = "Offisiell prognose – middels (anslag, ikke fasit)"
REL_AGGREGATOR = "Offisielle tall via aggregator (FRED) – høy"


# ---------------- fetch helpers ----------------
def jsonstat2_series(j: dict, time_dim="Tid") -> pd.Series:
    """Convert a 1-D (after fixing other dims to one value) JSON-stat2 dataset to a Series."""
    ids = j["id"]; sizes = j["size"]
    t_labels = list(j["dimension"][time_dim]["category"]["index"].keys()) if isinstance(
        j["dimension"][time_dim]["category"]["index"], dict) else j["dimension"][time_dim]["category"]["index"]
    vals = j["value"]
    if isinstance(vals, dict):
        n = 1
        for s in sizes: n *= s
        vals = [vals.get(str(i)) for i in range(n)]
    if any(s > 1 for i, s in enumerate(sizes) if ids[i] != time_dim):
        raise ValueError("more than one value in non-time dims")
    return pd.Series(vals, index=t_labels, dtype="float64")


def _period_to_ts(p: str) -> pd.Timestamp:
    p = str(p)
    if m := re.fullmatch(r"(\d{4})U(\d{2})", p):            # SSB week
        return pd.Timestamp(datetime.strptime(f"{m[1]}-W{m[2]}-3", "%G-W%V-%u"))
    if m := re.fullmatch(r"(\d{4})M(\d{2})", p):            # SSB/SCB month
        return pd.Timestamp(int(m[1]), int(m[2]), 1)
    if m := re.fullmatch(r"(\d{4})-(\d{2})", p):
        return pd.Timestamp(int(m[1]), int(m[2]), 1)
    if m := re.fullmatch(r"(\d{4}) ([A-Z]{3})", p):         # ONS "2026 AUG"
        return pd.Timestamp(datetime.strptime(p.title(), "%Y %b"))
    if re.fullmatch(r"\d{4}", p):
        return pd.Timestamp(int(p), 1, 1)
    return pd.Timestamp(p)


def ssb(table: str, codes: dict[str, str], top=120) -> pd.Series:
    params = {"lang": "en", "outputFormat": "json-stat2", "valueCodes[Tid]": f"top({top})"}
    params.update({f"valueCodes[{k}]": v for k, v in codes.items()})
    j = http.get_json(f"https://data.ssb.no/api/pxwebapi/v2/tables/{table}/data", params=params, cache_hours=6)
    s = jsonstat2_series(j)
    s.index = [_period_to_ts(p) for p in s.index]
    return s.sort_index()


def eurostat(dataset: str, filters: dict[str, str], last=60) -> pd.Series:
    params = {**filters, "lastTimePeriod": last}
    j = http.get_json(f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}", params=params, cache_hours=6)
    s = jsonstat2_series(j, time_dim="time")
    s.index = [_period_to_ts(p) for p in s.index]
    return s.sort_index().dropna()


def fred_csv(series_id: str, start="2018-01-01") -> pd.Series:
    r = http.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series_id, "cosd": start}, cache_hours=6)
    df = pd.read_csv(io.BytesIO(r.content))
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    return s.dropna()


def ons(cdid: str, dataset: str, topic_path: str) -> pd.Series:
    j = http.get_json(f"https://www.ons.gov.uk/{topic_path}/timeseries/{cdid.lower()}/{dataset.lower()}/data", cache_hours=6)
    rows = j.get("months") or j.get("quarters") or j.get("years")
    s = pd.Series({_period_to_ts(x["date"]): float(x["value"]) for x in rows if x.get("value") not in ("", None)})
    return s.sort_index()


def scb_ipi() -> pd.Series:
    q = {"query": [{"code": "SNI2007", "selection": {"filter": "item", "values": ["B-D"]}},
                   {"code": "ContentsCode", "selection": {"filter": "item", "values": ["NV0402AL"]}}],
         "response": {"format": "json-stat2"}}
    url = "https://api.scb.se/OV0104/v1/doris/en/ssd/NV/NV0402/NV0402A/IPI2010KedjM"
    try:
        j = http.get_json(url, method="POST", json_body=q, cache_hours=6)
    except Exception:
        meta = http.get_json(url)
        cc = [v for v in meta["variables"] if v["code"] == "ContentsCode"][0]["values"][0]
        q["query"][1]["selection"]["values"] = [cc]
        j = http.get_json(url, method="POST", json_body=q, cache_hours=6)
    s = jsonstat2_series(j, time_dim="Tid")
    s.index = [_period_to_ts(p) for p in s.index]
    return s.sort_index().iloc[-120:]


def dst(table: str, variables: list[dict]) -> pd.Series:
    body = {"table": table, "format": "CSV", "lang": "en", "delimiter": "Semicolon", "variables": variables}
    r = http.get("https://api.statbank.dk/v1/data", method="POST", json_body=body, cache_hours=6)
    df = pd.read_csv(io.StringIO(r.content.decode("utf-8-sig")), sep=";")
    s = pd.to_numeric(df["INDHOLD"].astype(str).str.replace(",", "."), errors="coerce")
    s.index = [_period_to_ts(str(t)) for t in df["TID"]]
    return s.sort_index().dropna()


def eia_crude_stocks() -> pd.Series:
    """EIA Weekly Petroleum Status Report table 1 (CSV, no key). Returns last two weeks' commercial crude stocks."""
    import csv
    r = http.get("https://ir.eia.gov/wpsr/table1.csv", cache_hours=6)
    rows = list(csv.reader(io.StringIO(r.content.decode("latin-1"))))
    head = rows[0]
    row = next(x for x in rows if x and x[0].startswith("Commercial (Excluding SPR)"))
    num = lambda v: float(v.replace(",", ""))
    s = pd.Series({pd.to_datetime(head[5], format="%m/%d/%y"): num(row[5]),
                   pd.to_datetime(head[2], format="%m/%d/%y"): num(row[2]),
                   pd.to_datetime(head[1], format="%m/%d/%y"): num(row[1])})
    return s.sort_index()


def oecd_cli(area="USA") -> pd.Series:
    r = http.get(f"https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,4.1/{area}.M.LI...AA...H",
                 params={"startPeriod": "2019-01", "format": "csvfilewithlabels"}, cache_hours=12)
    df = pd.read_csv(io.BytesIO(r.content))
    s = pd.Series(pd.to_numeric(df["OBS_VALUE"], errors="coerce").values, index=pd.to_datetime(df["TIME_PERIOD"]))
    return s.sort_index().dropna()


def imf_weo(indicator="NGDP_RPCH", countries=("NOR", "USA", "CHN", "DEU", "GBR", "SWE", "RUS")) -> pd.DataFrame:
    j = http.get_json(f"https://www.imf.org/external/datamapper/api/v1/{indicator}/{'/'.join(countries)}", cache_hours=24)
    return pd.DataFrame(j["values"][indicator]).sort_index()


def worldbank(indicator="NE.EXP.GNFS.ZS", country="NOR") -> pd.Series:
    j = http.get_json(f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}",
                      params={"format": "json", "per_page": 30}, cache_hours=24)
    return pd.Series({pd.Timestamp(int(x["date"]), 1, 1): x["value"] for x in j[1] if x["value"] is not None}).sort_index()


# ---------------- series catalogue ----------------
@dataclass
class MacroSeries:
    key: str
    name: str            # Norwegian display name
    source: str
    country: str
    freq: str
    fetch: Callable[[], pd.Series]
    reliability: str
    themes: list[str]
    why: str
    unit: str = ""
    url: str = ""
    change: str = "pct"   # 'pct' or 'diff'


SERIES: list[MacroSeries] = [
    MacroSeries("ssb_salmon_price", "Eksportpris fersk laks (NOK/kg, ukentlig)", "SSB", "Norge", "uke",
                lambda: ssb("03024", {"VareGrupper2": "01", "ContentsCode": "Kilopris"}, top=160),
                REL_OFFICIAL, ["tariffs_trade"], "Ledende for Mowi/SalMar/Lerøy-inntjening; tollsaker påvirker pris og volum.",
                "NOK/kg", "https://www.ssb.no/statbank/table/03024"),
    MacroSeries("ssb_salmon_volume", "Eksportvolum fersk laks (tonn, ukentlig)", "SSB", "Norge", "uke",
                lambda: ssb("03024", {"VareGrupper2": "01", "ContentsCode": "Vekt"}, top=160),
                REL_OFFICIAL, ["tariffs_trade"], "Volum × pris gir tidlig bilde av sjømateksport før selskapene rapporterer.",
                "tonn", "https://www.ssb.no/statbank/table/03024"),
    MacroSeries("ssb_exports_total", "Vareeksport totalt (mill. NOK, måned)", "SSB", "Norge", "måned",
                lambda: ssb("08792", {"HovedVareStrommer": "Etot", "ContentsCode": "VerdiUjustert"}),
                REL_OFFICIAL_PRELIM, ["sanctions_energy", "mideast_energy"], "Domineres av olje og gass – fanger energiprissjokk.",
                "mill. NOK", "https://www.ssb.no/statbank/table/08792"),
    MacroSeries("ssb_mainland_exports", "Fastlandseksport (mill. NOK, måned)", "SSB", "Norge", "måned",
                lambda: ssb("08792", {"HovedVareStrommer": "Etotusorn", "ContentsCode": "VerdiUjustert"}),
                REL_OFFICIAL_PRELIM, ["tariffs_trade"], "Eksport utenom olje/gass – følsom for toll og global etterspørsel.",
                "mill. NOK", "https://www.ssb.no/statbank/table/08792"),
    MacroSeries("ssb_cpi", "KPI Norge (2025=100)", "SSB", "Norge", "måned",
                lambda: ssb("14710", {"ContentsCode": "KpiIndMnd"}), REL_OFFICIAL, ["elections_political"],
                "Inflasjon styrer Norges Banks rente, kronekurs og bankaksjer.", "indeks", "https://www.ssb.no/statbank/table/14710"),
    MacroSeries("eurostat_ip_ea", "Industriproduksjon eurosonen (2021=100, sesongjustert)", "Eurostat", "Eurosonen", "måned",
                lambda: eurostat("sts_inpr_m", {"geo": "EA20", "unit": "I21", "s_adj": "SCA", "nace_r2": "B-D"}),
                REL_OFFICIAL_PRELIM, ["tariffs_trade"], "Etterspørsel etter norsk eksport (metaller, gass) og tollvirkninger.",
                "indeks", "https://ec.europa.eu/eurostat/databrowser/view/sts_inpr_m/default/table"),
    MacroSeries("eurostat_hicp_ea", "Inflasjon eurosonen (HICP, årlig %)", "Eurostat", "Eurosonen", "måned",
                lambda: eurostat("prc_hicp_minr", {"geo": "EA", "coicop18": "TOTAL", "unit": "RCH_A"}),
                REL_OFFICIAL, ["sanctions_energy"], "Energisjokk vises raskt i HICP; påvirker ECB og EURNOK.", "%",
                "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_manr/default/table", "diff"),
    MacroSeries("fred_brent", "Brent spotpris (USD/fat, EIA via FRED)", "FRED/EIA", "Global", "dag",
                lambda: fred_csv("DCOILBRENTEU"), REL_AGGREGATOR, ["mideast_energy", "sanctions_energy"],
                "Kjerneindikator for Midtøsten-/sanksjonsrisiko og norske oljeaksjer.", "USD", "https://fred.stlouisfed.org/series/DCOILBRENTEU"),
    MacroSeries("fred_henryhub", "Henry Hub naturgass (USD/MMBtu, via FRED)", "FRED/EIA", "USA", "dag",
                lambda: fred_csv("DHHNGSP"), REL_AGGREGATOR, ["sanctions_energy"], "Amerikansk gasspris – LNG-eksportmarginer.",
                "USD", "https://fred.stlouisfed.org/series/DHHNGSP"),
    MacroSeries("fred_indpro", "Industriproduksjon USA (Fed, indeks)", "FRED/Federal Reserve", "USA", "måned",
                lambda: fred_csv("INDPRO"), REL_AGGREGATOR, ["tariffs_trade"], "Syklisk etterspørsel; tollvirkninger på industri.",
                "indeks", "https://fred.stlouisfed.org/series/INDPRO"),
    MacroSeries("fred_cpi", "KPI USA (BLS, via FRED)", "FRED/BLS", "USA", "måned",
                lambda: fred_csv("CPIAUCSL"), REL_AGGREGATOR, ["tariffs_trade"], "Toll gir høyere importpriser → KPI → renter.",
                "indeks", "https://fred.stlouisfed.org/series/CPIAUCSL"),
    MacroSeries("fred_imports_china", "USA import fra Kina (mill. USD, via FRED)", "FRED/Census", "USA", "måned",
                lambda: fred_csv("IMPCH"), REL_AGGREGATOR, ["tariffs_trade", "rare_earths_semis"],
                "Direkte mål på handelskrig USA–Kina.", "mill. USD", "https://fred.stlouisfed.org/series/IMPCH"),
    MacroSeries("eia_crude_stocks", "USA kommersielle råoljelagre (mill. fat, ukentlig)", "EIA WPSR", "USA", "uke",
                eia_crude_stocks, REL_OFFICIAL_PRELIM, ["mideast_energy"], "Lagerfall + geopolitisk risiko = sterkere oljepris.",
                "mill. fat", "https://www.eia.gov/petroleum/supply/weekly/", "diff"),
    MacroSeries("ons_cpi_uk", "Inflasjon UK (KPI årlig %)", "ONS", "Storbritannia", "måned",
                lambda: ons("D7G7", "MM23", "economy/inflationandpriceindices"), REL_OFFICIAL, [],
                "Britisk inflasjon – BoE og GBP.", "%", "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23", "diff"),
    MacroSeries("ons_ip_uk", "Industriproduksjon UK (indeks)", "ONS", "Storbritannia", "måned",
                lambda: ons("K222", "DIOP", "economy/economicoutputandproductivity/output"), REL_OFFICIAL_PRELIM, [],
                "Britisk industri.", "indeks", "https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries/k222/diop"),
    MacroSeries("scb_ipi", "Industriproduksjon Sverige (SCB, indeks)", "SCB", "Sverige", "måned", scb_ipi,
                REL_OFFICIAL_PRELIM, ["conflict_defense"], "Nordisk industri (inkl. forsvar – Saab).", "indeks",
                "https://www.statistikdatabasen.scb.se/pxweb/en/ssd/START__NV__NV0402__NV0402A/"),
    MacroSeries("dst_cpi", "KPI Danmark (DST, indeks)", "DST", "Danmark", "måned",
                lambda: dst("PRIS113", [{"code": "TYPE", "values": ["INDEKS"]}, {"code": "Tid", "values": ["*"]}]).iloc[-120:],
                REL_OFFICIAL, [], "Dansk inflasjon (DKK er knyttet til EUR).", "indeks", "https://www.statbank.dk/PRIS113"),
    MacroSeries("oecd_cli_usa", "OECD ledende indikator USA (CLI)", "OECD", "USA", "måned", lambda: oecd_cli("USA"),
                REL_OFFICIAL_PRELIM, [], "Sammensatt ledende indikator for konjunktur 6–9 mnd frem.", "indeks",
                "https://data-explorer.oecd.org/", "diff"),
    MacroSeries("oecd_cli_chn", "OECD ledende indikator Kina (CLI)", "OECD", "Kina", "måned", lambda: oecd_cli("CHN"),
                REL_OFFICIAL_PRELIM, ["rare_earths_semis"], "Kinesisk konjunktur – råvareetterspørsel.", "indeks",
                "https://data-explorer.oecd.org/", "diff"),
]


def series_stats(s: pd.Series, change="pct") -> dict:
    s = s.dropna()
    ch = (s.pct_change() * 100) if change == "pct" else s.diff()
    ch = ch.dropna()
    z, _ = robust_z(ch, recent_n=1, baseline_n=24, min_baseline=8) if len(ch) > 9 else (float("nan"), {})
    yoy = None
    if len(s) > 1:
        prev_year = s[s.index <= s.index[-1] - pd.Timedelta(days=360)]
        if len(prev_year):
            yoy = float((s.iloc[-1] / prev_year.iloc[-1] - 1) * 100) if change == "pct" else float(s.iloc[-1] - prev_year.iloc[-1])
    return {"last_period": s.index[-1].strftime("%Y-%m-%d"), "last": float(s.iloc[-1]),
            "prev": float(s.iloc[-2]) if len(s) > 1 else None,
            "change": float(ch.iloc[-1]) if len(ch) else None, "change_type": "%" if change == "pct" else "diff",
            "yoy": yoy, "surprise_z": None if pd.isna(z) else round(float(z), 2),
            "spark": [round(float(x), 4) for x in s.iloc[-40:]]}


# ---------------- release calendars ----------------
def _parse_ics(text: str, source: str) -> list[dict]:
    """Parse VEVENTs; times converted to Europe/Oslo (UTC 'Z' or US-Eastern local)."""
    from zoneinfo import ZoneInfo
    oslo, ny = ZoneInfo("Europe/Oslo"), ZoneInfo("America/New_York")
    out = []
    for ev in text.split("BEGIN:VEVENT")[1:]:
        ev = re.sub(r"\r?\n[ \t]", "", ev)
        m_dt = re.search(r"DTSTART[^:]*:(\d{8})(?:T(\d{4})\d{0,2}(Z?))?", ev)
        m_s = re.search(r"SUMMARY[^:]*:(.*)", ev)
        if not (m_dt and m_s):
            continue
        title = m_s[1].strip().replace("\\,", ",").replace("\\;", ";")
        if m_dt[2]:
            dt = datetime.strptime(m_dt[1] + m_dt[2], "%Y%m%d%H%M").replace(tzinfo=ZoneInfo("UTC") if m_dt[3] else ny)
            dt = dt.astimezone(oslo)
            out.append({"date": dt.date().isoformat(), "time": dt.strftime("%H:%M"), "source": source, "title": title})
        else:
            out.append({"date": datetime.strptime(m_dt[1], "%Y%m%d").date().isoformat(), "time": "", "source": source, "title": title})
    return out


def calendars(days_ahead=14) -> tuple[list[dict], dict]:
    today = date.today(); horizon = today + timedelta(days=days_ahead)
    events, status = [], {}
    for name, url in {"BLS": "https://www.bls.gov/schedule/news_release/bls.ics",
                      "BEA": "https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics"}.items():
        try:
            ev = _parse_ics(http.get(url, cache_hours=12).text, name)
            events += [e for e in ev if today.isoformat() <= e["date"] <= horizon.isoformat()]
            status[f"{name} release calendar (ICS)"] = f"ok ({len(ev)} events)"
        except Exception as e:
            status[f"{name} release calendar (ICS)"] = f"FAILED: {e}"
    try:
        j = http.get_json("https://api.beta.ons.gov.uk/v1/search/releases",
                          params={"limit": 100, "release-type": "type-upcoming", "fromDate": today.isoformat(),
                                  "toDate": horizon.isoformat(), "sort": "release_date_asc"}, cache_hours=12)
        rel = j.get("releases", [])
        for r in rel:
            d = (r.get("description") or {})
            dt = (d.get("release_date") or "")[:10]
            if dt and today.isoformat() <= dt <= horizon.isoformat():
                events.append({"date": dt, "time": (d.get("release_date") or "")[11:16], "source": "ONS", "title": d.get("title")})
        status["ONS release calendar API"] = f"ok ({len(rel)} upcoming)"
    except Exception as e:
        status["ONS release calendar API"] = f"FAILED: {e}"
    # Estimated (cadence-based) releases for sources without a machine-readable calendar
    d = today
    while d <= horizon:
        if d.weekday() == 2:
            events.append({"date": d.isoformat(), "time": "08:00", "source": "SSB (estimert)", "title": "Eksport av laks, ukentlig (tabell 03024)"})
            events.append({"date": d.isoformat(), "time": "16:30", "source": "EIA (estimert)", "title": "Weekly Petroleum Status Report (råoljelagre)"})
        if d.day == 15 or (d.day in (16, 17) and d.weekday() == 0):
            events.append({"date": d.isoformat(), "time": "08:00", "source": "SSB (estimert)", "title": "Utenrikshandel med varer, månedlig (08792)"})
        if d.day == 10 and d.weekday() < 5:
            events.append({"date": d.isoformat(), "time": "08:00", "source": "SSB (estimert)", "title": "Konsumprisindeksen (KPI)"})
        d += timedelta(days=1)
    # keep geopolitically relevant US/UK releases to limit noise
    keep = re.compile(r"price|cpi|employment|payroll|trade|gdp|import|export|production|inflation|pce|laks|petroleum|KPI|Utenriks|retail|pmi", re.I)
    events = [e for e in events if keep.search(e["title"] or "")]
    return sorted(events, key=lambda e: (e["date"], e["time"])), status


def eurostat_recent_updates(keys=("sts_inpr_m", "prc_hicp_manr", "ext_st_eu27_2020sitc", "nrg_cb_oilm", "nrg_cb_gasm")) -> list[dict]:
    """Datasets from our list updated in the last 3 days, from Eurostat's update RSS."""
    import feedparser
    f = feedparser.parse(http.get("https://ec.europa.eu/eurostat/api/dissemination/catalogue/rss/en/statistics-update.rss", cache_hours=6).content)
    out = []
    for e in f.entries:
        code = (e.get("title") or "").split(" ")[0].strip()
        if any(code.startswith(k) for k in keys):
            out.append({"code": code, "title": e.get("title"), "published": e.get("published"), "link": e.get("link")})
    return out


def collect() -> tuple[dict, dict]:
    status: dict[str, str] = {}
    rows = []
    by_source: dict[str, list[str]] = {}
    for ms in SERIES:
        try:
            s = ms.fetch()
            st = series_stats(s, ms.change)
            rows.append({"key": ms.key, "name": ms.name, "source": ms.source, "country": ms.country, "freq": ms.freq,
                         "reliability": ms.reliability, "themes": ms.themes, "why": ms.why, "unit": ms.unit, "url": ms.url, **st})
            by_source.setdefault(ms.source, []).append("ok")
        except Exception as e:
            log.info("macro %s failed: %s", ms.key, e)
            by_source.setdefault(ms.source, []).append(f"{ms.key}: {e}")
    for src, res in by_source.items():
        ok = sum(r == "ok" for r in res)
        status[f"Makro: {src}"] = f"ok ({ok}/{len(res)} serier)" if ok == len(res) else (
            f"{'partial' if ok else 'FAILED'} ({ok}/{len(res)}): " + "; ".join(r for r in res if r != "ok")[:250])
    out = {"series": rows}
    try:
        out["imf_weo_gdp"] = imf_weo().loc[lambda d: d.index.isin([str(y) for y in range(date.today().year - 1, date.today().year + 3)])].to_dict()
        status["Makro: IMF WEO (DataMapper)"] = "ok"
    except Exception as e:
        status["Makro: IMF WEO (DataMapper)"] = f"FAILED: {e}"
    try:
        wb = worldbank()
        out["worldbank_nor_exports_gdp"] = {str(k.year): v for k, v in wb.tail(6).items()}
        status["Makro: World Bank API"] = "ok"
    except Exception as e:
        status["Makro: World Bank API"] = f"FAILED: {e}"
    try:
        out["eurostat_updates"] = eurostat_recent_updates()
        status["Makro: Eurostat update RSS"] = f"ok ({len(out['eurostat_updates'])} relevante oppdateringer)"
    except Exception as e:
        status["Makro: Eurostat update RSS"] = f"FAILED: {e}"
    out["calendar"], cal_status = calendars()
    status.update(cal_status)
    status["Makro: Destatis GENESIS"] = "not automated: GENESIS web service returned an HTML page for guest access (new API needs registration/token)"
    status["Makro: China NBS"] = "FAILED: data.stats.gov.cn returned 403 from this box"
    status["Makro: BLS API v1"] = "not used: shared daily quota exhausted from this IP; BLS series taken via FRED CSV"
    status["Makro: EIA API v2 / FRED API / BEA API"] = "need free API keys (sign-up) - not used; FRED graph CSV + EIA weekly CSV used instead"
    return out, status
