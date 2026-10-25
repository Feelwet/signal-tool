"""Evidensnivå per signal – ÉN plass. AnalBot kan flytte signaler mellom nivåer her (f.eks. etter nye tester).

Nivåer for røde flagg leses fra logs/red_flag_evidence.json (AnalBot). Øvrige:
  testet    «⚑ Testet her, sterkest»       oransje  – testet ut-av-utvalg her, men IKKE stabilt nok etter egen regel
  litteratur «❖ Litteratur, ikke testet her» grå     – støtte i litteraturen, ikke bestått egen test
  eksp      «⚗ Eksperimentelt»              grå     – eget eksperiment, svak/uavklart evidens
  oppm      «◌ Bare oppmerksomhet»          grå stiplet – oppmerksomhet/aktivitet, ikke testet som signal
"""
from __future__ import annotations
import html

E = lambda x: html.escape("" if x is None else str(x))

import json
from pathlib import Path
from . import site_layout as L

EVFILE = Path(__file__).resolve().parent.parent / "logs" / "red_flag_evidence.json"
EVREPORT = "https://github.com/feelwet/signal-tool/blob/master/reports/natt/red_flags_oslo.md"

LEVELS = {
    "testet": ("⚑", "Testet her", "ev-testet"),
    "litteratur": ("📚", "Litteratur, ikke testet her", "ev-lit"),
    "eksp": ("⚗", "Eksperimentelt", "ev-eksp"),
    "oppm": ("◌", "Bare oppmerksomhet", "ev-oppm"),
}
# AnalBot's file keys/levels -> ours
FILE_KEYS = {"weak_px": "svak_momentum_12_1", "high_vol": "hoy_volatilitet", "placement": "rettet_emisjon_60d", "neg_ebit": "negativ_ebit_ttm"}
FILE_LEVEL = {"testet": "testet", "testet_her": "testet", "eksperimentell": "eksp", "eksperimentelt": "eksp", "ikke_testet": "litteratur", "litteratur": "litteratur"}
_n = lambda x, d=1: f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def _flag_text(name: str, r: dict, lv: str) -> str:
    if lv == "litteratur" or r.get("effekt_60d") is None:
        return f"{name}: ikke testet her (mangler punkt-i-tid-data). Kun støtte i litteraturen."
    parts = [f"{name}: {_n(r['effekt_60d']*100)} % mot snittaksjen over 60 dager"]
    if r.get("t_oos") is not None:
        parts.append(f"t {_n(r['t_oos'])} etter 2018" if r.get("t_is") is not None else f"t {_n(r['t_oos'])} (data bare fra 2019)")
    if r.get("n"):
        parts.append(f"n ≈ {_n(r['n'])} aksjer per dato")
    t = ", ".join(parts) + "."
    if lv != "testet":
        t += (f" Ikke bestått testkravet: t {_n(r['t_is'])} før 2018." if r.get("t_is") is not None
              else " Ikke bestått testkravet: |t| < 3 og ingen periode før 2019.")
    return t


def load_red(path: Path = EVFILE) -> dict[str, tuple[str, str]]:
    try:
        J = json.loads(path.read_text())
    except Exception:
        J = {}
    names = {"weak_px": "Svak 12-1-momentum", "high_vol": "Høy volatilitet", "placement": "Rettet emisjon siste 60 d", "neg_ebit": "Negativt driftsresultat"}
    out = {}
    for k, fk in FILE_KEYS.items():
        r = J.get(fk)
        if r is None:
            out[k] = ("litteratur", f"{names[k]}: evidensnivå ikke satt ennå.")
            continue
        lv = FILE_LEVEL.get(str(r.get("evidens")), "eksp")
        out[k] = (lv, _flag_text(names[k], r, lv))
    r = J.get("to_pluss_flagg")
    if r is not None:
        lv = FILE_LEVEL.get(str(r.get("evidens")), "eksp")
        t = f"2+ flagg: {_n(r['effekt_60d']*100)} % mot alle aksjer over 60 dager (t {_n(r['t_oos'])}) etter 2018"
        t += f", n ≈ {_n(r['n'])} aksjer per dato." if r.get("n") else "."
        if lv != "testet" and r.get("t_is") is not None:
            t += f" Ikke bestått testkravet: t {_n(r['t_is'])} i 2014–18, testet etter at enkeltflaggene var sett."
        t += " Telles bare på svak kurs, høy volatilitet og rettet emisjon (de testede flaggene); negativ EBIT vises, men teller ikke."
        out["two_plus"] = (lv, t)
    else:
        out["two_plus"] = ("eksp", "2+ flagg: evidensnivå ikke satt ennå.")
    return out


evidens: dict[str, tuple[str, str]] = {
    **load_red(),
    "pead": ("eksp", "Sterk kvartalsrapport (PEAD): eksperimentelt, svak evidens; treffrate måles i forward-loggen."),
    "pead_s": ("eksp", "PEAD-S: eksperimentelt, svak evidens."),
    "theme": ("eksp", "Temascore: ikke testet mot kursutvikling ennå; logges daglig, treffrate måles ved n ≥ 100."),
    "gdelt": ("oppm", "GDELT-oppmerksomhet: ikke testet som kjøps-/salgssignal."),
    "unusual_volume": ("oppm", "Uvanlig volum: oppmerksomhet, ikke testet som signal."),
    "price_move": ("oppm", "Kursbevegelse: oppmerksomhet, ikke testet som signal."),
    "theme_unconfirmed": ("oppm", "Tema uten bekreftelse: bare oppmerksomhet."),
    "physical": ("oppm", "Fysiske data (skipstrafikk o.l.): oppmerksomhet, ikke testet som signal."),
}

DEFAULT = "oppm"
RED_FLAGS = ["weak_px", "neg_ebit", "placement", "high_vol"]

CSS = """
.evb{display:inline-block;border:1px solid #8b949e;color:#9ea9b5;background:transparent;border-radius:0;padding:0 5px;font-size:.72rem;font-weight:600;white-space:nowrap;vertical-align:middle;margin-right:6px}
.evb.ev-testet{border-color:#f0883e;color:#f0883e}
.evb.ev-lit{border-color:#f0883e;border-style:dashed}
.evb.ev-oppm{border-style:dashed}
.evrow{display:flex;align-items:flex-start;gap:4px;flex-wrap:wrap}
.rfl{list-style:none;padding:0;margin:0}.rfl li{padding:4px 0;border-bottom:1px solid #21262d;overflow-wrap:anywhere}
.summary p{margin:2px 0}
.why.clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.why.clamp.open{display:block}
.mer{background:none;border:0;color:var(--acc);padding:0;font:inherit;font-size:.8rem;cursor:pointer;min-height:24px}
td.tint.tup{background:rgba(63,185,80,.12)}td.tint.tdn{background:rgba(248,81,73,.12)}
.rfc{border:1px solid #30363d;border-radius:6px;padding:8px 10px;margin:0 0 8px;background:var(--card,#161b22)}
.rfc .top{display:flex;justify-content:space-between;gap:8px}.rfc .fb{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0}
.rfc details summary{cursor:pointer;color:var(--acc);font-size:.85rem;min-height:24px}.rfc details .evrow{font-size:.85rem;margin:4px 0}
"""


def level(key: str) -> str:
    return evidens.get(key, (DEFAULT, ""))[0]


def badge(key: str, extra: str = "") -> str:
    """Badge for a signal key: always placed first on its row, with an «i» showing n/treffrate where known."""
    lv, tip = evidens.get(key, (DEFAULT, ""))
    tip += extra
    ic, txt, cls = LEVELS[lv]
    i = L.info_tip(tip, txt)
    return f'<span class="evb {cls}">{ic} {E(txt)}</span>{i} '


def _plain(k: str) -> str:
    ic, txt, cls = LEVELS[level(k)]
    return f'<span class="evb {cls}">{ic} {E(txt)}</span> '


def focus_key(it: dict) -> str:
    """Map a «Hva bør jeg se på i dag?» item to a signal key."""
    s = f'{it.get("title", "")} {it.get("why", "")}'.lower()
    ln = str(it.get("link", ""))
    if "kvartalsrapport" in s or "pead" in s:
        return "pead"
    if ln.startswith("tema/"):
        return "theme"
    if "sund" in ln or "passeringer" in s:
        return "physical"
    if "svak kurs" in s:
        return "weak_px"
    return DEFAULT


# ---------------------------------------------------------------- Røde flagg Oslo (page, top-5, summary)
FLAG_SHORT = {"weak_px": "svak kurs", "neg_ebit": "negativ EBIT", "placement": "rettet emisjon", "high_vol": "høy volatilitet"}
TITLE = "Røde flagg Oslo · verdt å undersøke"


def red_rows(snap: dict) -> list[dict]:
    """Liquid Oslo stocks with ≥ 1 red flag, most flags first (weak price breaks ties)."""
    rows = [r for r in snap.get("oslo_universe_flags") or [] if r.get("flags")]
    return sorted(rows, key=lambda r: (-ntest(r), min([TESTED.index(k) for k in r["flags"] if k in TESTED] or [9]), r["ticker"]))


TESTED = ["weak_px", "high_vol", "placement"]        # counted/sorted (strongest first); neg_ebit shown but not counted


def ntest(r: dict) -> int:
    return sum(1 for k in r.get("flags", {}) if k in TESTED)


def nlabel(r: dict) -> str:
    n, eb = ntest(r), "neg_ebit" in r.get("flags", {})
    return (f"{n} flagg" + (" + EBIT" if eb else "")) if n else "bare EBIT"


def coverage(snap: dict) -> dict:
    meta = snap.get("oslo_flags_meta") or {}
    uni = snap.get("oslo_universe_flags") or []
    return {"n": len(uni), "ebit": sum(1 for r in uni if r.get("ebit_known")), "newsweb": bool(meta.get("newsweb_ok", meta.get("newsweb_days"))),
            "asof": meta.get("asof"), "by_flag": {k: sum(1 for r in uni if k in r.get("flags", {})) for k in RED_FLAGS}}


def _flag_items(r: dict, pre: str = "", noi: bool = False) -> str:
    return "".join(f'<div class="evrow">{badge(k, "") if not noi else _plain(k)}<span>{E(r["flags"][k])}</span></div>' for k in RED_FLAGS if k in r["flags"])


def short_badge(k: str, extra: str = "") -> str:
    ic, _, cls = LEVELS[level(k)]
    return f'<span class="evb {cls}">{ic} {E(FLAG_SHORT[k])}</span>'


def _legend(keys, ebx: str = "") -> str:
    """Én kort forklaring per flaggtype øverst i gruppen (erstatter «i» på hvert merke)."""
    li = "".join(f'<li>{short_badge(k)} <span class="mut">{E(evidens.get(k, ("", ""))[1] + (ebx if k == "neg_ebit" else ""))}</span></li>' for k in keys)
    return f'<ul class="rfl rflegend" style="font-size:.85em;margin:0 0 8px">{li}</ul>' if li else ""


def red_page(snap: dict) -> str:
    rows, c = red_rows(snap), coverage(snap)
    if not c["n"]:
        return (f'<h1>{E(TITLE)}</h1><p class="warnline">Flaggene er ikke beregnet i denne kjøringen (mangler Oslo-univers). '
                'Ingen tall vises heller enn oppdiktede.</p>')
    ebx = (f" Dekning: negativ EBIT er bare kjent for {c['ebit']} av {c['n']} aksjer (resten mangler regnskapstall fra Yahoo) – manglende ≠ positiv EBIT."
           if c["ebit"] < c["n"] else "")
    warn = "" if c["newsweb"] else '<p class="warnline">Newsweb var utilgjengelig: rettet emisjon er ikke beregnet i denne kjøringen.</p>'
    card = lambda r: (f'<div class="rfc"><div class="top"><b><a href="https://finance.yahoo.com/quote/{E(r["ticker"])}">{E(r["ticker"])}</a></b>'
                      f'<span class="mut">{E(nlabel(r))}</span></div><div class="fb">'
                      + "".join(short_badge(k, ebx if k == "neg_ebit" else "") for k in RED_FLAGS if k in r["flags"])
                      + f'</div><details><summary>Vis mer</summary>{_flag_items(r, noi=True)}</details></div>')
    multi, single, ebo = ([r for r in rows if ntest(r) >= 2], [r for r in rows if ntest(r) == 1], [r for r in rows if ntest(r) == 0])
    grp = lambda title, rs, open_: (f'<details class="fold"{" open" if open_ else ""}><summary><h2>{title}</h2></summary>'
                                    f'<div class="fold-body">{_legend([k for k in RED_FLAGS if any(k in r["flags"] for r in rs)], ebx)}{"".join(card(r) for r in rs)}</div></details>')
    return (f'<h1>{E(TITLE)}</h1><p class="pintro">Likvide Oslo-aksjer med røde flagg, verdt å undersøke nærmere – ingen flagg har bestått '
            f'testkravet (se forklaringen øverst i hver gruppe, <a href="metode.html">Metode</a>, <a href="{EVREPORT}">testrapport</a>); data per {E(c["asof"])}.</p>' + warn
            + grp(f'{badge("two_plus")}2+ flagg ({len(multi)})', multi, True)
            + grp(f'1 flagg ({len(single)}), ingen målt underavkastning', single, False)
            + grp(f'{badge("neg_ebit", ebx)}Bare negativ EBIT ({len(ebo)}), ikke testet', ebo, False))


def red_top5(snap: dict) -> str:
    rows, c = red_rows(snap), coverage(snap)
    if not c["n"]:
        return '<div class="card" id="rodeflagg"><h2 style="margin-top:0">Røde flagg Oslo</h2><p class="mut">Ikke beregnet i denne kjøringen.</p></div>'
    top = rows[:5]
    li = lambda r: (f'<li><b>{E(r["ticker"])}</b> · {E(nlabel(r))} – {E(", ".join(FLAG_SHORT[k] for k in RED_FLAGS if k in r["flags"]))}</li>')
    m1, s1 = [r for r in top if ntest(r) >= 2], [r for r in top if ntest(r) < 2]
    lis = ((f'<li class="evrow">{badge("two_plus")}<b>2+ flagg</b></li>' + "".join(li(r) for r in m1)) if m1 else "") + \
          (('<li class="mut"><b>Under 2 testede flagg</b></li>' + "".join(li(r) for r in s1)) if s1 else "")
    return (f'<div class="card" id="rodeflagg"><h2 style="margin-top:0">{E(TITLE)}</h2><ul class="rfl">{lis}</ul>'
            f'<p style="margin:6px 0 0"><a href="rode-flagg.html">Se alle ({len(rows)}) →</a> <span class="mut">data per {E(c["asof"])}</span></p></div>')


def summary(snap: dict) -> list[str]:
    reg = snap.get("regime") or {}
    o = reg.get("OSEBX.OL") or {}
    s = reg.get("^GSPC") or {}
    def rtxt(v, n):
        if not v:
            return f"{n}: ukjent"
        return f'{n} {"under" if v.get("below") else "over"} 10-mnd snitt{", høy volatilitet" if v.get("high_vol") else ""}'
    risk = any(v.get("risk_off") for v in reg.values())
    l1 = f'Markedsregime: {"halver nye posisjoner" if risk else "normalt"} ({rtxt(o, "OSEBX")}, {rtxt(s, "S&P 500")}).'
    rows, c = red_rows(snap), coverage(snap)
    l2 = (f"{len(rows)} av {c['n']} likvide Oslo-aksjer har røde flagg i dag." if c["n"] else "Røde flagg Oslo er ikke beregnet i denne kjøringen.")
    nk = sum(1 for e in snap.get("tickers", []) if e.get("category") == "kjop")
    l3 = "Ingen kjøp-kandidater i dag, det er normalt." if nk == 0 else f"{nk} kjøp-kandidat{'er' if nk > 1 else ''} i dag – verdt å undersøke, ikke råd."
    foc = [f["title"] for f in ((snap.get("briefing") or {}).get("focus") or [])[:2]]
    l4 = ("Se på: " + "; ".join(foc) + ".") if foc else "Ingenting spesielt å se på i dag."
    return [l1, l2, l3, l4]


def summary_html(snap: dict) -> str:
    return '<div class="card summary" id="oppsummering">' + "".join(f"<p>{E(x)}</p>" for x in summary(snap)) + "</div>"


def focus_html(snap: dict, link=lambda x: x) -> str:
    items = ((snap.get("briefing") or {}).get("focus") or [])[:5]
    lis = "".join(f'<li class="evrow">{badge(focus_key(it))}{"🔔 " if it.get("level") == "alert" else ""}'
                  f'<a href="{E(link(it.get("link", "")))}" title="{E(it.get("why"))}">{E(it["title"])}</a></li>' for it in items)
    if not lis:
        lis = '<li class="mut">Ingenting som krever oppmerksomhet i dag.</li>'
    return f'<div class="card hl" id="fokus"><h2 style="margin-top:0">🎯 Hva bør jeg se på i dag?</h2><ul class="rfl">{lis}</ul><p class="mut" style="margin:4px 0 0">Verdt å undersøke – ikke råd. Hold musen over / trykk for begrunnelse.</p></div>'
