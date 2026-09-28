"""Site sections for data quality («Datakvalitet»), the random-data control («Kontroll mot overtilpasning») and the
robustness helpers (a failing section shows «ikke oppdatert (siste: dato)» instead of breaking the build)."""
from __future__ import annotations
import html, json, logging
from .config import DATA

log = logging.getLogger(__name__)
E = lambda x: html.escape("" if x is None else str(x))
SECTION_OK = DATA / "section_last_ok.json"
FAILED_SECTIONS: list[str] = []


def _pp(x, d=1):
    if x is None:
        return "–"
    return (f"{0:.{d}f} %" if abs(x * 100) < 0.5 * 10 ** -d else f"{x*100:+.{d}f} %").replace(".", ",")


def _p(x):
    return "–" if x is None else (f"{x:.3f}".replace(".", ","))


# ---------------------------------------------------------------- robustness
def _last_ok() -> dict:
    try:
        return json.loads(SECTION_OK.read_text())
    except (OSError, ValueError):
        return {}


def _save_ok(name: str, day: str) -> None:
    try:
        d = _last_ok()
        if d.get(name) != day:
            d[name] = day
            SECTION_OK.parent.mkdir(parents=True, exist_ok=True)
            SECTION_OK.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True))
    except OSError:
        pass


def stale_card(name: str, last: str | None) -> str:
    return (f'<div class="card stale"><b>{E(name)}</b>: <span class="fail">ikke oppdatert</span> '
            f'<span class="mut">(siste: {E(last or "ukjent")}) – seksjonen feilet ved siste bygging og vises ikke i dag.</span></div>')


def section(name: str, fn, *args, snap: dict | None = None, **kw) -> str:
    """Render one section; an exception is logged as a warning and replaced by an «ikke oppdatert (siste: dato)» card."""
    day = (snap or {}).get("date") or ""
    try:
        out = fn(*args, **kw)
        _save_ok(name, day)
        return out or ""
    except Exception as ex:
        log.warning("site section %s failed: %s", name, ex, exc_info=True)
        FAILED_SECTIONS.append(name)
        return stale_card(name, _last_ok().get(name))


def source_note(snap: dict, *labels: str) -> str:
    """Warning line for failed sources feeding a section («ikke oppdatert (siste: dato)» from the pipeline status)."""
    st = snap.get("status") or {}
    last = snap.get("source_last_ok") or {}
    bad = [(k, last.get(k)) for k in labels if "FAIL" in str(st.get(k, ""))]
    if not bad:
        return ""
    return '<p class="warnbox">' + " · ".join(f"{E(k)}: ikke oppdatert (siste: {E(d or 'ukjent')})" for k, d in bad) + "</p>"


# ---------------------------------------------------------------- data quality
def dq_line(snap: dict, pre: str = "") -> str:
    dq = snap.get("data_quality")
    if not dq:
        return ""
    return (f'<p class="mut"><b>Datakvalitet i dag:</b> {dq.get("n_spikes", 0)} kurshopp reparert '
            f'({dq.get("n_spikes_12m", 0)} siste 12 mnd), {dq.get("n_stale", 0)} tickere med uendret kurs ≥ {dq["rules"]["stale_n"]} dager. '
            f'<a href="{pre}kilder.html#datakvalitet">Detaljer</a> · <a href="{pre}kilder.html#kontroll">Kontroll mot overtilpasning</a></p>')


def dq_html(snap: dict) -> str:
    dq = snap.get("data_quality")
    head = '<div class="card" id="datakvalitet"><h2 style="margin-top:0">Datakvalitet (kursdata)</h2>'
    if not dq:
        return head + '<p class="mut">Ikke beregnet i denne kjøringen (eldre øyeblikksbilde) – ikke oppdatert.</p></div>'
    r = dq["rules"]
    rows = "".join(f'<tr><td>{E(k)}</td><td>{v["n_tickers"]}</td><td>{v["n_spikes"]}</td><td>{v.get("n_spikes_12m", 0)}</td><td>{v["n_stale"]}</td></tr>'
                   for k, v in dq.get("sources", {}).items())
    sp = ", ".join(E(x) for x in sorted({f"{t} {d}" for v in dq.get("sources", {}).values() for t, d in v.get("spikes", [])},
                                         key=lambda s: s.split()[-1], reverse=True)[:12])
    st = sorted({(t, a, b, n) for v in dq.get("sources", {}).values() for t, a, b, n in v.get("stale", [])}, key=lambda x: x[2], reverse=True)
    stl = ", ".join(f"{E(t)} ({n} dager, {E(a)}–{E(b)})" for t, a, b, n in st[:15])
    return (head + f'<p>Før signaler, flagg og treffrater beregnes, sjekkes alle kursserier automatisk (oppdateres ved hver kjøring, siste {E(dq.get("asof"))}):</p><ul class="ev">'
            f'<li><b>Kurshopp som reverserer</b> (feilkurs): endring over {r["spike"]*100:.0f} % på én dag og tilbake innen {r["revert"]*100:.0f} % dagen etter. '
            'Den feilaktige sluttkursen fjernes og erstattes med forrige kurs før beregning. Et hopp på aller siste dag kan ikke oppdages ennå.</li>'
            f'<li><b>Uendret kurs</b> {r["stale_n"]} dager eller mer på rad selv om det er omsetning (kursen er trolig ikke oppdatert). '
            'Disse tickerne flagges her; kursene endres ikke.</li></ul>'
            f'<div class="tw"><table><tr><th>Datasett</th><th>Tickere</th><th>Reparerte kurshopp (hele historikken)</th><th>… siste 12 mnd</th><th>Tickere med uendret kurs</th></tr>{rows}</table></div>'
            + (f'<p class="mut"><b>Siste reparerte kurshopp:</b> {sp}</p>' if sp else "")
            + (f'<p class="mut"><b>Uendret kurs (siste år):</b> {stl}</p>' if stl else "")
            + '<p class="mut">Kode: signaltool/data_quality.py.</p></div>')


# ---------------------------------------------------------------- random-data control
ORDER = ["pead", "pead_s", "pead_s_vol", "weak_px"]


def _verdict(k: str, m: dict) -> str:
    p = m.get("p")
    if p is None:
        return "–"
    if k == "weak_px":
        return "klart svakere enn tilfeldig" if p <= 0.01 else "svakere enn tilfeldig, men usikkert" if p <= 0.1 else "ikke skilt fra tilfeldig"
    if k == "pead_s" and p <= 0.05:
        return "bedre enn tilfeldige rapporter – men se neste rad"
    return "klart bedre enn tilfeldig" if p <= 0.01 else "noe bedre enn tilfeldig" if p <= 0.05 else "ikke skilt fra tilfeldig"


def kontroll_html(snap: dict) -> str:
    from . import null_control as N
    K = N.load()
    head = '<div class="card" id="kontroll"><h2 style="margin-top:0">Kontroll mot overtilpasning (tilfeldige data)</h2>'
    rows = ""
    for k in ORDER:
        v = K.get(k)
        if not v:
            continue
        m, h = v["mean"], v["hit"]
        rows += (f'<tr><td>{E(v["label"])}<div class="mut">{E(v.get("period"))} · null: {E(v.get("null"))}</div></td><td>{f"{v['n']:,}".replace(",", " ")}</td><td>{_pp(m.get("real"))}</td>'
                 f'<td>{_pp(m.get("null_mean"))} <div class="mut">{_pp(m.get("null_p05"))} til {_pp(m.get("null_p95"))}</div></td>'
                 f'<td>{m.get("percentile", 0):.0f}</td><td>{_p(m.get("p"))}</td><td>{(h.get("real") or 0)*100:.0f} % mot {(h.get("null_mean") or 0)*100:.0f} %</td>'
                 f'<td>{E(_verdict(k, m))}</td></tr>')
    if not rows:
        body = '<p class="mut">Ikke beregnet ennå (kjør python -m signaltool backtest kontroll).</p>'
    else:
        meta = K.get("_meta", {})
        body = (f'<p>Et signal er bare interessant hvis det gjør det bedre (eller for røde flagg: dårligere) enn <b>like mange tilfeldige kjøp fra samme univers</b>. '
                f'Vi trekker {meta.get("n_draws")} tilfeldige utvalg (fast frø {meta.get("seed")}) og ser hvor det faktiske resultatet havner. '
                '<b>Persentil</b> = andel tilfeldige utvalg med lavere snitt. <b>p</b> = andel tilfeldige utvalg som var minst like gode (røde flagg: minst like dårlige); '
                f'laveste mulige p med {meta.get("n_draws")} trekk er ca. {_p(1/((meta.get("n_draws") or 500)+1))}.</p>'
                + '<div class="tw"><table><tr><th>Signal</th><th>Tilfeller</th><th>Faktisk snitt 60 d</th><th>Tilfeldig snitt (90 %)</th><th>Persentil</th><th>p</th>'
                '<th>Slo indeks: faktisk / tilfeldig</th><th>Vurdering</th></tr>' + rows + '</table></div>'
                '<p class="mut"><b>Tolkning:</b> Mot tilfeldige kvartalsrapporter ser PEAD-S bra ut, men mot tilfeldige rapporter i <i>like volatile</i> aksjer '
                'forsvinner mesteparten av forspranget – mye av effekten er altså bare «volatile aksjer». Svak kurs på Oslo Børs er derimot tydelig dårligere enn '
                'tilfeldige likvide aksjer samme dag. Forbehold: tilfeldige trekk behandler overlappende 60-dagersvinduer som uavhengige, så p-verdiene er for optimistiske '
                '(HAC-t på kvartalssnitt, som vi bruker ellers, er strengere); USA-universet har overlevelsesskjevhet unntatt PEAD-radene (punkt-i-tid). '
                f'Historikken beregnes lokalt (sist {E(meta.get("computed"))}) fordi kursarkivet ikke finnes i den nattlige kjøringen; kode: signaltool/null_control.py.</p>')
    fw = ((snap.get("track_record") or {}).get("null") or {})
    cats = fw.get("cats") or {}
    lab = {"kjop": "Kjøp-kandidat", "hold": "Hold", "watch": "Watchlist"}
    if cats:
        items = []
        for c, r in cats.items():
            if r.get("real") is not None:
                items.append(f'{lab.get(c, c)}: {_pp(r["real"])} mot tilfeldig {_pp(r.get("null_mean"))} (persentil {r["percentile"]:.0f}, p {_p(r["p"])}, n={r["n"]})')
            else:
                items.append(f'{lab.get(c, c)}: {r.get("n", 0)} modne tilfeller – for få (trenger {fw.get("min_n")})')
        body += (f'<h3>Fremoverloggen (ekte, daglig oppdatert)</h3><p class="mut">Hver ny plassering sammenlignes med en tilfeldig ticker som verktøyet så på '
                 f'samme dag i samme marked ({fw.get("h")} handelsdager, mot indeks). ' + "; ".join(items) + '.</p>')
    else:
        body += ('<h3>Fremoverloggen (ekte, daglig oppdatert)</h3><p class="mut">Ingen modne plasseringer ennå – sammenligningen med tilfeldige tickere samme dag '
                 'vises når hver kategori har nok tilfeller som har nådd 20 handelsdager.</p>')
    return head + body + "</div>"
