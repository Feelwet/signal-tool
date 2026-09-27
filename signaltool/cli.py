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
    b = sub.add_parser("backtest", help="run historical validation")
    b.add_argument("which", choices=["insider", "gdelt", "all"], nargs="?", default="all")
    s = sub.add_parser("serve", help="serve site/ locally")
    s.add_argument("--port", type=int, default=8765)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(asctime)s %(name)s %(message)s")
    for n in ("urllib3", "yfinance", "peewee"):
        logging.getLogger(n).setLevel(logging.WARNING)

    from .config import DATA
    if a.cmd == "run":
        from . import pipeline, report
        snap = pipeline.run(fast=a.fast)
        p = report.write(snap)
        print(f"report: {p}")
        if not a.no_site:
            from . import site
            print(f"site: {site.build(snap)}")
    elif a.cmd in ("report", "build-site"):
        snap = json.loads((DATA / "snapshots" / "latest.json").read_text())
        if a.cmd == "report":
            from . import report
            print(report.write(snap))
        else:
            from . import site
            print(site.build(snap))
    elif a.cmd == "backtest":
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
