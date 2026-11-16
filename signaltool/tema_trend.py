"""Trend på Temaer fra logs/tema_match_sjekk.csv (AnalBot/UxBot 16.11).

Mål: temaets andel av dagens overskrifter, ikke råtall og ikke logs/theme_score.csv.
Periode: snitt 7 dager mot de 21 dagene før (28 kalenderdager). Første gyldige
visning 2026-12-02, og bare når temamatch_ok er satt (AnalBot ≥27/30).
Til da: bare grå tekst «For lite data (x/28 dager)», ingen sparkline, stripe skjult,
kolonnen ikke sorterbar. Etter 02.12: «For få treff (n<30)» om 7-dagersvinduet
har under 30 treff. Etikett Mer/Mindre omtale bare ved relativ endring ≥50 % og
|z| ≥ 2 mot temaets daglige andeler i de 21 dagene; ellers «Uendret».
Ingen grønn/rød (grønn er reservert for positiv historisk kursendring).
Manglende dager i loggen markeres og fylles ikke.
"""
from __future__ import annotations

import csv
import math
import statistics
from datetime import date, datetime, timedelta
from html import escape as _esc
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "tema_match_sjekk.csv"
CONFIG = ROOT / "site_config" / "tema_trend.yaml"
FIRST_ACTIVE = date(2026, 12, 2)
MIN_HITS_7 = 30
REL_TH = 0.50
Z_TH = 2.0
NOTE = "Omtale, ikke kurs. Ikke testet som signal."
COL = "Trend 7d mot 21d før"
NEUTRAL = "#c8d1da"
MUT = "#94a3b8"
INK = "#e6edf3"
NEEDED = 28

def E(s) -> str:
    return _esc("" if s is None else str(s), quote=True)


def _fmt_pct(x, d=0) -> str:
    """Fortegn, desimalkomma og minustegn, uten fargeklasse."""
    if x is None or not math.isfinite(x):
        return "–"
    s = f"{x * 100:+.{d}f}".replace(".", ",").replace("-", "\u2212")
    if d and s.endswith(",0"):
        s = s[:-2]
    return s + "\u00a0%"


def as_of_from(snap) -> date:
    raw = (snap or {}).get("date") or ""
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return datetime.now().date()


def temamatch_ok(path: Path | None = None) -> bool:
    p = Path(path) if path else CONFIG
    if not p.exists():
        return False
    data = yaml.safe_load(p.read_text()) or {}
    return bool(data.get("temamatch_ok"))


def is_active(as_of: date, ok: bool) -> bool:
    return bool(ok) and as_of >= FIRST_ACTIVE


def load_rows(path: Path | None = None) -> list[dict]:
    p = Path(path) if path else LOG
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [{k: (r.get(k) or "").strip() for k in ("dato", "url", "tittel", "kilde", "tema")}
                for r in csv.DictReader(f) if (r.get("dato") or "").strip()]


def daily_shares(rows: list[dict]) -> dict[date, dict]:
    """Per dato: total = unike overskrifter (url, ellers tittel+kilde), andel per tema."""
    by: dict[date, list[dict]] = {}
    for r in rows:
        try:
            d = date.fromisoformat(r["dato"][:10])
        except ValueError:
            continue
        by.setdefault(d, []).append(r)
    out = {}
    for d, rs in by.items():
        keys, theme_hits = set(), {}
        for r in rs:
            k = r["url"] or (r["tittel"], r["kilde"])
            keys.add(k)
            theme_hits[r["tema"]] = theme_hits.get(r["tema"], 0) + 1
        n = len(keys) or 1
        out[d] = {"n": len(keys), "hits": theme_hits,
                  "share": {t: c / n for t, c in theme_hits.items()}}
    return out


def _window(end: date, days: int) -> list[date]:
    return [end - timedelta(days=days - 1 - i) for i in range(days)]


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _z(mean_7: float, xs_21: list[float]) -> float:
    if not xs_21:
        return 0.0
    mu = _mean(xs_21)
    if mu is None:
        return 0.0
    if len(xs_21) < 2:
        return 0.0 if mean_7 == mu else math.inf
    sd = statistics.stdev(xs_21)
    if sd == 0:
        return 0.0 if mean_7 == mu else math.inf
    return (mean_7 - mu) / sd


def ma7(series: dict[date, float | None], d: date) -> float | None:
    """7-dagers glidende snitt av tilgjengelige andeler, bare hvis dagen selv er logget."""
    if d not in series or series[d] is None:
        return None
    vals = [series[d - timedelta(days=k)] for k in range(7)
            if (d - timedelta(days=k)) in series and series[d - timedelta(days=k)] is not None]
    return _mean(vals)


def logged_days(shares: dict[date, dict], until: date) -> int:
    return sum(1 for d in shares if d <= until)


def thin_text(as_of: date, shares: dict[date, dict], hits_7: int | None = None) -> str:
    """Inaktiv kolonne (før 02.12 eller flagg av): alltid «For lite data (x/28 dager)».
    «For få treff» brukes bare i compute() når trenden er aktiv."""
    x = min(NEEDED, logged_days(shares, as_of))
    return f"For lite data ({x}/{NEEDED} dager)"


def compute(theme: str, shares: dict[date, dict], as_of: date, ok: bool) -> dict:
    """Én temarad. active=False => bare tynn tekst, ingen sparkline/etikett."""
    end_7 = as_of
    days_7 = _window(end_7, 7)
    days_21 = _window(end_7 - timedelta(days=7), 21)
    days_28 = _window(end_7, 28)
    series = {d: (shares[d]["share"].get(theme) if d in shares else None) for d in days_28}
    # series only has last 28; ma7 needs 6 days before the first of those
    for d in days_28:
        for k in range(7):
            dd = d - timedelta(days=k)
            if dd not in series:
                series[dd] = shares[dd]["share"].get(theme) if dd in shares else None
    hits_7 = sum((shares[d]["hits"].get(theme, 0) if d in shares else 0) for d in days_7)
    xs_7 = [shares[d]["share"].get(theme, 0.0) for d in days_7 if d in shares]
    xs_21 = [shares[d]["share"].get(theme, 0.0) for d in days_21 if d in shares]
    mean_7, mean_21 = _mean(xs_7), _mean(xs_21)
    chg = None if mean_7 is None or mean_21 is None else mean_7 - mean_21
    if mean_7 is None or mean_21 is None:
        rel = None
    elif mean_21 == 0:
        rel = math.inf if mean_7 > 0 else 0.0
    else:
        rel = (mean_7 / mean_21) - 1.0
    z = _z(mean_7, xs_21) if mean_7 is not None else 0.0
    ma_pts = [ma7(series, d) if d in shares else None for d in days_28]
    missing = [d for d in days_28 if d not in shares]
    active = is_active(as_of, ok)
    if not active:
        return {"active": False, "thin": True, "label": None, "text": thin_text(as_of, shares),
                "change": None, "rel": rel, "z": z, "hits_7": hits_7, "mean_7": mean_7,
                "mean_21": mean_21, "ma": ma_pts, "missing": missing, "sort": None}
    if hits_7 < MIN_HITS_7:
        return {"active": True, "thin": True, "label": None,
                "text": f"For få treff (n<{MIN_HITS_7})",
                "change": chg, "rel": rel, "z": z, "hits_7": hits_7, "mean_7": mean_7,
                "mean_21": mean_21, "ma": ma_pts, "missing": missing, "sort": None}
    passed = (rel is not None and abs(rel) >= REL_TH and abs(z) >= Z_TH)
    if passed and rel > 0:
        label = "Mer omtale"
    elif passed and rel < 0:
        label = "Mindre omtale"
    else:
        label = "Uendret"
    return {"active": True, "thin": False, "label": label, "text": None,
            "change": chg, "rel": rel, "z": z, "hits_7": hits_7, "mean_7": mean_7,
            "mean_21": mean_21, "ma": ma_pts, "missing": missing, "sort": chg}


def spark_svg(vals: list[float | None], w=120, h=32, *, dashed=False, dot=True, baseline=True) -> str:
    """Sparkline uten akser. None = brudd. Én nøytral farge. Stiplet grunnlinje på startverdi."""
    pts = [(i, v) for i, v in enumerate(vals) if v is not None]
    if not pts:
        return ""
    lo, hi = min(v for _, v in pts), max(v for _, v in pts)
    rng = (hi - lo) or 1.0
    n = max(len(vals) - 1, 1)

    def xy(i, v):
        return i * (w - 2) / n + 1, h - 1 - (v - lo) / rng * (h - 2)

    segs, cur = [], []
    for i, v in enumerate(vals):
        if v is None:
            if cur:
                segs.append(cur); cur = []
        else:
            cur.append((i, v))
    if cur:
        segs.append(cur)
    dash = ' stroke-dasharray="4 4"' if dashed else ""
    parts = []
    if baseline:
        y0 = xy(pts[0][0], pts[0][1])[1]
        parts.append(f'<line x1="1" y1="{y0:.2f}" x2="{w-1}" y2="{y0:.2f}" stroke="{MUT}" '
                     f'stroke-width="1" stroke-dasharray="2 2" fill="none"/>')
    for seg in segs:
        if len(seg) == 1:
            x, y = xy(seg[0][0], seg[0][1])
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.2" fill="{NEUTRAL}"/>')
            continue
        points = " ".join(f"{xy(i,v)[0]:.2f},{xy(i,v)[1]:.2f}" for i, v in seg)
        parts.append(f'<polyline fill="none" stroke="{NEUTRAL}" stroke-width="1.5"{dash} points="{points}"/>')
    if dot:
        x, y = xy(pts[-1][0], pts[-1][1])
        parts.append(f'<circle class="tt-dot" cx="{x:.2f}" cy="{y:.2f}" r="2" fill="{NEUTRAL}"/>')
    return (f'<svg class="tt-spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'aria-hidden="true">{"".join(parts)}</svg>')


def _change_html(tr: dict, *, mobile: bool) -> str:
    if tr["thin"] or not tr["active"]:
        return f'<span class="tt-thin">{E(tr["text"])}</span>'
    rel = tr["rel"]
    if rel is None:
        chg_s = "–"
    elif not math.isfinite(rel):
        chg_s = "ny omtale"
    else:
        chg_s = f"{_fmt_pct(rel, 0)} omtale"
    arrow = ""
    lab = tr["label"] or "Uendret"
    if lab == "Mer omtale":
        arrow = '<span class="tt-arr" aria-hidden="true">▲</span> '
    elif lab == "Mindre omtale":
        arrow = '<span class="tt-arr" aria-hidden="true">▼</span> '
    lab_h = "" if mobile else f'<span class="tt-lab">{E(lab)}</span> '
    return (f'{arrow}{lab_h}<span class="tt-chg">{chg_s}</span>'
            f'<span class="tt-per">, 7d</span>')


def _n_tickers(t: dict) -> int:
    tk = t.get("tickers")
    if isinstance(tk, list):
        return len(tk)
    return 0


def _n_label(n: int) -> str:
    return "1 ticker" if n == 1 else f"{n} tickere"


def _sort_themes(items: list[tuple[dict, dict]]) -> list[tuple[dict, dict]]:
    rest = [(t, tr) for t, tr in items if not tr["thin"]]
    thin = [(t, tr) for t, tr in items if tr["thin"]]
    rest.sort(key=lambda it: (it[1]["sort"] is None, -(it[1]["sort"] or 0)))
    return rest + thin


def stripe_html(items: list[tuple[dict, dict]], pre: str = "") -> str:
    mer = [(t, tr) for t, tr in items if tr.get("label") == "Mer omtale"][:3]
    minr = [(t, tr) for t, tr in items if tr.get("label") == "Mindre omtale"]
    minr.sort(key=lambda it: (it[1]["sort"] is None, it[1]["sort"] or 0))
    minr = minr[:3]
    if not mer and not minr:
        return ""
    def grp(title, rows):
        if not rows:
            return ""
        lis = "".join(
            f'<a class="tt-si" href="{E(pre)}tema/{E(t["key"])}.html">{E(t["name"])}'
            f'<span class="tt-per">{_fmt_pct(tr["rel"], 0)}</span></a>'
            for t, tr in rows)
        return f'<div class="tt-sg"><span class="tt-sg-h">{E(title)}</span>{lis}</div>'
    return f'<div class="tt-stripe">{grp("Mer omtale", mer)}{grp("Mindre omtale", minr)}</div>'


def cell_and_mobile(tr: dict) -> tuple[str, str]:
    """Desktop-celle og innhold til linje 2 på 390."""
    if not tr["active"] or (tr["thin"] and not tr["active"]):
        text = f'<span class="tt-thin">{E(tr["text"])}</span>'
        return text, text
    if tr["thin"]:
        svg = spark_svg(tr["ma"], 120, 32, dashed=True, dot=False, baseline=True)
        svg_m = spark_svg(tr["ma"], 96, 24, dashed=True, dot=False, baseline=True)
        text = f'<span class="tt-thin">{E(tr["text"])}</span>'
        return f'{svg}{text}', f'{svg_m}{text}'
    svg = spark_svg(tr["ma"], 120, 32, dashed=False, dot=True, baseline=True)
    svg_m = spark_svg(tr["ma"], 96, 24, dashed=False, dot=True, baseline=True)
    return f'{svg}{_change_html(tr, mobile=False)}', f'{svg_m}{_change_html(tr, mobile=True)}'


def block(themes: list, snap: dict, *, score_badge, as_of: date | None = None,
          log_path: Path | None = None, ok: bool | None = None, pre: str = "",
          source_html: str = "", score_info_html: str = "") -> str:
    as_of = as_of or as_of_from(snap)
    ok = temamatch_ok() if ok is None else bool(ok)
    shares = daily_shares(load_rows(log_path))
    active = is_active(as_of, ok)
    items = [(t, compute(t["key"], shares, as_of, ok)) for t in themes]
    items = _sort_themes(items) if active else items
    stripe = stripe_html(items, pre) if active else ""
    th_tr = (f'<th class="tt-tr-h sortable" scope="col" title="Sorter etter endring i andel">{E(COL)}</th>'
             if active else f'<th class="tt-tr-h" scope="col">{E(COL)}</th>')
    rows = []
    for i, (t, tr) in enumerate(items, 1):
        desk, mob = cell_and_mobile(tr)
        href = f'{pre}tema/{t["key"]}.html'
        nlab = _n_label(_n_tickers(t))
        chg_attr = "" if tr["sort"] is None else f'{tr["sort"]:.8f}'
        rows.append(
            f'<tr class="tt-row" data-tt-thin="{"1" if tr["thin"] or not active else "0"}" '
            f'data-tt-chg="{E(chg_attr)}" data-href="{E(href)}">'
            f'<td class="tt-ix">{i}</td>'
            f'<td class="tt-tema"><a class="tt-hit" href="{E(href)}">'
            f'<span class="tt-l1"><span class="tt-name">{E(t["name"])}</span>'
            f'<span class="tt-n">{E(nlab)}</span></span>'
            f'<span class="tt-l2">{mob}</span></a></td>'
            f'<td class="tt-score">{score_badge(t["score"], muted=True)}</td>'
            f'<td class="tt-h3">{t.get("headline_count_3d") or "–"}</td>'
            f'<td class="tt-tr">{desk}</td></tr>')
    js = JS if active else ""
    return (
        f'{stripe}<div class="card tw tt-card"><h2 style="margin-top:0">Temascore{source_html}</h2>'
        f'<table id="tt-tab"><thead><tr><th>#</th><th>Tema</th>'
        f'<th>Score {score_info_html}</th><th>Overskrifter 3d</th>{th_tr}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
        f'<p class="tt-note">{E(NOTE)}</p></div>{js}'
    )


def theme_chart(t: dict, snap: dict, *, as_of: date | None = None,
                log_path: Path | None = None, ok: bool | None = None) -> str:
    """Stor linje på temasiden. Skjult til både dato ≥ 02.12 og temamatch_ok."""
    as_of = as_of or as_of_from(snap)
    ok = temamatch_ok() if ok is None else bool(ok)
    if not is_active(as_of, ok):
        return ""
    shares = daily_shares(load_rows(log_path))
    tr = compute(t["key"], shares, as_of, ok)
    days = _window(as_of, 28)
    vals, labels = tr["ma"], days
    w, h_plot, h_lab = 800, 224, 16
    pts = [(i, v) for i, v in enumerate(vals) if v is not None]
    marks = []
    if pts:
        lo, hi = min(v for _, v in pts), max(v for _, v in pts)
        rng = (hi - lo) or 1.0
        n = max(len(vals) - 1, 1)
        def xy(i, v):
            return i * (w - 2) / n + 1, h_plot - 1 - (v - lo) / rng * (h_plot - 2)
        segs, cur = [], []
        for i, v in enumerate(vals):
            if v is None:
                if cur:
                    segs.append(cur); cur = []
            else:
                cur.append((i, v))
        if cur:
            segs.append(cur)
        path = []
        y0 = xy(pts[0][0], pts[0][1])[1]
        path.append(f'<line x1="1" y1="{y0:.2f}" x2="{w-1}" y2="{y0:.2f}" stroke="{MUT}" '
                    f'stroke-width="1" stroke-dasharray="2 2"/>')
        dash = ' stroke-dasharray="4 4"' if tr["thin"] else ""
        for seg in segs:
            if len(seg) < 2:
                x, y = xy(seg[0][0], seg[0][1])
                path.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="{NEUTRAL}"/>')
                continue
            points = " ".join(f"{xy(i,v)[0]:.2f},{xy(i,v)[1]:.2f}" for i, v in seg)
            path.append(f'<polyline fill="none" stroke="{NEUTRAL}" stroke-width="1.5"{dash} points="{points}"/>')
        x, y = xy(pts[-1][0], pts[-1][1])
        path.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.5" fill="{NEUTRAL}"/>')
        # manglende dager: kort strek nederst, ikke fylt verdi
        for i, d in enumerate(labels):
            if d in tr["missing"]:
                x0 = i * (w - 2) / n + 1
                path.append(f'<line class="tt-miss" x1="{x0:.2f}" y1="{h_plot-6}" x2="{x0:.2f}" y2="{h_plot}" '
                            f'stroke="{MUT}" stroke-width="1"/>')
        # 12 px treffflate
        hits = []
        for i, v in pts:
            x, y = xy(i, v)
            tip = f'{labels[i].strftime("%d.%m")}: {_fmt_pct(v, 1)} omtale (7d snitt)'
            hits.append(f'<button type="button" class="tt-hitbox" style="left:{x/w*100:.3f}%" '
                        f'data-tip="{E(tip)}" aria-label="{E(tip)}"></button>')
        marks = path
        hit_html = "".join(hits)
    else:
        marks, hit_html = [], ""
    # etikettrad 16 px: første og siste dato med logg
    first = next((d for d in labels if d not in tr["missing"]), labels[0])
    last = next((d for d in reversed(labels) if d not in tr["missing"]), labels[-1])
    lab = (f'<span class="tt-ch-d" style="left:0">{E(first.strftime("%d.%m"))}</span>'
           f'<span class="tt-ch-d tt-ch-dr">{E(last.strftime("%d.%m"))}</span>')
    return (
        f'<div class="card tt-ch-card"><h2 style="margin-top:0">Omtale, 7d glidende snitt</h2>'
        f'<p class="mut" style="margin:0 0 8px">Andel av dagens overskrifter. {E(NOTE)}</p>'
        f'<div class="tt-ch"><div class="tt-ch-lab">{lab}</div>'
        f'<div class="tt-ch-plot"><svg viewBox="0 0 {w} {h_plot}" preserveAspectRatio="none" '
        f'width="100%" height="100%" aria-hidden="true">{"".join(marks)}</svg>'
        f'{hit_html}<div class="tt-tip" hidden></div></div></div></div>'
        f'{CHART_JS}'
    )


# --- CSS: ingen --up/--down/grønn/rød i trend ---------------------------------
CSS = f"""
.tt-card table{{width:100%}}
.tt-tr-h,.tt-tr{{width:200px;min-width:200px;max-width:200px;box-sizing:border-box;vertical-align:middle}}
.tt-tr{{font-size:13px;line-height:18px;color:{INK};white-space:nowrap}}
.tt-thin{{display:inline-block;font-size:13px;line-height:18px;color:{MUT};white-space:nowrap}}
.tt-chg{{font-size:13px;line-height:18px;color:{INK};font-weight:400}}
.tt-per{{font-size:12px;line-height:16px;color:{MUT};margin-left:0}}
.tt-lab{{font-size:13px;line-height:18px;color:{INK}}}
.tt-arr{{color:{INK};font-size:13px;line-height:18px}}
.tt-spark{{display:inline-block;vertical-align:middle;margin-right:6px}}
.tt-n,.tt-l2{{display:none}}
.tt-hit{{color:inherit;text-decoration:none}}
.tt-hit .tt-name{{color:var(--acc)}}
.tt-note{{margin:8px 0 0;font-size:12px;line-height:16px;color:{MUT}}}
.tt-stripe{{display:flex;gap:24px;margin:0 0 14px;flex-wrap:wrap}}
.tt-sg{{display:flex;flex-direction:column;gap:4px;min-width:0}}
.tt-sg-h{{font-size:13px;line-height:18px;color:{INK};font-weight:600}}
.tt-si{{display:block;font-size:13px;line-height:18px;color:{INK};text-decoration:none;min-height:24px}}
.tt-si .tt-per{{margin-left:6px}}
.tt-ch{{height:240px}}
.tt-ch-lab{{position:relative;height:16px;font-size:12px;line-height:16px;color:{MUT}}}
.tt-ch-d{{position:absolute;top:0}}
.tt-ch-dr{{right:0;left:auto}}
.tt-ch-plot{{position:relative;height:224px}}
.tt-hitbox{{position:absolute;top:0;bottom:0;width:12px;margin-left:-6px;padding:0;border:0;background:transparent;cursor:pointer}}
.tt-tip{{position:absolute;z-index:6;max-width:240px;box-sizing:border-box;font-size:13px;line-height:18px;color:#cbd5e1;background:#161b22;border:1px solid #30363d;border-radius:6px;padding:6px 8px;white-space:pre-line;overflow-wrap:anywhere}}
th.tt-tr-h.sortable{{cursor:pointer;user-select:none}}
th.tt-tr-h.sortable[aria-sort]::after{{font-size:12px;color:{MUT}}}
th.tt-tr-h.sortable[aria-sort=ascending]::after{{content:" ▲"}}
th.tt-tr-h.sortable[aria-sort=descending]::after{{content:" ▼"}}
@media(max-width:599px){{
  .tt-stripe{{display:none!important}}
  .tt-card.tw{{overflow:visible}}
  .tt-card table,.tt-card thead,.tt-card tbody{{display:block;width:100%;max-width:100%}}
  .tt-card thead{{display:none}}
  .tt-card tr.tt-row{{display:block;max-height:96px;min-height:44px;box-sizing:border-box;padding:6px 0;border-bottom:1px solid var(--line);width:100%;max-width:100%}}
  .tt-card td.tt-ix,.tt-card td.tt-score,.tt-card td.tt-h3,.tt-card td.tt-tr{{display:none}}
  .tt-card td.tt-tema{{display:block;padding:0;border:0;width:100%;max-width:100%}}
  .tt-n,.tt-l2{{display:flex}}
  a.tt-hit{{display:flex;flex-direction:column;gap:2px;min-height:44px;min-width:0;max-width:100%;color:{INK};text-decoration:none;box-sizing:border-box}}
  a.tt-hit:focus-visible{{outline:2px solid {NEUTRAL};outline-offset:-2px}}
  .tt-l1{{display:flex;align-items:baseline;gap:6px;min-width:0;max-width:100%}}
  .tt-name{{flex:1 1 auto;min-width:0;font-size:15px!important;line-height:20px!important;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:{INK}!important}}
  .tt-n{{flex:0 0 auto;font-size:12px!important;line-height:16px!important;color:{MUT};white-space:nowrap}}
  .tt-l2{{display:flex;align-items:center;gap:8px;min-width:0;max-width:100%;font-size:13px;line-height:18px;overflow:hidden}}
  .tt-l2 .tt-thin{{white-space:nowrap}}
  .tt-l2 .tt-spark{{flex:none}}
  .tt-ch{{height:180px}}
  .tt-ch-plot{{height:164px}}
}}
"""

JS = """
<script>
(function(){
  var th=document.querySelector('#tt-tab th.tt-tr-h.sortable');
  if(!th) return;
  var tb=th.closest('table').tBodies[0];
  function place(dir){
    var rows=[].slice.call(tb.querySelectorAll('tr.tt-row'));
    var thin=rows.filter(function(r){return r.getAttribute('data-tt-thin')==='1';});
    var rest=rows.filter(function(r){return r.getAttribute('data-tt-thin')!=='1';});
    rest.sort(function(a,b){
      return (parseFloat(b.getAttribute('data-tt-chg')||'0')-parseFloat(a.getAttribute('data-tt-chg')||'0'))*dir;
    });
    rest.concat(thin).forEach(function(r){tb.appendChild(r);});
    th.setAttribute('aria-sort', dir>0?'descending':'ascending');
  }
  th.setAttribute('role','button'); th.tabIndex=0;
  th.setAttribute('aria-sort','descending');
  function tog(){place(th.getAttribute('aria-sort')==='descending'?-1:1);}
  th.addEventListener('click',tog);
  th.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();tog();}});
})();
</script>
"""

CHART_JS = """
<script>
(function(){
  var p=document.currentScript && document.currentScript.previousElementSibling;
  if(!p) p=document.querySelector('.tt-ch-card:last-of-type');
  if(!p) return;
  var plot=p.querySelector('.tt-ch-plot'), tip=p.querySelector('.tt-tip');
  if(!plot||!tip) return;
  function hide(){tip.hidden=true;}
  plot.querySelectorAll('.tt-hitbox').forEach(function(b){
    function show(){
      tip.hidden=false; tip.textContent=b.getAttribute('data-tip')||'';
      var W=plot.getBoundingClientRect().width, a=b.getBoundingClientRect(), P=plot.getBoundingClientRect();
      tip.style.maxWidth=Math.min(240,W)+'px';
      tip.style.left='0px'; tip.style.right='auto';
      var tw=Math.min(tip.getBoundingClientRect().width||240,W), x0=a.left-P.left+a.width/2;
      if(x0+tw>W) tip.style.left=Math.max(0,x0-tw)+'px'; else tip.style.left=Math.max(0,x0)+'px';
      tip.style.top='16px';
    }
    b.addEventListener('mouseenter',show); b.addEventListener('focus',show);
    b.addEventListener('mouseleave',hide); b.addEventListener('blur',hide);
  });
})();
</script>
"""
