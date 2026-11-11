"""Kandidatlista over tid (UxBot/AnalBot 11.11): endringsstripe på Oversikt, «N dager på rad» i kandidattabellen,
ut-grunner (logs/list_exits.csv), inn/ut-perioder (data/list_periods.json) og periodelinjene under kursgrafen.

Kilde: logs/categories.csv. «Lista» = kandidatlista = loggens rader uten kategori «tema» (temakart-tickere står utenfor
kandidatlista, jf. tickersiden). «Kjøring» = en dato i loggen (helger med); stripen sammenligner siste mot forrige kjøring.
- Stripe: inn = siste − forrige, ut = forrige − siste, står fortsatt = siste ∩ forrige (inn + står fortsatt = dagens antall).
- Dager: sammenhengende kjøringer bakover t.o.m. siste kjøring. Har tickeren stått på lista i hver kjøring siden første
  loggdato: «fra DD.MM» (første loggdato, lest fra loggen). Ikke på lista i siste kjøring: «–».
- Perioder: [inn, ut|None]; ut = første kjøring tickeren manglet (hver manglende kjøring bryter perioden).
- Ut-grunner logges fra 11.11 (record_exits) med kode below_threshold / out_of_top60 / no_price / delisted. Historiske
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
CODES = ("below_threshold", "out_of_top60", "no_price", "delisted")
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
def by_date(path: Path | None = None) -> dict[str, set]:
    """{dato: {tickere på kandidatlista}} fra loggen (tema-rader utenfor). Mangler filen: tom dict."""
    out: dict[str, set] = {}
    for r in _read(path or LOG):
        d, t = (r.get("date") or "").strip(), (r.get("ticker") or "").strip()
        if d and t and (r.get("category") or "") != "tema":
            out.setdefault(d, set()).add(t)
    return out


def scores(path: Path | None = None) -> dict[tuple, str]:
    return {(r["date"], r["ticker"]): r.get("score") or "" for r in _read(path or LOG) if (r.get("category") or "") != "tema"}


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
    ps = periods(by_date(log_path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"source": "logs/categories.csv", "first": min(by_date(log_path), default=None), "periods": ps},
                            ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return len(ps)


# ---------------------------------------------------------------------------------------------------------- grunner
def exits(path: Path | None = None) -> dict[tuple, dict]:
    """{(dato, ticker): rad} fra logs/list_exits.csv; bare godkjente koder teller."""
    return {(r["date"], r["ticker"]): r for r in _read(path or EXITS) if r.get("date") and r.get("ticker")}


def reason_text(row: dict | None) -> str:
    """En av de fire godkjente tekstene, eller "" når koden mangler / tallene mangler."""
    if not row:
        return ""
    c, o, n = row.get("code") or "", row.get("old_score") or "", row.get("new_score") or ""
    try:
        if c == "below_threshold" and o and n:
            return f"Score under grensen ({_nb(o)} → {_nb(n)})"
        if c == "out_of_top60" and n:
            return f"Ikke lenger blant de 60 høyeste (score {_nb(n)})"
    except ValueError:
        return ""
    return {"no_price": "Mangler kurs", "delisted": "Ikke børsnotert"}.get(c, "")


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


def exit_rows(snap: dict, ranked: list[dict], log_path: Path | None = None, today: str | None = None) -> list[dict]:
    """Tickere på lista i forrige kjøring som mangler i dag, med kode bare når kjøringen beviselig avgjør den:
    - delisted: strøket (verdikjede-rettelse med listed=false, dato ≤ i dag).
    - below_threshold: fortsatt kandidat, men score ≤ 0 (grensen i pipeline.run: score > 0), begge score kjent.
    - out_of_top60: fortsatt kandidat med score > 0, men ikke blant de 60 (pipeline/_coverage_cut).
    - no_price: kjøringen fjerner aldri en ticker for manglende kurs (den blir «Ikke rangert» og står på lista) -> skrives ikke.
    Ikke kandidat i dag (ingen score) eller fryst liste (kildefeil): ingen kode."""
    today = today or str(snap.get("date") or "")
    by = by_date(log_path)
    if today not in by:
        return []
    prevs = [d for d in by if d < today]
    if not prevs:
        return []
    prev = max(prevs)
    sc = scores(log_path)
    gone = sorted(by[prev] - by[today])
    cand = {e["ticker"]: e.get("score") for e in ranked}
    dl = _delisted(today)
    in_snap = {e["ticker"] for e in snap.get("tickers") or []}
    frozen = bool(snap.get("frozen_from")) or any(e.get("frozen") for e in snap.get("tickers") or [])
    out = []
    for t in gone:
        old, new = sc.get((prev, t), ""), cand.get(t)
        code = ""
        if t in dl:
            code = "delisted"
        elif frozen or new is None or t in in_snap:   # står i snapshotet (f.eks. ikke loggbar): ikke kuttet
            code = ""
        elif new <= 0 and old not in ("", None):
            code = "below_threshold"
        elif new > 0:
            code = "out_of_top60"
        out.append({"date": today, "ticker": t, "code": code, "old_score": old, "new_score": "" if new is None else new})
    return out


def record_exits(snap: dict, ranked: list[dict], path: Path | None = None, log_path: Path | None = None) -> int:
    """Skriver dagens utfall til logs/list_exits.csv (en ny kjøring samme dag erstatter dagens rader). Leser bare snap/ranked."""
    p = Path(path or EXITS)
    rows = exit_rows(snap, ranked, log_path)
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


def strip_html(snap: dict | None = None, path: Path | None = None, exits_path: Path | None = None) -> str:
    """«Siden DD.MM: N inn · N ut · N står fortsatt» som <details>; trykk åpner gruppene Inn, Ut og ev. «Ute pga. manglende kurs»."""
    dd = diff(by_date(path))
    if not dd:
        return ""
    pages = {e["ticker"] for e in (snap or {}).get("tickers") or [] if e.get("ticker")} if snap is not None else None
    ex, nr = exits(exits_path), no_reason(exits_path)
    line = f'Siden {_dm(dd["prev"])}: {len(dd["inn"])} inn · {len(dd["ut"])} ut · {len(dd["stay"])} står fortsatt'
    np_ = [t for t in dd["ut"] if (ex.get((dd["last"], t)) or {}).get("code") == "no_price"]
    ut = [t for t in dd["ut"] if t not in np_]
    sub = lambda t: f'Ut {_dm(dd["last"])}: {ut_text(dd["last"], t, ex, nr)}'

    def grp(name, chips, n):
        body = "".join(chips) if chips else '<span class="chg-0">Ingen</span>'
        return f'<div class="chg-grp"><h3>{E(name)} ({n})</h3><div class="chg-cs">{body}</div></div>'

    g = grp("Inn", [_chip(t, "+", pages) for t in dd["inn"]], len(dd["inn"])) + grp("Ut", [_chip(t, "−", pages, sub(t)) for t in ut], len(ut))
    if np_:
        g += grp(NO_PRICE_HEAD, [_chip(t, "−", pages, sub(t)) for t in np_], len(np_))
    return (f'<details class="ov-chg" data-last="{E(dd["last"])}" data-prev="{E(dd["prev"])}"><summary><span class="chg-l">{E(line)}</span></summary>'
            f'<div class="chg-p">{g}</div></details>')


def days_cell(t: str, dmap: dict[str, int], first: str | None = None, n_runs: int | None = None) -> str:
    n = dmap.get(t)
    if n is None:
        return '<td class="dg"><span class="dgv">–</span></td>'
    if first and n_runs and n >= n_runs:
        return f'<td class="dg"><span class="dgv">fra {_dm(first)}</span></td>'
    ny = '<span class="dg-ny">Ny</span>' if n == 1 else ""
    return f'<td class="dg"><span class="dgv">{n} {"dag" if n == 1 else "dager"} på rad</span>{ny}</td>'


def days_ctx(path: Path | None = None) -> tuple[dict, str | None, int]:
    by = by_date(path)
    return days(by), (min(by) if by else None), len(by)


# ---------------------------------------------------------------------------------------------------------- tickergraf
def ticker_periods(t: str, path: Path | None = None, exits_path: Path | None = None) -> list[dict]:
    """[{inn, ut, first, text, lead, why, title}] for tickersiden; tom liste når tickeren aldri har stått på lista."""
    by = by_date(path)
    ps = periods(by).get(t) or []
    if not ps:
        return []
    first = min(by)
    ex, nr = exits(exits_path), no_reason(exits_path)
    out = []
    for inn, ut in ps:
        a = f"på lista fra før {_dm(first)}" if inn == first else f"Inn {_dm(inn)}"
        if ut is None:
            lead, why = f"{a} · på lista nå", ""
            title = lead[0].upper() + lead[1:]
        else:
            lead, why = f"{a} · Ut {_dm(ut)}:", ut_text(ut, t, ex, nr)
            title = f"Ut {_dm(ut)}: {why}"
        out.append({"inn": inn, "ut": ut, "first": inn == first, "lead": lead, "why": why, "title": title,
                    "text": lead + (" " + why if why else "")})
    return out


def periods_html(ps: list[dict]) -> str:
    if not ps:
        return ""
    li = "".join(f'<li><span class="lp-a">{E(p["lead"])}</span>' + (f' <span class="lp-r">{E(p["why"])}</span>' if p["why"] else "") + "</li>" for p in ps)
    return f'<p class="lp-note">{E(CHART_NOTE)}</p><ul class="lp-list">{li}</ul>'


CSS = """
.ov-chg{margin:0 0 8px;border:1px solid #3b4757;border-radius:6px;background:#111821;color:#cbd5e1}
.ov-chg>summary{box-sizing:border-box;display:flex;align-items:center;min-height:48px;padding:5px 12px;font-size:14px;line-height:19px;cursor:pointer;list-style:none}
.ov-chg>summary::-webkit-details-marker{display:none}.ov-chg>summary::after{content:"▾";margin-left:auto;padding-left:8px;color:#94a3b8}.ov-chg[open]>summary::after{content:"▴"}
.ov-chg .chg-l{min-width:0}.ov-chg .chg-p{padding:0 12px 8px}.ov-chg h3{margin:4px 0;font-size:13px;line-height:18px;font-weight:600;color:#94a3b8}
.ov-chg .chg-cs{display:flex;flex-wrap:wrap;gap:6px}
.ov-chg .chg-c{box-sizing:border-box;display:inline-flex;flex-wrap:wrap;align-items:center;justify-content:center;column-gap:4px;min-width:44px;min-height:44px;padding:4px 10px;border:1px solid #3b4757;border-radius:6px;background:#1c2430;color:#cbd5e1;font-size:14px;line-height:20px;text-decoration:none}
.ov-chg a.chg-c:hover,.ov-chg a.chg-c:focus-visible{border-color:#94a3b8}
.ov-chg .chg-g{color:#94a3b8;font-weight:600}.ov-chg .chg-why{flex-basis:100%;text-align:center;font-size:13px;line-height:18px;color:#94a3b8}.ov-chg .chg-0{font-size:13px;line-height:18px;color:#94a3b8}
.ov-ct th.dg-h,.ov-ct td.dg{text-align:right;white-space:nowrap}.ov-ct td.dg{font-size:14px;line-height:20px;color:#94a3b8;font-variant-numeric:tabular-nums}
.ov-ct .dg-ny{display:inline-block;margin-left:6px;padding:0 6px;border:1px solid #3b4757;border-radius:999px;font-size:12px;line-height:16px;color:#94a3b8;vertical-align:1px}
@media(max-width:699px){.ov-ct td.dg{grid-area:dg;justify-self:end}.ov-ct .sgc{white-space:normal;overflow:visible;text-overflow:clip}}
.lp-note,.lp-list{font-size:13px;line-height:18px;color:#94a3b8}.lp-note{margin:6px 0 2px}.lp-list{list-style:none;margin:0;padding:0}.lp-list li{margin:0;padding:0;white-space:normal;overflow:visible;text-overflow:clip}
@media(max-width:599px){.lp-list li{max-height:40px}.lp-list .lp-r{display:block}}
"""
