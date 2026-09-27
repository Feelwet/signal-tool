"""Historical validation of signals. Results are written to reports/backtest.md (never fabricated:
every number is computed from downloaded data, with sample sizes and caveats)."""
from __future__ import annotations
from ..config import REPORTS


def run_all(which="all"):
    parts = []
    if which in ("insider", "all"):
        from . import insider
        parts.append(insider.run())
    if which in ("gdelt", "all"):
        from . import gdelt_theme
        parts.append(gdelt_theme.run())
    p = REPORTS / "backtest.md"
    old = p.read_text() if p.exists() else ""
    if which != "all" and old:
        # replace only the section that was re-run
        import re
        for sec in parts:
            head = sec.splitlines()[0]
            if head in old:
                old = re.sub(re.escape(head) + r".*?(?=\n## |\Z)", sec.replace("\\", "\\\\"), old, flags=re.S)
            else:
                old += "\n\n" + sec
        p.write_text(old)
    else:
        p.write_text("# Backtest / historisk validering\n\n_Alle tall er beregnet fra nedlastede data; ingen tall er manuelt satt inn. "
                     "Resultater er ikke garanti for fremtiden._\n\n" + "\n\n".join(parts))
    print(p)
