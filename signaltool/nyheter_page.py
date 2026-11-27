"""Nyheter-siden: UxBot-layout (390 og 1280). Bare overskrift, kilde, tid og lenke.

Henter logs/nyheter.json ved lasting fra raw.githubusercontent.com (master),
med site/data/nyheter.json som reserve, så 10-minuttersoppdateringer vises uten redeploy.
"""
from __future__ import annotations

from html import escape as E
from pathlib import Path
import shutil

RAW_JSON = "https://raw.githubusercontent.com/Feelwet/signal-tool/master/logs/nyheter.json"
FALLBACK_JSON = "data/nyheter.json"
RAW_KORT = "https://raw.githubusercontent.com/Feelwet/signal-tool/master/logs/nbs_industriprofitt.json"
FALLBACK_KORT = "data/nbs_industriprofitt.json"
TABS = ("Alt", "Norge", "Marked", "Verden", "Børsmeldinger")
FT_CREDIT = "© The Financial Times Limited 2026. Overskrifter og lenker; ingen artikkeltekst lagres."


PAGE_CSS = r"""
/* Nyheter (UxBot 17.11): 390 px og 1280 px. Ingen horisontal scroll. */
body.pg-nyheter{overflow-x:hidden}
body.pg-nyheter main{max-width:none;width:100%;margin:0;padding:0;flex:1;min-width:0}
body.pg-nyheter .ny{min-width:0;max-width:100%;overflow-x:hidden}
.ny-bar{height:56px;min-height:56px;max-height:56px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 12px;box-sizing:border-box;border-bottom:1px solid var(--line,#2d333b)}
.ny-bar h1{margin:0;font:600 17px/24px system-ui,-apple-system,sans-serif;color:var(--ink,#e6edf3)}
.ny-upd{margin:0;font:400 12px/16px system-ui,-apple-system,sans-serif;color:#94a3b8;white-space:nowrap}
.ny-tabs{height:44px;min-height:44px;display:flex;align-items:stretch;gap:0;overflow-x:auto;overflow-y:hidden;padding:0 12px;box-sizing:border-box;border-bottom:1px solid var(--line,#2d333b);scrollbar-width:none;-webkit-overflow-scrolling:touch}
.ny-tabs::-webkit-scrollbar{display:none}
.ny-tab{flex:none;height:44px;min-height:44px;min-width:44px;padding:0 12px;margin:0;border:0;background:none;color:#94a3b8;font:500 13px/16px system-ui,-apple-system,sans-serif;cursor:pointer;box-shadow:inset 0 -2px 0 transparent;white-space:nowrap}
.ny-tab[aria-selected="true"],.ny-tab.on{color:var(--ink,#e6edf3);box-shadow:inset 0 -2px 0 var(--acc,#6cb6ff)}
.ny-tools{height:44px;min-height:44px;display:flex;align-items:center;gap:8px;padding:0 12px;box-sizing:border-box}
.ny-q{flex:1 1 auto;min-width:0;height:44px;min-height:44px;box-sizing:border-box;padding:0 10px;border:1px solid var(--line,#2d333b);border-radius:6px;background:var(--card,#161b22);color:var(--ink,#e6edf3);font:400 14px/20px system-ui,-apple-system,sans-serif}
.ny-kbtn{flex:0 0 auto;width:auto;min-width:44px;height:44px;padding:0 8px;box-sizing:border-box;border:1px solid var(--line,#2d333b);border-radius:6px;background:var(--card,#161b22);color:var(--ink,#e6edf3);font:500 12px/16px system-ui,-apple-system,sans-serif;cursor:pointer;white-space:nowrap}
.ny-list{margin:0;padding:0;padding-bottom:calc(56px + env(safe-area-inset-bottom));min-width:0}
.ny-row{display:flex;align-items:center;gap:8px;min-height:56px;max-height:72px;height:auto;margin:0 12px;padding:8px 0;box-sizing:border-box;border-bottom:1px solid var(--line,#2d333b);color:inherit!important;text-decoration:none!important;overflow:hidden}
.ny-row:focus-visible{outline:2px solid var(--acc,#6cb6ff);outline-offset:2px;border-radius:4px}
.ny-time{flex:0 0 44px;width:44px;font:400 12px/16px system-ui,-apple-system,sans-serif;color:#94a3b8;padding-top:2px}
.ny-body{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:2px}
.ny-title{font:400 15px/20px system-ui,-apple-system,sans-serif;color:var(--ink,#e6edf3);display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;max-height:40px}
.ny-meta{display:flex;align-items:center;gap:6px;min-width:0;font:400 12px/16px system-ui,-apple-system,sans-serif;color:#94a3b8}
.ny-chip{flex:none;display:inline-flex;align-items:center;height:16px;padding:0 6px;border-radius:4px;border:1px solid var(--line,#2d333b);background:var(--pill,#262d38);font:500 12px/16px system-ui,-apple-system,sans-serif;color:var(--ink,#e6edf3)}
.ny-src{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ny-empty{height:48px;min-height:48px;display:flex;align-items:center;margin:0 12px;font:400 14px/20px system-ui,-apple-system,sans-serif;color:#94a3b8}
.ny-ft{margin:10px 12px 16px;font:400 11px/16px system-ui,-apple-system,sans-serif;color:#94a3b8}
.ny-kilder{display:none}
.ny-sheet-bg{display:block;position:fixed;inset:0;z-index:70;background:rgba(0,0,0,.5)}
.ny-sheet-bg[hidden]{display:none}
.ny-sheet{display:block;position:fixed;left:0;right:0;bottom:0;z-index:71;max-height:min(70vh,480px);overflow:auto;background:#1c2430;border-top:1px solid #3b4757;border-radius:12px 12px 0 0;padding:8px 0 calc(16px + env(safe-area-inset-bottom,0px))}
.ny-sheet[hidden]{display:none}
.ny-sheet-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:0 8px 0 16px;box-sizing:border-box;position:sticky;top:0;background:#1c2430;z-index:1}
.ny-sheet h2{margin:0;padding:8px 0;font:600 15px/20px system-ui,-apple-system,sans-serif;flex:1 1 auto;min-width:0}
.ny-slukk{flex:none;width:44px;height:44px;min-width:44px;min-height:44px;padding:0;border:0;border-radius:6px;background:transparent;color:var(--ink,#e6edf3);font:500 13px/16px system-ui,-apple-system,sans-serif;cursor:pointer}
.ny-ks{display:flex;align-items:center;gap:8px;width:100%;min-height:44px;padding:0 16px;box-sizing:border-box;font:400 13px/16px system-ui,-apple-system,sans-serif;cursor:pointer}
.ny-ks.down{border:1px dashed #94a3b8;border-width:1px 0;background:transparent}
.ny-ks input{flex:none;width:16px;height:16px;margin:0}
.ny-ks .ny-kn{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ny-ks .ny-kst{flex:none;color:#94a3b8;font:400 12px/16px system-ui,-apple-system,sans-serif}
body.pg-nyheter{overflow-x:hidden}
@media(max-width:768px){
body.pg-nyheter footer,body.pg-nyheter .gen-line{display:none!important}
body.pg-nyheter header.top{display:flex;height:56px;min-height:56px;max-height:56px}
body.pg-nyheter main{padding:0}
}
@media(min-width:1280px){
body.pg-nyheter,body.pg-nyheter .app,body.pg-nyheter .content,body.pg-nyheter main,body.pg-nyheter .ny,body.pg-nyheter .ny-desk{overflow:visible;overflow-x:visible;overflow-y:visible}
body.pg-nyheter .ny-desk{display:grid;grid-template-columns:minmax(0,720px) 280px;column-gap:24px;width:auto;max-width:1024px;margin:0 auto;align-items:start;padding:0 0 24px;box-sizing:border-box}
body.pg-nyheter .ny-main{min-width:0;max-width:720px;width:auto}
body.pg-nyheter .ny-kilder{display:block;width:280px;min-width:280px;position:sticky;top:16px;align-self:start;max-height:calc(100vh - 32px);overflow-y:auto;padding:8px 0;box-sizing:border-box;border:1px solid var(--line,#2d333b);border-radius:8px;background:var(--card,#161b22)}
body.pg-nyheter .ny-kilder h2{margin:0;padding:8px 12px 6px;font:600 15px/20px system-ui,-apple-system,sans-serif}
body.pg-nyheter .ny-ks{height:32px;min-height:32px;max-height:32px;padding:0 12px}
body.pg-nyheter .ny-kbtn{display:none}
body.pg-nyheter .ny-tools{height:44px;min-height:44px}
body.pg-nyheter .ny-tabs{height:44px}
body.pg-nyheter .ny-row{height:56px;min-height:56px;max-height:56px;align-items:center}
body.pg-nyheter .ny-title{-webkit-line-clamp:1;max-height:20px;white-space:nowrap;display:block;text-overflow:ellipsis}
}

/* Forklaringskort (UxBot + AnalBot 27.11). Retning med pil og tekst, ikke farge. */
.ny-item{margin:0 12px;border-bottom:1px solid var(--line,#2d333b);min-width:0}
.ny-item .ny-row{margin:0;border-bottom:0;padding-left:0;padding-right:0}
.ny-fkbtn{display:inline-flex;align-items:center;justify-content:center;height:44px;min-height:44px;max-height:44px;margin:0 0 8px;padding:0 12px;box-sizing:border-box;border:1px solid var(--line,#2d333b);border-radius:6px;background:var(--card,#161b22);color:var(--ink,#e6edf3);font:500 13px/16px system-ui,-apple-system,sans-serif;cursor:pointer}
.ny-fkort{display:none;box-sizing:border-box;max-width:720px;padding:12px 0 16px}
.ny-fkort.open{display:block}
.ny-fk-note{margin:0 0 12px;font:400 13px/18px system-ui,-apple-system,sans-serif;color:#94a3b8}
.ny-fk-h{margin:16px 0 8px;font:600 15px/22px system-ui,-apple-system,sans-serif;color:var(--ink,#e6edf3)}
.ny-fk-h:first-child{margin-top:0}
.ny-fk-body,.ny-fk-kort p,.ny-fk-txt{font:400 15px/22px system-ui,-apple-system,sans-serif;color:var(--ink,#e6edf3)}
.ny-fk-src,.ny-fk-src a{font:400 13px/18px system-ui,-apple-system,sans-serif;color:#94a3b8;text-decoration:underline}
.ny-fk-tall{display:flex;flex-wrap:wrap;gap:16px;margin:0 0 6px}
.ny-fk-tall span{font:600 24px/28px system-ui,-apple-system,sans-serif;color:var(--ink,#e6edf3)}
.ny-fk-tag{display:inline-block;margin:0 0 8px;padding:2px 8px;border-radius:4px;background:var(--pill,#262d38);color:#94a3b8;font:500 13px/18px system-ui,-apple-system,sans-serif}
.ny-fk-br{display:flex;align-items:center;justify-content:space-between;gap:8px;height:44px;min-height:44px;max-height:44px;box-sizing:border-box;font:400 15px/22px system-ui,-apple-system,sans-serif;color:var(--ink,#e6edf3)}
.ny-fk-br .ny-fk-ch{margin-left:auto;text-align:right;white-space:nowrap}
.ny-fk-nv{display:flex;align-items:center;justify-content:space-between;gap:8px;height:56px;min-height:56px;max-height:56px;box-sizing:border-box;font:400 15px/22px system-ui,-apple-system,sans-serif;color:var(--ink,#e6edf3);border-bottom:1px solid var(--line,#2d333b)}
.ny-fk-nv .ny-fk-ch{margin-left:auto;text-align:right}
.ny-fk-attr{font:400 13px/18px system-ui,-apple-system,sans-serif;color:#94a3b8;margin-left:6px}
.ny-fk-bg{display:block;position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.5)}
.ny-fk-bg[hidden]{display:none}
.ny-fk-sheet{display:block;position:fixed;left:0;right:0;bottom:0;z-index:81;width:390px;max-width:100%;min-height:560px;max-height:90vh;overflow:auto;margin:0 auto;background:#1c2430;border-top:1px solid #3b4757;border-radius:12px 12px 0 0;padding:8px 16px calc(16px + env(safe-area-inset-bottom,0px));box-sizing:border-box}
.ny-fk-sheet[hidden]{display:none}
.ny-fk-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;position:sticky;top:0;background:#1c2430;z-index:1;padding:0 0 8px}
.ny-fk-slukk{flex:none;width:44px;height:44px;min-width:44px;min-height:44px;padding:0;border:0;border-radius:6px;background:transparent;color:var(--ink,#e6edf3);font:500 13px/16px system-ui,-apple-system,sans-serif;cursor:pointer}
@media(min-width:1280px){
.ny-fk-bg,.ny-fk-sheet{display:none!important}
.ny-fkort{max-width:720px}
}
"""


def html(snap=None) -> str:
    tabs = "".join(
        f'<button type="button" class="ny-tab{" on" if t=="Alt" else ""}" role="tab" data-tab="{E(t)}" aria-selected="{"true" if t=="Alt" else "false"}">{E(t)}</button>'
        for t in TABS
    )
    raw, fb = E(RAW_JSON), E(FALLBACK_JSON)
    rawk, fbk = E(RAW_KORT), E(FALLBACK_KORT)
    return f"""
<div class="ny" id="ny" data-raw="{raw}" data-fallback="{fb}" data-kort="{rawk}" data-kort-fallback="{fbk}">
  <div class="ny-bar"><h1>Nyheter</h1><p class="ny-upd" id="ny-upd">Oppdatert --:--</p></div>
  <div class="ny-desk">
    <div class="ny-main">
      <div class="ny-tabs" role="tablist" aria-label="Seksjoner">{tabs}</div>
      <div class="ny-tools">
        <input class="ny-q" id="ny-q" type="search" placeholder="Søk" aria-label="Søk i overskrifter">
        <button type="button" class="ny-kbtn" id="ny-kbtn" aria-controls="ny-sheet" aria-expanded="false">Kilder (0)</button>
      </div>
      <div class="ny-list" id="ny-list"></div>
      <p class="ny-ft">{E(FT_CREDIT)}</p>
    </div>
    <aside class="ny-kilder" id="ny-kilder" aria-label="Kilder"><h2>Kilder</h2><div id="ny-kilder-rows"></div></aside>
  </div>
</div>
<div class="ny-fk-bg" id="ny-fk-bg" hidden></div>
<div class="ny-fk-sheet" id="ny-fk-sheet" role="dialog" aria-label="Hva betyr dette?" hidden>
  <div class="ny-fk-head">
    <p class="ny-fk-note" id="ny-fk-note-sheet">Forklaring fra kildene, ikke en prognose</p>
    <button type="button" class="ny-fk-slukk" id="ny-fk-slukk" aria-label="Lukk">Lukk</button>
  </div>
  <div class="ny-fk-body" id="ny-fk-sheet-body"></div>
</div>
<div class="ny-sheet-bg" id="ny-sheet-bg" hidden></div>
<div class="ny-sheet" id="ny-sheet" role="dialog" aria-label="Kilder" hidden>
  <div class="ny-sheet-head">
    <h2>Kilder</h2>
    <button type="button" class="ny-slukk" id="ny-slukk" aria-label="Lukk">Lukk</button>
  </div>
  <div id="ny-sheet-rows"></div>
</div>
<script>
(function(){{
  const root=document.getElementById('ny');
  if(!root) return;
  const RAW=root.getAttribute('data-raw');
  const FB=root.getAttribute('data-fallback');
  const RAWK=root.getAttribute('data-kort');
  const FBK=root.getAttribute('data-kort-fallback');
  const TABS=["Alt","Norge","Marked","Verden","Børsmeldinger"];
  const LS='nyheter-kilder';
  const list=document.getElementById('ny-list');
  const upd=document.getElementById('ny-upd');
  const qEl=document.getElementById('ny-q');
  const kbtn=document.getElementById('ny-kbtn');
  const sheet=document.getElementById('ny-sheet');
  const sheetBg=document.getElementById('ny-sheet-bg');
  const sheetRows=document.getElementById('ny-sheet-rows');
  const colRows=document.getElementById('ny-kilder-rows');
  let data={{items:[],sources:[],generated_at_utc:null}}, tab='Alt', off={{}}, kort=null;
  try{{ off=JSON.parse(localStorage.getItem(LS)||'{{}}')||{{}} }}catch(e){{ off={{}} }}
  function isNw(it){{ return it.pool==='newsweb'||it.source_id==='newsweb'||it.section==='Børsmeldinger'; }}
  function inTab(it,t){{ if(isNw(it)) return t==='Børsmeldinger'; if(t==='Alt') return true; return it.section===t; }}
  function osloHm(d){{
    try{{
      return new Intl.DateTimeFormat('nb-NO',{{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit',hour12:false}}).format(d);
    }}catch(e){{ return '--:--'; }}
  }}
  function osloYmd(d){{
    const p=new Intl.DateTimeFormat('en-CA',{{timeZone:'Europe/Oslo',year:'numeric',month:'2-digit',day:'2-digit'}}).format(d);
    return p;
  }}
  function rowTime(iso){{
    if(!iso) return '';
    const d=new Date(iso);
    if(isNaN(d)) return '';
    const today=osloYmd(new Date());
    const ymd=osloYmd(d);
    if(ymd===today) return osloHm(d);
    const yest=new Date(); yest.setDate(yest.getDate()-1);
    /* Compare Oslo calendar days, not local weekday drift around midnight */
    if(ymd===osloYmd(new Date(Date.now()-24*3600*1000))) return 'i går';
    return osloHm(d);
  }}
  function esc(s){{ return String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c])); }}
  function kortOk(c){{ return !!(c&&c.ok&&!c.hide); }}
  function itemMatchesKort(it,c){{
    if(!kortOk(c)) return false;
    const rules=c.match||{{}};
    const url=String(it.url||'').trim();
    const title=String(it.title||'');
    const blob=(title+' '+url).toLowerCase();
    const srcs=rules.source_urls||[];
    for(let i=0;i<srcs.length;i++){{ if(srcs[i]&&(url===srcs[i]||(url.endsWith('/')?url.slice(0,-1):url)===(String(srcs[i]).endsWith('/')?String(srcs[i]).slice(0,-1):String(srcs[i])))) return true; }}
    const needles=rules.url_needles||[];
    for(let i=0;i<needles.length;i++){{ if(needles[i]&&url.toLowerCase().indexOf(String(needles[i]).toLowerCase())>=0&&url.toLowerCase().indexOf('stats.gov.cn')>=0) return true; }}
    const phrase=(rules.phrases||[]).some(p=>blob.indexOf(String(p).toLowerCase())>=0);
    const fig=(rules.figures||[]).some(f=>blob.indexOf(String(f).toLowerCase())>=0||title.indexOf(String(f))>=0);
    const geo=(rules.geo||[]).some(g=>blob.indexOf(String(g).toLowerCase())>=0);
    return phrase&&fig&&geo;
  }}
  function kortInner(c){{
    if(!kortOk(c)) return '';
    const b=c.blocks||{{}};
    const tal=(b.tallet&&b.tallet.values)||[];
    const tall=tal.map(v=>'<span>'+esc(v.label)+'</span>').join('');
    const srcUrl=(b.tallet&&b.tallet.source_url)||(c.source&&c.source.url)||'';
    const srcLine=(b.tallet&&b.tallet.source_line)||(c.source&&c.source.line)||'NBS';
    const src='<p class="ny-fk-src">'+(srcUrl?('<a href="'+esc(srcUrl)+'" target="_blank" rel="noopener noreferrer">'+esc(srcLine)+'</a>'):esc(srcLine))+'</p>';
    function rows(list, cls){{
      return (list||[]).map(r=>'<div class="'+cls+'"><span>'+esc(r.industry)+'</span><span class="ny-fk-ch">'+esc((r.arrow?r.arrow+' ':'')+(r.dir_text?r.dir_text+' ':'')+r.change)+'</span></div>').join('');
    }}
    const contrib=b.bidrag||{{}};
    const up=rows(contrib.up,'ny-fk-br');
    const down=rows(contrib.down,'ny-fk-br');
    const fk=b.forklaring||{{}};
    const expl='<div class="ny-fk-tag">'+esc(fk.label||'Kildens egen forklaring')+'</div><p class="ny-fk-txt">'+esc(fk.text||'')+(fk.attribution?'<span class="ny-fk-attr">'+esc(fk.attribution)+'</span>':'')+'</p>';
    const nv=b.nevnt||{{}};
    let nevnt='';
    if(!nv.hidden&&((nv.sectors||[]).length||(nv.exposures||[]).length)){{
      const sec=(nv.sectors||[]).map(s=>'<div class="ny-fk-nv"><span>'+esc(s.detail||s.name)+'</span></div>').join('');
      const exp=(nv.exposures||[]).map(e=>{{
        const lab=esc(e.ticker||'')+' '+esc(e.share_label||'')+' '+esc(e.report_date||'');
        const href=e.report_url?'<a class="ny-fk-src" href="'+esc(e.report_url)+'" target="_blank" rel="noopener noreferrer">'+lab+'</a>':lab;
        return '<div class="ny-fk-nv">'+href+'</div>';
      }}).join('');
      nevnt='<h3 class="ny-fk-h">Nevnt i kilden</h3>'+sec+exp;
    }}
    return '<p class="ny-fk-note">'+esc(c.note||'Forklaring fra kildene, ikke en prognose')+'</p>'
      +'<h3 class="ny-fk-h">Tallet</h3><div class="ny-fk-tall">'+tall+'</div>'+src
      +'<h3 class="ny-fk-h">Hva drar opp og ned</h3><p class="ny-fk-h">Største bidrag</p>'+up+'<p class="ny-fk-h">Største fall</p>'+down
      +'<h3 class="ny-fk-h">Kildens forklaring</h3>'+expl
      +nevnt;
  }}
  function isWide(){{ return window.matchMedia && window.matchMedia('(min-width:1280px)').matches; }}
  function closeForklaring(){{
    const sh=document.getElementById('ny-fk-sheet');
    const bg=document.getElementById('ny-fk-bg');
    if(sh) sh.hidden=true;
    if(bg) bg.hidden=true;
    document.querySelectorAll('.ny-fkort.open').forEach(el=>el.classList.remove('open'));
  }}
  function openForklaring(btn){{
    const inner=kortInner(kort);
    if(!inner) return;
    if(isWide()){{
      closeForklaring();
      const box=btn.parentElement && btn.parentElement.querySelector('.ny-fkort');
      if(box){{ box.innerHTML=inner; box.classList.add('open'); box.hidden=false; }}
      return;
    }}
    document.querySelectorAll('.ny-fkort.open').forEach(el=>el.classList.remove('open'));
    const sh=document.getElementById('ny-fk-sheet');
    const bg=document.getElementById('ny-fk-bg');
    const body=document.getElementById('ny-fk-sheet-body');
    if(body) body.innerHTML=inner;
    if(sh) sh.hidden=false;
    if(bg) bg.hidden=false;
  }}
  function setSheet(open){{
    if(!sheet) return;
    const wasOpen=!sheet.hidden;
    sheet.hidden=!open; if(sheetBg) sheetBg.hidden=!open;
    if(kbtn) kbtn.setAttribute('aria-expanded',open?'true':'false');
    if(!open && wasOpen && kbtn) kbtn.focus();
  }}
  function renderKilder(into){{
    if(!into) return;
    const srcs=data.sources||[];
    into.innerHTML=srcs.map(s=>{{
      const down=s.status==='kilde nede';
      const st=down?'kilde nede':(s.last_updated||'');
      const checked=off[s.id]?'':' checked';
      return '<label class="ny-ks'+(down?' down':'')+'"><input type="checkbox" data-sid="'+esc(s.id)+'"'+checked+'><span class="ny-kn">'+esc(s.name)+(s.paywall?' 🔒':'')+'</span><span class="ny-kst">'+esc(st)+'</span></label>';
    }}).join('');
    into.querySelectorAll('input[data-sid]').forEach(inp=>{{
      inp.addEventListener('change',()=>{{
        if(inp.checked) delete off[inp.dataset.sid]; else off[inp.dataset.sid]=1;
        try{{ localStorage.setItem(LS,JSON.stringify(off)); }}catch(e){{}}
        renderKilder(sheetRows); renderKilder(colRows); renderList();
      }});
    }});
  }}
  function renderList(){{
    const q=(qEl&&qEl.value||'').trim().toLowerCase();
    const srcs=data.sources||[];
    const allDown=srcs.length>0&&srcs.every(s=>s.status==='kilde nede');
    const items=(data.items||[]).filter(it=>inTab(it,tab)&&!off[it.source_id]&&(!q||(it.title||'').toLowerCase().includes(q)||(it.source||'').toLowerCase().includes(q)||(it.issuer||'').toLowerCase().includes(q)));
    if(kbtn) kbtn.textContent='Kilder ('+srcs.length+')';
    if(!items.length){{
      if(q) list.innerHTML='<div class="ny-empty">Ingen saker matcher «'+esc(qEl.value.trim())+'»</div>';
      else if(allDown) {{
        const hm=data.generated_at_utc?osloHm(new Date(data.generated_at_utc)):(upd.textContent.replace(/^Oppdatert\\s/,'' )||'--:--');
        list.innerHTML='<div class="ny-empty">Ingen kilder svarer nå. Sist oppdatert '+esc(hm)+'.</div>';
      }} else list.innerHTML='';
      return;
    }}
    list.innerHTML=items.map(it=>{{
      const iss=(it.issuer||'').trim(); const chip=(iss&&iss!=='-')?'<span class="ny-chip">'+esc(iss)+'</span>':'';
      const lock=it.paywall?' 🔒':'';
      const row='<a class="ny-row" href="'+esc(it.url)+'" target="_blank" rel="noopener noreferrer"><span class="ny-time">'+esc(rowTime(it.published_utc))+'</span><span class="ny-body"><span class="ny-title">'+esc(it.title)+'</span><span class="ny-meta">'+chip+'<span class="ny-src">'+esc(it.source)+lock+'</span></span></span></a>';
      if(itemMatchesKort(it,kort)){{
        return '<div class="ny-item">'+row+'<button type="button" class="ny-fkbtn" aria-haspopup="dialog">Hva betyr dette?</button><div class="ny-fkort" hidden></div></div>';
      }}
      return '<div class="ny-item">'+row+'</div>';
    }}).join('');
    list.querySelectorAll('.ny-fkbtn').forEach(btn=>{{
      btn.addEventListener('click',e=>{{ e.preventDefault(); e.stopPropagation(); openForklaring(btn); }});
    }});
  }}
  function apply(d){{
    data=d||{{items:[],sources:[]}};
    if(data.generated_at_utc){{
      const dte=new Date(data.generated_at_utc);
      if(!isNaN(dte)) upd.textContent='Oppdatert '+osloHm(dte);
    }} else if(data.generated_at_oslo){{
      const m=String(data.generated_at_oslo).match(/(\\d{{2}}):(\\d{{2}})/);
      if(m) upd.textContent='Oppdatert '+m[1]+':'+m[2];
    }}
    renderKilder(sheetRows); renderKilder(colRows); renderList();
  }}
  function fetchJson(url){{
    return fetch(url+(url.includes('?')?'&':'?')+'t='+Date.now(),{{cache:'no-store'}}).then(r=>{{
      if(!r.ok) throw new Error(String(r.status));
      return r.json();
    }});
  }}
  function loadKort(){{
    if(!RAWK) return Promise.resolve(null);
    return fetchJson(RAWK).catch(()=>FBK?fetchJson(FBK):Promise.reject()).catch(()=>null);
  }}
  Promise.all([fetchJson(RAW).catch(()=>fetchJson(FB)), loadKort()]).then(([d,k])=>{{
    kort=k&&k.ok&&!k.hide?k:null;
    apply(d);
  }}).catch(()=>{{
    upd.textContent='Oppdatert --:--';
    list.innerHTML='<div class="ny-empty">Ingen kilder svarer nå. Sist oppdatert --:--.</div>';
  }});
  document.querySelectorAll('.ny-tab').forEach(btn=>{{
    btn.addEventListener('click',()=>{{
      tab=btn.getAttribute('data-tab');
      document.querySelectorAll('.ny-tab').forEach(b=>{{
        const on=b.getAttribute('data-tab')===tab;
        b.classList.toggle('on',on);
        b.setAttribute('aria-selected',on?'true':'false');
      }});
      renderList();
    }});
  }});
  if(qEl) qEl.addEventListener('input',renderList);
  if(kbtn) kbtn.addEventListener('click',()=>setSheet(sheet.hidden));
  const slukk=document.getElementById('ny-slukk');
  if(slukk) slukk.addEventListener('click',()=>setSheet(false));
  if(sheetBg) sheetBg.addEventListener('click',()=>setSheet(false));
  const fkSlukk=document.getElementById('ny-fk-slukk');
  const fkBg=document.getElementById('ny-fk-bg');
  if(fkSlukk) fkSlukk.addEventListener('click',()=>closeForklaring());
  if(fkBg) fkBg.addEventListener('click',()=>closeForklaring());
  document.addEventListener('keydown',e=>{{ if(e.key==='Escape'){{ setSheet(false); closeForklaring(); }} }});
}})();
</script>
"""


def copy_json(site: Path, src: Path | None = None) -> Path | None:
    """Copy logs/nyheter.json into the built site as the runtime fallback."""
    from .nyheter import OUT_PATH
    src = src or OUT_PATH
    if not src.exists():
        return None
    dest = Path(site) / "data" / "nyheter.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    from .nbs_industriprofitt import OUT_PATH as KORT_OUT
    if KORT_OUT.exists():
        kdest = Path(site) / "data" / "nbs_industriprofitt.json"
        kdest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(KORT_OUT, kdest)
    return dest
