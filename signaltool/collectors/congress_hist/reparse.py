# Re-parse cached PDFs with case-tolerant ticker/owner (old 2015-2017 PDFs have garbled case). No network.
import re, subprocess, sys
import pandas as pd
sys.path.insert(0, "/workspace/signal-tool")
from signaltool.collectors.congress import TYPE_RE, ATYPE_RE
from pathlib import Path
OUT = Path("/workspace/signal-tool/data/congress_hist")
TK = re.compile(r"\(([A-Za-z][A-Za-z.\-]{0,6})\)\s*(?:\[[A-Za-z]{2}\])?")
OWN = re.compile(r"^\s*(?:\d{6,}\s+)?(SP|JT|DC)\s", re.I)
tx = pd.read_parquet(OUT / "transactions.parquet")
docs = tx.drop_duplicates("doc_id").set_index("doc_id")
rows = []
for doc, f in docs.iterrows():
    text = subprocess.run(["pdftotext", "-layout", str(OUT / "pdfs" / f"{doc}.pdf"), "-"], capture_output=True, text=True).stdout
    for block in re.split(r"\n\s*\n", text):
        flat = " " + re.sub(r"\s+", " ", block); m = TYPE_RE.search(flat)
        if not m: continue
        head = flat[:m.start()]; tks = TK.findall(head); at = ATYPE_RE.search(flat)
        om = OWN.match(block.lstrip("\n").split("\n")[0])
        rows.append({"member": f.member, "state": f.state, "owner": om.group(1).upper() if om else None,
            "ticker": tks[-1].upper() if tks else None, "ticker_case_fixed": bool(tks) and tks[-1] != tks[-1].upper(),
            "asset": re.sub(r"\s+", " ", head).strip()[-120:], "asset_type": at.group(1) if at else None,
            "type": m.group(1)[0], "trans_date": m.group(2), "filing_date": f.filing_date,
            "amount": (m.group(4) or "").strip(), "doc_id": doc, "url": f.url, "year": f.year})
d = pd.DataFrame(rows); print(len(tx), "->", len(d))
d.to_parquet(OUT / "transactions.parquet"); d.to_csv(OUT / "transactions.csv", index=False)
