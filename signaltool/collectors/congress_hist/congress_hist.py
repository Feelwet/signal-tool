import faulthandler, signal; faulthandler.register(signal.SIGUSR1)
import sys, re, json, subprocess, logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import pandas as pd
sys.path.insert(0, "/workspace/signal-tool")
from signaltool import http
from signaltool.collectors.congress import load_index, parse_ptr_text, TYPE_RE
from pathlib import Path
OUT = Path("/workspace/signal-tool/data/congress_hist"); PD = OUT / "pdfs"
OLD = Path("/workspace/signal-tool/data/cache/house_ptr")
OWN_RE = re.compile(r"^\s*(?:\d{6,}\s+)?(SP|JT|DC)\s")
def owner_of(block):
    m = OWN_RE.match(block.lstrip("\n").split("\n")[0]); return m.group(1) if m else None
def parse(text):
    out = []
    for block in re.split(r"\n\s*\n", text):
        r = parse_ptr_text(block)
        if r:
            r[0]["owner"] = owner_of(block); out.append(r[0])
    return out
idx = []
for y in range(2013, date.today().year + 1):
    d = load_index(y); d["year"] = y; idx.append(d)
idx = pd.concat(idx); ptr = idx[idx.FilingType == "P"].copy()
print("PTRs", len(ptr), flush=True)
def work(f):
    doc, y = str(f.DocID), f.year
    url = f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{y}/{doc}.pdf"
    pdf = PD / f"{doc}.pdf"
    try:
        if not pdf.exists():
            if (OLD / pdf.name).exists(): pdf.write_bytes((OLD / pdf.name).read_bytes())
            else: pdf.write_bytes(http.get(url).content)
        text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, timeout=60).stdout
    except Exception as e:
        return doc, url, None, f"error:{e}"[:120]
    if len(text.strip()) < 50: return doc, url, None, "scanned_no_text"
    return doc, url, parse(text), None
rows, skipped = [], []
recs = list(ptr.itertuples())
with ThreadPoolExecutor(3) as ex:
    for i, (f, (doc, url, tx, err)) in enumerate(zip(recs, ex.map(work, recs))):
        base = {"member": f"{f.First} {f.Last}".strip(), "state": f.StateDst, "doc_id": doc, "url": url,
                "filing_date": f.FilingDate.date().isoformat() if pd.notna(f.FilingDate) else None, "year": f.year}
        if err: skipped.append({**base, "reason": err})
        else:
            if not tx: skipped.append({**base, "reason": "text_but_no_tx_parsed"})
            for t in tx: rows.append({**base, **t})
        if i % 500 == 0: print(i, len(rows), len(skipped), flush=True)
tx = pd.DataFrame(rows); sk = pd.DataFrame(skipped)
tx.to_parquet(OUT / "transactions.parquet"); tx.to_csv(OUT / "transactions.csv", index=False)
sk.to_csv(OUT / "skipped.csv", index=False)
ptr["member"] = (ptr.First.fillna("") + " " + ptr.Last.fillna("")).str.strip()
tot = ptr.groupby(["member", "StateDst", "year"]).size().rename("ptrs")
s = sk[sk.reason == "scanned_no_text"].groupby(["member", "state", "year"]).size().rename("skipped") if len(sk) else pd.Series(dtype=int)
s.index.names = tot.index.names
by = pd.concat([tot, s], axis=1).fillna(0).astype(int).reset_index(); by.to_csv(OUT / "skipped_by_member_year.csv", index=False)
m = by.groupby(["member", "StateDst"])[["ptrs", "skipped"]].sum().reset_index(); m["share"] = m.skipped / m.ptrs
m[m.share > 0.10].sort_values("share", ascending=False).to_csv(OUT / "member_flags.csv", index=False)
print("DONE", len(ptr), len(tx), len(sk), flush=True)
