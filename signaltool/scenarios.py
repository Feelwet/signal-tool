"""Bull / base / bear scenario per theme (for the exposed 'winners') + the key indicators to watch, with live values
pulled from the snapshot. Bull = the theme's escalation text, bear = de-escalation text (themes_no.py); base cases and
indicator choices are written here. Indicator values are only ever read from collected data - missing -> '–'."""
from __future__ import annotations

BASE = {
    "conflict_defense": "Krigen og opprustningen fortsetter uten store brudd: budsjettene øker gradvis, ordrer kommer som ventet. Aksjene følger inntjening mer enn overskrifter.",
    "mideast_energy": "Spenningen varer, men uten varig forsyningsbrudd. Brent holder en moderat risikopremie; tankrater høye, men volatile.",
    "sanctions_energy": "Sanksjonsregimet strammes gradvis til (nye pakker, skyggeflåte-listing), uten brå forsyningssjokk. Europeisk gass følger vær og lagernivå.",
    "shipping_chokepoints": "Omruting rundt Kapp det gode håp fortsetter; ratene stabiliseres på et høyere nivå enn før krisen, mens ny flåtekapasitet presser gradvis.",
    "tariffs_trade": "Toll brukes som forhandlingskort: kunngjøringer og utsettelser veksler. Beskyttede produsenter (stål/aluminium i USA) har støtte, eksportører mer usikkerhet.",
    "rare_earths_semis": "Eksportkontroller strammes stegvis på begge sider; AI-etterspørselen bærer halvlederkjeden. Taiwans månedstall viser om etterspørselen holder.",
    "elections_political": "Valg og politisk støy gir kortvarige utslag i valuta og lokale indekser, men endrer sjelden inntjeningen på kort sikt.",
    "nordic_arctic": "Gradvis økt forsvars- og infrastrukturfokus i nord; kontrakter kommer over år. Norsk sokkel og subsea drives mer av oljepris og investeringsnivå.",
    "food_agri": "Normale avlinger og handelsflyt; gjødselpriser følger gasspris. Geopolitikk gir bare kortvarige topper.",
    "risk_off_haven": "Moderat usikkerhet: gull og CHF holder seg godt, VIX på normale nivåer. Ingen panikk, men etterspørsel etter sikring.",
}

CHOKE_FOR = {"mideast_energy": ["chokepoint6"], "shipping_chokepoints": ["chokepoint4", "chokepoint1", "chokepoint7"],
             "sanctions_energy": ["chokepoint3"], "rare_earths_semis": ["chokepoint11"], "tariffs_trade": ["chokepoint5", "chokepoint2"]}
PRICE_FOR = {"conflict_defense": ["ITA", "KOG.OL"], "mideast_energy": ["BZ=F", "FRO"], "sanctions_energy": ["TTF=F", "EQNR.OL"],
             "shipping_chokepoints": ["BDRY", "ZIM"], "tariffs_trade": ["ALI=F", "HG=F"], "rare_earths_semis": ["SMH", "MP"],
             "elections_political": ["USDNOK=X", "FEZ"], "nordic_arctic": ["KOG.OL", "SUBC.OL"], "food_agri": ["ZW=F", "YAR.OL"],
             "risk_off_haven": ["GC=F", "^VIX"]}
POLICY_FOR = {"conflict_defense": ("OFAC", "EU"), "sanctions_energy": ("OFAC", "EU"), "mideast_energy": ("OFAC",),
              "tariffs_trade": ("USTR", "ITA"), "rare_earths_semis": ("BIS",)}


def _p(x, d=1):
    return "–" if x is None else f"{x*100:+.{d}f} %"


def indicators(t: dict, snap: dict) -> list[dict]:
    """[{label, value, watch, lean}] lean in {'bull','bear','nøytral'} = which scenario the reading leans to."""
    k, out = t["key"], []
    s = t.get("score") or 0
    out.append({"label": "Temascore (oppmerksomhet vs egen historikk)", "value": f"{s:.2f}",
                "watch": "≥ 2 = uvanlig høy oppmerksomhet (eskalering); < 0,5 = rolig", "lean": "bull" if s >= 2 else "bear" if s < 0.5 else "nøytral"})
    rows = {r["ticker"]: r for r in t.get("tickers", [])}
    for tk in PRICE_FOR.get(k, []):
        r = rows.get(tk)
        if r and r.get("ret_20d") is not None:
            v = r["ret_20d"]
            inv = tk in ("^VIX",) and False
            out.append({"label": f"{tk} kursutvikling 20 d (5 d)", "value": f"{_p(v)} ({_p(r.get('ret_5d'))})",
                        "watch": "stigende = markedet priser eskalering/vekst; fallende = nedtrapping", "lean": "bull" if v > 0.05 else "bear" if v < -0.05 else "nøytral"})
    for cp in CHOKE_FOR.get(k, []):
        c = (snap.get("chokepoints") or {}).get(cp)
        if c and c.get("alle"):
            a = c["alle"]
            lean = "bull" if (a.get("yoy") is not None and a["yoy"] <= -0.3) or (a.get("z90") is not None and a["z90"] <= -2) else "nøytral"
            if a.get("yoy") is not None and a["yoy"] >= 0.1 and k in ("shipping_chokepoints",) and cp != "chokepoint7":
                lean = "bear"
            out.append({"label": f"{c['name']}: skipspasseringer/dag (7 d snitt)", "value": f"{a.get('last7')} ({_p(a.get('yoy'), 0)} å/å, z={a.get('z90')})",
                        "watch": f"kraftig fall = forstyrrelse; normalisering = nedtrapping. Data t.o.m. {c.get('last_date')} (IMF PortWatch, ~1 uke forsinkelse)", "lean": lean})
    if k in ("mideast_energy", "sanctions_energy"):
        on = (snap.get("oil_nowcast") or {})
        for sid in ("WCESTUS1", "WDISTUS1"):
            v = on.get(sid)
            if v and v.get("dev_pct") is not None:
                out.append({"label": f"{v['label']} vs 5-årssnitt (uke {v.get('week')})", "value": f"{_p(v['dev_pct'])} ({v['last']} mill. fat)",
                            "watch": "under snitt = stramt fysisk marked (støtter pris); over = rikelig. Historisk svak prediktor (se metode)",
                            "lean": "bull" if v["dev_pct"] <= -0.05 else "bear" if v["dev_pct"] >= 0.05 else "nøytral"})
    if k in ("rare_earths_semis", "tariffs_trade"):
        tw = snap.get("taiwan_revenue") or {}
        lt = tw.get("latest") or {}
        if lt.get("basket") is not None:
            out.append({"label": f"Taiwan AI/halvleder-kurv omsetning å/å ({tw.get('month')})", "value": f"{_p(lt['basket'])} (bredde {_p(lt.get('breadth'), 0).replace('+', '')} av alle selskaper opp å/å)" if lt.get("breadth") is not None else _p(lt["basket"]),
                        "watch": "akselerasjon = sterk etterspørsel i forsyningskjeden; oppbremsing = svakere", "lean": "nøytral"})
    pol = POLICY_FOR.get(k)
    if pol:
        al = [a for a in snap.get("policy_alerts") or [] if a.get("hot") and any(p in a.get("kind", "") for p in pol)]
        out.append({"label": "Politikkdokumenter siste 10 d (" + "/".join(pol) + ")", "value": str(len(al)),
                    "watch": "nye eksportkontroller/sanksjoner/toll = eskalering i regelverket", "lean": "bull" if len(al) >= 5 else "nøytral"})
    pm = (t.get("polymarket") or [])[:1]
    if pm:
        m = pm[0]
        out.append({"label": "Prediksjonsmarked: " + m["question"][:90], "value": f"{(m.get('p_yes') or 0)*100:.0f} % ({(m.get('chg_1w') or 0)*100:+.1f} pp 1 uke)",
                    "watch": "store ukesendringer = markedet endrer syn; les spørsmålet (ja kan bety nedtrapping)", "lean": "nøytral"})
    return out


def scenario(t: dict, snap: dict) -> dict:
    ind = indicators(t, snap)
    n_bull, n_bear = sum(i["lean"] == "bull" for i in ind), sum(i["lean"] == "bear" for i in ind)
    lean = "bull" if n_bull > n_bear + 1 else "bear" if n_bear > n_bull + 1 else "base"
    return {"bull": t.get("escalation", ""), "base": BASE.get(t["key"], ""), "bear": t.get("deescalation", ""), "indicators": ind,
            "lean": lean, "n_bull": n_bull, "n_bear": n_bear}
