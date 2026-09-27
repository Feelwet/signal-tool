"""Geopolitical theme map.

Each theme links a class of geopolitical developments to the sectors, commodities and
example tickers most directly exposed, with the causal reasoning written out, plus the
matching rules the collectors use (keywords, GDELT countries / CAMEO event codes).

Tickers are *examples of exposure*, not recommendations. `.OL` = Oslo Børs.
GDELT countries are FIPS 10-4 codes (as used in ActionGeo_CountryCode).
CAMEO root codes: 13 threaten, 15 force posture, 16 reduce relations (163 = sanctions/embargo),
17 coerce, 18 assault, 19 fight, 20 mass violence.
"""
from __future__ import annotations
from dataclasses import dataclass, field

CONFLICT_ROOTS = ["15", "17", "18", "19", "20"]


@dataclass
class Theme:
    key: str
    name: str
    reasoning: str
    sectors: list[str]
    commodities: list[str]            # yfinance symbols
    tickers_us: list[str]
    tickers_ose: list[str]            # Oslo Børs
    tickers_other: list[str] = field(default_factory=list)
    losers: list[str] = field(default_factory=list)   # negatively exposed
    keywords: list[str] = field(default_factory=list) # lower-case, used on headlines / questions
    gdelt_countries: list[str] = field(default_factory=list)
    gdelt_roots: list[str] = field(default_factory=lambda: list(CONFLICT_ROOTS))
    url_keywords: list[str] = field(default_factory=list)  # substrings searched in GDELT source URLs
    trends_terms: list[str] = field(default_factory=list)  # max 5 for Google Trends
    sector_etf: str = "SPY"                                 # used for backtests / relative moves
    escalation: str = ""
    deescalation: str = ""
    risks: str = ""

    @property
    def all_tickers(self) -> list[str]:
        return list(dict.fromkeys(self.tickers_us + self.tickers_ose + self.tickers_other))


THEMES: list[Theme] = [
    Theme(
        key="conflict_defense",
        name="Europe/Russia conflict & defence spending",
        reasoning=("Escalation in Russia-Ukraine or wider NATO tension raises the odds of higher defence "
                   "budgets and ammunition/air-defence orders. Defence primes and European suppliers (incl. "
                   "Kongsberg, which makes NASAMS air defence and naval strike missiles) tend to re-rate on "
                   "procurement news; order books react with months of lag, prices react on headlines."),
        sectors=["Aerospace & defence", "Defence electronics", "Ammunition"],
        commodities=[],
        tickers_us=["LMT", "RTX", "NOC", "GD", "LHX", "ITA"],
        tickers_ose=["KOG.OL", "KIT.OL"],
        tickers_other=["RHM.DE", "SAAB-B.ST", "BA.L"],
        losers=[],
        keywords=["ukraine", "russia", "nato", "missile", "drone", "air defense", "air defence", "artillery",
                  "defence spending", "defense spending", "kremlin", "zelensky", "putin", "rearm"],
        gdelt_countries=["UP", "RS", "BO", "PL", "EN", "LG", "LH", "FI"],
        url_keywords=["ukrain", "russia", "nato", "missile", "drone", "kremlin"],
        trends_terms=["NATO", "Ukraine war", "missile attack", "defense stocks"],
        sector_etf="ITA",
        escalation="Defence names up; European defence usually more sensitive than US primes. NOK can weaken on risk-off.",
        deescalation="Ceasefire headlines have historically caused sharp one-day drops in European defence (profit taking).",
        risks="Much of the rearmament story is already priced (high multiples); budgets take years to convert into orders.",
    ),
    Theme(
        key="mideast_energy",
        name="Middle East / Iran / Gulf oil supply risk",
        reasoning=("Around a fifth of world oil and a large share of LNG transits the Strait of Hormuz. "
                   "Military escalation involving Iran, Israel or Gulf states raises a risk premium in Brent, "
                   "benefits producers outside the region (Equinor, Aker BP, Vår Energi, US majors) and tanker "
                   "owners (longer routes, higher rates), and hurts fuel-heavy airlines."),
        sectors=["Oil & gas producers", "Tankers", "Oil services"],
        commodities=["BZ=F", "CL=F"],
        tickers_us=["XLE", "XOM", "CVX", "FRO", "DHT", "STNG"],
        tickers_ose=["EQNR.OL", "AKRBP.OL", "VAR.OL", "HAFNI.OL"],
        losers=["JETS", "NAS.OL"],
        keywords=["iran", "israel", "hormuz", "gulf", "saudi", "tehran", "hezbollah", "gaza", "iraq", "opec",
                  "oil price", "brent", "tanker", "blockade"],
        gdelt_countries=["IR", "IS", "SA", "IZ", "LE", "SY", "TC", "MU", "QA", "KU", "GZ", "WE"],
        url_keywords=["iran", "israel", "hormuz", "opec", "tehran", "hezbollah"],
        trends_terms=["Iran", "Strait of Hormuz", "oil price", "OPEC"],
        sector_etf="XLE",
        escalation="Brent up, tankers up, European E&Ps up, airlines down. Watch Polymarket ceasefire/blockade markets.",
        deescalation="Risk premium unwinds fast: oil and tanker stocks can give back weeks of gains in days.",
        risks="OPEC spare capacity and SPR releases cap spikes; the market may already price a large premium.",
    ),
    Theme(
        key="sanctions_energy",
        name="Sanctions, Russian energy & European gas",
        reasoning=("New sanctions on Russian oil/gas, price-cap enforcement against the 'shadow fleet', or "
                   "secondary sanctions on buyers tighten supply and reshuffle trade routes. Norway is Europe's "
                   "largest pipeline gas supplier, so Equinor benefits from higher European gas prices; "
                   "compliant tanker owners benefit from longer voyages."),
        sectors=["Gas producers", "LNG", "Tankers"],
        commodities=["TTF=F", "NG=F", "BZ=F"],
        tickers_us=["LNG", "FRO", "DHT"],
        tickers_ose=["EQNR.OL", "OKEA.OL", "HAFNI.OL", "FRO.OL"],
        keywords=["sanction", "price cap", "shadow fleet", "embargo", "ofac", "gazprom", "rosneft", "lng",
                  "gas price", "pipeline", "secondary sanctions"],
        gdelt_countries=["RS", "IR", "VE", "BO"],
        gdelt_roots=["16", "17"],
        url_keywords=["sanction", "embargo", "price-cap", "shadow-fleet"],
        trends_terms=["sanctions", "gas price", "shadow fleet"],
        sector_etf="XLE",
        escalation="European gas and Equinor up; product tankers up.",
        deescalation="Sanctions relief (e.g. a peace deal) would push gas prices and Equinor lower.",
        risks="Sanctions are often poorly enforced; mild winters and full storage dominate gas prices.",
    ),
    Theme(
        key="shipping_chokepoints",
        name="Shipping chokepoints (Red Sea, Suez, Taiwan Strait, Panama)",
        reasoning=("Attacks or blockades at chokepoints force rerouting (e.g. around the Cape), absorbing "
                   "fleet capacity and lifting freight rates. Container lines, car carriers and tanker owners "
                   "earn more; Oslo Børs has an unusually deep shipping sector (Hafnia, Wallenius Wilhelmsen, "
                   "Höegh Autoliners, MPC Container, BW LPG)."),
        sectors=["Container shipping", "Car carriers", "Tankers", "LPG shipping"],
        commodities=[],
        tickers_us=["ZIM", "BDRY", "FRO"],
        tickers_ose=["MPCC.OL", "WAWI.OL", "HAUTO.OL", "BWLPG.OL", "HAFNI.OL"],
        tickers_other=["MAERSK-B.CO", "HLAG.DE"],
        keywords=["red sea", "houthi", "suez", "shipping", "freight", "container ship", "chokepoint",
                  "panama canal", "strait", "vessel attacked", "rerout", "bab el-mandeb"],
        gdelt_countries=["YM", "EG", "DJ", "ER", "SO", "PM"],
        url_keywords=["houthi", "red-sea", "suez", "shipping", "freight", "vessel"],
        trends_terms=["Houthi", "Red Sea shipping", "Suez Canal", "freight rates"],
        sector_etf="BDRY",
        escalation="Freight rates and shipping equities up (often within days).",
        deescalation="Reopening of Suez/Red Sea routes releases capacity -> rates and shipping stocks fall.",
        risks="Newbuild deliveries create overcapacity; high dividends can hide falling earnings.",
    ),
    Theme(
        key="tariffs_trade",
        name="Tariffs, trade wars & export controls",
        reasoning=("New tariffs protect domestic producers (US steel/aluminium) and hurt exporters and "
                   "importers exposed to the targeted trade flow. Norwegian exporters (salmon, aluminium, "
                   "fertiliser) are exposed to US/China/EU trade policy; retaliation cycles move FX too."),
        sectors=["Steel & aluminium", "Seafood exporters", "Retail/importers", "Autos"],
        commodities=["ALI=F", "HG=F"],
        tickers_us=["NUE", "STLD", "CLF", "AA", "FXI", "EWW"],
        tickers_ose=["NHY.OL", "MOWI.OL", "SALM.OL"],
        losers=["XRT"],
        keywords=["tariff", "trade war", "export control", "customs duty", "trade deal", "retaliat", "import tax",
                  "section 232", "dumping"],
        gdelt_countries=["CH", "US", "CA", "MX"],
        gdelt_roots=["16", "13"],
        url_keywords=["tariff", "trade-war", "trade-deal", "export-control"],
        trends_terms=["tariffs", "trade war", "trade deal"],
        sector_etf="XLI",
        escalation="Protected producers up, targeted exporters and broad market down; USD often up.",
        deescalation="Trade deals lift exporters and cyclical/EM ETFs.",
        risks="Tariff announcements are frequently delayed, diluted or reversed; headline noise is extreme.",
    ),
    Theme(
        key="rare_earths_semis",
        name="China/Taiwan tech tension, rare earths & semiconductors",
        reasoning=("China dominates rare-earth refining and has used export controls (gallium, germanium, rare "
                   "earths) as leverage; the US restricts chip/tool exports to China. Escalation helps non-Chinese "
                   "rare-earth producers (MP Materials) and hurts chip firms with China/Taiwan exposure. Nordic "
                   "Semiconductor and Elkem (silicon materials) are Oslo-listed exposures."),
        sectors=["Rare earths", "Semiconductors", "Semi equipment", "Silicon materials"],
        commodities=[],
        tickers_us=["MP", "REMX", "SMH", "TSM", "NVDA", "ASML"],
        tickers_ose=["NOD.OL", "ELK.OL"],
        keywords=["taiwan", "rare earth", "semiconductor", "chip", "export control", "gallium", "germanium",
                  "south china sea", "beijing", "pla", "tsmc"],
        gdelt_countries=["CH", "TW", "RP", "VM", "JA", "KS", "KN"],
        url_keywords=["taiwan", "rare-earth", "semiconductor", "chip", "south-china-sea"],
        trends_terms=["Taiwan", "rare earth", "chip export"],
        sector_etf="SMH",
        escalation="Rare-earth miners up, Taiwan/China-exposed chip names down; broad risk-off.",
        deescalation="Chip stocks rally on détente; rare-earth premium fades.",
        risks="Semis are dominated by the AI earnings cycle; geopolitics is often second-order.",
    ),
    Theme(
        key="elections_political",
        name="Elections & political instability",
        reasoning=("Elections, coups and government collapses change fiscal, energy and regulatory policy. "
                   "The effect is country-specific: country ETFs, the currency and domestic banks are the most "
                   "direct exposures. Volatility (VIX) tends to rise into contested outcomes."),
        sectors=["Country ETFs", "Banks", "FX"],
        commodities=["USDNOK=X", "EURUSD=X"],
        tickers_us=["SPY", "FEZ", "EWZ", "EWW", "EWG"],
        tickers_ose=["DNB.OL"],
        keywords=["election", "referendum", "coup", "resign", "no-confidence", "impeach", "snap election",
                  "parliament dissolved", "martial law", "protest"],
        gdelt_countries=[],
        gdelt_roots=["14"],
        url_keywords=["election", "coup", "referendum", "impeach", "resign"],
        trends_terms=["election", "coup", "resigns"],
        sector_etf="SPY",
        escalation="Country ETF / currency weakens on instability; volatility up.",
        deescalation="Clear outcomes usually relieve risk premia (relief rally).",
        risks="Very noisy; outcome markets (Polymarket) usually price results before news flow peaks.",
    ),
    Theme(
        key="nordic_arctic",
        name="Nordic/Arctic security & subsea infrastructure",
        reasoning=("Sabotage of Baltic/North Sea cables and pipelines, Russian activity in the High North and "
                   "Nordic rearmament create demand for surveillance, naval systems and subsea repair/protection. "
                   "Norwegian exposure: Kongsberg (maritime/defence), Kitron (defence electronics), Subsea 7; "
                   "gas-supply scares lift Equinor."),
        sectors=["Defence", "Subsea services", "Cables", "Gas supply"],
        commodities=["TTF=F"],
        tickers_us=["FTI"],
        tickers_ose=["KOG.OL", "KIT.OL", "SUBC.OL", "EQNR.OL"],
        tickers_other=["NKT.CO"],
        keywords=["subsea cable", "undersea cable", "sabotage", "baltic", "arctic", "svalbard", "high north",
                  "norway", "finnmark", "gas pipeline", "greenland", "north sea"],
        gdelt_countries=["NO", "SV", "SW", "FI", "DA", "GL", "EN", "LG", "LH"],
        url_keywords=["baltic", "sabotage", "undersea", "subsea", "arctic", "svalbard", "greenland"],
        trends_terms=["Baltic Sea cable", "Svalbard", "Greenland"],
        sector_etf="ITA",
        escalation="Kongsberg/Kitron and gas prices up.",
        deescalation="Limited direct downside; mostly a slow-burn procurement theme.",
        risks="Incidents are rare and often ambiguous (accident vs sabotage); moves fade quickly.",
    ),
    Theme(
        key="food_agri",
        name="Food, grain & fertiliser supply shocks",
        reasoning=("War or export bans in major grain/fertiliser exporters (Black Sea, Belarus/Russia potash) "
                   "raise grain and fertiliser prices. Yara (Oslo) and North American fertiliser makers benefit "
                   "from higher nitrogen/potash prices, but Yara's gas costs rise with European gas."),
        sectors=["Fertiliser", "Grain"],
        commodities=["ZW=F", "ZC=F"],
        tickers_us=["CF", "NTR", "MOS"],
        tickers_ose=["YAR.OL"],
        keywords=["grain", "wheat", "fertiliser", "fertilizer", "black sea", "food crisis", "export ban",
                  "potash", "famine", "drought"],
        gdelt_countries=["UP", "RS", "BO"],
        gdelt_roots=["16"],
        url_keywords=["grain", "wheat", "fertili", "famine", "food-crisis"],
        trends_terms=["wheat price", "fertilizer", "food crisis"],
        sector_etf="MOO",
        escalation="Wheat/corn and fertiliser equities up.",
        deescalation="Grain corridors / deals push prices down.",
        risks="Weather and harvests dominate grain prices far more than geopolitics.",
    ),
    Theme(
        key="risk_off_haven",
        name="Broad risk-off / safe havens",
        reasoning=("When several geopolitical risks rise at once, money typically flows into gold, the Swiss "
                   "franc, yen and US Treasuries, and out of small currencies such as NOK. Gold miners are a "
                   "leveraged play on the gold price."),
        sectors=["Gold", "Gold miners", "Safe-haven FX"],
        commodities=["GC=F", "USDCHF=X", "USDJPY=X", "USDNOK=X", "^VIX"],
        tickers_us=["GLD", "GDX", "NEM"],
        tickers_ose=[],
        keywords=["war", "nuclear", "escalat", "invasion", "world war", "gold price", "safe haven",
                  "martial law", "state of emergency"],
        gdelt_countries=[],
        gdelt_roots=["18", "19", "20"],
        url_keywords=["nuclear", "invasion", "escalat", "world-war"],
        trends_terms=["gold price", "world war 3", "nuclear war"],
        sector_etf="GLD",
        escalation="Gold, CHF, JPY up; NOK and small caps down.",
        deescalation="Havens give back gains; cyclicals and NOK recover.",
        risks="Gold is also driven by real rates and central-bank buying, unrelated to headlines.",
    ),
]

THEME_BY_KEY = {t.key: t for t in THEMES}


_RX: dict[str, "re.Pattern"] = {}


def _theme_regex(th: "Theme"):
    """Keywords match at a word start; short keywords (<= 4 chars) must be whole words (optional plural 's'),
    so 'war' does not match 'award' and 'pla' does not match 'plan'."""
    import re
    if th.key not in _RX:
        parts = [rf"\b{re.escape(k)}s?\b" if len(k) <= 4 else rf"\b{re.escape(k)}" for k in th.keywords]
        _RX[th.key] = re.compile("|".join(parts), re.I)
    return _RX[th.key]


def match_themes(text: str) -> list[str]:
    """Return theme keys whose keywords appear in text (case-insensitive, word-boundary aware)."""
    t = text or ""
    return [th.key for th in THEMES if _theme_regex(th).search(t)]


def all_watch_tickers() -> list[str]:
    out: list[str] = []
    for th in THEMES:
        out += th.all_tickers + th.commodities + th.losers + [th.sector_etf]
    return list(dict.fromkeys(out))


# Map common contractor / company names (as they appear in USAspending, news) to tickers.
NAME_TO_TICKER = {
    "LOCKHEED MARTIN": "LMT", "RAYTHEON": "RTX", "RTX CORP": "RTX", "NORTHROP GRUMMAN": "NOC",
    "GENERAL DYNAMICS": "GD", "L3HARRIS": "LHX", "HARRIS CORP": "LHX", "BOEING": "BA", "HUNTINGTON INGALLS": "HII",
    "LEIDOS": "LDOS", "BOOZ ALLEN": "BAH", "SAIC": "SAIC", "SCIENCE APPLICATIONS": "SAIC", "CACI": "CACI",
    "PALANTIR": "PLTR", "ANDURIL": None, "KONGSBERG": "KOG.OL", "BAE SYSTEMS": "BA.L", "HONEYWELL": "HON",
    "GENERAL ELECTRIC": "GE", "TEXTRON": "TXT", "OSHKOSH": "OSK", "AEROVIRONMENT": "AVAV", "KRATOS": "KTOS",
    "BWX": "BWXT", "FLUOR": "FLR", "JACOBS": "J", "KBR": "KBR", "PARSONS": "PSN", "V2X": "VVX", "MERCURY SYSTEMS": "MRCY",
    "MCKESSON": "MCK", "HUMANA": "HUM", "CENTENE": "CNC", "UNITEDHEALTH": "UNH", "PFIZER": "PFE", "MODERNA": "MRNA",
    "SPACE EXPLORATION": None, "AMENTUM": "AMTM", "EXXON": "XOM", "CHEVRON": "CVX", "MP MATERIALS": "MP",
    "METALLUS": "MTUS", "GEORGIA POWER": "SO", "SIKORSKY": "LMT", "PRATT & WHITNEY": "RTX", "COLLINS AEROSPACE": "RTX",
    "ELECTRIC BOAT": "GD", "BATH IRON WORKS": "GD", "GULFSTREAM": "GD", "INGALLS": "HII", "NEWPORT NEWS": "HII",
    "SIERRA NEVADA": None, "ACCENTURE": "ACN", "IBM": "IBM", "MICROSOFT": "MSFT", "AMAZON WEB": "AMZN", "ORACLE": "ORCL",
    "DELL ": "DELL", "CURTISS-WRIGHT": "CW", "MOOG": "MOG-A", "HEICO": "HEI", "TRANSDIGM": "TDG", "ALLISON TRANSMISSION": "ALSN",
    "ROLLS-ROYCE": "RR.L", "THALES": "HO.PA", "SAAB": "SAAB-B.ST", "RHEINMETALL": "RHM.DE", "NAMMO": None, "KITRON": "KIT.OL",
    "LEONARDO": "LDO.MI", "AIRBUS": "AIR.PA", "DRS": "DRS", "ELBIT": "ESLT", "PERSPECTA": None, "SUBSEA 7": "SUBC.OL",
    "TECHNIPFMC": "FTI", "HALLIBURTON": "HAL", "SCHLUMBERGER": "SLB", "SLB ": "SLB",
}


def _apply_norwegian() -> None:
    """Use Norwegian display texts (UI language); English originals kept as `name_en` etc."""
    from .themes_no import NO
    for th in THEMES:
        for field_name, val in NO.get(th.key, {}).items():
            setattr(th, field_name + "_en", getattr(th, field_name))
            setattr(th, field_name, val)


_apply_norwegian()
