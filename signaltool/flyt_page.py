"""flyt.html – verdikjede/materialflyt (UxBot-oppsett, AnalBots datakrav)."""
from __future__ import annotations

import html as _html
import json
from pathlib import Path
from urllib.parse import quote

from .config import ROOT
from .flyt_schema import coverage, universe_tickers, scenario_chips, ticker_har_publisert_flyt

STATIC = Path(__file__).resolve().parent / "flyt_static"
LINK_CSS = (
    "a.flyt-l{position:relative;z-index:2;display:inline-flex;align-items:center;justify-content:center;"
    "min-width:44px;min-height:44px;padding:0 8px;font-size:13px;line-height:18px;color:var(--acc);text-decoration:none}"
    "p.flyt-jump{margin:8px 0}"
)

E = lambda x: _html.escape("" if x is None else str(x))
SITE = ROOT / "site"
FLYT = SITE / "flyt"
_PUB_CACHE = None

def _official_graph():
    global _PUB_CACHE
    if _PUB_CACHE is None:
        from .config import ROOT as _R
        n = __import__("json").loads((_R / "flyt" / "noder.json").read_text(encoding="utf-8"))
        k = __import__("json").loads((_R / "flyt" / "kanter.json").read_text(encoding="utf-8"))
        if isinstance(n, dict):
            n = n.get("noder") or n
        if isinstance(k, dict):
            k = k.get("kanter") or k
        _PUB_CACHE = (n, k)
    return _PUB_CACHE

def fokus_href(ticker: str, pre: str = "") -> str:
    return f"{pre}flyt.html?fokus={quote(str(ticker), safe='')}"


def link(ticker: str, pre: str = "", *, noder=None, kanter=None) -> str:
    """Synlig «Flyt»-lenke (min 44×44) bare ved minst én publisert kant. Ellers ingenting."""
    if noder is None or kanter is None:
        noder, kanter = _official_graph()
    if not ticker_har_publisert_flyt(ticker, noder, kanter):
        return ""
    return (f'<a class="flyt-l" href="{E(fokus_href(ticker, pre))}">Flyt</a>')


def jump(ticker: str, pre: str = "../") -> str:
    return f'<p class="flyt-jump">{link(ticker, pre)}</p>'


def _chips(scenarioer=None) -> str:
    """Bare scenarioer med minst én kildebelagt mekanismesetning får chip.

    Chip-raden ligger rett under topplinja (over scenen); vises når Hva hvis er aktivt.
    """
    btns = "".join(
        f'<button type="button" class="flyt-chip" data-scenario="{E(i)}" aria-pressed="false">{E(n)}</button>'
        for i, n in scenario_chips(scenarioer)
    )
    return (
        f'<div class="flyt-hvis-chips" id="flyt-hvis-chips" role="group" '
        f'aria-label="Hva hvis" hidden>{btns}</div>'
    )


def body_html(*, meta: dict | None = None) -> str:
    meta = meta or {}
    meta_json = json.dumps(meta, ensure_ascii=False)
    chips = _chips(meta.get("scenarioer"))
    cov = meta.get("coverage") or {}
    # A (runde 5): vis statuslinja bare når k ≥ 1; skjul ved k = 0.
    if cov.get("beregnet") and cov.get("statuslinje") and (cov.get("k") or 0) >= 1:
        status = f'<p class="flyt-status" id="flyt-status">{E(cov["statuslinje"])}</p>'
    else:
        status = '<p class="flyt-status" id="flyt-status" hidden></p>'
    return f"""
<div class="flyt" id="flyt-app">
  <div class="flyt-top" id="flyt-top">
    <label class="flyt-search"><span class="flyt-vh">Søk ticker, materiale eller land</span>
      <input id="flyt-q" type="search" placeholder="Søk ticker, materiale eller land" aria-label="Søk ticker, materiale eller land" autocomplete="off" list="flyt-q-list">
    </label>
    <datalist id="flyt-q-list"></datalist>
    <div class="flyt-toggle" role="group" aria-label="Visning">
      <button type="button" id="flyt-kart" class="on" aria-pressed="true">Kart</button>
      <button type="button" id="flyt-liste" aria-pressed="false">Liste</button>
    </div>
    <button type="button" id="flyt-hvis" aria-pressed="false">Hva hvis</button>
  </div>
  {chips}
  <div id="flyt-hvis-box" class="flyt-hvis" hidden>
    <div class="flyt-hvis-panel">
      <p class="flyt-hvis-lead">Forklaring fra kildene, ikke en prognose</p>
      <h2>Hva kildene sier</h2>
      <p class="flyt-etikett">Mekanisme ifølge kilden</p>
      <div id="flyt-hvis-tekst"></div>
      <div id="flyt-hvis-tall" class="flyt-hvis-tall"></div>
    </div>
  </div>
  <p class="flyt-disc">Undersøkelse og kontekst, ikke kjøpsanbefaling. Stiplet = estimat.</p>
  {status}
  <div class="flyt-crumb" id="flyt-crumb" hidden></div>
  <div class="flyt-desk" id="flyt-desk">
    <div class="flyt-stage-wrap" id="flyt-stage-wrap">
      <div id="flyt-scene" class="flyt-scene" role="img" aria-label="Flyt-kart"></div>
      <div class="flyt-labels" id="flyt-labels"></div>
      <div class="flyt-zoom">
        <button type="button" id="flyt-zoom-in" aria-label="Zoom inn">+</button>
        <button type="button" id="flyt-zoom-out" aria-label="Zoom ut">−</button>
        <button type="button" id="flyt-reset" aria-label="Tilbakestill">Tilbakestill</button>
      </div>
    </div>
    <aside id="flyt-panel" class="flyt-panel" hidden>
      <div class="flyt-panel-bar">
        <button type="button" class="flyt-sheet-handle" id="flyt-sheet-handle" aria-label="Utvid detaljer"></button>
        <button type="button" id="flyt-panel-close" aria-label="Lukk">Lukk</button>
      </div>
      <div id="flyt-panel-body"></div>
    </aside>
  </div>
  <div id="flyt-list" class="flyt-list" hidden></div>
</div>
<script type="application/json" id="flyt-meta">{meta_json}</script>
"""


def _attach_assets(page: str, pre: str = "") -> str:
    css = f'<link rel="stylesheet" href="{pre}flyt.css">'
    js = (f'<script type="module" src="{pre}flyt.js"></script>')
    if css not in page:
        page = page.replace("</head>", css + "</head>", 1)
    if "flyt.js" not in page:
        page = page.replace("</body>", js + "</body>", 1)
    return page


def meta_from(*, universe: list[str] | None = None, noder=None, kanter=None,
              scenarioer=None, data_base: str = "flyt", kurs_url: str = "data.json") -> dict:
    # N og k bare når univers og flyt-data kommer fra samme bygg.
    # Mangler ett av dem: coverage.beregnet = False, statuslinja skjules.
    if universe is not None:
        uni = list(universe)
        uni_ok = True
    else:
        uni = universe_tickers()
        uni_ok = bool(uni)
    cov = None
    if noder is not None and kanter is not None and uni_ok:
        cov = coverage(noder, kanter, uni)
        cov["beregnet"] = True
    else:
        cov = {"beregnet": False, "n": len(uni), "k": None, "statuslinje": ""}
    return {
        "universe": uni,
        "n": len(uni),
        "coverage": cov,
        "data_base": data_base,
        "kurs_url": kurs_url,
        "default_fokus": "NHY.OL",
        "scenarioer": scenarioer or [],
    }


def html(snap=None, *, universe: list[str] | None = None, noder=None, kanter=None,
         scenarioer=None, data_base: str = "flyt", kurs_url: str = "data.json", pre: str = "") -> str:
    from . import site as S
    meta = meta_from(universe=universe, noder=noder, kanter=kanter, scenarioer=scenarioer, data_base=data_base, kurs_url=kurs_url)
    page = S.page("Flyt", body_html(meta=meta), 0, snap)
    return _attach_assets(page, pre)


def copy_static(site: Path | None = None) -> None:
    """Kopier CSS, JS og vendoret Three.js til site/ (tåler at build() tømmer site/)."""
    import shutil
    site = Path(site or SITE)
    site.mkdir(parents=True, exist_ok=True)
    shutil.copy2(STATIC / "flyt.css", site / "flyt.css")
    shutil.copy2(STATIC / "flyt.js", site / "flyt.js")
    vend = site / "vendor"
    vend.mkdir(parents=True, exist_ok=True)
    for fn in ("three.module.min.js", "THREE_LICENSE.txt", "README.md"):
        shutil.copy2(STATIC / "vendor" / fn, vend / fn)
    (site / "flyt").mkdir(parents=True, exist_ok=True)
    src_rm = STATIC / "flyt_data_README.md"
    if src_rm.exists():
        shutil.copy2(src_rm, site / "flyt" / "README.md")


def write(site: Path | None = None, snap=None, **kw) -> Path:
    site = Path(site or SITE)
    copy_static(site)
    out = site / "flyt.html"
    if kw.get("noder") is None:
        from .flyt_build import publish_repo_flyt
        publish_repo_flyt(site / "flyt")
        if (site / "flyt" / "noder.json").exists():
            import json
            from .flyt_schema import universe_tickers
            noder = json.loads((site / "flyt" / "noder.json").read_text(encoding="utf-8"))
            kanter = json.loads((site / "flyt" / "kanter.json").read_text(encoding="utf-8")) if (site / "flyt" / "kanter.json").exists() else None
            sc_path = site / "flyt" / "scenarios.json"
            if not sc_path.exists():
                sc_path = site / "flyt" / "scenarioer.json"
            scenarioer = json.loads(sc_path.read_text(encoding="utf-8")) if sc_path.exists() else None
            kw.setdefault("noder", noder)
            kw.setdefault("kanter", kanter)
            kw.setdefault("scenarioer", scenarioer)
            kw.setdefault("universe", universe_tickers())
    out.write_text(html(snap, **kw), encoding="utf-8")
    return out


def prepare_preview(dest: Path, *, fixture: bool = False, snap=None) -> Path:
    """Bygg en lokal visning av flyt.html. fixture=True kopierer fiktive testdata til dest (aldri til site/)."""
    import shutil
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    from . import site as S
    from . import tabbar as TB
    (dest / "style.css").write_text(S.CSS + TB.CSS + LINK_CSS, encoding="utf-8")
    uni = noder = kanter = None
    data_base, kurs_url = "flyt", "data.json"
    if fixture:
        fx = ROOT / "tests" / "fixtures" / "flyt"
        (dest / "flyt").mkdir(exist_ok=True)
        for fn in ("noder.json", "kanter.json", "scenarioer.json"):
            shutil.copy2(fx / fn, dest / "flyt" / fn)
        if (fx / "data.json").exists():
            shutil.copy2(fx / "data.json", dest / "data.json")
        if (fx / "godkjent.csv").exists():
            shutil.copy2(fx / "godkjent.csv", dest / "flyt" / "godkjent.csv")
            from .flyt_build import apply_godkjent_file
            apply_godkjent_file(dest / "flyt", dest / "flyt" / "godkjent.csv")
        uni = universe_tickers(fx / "list_members.csv")
        # Dekning og meta skal bruke de samme filene som siden laster (etter godkjent.csv).
        noder = json.loads((dest / "flyt" / "noder.json").read_text(encoding="utf-8"))
        kanter = json.loads((dest / "flyt" / "kanter.json").read_text(encoding="utf-8"))
        scenarioer = json.loads((dest / "flyt" / "scenarioer.json").read_text(encoding="utf-8"))
    else:
        scenarioer = None
    write(dest, snap or {"generated": "2026-11-27 13:00"}, universe=uni, noder=noder, kanter=kanter,
          scenarioer=scenarioer, data_base=data_base, kurs_url=kurs_url)
    return dest / "flyt.html"
