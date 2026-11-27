"""NBS industriprofitt: deterministisk parsing av offisiell kunngjøring til forklaringskort.

Ingen språkmodell. Tall som ikke finnes ordrett i lagret kildetekst, skjuler kortet.
Engelsk kunngjøring foretrekkes når den er publisert; ellers brukes den kinesiske.
Forklaringen hentes fra NBSs egen statistikerkommentar når den finnes.
"""
from __future__ import annotations

import json, logging, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from .config import LOGS, ROOT

log = logging.getLogger(__name__)

OSLO = ZoneInfo("Europe/Oslo")
SHANGHAI = ZoneInfo("Asia/Shanghai")

OUT_PATH = LOGS / "nbs_industriprofitt.json"
SITE_PATH = ROOT / "site" / "data" / "nbs_industriprofitt.json"

EN_INDEX = "https://www.stats.gov.cn/english/PressRelease/"
CN_INDEX = "https://www.stats.gov.cn/sj/zxfb/"
CN_INTERP_INDEX = "https://www.stats.gov.cn/sj/sjjd/"

KIND = "nbs_industriprofitt"
NOTE = "Forklaring fra kildene, ikke en prognose"
MISSING_CAUSE = "Kilden oppgir ikke årsak"
ATTR = "ifølge NBS"

EN_TITLE_RE = re.compile(
    r"Profits of Industrial Enterprises above the Designated Size from January to ([A-Za-z]+)(?:\s+in\s+(20\d{2}))?",
    re.I,
)
CN_TITLE_RE = re.compile(
    r"(20\d{2})年1\s*[—–-]\s*(\d{1,2})\s*月份全国规模以上工业企业利润",
)
CN_INTERP_RE = re.compile(
    r"(20\d{2})年1\s*[—–-]\s*(\d{1,2})\s*月份工业企业利润",
)

EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
NO_MON = {
    1: "jan.", 2: "feb.", 3: "mars", 4: "apr.", 5: "mai", 6: "juni",
    7: "juli", 8: "aug.", 9: "sep.", 10: "okt.", 11: "nov.", 12: "des.",
}

# Offisielle bransjenavn -> kort norsk etikett. Aldri utledet effekt, bare navn.
INDUSTRY_NO = {
    "manufacture of computers, communication equipment and other electronic equipment": "Elektronikk og kommunikasjon",
    "计算机、通信和其他电子设备制造业": "Elektronikk og kommunikasjon",
    "电子行业": "Elektronikk og kommunikasjon",
    "smelting and pressing of non-ferrous metals": "Ikke-jernholdige metaller",
    "有色金属冶炼和压延加工业": "Ikke-jernholdige metaller",
    "有色行业": "Ikke-jernholdige metaller",
    "mining and washing of coal": "Kull",
    "煤炭开采和洗选业": "Kull",
    "manufacture of raw chemical materials and chemical products": "Kjemikalier",
    "化学原料和化学制品制造业": "Kjemikalier",
    "化工": "Kjemikalier",
    "extraction of petroleum and natural gas": "Olje- og gassutvinning",
    "石油和天然气开采业": "Olje- og gassutvinning",
    "油气开采": "Olje- og gassutvinning",
    "textile industry": "Tekstil",
    "纺织业": "Tekstil",
    "manufacture of general-purpose machinery": "Generell maskinindustri",
    "通用设备制造业": "Generell maskinindustri",
    "manufacture of special-purpose machinery": "Spesialmaskiner",
    "专用设备制造业": "Spesialmaskiner",
    "manufacture of electrical machinery and apparatus": "Elektrisk utstyr",
    "电气机械和器材制造业": "Elektrisk utstyr",
    "processing of food from agricultural and sideline products": "Næringsmidler",
    "农副食品加工业": "Næringsmidler",
    "production and supply of electricity and heat power": "Kraft og varme",
    "电力、热力生产和供应业": "Kraft og varme",
    "production and supply of electricity, heat power, gas and water": "Kraft, varme, gass og vann",
    "电力、热力、燃气及水生产和供应业": "Kraft, varme, gass og vann",
    "manufacture of automobiles": "Biler",
    "汽车制造业": "Biler",
    "manufacture of non-metallic mineral products": "Ikke-metalliske mineralprodukter",
    "非金属矿物制品业": "Ikke-metalliske mineralprodukter",
    "smelting and pressing of ferrous metals": "Jernholdige metaller",
    "黑色金属冶炼和压延加工业": "Jernholdige metaller",
    "processing of petroleum, coal and other fuels": "Olje- og kullforedling",
    "石油、煤炭及其他燃料加工业": "Olje- og kullforedling",
    "石油加工行业": "Olje- og kullforedling",
    "petroleum, coal and other fuels": "Olje- og kullforedling",
    "mining": "Bergverk",
    "采矿业": "Bergverk",
    "manufacturing": "Industri",
    "制造业": "Industri",
    "有色金属矿": "Ikke-jernholdig malm",
    "化纤": "Kjemiske fibre",
}

PRIMARY_HOSTS = {
    "stats.gov.cn": "nbs",
    "bls.gov": "bls",
    "ssb.no": "ssb",
    "ssb.no": "ssb",
    "ec.europa.eu": "eurostat",
    "eurostat.ec.europa.eu": "eurostat",
    "newsweb.oslobors.no": "newsweb",
    "norges-bank.no": "cb",
    "federalreserve.gov": "cb",
    "ecb.europa.eu": "cb",
    "riksbank.se": "cb",
    "riksbank.se": "cb",
    "nationalbanken.dk": "cb",
    "bankofengland.co.uk": "cb",
    "boe.org.uk": "cb",
    "pbc.gov.cn": "cb",
    "bundesbank.de": "cb",
    "banque-france.fr": "cb",
    "boj.or.jp": "cb",
    "bankofcanada.ca": "cb",
    "rba.gov.au": "cb",
    "snb.ch": "cb",
}

PROFIT_PHRASES = (
    "industrial profit", "industrial profits", "工业企业利润", "规模以上工业企业利润",
    "industriprofitt", "industriprofitten", "profits of industrial enterprises",
)
GEO_PHRASES = ("china", "kina", "chinese", "kinesisk", "nbs", "中国", "stats.gov", "national bureau of statistics")

_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _host(url: str) -> str:
    h = (urlparse(url).netloc or "").lower()
    if h.startswith("www."):
        h = h[4:]
    return h


def is_primary_url(url: str) -> bool:
    h = _host(url)
    if h in PRIMARY_HOSTS:
        if PRIMARY_HOSTS[h] == "eurostat" and h == "ec.europa.eu":
            return "eurostat" in (urlparse(url).path or "").lower()
        return True
    return any(h.endswith("." + k) for k in PRIMARY_HOSTS)


def _fmt_num(value: float, min_dec: int = 1) -> str:
    """Keep source decimals (5.69 -> 5,69) and at least one decimal for rates (16.0 -> 16,0)."""
    av = abs(value)
    s = f"{av:.4f}".rstrip("0")
    if "." not in s:
        s += "."
    dec = len(s.split(".", 1)[1])
    dec = max(dec, min_dec)
    return f"{av:.{dec}f}".replace(".", ",")


def _pct_no(value: float, signed: bool = True) -> str:
    s = _fmt_num(value)
    if signed:
        if value > 0:
            return f"+{s} %"
        if value < 0:
            return f"−{s} %"
    return f"{s} %"


def _fold_no(fold: float) -> str:
    s = _fmt_num(fold)
    return f"+{s} gang" if fold == 1 else f"+{s} ganger"


class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.title: list[str] = []
        self._skip = 0
        self._in_title = False
        self._in_a = False
        self._a_href = ""
        self._a_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
            return
        d = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag in ("p", "div", "tr", "h1", "h2", "h3", "li", "br", "section", "table"):
            self.chunks.append("\n")
        if tag == "a":
            self._in_a = True
            self._a_href = d.get("href") or ""
            self._a_text = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._in_a:
            self._in_a = False
            self.links.append(("".join(self._a_text).strip(), self._a_href))
        if tag in ("p", "div", "tr", "h1", "h2", "h3", "li", "section"):
            self.chunks.append("\n")

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title.append(data)
        self.chunks.append(data)
        if self._in_a:
            self._a_text.append(data)

    def text(self) -> str:
        t = unescape("".join(self.chunks))
        t = re.sub(r"[ \t\xa0\u2003\u2002\u2009]+", " ", t)
        t = re.sub(r"\n[ \t]+", "\n", t)
        t = re.sub(r"[ \t]+\n", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()

    def title_text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self.title)).strip()


def parse_html(html: str) -> _Html:
    p = _Html()
    p.feed(html or "")
    p.close()
    return p


def source_text(html: str) -> str:
    """Plain text for verbatim number checks: tags stripped without breaking 16.0%."""
    t = re.sub(r"(?is)<(script|style|noscript)\b[^>]*>.*?</\1>", " ", html or "")
    t = re.sub(r"(?i)</?(p|div|br|tr|h1|h2|h3|li|table|section)[^>]*>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", "", t)
    t = unescape(t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return t


def _compact(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def parse_published(html: str, text: str | None = None) -> datetime | None:
    blob = (html or "") + "\n" + (text or "")
    m = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", blob)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh = int(m.group(4) or 9)
    mm = int(m.group(5) or 30)
    try:
        return datetime(y, mo, d, hh, mm, tzinfo=SHANGHAI)
    except ValueError:
        return None


def _industry_no(name: str) -> str:
    key = _norm_ws(name).lower()
    for en, no in INDUSTRY_NO.items():
        if key == en.lower() or key == en:
            return no
    # substring, longest key first
    for en, no in sorted(INDUSTRY_NO.items(), key=lambda kv: len(kv[0]), reverse=True):
        if en.lower() in key or key in en.lower():
            return no
    return _norm_ws(name)


@dataclass
class IndustryChange:
    name_src: str
    name_no: str
    pct: float | None = None  # signed percent; None if loss-to-profit
    fold: float | None = None
    loss_to_profit: bool = False

    @property
    def rank_pct(self) -> float:
        if self.fold is not None:
            return self.fold * 100.0
        if self.loss_to_profit:
            return float("inf")
        return self.pct if self.pct is not None else 0.0

    def change_label(self) -> str:
        if self.loss_to_profit:
            return "fra underskudd til overskudd"
        if self.fold is not None:
            return _fold_no(self.fold)
        if self.pct is not None:
            return _pct_no(self.pct)
        return ""

    def direction(self) -> str:
        if self.loss_to_profit or (self.fold or 0) > 0 or (self.pct or 0) > 0:
            return "opp"
        if (self.pct or 0) < 0:
            return "ned"
        return ""


@dataclass
class Release:
    year: int
    start_month: int
    end_month: int
    lang: str
    title: str
    url: str
    published: datetime | None
    html: str
    text: str
    yoy_month: float | None = None
    yoy_cum: float | None = None
    industries: list[IndustryChange] = field(default_factory=list)
    interp_url: str = ""
    interp_html: str = ""
    interp_text: str = ""
    interp_published: datetime | None = None


def _parse_period_from_title(title: str) -> tuple[int, int, int] | None:
    t = _norm_ws(title)
    m = EN_TITLE_RE.search(t)
    if m:
        mon = EN_MONTHS.get(m.group(1).lower())
        if mon:
            return int(m.group(2)), 1, mon
    m = CN_TITLE_RE.search(_compact(t)) or CN_TITLE_RE.search(t)
    if m:
        return int(m.group(1)), 1, int(m.group(2))
    m = re.search(r"(20\d{2})年1\s*[—–-]\s*(\d{1,2})\s*月份", t)
    if m:
        return int(m.group(1)), 1, int(m.group(2))
    m = re.search(r"from January to ([A-Za-z]+) in (20\d{2})", t, re.I)
    if m and m.group(1).lower() in EN_MONTHS:
        return int(m.group(2)), 1, EN_MONTHS[m.group(1).lower()]
    return None


def parse_industries_en(text: str) -> list[IndustryChange]:
    compact = _norm_ws(text)
    m = re.search(r"profits of main industries were as follows:\s*(.+?)(?:From January|\nIn [A-Z]|$)", compact, re.I | re.S)
    blob = m.group(1) if m else compact
    out: list[IndustryChange] = []
    pat = re.compile(
        r"(?:the profit of the |that of the |and the )(.+?)(?:\s+increased by (\d+(?:\.\d+)?)%\s*(?:year on year)?|\s+decreased by (\d+(?:\.\d+)?)%|\s+turned from loss to profit)",
        re.I,
    )
    for sm in pat.finditer(blob):
        name = _norm_ws(sm.group(1)).rstrip(",")
        if sm.group(2) is not None:
            pct = float(sm.group(2))
            out.append(IndustryChange(name, _industry_no(name), pct=pct))
        elif sm.group(3) is not None:
            pct = -float(sm.group(3))
            out.append(IndustryChange(name, _industry_no(name), pct=pct))
        else:
            out.append(IndustryChange(name, _industry_no(name), loss_to_profit=True))
    return out


def parse_industries_cn(text: str) -> list[IndustryChange]:
    compact = re.sub(r"\s+", "", text or "")
    m = re.search(r"主要行业利润情况如下[：:](.+?)(?:。|规模以上工业企业实现营业收入|$)", compact)
    blob = m.group(1) if m else compact
    out: list[IndustryChange] = []
    for part in blob.split("，"):
        part = part.strip("。；; ")
        if not part:
            continue
        if "由亏转盈" in part:
            name = part.replace("由亏转盈", "").strip()
            out.append(IndustryChange(name, _industry_no(name), loss_to_profit=True))
            continue
        fm = re.search(r"^(.+?)(?:利润)?同比(?:增长|增长了)?(\d+(?:\.\d+)?)倍$", part)
        if not fm:
            fm = re.search(r"^(.+?)增长(\d+(?:\.\d+)?)倍$", part)
        if fm:
            name = re.sub(r"(?:利润同比)$", "", fm.group(1))
            fold = float(fm.group(2))
            out.append(IndustryChange(name, _industry_no(name), fold=fold))
            continue
        gm = re.search(r"^(.+?)(?:利润)?同比(?:增长|增长了)?(\d+(?:\.\d+)?)%$", part)
        if not gm:
            gm = re.search(r"^(.+?)增长(\d+(?:\.\d+)?)%$", part)
        if gm:
            name = re.sub(r"(?:利润同比)$", "", gm.group(1))
            out.append(IndustryChange(name, _industry_no(name), pct=float(gm.group(2))))
            continue
        dm = re.search(r"^(.+?)下降(\d+(?:\.\d+)?)%$", part)
        if dm:
            out.append(IndustryChange(dm.group(1), _industry_no(dm.group(1)), pct=-float(dm.group(2))))
    return out


def parse_totals(text: str, lang: str) -> tuple[float | None, float | None]:
    """Return (monthly YoY %, cumulative YoY %)."""
    t = _norm_ws(text)
    c = re.sub(r"\s+", "", text or "")
    month = cum = None
    if lang == "en":
        m = re.search(r"In ([A-Za-z]+), the profits of industrial enterprises above the designated size increased by (\d+(?:\.\d+)?)%\s*year on year", t, re.I)
        if m:
            month = float(m.group(2))
        m = re.search(r"total profits of industrial enterprises above the designated size nationwide reached .+? year-on-year increase of (\d+(?:\.\d+)?)%", t, re.I)
        if m:
            cum = float(m.group(1))
    else:
        m = re.search(r"(?<![—–\-\d])(\d{1,2})月份，?(全国)?规模以上工业企业利润同比增长(\d+(?:\.\d+)?)%", c)
        if m:
            month = float(m.group(3))
        m = re.search(r"1[—–-]\d{1,2}月份，?全国规模以上工业企业实现利润总额.+?同比增长(\d+(?:\.\d+)?)%", c)
        if m:
            cum = float(m.group(1))
        if cum is None:
            m = re.search(r"规模以上工业企业利润同比增长(\d+(?:\.\d+)?)%", c)
            if m:
                cum = float(m.group(1))
    return month, cum


def parse_bulletin(html: str, url: str = "", lang: str | None = None) -> Release | None:
    doc = parse_html(html)
    text = doc.text()
    title = doc.title_text() or ""
    if not title:
        first = (text.split("\n") or [""])[0]
        title = _norm_ws(first)[:200]
    if lang is None:
        lang = "en" if EN_TITLE_RE.search(title) or "Designated Size" in (html or "") or "year-on-year" in text.lower() else "cn"
    period = _parse_period_from_title(title) or _parse_period_from_title(text)
    if not period:
        return None
    year, start, end = period
    month, cum = parse_totals(text, lang)
    industries = parse_industries_en(text) if lang == "en" else parse_industries_cn(text)
    if month is None and cum is None:
        return None
    pub = parse_published(html, text)
    return Release(
        year=year, start_month=start, end_month=end, lang=lang, title=title, url=url,
        published=pub, html=html, text=source_text(html),
        yoy_month=month, yoy_cum=cum, industries=industries,
    )


def parse_interp(html: str, url: str = "") -> dict:
    text = parse_html(html).text()
    src = source_text(html)
    compact = re.sub(r"\s+", "", text)
    facts: dict = {"url": url, "html": html, "text": src, "published": parse_published(html, text), "ok": False}

    # AI / memory chips cause (NBS's own wording, mapped with a fixed glossary)
    ai = "人工智能算力需求" in compact or "人工智能算力" in compact
    chips = "存储芯片" in compact
    elec_fold = None
    elec_pp = None
    m = re.search(r"电子行业利润同比增长(\d+(?:\.\d+)?)倍，拉动全部规模以上工业企业利润增长(\d+(?:\.\d+)?)个百分点", compact)
    if m:
        elec_fold, elec_pp = float(m.group(1)), float(m.group(2))
    nf_pct = nf_pp = None
    copper = "铜" in compact and "铝" in compact and ("价格上涨" in compact or "需求旺盛" in compact)
    m = re.search(r"有色行业利润同比分别增长(\d+(?:\.\d+)?)%、(\d+(?:\.\d+)?)%，合计拉动规模以上工业企业利润增长(\d+(?:\.\d+)?)个百分点", compact)
    # actually: 有色金属矿、有色行业利润同比分别增长60.2%、71.7%，合计拉动...
    m = re.search(r"有色金属矿、有色行业利润同比分别增长(\d+(?:\.\d+)?)%、(\d+(?:\.\d+)?)%，合计拉动规模以上工业企业利润增长(\d+(?:\.\d+)?)个百分点", compact)
    if m:
        nf_pct, nf_pp = float(m.group(2)), float(m.group(3))
    margin = margin_pp = None
    m = re.search(r"营业收入利润率为(\d+(?:\.\d+)?)%，同比提高(\d+(?:\.\d+)?)个百分点", compact)
    if m:
        margin, margin_pp = float(m.group(1)), float(m.group(2))

    parts = []
    if ai and chips:
        parts.append("Etterspørselen etter regnekraft til kunstig intelligens økte og trakk opp profitten i minnebrikker og tilhørende produksjon")
    elif ai:
        parts.append("Etterspørselen etter regnekraft til kunstig intelligens økte")
    if elec_fold is not None and elec_pp is not None:
        parts.append(f"elektronikkindustrien økte profitten med {_fold_no(elec_fold).lstrip('+')} og trakk opp samlet profitt med {str(elec_pp).replace('.', ',')} prosentpoeng")
    elif elec_fold is not None:
        parts.append(f"elektronikkindustrien økte profitten med {_fold_no(elec_fold).lstrip('+')}")
    if copper and nf_pct is not None and nf_pp is not None:
        parts.append(f"etterspørsel etter kobber og aluminium og høyere priser trakk opp ikke-jernholdige metaller ({_pct_no(nf_pct, signed=False)}) med {str(nf_pp).replace('.', ',')} prosentpoeng")
    elif nf_pct is not None and nf_pp is not None:
        parts.append(f"ikke-jernholdige metaller ({_pct_no(nf_pct, signed=False)}) trakk opp samlet profitt med {str(nf_pp).replace('.', ',')} prosentpoeng")
    if margin is not None and margin_pp is not None:
        parts.append(f"inntektsmarginen var {_pct_no(margin, signed=False)}, opp {str(margin_pp).replace('.', ',')} prosentpoeng")

    if not parts:
        facts["cause"] = None
        return facts
    # Capitalize first sentence, join with period/comma naturally
    text_no = parts[0][0].upper() + parts[0][1:]
    for p in parts[1:]:
        text_no += ", " + p
    text_no += "."
    facts["cause"] = text_no
    facts["ok"] = True
    facts["numbers"] = {
        "elec_fold": elec_fold, "elec_pp": elec_pp, "nf_pct": nf_pct, "nf_pp": nf_pp,
        "margin": margin, "margin_pp": margin_pp,
    }
    return facts


def number_forms(tok: str) -> set[str]:
    t = tok.strip().replace("−", "-")
    if not _NUM.fullmatch(t.replace("-", "", 1) if t.startswith("-") else t):
        t = tok
    forms = {t, t.replace(",", "."), t.replace(".", ",")}
    # 16,0 <-> 16.0; also 16.0 <-> 16 if trailing zero? Do NOT drop trailing zeros:
    # 16.0 in source must stay 16.0 / 16,0. "16" may also appear, but requiring 16.0 is stricter.
    if "," in t:
        forms.add(t.replace(",", "."))
    if "." in t:
        forms.add(t.replace(".", ","))
    return {f for f in forms if f}


_DATE = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b")


def numbers_in(text: str) -> list[str]:
    # Display dates like 27.11.2026 are a format, not a source figure.
    return _NUM.findall(_DATE.sub(" ", text or ""))


def _has_form(blob: str, form: str) -> bool:
    """True if form is a complete number token, not a substring of 6299.9 or 6,033.74."""
    return re.search(r"(?<![\d.,])" + re.escape(form) + r"(?![\d.,])", blob) is not None


def source_has_numbers(display: str, sources: list[str]) -> tuple[bool, list[str]]:
    """Every number in display must appear verbatim (dot/comma equivalent) in some source text."""
    blob = "\n".join(sources)
    missing = []
    for tok in numbers_in(display):
        if not any(_has_form(blob, form) for form in number_forms(tok)):
            missing.append(tok)
    return (not missing), missing


def _oslo_date(ts: datetime | None) -> str:
    if ts is None:
        return ""
    return ts.astimezone(OSLO).strftime("%d.%m.%Y")


def _iso(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_card(rel: Release, interp: dict | None = None, exposures: list[dict] | None = None) -> dict:
    interp = interp or {}
    exposures = [e for e in (exposures or []) if e.get("share") is not None and e.get("report_url") and e.get("report_date")]
    mon_label = NO_MON.get(rel.end_month, str(rel.end_month))
    values = []
    if rel.yoy_month is not None:
        values.append({"label": f"{_pct_no(rel.yoy_month)} {mon_label}", "raw": rel.yoy_month})
    if rel.yoy_cum is not None:
        if rel.start_month == 1:
            values.append({"label": f"{_pct_no(rel.yoy_cum)} jan.–{mon_label}", "raw": rel.yoy_cum})
        else:
            values.append({"label": f"{_pct_no(rel.yoy_cum)}", "raw": rel.yoy_cum})
    numeric = [i for i in rel.industries if not i.loss_to_profit and (i.pct is not None or i.fold is not None)]
    ups = sorted([i for i in numeric if i.rank_pct > 0], key=lambda i: i.rank_pct, reverse=True)[:4]
    downs = sorted([i for i in numeric if i.rank_pct < 0], key=lambda i: i.rank_pct)[:4]

    def row(i: IndustryChange, height_note=None) -> dict:
        d = i.direction()
        return {
            "industry": i.name_no,
            "change": i.change_label(),
            "direction": d,
            "arrow": "↑" if d == "opp" else ("↓" if d == "ned" else ""),
            "dir_text": d,
        }

    cause = interp.get("cause") if interp.get("ok") else None
    forklaring = {
        "label": "Kildens egen forklaring",
        "text": cause or MISSING_CAUSE,
        "attribution": ATTR if cause else "",
        "missing": not bool(cause),
    }
    sectors = []
    for i in rel.industries:
        label = i.change_label()
        if i.loss_to_profit:
            detail = f"{i.name_no} {label}"
        else:
            detail = f"{i.name_no} {label} profitt jan.–{mon_label}"
        sectors.append({"name": i.name_no, "detail": detail, "source": "NBS"})
    nevnt = {"sectors": sectors, "exposures": exposures}
    hide_nevnt = not sectors and not exposures
    pub = rel.published or interp.get("published")
    source_line = "NBS" + (f" · {_oslo_date(pub)}" if pub else "")
    sources = [rel.text or rel.html]
    if interp.get("text"):
        sources.append(interp["text"])
    if rel.interp_text:
        sources.append(rel.interp_text)
    # Visible text that contains numbers (for the automatic check)
    visible = " ".join([
        NOTE,
        " ".join(v["label"] for v in values),
        source_line,
        " ".join(f"{r['industry']} {r['change']}" for r in [row(i) for i in ups + downs]),
        forklaring["text"],
        " ".join(s["detail"] for s in sectors),
        " ".join(
            f"{e.get('ticker','')} {e.get('share_label','')} {e.get('report_date','')}"
            for e in exposures
        ),
    ])
    ok, missing = source_has_numbers(visible, sources)
    urls = [u for u in [rel.url, interp.get("url") or rel.interp_url] if u]
    figures = []
    for v in (rel.yoy_month, rel.yoy_cum):
        if v is None:
            continue
        figures.append(f"{v:.1f}")
        figures.append(f"{v:.1f}".replace(".", ","))
    card = {
        "id": f"nbs-industriprofitt-{rel.year}-{rel.start_month:02d}-{rel.end_month:02d}",
        "kind": KIND,
        "ok": ok and rel.yoy_month is not None and rel.yoy_cum is not None,
        "hide": not (ok and rel.yoy_month is not None and rel.yoy_cum is not None),
        "missing_numbers": missing,
        "note": NOTE,
        "source": {
            "name": "NBS",
            "url": rel.url,
            "urls": urls,
            "published": _iso(pub),
            "published_oslo": _oslo_date(pub),
            "line": source_line,
            "lang": rel.lang,
        },
        "period": {"year": rel.year, "start_month": rel.start_month, "end_month": rel.end_month},
        "blocks": {
            "tallet": {"values": values, "source_line": source_line, "source_url": rel.url},
            "bidrag": {"up": [row(i) for i in ups], "down": [row(i) for i in downs]},
            "forklaring": forklaring,
            "nevnt": {**nevnt, "hidden": hide_nevnt},
        },
        "match": {
            "source_urls": urls,
            "url_needles": [Path(urlparse(u).path).name.replace(".html", "") for u in urls if u],
            "phrases": list(PROFIT_PHRASES),
            "figures": figures,
            "geo": list(GEO_PHRASES),
        },
        "source_text": "\n\n".join(s for s in sources if s),
    }
    if not card["ok"]:
        log.warning("nbs_industriprofitt: kort skjules (ok=%s, missing=%s)", card["ok"], missing)
    return card


def item_matches_card(item: dict, card: dict | None) -> bool:
    """Button is shown only when this exact key figure is matched, never by theme alone."""
    if not card or card.get("hide") or not card.get("ok"):
        return False
    rules = card.get("match") or {}
    url = (item.get("url") or "").strip()
    title = item.get("title") or ""
    blob = f"{title} {url}".lower()
    # Direct link to the saved primary source document
    for u in rules.get("source_urls") or []:
        if u and (url == u or url.rstrip("/") == u.rstrip("/")):
            return True
    for n in rules.get("url_needles") or []:
        if n and n.lower() in url.lower() and "stats.gov.cn" in _host(url):
            return True
    # Key-figure match: industrial-profit phrase + a figure from the card + China/NBS cue
    # (not theme match: "makro" or "Kina" alone is not enough)
    has_phrase = any(p.lower() in blob for p in rules.get("phrases") or [])
    has_fig = any(f.lower() in blob or f in title or f in url for f in rules.get("figures") or [])
    has_geo = any(g.lower() in blob for g in rules.get("geo") or [])
    return bool(has_phrase and has_fig and has_geo)


def discover_links(index_html: str, index_url: str, kind: str) -> list[dict]:
    """kind: 'en', 'cn', 'interp'."""
    doc = parse_html(index_html)
    out = []
    seen = set()
    for text, href in doc.links:
        if not href or href.startswith("#"):
            continue
        url = urljoin(index_url, href)
        title = _norm_ws(text)
        period = None
        if kind == "en":
            m = EN_TITLE_RE.search(title)
            if not m:
                continue
            mon = EN_MONTHS.get(m.group(1).lower())
            if not mon:
                continue
            year = int(m.group(2)) if m.group(2) else 0
            period = (year, 1, mon)
        elif kind == "cn":
            m = CN_TITLE_RE.search(_compact(title)) or CN_TITLE_RE.search(title)
            if not m:
                continue
            period = (int(m.group(1)), 1, int(m.group(2)))
        else:
            if "工业企业利润" not in title:
                continue
            m = re.search(r"(20\d{2})年1\s*[—–-]\s*(\d{1,2})\s*月份", title)
            if not m:
                continue
            period = (int(m.group(1)), 1, int(m.group(2)))
        key = (period, url)
        if key in seen:
            continue
        seen.add(key)
        out.append({"url": url, "title": title, "year": period[0], "start": period[1], "end": period[2], "kind": kind})
    out.sort(key=lambda r: (r["year"], r["end"]), reverse=True)
    return out


def _get_default():
    from . import http
    return http.get


def fetch_release(get, url: str) -> tuple[str, str]:
    r = get(url, timeout=40, retries=2)
    html = r.content.decode("utf-8", errors="replace") if hasattr(r, "content") else str(r)
    final = getattr(r, "url", None) or url
    return html, final


def collect(cfg=None, get=None, write: bool = False, exposures: list[dict] | None = None,
            en_index_html=None, cn_index_html=None, interp_index_html=None,
            pages: dict | None = None) -> dict | None:
    """Fetch latest NBS industrial-profits release, parse, and optionally write the card.

    `pages` maps url -> html for tests (no network). Missing pages or parse failure
    returns None (no button).
    """
    get = get or _get_default()
    pages = dict(pages or {})

    def load(url, preset=None):
        if preset is not None:
            return preset, url
        if url in pages:
            return pages[url], url
        html, final = fetch_release(get, url)
        pages[final] = html
        return html, final

    try:
        en_html, _ = load(EN_INDEX, en_index_html)
        cn_html, _ = load(CN_INDEX, cn_index_html)
        ip_html, _ = load(CN_INTERP_INDEX, interp_index_html)
    except Exception as ex:
        log.warning("nbs_industriprofitt: indeks feilet: %s", ex)
        return None

    en_links = discover_links(en_html, EN_INDEX, "en")
    cn_links = discover_links(cn_html, CN_INDEX, "cn")
    ip_links = discover_links(ip_html, CN_INTERP_INDEX, "interp")
    if not en_links and not cn_links:
        log.warning("nbs_industriprofitt: fant ingen kunngjøring")
        return None

    def key(L):
        return (L["year"], L["end"])

    latest = max([*en_links[:1], *cn_links[:1]], key=key)
    period = (latest["year"], latest["end"])
    en = next((L for L in en_links if (L["year"], L["end"]) == period), None)
    cn = next((L for L in cn_links if (L["year"], L["end"]) == period), None)
    ip = next((L for L in ip_links if (L["year"], L["end"]) == period), None)
    chosen = en or cn
    if not chosen:
        return None
    try:
        html, final = load(chosen["url"])
    except Exception as ex:
        log.warning("nbs_industriprofitt: henting feilet: %s", ex)
        return None
    lang = "en" if chosen["kind"] == "en" else "cn"
    rel = parse_bulletin(html, url=final, lang=lang)
    if rel is None:
        log.warning("nbs_industriprofitt: parsing feilet for %s", final)
        return None
    interp = None
    if ip:
        try:
            ih, iu = load(ip["url"])
            interp = parse_interp(ih, iu)
            rel.interp_url = iu
            rel.interp_html = ih
            rel.interp_text = interp.get("text") or ""
            rel.interp_published = interp.get("published")
        except Exception as ex:
            log.warning("nbs_industriprofitt: tolkning feilet: %s", ex)
            interp = None
    card = build_card(rel, interp, exposures)
    if write and card:
        write_output(card)
    return card


def write_output(card: dict, path: Path | None = None, site_path: Path | None = None) -> None:
    path = path or OUT_PATH
    if site_path is None:
        site_path = SITE_PATH
    # Do not store full HTML in the committed JSON (size); keep source_text + urls.
    slim = {k: v for k, v in card.items() if k not in {"source_html"}}
    text = json.dumps(slim, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if site_path is not None:
        site_path.parent.mkdir(parents=True, exist_ok=True)
        site_path.write_text(text)


def load_card(path: Path | None = None) -> dict | None:
    path = path or OUT_PATH
    if not path.exists():
        alt = SITE_PATH
        path = alt if alt.exists() else path
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def main(argv=None) -> int:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="nbs_industriprofitt")
    p.add_argument("--dry", action="store_true", help="Hent og parse, ikke skriv")
    args = p.parse_args(argv)
    card = collect(write=not args.dry)
    if not card or card.get("hide"):
        log.warning("ingen gyldig kort")
        return 1
    print(json.dumps({k: card[k] for k in ("id", "ok", "hide", "source", "period") if k in card}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
