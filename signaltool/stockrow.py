"""Felles aksjerad for Trender-sektorer (og fargeregler delt med Oversikt).

Bare data fra samme snapshot som tickersidene bruker; mangler noe, vises «–» eller «Ikke i datasettet»
(aldri oppdiktede verdier). Fargeregel (bruker 09.11): grønn = positiv kursendring, rød = negativ/flagg,
gul = advarsel (Middels risiko). Grønn brukes aldri på status, score eller kandidater (AnalBot 09.11).
Ingen sortering på score eller avkastning: rekkefølgen følger kjeden/kilden.
"""
from __future__ import annotations
from html import escape

from . import evidens as EV

NOT_IN_DATA = 'Ingen data'   # UxBot/AnalBot 09.11: grå, over hele raden
UNLISTED = 'Ikke børsnotert'
SCORE_HEAD = 'Score (rangering, ikke testet)'


def E(v):
    return escape(str(v), quote=True)


def dm(d) -> str | None:
    d = str(d or '')
    return f'{d[8:10]}.{d[5:7]}' if len(d) >= 10 else None


def pct(x: float) -> str:
    """Fortegn alltid: «+2,1 %», «−3,1 %», «0,0 %» (ekte minus)."""
    v = round(x * 100, 1)
    sign = '+' if v > 0 else '−' if v < 0 else ''
    return f'{sign}{abs(v):.1f}'.replace('.', ',') + ' %'


def ret_cls(x) -> str:
    if x is None:
        return 'r0'
    v = round(x * 100, 1)
    return 'rup' if v > 0 else 'rdn' if v < 0 else 'r0'


def ret(label: str, x, asof, show_date: bool = True) -> str:
    """«20d −3,1 % (per 08.11)»; datoen utelates bare når panelets overskrift bærer samme dato (AnalBot 09.11).
    Mangler kurs eller dato: «20d –» (aldri 0)."""
    d = dm(asof)
    if x is None or d is None:
        return f'<span class="sr-ret r0">{label} –</span>'
    per = f' <span class="sr-per">(per {d})</span>' if show_date else ''
    return f'<span class="sr-ret {ret_cls(x)}">{label} {pct(x)}{per}</span>'


def asof(e: dict | None):
    if not e:
        return None
    return (e.get('stats') or {}).get('last_date') or e.get('_px_date')


def panel_date(rows: list[tuple], snap: dict):
    """Nyeste kursdato blant radene med kursdata (eller None). Eldre rader får egen dato ved verdien."""
    em = entry_map(snap)
    ds = [asof(em.get(r[2])) for r in rows if r[2] in em and not em[r[2]].get('unranked')]
    ds = [str(d)[:10] for d in ds if d]
    return max(ds) if ds else None


def flag_state(sym: str | None, snap: dict) -> tuple[str, str]:
    """('red'|'ok'|'na', tekst). Bare Oslo-aksjer i flagguniverset er sjekket; andre: «ikke sjekket», aldri ✔."""
    if not sym or not sym.endswith('.OL'):
        return 'na', 'ikke sjekket'
    rows = {r.get('ticker'): r for r in snap.get('oslo_universe_flags') or []}
    if sym not in rows:
        return 'na', 'ikke sjekket'
    r = rows[sym]
    if not r.get('flags'):
        return 'ok', '✔ 0'
    n, eb = EV.ntest(r), 'neg_ebit' in r.get('flags', {})
    return 'red', (f'⚑ {n}' + (' + EBIT' if eb else '')) if n else '⚑ bare EBIT'


def flag_badge(sym, snap) -> str:
    st, txt = flag_state(sym, snap)
    return f'<span class="sr-fl fl-{st}">{E(txt)}</span>'


def entry_map(snap: dict) -> dict:
    return {e['ticker']: e for e in snap.get('tickers') or []}


def cells(e: dict | None, sym: str | None, snap: dict, listed: bool = True, pdate=None) -> str:
    """Hovedsignal · 5d / 20d · Risiko · Flagg · Score (UxBot 09.11). Uten data: «Ingen data» over hele raden."""
    from . import overview as OV, site_risk as RK
    if not e:
        miss = NOT_IN_DATA if listed else UNLISTED
        st, _ = flag_state(sym, snap)
        extra = f' · {flag_badge(sym, snap)}' if st != 'na' else ''   # sjekket Oslo-flagg er ekte data, vises
        return f'<td class="sr-miss" colspan="5"><span class="sr-na">{miss}</span>{extra}</td>'
    st = e.get('stats') or {}
    d = asof(e)
    own = d is not None and str(d)[:10] != pdate
    unr = e.get('unranked')
    rt = ('<span class="sr-ret r0">5d –</span> <span class="sr-ret r0">20d –</span>' if unr else
          ret('5d', st.get('ret_5d'), d, own) + ' ' + ret('20d', st.get('ret_20d'), d, own))
    sc = (f'<span class="sr-na">Score {OV._nb(e["score"], 1)} · ikke testet</span>' if e.get('score') is not None
          else '<span class="sr-na">–</span>')
    return (f'<td class="sr-sg">{OV._main_signal(e)}</td><td class="sr-rt">{rt}</td>'
            f'<td class="sr-rk">{RK.chip(e.get("_risk"), small=True, bare=True)}</td>'
            f'<td class="sr-flc">{flag_badge(sym, snap)}</td><td class="sr-sc">{sc}</td>')


def name_cell(name: str, ticker: str | None, sym: str | None, have: set) -> str:
    from .site import slug
    tk = E(ticker) if ticker else UNLISTED
    if sym and sym in have:
        tk = f'<a href="ticker/{E(slug(sym))}.html">{tk}</a>'
    return f'<td class="sr-tk"><b>{tk}</b> <span class="sr-nm">{E(name)}</span></td>'


def date_line(rows: list[tuple], snap: dict) -> str:
    """390: én grå linje øverst i panelet «Kurs per 08.11» (UxBot 09.11)."""
    d = dm(panel_date(rows, snap))
    return f'<p class="sr-kurs">Kurs per {d}</p>' if d else ''


def table(rows: list[tuple], snap: dict, order_col: bool = False) -> str:
    """rows: (navn, ticker|None, symbol i datasettet|None, orden-tekst|None[, region]). Rekkefølgen beholdes."""
    from .ux2 import RISK_LINE
    em = entry_map(snap)
    have = set(em)
    pdate = panel_date(rows, snap)
    rt_head = '5d / 20d' + (f' (per {dm(pdate)})' if pdate else '')
    head = ('<thead><tr><th scope="col">Ticker</th>' + ('<th scope="col">Orden</th>' if order_col else '') +
            f'<th scope="col">Hovedsignal</th><th scope="col">{rt_head}</th><th scope="col">Risiko</th>'
            f'<th scope="col">Flagg</th><th scope="col">{SCORE_HEAD}</th></tr></thead>')
    body = []
    for row in rows:
        name, ticker, sym, order = row[:4]
        rg = f' data-region="{E(row[4])}"' if len(row) > 4 else ''
        oc = f'<td class="sr-or">{E(order)}</td>' if order_col else ''
        body.append(f'<tr{rg}>{name_cell(name, ticker, sym, have)}{oc}'
                    f'{cells(em.get(sym) if sym else None, sym, snap, listed=bool(ticker), pdate=pdate)}</tr>')
    return (f'<table class="sr-t{" sr-ord" if order_col else ""}">{head}<tbody>{"".join(body)}</tbody></table>'
            f'<p class="sr-rkline">{E(RISK_LINE)}</p><p class="sr-note">Flagg: bare Oslo-aksjer er sjekket.</p>')


def status(rows: list[tuple], snap: dict) -> str:
    """AnalBot 09.11: «8 aksjer · 3 Oslo sjekket · 1 med røde flagg»; ingen sjekket: «8 aksjer · ingen sjekket for røde flagg».
    «Aksjer» = børsnoterte selskaper i sektoren; flagg telles bare blant sjekkede Oslo-aksjer (≥ 1 flagg)."""
    n = sum(1 for r in rows if r[1])
    head = f'{n} aksje{"" if n == 1 else "r"}'
    checked = [r[2] for r in rows if r[1] and flag_state(r[2], snap)[0] != 'na']
    if not checked:
        return f'{head} · ingen sjekket for røde flagg'
    red = sum(1 for s in checked if flag_state(s, snap)[0] == 'red')
    return f'{head} · {len(checked)} Oslo sjekket · {red} med røde flagg'


CSS = r"""
.sr-t{width:100%;border-collapse:collapse;font-size:14px;line-height:20px;margin:0 0 8px}
.sr-t th{font-size:12px;line-height:16px;font-weight:600;color:var(--mut);text-align:left;padding:8px;white-space:nowrap;border-bottom:1px solid var(--line)}
.sr-t tr[hidden]{display:none}.sr-t td{padding:8px;border-top:1px solid var(--line);vertical-align:middle}
.sr-tk b a{color:var(--acc)}.sr-nm{color:var(--mut);font-size:13px}
.sr-rt{white-space:nowrap}.sr-ret{white-space:nowrap;font-variant-numeric:tabular-nums}.sr-per{color:var(--mut);font-size:12px}
.rup{color:var(--up)}.rdn{color:var(--down)}.r0{color:var(--mut)}
.sr-fl{display:inline-block;white-space:nowrap;font-size:13px;line-height:18px;padding:1px 8px;border-radius:999px}
.fl-red{color:var(--down);border:1px solid var(--down);font-weight:700}.fl-ok,.fl-na{color:var(--mut)}
.sr-na{color:var(--mut)}.sr-sc{white-space:nowrap;font-variant-numeric:tabular-nums}
.sr-sg .sgc{display:inline-flex;align-items:center;gap:4px;max-width:100%;padding:1px 8px;border-radius:999px;border:1px solid var(--line);background:var(--pill);font-size:12px;line-height:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sr-note,.sr-rkline,.sr-kurs{font-size:13px;line-height:18px;color:var(--mut);margin:0 0 8px}.sr-note{margin-bottom:16px}.sr-kurs{display:none}
@media(max-width:600px){.sr-kurs{display:block}.sr-per{display:inline}.sr-t thead{display:none}.sr-t,.sr-t tbody{display:block;width:100%}
.sr-t tr{display:grid;grid-template-columns:repeat(4,minmax(0,auto));grid-template-areas:"tk tk tk tk" "rt rt rt rt" "sg rk fl sc";justify-content:start;gap:2px 8px;align-items:center;max-height:88px;overflow:hidden;padding:6px 0;border-top:1px solid var(--line)}
.sr-t.sr-ord tr{grid-template-areas:"tk tk tk or" "rt rt rt rt" "sg rk fl sc"}
.sr-t td{display:block;padding:0;border:0;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;line-height:20px}
.sr-t td.sr-tk{grid-area:tk}.sr-t td.sr-or{grid-area:or;justify-self:end;color:var(--mut)}.sr-t td.sr-sg{grid-area:sg}.sr-t td.sr-rt{grid-area:rt}
.sr-t td.sr-rk{grid-area:rk}.sr-t td.sr-flc{grid-area:fl}.sr-t td.sr-sc{grid-area:sc}.sr-t td.sr-miss{grid-row:2;grid-column:1/-1}
.sr-t .rk-s{height:20px}}
"""
