"""Kursgraf på tickersiden: daglige sluttkurser (Yahoo, ekte historikk) + stiplet 50-dagers snitt, grått innkurspunkt for
gjeldende listeperiode (entry_point), grå Inn/Ut-markører og bånd for listeperiodene. Ingen prognoser eller trendlinjer; hull i dataene blir hull i linja. Én farge (#58a6ff)."""
from __future__ import annotations
import json, math
from datetime import date
from html import escape as E

PERIODS = [("1M", 22), ("6M", 126), ("1Å", 252), ("5Å", 1260)]
DEFAULT = "6M"
COL = "#58a6ff"
_CACHE: dict = {}


def download(tickers: list[str]) -> dict:
    """{ticker: [(YYYY-MM-DD, close|None), ...]} for 5 år, ett samlet Yahoo-kall. Feil: tomt (grafen utelates)."""
    if "v" in _CACHE:
        return _CACHE["v"]
    out = {}
    try:
        import yfinance as yf
        d = yf.download(sorted(set(tickers)), period="5y", auto_adjust=False, progress=False, group_by="column")["Close"]
        if hasattr(d, "to_frame") and not hasattr(d, "columns"):
            d = d.to_frame(tickers[0])
        d = d.dropna(how="all")
        for t in d.columns:
            ser = d[t]
            first = ser.first_valid_index()
            if first is None:
                continue
            ser = ser.loc[first:]
            out[str(t)] = [(str(k.date()), None if v != v else round(float(v), 4)) for k, v in ser.items()]
    except Exception:
        out = {}
    _CACHE["v"] = out
    _CACHE["date"] = date.today().isoformat()
    return out


def _sma(vals, n=50):
    """50-dagers snitt over de siste 50 handelsdagene MED kurs (manglende dager hoppes over, ikke fylt inn)."""
    out, win = [], []
    for v in vals:
        if v is None:
            out.append(None)
            continue
        win.append(v)
        if len(win) > n:
            win.pop(0)
        out.append(sum(win) / n if len(win) == n else None)
    return out


def _path(xs, ys, fx, fy):
    d, pen = [], False
    for x, y in zip(xs, ys):
        if y is None:
            pen = False
            continue
        d.append(f'{"L" if pen else "M"}{fx(x):.1f},{fy(y):.1f}')
        pen = True
    return "".join(d)


def svg(series, n, mark_date=None, W=600, H=240, bands=None):
    full = series
    sm = _sma([v for _, v in full])
    s, m = full[-n:], sm[-n:]
    vals = [v for _, v in s if v is not None] + [v for v in m if v is not None]
    if len([v for _, v in s if v is not None]) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1
    pad, L = 6, len(s)
    fx = lambda i: pad + i * (W - 2 * pad) / max(1, L - 1)
    fy = lambda v: pad + (hi - v) * (H - 2 * pad) / (hi - lo)
    xs = range(L)
    p1 = _path(xs, [v for _, v in s], fx, fy)
    p2 = _path(xs, m, fx, fy)
    mk, ov = "", ""
    if mark_date and bands:   # AnalBot 11.11: grått innkurspunkt uten tekst, bare for gjeldende periode (velges i entry_point)
        for i, (dd, v) in enumerate(s):
            if dd == mark_date and v is not None:
                ov = f'<span class="pcdot" aria-hidden="true" style="left:{fx(i) / W * 100:.2f}%;top:{fy(v) / H * 100:.2f}%"></span>'
    bd, gp, ov2 = _bands(s, bands, fx, W, H)
    ov += ov2
    fmt = lambda v: f"{v:,.2f}".replace(",", " ").replace(".", ",")
    okv = [v for _, v in s if v is not None]
    lab = f'<span class="hi">{fmt(max(okv))}</span><span class="lo">{fmt(min(okv))}</span>{ov}'
    return (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" aria-label="Sluttkurs siste {n} handelsdager">'
            f'{bd}{gp}'
            f'<path d="{p2}" fill="none" stroke="{COL}" stroke-width="1.2" stroke-dasharray="4 3" opacity=".7" vector-effect="non-scaling-stroke"/>'
            f'<path d="{p1}" fill="none" stroke="{COL}" stroke-width="1.8" vector-effect="non-scaling-stroke"/>{mk}</svg>'
            f'<div class="pcl">{lab}</div>')


def _idx_ge(s, d):
    return next((i for i, (dd, _) in enumerate(s) if dd >= d), None)


def _pct(x, W):
    return f"{x / W * 100:.2f}"


def events(s, bands) -> list[tuple]:
    """(type, dato, periode) for Inn/Ut innenfor vinduet s. «på lista fra før» (loggstart) er ingen Inn-hendelse."""
    if not s:
        return []
    lo, hi = s[0][0], s[-1][0]
    out = []
    for b in bands or ():
        if not b.get("first") and lo <= b["inn"] <= hi:
            out.append(("Inn", b["inn"], b))
        if b.get("ut") and lo <= b["ut"] <= hi:
            out.append(("Ut", b["ut"], b))
    return sorted(out, key=lambda e: e[1])


def _bands(s, bands, fx, W, H):
    """UxBot/AnalBot 11.11: grått bånd per periode (gjennom datahull), grå strek + «Inn»/«Ut» med dato under for hver hendelse
    i vinduet, stiplet 1 px grå kant over båndet på hulldagene. Verktøytips på hover og fokus (tabindex)."""
    bd, gp, ov = "", "", ""
    for b in bands or ():
        ix = [i for i, (dd, _) in enumerate(s) if dd >= b["inn"] and (b["ut"] is None or dd < b["ut"])]
        tip = E(b.get("tip") or b.get("title") or "")
        if ix:
            x0, x1 = fx(ix[0]), fx(ix[-1])
            if x1 - x0 < 2:
                x0, x1 = x0 - 1, x1 + 1
            bd += f'<rect class="pcband" x="{x0:.1f}" y="0" width="{x1 - x0:.1f}" height="{H}" fill="#8b949e" fill-opacity=".14"/>'
            ov += (f'<span class="pcbd" tabindex="0" aria-label="{tip}" style="left:{_pct(x0, W)}%;width:{_pct(x1 - x0, W)}%">'
                   f'<span class="tip">{tip}</span></span>')
        for g0, g1 in b.get("gap_ranges") or ():
            gi = [i for i, (dd, _) in enumerate(s) if g0 <= dd <= g1]
            if gi:
                x0, x1 = fx(gi[0]) - 2, fx(gi[-1]) + 2
            else:   # hull bare på dager uten handel: kort stykke ved overgangen
                j = _idx_ge(s, g0)
                if j is None or j == 0 or not (s[0][0] <= g0 <= s[-1][0]):
                    continue
                xm = (fx(j - 1) + fx(j)) / 2
                x0, x1 = xm - 3, xm + 3
            gp += (f'<line class="pcgap" x1="{x0:.1f}" x2="{x1:.1f}" y1="0.5" y2="0.5" stroke="#8b949e" stroke-width="1" '
                   f'stroke-dasharray="3 2" vector-effect="non-scaling-stroke"/>')
    for kind, d, b in events(s, bands):
        j = _idx_ge(s, d)
        if j is None:
            continue
        x = fx(j)
        tip = E(b.get("tip") or b.get("title") or "")
        ov += (f'<span class="pcmk{" r" if x / W > .85 else ""}" data-k="{kind}" tabindex="0" aria-label="{E(kind)} {d[8:10]}.{d[5:7]}. {tip}" '
               f'style="left:{_pct(x, W)}%"><span class="pcml">{kind} {d[8:10]}.{d[5:7]}</span><span class="tip">{tip}</span></span>')
    return bd, gp, ov


def entry_point(series, periods, entry_date=None):
    """AnalBot 11.11: innkurspunktet = innkursens price_date i GJELDENDE listeperiode (samme som avkastningen i Siden-raden,
    since.from_period). Ikke på lista nå / ingen perioder / price_date uten sluttkurs i serien: None (ingen punkt, aldri flyttet)."""
    if not periods or periods[-1].get("ut") is not None or not series or not entry_date:
        return None
    d = str(entry_date)[:10]
    return d if d in {x for x, v in series if v is not None} else None


def html(ticker: str, series, mark_date=None, upd: str | None = None, periods=None) -> str:
    if not series:
        return ""
    mark_date = entry_point(series, periods, mark_date)
    panes, btns = [], []
    for lab, n in PERIODS:
        g = svg(series, n, mark_date, bands=periods)
        if not g:
            continue
        on = lab == DEFAULT
        btns.append(f'<button type="button" class="pcb" aria-pressed="{"true" if on else "false"}" data-p="{lab}">{lab}</button>')
        panes.append(f'<div class="pcp" data-p="{lab}"{"" if on else " hidden"}>{g}</div>')
    if not panes:
        return ""
    if not any(b for b in btns if 'aria-pressed="true"' in b):
        btns[-1] = btns[-1].replace('aria-pressed="false"', 'aria-pressed="true"'); panes[-1] = panes[-1].replace(" hidden", "")
    u = f" · {upd[8:10]}.{upd[5:7]}" if upd else ""
    full = f"Kilde: Yahoo Finance, daglige sluttkurser{' · oppdatert ' + upd[8:10] + '.' + upd[5:7] if upd else ''}"
    return (f'<div class="card pc nofold" id="kursgraf"><div class="pch"><h2 class="pct">Kurs</h2><div class="pcbs" role="group" aria-label="Periode">{"".join(btns)}</div></div>{"".join(panes)}'
            f'{_periods_html(periods)}<p class="mut pcs">Yahoo{u} <span class="ri" tabindex="0" aria-expanded="false" aria-label="{full}">ⓘ<span class="tip">{full}</span></span></p>'
            '<script>(()=>{const c=document.getElementById("kursgraf");c.querySelectorAll(".pcb").forEach(b=>b.addEventListener("click",()=>{'
            'c.querySelectorAll(".pcb").forEach(x=>x.setAttribute("aria-pressed",x===b?"true":"false"));'
            'c.querySelectorAll(".pcp").forEach(p=>p.hidden=p.dataset.p!==b.dataset.p);lab()}));'
            # UxBot 11.11: etikettrad 16 px øverst; fra nyeste til eldste, vis bare med ≥ 28 px til forrige viste og uten overlapp
            + LAY_JS + MEASURE_JS + TIP_JS +
            'function lab(){c.querySelectorAll(".pcp:not([hidden])").forEach(p=>{const W=p.getBoundingClientRect().width||c.clientWidth,'
            'k=[...p.querySelectorAll(".pcmk")],ls=k.map(x=>x.querySelector(".pcml"));ls.forEach(l=>{if(l)l.hidden=false});'
            'const o=pcLay(k.map((x,i)=>({x:parseFloat(x.style.left)*W/100,w:pcW(ls[i])})),W);'
            'k.forEach((x,i)=>{if(ls[i])ls[i].hidden=!o[i].show;x.classList.toggle("r",!!o[i].rt)})})}'
            'c.querySelectorAll(".pcmk,.pcbd").forEach(x=>{x.addEventListener("pointerenter",pcTip);x.addEventListener("focus",pcTip)});'
            'lab();addEventListener("resize",lab,{passive:true})})()</script></div>')



# Etikettoppsett (samme funksjon brukes i testen via node): ms = [{x, w}] i px fra venstre, W = grafbredde, w = MÅLT
# etikettbredde (nettleseren: getBoundingClientRect, ellers canvas measureText; node-testen: 6,6 px/tegn + 20 %).
# Nyeste (størst x) først; etiketten står til høyre for streken (3 px), eller til venstre når den ellers går utenfor grafen.
# UxBot 11.11: vises bare når avstanden til forrige viste markør er ≥ 28 px OG det er ≥ 28 px luft mellom etikettboksene.
LAY_GAP = 28
LAY_JS = ('function pcLay(ms,W){const G=28,o=ms.map(()=>({show:false})),ix=ms.map((m,i)=>i).sort((a,b)=>ms[b].x-ms[a].x);let px=null;const bx=[];'
          'for(const i of ix){const m=ms[i];let l=m.x+3,r=l+m.w,rt=false;if(r>W){r=m.x-3;l=r-m.w;rt=true}if(l<0){l=0;r=m.w}'
          'const ok=(px===null||px-m.x>=G)&&bx.every(b=>r+G<=b[0]||l>=b[1]+G);o[i]={show:ok,l:l,r:r,rt:rt};if(ok){px=m.x;bx.push([l,r])}}return o}')
# Målt bredde: synlig etikett -> getBoundingClientRect; ellers (0 px, f.eks. skjult rute) canvas measureText med etikettens font.
MEASURE_JS = ('function pcW(l){if(!l)return 0;const r=l.getBoundingClientRect().width;if(r>0)return r;const cs=getComputedStyle(l),'
              'cv=pcW.c||(pcW.c=document.createElement("canvas")).getContext("2d");cv.font=cs.font||"11px sans-serif";return cv.measureText(l.textContent).width}')
# UxBot 11.11: verktøytips maks 240 px med bryting; går det forbi grafens høyrekant legges det til venstre for markøren;
# alltid klemt innenfor grafboksen [0, W].
TIP_JS = ('function pcTip(e){const el=e.currentTarget,t=el.querySelector(".tip"),p=el.closest(".pcp");if(!t||!p)return;'
          'const W=p.getBoundingClientRect().width,a=el.getBoundingClientRect(),P=p.getBoundingClientRect();t.style.maxWidth=Math.min(240,W)+"px";'
          't.style.left="0px";t.style.right="auto";const tw=Math.min(t.getBoundingClientRect().width||240,W),x0=a.left-P.left,'
          'cx=el.classList.contains("pcmk")?x0+a.width/2:x0;let L=cx;if(L+tw>W)L=cx-tw;L=Math.max(0,Math.min(L,W-tw));t.style.left=(L-x0)+"px"}')
LABEL_ROW = 16


def _periods_html(periods) -> str:
    from .ov_changes import periods_html
    return periods_html(periods or [])


CSS = """.pc{padding-top:8px;padding-bottom:8px}.pcbs{display:flex;gap:6px;margin-bottom:6px}.pcb{height:32px;min-width:44px;padding:0 10px;border:1px solid #30363d;border-radius:6px;background:none;color:inherit;font:inherit;cursor:pointer}
.pcb[aria-pressed=true]{border-color:#58a6ff;color:#58a6ff}.pcp{position:relative;padding-top:16px;overflow-x:clip}.pcl{position:absolute;left:0;right:0;top:16px;bottom:0}.pcp svg{display:block;width:100%;height:240px}.pcdot{position:absolute;z-index:3;width:6px;height:6px;margin:-3px 0 0 -3px;border-radius:50%;background:#94a3b8;box-shadow:0 0 0 1.5px #0d1117;pointer-events:none}
.pcl .hi,.pcl .lo{position:absolute;right:4px;font-size:11px;color:#8b949e;font-variant-numeric:tabular-nums}.pcl .hi{top:2px}.pcl .lo{bottom:0}
.pcs{font-size:11px;margin:4px 0 0;text-align:right}.pct{display:none}
.pcbd{position:absolute;top:0;bottom:0;z-index:1;outline-offset:-2px}.pcmk{position:absolute;top:-16px;bottom:0;z-index:4;width:12px;margin-left:-6px;outline-offset:-2px;pointer-events:auto;cursor:default}
.pcmk::before{content:"";position:absolute;left:6px;top:16px;bottom:0;border-left:1px solid #8b949e;pointer-events:none}.pcml{position:absolute;top:0;left:9px;height:16px;font-size:11px;line-height:16px;color:#94a3b8;white-space:nowrap}.pcmk.r .pcml{left:auto;right:9px;text-align:right}.pcml[hidden]{display:none}
.pcbd .tip,.pcmk .tip{display:none;position:absolute;top:32px;left:0;z-index:6;width:max-content;max-width:240px;white-space:pre-line;overflow-wrap:anywhere;box-sizing:border-box;font-size:13px;line-height:18px;color:#cbd5e1;background:#161b22;border:1px solid #30363d;border-radius:6px;padding:6px 8px}.pcmk.r .tip{left:auto;right:0}
.pcbd:hover .tip,.pcbd:focus .tip,.pcmk:hover .tip,.pcmk:focus .tip{display:block}
@media(max-width:599px){.card.pc{padding:3px 10px;margin:0 0 12px}
.pch{display:flex;align-items:center;justify-content:space-between;height:28px;margin-bottom:2px}.pct{display:block;font-size:14px;margin:0}
.pcbs{margin:0;gap:4px}.pcb{height:28px;min-width:40px;padding:0 8px;font-size:13px}.pcp svg{height:150px}.pcs{font-size:11px;margin:4px 0 0;line-height:1.2}}"""


def write_json(ticker, series, path, upd=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ticker": ticker, "source": "Yahoo Finance", "updated": upd, "close": series}, separators=(",", ":")))
