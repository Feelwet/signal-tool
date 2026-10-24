"""Oslo-sektorer (eksperimentell): målbare drivere + kandidater screenet med AnalBots CLEAR/FLAG-regler.

Ingen «Kjøp»: CLEAR betyr bare at alle fem nøkkeltall-regler holder i siste tilgjengelige data.
Manglende tall => FLAG på den regelen (vi finner ikke opp tall).
Fundamentaldata hentes med yfinance og lagres i signaltool/sector_fundamentals.json
(oppdater: python3 -m signaltool.sectors).
"""
from __future__ import annotations
import html
import json
from datetime import date
from pathlib import Path

FUND_PATH = Path(__file__).with_name("sector_fundamentals.json")


def _E(x):
    return html.escape("" if x is None else str(x))


def _d(name, source, url, how):
    return {"name": name, "source": source, "url": url, "how": how}


SECTORS: dict[str, dict] = {
    "energi": dict(
        name="Energi / olje og gass", file="sektor_energi",
        drivers=[_d("Brent-pris (USD/fat)", "ICE via Yahoo (BZ=F)", "https://finance.yahoo.com/quote/BZ%3DF", "Månedssnitt og endring 12 mnd."),
                 _d("Gasspris Europa (TTF, EUR/MWh)", "ICE Endex", "https://www.theice.com/products/27996665/Dutch-TTF-Gas-Futures", "Front-måned, endring 12 mnd."),
                 _d("Investeringer på sokkelen (mrd NOK)", "SSB investeringsundersøkelse olje og gass", "https://www.ssb.no/energi-og-industri/olje-og-gass/statistikk/investeringar-i-olje-og-gassverksemd-industri-og-energiforsyning", "Kvartalsvis anslag for neste år vs. i år.")],
        prose=("Inntektene til produsentene følger olje- og gasspris nesten direkte. Leverandørene (rigg, subsea, service) følger heller "
               "investeringene på sokkelen, som henger etter prisene med 1–2 år. Skatteregimet (78 % særskatt) gjør at staten tar mesteparten av en prisoppgang."),
        tickers=["EQNR.OL", "AKRBP.OL", "VAR.OL", "DNO.OL", "OKEA.OL", "SUBC.OL", "TGS.OL", "AKSO.OL", "BWO.OL"]),
    "sjomat": dict(
        name="Sjømat", file="sektor_sjomat",
        drivers=[_d("Laksepris (NOK/kg)", "SSB eksportpris fersk laks, uke", "https://www.ssb.no/jord-skog-jakt-og-fiskeri/fiske/statistikk/eksport-av-laks", "Ukespris vs. samme uke i fjor."),
                 _d("Eksportvolum laks (tonn)", "Sjømatrådet", "https://seafood.no/markedsinnsikt/", "Månedlig volum, endring 12 mnd."),
                 _d("EURNOK", "Norges Bank", "https://www.norges-bank.no/tema/Statistikk/Valutakurser/", "Svakere krone = høyere pris i NOK.")],
        prose=("Lakseprisen bestemmes av tilbud: biologi (lus, dødelighet) og konsesjoner begrenser veksten i volum. "
               "Grunnrenteskatt (25 %) siden 2023 og trafikklyssystemet styrer hvor mye selskapene kan vokse i Norge."),
        tickers=["MOWI.OL", "SALM.OL", "LSG.OL", "GSF.OL", "BAKKA.OL", "AUSS.OL", "NRS.OL"]),
    "shipping": dict(
        name="Shipping", file="sektor_shipping",
        drivers=[_d("Baltic Dry Index", "Baltic Exchange", "https://www.balticexchange.com/", "Daglig indeks, 30-dagers snitt."),
                 _d("Tankrater (VLCC/MR, USD/dag)", "Clarksons / selskapenes kvartalsrapporter", "https://www.clarksons.com/", "Oppnådde rater i kvartalsrapport vs. forrige kvartal."),
                 _d("Ordrebok i % av flåten", "Clarksons / selskapspresentasjoner", "https://www.clarksons.com/", "Høy ordrebok = mer tonnasje om 2–3 år = lavere rater.")],
        prose=("Ratene settes av forholdet mellom etterspørsel (tonn × distanse) og flåtestørrelse. Krig, sanksjoner og omveier (Suez/Rødehavet) øker distansen. "
               "Inntjeningen er svært syklisk; høy utbytte i gode år er ikke et tegn på varig vekst."),
        tickers=["FRO.OL", "HAFNI.OL", "WAWI.OL", "MPCC.OL", "BWLPG.OL", "HAUTO.OL", "OET.OL", "2020.OL"]),
    "forsvar": dict(
        name="Forsvar", file="sektor_forsvar",
        drivers=[_d("NATO-landenes forsvarsutgifter (% av BNP)", "NATO Defence Expenditure", "https://www.nato.int/cps/en/natohq/topics_49198.htm", "Årlig tall; mål 2 % → 3,5 %."),
                 _d("Norsk forsvarsbudsjett (mrd NOK)", "Regjeringen, Prop. 1 S (FD)", "https://www.regjeringen.no/no/dep/fd/", "Vedtatt budsjett vs. i fjor, langtidsplanen."),
                 _d("Ordrereserve", "Selskapenes kvartalsrapporter / Newsweb", "https://newsweb.oslobors.no/", "Ordrereserve vs. 12 mnd. siden.")],
        prose=("Etterspørselen kommer fra statsbudsjetter, som økte etter 2022. Kontrakter er lange og kommer i klumper, så ordrereserven sier mer enn ett kvartal. "
               "Mye av økningen kan allerede være priset inn. Se også temakartet Forsvar."),
        tickers=["KOG.OL", "KIT.OL", "NORBT.OL", "NTI.OL"]),
    "bank": dict(
        name="Bank og finans", file="sektor_bank",
        drivers=[_d("Styringsrenten", "Norges Bank", "https://www.norges-bank.no/tema/pengepolitikk/Styringsrenten/", "Nivå og rentebane fra siste pengepolitiske rapport."),
                 _d("Kredittvekst (K2)", "SSB", "https://www.ssb.no/bank-og-finansmarked/finansinstitusjonar-og-andre-finansielle-foretak/statistikk/kredittindikatoren", "12-måneders vekst."),
                 _d("Tap på utlån / mislighold", "Finanstilsynet, bankenes rapporter", "https://www.finanstilsynet.no/", "Tap i % av utlån per kvartal.")],
        prose=("Bankene tjener på forskjellen mellom utlåns- og innskuddsrente, som øker når styringsrenten er høy. Det motsatte gjelder når renten kuttes. "
               "Kredittap øker ved arbeidsledighet."),
        tickers=["DNB.OL", "STB.OL", "GJF.OL", "SB1NO.OL", "MING.OL", "NONG.OL", "SPOL.OL", "PROT.OL"]),
    "industri": dict(
        name="Industri og teknologi", file="sektor_industri",
        drivers=[_d("Innkjøpssjefsindeks (PMI) Europa/Norge", "S&P Global / NIMA", "https://www.pmi.spglobal.com/", "Månedlig, over/under 50."),
                 _d("Halvlederomsetning", "SIA (Semiconductor Industry Association)", "https://www.semiconductors.org/", "Global omsetning, 3-mnd snitt vs. i fjor."),
                 _d("Ordreinngang i industrien", "SSB", "https://www.ssb.no/energi-og-industri/industri/statistikk/ordrestatistikk", "Kvartalsvis indeks.")],
        prose=("Kontraktsprodusenter og teknologiselskaper følger investeringssyklusen i industri, elektronikk og forsvar. "
               "Lagernedbygging hos kunder gir svingninger selv når langsiktig etterspørsel er stabil."),
        tickers=["KIT.OL", "NOD.OL", "TOM.OL", "AKER.OL", "VEI.OL", "AFG.OL", "SCATC.OL"]),
    "materialer": dict(
        name="Materialer / metaller", file="sektor_materialer",
        drivers=[_d("Aluminiumspris (USD/tonn)", "LME", "https://www.lme.com/en/metals/non-ferrous/lme-aluminium", "Månedssnitt, endring 12 mnd."),
                 _d("Strømpris Norden (NOK/MWh)", "Nord Pool", "https://www.nordpoolgroup.com/", "Systempris; kostnad for kraftkrevende industri."),
                 _d("Gjødselpris (urea)", "Verdensbanken Pink Sheet", "https://www.worldbank.org/en/research/commodity-markets", "Månedlig pris.")],
        prose=("Metall- og gjødselprodusenter tjener på differansen mellom produktpris og kostnad for energi og råvarer. "
               "Norske verk har billig vannkraft på lange kontrakter. Sjeldne jordarter: ingen notert produsent med omsetning på Oslo Børs per i dag (se USAR-diskusjonen)."),
        tickers=["NHY.OL", "YAR.OL", "ELK.OL", "BRG.OL"]),
}

RULES = [  # (key, kolonneoverskrift med grense, langtekst)
    ("growth", "Vekst >10 %/år", "Omsetningsvekst > 10 %/år (3 år)"),
    ("fcf", "FCF >0", "Positiv fri kontantstrøm"),
    ("roic", "ROIC >10 %", "ROIC > 10 % (grovt anslag)"),
    ("dilution", "Utvanning <3 %/år", "Aksjeøkning < 3 %/år"),
    ("debt", "Gjeld/EBITDA <3", "Netto gjeld / EBITDA < 3"),
]
BANK_RULES = [
    ("roe", "ROE >10 %", "Egenkapitalavkastning > 10 %"),
    ("cost_income", "Kost/inntekt <50 %", "Kostnad / inntekt < 50 %"),
    ("loan_loss", "Utlånstap <0,3 %", "Utlånstap < 0,3 % av utlån (kvartalsrapport)"),
    ("cet1", "CET1 ≥ krav+1pp", "Ren kjernekapital minst 1 pp over kravet (kvartalsrapport)"),
    ("dilution", "Utvanning <3 %/år", "Aksjeøkning < 3 %/år"),
]
QUARTERLY = {"loan_loss", "cet1"}
ROUGH = {"roic"}


def rules_for(key: str):
    return BANK_RULES if key == "bank" else RULES


def evaluate(f: dict | None, bank: bool = False) -> dict:
    """CLEAR bare hvis ALLE regler har tall OG består. Ett brudd => FAIL. Ellers manglende tall => MISSING.
    Returns {'status': 'CLEAR'|'FAIL'|'MISSING', 'failed', 'missing', 'checks'}."""
    f = f or {}
    def chk(v, ok):
        return None if v is None else bool(ok(v))
    if bank:
        cet1 = None if f.get("cet1") is None or f.get("cet1_req") is None else f["cet1"] - f["cet1_req"]
        checks = {
            "roe": chk(f.get("roe"), lambda v: v > 0.10),
            "cost_income": chk(f.get("cost_income"), lambda v: v < 0.50),
            "loan_loss": chk(f.get("loan_loss"), lambda v: v < 0.003),
            "cet1": chk(cet1, lambda v: v >= 0.01),
            "dilution": chk(f.get("shares_cagr3"), lambda v: v < 0.03),
        }
    else:
        nde = f.get("net_debt_ebitda")
        if nde is None and f.get("net_debt") is not None and f["net_debt"] <= 0:
            nde = 0.0                                     # netto kontanter: oppfyller gjeldsregelen
        checks = {
            "growth": chk(f.get("rev_cagr3"), lambda v: v > 0.10),
            "fcf": chk(f.get("fcf"), lambda v: v > 0),
            "roic": chk(f.get("roic"), lambda v: v > 0.10),
            "dilution": chk(f.get("shares_cagr3"), lambda v: v < 0.03),
            "debt": chk(nde, lambda v: v < 3),
        }
    failed = [k for k, v in checks.items() if v is False]
    missing = [k for k, v in checks.items() if v is None]
    status = "FAIL" if failed else ("MISSING" if missing else "CLEAR")
    return {"status": status, "failed": failed, "missing": missing, "checks": checks}


# ---------------- fetch (yfinance) ----------------
def _row(df, *names):
    for n in names:
        if df is not None and n in df.index:
            s = df.loc[n].dropna()
            if len(s):
                return s.sort_index()
    return None


def fetch_one(t: str) -> dict:
    import yfinance as yf
    tk = yf.Ticker(t)
    inc, cf, bs = tk.income_stmt, tk.cashflow, tk.balance_sheet
    out = {"ticker": t, "name": None}
    try:
        out["name"] = (tk.info or {}).get("shortName")
    except Exception:
        pass
    rev = _row(inc, "Total Revenue", "Operating Revenue")
    if rev is not None and len(rev) >= 4 and rev.iloc[-4] > 0 and rev.iloc[-1] > 0:
        out["rev_cagr3"] = float((rev.iloc[-1] / rev.iloc[-4]) ** (1 / 3) - 1)
    fcf = _row(cf, "Free Cash Flow")
    if fcf is not None:
        out["fcf"] = float(fcf.iloc[-1])
    ebit, tax_rate = _row(inc, "EBIT", "Operating Income"), _row(inc, "Tax Rate For Calcs")
    eq, debt, cash = _row(bs, "Stockholders Equity"), _row(bs, "Total Debt"), _row(bs, "Cash And Cash Equivalents")
    if ebit is not None and eq is not None:
        ic = float(eq.iloc[-1]) + (float(debt.iloc[-1]) if debt is not None else 0) - (float(cash.iloc[-1]) if cash is not None else 0)
        tr = float(tax_rate.iloc[-1]) if tax_rate is not None else 0.22
        if ic > 0:
            out["roic"] = float(ebit.iloc[-1]) * (1 - tr) / ic
    sh = _row(inc, "Diluted Average Shares", "Basic Average Shares")
    if sh is None:
        sh = _row(bs, "Ordinary Shares Number", "Share Issued")
    if sh is not None and len(sh) >= 2 and sh.iloc[0] > 0:
        n = min(3, len(sh) - 1)
        out["shares_cagr3"] = float((sh.iloc[-1] / sh.iloc[-1 - n]) ** (1 / n) - 1)
    ebitda = _row(inc, "EBITDA", "Normalized EBITDA")
    if debt is not None:
        nd = float(debt.iloc[-1]) - (float(cash.iloc[-1]) if cash is not None else 0)
        out["net_debt"] = nd
        if ebitda is not None and float(ebitda.iloc[-1]) > 0:
            out["net_debt_ebitda"] = nd / float(ebitda.iloc[-1])
    ni = _row(inc, "Net Income", "Net Income Common Stockholders")
    if ni is not None and eq is not None and float(eq.iloc[-1]) > 0:
        out["roe"] = float(ni.iloc[-1]) / float(eq.iloc[-1])
    opx = _row(inc, "Operating Expense", "Selling General And Administration")
    if opx is not None and rev is not None and float(rev.iloc[-1]) > 0 and t in SECTORS["bank"]["tickers"]:
        out["cost_income"] = float(opx.iloc[-1]) / float(rev.iloc[-1])
    if rev is not None:
        out["fy"] = str(rev.index[-1])[:10]
    return out


def fetch_all(path: Path = FUND_PATH) -> dict:
    tickers = sorted({t for S in SECTORS.values() for t in S["tickers"]})
    data = {}
    for t in tickers:
        try:
            data[t] = fetch_one(t)
        except Exception as ex:
            data[t] = {"ticker": t, "error": str(ex)[:120]}
    from datetime import datetime
    doc = {"asof": date.today().isoformat(), "fetched": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "Yahoo Finance via yfinance (årsregnskap)", "data": data}
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    return doc


def load(path: Path = FUND_PATH) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"asof": None, "data": {}}


# ---------------- html ----------------
DISCLAIMER = ("Eksperimentell skjerm-output: illustrerer eksponering mot sektoren, ikke investeringsråd. CLEAR ≠ Kjøp, og tema alene ≠ Kjøp. "
              "Reglene er ikke bakovertestet; de følges i en framovertest (listen frosset 24.10.2026).")
FORWARD_PATH = Path(__file__).resolve().parent.parent / "logs" / "sector_forward.json"
FORWARD_TXT = "Framovertest: Frosset 24.10, første måling jan 2027"
CSS = """<style>
.sb{display:inline-block;border-radius:3px;padding:1px 7px;font-size:.85em;font-weight:600;border:1px solid;white-space:nowrap;background:transparent}
.sb.clear{color:#5b9cff;border-color:#5b9cff}.sb.fail{color:#ff7b7b;border-color:#ff7b7b}.sb.miss{color:#aab;border:1px dashed #aab}
.ok{color:#5b9cff}.no{color:#ff7b7b}.na{color:#999}.rough{border-bottom:1px dotted;cursor:help}
.scards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.scard{display:block;text-decoration:none;color:inherit;border:1px solid #445;border-radius:6px;padding:12px}.scard:hover,.scard:focus{border-color:#5b9cff}
.flt{margin:8px 0}.flt button{margin:0 6px 6px 0;padding:3px 10px;border:1px solid #778;border-radius:3px;background:transparent;color:inherit;cursor:pointer;font:inherit}
.flt button[aria-pressed=true]{background:#5b9cff;border-color:#5b9cff;color:#0b0f17}
.src{font-size:.8em;color:#999}
.tscroll{overflow-x:auto;-webkit-overflow-scrolling:touch}.tscroll table{min-width:640px}
.tscroll td:first-child,.tscroll th:first-child{position:sticky;left:0;background:var(--card,#151a24);z-index:1}
</style>"""
FILTER_JS = """<script>document.querySelectorAll('.flt button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.flt button').forEach(x=>x.setAttribute('aria-pressed',x===b));
document.querySelectorAll('tr[data-st]').forEach(r=>r.style.display=(b.dataset.f==='all'||r.dataset.st===b.dataset.f)?'':'none')})</script>"""
LABEL = {"CLEAR": "◆ CLEAR", "FAIL": "✕ Består ikke", "MISSING": "? Mangler data"}
CLS = {"CLEAR": "clear", "FAIL": "fail", "MISSING": "miss"}


def _pct(v):
    return "–" if v is None else f"{v*100:.1f} %"


def _badge(st, extra=""):
    return f'<span class="sb {CLS[st]}">{LABEL[st]}{extra}</span>'


def _status_badge(r):
    if r["status"] == "FAIL":
        return _badge("FAIL", f' · {len(r["failed"])} brudd')
    if r["status"] == "MISSING":
        return _badge("MISSING", f' · {len(r["missing"])} mangler')
    return _badge("CLEAR")


def is_stale(asof: str | None, today: date | None = None) -> bool:
    """Eldre enn ett kvartal (92 dager)."""
    if not asof:
        return True
    try:
        return ((today or date.today()) - date.fromisoformat(asof[:10])).days > 92
    except ValueError:
        return True


def _value(k, f):
    if k == "debt":
        nde = f.get("net_debt_ebitda")
        if nde is None and f.get("net_debt") is not None and f["net_debt"] <= 0:
            return "netto kontanter"
        return None if nde is None else f"{nde:.1f}x"
    if k == "fcf":
        return None if f.get("fcf") is None else ("positiv" if f["fcf"] > 0 else "negativ")
    if k == "cet1":
        return None if f.get("cet1") is None or f.get("cet1_req") is None else f"{(f['cet1']-f['cet1_req'])*100:+.1f} pp"
    src = {"growth": "rev_cagr3", "dilution": "shares_cagr3", "loan_loss": "loan_loss"}.get(k, k)
    return None if f.get(src) is None else _pct(f[src])


def _cell(k, ok, f):
    v = _value(k, f)
    if ok is None:
        why = "kvartalsrapport" if k in QUARTERLY else "mangler data"
        return f'<td class="na">? {why}</td>'
    v = _E(v)
    if k in ROUGH:
        v = f'<span class="rough" tabindex="0" title="Grovt anslag: EBIT×(1−skatt) / (egenkapital + gjeld − kontanter), siste årsregnskap">≈ {v}</span>'
    return f'<td class="{"ok" if ok else "no"}">{"✓" if ok else "✕"} {v}</td>'


def sector_rows(key: str, fund: dict) -> list[dict]:
    d = (fund or {}).get("data", {})
    return [{"ticker": t, "name": (d.get(t) or {}).get("name") or "", "f": d.get(t) or {}, **evaluate(d.get(t), key == "bank")}
            for t in SECTORS[key]["tickers"]]


def counts(key: str, fund: dict) -> dict:
    r = sector_rows(key, fund)
    return {st: sum(x["status"] == st for x in r) for st in ("CLEAR", "FAIL", "MISSING")} | {"n": len(r)}


def clear_list(fund: dict) -> dict:
    return {k: [r["ticker"] for r in sector_rows(k, fund) if r["status"] == "CLEAR"] for k in SECTORS}


def freeze_forward(fund: dict, frozen: str = "2026-10-24", path: Path = FORWARD_PATH) -> dict:
    """Fryser CLEAR-listen én gang (skriver ikke over en eksisterende frysing)."""
    if path.exists():
        return json.loads(path.read_text())
    doc = {"frozen": frozen, "first_measurement": "2027-01", "benchmark": ["sektorsnitt", "OSEBX"],
           "data_asof": fund.get("asof"), "clear": clear_list(fund),
           "note": "Framovertest: listen er frosset og måles hvert kvartal mot sektorsnitt og OSEBX. Ikke bakovertestet."}
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    return doc


def _dsrc(x, asof):
    stale = ' · <b>⏱ Utdatert</b>' if is_stale(asof) else ""
    return f'<a href="{_E(x["url"])}">{_E(x["source"])}</a><div class="src">dato: {_E(asof or "–")}{stale}</div>'


def sector_html(key: str, fund: dict | None = None) -> str:
    fund = fund if fund is not None else load()
    S, R, asof = SECTORS[key], rules_for(key), fund.get("asof")
    dasof = S.get("drivers_asof", "2026-10-24")
    drv = "".join(f'<tr><td>{_E(x["name"])}</td><td>{_dsrc(x, dasof)}</td><td class="mut">{_E(x["how"])}</td></tr>' for x in S["drivers"])
    trs, rows_src = [], []
    for r in sector_rows(key, fund):
        f = r["f"]
        fy = f.get("fy")
        # årsregnskap: utdatert hvis regnskapsåret sluttet for mer enn ett år + ett kvartal siden
        old = bool(fy) and is_stale((date.fromisoformat(fy[:10]).replace(year=date.fromisoformat(fy[:10]).year + 1)).isoformat())
        src = f'Yahoo/yfinance, årsregnskap {_E(fy or "–")}' + (" · ⏱ Utdatert" if old or not fy else "")
        cells = "".join(_cell(k, r["checks"][k], f) for k, _, _ in R)
        rows_src.append(src)
        trs.append((r, cells, src))
    from collections import Counter
    common = Counter(rows_src).most_common(1)[0][0] if rows_src else ""
    trs = [f'<tr data-st="{r["status"]}"><td><b>{_E(r["ticker"])}</b><div class="src">{_E(r["name"])}</div>'
           + (f'<div class="src">{src}</div>' if src != common else "") + f'</td><td>{_status_badge(r)}</td>{cells}</tr>' for r, cells, src in trs]
    head = "".join(f'<th>{_E(h)}</th>' for _, h, _ in R)
    rules = "".join(f"<li>{_E(l)}</li>" for _, _, l in R)
    stale = " · <b>⏱ Utdatert</b>" if is_stale(asof) else ""
    bank_note = ('<p class="mut">Bank: ROIC, fri kontantstrøm og gjeld/EBITDA gir lite mening og er erstattet med bankregler. Vekstkrav gjelder ikke. '
                 'Utlånstap og CET1 må hentes fra kvartalsrapportene og står som «? Mangler data» inntil videre – da kan ingen bank bli CLEAR.</p>') if key == "bank" else ""
    flt = '<div class="flt" role="group" aria-label="Filter">' + "".join(
        f'<button data-f="{f}" aria-pressed="{str(f=="all").lower()}">{l}</button>' for f, l in
        [("all", "Alle"), ("CLEAR", "◆ CLEAR"), ("FAIL", "✕ Består ikke"), ("MISSING", "? Mangler data")]) + "</div>"
    return (f'{CSS}<div class="warnbox">{_E(DISCLAIMER)}</div><h1>Sektor: {_E(S["name"])}</h1>'
            f'<div class="card"><h2 style="margin-top:0">Hva driver sektoren</h2><p>{_E(S["prose"])}</p></div>'
            f'<div class="card tw"><h2 style="margin-top:0">Målbare drivere</h2><div class="tscroll"><table><tr><th>Driver</th><th>Kilde og dato</th><th>Slik måles den</th></tr>{drv}</table></div></div>'
            f'<div class="card tw"><h2 style="margin-top:0">Kandidater</h2><p class="mut">◆ CLEAR = alle reglene har tall og består:</p><ul>{rules}</ul>'
            f'<p class="mut">Ett brudd gir «✕ Består ikke». Mangler et tall (og ingen brudd), blir status «? Mangler data» – vi finner ikke opp tall. '
            f'Data: {_E(fund.get("source") or "–")}, hentet {_E(fund.get("fetched") or asof or "–")}{stale}. Ikke bakovertestet. Tema alene er ikke grunn til å kjøpe.</p>{bank_note}'
            f'<p><b>{_E(FORWARD_TXT)}</b> (mot sektorsnitt og OSEBX).</p>{flt}'
            f'<div class="tscroll"><table><tr><th>Selskap</th><th>Status</th>{head}</tr>{"".join(trs)}</table></div><p class="src">Kilde: {common}</p></div>{FILTER_JS}')


def index_html(fund: dict | None = None) -> str:
    fund = fund if fund is not None else load()
    cards = []
    for k, S in SECTORS.items():
        c = counts(k, fund)
        flag = ' <span class="sb miss">FLAG: n&lt;5</span>' if c["n"] < 5 else ""
        drv = "".join(f"<li>{_E(x['name'])}</li>" for x in S["drivers"])
        cards.append(f'<a class="scard" href="tema/{S["file"]}.html"><h3 style="margin:0 0 6px">{_E(S["name"])}</h3><ul class="mut">{drv}</ul>'
                     '<div>' + " ".join(_badge(st, f" {c[st]}") for st in ("CLEAR", "FAIL", "MISSING")) + '</div>'
                     f'<div class="src">n={c["n"]}{flag}</div></a>')
    stale = " · <b>⏱ Utdatert</b>" if is_stale(fund.get("asof")) else ""
    return (f'{CSS}<div class="warnbox">{_E(DISCLAIMER)}</div><h1>Oslo-sektorer</h1>'
            f'<p class="mut">Per sektor: hva som driver den, tre målbare drivere med kilde, og kandidater screenet med fem nøkkeltall-regler (egne regler for bank). '
            f'Nøkkeltall hentet {_E(fund.get("fetched") or fund.get("asof") or "–")}{stale}. {_E(FORWARD_TXT)}.</p>'
            f'<div class="scards">{"".join(cards)}</div>')


if __name__ == "__main__":
    doc = fetch_all()
    for k in SECTORS:
        print(k, counts(k, doc))
