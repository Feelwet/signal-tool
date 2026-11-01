"""UxBot-runde 01.11 (bindende) for Oversikt, Makro, Temaer, Sektorer, Oslo, Tickere, Røde flagg og Signal-boka.
Bare layout: ingen tall, AnalBot-tekster, merker eller sortering endres. Usikkerhetstekster («Rangering, ikke testet», «For få handler»,
ferskhetsvarsel, «kort periode») står synlig ved tallet; bare generell veiledning flyttes inn i ⓘ (AnalBot 01.11)."""
from __future__ import annotations
from html import escape as E

MODS = ("index", "makro", "temaer", "sektorer", "oslo")
RISK_LINE = "Testet for kurssvingninger, ikke avkastning"   # AnalBot 01.11: synlig ved risikofeltet; resten av STATUS i ⓘ


def dm(d) -> str:
    """«2026-10-31» -> «31.10». Ukjent -> «–» (dikter aldri opp en dato)."""
    s = str(d or "")[:10]
    return f"{s[8:10]}.{s[5:7]}" if len(s) == 10 and s[4] == "-" else "–"


def i(tip: str, label: str = "") -> str:
    """ⓘ med 14 px ikon og 32×32 trykkflate (.sc-i, SCORE_I_JS)."""
    return (f'<button type="button" class="ri ri-c sc-i" aria-expanded="false" aria-label="{E(label or tip)}">ⓘ'
            f'<span class="tip">{E(tip)}</span></button>')


def meta(src: str, date=None) -> str:
    """Én metalinje 12 px under tittelen: «kilde t.o.m. 31.10»."""
    t = f"{src} t.o.m. {dm(date)}" if date else src
    return f'<p class="pmeta">{E(t)}</p>'


def csrc(src: str, date=None, tip: str = "") -> str:
    """Kilde + dato til høyre i korttittelen, 12 px #94a3b8, med ⓘ når det finnes en forklaring."""
    t = f"{src} · {dm(date)}" if date else src
    return f'<span class="csrc">{E(t)}{i(tip) if tip else ""}</span>'


def body_class(cur: str | None) -> str:
    stem = (cur or "").split(".")[0].split("?")[0]
    return f"pg-{stem}" if stem else "pg-other"


S = ":is(.pg-index,.pg-makro,.pg-temaer,.pg-sektorer,.pg-oslo)"
CSS = (
    # 5) sidetopp: tittel 24 px, én metalinje 12 px
    f"body{S} main h1{{font-size:24px;line-height:30px;margin:0 0 2px}}"
    ".pmeta{margin:0 0 8px;font-size:12px;line-height:16px;color:#94a3b8}"
    "h1 .sc-i{vertical-align:middle;font-weight:400}"
    # 4) ingress: én linje 14 px #cbd5e1 (resten i ⓘ ved tittelen)
    f"body{S} main .pintro{{margin:0 0 10px;font-size:14px;line-height:20px;color:#cbd5e1}}"
    # 1) korttittel 16 px semibold, lukkepil 12 px, kilde+dato til høyre
    f"body{S} main .card>h2,body{S} main .card>h3:first-child,body{S} details.fold>summary h2,body{S} details.fold>summary h3{{font-size:16px;line-height:22px;font-weight:600}}"
    f"body{S} details.fold>summary::before{{font-size:12px}}"
    "body.pg-sektorer a.scard h3{font-size:16px;line-height:22px;font-weight:600}"
    f"body{S} details.fold>summary h2{{display:flex;flex-wrap:wrap;align-items:center;column-gap:6px;row-gap:2px}}"
    f"body{S} .fold-sum{{font-size:12px;font-weight:400;color:#94a3b8}}"
    ".csrc{margin-left:auto;display:inline-flex;align-items:center;gap:2px;font-size:12px;line-height:16px;font-weight:400;color:#94a3b8;white-space:nowrap}"
    ".card>h2:has(.csrc),.ov-th>h2:has(.csrc){display:flex;align-items:center;flex-wrap:wrap;column-gap:6px}"
    # 2) nøkkeltall i rutenett: 2 kolonner på 390, 3–4 på 1280
    f"body{S} main .kpis.small,body{S} main .kpis.k3{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:0 0 12px}}"
    f"@media(min-width:700px){{body{S} main .kpis.small,body{S} main .kpis.k3{{grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}}}}"
    f"body{S} main .kpis a.kpi,body{S} main .kpis.k3 a.kpi{{background:#111821;border:0;border-radius:6px;padding:8px 10px;min-width:0;margin:0}}"
    f"body{S} main .kpis a.kpi .lbl,body{S} main .kpis.k3 a.kpi .lbl{{font-size:12px;line-height:16px;text-transform:uppercase;letter-spacing:.03em;color:#cbd5e1}}"
    f"body{S} main .kpis a.kpi .val,body{S} main .kpis.k3 a.kpi .val{{font-size:20px;line-height:24px;font-weight:600;margin:2px 0 0}}"
    f"body{S} main .kpis a.kpi .sub,body{S} main .kpis.k3 a.kpi .sub{{font-size:12px;line-height:16px;color:#cbd5e1;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}"
    # 3) filterknapper 32 px, 13 px; kompakt «Bare»
    "body.pg-makro .infl-leg{display:flex;flex-wrap:wrap;gap:3px;align-items:center;margin:0 0 6px}"
    "body.pg-makro .infl-leg .chip{margin:0;border-radius:16px}"
    "body.pg-makro .infl-leg .chip button,body.pg-makro .infl-all{height:32px;min-height:32px;min-width:0;font-size:13px;line-height:30px;padding:0 4px;white-space:nowrap}"
    "body.pg-makro .infl-leg .chip button i{width:8px;height:8px;border-radius:50%;margin-right:4px}"
    "body.pg-makro .infl-leg .chip .only{padding:0 3px;font-size:10px;letter-spacing:0}"
    "body.pg-makro .infl-all{margin:0;border-radius:16px}"
    ".tf-row button{height:32px!important;min-height:32px!important;font-size:13px!important;padding:0 10px!important}"
    ".flt button{height:32px;min-height:32px;font-size:13px;padding:0 10px}"
    # Oversikt: nøkkelfelt
    "body.pg-index .ov-strip{gap:8px}"
    "body.pg-index .ov-tile{background:#111821;border:0;border-radius:6px;padding:8px 10px}"
    "body.pg-index .ov-tile .lbl{font-size:12px;line-height:16px;text-transform:uppercase;letter-spacing:.03em;color:#cbd5e1}"
    "body.pg-index .ov-tile .lbl a{color:#cbd5e1}body.pg-index .ov-tile .stretch{font-size:12px;text-transform:none;letter-spacing:0}"
    "body.pg-index .ov-tile .big{font-size:20px;line-height:24px;font-weight:600;margin:2px 0 0}"
    "body.pg-index .ov-tile .sub,body.pg-index .ov-tile .sub2{font-size:12px;line-height:16px;color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:0}"
    "body.pg-index .ov-tile .sub a.in{padding:0}"
    "body.pg-index .ov-tile .sub2.rkl{white-space:normal;overflow:visible;display:flex;align-items:center;gap:2px}body.pg-index .ov-tile .sub2.rkl .sc-i{flex:none}"
    "body.pg-index .ov-stack{height:6px;margin:4px 0}"
    "body.pg-index .ov-th h2,body.pg-index .ov-2 h2,body.pg-index .ov-low h2{font-size:16px;line-height:22px;font-weight:600}"
    "body.pg-index .pwa-inst{margin-top:12px}"
    # Tickerlista
    "#tf-table th{font-size:12px;line-height:16px;text-transform:uppercase;letter-spacing:.03em;color:#94a3b8;background:#111821;font-weight:600}"
    "@media(min-width:600px){#tf-table table:not(.ur-tab) tr:first-child th{padding-top:12px;padding-bottom:10px;vertical-align:top}}"
    "#tf-table>p.catdisc.rk-status,p.catdisc.rk-status{margin-top:12px;font-size:12px;color:#cbd5e1}"
    ".xscroll,.card.tw{position:relative}"   # skjermleser-spenn (.sr) i rulletabeller lekket ut og gjorde siden 790 px bred på mobil (Metode)
    ".sc-i .tip.pop,.ri.ri-c .tip.pop{position:fixed;right:auto;bottom:auto;z-index:1000;box-sizing:border-box;width:max-content;max-width:calc(100vw - 16px);white-space:normal;overflow-wrap:break-word;text-align:left}"
    ".tf-wrap{position:sticky;top:0;z-index:20;background:var(--bg,#0d1117);padding:6px 0;margin:0 0 6px;display:flex;gap:8px;align-items:center}"
    ".tf-wrap .tf-q{flex:0 0 120px;width:120px;height:32px;box-sizing:border-box;padding:0 10px;border-radius:16px;border:1px solid #3b4757;background:#111821;color:inherit;font:inherit;font-size:13px}"
    ".tf-wrap .tf-row{flex:1 1 auto;min-width:0;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:thin}"
    ".tf-wrap::after{top:6px;bottom:6px}"
    "@media(max-width:599px){"
    "#tf-table .evleg{display:flex!important;flex-wrap:nowrap;overflow-x:auto;white-space:nowrap;font-size:12px;line-height:16px;margin:0 0 6px;gap:8px;scrollbar-width:none}"
    "#tf-table .card{padding:8px 12px}"
    "#tf-table table:not(.ur-tab),#tf-table table:not(.ur-tab) tbody{display:block;width:100%}"
    "#tf-table table:not(.ur-tab) tr:first-child{display:flex;justify-content:flex-end;gap:12px;border-bottom:1px solid #3b4757;background:#111821}"
    "#tf-table table:not(.ur-tab) tr:first-child th{display:none;background:none;padding:6px 4px}"
    "#tf-table table:not(.ur-tab) tr:first-child th.sortable.rk-h,#tf-table table:not(.ur-tab) tr:first-child th.ret-h{display:block;width:auto!important;min-width:0!important;max-width:none!important}"
    "#tf-table tr.rowlink{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;column-gap:6px;row-gap:2px;align-items:center;padding:7px 0;border-bottom:1px solid #3b4757}"
    "#tf-table tr.rowlink[hidden]{display:none}"
    "#tf-table tr.rowlink>td{display:block;padding:0!important;border:0!important;width:auto!important;min-width:0!important;max-width:none!important;height:auto!important;min-height:0!important;white-space:nowrap}"
    "#tf-table tr.rowlink>td:first-child,#tf-table tr.rowlink td.rk-c,#tf-table tr.rowlink .rkp-s{display:contents!important}"
    "#tf-table tr.rowlink .tn{grid-column:1/3;grid-row:1;display:flex!important;flex-direction:row;align-items:baseline;gap:6px;min-width:0;overflow:hidden}"
    "#tf-table tr.rowlink .tn .nm{flex:0 1 auto;font-size:15px;line-height:20px;font-weight:600;display:block!important;-webkit-line-clamp:unset;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:3em}"
    "#tf-table tr.rowlink .tn .tk{flex:0 1000 auto;min-width:4.6em!important;font-size:12px!important;line-height:16px!important;color:#94a3b8;flex-wrap:nowrap!important;white-space:nowrap;overflow:hidden;min-width:0}"
    "#tf-table tr.rowlink .tn .tk .fchip,#tf-table tr.rowlink .tn .tk .dchip{font-size:11px!important;white-space:nowrap}"
    "#tf-table tr.rowlink .since-m{grid-column:1/3;grid-row:2;display:block!important;font-size:12px!important;line-height:16px!important;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}"
    "#tf-table tr.rowlink .since-m *{font-size:12px!important;line-height:16px!important;display:inline!important;white-space:nowrap!important}"
    "#tf-table tr.rowlink .since-m .tip{display:none!important}#tf-table tr.rowlink .since-m .ri[aria-expanded=true] .tip{display:block!important}"
    "#tf-table tr.rowlink .since-m .inn-m::before{content:' · '}"
    "#tf-table tr.rowlink .since-m .ret-m{display:none!important}"
    "#tf-table tr.rowlink td.ret-c{grid-column:3;grid-row:1/3;display:flex!important;flex-flow:row wrap;align-items:baseline;justify-content:flex-end;column-gap:2px;text-align:right;align-self:start;max-width:150px!important;width:auto!important}"
    "#tf-table tr.rowlink td.ret-c .rex{flex-basis:100%}#tf-table tr.rowlink td.ret-c .rsh-t{display:inline!important;margin:0 0 0 2px}"
    "#tf-table tr.rowlink td.ret-c .rv{font-size:15px;line-height:20px;font-weight:600}"
    "#tf-table tr.rowlink td.ret-c .rex,#tf-table tr.rowlink td.ret-c .rsh-t{font-size:11px;line-height:14px;color:#94a3b8;white-space:nowrap}"
    "#tf-table tr.rowlink td.mcol{grid-column:4;grid-row:1/3;align-self:start;justify-self:end}"
    "#tf-table tr.rowlink td.mcol .mstar{width:32px;height:32px;min-width:32px;min-height:32px;padding:0}"
    "#tf-table tr.rowlink .rk{grid-column:1;grid-row:3;justify-self:start}"
    "#tf-table tr.rowlink td.sg-c{grid-column:2/4;grid-row:3;display:block!important;overflow:hidden;min-width:0}"
    "#tf-table tr.rowlink td.sg-c .sgw{display:flex!important;flex-wrap:nowrap;gap:4px;align-items:center;min-width:0;max-width:none}"
    "#tf-table tr.rowlink td.sg-c .sgl{display:contents!important}"
    "#tf-table tr.rowlink td.sg-c .pill{font-size:11px;line-height:16px;padding:1px 6px;margin:0;white-space:nowrap;max-width:6.2em;overflow:hidden;text-overflow:ellipsis;flex:none}"
    "#tf-table tr.rowlink td.sg-c .pill.px{display:none}"
    "#tf-table tr.rowlink td.sg-c .pmore{display:inline-flex!important;flex:none;font-size:11px;line-height:16px;padding:1px 6px;min-height:0;min-width:0}"
    "#tf-table tr.rowlink .rkp-s .score{grid-column:4;grid-row:3;justify-self:end}"
    "#tf-table tr.rowlink .rkp-s .score .sv{font-size:14px;color:#94a3b8}"
    "#tf-table tr.rowlink td.pt-c,#tf-table tr.rowlink td.tint,#tf-table tr.rowlink td.since-c,#tf-table tr.rowlink>td:nth-child(5),#tf-table tr.rowlink>td:nth-child(6){display:none!important}"
    "#tf-table .evleg .evs{flex:none;white-space:nowrap}"
    "}"
    # Røde flagg: ett kort per ticker
    ".rfc{background:#1c2430;border:1px solid #3b4757;border-radius:12px;padding:12px;margin:0 0 8px}"
    ".rfc-h{display:flex;align-items:center;justify-content:space-between;gap:8px}.rfc-h .tn .nm{font-size:16px;line-height:22px;font-weight:600}"
    ".rfc-n{flex:none;font-size:12px;line-height:20px;padding:0 8px;border-radius:10px;background:#3a1418;color:#ff7b72;border:1px solid #f8514966;white-space:nowrap}"
    ".rfc ul.fb{display:block!important;list-style:none;margin:6px 0 0;padding:0}.rfc li{font-size:13px;line-height:20px;display:flex!important;width:100%;align-items:center;gap:6px;flex-wrap:wrap;margin:0 0 2px}.rfc li .evb{font-size:13px}"
    ".rfc li .d{font-size:12px;color:#94a3b8}"
    # Signal-boka: ett kort per signal
    ".pfs{background:#1c2430;border:1px solid #3b4757;border-top:3px solid #58a6ff;border-radius:12px;padding:12px;margin:0 0 8px}"
    ".pfs-h{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}.pfs-h b{font-size:16px}.pfs-h .t,.pfs-h .d{font-size:12px;color:#94a3b8}.pfs-h .d{margin-left:auto}"
    ".pfs-k{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:8px}"
    ".pfs-k>div{background:#111821;border-radius:6px;padding:8px}.pfs-k .l{display:block;font-size:12px;line-height:16px;text-transform:uppercase;color:#cbd5e1}"
    ".pfs-k .v{display:block;font-size:20px;line-height:24px;font-weight:600}.pfs-k .s{display:block;font-size:11px;line-height:14px;color:#94a3b8}"
    "\n")

# Søk i lista: filtrerer synlige rader på navn/ticker sammen med filterknappene (skjuler bare, endrer ikke sortering).
SEARCH_HTML = '<input type="search" class="tf-q" id="tf-q" placeholder="Søk" aria-label="Søk i lista" autocomplete="off">'
SEARCH_JS = ("<script>(()=>{const q=document.getElementById('tf-q');if(!q)return;const run=()=>{const v=q.value.trim().toLowerCase();"
             "document.querySelectorAll('#tf-table tr.rowlink').forEach(r=>{const t=(r.dataset.t+' '+(r.querySelector('.nm')||{}).textContent).toLowerCase();"
             "if(v&&!t.includes(v)){r.dataset.qh='1';r.style.display='none'}else if(r.dataset.qh){delete r.dataset.qh;r.style.display=''}})};"
             "q.addEventListener('input',run)})()</script>")
