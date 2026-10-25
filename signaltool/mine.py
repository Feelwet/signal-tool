"""«★ Mine»: personlig tickerliste som bare ligger i nettleseren (localStorage `signaltool.minliste`).

Ingenting lagres i repoet eller på serveren, og lista påvirker aldri treffrater, tellere eller kategoriregler:
den leses bare i nettleseren, etter at siden er generert. Deling/flytting: `?mine=HAS,EQNR.OL` (flettes inn,
validert mot sidens egen tickerliste)."""
from __future__ import annotations

import json
from html import escape as E

KEY = "signaltool.minliste"
PARAM = "mine"
CAT_SHORT = {"kjop": "Kjøp", "hold": "Hold", "watch": "Følg"}


def data(tickers: list[dict], slug) -> dict:
    """Bare felt som allerede finnes i snapshotet: kategori, endring siden i går (ret_1d) og røde flagg."""
    out = {}
    for e in tickers:
        st = e.get("stats") or {}
        cf = e.get("cat_flags") or {}
        fl = [str(x) for x in (cf.values() if isinstance(cf, dict) else cf)]
        out[e["ticker"]] = {"s": slug(e["ticker"]), "n": e.get("name") or "", "c": CAT_SHORT.get(e.get("category"), "–"),
                            "d": st.get("ret_1d"), "f": fl}
    return out


def script(tickers: list[dict], slug) -> str:
    m = json.dumps(data(tickers, slug), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"<script>window.ST_T={m};</script>" + JS.replace("{KEY}", KEY).replace("{PARAM}", PARAM)


def star(ticker: str) -> str:
    return (f'<button type="button" class="mstar" data-t="{E(ticker)}" aria-pressed="false" '
            f'aria-label="Lagre {E(ticker)} i ★ Mine" title="Lagre i ★ Mine">☆</button>')


def tile() -> str:
    return ('<div id="mine-tile" class="card mine-tile" hidden><h2 style="margin:0 0 6px">★ Mine</h2>'
            '<div class="mine-rows"></div><p class="mut" style="margin:6px 0 0"><a href="#" class="mine-share">Del / flytt lista</a>'
            ' · Lista ligger bare i denne nettleseren.</p></div>')


EMPTY = "Trykk ☆ på en ticker for å lagre den"

CSS = """
.mstar{min-width:44px;min-height:44px;width:44px;height:44px;padding:0;border:0;background:none;color:var(--mut);font-size:22px;line-height:1;cursor:pointer;border-radius:8px;flex:none}
.mstar[aria-pressed=true]{color:#e3b341}.mstar:focus-visible{outline:2px solid var(--acc)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
td.mcol{width:44px;padding:0!important;text-align:right}
.mine-toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#1f2937;color:#fff;border:1px solid #30363d;padding:10px 16px;border-radius:10px;z-index:99;font-size:14px}
.mine-tile .mrow{display:flex;gap:10px;align-items:center;padding:4px 0;border-bottom:1px solid #21262d;flex-wrap:wrap}
.mine-tile .mrow a{font-weight:700}.mine-tile .up{color:var(--up,#56d364)}.mine-tile .dn{color:var(--down,#ff7b72)}
.mine-share-out{font:12px ui-monospace,monospace;word-break:break-all}
"""

JS = r"""<script>(()=>{const K='{KEY}',P='{PARAM}',T=window.ST_T||{},d=document;
function load(){try{const v=JSON.parse(localStorage.getItem(K)||'[]');return Array.isArray(v)?v.filter(t=>T[t]):[]}catch(e){return[]}}
function save(a){try{localStorage.setItem(K,JSON.stringify(a))}catch(e){}}
function toast(m){const t=d.createElement('div');t.className='mine-toast';t.setAttribute('role','status');t.textContent=m;d.body.appendChild(t);setTimeout(()=>t.remove(),1800)}
function parse(s){return[...new Set((s||'').split(',').map(x=>x.trim().toUpperCase()).filter(x=>T[x]))]}
function link(){const u=new URL(d.querySelector('a.brand').href);u.pathname=u.pathname.replace(/[^/]*$/,'tickere.html');u.search='?'+P+'='+load().join(',');u.hash='';return u.toString().replace(/%2C/g,',')}
let imp=false;const q=new URL(location.href);if(q.searchParams.has(P)){imp=true;const add=parse(q.searchParams.get(P)),cur=load(),n=add.filter(t=>!cur.includes(t)).length;save([...cur,...add.filter(t=>!cur.includes(t))]);
q.searchParams.delete(P);if(!q.searchParams.has('filter')&&add.length)q.searchParams.set('filter','mine');history.replaceState(null,'',q);setTimeout(()=>toast(n+' ticker'+(n===1?'':'e')+' lagt til i ★ Mine'),50)}
function pct(x){return x==null?'':(x>0?'+':'')+(x*100).toFixed(1).replace('.',',')+' %'}
function paint(){const a=load();d.querySelectorAll('.mstar').forEach(b=>{const on=a.includes(b.dataset.t);b.textContent=on?'★':'☆';b.setAttribute('aria-pressed',on?'true':'false');b.title=on?'Fjern fra ★ Mine':'Lagre i ★ Mine'});
d.querySelectorAll('.mine-n').forEach(s=>s.textContent=a.length);
const tl=d.getElementById('mine-tile');if(tl){tl.hidden=!a.length;const pre=d.querySelector('a.brand').getAttribute('href').replace(/index\.html$/,'');
tl.querySelector('.mine-rows').innerHTML=a.map(t=>{const r=T[t],e=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]);
return '<div class="mrow"><a href="'+pre+'ticker/'+e(r.s)+'.html">'+e(t)+'</a><span>'+e(r.c)+'</span>'+(r.d==null?'':'<span class="'+(r.d>0?'up':r.d<0?'dn':'')+'" title="Endring siden i går">'+pct(r.d)+'</span>')+(r.f.length?'<span class="fchip" title="'+e(r.f.join('; '))+'">⚑ '+r.f.length+' rødt flagg'+(r.f.length>1?'':'')+'</span>':'')+'</div>'}).join('')}
d.dispatchEvent(new CustomEvent('mine:change',{detail:{imp:imp}}));imp=false}
d.addEventListener('click',ev=>{const b=ev.target.closest&&ev.target.closest('.mstar');if(b){ev.preventDefault();const a=load(),t=b.dataset.t,i=a.indexOf(t);if(i<0){a.push(t);save(a);toast('Lagt til i ★ Mine')}else{a.splice(i,1);save(a);toast('Fjernet fra ★ Mine')}paint();return}
const s=ev.target.closest&&ev.target.closest('.mine-share');if(s){ev.preventDefault();const u=link();let o=s.parentNode.querySelector('.mine-share-out');if(!o){o=d.createElement('div');o.className='mine-share-out';s.parentNode.appendChild(o)}o.textContent=u;
try{navigator.clipboard.writeText(u).then(()=>toast('Lenken er kopiert'),()=>{})}catch(e){}}});
window.STMine={load:load};paint()})()</script>"""
