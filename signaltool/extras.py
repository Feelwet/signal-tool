"""Extra decision layers added on top of the core pipeline (all free, no keys). Each step is isolated: a failure only
adds a FAILED status line and never breaks the run.
  * decision data per ticker (priced-in, valuation, risk, invalidation, event risk)  -> e["decision"]
  * IMF PortWatch chokepoint transits                                                -> snap["chokepoints"]
  * Federal Register / EU sanctions policy alerts                                     -> snap["policy_alerts"]
  * oil stocks vs 5-year seasonal norm (EIA)                                          -> snap["oil_nowcast"]
  * Taiwan monthly revenue (AI/semis supply chain)                                    -> snap["taiwan_revenue"]
  * Newsweb insider notices classified buy/sell (message body)                        -> snap["newsweb_insider_classified"]
"""
from __future__ import annotations
import logging
import pandas as pd

log = logging.getLogger(__name__)


def decision(snap: dict, status: dict) -> None:
    try:
        from . import decision as dec
        dec.apply(snap)
        n = sum(1 for e in snap.get("tickers", []) if e.get("decision"))
        status["Beslutningsdata (Yahoo: risiko, verdsettelse, stopp)"] = f"ok ({n}/{len(snap.get('tickers', []))} tickere)"
    except Exception as ex:
        log.exception("decision failed")
        status["Beslutningsdata (Yahoo: risiko, verdsettelse, stopp)"] = f"FAILED: {ex}"


def collectors(snap: dict, status: dict) -> None:
    from .collectors import portwatch, policy, oil_nowcast, taiwan_revenue, newsweb_insider
    steps = [("chokepoints", "IMF PortWatch (sundpassasjer)", portwatch.collect),
             ("policy_alerts", "Politikkvarsler (Federal Register / EU)", policy.collect),
             ("oil_nowcast", "EIA lagre vs 5-årssnitt", oil_nowcast.collect),
             ("taiwan_revenue", "Taiwan månedlig omsetning (MOPS)", taiwan_revenue.collect)]
    for key, lab, fn in steps:
        try:
            snap[key], status[lab] = fn()
        except Exception as ex:
            log.exception("%s failed", key)
            status[lab] = f"FAILED: {ex}"
    try:
        df, status["Newsweb innsidehandel: kjøp/salg (meldingstekst)"] = newsweb_insider.collect(days=21)
        if len(df):
            df = df.sort_values("published", ascending=False)
            df["published"] = df["published"].astype(str)
            cols = [c for c in ["published", "issuer", "issuer_name", "title", "kind", "shares", "price_nok", "value_nok", "url"] if c in df.columns]
            snap["newsweb_insider_classified"] = df[cols].head(80).where(pd.notna(df[cols].head(80)), None).to_dict("records")
            annotate_insider(snap)
    except Exception as ex:
        log.exception("newsweb insider failed")
        status["Newsweb innsidehandel: kjøp/salg (meldingstekst)"] = f"FAILED: {ex}"


def flags(snap: dict, status: dict, nw=None, fetch: bool = True) -> None:
    """Oslo red/yellow flags + info tags (oslo_flags.py) and the market-regime box (regime.py)."""
    try:
        from . import oslo_flags
        status["Oslo-flagg (kurs, EBIT, emisjon, tilbakekjøp)"] = oslo_flags.apply(snap, nw=nw, fetch=fetch)
    except Exception as ex:
        log.exception("oslo flags failed")
        status["Oslo-flagg (kurs, EBIT, emisjon, tilbakekjøp)"] = f"FAILED: {ex}"
    try:
        from . import regime
        status["Markedsregime (10-mnd snitt, volatilitet)"] = regime.apply(snap, fetch=fetch)
    except Exception as ex:
        log.exception("regime failed")
        status["Markedsregime (10-mnd snitt, volatilitet)"] = f"FAILED: {ex}"


def annotate_insider(snap: dict) -> None:
    """Replace the generic 'direction must be checked' evidence with the classified direction (no score change)."""
    rows = snap.get("newsweb_insider_classified") or []
    by = {}
    for r in rows:
        by.setdefault(f"{r.get('issuer')}.OL", []).append(r)
    for e in snap.get("tickers", []):
        rs = by.get(e["ticker"])
        if not rs:
            continue
        k = pd.Series([r["kind"] for r in rs]).value_counts().to_dict()
        buy_val = sum(r.get("value_nok") or 0 for r in rs if r["kind"] == "kjøp")
        txt = "Newsweb innsidehandel (21 d, klassifisert fra meldingsteksten): " + ", ".join(f"{n} {v}" for v, n in k.items())
        if buy_val:
            txt += f"; kjøp for ca. NOK {buy_val/1e6:,.1f} mill."
        e["insider_oslo"] = {"counts": k, "buy_value_nok": buy_val}
        ev = [x for x in e.get("evidence", []) if "retning (kjøp/salg) må sjekkes" not in x.get("text", "")
              and not x.get("text", "").startswith("Newsweb innsidehandel (21 d")]   # idempotent on re-runs
        best = next((r for r in rs if r["kind"] == "kjøp"), rs[0])
        ev.append({"text": txt, "url": best.get("url")})
        e["evidence"] = ev
