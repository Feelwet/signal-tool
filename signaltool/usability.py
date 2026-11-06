"""UxBot 06.11: lesbarhet uten endring av verdier, regler eller sortering."""
CSS = """
.score-note{display:block;font-size:11px!important;line-height:14px!important;font-weight:400;color:#94a3b8;white-space:normal;overflow-wrap:anywhere;margin-top:3px}
.score.mu{max-width:100%;min-width:0;box-sizing:border-box;white-space:normal;height:auto}
.ov-list li>span:first-child{white-space:normal;overflow:visible;text-overflow:clip;min-width:0}
.ov-list .tn .nm{white-space:normal;overflow:visible;text-overflow:clip}
.ov-list li>.sc-mu{white-space:normal;max-width:100px;text-align:right}
#tf-table .tn .nm{display:block!important;-webkit-line-clamp:unset!important;line-clamp:unset!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important;overflow-wrap:anywhere!important;min-width:0!important}
#tf-table .tn .tk{white-space:normal!important;overflow:visible!important;flex-wrap:wrap!important;overflow-wrap:anywhere;min-width:0!important}
#tf-table td.sg-c .pill{white-space:normal!important;overflow:visible!important;text-overflow:clip!important;max-width:100%!important;overflow-wrap:anywhere;box-sizing:border-box}
#tf-table td.sg-c .sgw{flex-wrap:wrap!important;max-width:100%!important;gap:4px}
#tf-table td.sg-c .sgl{flex-wrap:wrap!important;max-width:100%;min-width:0}
#tf-table td.sg-c{overflow:visible!important}
#tf-table .rsh-t,.rsh-t{display:block!important;white-space:normal!important;margin:3px 0 0!important;flex-basis:100%}
.ticker-details{font-size:12px;line-height:18px;white-space:normal;margin-top:8px;min-width:0}
.ticker-details>summary{min-height:44px;display:flex;align-items:center;color:#58a6ff;cursor:pointer;white-space:normal}
.ticker-details p{margin:6px 0;white-space:normal}.ticker-details .inn-p{white-space:normal}
@media(min-width:600px){
#tf-table .card,#tf-table .tw{min-width:0;max-width:100%;box-sizing:border-box}
#tf-table table{width:100%;min-width:0;max-width:100%;table-layout:fixed}
#tf-table table th,#tf-table table td{min-width:0!important;max-width:none;white-space:normal;overflow-wrap:anywhere;box-sizing:border-box;padding-left:6px;padding-right:6px}
#tf-table table th:first-child,#tf-table table tr.rowlink>td:first-child{width:30%!important;min-width:0!important}
#tf-table table th:nth-child(2),#tf-table table td:nth-child(2){width:12%}
#tf-table table th:nth-child(3),#tf-table table td:nth-child(3){width:12%}
#tf-table table th:nth-child(4),#tf-table table td:nth-child(4){width:23%;max-width:none}
#tf-table table th:nth-child(5),#tf-table table td:nth-child(5),#tf-table table th:nth-child(6),#tf-table table td:nth-child(6),#tf-table table th:nth-child(7),#tf-table table td:nth-child(7){display:none}
#tf-table table th:nth-child(8),#tf-table table td:nth-child(8){width:16%;white-space:normal}
#tf-table table th:last-child,#tf-table table td:last-child{width:7%;text-align:center}
#tf-table table .mstar{min-width:32px;width:32px;padding:0}
#tf-table table .tn{max-width:100%}
}
@media(max-width:599px){
#tf-table tr.rowlink .tn{flex-direction:column!important;align-items:flex-start;overflow:visible!important;gap:2px}
#tf-table tr.rowlink .tn .tk{flex:0 1 auto!important}
#tf-table tr.rowlink .since-m,#tf-table tr.rowlink .since-m *{white-space:normal!important;overflow:visible!important;text-overflow:clip!important}
#tf-table tr.rowlink .ticker-details{grid-column:1/-1;grid-row:5}
#tf-table tr.rowlink .rkp-s .score .score-note{font-size:10px!important;line-height:13px!important}
#tf-table tr.rowlink td.ret-c .rsh-t{display:block!important;flex-basis:100%}
}
"""
