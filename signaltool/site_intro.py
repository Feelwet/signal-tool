"""Synlige sideforklaringer; ingen signalregler eller tall beregnes her."""
from html import escape

TEXTS = {
    "Oversikt": "Samlet oversikt over markedsdata, aksjekandidater og nyheter. Kandidatene er utgangspunkt for videre undersøkelse, ikke kjøpsråd.",
    "Trender": "Her ser du hvordan råvarer og materialer brukes i komponenter og sektorer, og hvilke selskaper som har dokumentert tilknytning. Vi skiller mellom avhengighet, bekreftet mangel og rapportert utvikling. Tilknytning betyr ikke at selskapet vil tjene mer eller aksjen stige.",
    "Sektorer": "Her undersøker vi Oslo-sektorene, hva som driver dem og hvilke selskaper som passer utvalgsreglene. Utvalget er under måling, ikke en kjøpsanbefaling.",
    "Oslo": "Her finner du børsmeldinger, innsidehandler og shortdata fra Oslo Børs. Dette er rådata til egen undersøkelse, ikke kjøps- eller salgssignaler.",
    "Makro": "Her følger du inflasjon, renter og det fysiske oljemarkedet. Faktiske tall skilles fra kildenes prognoser; siden viser ikke egne prognoser.",
    "Temaer": "Her ser du hvor mye oppmerksomhet geopolitiske temaer får sammenlignet med sin egen historikk, og eksempler på tilknyttede verdikjeder. Temascore er rangering, ikke dokumentasjon på framtidig avkastning.",
    "Signal-boka": "Her logges regelstyrte handler med fiktive penger for å undersøke hvordan reglene virker over tid. Dette er ikke faktiske handler eller kjøpsråd.",
}
THEME_CAUTION = "Nyheter kobles automatisk til temaer. Koblingene kan være feil; siste kvalitetskontroll besto ikke."
CSS = ".page-intro{font-size:15px;line-height:23px;max-width:720px;margin:0 0 16px;color:#cbd5e1}.page-intro-caution{font-size:14px;line-height:22px;max-width:720px;margin:0 0 16px;color:#cbd5e1}"

def html(title):
    out = '<p class="page-intro">' + escape(TEXTS[title]) + '</p>'
    if title == "Temaer":
        out += '<p class="page-intro-caution">' + escape(THEME_CAUTION) + '</p>'
    return out
