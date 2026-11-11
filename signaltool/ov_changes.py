"""Kandidatlista over tid (UxBot/AnalBot 11.11): endringsstripe på Oversikt, «N dager på rad» i kandidattabellen,
ut-grunner (logs/list_exits.csv), inn/ut-perioder (data/list_periods.json) og periodelinjene under kursgrafen.

Kilde: logs/categories.csv. «Lista» = kandidatlista = loggens rader uten kategori «tema» (temakart-tickere står utenfor
kandidatlista, jf. tickersiden) + innkurs-sideloggen for ikke-loggbare kandidater (ETF-er o.l.), som i since.py. «Kjøring» = en dato i loggen (helger med); stripen sammenligner siste mot forrige kjøring.
- Stripe: inn = siste − forrige, ut = forrige − siste, står fortsatt = siste ∩ forrige (inn + står fortsatt = dagens antall).
- Dager: sammenhengende kjøringer bakover t.o.m. siste kjøring. Har tickeren stått på lista i hver kjøring siden første
  loggdato: «fra DD.MM» (første loggdato, lest fra loggen). Ikke på lista i siste kjøring: «–».
- Perioder: [inn, ut|None]; ut = første kjøring tickeren manglet (hver manglende kjøring bryter perioden).
- Ut-grunner logges fra 11.11 (record_exits) med kode below_threshold / out_of_top60 / no_price / delisted / moved_to_theme. Historiske
  utfall har ingen kode og vises som «grunn ikke logget». Ingen kode -> aldri en grunn; «rødt flagg» er aldri en grunn.
Bare lesing: ingenting her endrer kandidatutvalg, score eller kategorier."""
from __future__ import annotations

import csv
import json
import re
from html import escape as E
from pathlib import Path

from .config import DATA, LOGS

LOG = LOGS / "categories.csv"
EXITS = LOGS / "list_exits.csv"
PERIODS_JSON = DATA / "list_periods.json"
EXIT_COLS = ["date", "ticker", "code", "old_score", "new_score"]
CODES = ("below_threshold", "out_of_top60", "no_price", "delisted", "moved_to_theme")
NO_REASON = "grunn ikke logget"
# Kan slås på som " (før {dm})"; {dm} = første dato i logs/list_exits.csv (aldri hardkodet). Tom = av.
NO_REASON_SUFFIX = ""
DAYS_HEAD = "Dager på lista"
NO_PRICE_HEAD = "Ute pga. manglende kurs"
CHART_NOTE = "Grått felt = perioder på kandidatlista. Ikke kjøps- eller salgssignal."


def _slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", t)


def _dm(d: str) -> str:
    return f"{d[8:10]}.{d[5:7]}"


def _nb(x) -> str:
    return f"{float(x):.1f}".replace(".", ",").replace("-", "−")


def _read(path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open(newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------------------------------------- lista
_DEF = object()


def _entry_default(path):
    from .since import ENTRY_LOG
    return ENTRY_LOG if path is None or Path(path) == LOG else None


def _rows(path=None, entry_path=_DEF) -> list[dict]:
    """Kandidatlista per kjøring = categories.csv uten tema-rader + innkurs-sideloggen (logs/entry_prices.csv, rader fra
    since.SIDE_START) for kandidater som ikke logges i categories.csv (ETF-er, BA.L o.l.) – samme kilde som «Siden DD.MM».
    Hver rad får «src» (cat/side) slik at «fra før DD.MM» bruker første dato i tickerens egen kilde."""
    from .since import SIDE_START
    out, have = [], set()
    for r in _read(path or LOG):
        d, t = (r.get("date") or "").strip(), (r.get("ticker") or "").strip()
        if d and t and (r.get("category") or "") != "tema":
            out.append({**r, "date": d, "ticker": t, "src": "cat"})
            have.add((d, t))
    ep = _entry_default(path) if entry_path is _DEF else entry_path
    if ep is not None:
        for r in _read(ep):
            d, t = (r.get("date") or "").strip(), (r.get("ticker") or "").strip()
            if d and t and d >= SIDE_START and (d, t) not in have:
                out.append({**r, "date": d, "ticker": t, "score": "", "src": "side"})
    # Tickere i sideloggen (f.eks. SPY, logget i categories.csv bare 27.09): hullet før SIDE_START er ikke bevis for at de
    # falt av lista (AnalBot 28.10) -> categories-rader før SIDE_START brukes ikke for dem; perioden starter i sideloggen.
    side = {r["ticker"] for r in out if r["src"] == "side"}
    return [r for r in out if not (r["ticker"] in side and r["src"] == "cat" and r["date"] < SIDE_START)]


MEMBERS = LOGS / "list_members.csv"   # AnalBot 11.11: hele kandidatlista per kjøring, rett fra snapshotet (= kandidattabellen)
MEMBER_COLS = ["date", "ticker"]


def _members_default(path):
    return MEMBERS if path is None or Path(path) == LOG else None


def members(path=None) -> dict[str, set]:
    out: dict[str, set] = {}
    for r in _read(path or MEMBERS):
        d, t = (r.get("date") or "").strip(), (r.get("ticker") or "").strip()
        if d and t:
            out.setdefault(d, set()).add(t)
    return out


def write_members(snap: dict, path: Path | None = None) -> int:
    """Skriver dagens kandidatliste (samme utvalg som kandidattabellen på Oversikt: tickere med score, også uten sluttkurs;
    tema-rader bare hvis de står i tabellen) til logs/list_members.csv. En ny kjøring samme dag erstatter dagens rader."""
    from .overview import candidates
    p, day = Path(path or MEMBERS), str(snap.get("date") or "")
    if not day:
        return 0
    rows = [{"date": day, "ticker": t} for t in sorted({e["ticker"] for e in candidates(snap)})]
    old = [r for r in _read(p) if r.get("date") != day]
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MEMBER_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(old + rows)
    return len(rows)


def _model(path=None, entry_path=_DEF, members_path=_DEF) -> tuple[dict, dict, dict]:
    """(by_date, gaps, src_first).
    - Fra første dato i logs/list_members.csv brukes BARE den loggen (= kandidattabellen den dagen).
    - Før det: categories.csv (uten tema) + sideloggen, som før.
    - Historiske hull i sideloggen (tickeren mangler én eller flere kjøringer, men står der før og etter): ikke Ut/Inn;
      hullet fylles (perioden er sammenhengende) og datoene returneres i gaps for teksten «data mangler dd.mm»."""
    rows = _rows(path, entry_path)
    mp = _members_default(path) if members_path is _DEF else members_path
    mem = members(mp) if mp is not None else {}
    m0 = min(mem) if mem else None
    old: dict[str, set] = {}
    for r in rows:
        if m0 is None or r["date"] < m0:
            old.setdefault(r["date"], set()).add(r["ticker"])
    by = {d: set(v) for d, v in old.items()}
    by.update({d: set(v) for d, v in mem.items()})
    ds = sorted(by)
    side = {r["ticker"] for r in rows if r["src"] == "side"}
    gaps: dict[str, list] = {}
    for t in side:
        idx = [i for i, d in enumerate(ds) if t in by[d]]
        old_idx = [i for i in idx if ds[i] in old and t in old[ds[i]]]
        for a, b in zip(idx, idx[1:]):
            if b - a > 1 and a in old_idx:
                hole = [ds[i] for i in range(a + 1, b) if ds[i] in old]   # bare hull i den gamle sideloggen
                if len(hole) == b - a - 1:
                    for d in hole:
                        by[d].add(t)
                    gaps.setdefault(t, []).extend(hole)
    first = {}
    for r in rows:
        first[r["src"]] = min(first.get(r["src"], r["date"]), r["date"])
    sf = {r["ticker"]: first["side" if r["ticker"] in side else "cat"] for r in rows}
    return by, {t: sorted(v) for t, v in gaps.items()}, sf


def by_date(path: Path | None = None, entry_path=_DEF, members_path=_DEF) -> dict[str, set]:
    """{dato: {tickere på kandidatlista}}. Mangler filene: tom dict."""
    return _model(path, entry_path, members_path)[0]


def gaps(path: Path | None = None, entry_path=_DEF, members_path=_DEF) -> dict[str, list]:
    return _model(path, entry_path, members_path)[1]


def src_first(path: Path | None = None, entry_path=_DEF, members_path=_DEF) -> dict[str, str]:
    """{ticker: første dato i tickerens kilde} (categories.csv eller sideloggen), for «fra før DD.MM»/«fra DD.MM»."""
    return _model(path, entry_path, members_path)[2]


def _ranges(dates: list[str], runs: list[str]) -> list[tuple]:
    pos = {d: i for i, d in enumerate(runs)}
    out = []
    for d in dates:
        if out and pos.get(d, -9) == pos.get(out[-1][1], -99) + 1:
            out[-1] = (out[-1][0], d)
        else:
            out.append((d, d))
    return out


def gap_text(dates: list[str], runs: list[str]) -> str:
    """«data mangler 08.11», «data mangler 08.11, 10.11» eller «data mangler 31.10–04.11» (sammenhengende kjøringer)."""
    if not dates:
        return ""
    pos = {d: i for i, d in enumerate(runs)}
    grp, cur = [], [dates[0]]
    for d in dates[1:]:
        if pos.get(d, -9) == pos.get(cur[-1], -99) + 1:
            cur.append(d)
        else:
            grp.append(cur)
            cur = [d]
    grp.append(cur)
    return "data mangler " + ", ".join(_dm(g[0]) if len(g) == 1 else f"{_dm(g[0])}–{_dm(g[-1])}" for g in grp)


def scores(path: Path | None = None) -> dict[tuple, str]:
    return {(r["date"], r["ticker"]): r.get("score") or "" for r in _read(path or LOG) if (r.get("category") or "") != "tema"}


def theme_rows(path: Path | None = None) -> set:
    """{(dato, ticker)} med kategori «tema» (temakart, utenfor kandidatlista)."""
    return {(r["date"], r["ticker"]) for r in _read(path or LOG) if (r.get("category") or "") == "tema"}


def diff(by: dict[str, set]) -> dict | None:
    """Siste mot forrige kjøring. None når loggen har færre enn to kjøringer."""
    ds = sorted(by)
    if len(ds) < 2:
        return None
    prev, last = ds[-2], ds[-1]
    a, b = by[prev], by[last]
    return {"prev": prev, "last": last, "inn": sorted(b - a), "ut": sorted(a - b), "stay": sorted(a & b), "n_last": len(b)}


def days(by: dict[str, set]) -> dict[str, int]:
    """{ticker: sammenhengende kjøringer bakover t.o.m. siste kjøring} for tickere på lista i siste kjøring."""
    ds = sorted(by)
    if not ds:
        return {}
    out = {}
    for t in by[ds[-1]]:
        n = 0
        for d in reversed(ds):
            if t not in by[d]:
                break
            n += 1
        out[t] = n
    return out


def periods(by: dict[str, set]) -> dict[str, list]:
    """{ticker: [[inn, ut|None], ...]} for alle perioder fra første loggdato, også gjentatte inn/ut."""
    ds = sorted(by)
    out: dict[str, list] = {}
    for t in sorted(set().union(*by.values()) if by else ()):
        ps, cur = [], None
        for d in ds:
            if t in by[d]:
                if cur is None:
                    cur = [d, None]
            elif cur is not None:
                cur[1] = d
                ps.append(cur)
                cur = None
        if cur is not None:
            ps.append(cur)
        out[t] = ps
    return out


def write_periods(path: Path | None = None, log_path: Path | None = None) -> int:
    p = Path(path or PERIODS_JSON)
    by, gp, _ = _model(log_path)
    ps = periods(by)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"source": "logs/list_members.csv (før: categories.csv + entry_prices.csv)", "first": min(by, default=None),
                             "periods": ps, "data_gaps": gp},
                            ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return len(ps)


# ---------------------------------------------------------------------------------------------------------- grunner
def exits(path: Path | None = None) -> dict[tuple, dict]:
    """{(dato, ticker): rad} fra logs/list_exits.csv; bare godkjente koder teller."""
    return {(r["date"], r["ticker"]): r for r in _read(path or EXITS) if r.get("date") and r.get("ticker")}


def reason_text(row: dict | None) -> str:
    """En av de fem godkjente tekstene, eller "" når koden mangler / tallene mangler. Bare faktiske tall vises."""
    if not row:
        return ""
    v = lambda k: "" if row.get(k) is None else str(row.get(k)).strip()   # 0.0 er et faktisk tall, ikke «mangler»
    c, o, n = v("code"), v("old_score"), v("new_score")
    try:
        if c == "below_threshold" and o and n:
            return f"Score under grensen ({_nb(o)} → {_nb(n)})"
        if c == "out_of_top60" and n:
            return f"Ikke lenger blant de 60 høyeste (score {_nb(n)})"
    except ValueError:
        return ""
    return {"no_price": "Mangler kurs", "delisted": "Ikke børsnotert", "moved_to_theme": "Flyttet til temakartet"}.get(c, "")


def no_reason(path: Path | None = None) -> str:
    if not NO_REASON_SUFFIX:
        return NO_REASON
    ds = sorted(r["date"] for r in _read(path or EXITS) if r.get("date"))
    return NO_REASON + NO_REASON_SUFFIX.format(dm=_dm(ds[0])) if ds else NO_REASON


def ut_text(day: str, ticker: str, ex: dict, nr: str) -> str:
    return reason_text(ex.get((day, ticker))) or nr


# ---------------------------------------------------------------------------------------------------------- logging
def _delisted(today: str) -> set:
    """Tickere med rettelseslinje listed=false og strykedato ≤ i dag i verdikjede-dataene (kildebelagt, f.eks. REC)."""
    from .verdikjeder import DIR
    out = set()
    for f in sorted(Path(DIR).glob("*.jsonl")):
        for s in f.read_text().splitlines():
            try:
                d = json.loads(s)
            except ValueError:
                continue
            if d.get("listed") is False and d.get("ticker") and d.get("delisted") and str(d["delisted"]) <= today:
                out.add(d["ticker"])
                if "Oslo" in (d.get("exchange") or "") and not d["ticker"].endswith(".OL"):
                    out.add(d["ticker"] + ".OL")
    return out


TOP_CAP = 60   # pipeline.run: snap["tickers"] = [score > 0][:60]; _coverage_cut: kept (rangerbare) [:60] + «Ikke rangert»


def exit_rows(snap: dict, ranked: list[dict], log_path: Path | None = None, today: str | None = None, entry_path=_DEF,
              members_path=_DEF) -> list[dict]:
    """Tickere på kandidatlista i forrige kjøring som mangler i dag. Nøyaktig én kode, eller tom (= «grunn ikke logget»):
    - delisted: strøket (verdikjede-rettelse med listed=false, strykedato ≤ i dag).
    - moved_to_theme: står i dagens logg med kategori «tema» (temakartet, utenfor kandidatlista).
    - below_threshold: fortsatt kandidat, men score ≤ 0. Grensen er score > 0 (pipeline.run), f.eks. «Score under grensen
      (2,1 → 0,0)»; skrives bare når begge score er kjent.
    - out_of_top60: 60-taket telles på de RANGERBARE kandidatene i snapshotet (pipeline.run [:60] og _coverage_cut kept[:60]);
      tema-rader (theme_maps.log_rows, tickere utenfor snapshotet) og «Ikke rangert» (low) telles IKKE. Koden skrives bare når
      taket faktisk biter: tickeren er fortsatt kandidat med score > 0, står ikke i snapshotet, og snapshotet har nøyaktig
      60 rangerbare kandidater. Biter ikke taket: aldri.
    - no_price: kjøringen fjerner aldri en ticker for manglende kurs (den blir «Ikke rangert» og står på lista) -> skrives ikke.
    Ikke kandidat i dag (ingen score), fryst liste (kildefeil) eller står i snapshotet (f.eks. ikke loggbar): ingen kode.
    «Rødt flagg» er aldri en kode."""
    today = today or str(snap.get("date") or "")
    by = by_date(log_path, entry_path, members_path)   # hull i den gamle sideloggen er fylt: aldri en utgang
    if today not in by:
        return []
    prevs = [d for d in by if d < today]
    if not prevs:
        return []
    prev = max(prevs)
    sc, tema = scores(log_path), theme_rows(log_path)
    gone = sorted(by[prev] - by[today])
    cand = {e["ticker"]: e.get("score") for e in ranked}
    dl = _delisted(today)
    tk = snap.get("tickers") or []
    in_snap = {e["ticker"] for e in tk}
    n_kept = sum(1 for e in tk if not e.get("unranked"))
    frozen = bool(snap.get("frozen_from")) or any(e.get("frozen") for e in tk)
    out = []
    for t in gone:
        old, new = sc.get((prev, t), ""), cand.get(t)
        code = ""
        if t in dl:
            code = "delisted"
        elif (today, t) in tema:
            code = "moved_to_theme"
        elif frozen or new is None or t in in_snap:
            code = ""
        elif new <= 0 and old not in ("", None):
            code = "below_threshold"
        elif new > 0 and n_kept == TOP_CAP:
            code = "out_of_top60"
        out.append({"date": today, "ticker": t, "code": code, "old_score": old, "new_score": "" if new is None else new})
    return out


def record_exits(snap: dict, ranked: list[dict], path: Path | None = None, log_path: Path | None = None, members_path=_DEF) -> int:
    """Skriver dagens utfall til logs/list_exits.csv (en ny kjøring samme dag erstatter dagens rader). Leser bare snap/ranked."""
    p = Path(path or EXITS)
    rows = exit_rows(snap, ranked, log_path, members_path=members_path)
    today = str(snap.get("date") or "")
    old = [r for r in _read(p) if r.get("date") != today]
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXIT_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(old + rows)
    return len(rows)


# ---------------------------------------------------------------------------------------------------------- Oversikt
def _chip(t: str, sign: str, pages: set | None, sub: str = "") -> str:
    g = f'<span class="chg-g" aria-hidden="true">{sign}</span>'
    lab = f'{g}<span class="chg-t">{E(t)}</span>' + (f'<span class="chg-why">{E(sub)}</span>' if sub else "")
    if pages is None or t in pages:
        return f'<a class="chg-c" href="ticker/{_slug(t)}.html">{lab}</a>'
    return f'<span class="chg-c chg-np">{lab}</span>'   # ingen tickerside i denne byggingen: ingen død lenke


def strip_html(snap: dict | None = None, path: Path | None = None, exits_path: Path | None = None, members_path=_DEF) -> str:
    """«Siden DD.MM: N inn · N ut · N står fortsatt» som <details>; trykk åpner gruppene Inn, Ut og ev. «Ute pga. manglende kurs»."""
    dd = diff(by_date(path, members_path=members_path))
    if not dd:
        return ""
    pages = {e["ticker"] for e in (snap or {}).get("tickers") or [] if e.get("ticker")} if snap is not None else None
    ex, nr = exits(exits_path), no_reason(exits_path)
    line = f'Siden {_dm(dd["prev"])}: {len(dd["inn"])} inn · {len(dd["ut"])} ut · {len(dd["stay"])} står fortsatt'
    np_ = [t for t in dd["ut"] if (ex.get((dd["last"], t)) or {}).get("code") == "no_price"]
    ut = [t for t in dd["ut"] if t not in np_]
    sub = lambda t: f'Ut {_dm(dd["last"])}: {ut_text(dd["last"], t, ex, nr)}'

    def grp(name, chips, n):   # UxBot 11.11: tom gruppe skjules helt (ingen overskrift, ingen plassholder); tallet i stripen står
        if not chips:
            return ""
        return f'<div class="chg-grp"><h3>{E(name)} ({n})</h3><div class="chg-cs">{"".join(chips)}</div></div>'

    g = grp("Inn", [_chip(t, "+", pages) for t in dd["inn"]], len(dd["inn"])) + grp("Ut", [_chip(t, "−", pages, sub(t)) for t in ut], len(ut))
    if np_:
        g += grp(NO_PRICE_HEAD, [_chip(t, "−", pages, sub(t)) for t in np_], len(np_))
    return (f'<details class="ov-chg" data-last="{E(dd["last"])}" data-prev="{E(dd["prev"])}"><summary><span class="chg-l">{E(line)}</span></summary>'
            f'<div class="chg-p">{g}</div></details>')


STRIP_RE = re.compile(r'<details class="ov-chg" data-last="(\d{4}-\d\d-\d\d)" data-prev="(\d{4}-\d\d-\d\d)"><summary><span class="chg-l">'
                      r'Siden (\d\d\.\d\d): (\d+) inn · (\d+) ut · (\d+) står fortsatt</span></summary>(.*?)</details>', re.S)


def strip_check(html: str) -> dict:
    """Verifisering (AnalBot 11.11): slår bare ut når stripen og kandidattabellen regnes fra hver sin kilde
    (inn + står fortsatt ≠ tabellens rader) eller Ut-brikkene ikke stemmer med «n ut». Manglende kurs er aldri en feil."""
    m = STRIP_RE.search(html)
    if not m:
        return {"ok": False, "why": "endringsstripe mangler"}
    inn, ut, stay, body = int(m.group(4)), int(m.group(5)), int(m.group(6)), m.group(7)
    rows = html.count("<tr data-nf=")
    chips_ut = len(re.findall(r'<span class="chg-why">Ut ', body))
    chips_in = body.count('<span class="chg-g" aria-hidden="true">+</span>')
    ok = inn + stay == rows and chips_ut == ut and chips_in == inn and m.group(3) == f"{m.group(2)[8:10]}.{m.group(2)[5:7]}"
    return {"ok": ok, "why": "" if ok else f"stripe {inn}+{stay} mot tabell {rows}, ut-brikker {chips_ut}/{ut}, inn-brikker {chips_in}/{inn}",
            "text": f"Siden {m.group(3)}: {inn} inn · {ut} ut · {stay} står fortsatt", "rows": rows, "last": m.group(1), "prev": m.group(2)}


def days_cell(t: str, dmap: dict[str, int], full: set | None = None) -> str:
    """«N dager på rad», «fra DD.MM» (sammenhengende siden første dato i kilden), «–» (ikke på lista). Grå, ingen sortering."""
    n = dmap.get(t)
    if n is None:
        return '<td class="dg"><span class="dgv">–</span></td>'
    if full and t in full:
        return f'<td class="dg"><span class="dgv">fra {_dm(full[t])}</span></td>'
    ny = '<span class="dg-ny">Ny</span>' if n == 1 else ""
    return f'<td class="dg"><span class="dgv">{n} {"dag" if n == 1 else "dager"} på rad</span>{ny}</td>'


def days_ctx(path: Path | None = None, entry_path=_DEF, members_path=_DEF) -> tuple[dict, dict]:
    """(dager, {ticker: første dato} for tickere som har stått i hver kjøring siden første dato i sin kilde). Hull er ikke brudd."""
    by, _, sf = _model(path, entry_path, members_path)
    dmap, ds = days(by), sorted(by)
    full = {t: sf[t] for t, n in dmap.items() if t in sf and n >= len([d for d in ds if d >= sf[t]])}
    return dmap, full


# ---------------------------------------------------------------------------------------------------------- tickergraf
def ticker_periods(t: str, path: Path | None = None, exits_path: Path | None = None, members_path=_DEF) -> list[dict]:
    """[{inn, ut, first, text, lead, why, title}] for tickersiden; tom liste når tickeren aldri har stått på lista."""
    by, gp, sf = _model(path, members_path=members_path)
    ps = periods(by).get(t) or []
    if not ps:
        return []
    first = sf.get(t) or min(by)
    runs = sorted(by)
    ex, nr = exits(exits_path), no_reason(exits_path)
    out = []
    for inn, ut in ps:
        a = f"på lista fra før {_dm(first)}" if inn == first else f"Inn {_dm(inn)}"
        gd = [d for d in gp.get(t, []) if d >= inn and (ut is None or d < ut)]
        g = gap_text(gd, runs)
        if ut is None:
            lead, why = f"{a} · på lista nå", ""
            title = lead[0].upper() + lead[1:]
        else:
            lead, why = f"{a} · Ut {_dm(ut)}:", ut_text(ut, t, ex, nr)
            title = f"Ut {_dm(ut)}: {why}"
        main = lead + (" " + why if why else "")
        main = main[0].upper() + main[1:]
        out.append({"inn": inn, "ut": ut, "first": inn == first, "lead": lead, "why": why, "title": title, "gap": g,
                    "gap_ranges": _ranges(gd, runs), "tip": main + (f"\n{g}" if g else ""),   # 1280: hullet på egen linje
                    "text": lead + (" " + why if why else "") + (f" · {g}" if g else "")})
    return out


def periods_html(ps: list[dict]) -> str:
    if not ps:
        return ""
    li = "".join(f'<li><span class="lp-a">{E(p["lead"])}</span>' + (f' <span class="lp-r">{E(p["why"])}</span>' if p["why"] else "")
                 + (f'<span class="lp-g"> · {E(p["gap"])}</span>' if p.get("gap") else "") + "</li>" for p in ps)
    return f'<p class="lp-note">{E(CHART_NOTE)}</p><ul class="lp-list">{li}</ul>'


CSS = """
.ov-chg{margin:0 0 8px;border:1px solid #3b4757;border-radius:6px;background:#111821;color:#cbd5e1}
.ov-chg>summary{box-sizing:border-box;display:flex;align-items:center;min-height:48px;padding:5px 12px;font-size:14px;line-height:19px;cursor:pointer;list-style:none}
.ov-chg>summary::-webkit-details-marker{display:none}.ov-chg>summary::after{content:"▾";margin-left:auto;padding-left:8px;color:#94a3b8}.ov-chg[open]>summary::after{content:"▴"}
.ov-chg .chg-l{min-width:0}.ov-chg .chg-p{padding:0 12px 8px}.ov-chg h3{margin:4px 0;font-size:13px;line-height:18px;font-weight:600;color:#94a3b8}
.ov-chg .chg-cs{display:flex;flex-wrap:wrap;gap:6px}
.ov-chg .chg-c{box-sizing:border-box;display:inline-flex;flex-wrap:wrap;align-items:center;justify-content:center;column-gap:4px;min-width:44px;min-height:44px;padding:4px 10px;border:1px solid #3b4757;border-radius:6px;background:#1c2430;color:#cbd5e1;font-size:14px;line-height:20px;text-decoration:none}
.ov-chg a.chg-c:hover,.ov-chg a.chg-c:focus-visible{border-color:#94a3b8}
.ov-chg .chg-g{color:#94a3b8;font-weight:600}.ov-chg .chg-why{flex-basis:100%;text-align:center;font-size:13px;line-height:18px;color:#94a3b8}
.ov-ct th.dg-h,.ov-ct td.dg{text-align:right;white-space:nowrap}.ov-ct td.dg{font-size:14px;line-height:20px;color:#94a3b8;font-variant-numeric:tabular-nums}
.ov-ct .dg-ny{display:inline-block;margin-left:6px;padding:0 6px;border:1px solid #3b4757;border-radius:999px;font-size:12px;line-height:16px;color:#94a3b8;vertical-align:1px}
@media(max-width:699px){.ov-ct td.dg{grid-area:dg;justify-self:end;align-self:start;font-size:13px;line-height:18px;color:#94a3b8;padding-top:1px}.ov-ct td.dg .dg-ny{margin-left:4px}
.ov-ct td.sgt .sgc{white-space:normal;overflow:visible;text-overflow:clip;max-width:100%}.ov-ct td.nmc{min-width:0}}
.lp-note,.lp-list{font-size:13px;line-height:18px;color:#94a3b8}.lp-note{margin:6px 0 2px}.lp-list{list-style:none;margin:0;padding:0}.lp-list li{margin:0;padding:0;white-space:normal;overflow:visible;text-overflow:clip}
@media(max-width:599px){.lp-list li{max-height:40px}.lp-list .lp-r{display:block}.lp-list .lp-r+.lp-g{display:inline}}
"""
