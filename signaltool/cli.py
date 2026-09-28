"""Command line: python -m signaltool {run,report,build-site,backtest,serve}"""
from __future__ import annotations
import argparse, json, logging, sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="signaltool", description="Geopolitisk tidlig-varsling for aksjer (informasjon, ikke råd).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="collect all sources, score, write report + snapshot (+ site)")
    r.add_argument("--fast", action="store_true", help="skip slow sources (Google Trends, earnings) and cap Form 4 scan")
    r.add_argument("--no-site", action="store_true")
    sub.add_parser("report", help="re-render markdown report from latest snapshot")
    sub.add_parser("build-site", help="build static website in site/ from latest snapshot")
    sub.add_parser("check-site", help="sanity check of site/ before deploy (exit 1 = do not deploy)")
    sub.add_parser("categorize", help="refresh prices + Kjøp/Hold/Watchlist categories on the latest snapshot, then report + site")
    b = sub.add_parser("backtest", help="run historical validation")
    b.add_argument("which", choices=["insider", "gdelt", "categories", "kontroll", "all"], nargs="?", default="all")
    s = sub.add_parser("serve", help="serve site/ locally")
    s.add_argument("--port", type=int, default=8765)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(asctime)s %(name)s %(message)s")
    for n in ("urllib3", "yfinance", "peewee"):
        logging.getLogger(n).setLevel(logging.WARNING)

    from .config import DATA
    if a.cmd == "check-site":
        from .config import ROOT
        from .sitecheck import check
        problems = check(ROOT / "site")
        for p in problems:
            print(f"::error::site check: {p}")
        print("site check: OK" if not problems else f"site check: {len(problems)} problem(s) - do not deploy")
        sys.exit(1 if problems else 0)
    if a.cmd == "run":
        from . import pipeline, report
        snap = pipeline.run(fast=a.fast)
        p = report.write(snap)
        print(f"report: {p}")
        if not a.no_site:
            from . import site
            print(f"site: {site.build(snap)}")
            from .site_quality import FAILED_SECTIONS
            if FAILED_SECTIONS:
                print(f"::warning::sections not updated: {', '.join(FAILED_SECTIONS)}")
    elif a.cmd in ("report", "build-site"):
        snap = json.loads((DATA / "snapshots" / "latest.json").read_text())
        if a.cmd == "report":
            from . import report
            print(report.write(snap))
        else:
            from . import site
            print(site.build(snap))
    elif a.cmd == "categorize":
        from . import categories, report, site
        from .collectors import markets
        p = DATA / "snapshots" / "latest.json"
        snap = json.loads(p.read_text())
        ms, _, msg = markets.collect([e["ticker"] for e in snap["tickers"]])
        print(f"prices: {msg}")
        for e in snap["tickers"]:
            if e["ticker"] in ms.index:
                st = ms.loc[e["ticker"]]
                old = e.get("stats") or {}
                old.update({k: (None if st.get(k) is None or st.get(k) != st.get(k) else round(float(st.get(k)), 4))
                            for k in ["close", "ret_1d", "ret_5d", "ret_20d", "ret5_z", "vol5_z", "vol_ratio_5d", "sma50", "maxdd20", "adv20"]})
                old["last_date"] = st.get("last_date")
                e["stats"] = old
        from . import extras, briefing
        extras.decision(snap, snap["status"])
        extras.collectors(snap, snap["status"])
        extras.flags(snap, snap["status"])
        categories.apply(snap)
        briefing.apply(snap)
        snap["status"]["Kategorier (Kjøp/Hold/Watchlist)"] = "ok (" + ", ".join(f"{categories.CAT_NO[k]}: {v}" for k, v in snap["categories_meta"]["counts"].items()) + ")"
        txt = json.dumps(snap, indent=1, default=str)
        p.write_text(txt); (DATA / "snapshots" / f"{snap['date']}.json").write_text(txt)
        print(report.write(snap)); print(site.build(snap))
    elif a.cmd == "backtest":
        if a.which == "kontroll":   # random-data control (null_control.py) -> reports/kontroll.json (commit it)
            from . import null_control
            r = null_control.build()
            print(json.dumps({k: {"n": v.get("n"), "mean": v.get("mean")} for k, v in r.items() if not k.startswith("_")}, indent=1, ensure_ascii=False))
        else:
            from .backtest import run_all
            run_all(a.which)
    elif a.cmd == "serve":
        import http.server, functools, socketserver
        from .config import ROOT
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "site"))
        with socketserver.TCPServer(("0.0.0.0", a.port), h) as srv:
            print(f"serving http://localhost:{a.port}/")
            srv.serve_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
