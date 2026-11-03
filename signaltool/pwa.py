"""PWA (UxBot/AnalBot 01.11, bindende): manifest, ikoner, service worker, iOS-meta og «Installer som app».
Data og HTML er alltid network-first; cache brukes bare som fallback uten nett, og da sier «Oppdatert …»-linjen
«Frakoblet, viser data fra {dato}» i #fdba74. Cache-versjonen er build-id, så ny deploy sletter gammel cache. Aldri stille gamle tall."""
from __future__ import annotations
import json
import shutil
from pathlib import Path

ICON_DIR = Path(__file__).with_name("pwa_icons")
ICONS = (("icon-192.png", 192, False), ("icon-512.png", 512, False), ("icon-maskable-512.png", 512, True), ("apple-touch-icon.png", 180, False))
BG, FG, THEME = "#111821", "#58a6ff", "#1c2430"
SCOPE = "/signal-tool/"
NAME, SHORT = "Signal-tool", "Signal"
INSTALL_SAFARI = "Trykk ⋯ eller Del i Safari, velg Del og så Legg til på Hjem-skjerm."
INSTALL_OTHER = "Åpne siden i Safari for å installere."
INSTALL_TIP = INSTALL_SAFARI
OFFLINE_TXT = "Frakoblet, viser kurser per {kurs} (hentet {hentet})"
OFFLINE_NOKD = "Frakoblet, viser data hentet {hentet}"


def kurs_date(snap) -> str:
    """Siste sluttkursdato i dataene (vanligste _ret.last blant tickerne; likt antall -> nyeste). '' når ukjent."""
    from collections import Counter
    c = Counter(str((e.get("_ret") or {}).get("last") or "")[:10] for e in (snap or {}).get("tickers") or [])
    c.pop("", None)
    return max(c.items(), key=lambda kv: (kv[1], kv[0]))[0] if c else ""


def make_icons(out: Path = ICON_DIR) -> None:
    """Enkel «G» i #58a6ff på #111821 (Pillow). Maskable: G innenfor midterste 60 % (sikker sone). Kjøres lokalt; PNG-ene committes."""
    from PIL import Image, ImageDraw, ImageFont
    out.mkdir(exist_ok=True)
    fonts = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]
    for fn, px, mask in ICONS:
        big = px * 4
        im = Image.new("RGB", (big, big), BG)
        d = ImageDraw.Draw(im)
        box = big * (0.60 if mask else 0.78)          # glyfens største side
        f = next((p for p in fonts if Path(p).exists()), None)
        size = int(box)
        font = ImageFont.truetype(f, size) if f else ImageFont.load_default()
        while True:
            l, t, r, b = d.textbbox((0, 0), "G", font=font)
            if max(r - l, b - t) <= box or size < 10:
                break
            size -= 4
            font = ImageFont.truetype(f, size)
        l, t, r, b = d.textbbox((0, 0), "G", font=font)
        d.text(((big - (r - l)) / 2 - l, (big - (b - t)) / 2 - t), "G", font=font, fill=FG)
        im.resize((px, px), Image.LANCZOS).save(out / fn, optimize=True)


def manifest() -> dict:
    return {"name": NAME, "short_name": SHORT, "id": SCOPE, "start_url": SCOPE, "scope": SCOPE, "display": "standalone",
            "background_color": BG, "theme_color": THEME, "lang": "no", "orientation": "portrait",
            "icons": [{"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                      {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                      {"src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}


SW = r"""/* Signal-tool service worker. Build: __BUILD__. HTML og data: network-first (cache bare uten nett). Appskall: cache-first. */
const V='st-__BUILD__',SHELL=__SHELL__;
self.addEventListener('install',e=>{e.waitUntil(caches.open(V).then(c=>Promise.all(SHELL.map(u=>c.add(new Request(u,{cache:'reload'})).catch(()=>0)))).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith('st-')&&k!==V).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
const isShell=u=>/\.(css|js|png|webmanifest)$/.test(u.pathname)&&!u.pathname.endsWith('/sw.js');
async function net(req){const c=await caches.open(V);try{const r=await fetch(req,{cache:'no-store'});if(r&&r.ok)c.put(req,r.clone());return r}
catch(err){const m=await c.match(req,{ignoreSearch:true});if(!m)throw err;
 if((m.headers.get('content-type')||'').includes('text/html')){const t=(await m.text()).replace('<html ','<html data-offline="1" ');
  return new Response(t,{headers:{'content-type':'text/html; charset=utf-8'}})}return m}}
self.addEventListener('fetch',e=>{const r=e.request,u=new URL(r.url);if(r.method!=='GET'||u.origin!==location.origin)return;
 if(isShell(u)){e.respondWith(caches.open(V).then(c=>c.match(r).then(m=>m||fetch(r).then(x=>{if(x.ok)c.put(r,x.clone());return x}))));return}
 e.respondWith(net(r))});
"""


def head(pre: str) -> str:
    return (f'<link rel="manifest" href="{pre}manifest.webmanifest"><link rel="apple-touch-icon" href="{pre}icons/apple-touch-icon.png">'
            f'<link rel="icon" type="image/png" sizes="192x192" href="{pre}icons/icon-192.png">'
            f'<meta name="theme-color" content="{THEME}"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">'
            f'<meta name="apple-mobile-web-app-title" content="{SHORT}"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">')


# Safe area (viewport-fit=cover): i nettleseren er env(...) 0, så høyder og avstander er uendret.
CSS = ("header.top{height:calc(48px + env(safe-area-inset-top,0px));min-height:calc(48px + env(safe-area-inset-top,0px));max-height:calc(48px + env(safe-area-inset-top,0px));"
       "padding-top:env(safe-area-inset-top,0px);padding-left:calc(4px + env(safe-area-inset-left,0px));padding-right:calc(12px + env(safe-area-inset-right,0px))}"
       ".side{padding-top:calc(16px + env(safe-area-inset-top,0px));padding-bottom:calc(16px + env(safe-area-inset-bottom,0px))}"
       "footer{padding-bottom:env(safe-area-inset-bottom,0px)}"
       "html[data-offline] .gen-line{color:#fdba74}"
       ".pwa-inst{margin:16px 0 4px;font-size:13px;line-height:18px;color:#94a3b8}.pwa-inst[hidden]{display:none}"
       ".pwa-inst button.pwa-go{color:#94a3b8;font:inherit;background:none;border:0;padding:0;min-height:32px;display:inline-flex;align-items:center;text-decoration:underline;cursor:pointer}"
       ".pwa-help{box-sizing:border-box;max-width:100%;margin:4px 0 0;padding:16px;font-size:13px;line-height:1.45;color:#cbd5e1;text-align:left;white-space:normal;overflow-wrap:break-word;background:#111821;border-radius:6px}.pwa-help[hidden]{display:none}"
       "@media(display-mode:standalone){.pwa-inst{display:none!important}}\n")


def install_html() -> str:
    """Lenke nederst på Oversikt. Skjult til JS vet at installering er mulig (beforeinstallprompt) eller at det er iPhone/iPad.
    iOS: trykk folder ut en tekstblokk rett under lenken (ingen popup)."""
    return ('<div class="pwa-inst" id="pwa-inst" hidden><button type="button" class="pwa-go" id="pwa-go" aria-expanded="false" aria-controls="pwa-help">Installer som app</button>'
            '<p class="pwa-help" id="pwa-help" hidden></p></div>')


def js(pre: str) -> str:
    """Registrer SW, frakoblet-linje, klient-side ferskhetsvarsel for markedsstripen (samme regel som mstrip.py), installer-lenke."""
    off = json.dumps(OFFLINE_TXT)
    sc = pre or "./"
    return ("<script>(()=>{const d=document,H=d.documentElement;"
            f"if('serviceWorker' in navigator)addEventListener('load',()=>navigator.serviceWorker.register('{pre}sw.js',{{scope:'{sc}'}}).catch(()=>0));"
            # frakoblet: siden kom fra cache (SW merker <html data-offline>); kursdato fra data, hentetid fra build
            "if(H.dataset.offline){const g=d.querySelector('header.top+p.gen');if(g){const h=g.dataset.hent||g.textContent.replace(/^Oppdatert\\s*/,'')||'ukjent tid';"
            f"g.textContent=g.dataset.kd?{json.dumps(OFFLINE_TXT)}.replace('{{kurs}}',g.dataset.kd).replace('{{hentet}}',h):{json.dumps(OFFLINE_NOKD)}.replace('{{hentet}}',h)}}}}"
            # ferskhet: Brent = siste handelsdag (UTC >= 23 -> i dag, ellers i går; helg tilbake), BTC = i går UTC
            "const day=86400000,iso=x=>new Date(x+'T00:00:00Z').getTime(),n=new Date(),u=Date.UTC(n.getUTCFullYear(),n.getUTCMonth(),n.getUTCDate());"
            "d.querySelectorAll('.ms-f[data-d]').forEach(f=>{if(f.querySelector('.ms-w'))return;let e;"
            "if(f.dataset.sym==='BTC-USD')e=u-day;else{e=n.getUTCHours()>=23?u:u-day;while([0,6].includes(new Date(e).getUTCDay()))e-=day}"
            "if(iso(f.dataset.d)<e){const s=f.querySelector('.ms-s');if(s){const w=d.createElement('div');w.className='ms-w';w.textContent='⚠ eldre kurs';"
            "w.setAttribute('aria-label','Kursen er eldre enn '+(f.dataset.sym==='BTC-USD'?'i går':'siste handelsdag'));s.after(w)}}});"
            # installer-lenke: aldri auto-popup, bare ved trykk
            "const box=d.getElementById('pwa-inst');if(!box)return;const sa=matchMedia('(display-mode: standalone)').matches||navigator.standalone;if(sa)return;"
            "const ios=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);let ev=null;"
            "if(ios){box.hidden=false;const g=d.getElementById('pwa-go'),hp=d.getElementById('pwa-help'),oth=/CriOS|FxiOS|EdgiOS|OPiOS|OPT\\/|GSA\\/|DuckDuckGo|YaBrowser|Brave/.test(navigator.userAgent);"
            f"hp.textContent=oth?{json.dumps(INSTALL_OTHER)}:{json.dumps(INSTALL_SAFARI)};"
            "g.addEventListener('click',e=>{e.stopPropagation();const o=hp.hidden;hp.hidden=!o;g.setAttribute('aria-expanded',o?'true':'false')})}"
            "addEventListener('beforeinstallprompt',e=>{e.preventDefault();ev=e;box.hidden=false});"
            "d.getElementById('pwa-go').addEventListener('click',async()=>{if(!ev)return;ev.prompt();try{await ev.userChoice}catch(x){}ev=null;box.hidden=true});"
            "addEventListener('appinstalled',()=>{box.hidden=true})})()</script>")


def write(site: Path, build_id: str) -> None:
    (site / "icons").mkdir(exist_ok=True)
    for fn, _, _ in ICONS:
        shutil.copyfile(ICON_DIR / fn, site / "icons" / fn)
    (site / "manifest.webmanifest").write_text(json.dumps(manifest(), ensure_ascii=False, indent=1))
    shell = ["./", "index.html", "tickere.html", "makro.html", "kalender.html", "oslo.html", "sektorer.html", "temaer.html", "metode.html", "portefolje.html", "style.css", "manifest.webmanifest"] + [f"icons/{fn}" for fn, _, _ in ICONS]
    (site / "sw.js").write_text(SW.replace("__BUILD__", build_id).replace("__SHELL__", json.dumps(shell)))


if __name__ == "__main__":
    make_icons()
