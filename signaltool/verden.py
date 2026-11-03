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
RESERVE_LINE = "Ingen oppsummering i dag, viser siste overskrifter"
FOOTNOTE = "Nyhetsoppsummering, ikke signaler eller råd. Rekkefølgen viser hvor mye et tema er omtalt, ikke betydning for kurs."
WARN = "#fdba74"

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


def _themes(title: str) -> list[str]:
    from .themes import match_themes
    return match_themes(title or "")


def gdelt_query() -> str:
    from .themes import THEMES
    kw = []
    for th in THEMES:
        kw += [k for k in (th.__dict__.get("keywords_en") or th.keywords) if len(k) >= 4][:2]
    kw = list(dict.fromkeys(kw))
    return "(" + " OR ".join(f'"{k}"' if " " in k else k for k in kw) + ") sourcelang:english"


def _gdelt() -> list[dict]:
    from . import http
    j = http.get_json(GDELT_API, params={"query": gdelt_query(), "mode": "artlist", "format": "json", "timespan": f"{WINDOW_H}h",
                                         "maxrecords": 250, "sort": "datedesc"}, retries=2, timeout=40)
    out = []
    for a in j.get("articles") or []:
        out.append({"tittel": a.get("title"), "url": a.get("url"), "kilde": "GDELT", "domene": a.get("domain") or "",
                    "publisert": _parse_ts(a.get("seendate"))})
    return out


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
            got = fn(); raw += got; st[name] = f"ok ({len(got)})"
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
    items, seen = [], set()
    for it in raw:
        ts, url, title = it.get("publisert"), (it.get("url") or "").strip(), (it.get("tittel") or "").strip()
        if not ts or not url or not title or url in seen or (it["kilde"], title.lower()) in seen or not (since <= ts <= now + timedelta(minutes=10)):
            continue
        if it["kilde"] in ("Norges Bank", *FEEDS):
            tema = [CB]
        else:
            tema = _themes(title)
            if not tema:   # bare saker som kan knyttes til et tema (Newsweb-rutinemeldinger og GDELT-støy tas ikke med)
                continue
        seen.update({url, (it["kilde"], title.lower())})   # samme melding publisert to ganger (Newsweb) telles én gang
        items.append({"tittel": title, "url": url, "kilde": it["kilde"], **({"domene": it["domene"]} if it.get("domene") else {}),
                      "publisert": _iso(ts), "tema": tema[0], "temaer": tema})
    counts: dict[str, int] = {}
    for it in items:
        for k in it["temaer"]:
            counts[k] = counts.get(k, 0) + 1
    order = sorted(counts, key=lambda k: (-counts[k], k))
    rank = {k: i for i, k in enumerate(order)}
    items = sorted(items, key=lambda it: (rank[it["tema"]], -datetime.fromisoformat(it["publisert"].replace("Z", "+00:00")).timestamp()))
    loc = now.astimezone(OSLO)
    data = {"hentet": loc.strftime("%Y-%m-%dT%H:%M:%S%z"), "dato": loc.date().isoformat(), "vindu_timer": WINDOW_H,
            "kilder_status": st, "temaer": [{"tema": k, "antall": counts[k]} for k in order], "saker": items}
    used = sorted({it["kilde"] for it in items})
    return data, f"ok ({len(items)} saker; " + ", ".join(f"{k}: {v}" for k, v in st.items()) + ")" + ("" if used else " – ingen saker")


def save(data: dict, site: Path | None = None) -> None:
    txt = json.dumps(data, ensure_ascii=False, indent=1)
    DATA_LOG.write_text(txt)
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
       ".vn-sak{padding:7px 0;border-top:1px solid #3b4757;max-height:110px;overflow:hidden}"
       ".vn-t{margin:0;font-size:15px;line-height:20px;font-weight:700;color:#e6edf3}"
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
    from . import ux2 as UX2
    name = _tema_names(snap).get(key, key)
    sc = next((t.get("score") for t in snap.get("themes") or [] if t.get("key") == key), None)
    s = (f'<span class="vn-sc">· score {str(round(float(sc), 1)).replace(".", ",")}</span>{UX2.i("Rangering, ikke testet")}' if sc is not None else "")
    return f'<span class="vn-chip"><span class="vn-cn">{E(name)}</span>{s}</span>'


def _links(urls) -> str:
    return "".join(f'<a class="vn-l" href="{E(u)}" rel="noopener" target="_blank" aria-label="Kilde">↗</a>' for u in urls)


def _sent(s: dict) -> str:
    return f'{E(s.get("tekst") or "")}{_links(s.get("lenker") or [])}'


def _wrap(head: str, rows: list[str], foot_more: str = "Vis alle saker ↓") -> str:
    vis, rest = rows[:3], rows[3:7]
    more = f'<details class="vn-more"><summary>{E(foot_more)}</summary>{"".join(rest)}</details>' if rest else ""
    return (f'<section class="card vn" id="verden-naa"><style>{CSS}</style><h2>Verden nå</h2>{head}{"".join(vis)}{more}'
            f'<p class="vn-fn">{E(FOOTNOTE)}</p></section>')


def _reserve(data: dict, snap: dict) -> str:
    items = (data or {}).get("saker") or []
    by: dict[str, list] = {}
    for it in items:
        by.setdefault(it["tema"], []).append(it)
    counts = {t["tema"]: t["antall"] for t in (data or {}).get("temaer") or []}
    order = [t["tema"] for t in (data or {}).get("temaer") or [] if t["tema"] in by]
    names = _tema_names(snap)
    rows = []
    for k in order[:7]:
        hs = by[k][:2]
        rows.append('<div class="vn-sak">' + f'<p class="vn-t">{E(names.get(k, k))} <span class="vn-sc" style="font-weight:400;font-size:12px">· {counts.get(k, len(by[k]))} saker</span></p>'
                    + "".join(f'<a class="vn-h" href="{E(h["url"])}" rel="noopener" target="_blank">{E(h["tittel"])} ↗</a>' for h in hs)
                    + f'<p class="vn-f">{_chip(k, snap)}<span class="vn-k">{E(", ".join(sorted({h["kilde"] for h in by[k]})))}</span></p></div>')
    srcs = sorted({it["kilde"] for it in items})
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
    used_urls = [u for s in clean["ingress"] for u in s.get("lenker") or []] + [u for k in clean["saker"] for s in k["setninger"] for u in s.get("lenker") or []]
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
    for k in clean["saker"][:7]:
        kil = list(dict.fromkeys(by_url[u]["kilde"] + (f' ({by_url[u]["domene"]})' if by_url[u].get("domene") else "")
                                 for s in k["setninger"] for u in s.get("lenker") or [] if u in by_url))
        lk = list(dict.fromkeys(u for s in k["setninger"] for u in s["lenker"]))[:3]
        rows.append('<div class="vn-sak">' + f'<p class="vn-t">{E(k.get("tittel") or "")}</p>'
                    + f'<p class="vn-s">{" ".join(E(s.get("tekst") or "") for s in k["setninger"][:2])}</p>'
                    + f'<p class="vn-f">{_chip(k.get("tema") or "", snap) if k.get("tema") else ""}<span class="vn-k">{E(", ".join(kil))}</span>{_links(lk)}</p></div>')
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
