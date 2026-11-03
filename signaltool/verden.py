"""«Verden nå» øverst på Oversikt (UxBot/AnalBot 03.11).

Henting (nattkjøringen): bare titler, lenker, kilde og tidspunkt for siste døgn, aldri artikkeltekst. Kilder som tillater
automatisk henting: GDELT DOC 2.0 API (åpne data, maks 1 kall / 5 s), Oslo Børs Newsweb (allerede hentet i kjøringen),
pressemeldings-RSS fra Norges Bank, ECB og Federal Reserve. Ingen nyhetsbyråer (vilkårene tillater ikke automatisk henting).
Lagres i logs/verden_overskrifter.json (committes) og site/data/verden_overskrifter.json (publiseres).

Teksten skrives av GSbot i site_config/verden_naa.json. Før visning kontrolleres hver setning (validate): lenke til en URL i
dagens hentede data og ingen ord om kursretning eller sikkerhet. Setninger som bryter reglene fjernes (skrives ikke om) og
logges append-only i logs/oppsummering_avvik.csv; saker uten setninger droppes. Mangler tekstfila eller er den eldre enn
dagens hentede data, vises den mekaniske listen (reserve)."""
from __future__ import annotations
import calendar, csv, json, re
from datetime import datetime, timedelta, timezone
from html import escape as E
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import LOGS, ROOT

OSLO = ZoneInfo("Europe/Oslo")
TEXT = ROOT / "site_config" / "verden_naa.json"
DATA_LOG = LOGS / "verden_overskrifter.json"
AVVIK = LOGS / "oppsummering_avvik.csv"
GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"
FEEDS = {"ECB": "https://www.ecb.europa.eu/rss/press.html",
         "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml"}
CB = "sentralbanker"
CB_NAME = "Sentralbanker"
WINDOW_H = 24
MAX_PER_TEMA = 20
CB_WINDOW_H = 72   # sentralbanker publiserer ikke hvert døgn (03.11: ECB/Fed/Norges Bank ga 0 saker med 24 t)
GDELT_GKG_LAST = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
GDELT_GKG_FILES = 8   # reserve når DOC-API-et gir 429: 8 GKG-filer spredt over siste døgn (åpne data, bare tittel/URL brukes)
RESERVE_LINE = "Ingen oppsummering i dag, viser siste overskrifter"
CHIP_PREFIX = "Tema (automatisk)"   # AnalBot 04.11: til temamatchingen har bestått 27/30-kontrollen; ingen score
FOOTNOTE = "Nyhetsoppsummering, ikke signaler eller råd. Rekkefølgen viser hvor mye et tema er omtalt, ikke betydning for kurs."
WARN = "#fdba74"
RANK_TIP = "Rangering, ikke testet"

# AnalBot 03.11: ingen ord om kursretning eller sikkerhet. Treff -> setningen fjernes.
_KURS = r"(?:kurs\w*|aksje\w*|pris\w*|børs\w*|marked\w*|olje\w*|renter?\w*|valuta\w*|krone\w*|dollar\w*|indeks\w*)"
_RETN = r"(?:stige\w*|stiger|steg|stigning\w*|falle\w*|faller|falt|fall)"
BANNED: list[tuple[str, str]] = [
    ("vil stige", r"\bvil\s+stige\b"), ("vil falle", r"\bvil\s+falle\b"),
    ("stige/falle om kurs", rf"\b{_KURS}\W+(?:\w+\W+){{0,4}}?{_RETN}\b|\b{_RETN}\W+(?:\w+\W+){{0,4}}?{_KURS}\b"),
    ("bra for", r"\bbra\s+for\b"), ("dårlig for", r"\bdårlig\s+for\b"),
    ("sikker", r"\bsikker(?:t|e)?\b"), ("garantert", r"\bgarant\w*"), ("ventes å", r"\bventes\s+å\b"),
    ("kjøp", r"\bkjøp\w*"), ("selg", r"\bselg\w*"), ("kursmål", r"\bkursmål\w*"),
    ("will rise/fall", r"\bwill\s+(?:rise|fall|climb|drop)\b"), ("buy/sell", r"\b(?:buy|sell)\b"),
    ("price target", r"\bprice\s+target"), ("guaranteed", r"\bguarantee"),
]
_BANNED_RX = [(n, re.compile(p, re.I)) for n, p in BANNED]


# ---------------------------------------------------------------- henting
def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(v) -> datetime | None:
    if v is None or v == "":
        return None
    if hasattr(v, "timetuple") and not isinstance(v, str):   # pandas.Timestamp / datetime
        d = v.to_pydatetime() if hasattr(v, "to_pydatetime") else v
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    s = str(v)
    if re.fullmatch(r"\d{8}T\d{6}Z", s):   # GDELT seendate
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    from email.utils import parsedate_to_datetime
    try:
        d = parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


# Streng temamatching for «Verden nå» (03.11): bare entydige ord/fraser, hele ord (evt. flertall), i tittelen.
# Generiske ord som også er firmanavn eller hverdagsord (norway, pipeline, shipping, gulf, chip, strait, war, resign,
# protest, lng, north sea …) er tatt ut, så «Blue Moon Norway … Nussir» og «Solar Development Pipeline» ikke får tema.
STRICT: dict[str, list[str]] = {
    "conflict_defense": ["ukraine", "ukrainian", "russia", "russian", "nato", "kremlin", "zelensky", "zelenskyy", "putin",
                         "missile", "air defense", "air defence", "artillery", "defence spending", "defense spending", "rearmament"],
    "mideast_energy": ["iran", "iranian", "israel", "israeli", "hormuz", "tehran", "hezbollah", "gaza", "iraq", "opec",
                       "saudi arabia", "oil price", "brent crude", "persian gulf"],
    "sanctions_energy": ["sanction", "sanctioned", "price cap", "shadow fleet", "embargo", "ofac", "gazprom", "rosneft"],
    "shipping_chokepoints": ["red sea", "houthi", "suez", "panama canal", "bab el-mandeb", "strait of hormuz", "taiwan strait",
                             "chokepoint", "container ship"],
    "tariffs_trade": ["tariff", "trade war", "export control", "customs duty", "trade deal", "import tax", "section 232", "anti-dumping"],
    "rare_earths_semis": ["taiwan", "rare earth", "semiconductor", "gallium", "germanium", "south china sea", "tsmc", "chipmaker"],
    "elections_political": ["election", "referendum", "coup", "no-confidence", "impeach", "impeachment", "snap election",
                            "martial law", "parliament dissolved"],
    "nordic_arctic": ["subsea cable", "undersea cable", "sabotage", "baltic sea", "arctic", "svalbard", "high north", "finnmark", "greenland"],
    "food_agri": ["grain", "wheat", "fertiliser", "fertilizer", "black sea", "food crisis", "export ban", "potash", "famine", "drought"],
    "risk_off_haven": ["nuclear war", "world war", "nuclear weapon", "invasion", "gold price", "safe haven", "state of emergency"],
}
_WORD_RX = {k: [(w, re.compile(r"(?<![\w-])" + re.escape(w).replace(r"\ ", r"[\s-]+") + r"(?:s|es)?(?![\w-])", re.I))
                 for w in sorted(v, key=len, reverse=True)] for k, v in STRICT.items()}


def _same(a: str, b: str) -> bool:
    """Bøyningsvarianter (ukraine/ukrainian, iran/iranian, israel/israeli) teller som samme ord."""
    n = min(6, len(a), len(b))
    return a[:n] == b[:n]


def _is_phrase(w: str) -> bool:
    return " " in w or "-" in w


def _matches(title: str) -> dict[str, list[str]]:
    """AnalBot/GSbot 04.11: tema bare ved minst to ulike nøkkelord fra temaet, eller én hel frase (flere ord), i tittelen.
    Ett enkeltord alene («drought», «chokepoint», «tariff») gir ikke treff. Bøyningsvarianter (russia/russian) teller som ett ord.
    Returnerer {tema: [matchede ord]} i STRICT-rekkefølge."""
    t = title or ""
    out: dict[str, list[str]] = {}
    for k, pats in _WORD_RX.items():
        hit = []
        for w, rx in pats:
            if rx.search(t) and not any(_same(h, w) for h in hit):
                hit.append(w)
        if any(_is_phrase(w) for w in hit) or len(hit) >= 2:
            out[k] = hit
    return out


def _themes(title: str) -> list[str]:
    """Temaer som oppfyller regelen i _matches. Ellers [] -> saken utelates."""
    return list(_matches(title))


def gdelt_query() -> str:
    kw = []
    for words in STRICT.values():
        pick = []
        for k in words:   # 2 per tema, uten bøyningsvarianter (ukraine/ukrainian)
            if len(k) >= 4 and not any(k.startswith(p) for p in pick) and len(pick) < 2:
                pick.append(k)
        kw += pick
    kw = list(dict.fromkeys(kw))
    return "(" + " OR ".join(f'"{k}"' if " " in k else k for k in kw) + ") sourcelang:english"


GDELT_WAITS = (10, 30, 60)   # pause før forsøk 2, 3, 4 (GDELT: maks 1 kall / 5 s; etter 429 må det gå lenger tid)


def _gdelt_doc(sleep=None) -> list[dict]:
    """GDELT DOC 2.0 artlist. Ett kall, med pauser og nye forsøk ved 429/5xx/ikke-JSON."""
    import time
    import requests
    from .config import USER_AGENT
    sleep = sleep or time.sleep
    params = {"query": gdelt_query(), "mode": "artlist", "format": "json", "timespan": f"{WINDOW_H}h", "maxrecords": 250, "sort": "datedesc"}
    err = None
    for i in range(len(GDELT_WAITS) + 1):
        if i:
            sleep(GDELT_WAITS[i - 1])
        try:
            from . import http
            http._throttle("api.gdeltproject.org")   # felles 6 s-grense med resten av kjøringen
            r = requests.get(GDELT_API, params=params, timeout=40, headers={"User-Agent": USER_AGENT})
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return [{"tittel": a.get("title"), "url": a.get("url"), "kilde": "GDELT", "domene": a.get("domain") or "",
                         "publisert": _parse_ts(a.get("seendate"))} for a in r.json().get("articles") or []]
            err = f"HTTP {r.status_code}: {r.text.strip()[:60]}"
        except (requests.RequestException, ValueError) as ex:
            err = str(ex)[:80]
    raise RuntimeError(f"GDELT DOC etter {len(GDELT_WAITS) + 1} forsøk: {err}")


def _gdelt_gkg(now: datetime | None = None, files: int = GDELT_GKG_FILES) -> list[dict]:
    """Reserve: GDELT 2.0 GKG-filer (data.gdeltproject.org, åpne data uten kallgrense). Bare <PAGE_TITLE>, URL, domene, tid.
    Filene spres over siste døgn (hver 3. time fra siste oppdatering)."""
    import io, zipfile
    from . import http
    last = http.get(GDELT_GKG_LAST, timeout=20, retries=2).text
    m = re.search(r"/(\d{14})\.gkg\.csv\.zip", last)
    if not m:
        raise RuntimeError("GDELT GKG: fant ikke siste fil")
    t0 = datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    out = []
    for k in range(files):
        ts = t0 - timedelta(hours=3 * k)
        url = f"https://data.gdeltproject.org/gdeltv2/{ts:%Y%m%d%H%M%S}.gkg.csv.zip"
        try:
            z = zipfile.ZipFile(io.BytesIO(http.get(url, timeout=60, retries=2).content))
        except Exception:
            continue
        with z.open(z.namelist()[0]) as f:
            for line in io.TextIOWrapper(f, encoding="utf-8", errors="replace"):
                c = line.rstrip("\n").split("\t")
                if len(c) < 27 or not c[4].startswith("http"):
                    continue
                tm = re.search(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", c[26])
                if not tm:
                    continue
                from html import unescape
                out.append({"tittel": unescape(tm.group(1)).strip(), "url": c[4], "kilde": "GDELT", "domene": c[3],
                            "publisert": _parse_ts(c[1][:8] + "T" + c[1][8:] + "Z")})
    if not out:
        raise RuntimeError("GDELT GKG: ingen filer lest")
    return out


GDELT_MODE = {"siste": ""}
ALL_MATCHES: list[dict] = []   # siste collect(): alle saker med nøkkelordtreff før MAX_PER_TEMA-kuttet


def _gdelt() -> list[dict]:
    """DOC-API-et først (med pauser og nye forsøk); gir det fortsatt 429, brukes GKG-filene (samme kilde, åpne data)."""
    try:
        got = _gdelt_doc(); GDELT_MODE["siste"] = "DOC API"
        return got
    except Exception as ex:
        import logging
        logging.getLogger(__name__).warning("verden: %s – bruker GDELT GKG-filer", ex)
    got = _gdelt_gkg(); GDELT_MODE["siste"] = "GKG-filer (DOC API ga 429)"
    return got


def _rss(name: str, url: str) -> list[dict]:
    import feedparser
    from . import http
    f = feedparser.parse(http.get(url, timeout=25, retries=2).content)
    out = []
    for e in f.entries:
        ts = None
        for k in ("published_parsed", "updated_parsed"):
            if e.get(k):
                ts = datetime.fromtimestamp(calendar.timegm(e[k]), tz=timezone.utc); break
        out.append({"tittel": e.get("title"), "url": e.get("link"), "kilde": name, "publisert": ts})
    return out


def collect(newsweb_df=None, nb_press=None, now: datetime | None = None, fetch=None) -> tuple[dict, str]:
    """Samle siste døgns titler/lenker. `fetch` (tester) erstatter nettkall: dict kilde -> callable."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    since = now - timedelta(hours=WINDOW_H)
    fetch = fetch or {"GDELT": _gdelt, **{n: (lambda n=n, u=u: _rss(n, u)) for n, u in FEEDS.items()}}
    raw, st = [], {}
    for name, fn in fetch.items():
        try:
            got = fn(); raw += got; st[name] = f"ok ({len(got)})" + (f" via {GDELT_MODE['siste']}" if name == "GDELT" and GDELT_MODE["siste"] and fn is _gdelt else "")
        except Exception as ex:   # én kilde feiler -> de andre brukes
            st[name] = f"FAILED: {str(ex)[:120]}"
    if newsweb_df is not None and len(newsweb_df):
        nw = [{"tittel": r.get("title"), "url": r.get("url"), "kilde": "Oslo Børs Newsweb", "publisert": _parse_ts(r.get("published"))}
              for r in newsweb_df.to_dict("records")]
        raw += nw; st["Oslo Børs Newsweb"] = f"ok ({len(nw)} i 95d-uttrekket)"
    else:
        st["Oslo Børs Newsweb"] = "ingen data"
    if nb_press is not None:
        raw += [{"tittel": p.get("title"), "url": p.get("link"), "kilde": "Norges Bank", "publisert": _parse_ts(p.get("published"))} for p in nb_press]
        st["Norges Bank"] = f"ok ({len(nb_press)})"
    since_cb = now - timedelta(hours=CB_WINDOW_H)
    items, seen = [], set()
    for it in raw:
        ts, url, title = it.get("publisert"), (it.get("url") or "").strip(), (it.get("tittel") or "").strip()
        is_cb = it["kilde"] in ("Norges Bank", *FEEDS)
        if not ts or not url or not title or url in seen or (it["kilde"], title.lower()) in seen \
                or not ((since_cb if is_cb else since) <= ts <= now + timedelta(minutes=10)):
            continue
        words: list[str] = []
        if is_cb:
            tema = [CB]   # sentralbanker: tema etter kilde (pressemelding), ikke nøkkelord – logges ikke i tema_match_sjekk
        else:
            m = _matches(title)
            tema = list(m)
            if not tema:   # to nøkkelord eller én frase i tittelen; ellers utelates saken (Newsweb-rutine, GDELT-støy)
                continue
            words = m[tema[0]]
        seen.update({url, (it["kilde"], title.lower())})   # samme melding publisert to ganger (Newsweb) telles én gang
        items.append({"tittel": title, "url": url, "kilde": it["kilde"], **({"domene": it["domene"]} if it.get("domene") else {}),
                      "publisert": _iso(ts), "tema": tema[0], "temaer": tema, **({"matchede_ord": words} if words else {})})
    counts: dict[str, int] = {}
    for it in items:
        for k in it["temaer"]:
            counts[k] = counts.get(k, 0) + 1
    order = sorted(counts, key=lambda k: (-counts[k], k))
    # AnalBot 04.11: til temamatchingen har bestått kontrollen (27 av 30), sorteres sakene etter dato, nyeste først
    items = sorted(items, key=lambda it: (-_parse_ts(it["publisert"]).timestamp(), it["url"]))
    kept: dict[str, int] = {}
    ALL_MATCHES[:] = [it for it in items if it.get("matchede_ord")]   # alle treff logges, også de som ikke lagres (cap)
    capped = []
    for it in items:   # antall per tema telles over alle saker; bare de nyeste MAX_PER_TEMA lagres (GKG gir hundrevis)
        kept[it["tema"]] = kept.get(it["tema"], 0) + 1
        if kept[it["tema"]] <= MAX_PER_TEMA:
            capped.append(it)
    items = capped
    loc = now.astimezone(OSLO)
    data = {"hentet": loc.strftime("%Y-%m-%dT%H:%M:%S%z"), "dato": loc.date().isoformat(), "vindu_timer": WINDOW_H,
            "vindu_timer_sentralbanker": CB_WINDOW_H,
            "kilder_status": st, "temaer": [{"tema": k, "antall": counts[k]} for k in order], "saker": items}
    used = sorted({it["kilde"] for it in items})
    return data, f"ok ({len(items)} saker; " + ", ".join(f"{k}: {v}" for k, v in st.items()) + ")" + ("" if used else " – ingen saker")


TEMA_LOG = LOGS / "tema_match_sjekk.csv"
TEMA_COLS = ["dato", "url", "tittel", "kilde", "tema", "matchede_ord"]


def log_matches(data: dict, path: Path | None = None, items: list[dict] | None = None) -> int:
    """AnalBot 04.11: alle nøkkelordtreff append-only i logs/tema_match_sjekk.csv (3 netter -> 30 tilfeldige kontrolleres).
    Eksisterende rader endres aldri; (dato, url, tema) som allerede finnes, skrives ikke på nytt. Returnerer antall nye rader."""
    path = path or TEMA_LOG
    have = set()
    if path.exists() and path.stat().st_size:
        with path.open(newline="") as f:
            have = {(r["dato"], r["url"], r["tema"]) for r in csv.DictReader(f)}
    dato = (data or {}).get("dato") or ""
    rows = []
    for it in (items if items is not None else (data or {}).get("saker") or []):
        if not it.get("matchede_ord"):
            continue
        r = {"dato": dato, "url": it["url"], "tittel": it["tittel"], "kilde": it.get("domene") or it["kilde"], "tema": it["tema"],
             "matchede_ord": "; ".join(it["matchede_ord"])}
        k = (r["dato"], r["url"], r["tema"])
        if k not in have:
            have.add(k); rows.append(r)
    new = not (path.exists() and path.stat().st_size)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, TEMA_COLS)
        if new:
            w.writeheader()
        w.writerows(rows)
    return len(rows)


def save(data: dict, site: Path | None = None) -> None:
    txt = json.dumps(data, ensure_ascii=False, indent=1)
    DATA_LOG.write_text(txt)
    log_matches(data, items=list(ALL_MATCHES) if ALL_MATCHES else None)
    if site is not None:
        (site / "data").mkdir(parents=True, exist_ok=True)
        (site / "data" / "verden_overskrifter.json").write_text(txt)


# ---------------------------------------------------------------- kontroll (AnalBot)
def banned(text: str) -> str | None:
    for n, rx in _BANNED_RX:
        if rx.search(text or ""):
            return f"forbudt ord: «{n}»"
    return None


def _check_sentence(s, urls: set) -> str | None:
    if not isinstance(s, dict):
        return "ugyldig format"
    links = [l for l in (s.get("lenker") or []) if isinstance(l, str) and l.strip()]
    if not links:
        return "mangler kildelenke"
    bad = [l for l in links if l not in urls]
    if bad:
        return f"lenke finnes ikke i dagens hentede data: {bad[0]}"
    return banned(s.get("tekst") or "")


def validate(text: dict, data: dict, today: str, log_path: Path | None = None) -> tuple[dict, list[dict]]:
    """Fjern (ikke skriv om) setninger som bryter reglene, logg hver fjerning, dropp saker uten setninger."""
    urls = {it["url"] for it in (data or {}).get("saker", [])}
    removed = []

    def keep(sents):
        out = []
        for s in sents or []:
            why = _check_sentence(s, urls)
            if why:
                removed.append({"dato": today, "setning": (s.get("tekst") if isinstance(s, dict) else str(s)) or "", "grunn": why})
            else:
                out.append(s)
        return out

    clean = {**text, "ingress": keep(text.get("ingress")), "saker": []}
    for sak in text.get("saker") or []:
        why_t = banned(sak.get("tittel") or "")
        if why_t:
            removed.append({"dato": today, "setning": f"[tittel] {sak.get('tittel')}", "grunn": why_t + " (saken droppet)"})
            continue
        ss = keep(sak.get("setninger"))
        if ss:
            clean["saker"].append({**sak, "setninger": ss})
    _log(removed, log_path or AVVIK)
    return clean, removed


def _log(rows: list[dict], path: Path) -> None:
    """Append-only; samme (dato, setning, grunn) logges bare én gang (bygget kan kjøres flere ganger samme dag)."""
    if not rows:
        return
    have = set()
    if path.exists():
        with path.open(newline="") as f:
            have = {(r["dato"], r["setning"], r["grunn"]) for r in csv.DictReader(f)}
    new = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, ["dato", "setning", "grunn"])
        if not new:
            w.writeheader()
        for r in rows:
            k = (r["dato"], r["setning"], r["grunn"])
            if k not in have:
                have.add(k); w.writerow(r)


def load_text(path: Path | None = None) -> dict | None:
    p = path or TEXT
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except ValueError:
        return None


# ---------------------------------------------------------------- visning (UxBot)
CSS = (".vn{padding:12px 16px}.vn h2{margin:0 0 2px;font-size:18px;line-height:24px}"
       ".vn-meta{margin:0 0 8px;font-size:12px;line-height:16px;color:#94a3b8}"
       ".vn-warn{margin:0 0 8px;font-size:12px;line-height:16px;color:#fdba74}"
       ".vn-ing{margin:0 0 10px;font-size:16px;line-height:1.55;color:#e6edf3}"
       ".vn-l{font-size:12px;text-decoration:none;margin-left:3px;white-space:nowrap}"
       ".vn-sak{padding:8px 0;border-top:1px solid #3b4757;min-height:80px;max-height:110px;overflow:hidden}"
       ".vn-t{margin:0;font-size:15px;line-height:20px;font-weight:600;color:#e6edf3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}"
       ".vn-m{margin:2px 0 0;font-size:12px;line-height:16px;color:#94a3b8}.vn-m .vn-l{margin-left:2px}"
       ".vn-c{margin:3px 0 0;font-size:12px;line-height:16px}"
       ".vn-c .vn-chip{display:inline;padding:0 6px;border-radius:8px;background:#334155;color:#cbd5e1;white-space:normal;box-decoration-break:clone;-webkit-box-decoration-break:clone}"
       ".vn-s{margin:2px 0 0;font-size:14px;line-height:19px;color:#cbd5e1;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}"
       ".vn-f{display:flex;align-items:center;gap:6px;margin:3px 0 0;font-size:12px;line-height:16px;color:#94a3b8;white-space:nowrap}"
       ".vn-chip{display:inline-flex;align-items:center;flex:0 1 auto;min-width:0;padding:0 6px;border-radius:8px;background:#334155;color:#cbd5e1}"
       ".vn-cn{overflow:hidden;text-overflow:ellipsis;min-width:0}.vn-chip .vn-sc{flex:none;margin-left:3px}.vn-chip .sc-i{flex:none}"
       ".vn-k{flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis}.vn-f .vn-l{flex:none;margin-left:0}"
       ".vn-sc{color:#94a3b8}"
       ".vn-h{display:block;font-size:14px;line-height:19px;color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
       ".vn-more>summary{cursor:pointer;color:var(--acc,#60a5fa);font-size:14px;min-height:32px;line-height:32px;border-top:1px solid #3b4757;list-style:none}"
       ".vn-more>summary::-webkit-details-marker{display:none}.vn-more[open]>summary{display:none}"
       ".vn-fn{margin:8px 0 0;font-size:12px;line-height:16px;color:#94a3b8}"
       ".vn,.vn *{min-width:0;max-width:100%;box-sizing:border-box}.vn{overflow-wrap:anywhere}")


def _gen(snap: dict) -> datetime | None:
    """snap["generated"] er lokal Oslo-tid uten sone («2026-11-03 13:53»)."""
    try:
        return datetime.strptime(str(snap.get("generated") or "")[:16], "%Y-%m-%d %H:%M").replace(tzinfo=OSLO)
    except ValueError:
        return None


def _dm(ts: datetime) -> str:
    return ts.astimezone(OSLO).strftime("%d.%m")


def _tema_names(snap: dict) -> dict:
    from .themes import THEMES
    names = {th.key: th.name for th in THEMES}
    names[CB] = CB_NAME
    return names


def _chip(key: str, snap: dict) -> str:
    """«Tema (automatisk): <tema>», ingen score (AnalBot 04.11). Kan bryte linja (UxBot 04.11)."""
    name = _tema_names(snap).get(key, key)
    return f'<span class="vn-chip">{E(CHIP_PREFIX)}: {E(name)}</span>'


def _ts(it: dict) -> float:
    t = _parse_ts(it.get("publisert"))
    return t.timestamp() if t else 0.0


def _row(h: dict, data: dict, snap: dict, sents: str = "") -> str:
    """UxBot 04.11: tittel (15 px, maks 2 linjer), «kilde-domene · dd.mm hh:mm ↗» (12 px), chip «Tema (automatisk): …»."""
    ts = _parse_ts(h.get("publisert"))
    when = f" · {_dm(ts)} {ts.astimezone(OSLO):%H:%M}" if ts else ""
    return ('<div class="vn-sak">' + f'<p class="vn-t">{E(h["tittel"])}</p>' + sents
            + f'<p class="vn-m">{E(h.get("domene") or h["kilde"])}{when}{_links([h["url"]])}</p>'
            + (f'<p class="vn-c">{_chip(h["tema"], snap)}</p>' if h.get("tema") else "") + '</div>')


def _links(urls) -> str:
    return "".join(f'<a class="vn-l" href="{E(u)}" rel="noopener" target="_blank" aria-label="Kilde">↗</a>' for u in urls)


def _sent(s: dict) -> str:
    return f'{E(s.get("tekst") or "")}{_links(s.get("lenker") or [])}'


def _wrap(head: str, rows: list[str], foot_more: str = "Vis alle saker ↓") -> str:
    vis, rest = rows[:3], rows[3:7]
    more = f'<details class="vn-more"><summary>{E(foot_more)}</summary>{"".join(rest)}</details>' if rest else ""
    return (f'<section class="card vn" id="verden-naa"><style>{CSS}</style><h2>Verden nå</h2>{head}{"".join(vis)}{more}'
            f'<p class="vn-fn">{E(FOOTNOTE)}</p></section>')


def _old(h: dict, data: dict) -> str:
    """Sentralbanksaker kan være opptil 72 t gamle: vis datoen når saken er eldre enn 24 t."""
    ts, ref = _parse_ts(h.get("publisert")), _parse_ts((data or {}).get("hentet"))
    return f" ({_dm(ts)})" if ts and ref and ref - ts > timedelta(hours=WINDOW_H) else ""


def _reserve(data: dict, snap: dict) -> str:
    """Flat liste, nyeste først (AnalBot/UxBot 04.11). Ingen temaoverskrifter eller antall."""
    items = sorted((data or {}).get("saker") or [], key=lambda it: (-_ts(it), it["url"]))[:7]
    rows = [_row(h, data, snap) for h in items]
    srcs = sorted({it["kilde"] for it in items})   # bare kilder som er lenket i en sak som vises
    newest = max((_parse_ts(it["publisert"]) for it in items), default=None)
    h = _parse_ts((data or {}).get("hentet"))
    meta = " · ".join(x for x in ["Siste overskrifter", f"hentet {_dm(h)} kl. {h.astimezone(OSLO):%H:%M}" if h else "",
                                    f"nyeste sak {_dm(newest)}" if newest else "", f"kilder: {', '.join(srcs)}" if srcs else ""] if x)
    head = f'<p class="vn-meta">{E(meta)}</p><p class="vn-warn">{E(RESERVE_LINE)}</p>'
    if not rows:
        head += '<p class="vn-meta">Ingen saker hentet siste døgn.</p>'
    return _wrap(head, rows)


def html(snap: dict, text_path: Path | None = None, log_path: Path | None = None, now: datetime | None = None) -> str:
    data = snap.get("verden") or {}
    text = load_text(text_path)
    fetched = _parse_ts(data.get("hentet"))
    written = _parse_ts((text or {}).get("written_at"))
    if not text or not written:
        return _reserve(data, snap)
    if fetched and written.astimezone(OSLO).date() < fetched.astimezone(OSLO).date():   # eldre enn dagens hentede data
        return _reserve(data, snap)
    today = (fetched or written).astimezone(OSLO).date().isoformat()
    clean, _ = validate(text, data, today, log_path)
    if not clean["saker"]:
        return _reserve(data, snap)
    by_url = {it["url"]: it for it in data.get("saker", [])}
    def newest_of(k):
        return max((_ts(by_url[u]) for s in k["setninger"] for u in s.get("lenker") or [] if u in by_url), default=0.0)
    saker = sorted(clean["saker"], key=lambda k: -newest_of(k))[:7]   # nyeste først (AnalBot 04.11)
    used_urls = [u for s in clean["ingress"][:4] for u in s.get("lenker") or []] + [u for k in saker for s in k["setninger"] for u in s.get("lenker") or []]
    used = [by_url[u] for u in dict.fromkeys(used_urls) if u in by_url]
    srcs = list(dict.fromkeys(sorted(it["kilde"] for it in used)))
    newest = max((_parse_ts(it["publisert"]) for it in used), default=None) or _parse_ts(text.get("newest_item"))
    meta = (f"Automatisk oppsummering · skrevet {_dm(written)} kl. {written.astimezone(OSLO):%H:%M}"
            + (f" · nyeste sak {_dm(newest)}" if newest else "") + f" · kilder: {', '.join(srcs)}")
    now = now or _gen(snap) or datetime.now(timezone.utc)
    head = f'<p class="vn-meta">{E(meta)}</p>'
    if now - written > timedelta(hours=24):
        head += f'<p class="vn-warn">Oppsummeringen er fra {_dm(written)}</p>'
    if clean["ingress"]:
        head += '<p class="vn-ing">' + " ".join(_sent(s) for s in clean["ingress"][:4]) + "</p>"
    rows = []
    for k in saker:
        lk = list(dict.fromkeys(u for s in k["setninger"] for u in s["lenker"] if u in by_url))[:3]
        top = max((by_url[u] for u in lk), key=_ts)
        kil = " · ".join(dict.fromkeys(by_url[u].get("domene") or by_url[u]["kilde"] for u in lk))
        ts = _parse_ts(top.get("publisert"))
        when = f" · {_dm(ts)} {ts.astimezone(OSLO):%H:%M}" if ts else ""
        rows.append('<div class="vn-sak">' + f'<p class="vn-t">{E(k.get("tittel") or "")}</p>'
                    + f'<p class="vn-s">{" ".join(E(s.get("tekst") or "") for s in k["setninger"][:2])}</p>'
                    + f'<p class="vn-m">{E(kil)}{when}{_links(lk)}</p>'
                    + (f'<p class="vn-c">{_chip(k["tema"], snap)}</p>' if k.get("tema") else "") + '</div>')
    return _wrap(head, rows)


def main(argv=None) -> int:
    """python -m signaltool.verden [tekstfil] : kontroller teksten mot dagens hentede data (logs/verden_overskrifter.json).
    Skriver fjernede setninger (og logger dem i logs/oppsummering_avvik.csv). Exit 0 alltid; 1 bare ved ulesbar fil."""
    import sys
    a = (argv if argv is not None else sys.argv[1:])
    p = Path(a[0]) if a else TEXT
    if not p.exists():
        print(f"verden nå: ingen tekstfil ({p}) – siden viser reserven"); return 0
    text = load_text(p)
    if text is None:
        print(f"verden nå: {p} er ikke gyldig JSON – siden viser reserven"); return 1
    data = json.loads(DATA_LOG.read_text()) if DATA_LOG.exists() else {}
    today = (_parse_ts(data.get("hentet")) or datetime.now(OSLO)).astimezone(OSLO).date().isoformat()
    clean, rem = validate(text, data, today)
    for r in rem:
        print(f"FJERNET: {r['setning']} – {r['grunn']}")
    print(f"verden nå: {len(clean['ingress'])} ingress-setninger, {len(clean['saker'])} saker beholdt, {len(rem)} fjernet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
