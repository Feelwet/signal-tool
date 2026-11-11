"""UxBot 11.11 (bindende): tickertabellen ved ≤ 599 px – rad i to linjer + scoreboks i fast 44 px-kolonne til høyre.

Linje 1: navn 15/20 med ellipsis (min-width:0) + ticker 12/16 grå. Linje 2: avkastning 13/18 høyrestilt, «mot indeks» under.
Høyre kolonne (44 px): ★ øverst, scoreboks under – ingen overlapp. Nederst: risikobrikke + én signalbrikke + «+n» for resten
(data-m på cellen). Evidens-forklaringen brytes (flex-wrap). Krav: alle rader ≤ 96 px og scrollWidth = clientWidth ved 390.
«siden/inn»-linja og «Detaljer» vises ikke i raden på mobil (står på tickersiden). Lastes sist og bare under 600 px:
1280 er uendret. Prefikset «html body» gir høyere spesifisitet enn de eldre mobilreglene (ux2/usability/since)."""

R = "html body #tf-table tr.rowlink"
CSS = ("@media(max-width:599px){"
       "html body #tf-table .evleg{display:flex!important;flex-wrap:wrap!important;overflow:visible!important;white-space:normal!important;gap:2px 8px!important}"
       "html body #tf-table .evleg .evs{white-space:nowrap}"
       f"{R}{{display:grid!important;grid-template-columns:auto minmax(0,1fr) 44px!important;grid-template-rows:auto auto auto auto;column-gap:6px!important;row-gap:2px!important;"
       "align-items:center;padding:6px 0!important;max-height:96px;overflow:hidden;box-sizing:border-box}"
       f"{R}[hidden]{{display:none!important}}"
       f"{R}>td:first-child,{R} td.rk-c,{R} .rkp-s{{display:contents!important}}"
       f"{R} .tn{{grid-column:1/3!important;grid-row:1!important;display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:baseline!important;gap:6px!important;min-width:0!important;overflow:hidden!important}}"
       f"{R} .tn .nm{{flex:0 1 auto!important;min-width:0!important;font-size:15px!important;line-height:20px!important;font-weight:600;display:block!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;overflow-wrap:normal!important}}"
       f"{R} .tn .tk{{flex:0 0 auto!important;max-width:55%;min-width:0!important;display:flex!important;flex-wrap:nowrap!important;align-items:baseline;gap:4px;font-size:12px!important;line-height:16px!important;color:#94a3b8;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis}}"
       f"{R} .tn .tk *{{white-space:nowrap!important}}{R} .tn .tk .tv,{R} .tn .tk .dci{{display:none!important}}"
       f"{R} .since-m,{R} .ticker-details,{R} td.pt-c,{R} td.tint,{R} td.since-c,{R}>td:nth-child(5),{R}>td:nth-child(6){{display:none!important}}"
       f"{R} td.ret-c{{grid-column:1/3!important;grid-row:2/4!important;display:block!important;text-align:right!important;justify-self:end;align-self:start;max-width:none!important;width:auto!important;white-space:nowrap!important;padding:0!important}}"
       f"{R} td.ret-c .rv,{R} td.ret-c .ri.ri-c>.rv{{font-size:13px!important;line-height:18px!important;font-weight:600}}"
       f"{R} td.ret-c .rtx{{display:inline!important;font-size:13px!important;line-height:18px!important;white-space:nowrap!important;max-width:none!important;margin:0!important}}"
       f"{R} td.ret-c .rsh-t{{display:inline!important;font-size:11px!important;line-height:18px!important;margin:0 0 0 4px!important;flex-basis:auto!important}}"
       f"{R} td.ret-c .rex{{display:block!important;font-size:11px!important;line-height:14px!important;color:#94a3b8;white-space:nowrap!important}}"
       f"{R} td.mcol{{grid-column:3!important;grid-row:1/3!important;align-self:start;justify-self:center;width:44px!important}}"
       f"{R} td.mcol .mstar{{width:32px;height:32px;min-width:32px;min-height:32px;padding:0}}"
       f"{R} .rkp-s .score{{grid-column:3!important;grid-row:3/5!important;justify-self:stretch;align-self:end;width:44px!important;max-width:44px!important;min-width:0!important;box-sizing:border-box;padding:2px 0!important;margin:0!important;text-align:center;height:auto}}"
       f"{R} .rkp-s .score .sv{{font-size:13px!important;line-height:16px!important}}{R} .rkp-s .score .score-note{{display:none!important}}"
       f"{R} .rk{{grid-column:1!important;grid-row:4!important;justify-self:start;font-size:11px;line-height:16px}}"
       f"{R} td.sg-c{{grid-column:2!important;grid-row:4!important;display:flex!important;flex-wrap:nowrap!important;align-items:center;gap:4px;min-width:0!important;overflow:hidden!important;white-space:nowrap!important}}"
       f"{R} td.sg-c .sgw,{R} td.sg-c .sgl{{display:contents!important}}"
       f"{R} td.sg-c .pill,{R} td.sg-c .pmore{{display:none!important}}"
       f"{R} td.sg-c>.pill:first-child,{R} td.sg-c>.sgw>.pill:first-child{{display:inline-block!important;flex:0 1 auto;min-width:0;max-width:100%!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;font-size:11px;line-height:16px;padding:1px 6px;margin:0}}"
       f"{R} td.sg-c[data-m]::after{{content:'+' attr(data-m);flex:none;font-size:11px;line-height:16px;padding:1px 6px;border:1px solid #333b47;border-radius:999px;color:#d5dde6}}"
       "}"
       "@media(min-width:600px){#tf-table td.sg-c::after{content:none}}\n")
