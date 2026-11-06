"""Fanelinje nederst på mobil (≤768 px, UxBot 01.11). 1280 beholder toppmeny/sidemeny.
Fem faner: Oversikt, Tickere, Oslo, Signal-boka, Mer. «Mer» åpner bunnark med resten av sidene, så ingen side blir uoppnåelig."""
from html import escape as E

TABS = [("index.html", "Oversikt", "home"), ("tickere.html", "Tickere", "list"), ("oslo.html", "Oslo", "pin"),
        ("portefolje.html", "Signal-boka", "book")]
# Alle sider fra ☰ som ikke har egen fane + undersider/ankre som hadde egen lenke (Røde flagg, Treffrate, Kilder)
MORE = [("trender.html", "Trender"), ("om.html", "Om siden"), ("temaer.html", "Temaer"), ("sektorer.html", "Sektorer"), ("makro.html", "Makro"), ("kalender.html", "Kalender"),
        ("metode.html", "Metode"), ("tickere.html?filter=flagg", "Røde flagg Oslo"), ("metode.html#treffrate", "Treffrate"),
        ("kilder.html", "Kilder og metode")]
MORE_ON = {"trender.html", "om.html", "temaer.html", "sektorer.html", "makro.html", "kalender.html", "metode.html", "kilder.html"}

_P = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
ICON = {
    "home": f'<path {_P} d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
    "list": f'<path {_P} d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    "pin": f'<path {_P} d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle {_P} cx="12" cy="9.5" r="2.5"/>',
    "book": f'<path {_P} d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 5v16M8 7h7"/>',
    "more": f'<circle {_P} cx="5" cy="12" r="1.3"/><circle {_P} cx="12" cy="12" r="1.3"/><circle {_P} cx="19" cy="12" r="1.3"/>',
}


def _svg(k):
    return f'<svg class="tb-i" width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">{ICON[k]}</svg>'


def html(cur: str | None, pre: str) -> str:
    cur = (cur or "").split("?")[0]
    tabs = "".join(f'<a class="tb-t{" on" if h == cur else ""}" href="{pre}{h}"{" aria-current=page" if h == cur else ""}>{_svg(k)}<span>{E(l)}</span></a>'
                   for h, l, k in TABS)
    mon = cur in MORE_ON
    rows = "".join(f'<a class="ms-r{" on" if h == cur else ""}" href="{pre}{h}">{E(l)}</a>' for h, l in MORE)
    return (f'<nav class="tabbar" aria-label="Hovedmeny">{tabs}'
            f'<button type="button" class="tb-t tb-more{" on" if mon else ""}" id="tb-more" aria-expanded="false" aria-controls="more-sheet">{_svg("more")}<span>Mer</span></button></nav>'
            f'<div class="ms-bg" id="ms-bg" hidden></div><div class="more-sheet" id="more-sheet" role="dialog" aria-label="Flere sider" hidden>'
            f'<div class="ms-h">Flere sider</div>{rows}'
            '<button type="button" class="ms-r ms-b" data-folds="1">Åpne alle områder</button><button type="button" class="ms-r ms-b" data-folds="0">Lukk alle områder</button></div>')


CSS = """
.tabbar,.more-sheet,.ms-bg,.tm-chips{display:none}
@media(max-width:768px){
.side,.side-toggle,body.nav-open::after{display:none!important}
header.top{padding-left:calc(12px + env(safe-area-inset-left,0px))}
.tabbar{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:60;height:calc(56px + env(safe-area-inset-bottom,0px));padding:0 env(safe-area-inset-right,0px) env(safe-area-inset-bottom,0px) env(safe-area-inset-left,0px);box-sizing:border-box;background:#1c2430;border-top:1px solid #3b4757}
.tb-t{flex:1 1 0;min-width:64px;height:56px;min-height:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;color:#94a3b8!important;text-decoration:none!important;font:500 11px/14px system-ui,-apple-system,sans-serif;background:none;border:0;border-top:2px solid transparent;padding:0;margin:-1px 0 0;cursor:pointer;-webkit-tap-highlight-color:transparent}
.tb-t.on{color:#58a6ff!important;border-top-color:#58a6ff}.tb-t span{white-space:nowrap}.tb-i{width:22px;height:22px;flex:none}
body{padding-bottom:calc(72px + env(safe-area-inset-bottom,0px))!important}
.ms-bg{display:block;position:fixed;inset:0;z-index:58;background:rgba(0,0,0,.5)}.ms-bg[hidden]{display:none}
.more-sheet{display:block;position:fixed;left:0;right:0;bottom:calc(56px + env(safe-area-inset-bottom,0px));z-index:59;max-height:calc(100vh - 120px);overflow:auto;background:#1c2430;border-top:1px solid #3b4757;border-radius:12px 12px 0 0;padding:4px 0 8px}
.more-sheet[hidden]{display:none}
.ms-h{font-size:12px;line-height:16px;text-transform:uppercase;letter-spacing:.03em;color:#94a3b8;padding:10px 16px 6px}
.ms-r{display:flex;align-items:center;box-sizing:border-box;width:100%;height:48px;padding:0 16px;color:#e6edf3!important;text-decoration:none!important;font:400 15px/20px system-ui,-apple-system,sans-serif;background:none;border:0;border-top:1px solid #2b3442;text-align:left;cursor:pointer}
.ms-r.on{color:#58a6ff!important}.ms-b{color:#94a3b8!important;font-size:14px}
.tm-chips{display:flex;position:sticky;top:env(safe-area-inset-top,0px);z-index:20;height:40px;box-sizing:border-box;align-items:center;gap:6px;overflow-x:auto;overflow-y:hidden;margin:0 0 8px;padding:0 4px;max-width:100%;background:#111821;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.tm-chips::-webkit-scrollbar{display:none}
.tm-chips a{flex:none;height:32px;display:inline-flex;align-items:center;padding:0 10px;border-radius:16px;border:1px solid #3b4757;background:#1c2430;color:#cbd5e1!important;font-size:13px;text-decoration:none!important;white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis}
.pg-temaer tr.tm-hit td{background:rgba(88,166,255,.12)}
.pg-temaer tr[id^=tm-]{scroll-margin-top:56px}
}
"""

JS = ("<script>(()=>{const d=document,b=d.getElementById('tb-more'),s=d.getElementById('more-sheet'),g=d.getElementById('ms-bg');if(!b||!s)return;"
      "const set=o=>{s.hidden=!o;g.hidden=!o;b.setAttribute('aria-expanded',o?'true':'false')};"
      "b.addEventListener('click',e=>{e.stopPropagation();set(s.hidden)});g.addEventListener('click',()=>set(false));"
      "d.addEventListener('keydown',e=>{if(e.key==='Escape')set(false)});"
      "s.querySelectorAll('[data-folds]').forEach(x=>x.addEventListener('click',()=>{const o=x.dataset.folds==='1';d.querySelectorAll('details.fold').forEach(f=>f.open=o);set(false)}));"
      "s.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>set(false)));"
      # Temaer: klistret chip-rad, trykk hopper til temaet i tabellen
      "if(d.body.classList.contains('pg-temaer')){const rows=[...d.querySelectorAll('main table tr')].filter(r=>r.querySelector('a[href^=\"tema/\"]'));"
      "if(rows.length){const c=d.createElement('nav');c.className='tm-chips';c.setAttribute('aria-label','Hopp til tema');"
      "rows.forEach(r=>{const a=r.querySelector('a[href^=\"tema/\"]'),k=a.getAttribute('href').replace(/^tema\\/|\\.html$/g,'');r.id=r.id||'tm-'+k;"
      "const ch=d.createElement('a');ch.href='#'+r.id;ch.textContent=a.textContent.split(/ [–/]| og /)[0];ch.title=a.textContent;"
      "ch.addEventListener('click',e=>{e.preventDefault();rows.forEach(x=>x.classList.remove('tm-hit'));r.classList.add('tm-hit');r.scrollIntoView({block:'start',behavior:'smooth'})});c.appendChild(ch)});"
      "const h=d.querySelector('main h1');const m=h&&h.nextElementSibling&&h.nextElementSibling.classList.contains('pmeta')?h.nextElementSibling:h;(m||d.querySelector('main').firstChild).after(c)}}"
      "})()</script>")
