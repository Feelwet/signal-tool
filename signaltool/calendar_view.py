"""Månedskalender (vanilla JS) bygd oppå den statiske listen. Alle hendelser bakes inn som JSON."""
from __future__ import annotations
import html
import json
from . import sectors as SEC

TYPES = {"sentralbank": ("◆", "Sentralbank"), "resultat": ("▲", "Resultat"), "makro": ("●", "Makro")}
FOLLOWED = {"USAR", "SUBC.OL", "AKSO.OL", "FRO.OL", "OET.OL", "NORBT.OL"}


def ev_type(e: dict) -> str:
    k = (e.get("kind") or "").lower()
    if "sentral" in k or "rente" in k:
        return "sentralbank"
    if k in ("resultat", "earnings", "kvartal", "rapport") or e.get("ticker"):
        return "resultat"
    return "makro"


def events_json(cal: list[dict]) -> list[dict]:
    out = []
    for e in cal or []:
        t = e.get("ticker") or ""
        src = e.get("source") or ""
        out.append({"date": str(e.get("date", ""))[:10], "time": e.get("time") or "", "type": ev_type(e),
                    "title": e.get("title") or "", "source": src, "est": "estimert" in src.lower() or bool(e.get("estimated")),
                    "ticker": t, "tv": SEC.tv_url(t) if t else None,
                    "follow": t.upper() in FOLLOWED or t.upper().replace(".OL", "") in {x.replace(".OL", "") for x in FOLLOWED}})
    return out


CSS = """<style>
.cal-js{display:none}.js .cal-js{display:block}.js .cal-list{display:none}
.calbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:8px 0}
.calbar h2{margin:0;min-width:11ch;text-align:center;font-size:1.2em}
.calbar button,.calflt button{min-width:44px;min-height:44px;padding:4px 12px;border:1px solid #778;border-radius:3px;background:transparent;color:inherit;font:inherit;cursor:pointer}
.calflt{margin:6px 0}.calflt button{min-height:32px;margin:0 6px 6px 0}.calflt button[aria-pressed=true]{background:#6cb6ff;border-color:#6cb6ff;color:#0d1117}
.grid{display:grid;grid-template-columns:32px repeat(7,1fr);border-top:1px solid #30363d;border-left:1px solid #30363d}
.grid>div{border-right:1px solid #30363d;border-bottom:1px solid #30363d;min-height:92px;padding:4px;font-size:.8em;overflow:hidden}
.grid .wd{min-height:0;text-align:center;color:#9ea9b5;font-weight:600}.grid .wk{color:#9ea9b5;text-align:center;min-height:0}
.day{cursor:pointer}.day:focus{outline:2px solid #6cb6ff;outline-offset:-2px}.day.out{opacity:.4}
.day .dn{font-weight:600}.day.today .dn{display:inline-block;border:2px solid #6cb6ff;border-radius:50%;width:24px;height:24px;line-height:20px;text-align:center}
.evl{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
.t-sentralbank{color:#d2a8ff}.t-resultat{color:#6cb6ff}.t-makro{color:#e3b341}
.more{color:#9ea9b5}.fol{font-size:.75em;border:1px solid #3fb950;color:#3fb950;border-radius:3px;padding:0 4px;margin-left:4px}
.panel{margin-top:12px;border:1px solid #6cb6ff;border-radius:6px;padding:10px 12px}.panel ul{margin:6px 0 0;padding-left:0;list-style:none}.panel li{margin:6px 0}
.mlist h3{margin:14px 0 4px;font-size:1em}.mlist ul{list-style:none;padding:0;margin:0}.mlist li{margin:4px 0}
.mlist{display:none}@media(max-width:699px){.grid{display:none}.mlist{display:block}}
</style>"""

JS = r"""<script>(()=>{document.documentElement.classList.add('js');
const EV=JSON.parse(document.getElementById('cal-data').textContent),TY=%TYPES%;
const MN=['januar','februar','mars','april','mai','juni','juli','august','september','oktober','november','desember'];
const WD=['man','tir','ons','tor','fre','lør','søn'];
const p2=n=>String(n).padStart(2,'0'),iso=d=>d.getFullYear()+'-'+p2(d.getMonth()+1)+'-'+p2(d.getDate());
const now=new Date(),today=iso(now);const on=new Set(Object.keys(TY));
let y,m;function fromUrl(){const q=new URLSearchParams(location.search).get('m');const r=/^(\d{4})-(\d{2})$/.exec(q||'');
if(r){y=+r[1];m=+r[2]-1}else{y=now.getFullYear();m=now.getMonth()}}
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const byDay=d=>EV.filter(e=>e.date===d&&on.has(e.type)).sort((a,b)=>a.time.localeCompare(b.time));
function wk(d){const t=new Date(Date.UTC(d.getFullYear(),d.getMonth(),d.getDate()));const n=t.getUTCDay()||7;t.setUTCDate(t.getUTCDate()+4-n);
const y1=new Date(Date.UTC(t.getUTCFullYear(),0,1));return Math.ceil(((t-y1)/864e5+1)/7)}
function name(e){const tk=e.ticker?(e.tv?`<a class="tv" target="_blank" rel="noopener" title="Graf på TradingView" aria-label="${esc(e.ticker)} – åpne graf på TradingView (ny fane)" href="${esc(e.tv)}"><b>${esc(e.ticker)}</b> ↗</a> `:`<b>${esc(e.ticker)}</b> `):'';
return tk+esc(e.title)}
function line(e){const[i,l]=TY[e.type];return `<span class="evl t-${e.type}" title="${esc(l)}: ${esc(e.title)}">${i} ${esc(e.time)} ${esc(e.ticker||e.title)}</span>`}
function detail(e){const[i,l]=TY[e.type];return `<li><span class="t-${e.type}">${i} ${l}</span> · ${esc(e.time||'hele dagen')} · ${name(e)}${e.follow?'<span class="fol">Følges</span>':''}<div class="src">${esc(e.source)}${e.est&&!/estimert/i.test(e.source)?' (estimert)':''}</div></li>`}
const $=id=>document.getElementById(id);
function render(){const first=new Date(y,m,1),title=MN[m][0].toUpperCase()+MN[m].slice(1)+' '+y;$('cal-title').textContent=title;
let h='<div class="wd">uke</div>'+WD.map(w=>`<div class="wd">${w}</div>`).join('');
const st=new Date(y,m,1-((first.getDay()+6)%7));
for(let r=0;r<6;r++){const ws=new Date(st.getFullYear(),st.getMonth(),st.getDate()+r*7);if(r>3&&ws.getMonth()!==m)break;h+=`<div class="wk">${wk(ws)}</div>`;
for(let c=0;c<7;c++){const d=new Date(ws.getFullYear(),ws.getMonth(),ws.getDate()+c),k=iso(d),ev=byDay(k);
const cls='day'+(d.getMonth()!==m?' out':'')+(k===today?' today':'');
h+=`<div class="${cls}" tabindex="0" role="button" data-d="${k}" aria-label="${d.getDate()}. ${MN[d.getMonth()]}: ${ev.length} hendelser"${k===today?' aria-current="date"':''}><span class="dn">${d.getDate()}</span>`
+ev.slice(0,3).map(line).join('')+(ev.length>3?`<span class="evl more">+${ev.length-3} til</span>`:'')+'</div>'}}
$('cal-grid').innerHTML=h;
let L='';const last=new Date(y,m+1,0).getDate();const startD=(y===now.getFullYear()&&m===now.getMonth())?now.getDate():1;
for(let d=startD;d<=last;d++){const k=y+'-'+p2(m+1)+'-'+p2(d),ev=byDay(k);if(!ev.length)continue;
const dt=new Date(y,m,d);L+=`<h3>${WD[(dt.getDay()+6)%7]} ${d}. ${MN[m]}${k===today?' (i dag)':''}</h3><ul>${ev.map(detail).join('')}</ul>`}
$('cal-mlist').innerHTML=L||'<p class="mut">Ingen hendelser'+(startD>1?' resten av måneden':' denne måneden')+'.</p>';closePanel()}
function openPanel(k){const ev=byDay(k),[yy,mm,dd]=k.split('-').map(Number);const P=$('cal-panel');
P.innerHTML=`<h3 style="margin:0">${dd}. ${MN[mm-1]} ${yy}</h3>`+(ev.length?`<ul>${ev.map(detail).join('')}</ul>`:'<p class="mut">Ingen hendelser.</p>')+'<p class="src">Tider i norsk tid. Esc lukker.</p>';P.hidden=false}
function closePanel(){$('cal-panel').hidden=true}
function go(dm,push=true){m+=dm;if(dm===0){y=now.getFullYear();m=now.getMonth()}y+=Math.floor(m/12);m=((m%12)+12)%12;
if(push)history.pushState({},'','?m='+y+'-'+p2(m+1));render()}
$('cal-prev').onclick=()=>go(-1);$('cal-next').onclick=()=>go(1);$('cal-today').onclick=()=>go(0);
$('cal-grid').addEventListener('click',e=>{const d=e.target.closest('.day');if(d&&!e.target.closest('a'))openPanel(d.dataset.d)});
$('cal-grid').addEventListener('keydown',e=>{const d=e.target.closest('.day');if(d&&(e.key==='Enter'||e.key===' ')){e.preventDefault();openPanel(d.dataset.d)}});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closePanel();
if(/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;if(e.key==='ArrowLeft')go(-1);if(e.key==='ArrowRight')go(1)});
document.querySelectorAll('.calflt button').forEach(b=>b.onclick=()=>{const t=b.dataset.t;on.has(t)?on.delete(t):on.add(t);b.setAttribute('aria-pressed',on.has(t));render()});
addEventListener('popstate',()=>{fromUrl();render()});fromUrl();render()})()</script>"""


def calendar_html(cal: list[dict], list_html: str) -> str:
    data = json.dumps(events_json(cal), ensure_ascii=False).replace("</", "<\\/")
    flt = "".join(f'<button data-t="{k}" aria-pressed="true"><span class="t-{k}">{i}</span> {l}</button>' for k, (i, l) in TYPES.items())
    js = JS.replace("%TYPES%", json.dumps({k: list(v) for k, v in TYPES.items()}, ensure_ascii=False))
    return (CSS + '<div class="cal-js card"><div class="calbar"><button id="cal-prev" aria-label="Forrige måned">‹</button>'
            '<h2 id="cal-title" aria-live="polite"></h2><button id="cal-next" aria-label="Neste måned">›</button>'
            '<button id="cal-today">I dag</button></div>'
            f'<div class="calflt" role="group" aria-label="Filtrer type">{flt}</div>'
            '<div class="grid" id="cal-grid"></div><div class="mlist" id="cal-mlist"></div>'
            '<div class="panel" id="cal-panel" hidden aria-live="polite"></div></div>'
            f'<script type="application/json" id="cal-data">{data}</script>'
            f'<div class="cal-list">{list_html}</div>{js}')
