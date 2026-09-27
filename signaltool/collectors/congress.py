"""US House Periodic Transaction Reports (STOCK Act) from the House Clerk (free, no key).

Index: https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{YEAR}FD.zip
PDFs:  https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{YEAR}/{DocID}.pdf
Only electronically filed PTRs (text PDFs) are parsed; scanned paper filings are listed but skipped.
Senate eFD requires an interactive terms-acceptance session -> not automated here.
The community S3 datasets (house/senate-stock-watcher) now return 403.
"""
from __future__ import annotations
import io, logging, re, subprocess, zipfile
from datetime import date, timedelta
import pandas as pd
from .. import http
from ..config import CACHE

log = logging.getLogger(__name__)
PDF_DIR = CACHE / "house_ptr"
PDF_DIR.mkdir(parents=True, exist_ok=True)
_OLD_TX_RE = re.compile(r"\(([A-Z][A-Z.\-]{0,6})\)\s*\[(ST|OP|EF|OT|AB|GS|CS|PS|OI)\]\s+(P|S \(partial\)|S|E)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\$[\d,]+(?:\s*-\s*\$?[\d,]*)?)?")


def load_index(year: int) -> pd.DataFrame:
    r = http.get(f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip", cache_hours=12)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    df = pd.read_csv(z.open(f"{year}FD.txt"), sep="\t", dtype=str)
    df["FilingDate"] = pd.to_datetime(df["FilingDate"], format="%m/%d/%Y", errors="coerce")
    return df


TYPE_RE = re.compile(r"\s(P|S \(partial\)|S|E)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(Over \$[\d,]+|\$[\d,]+(?:\s*-\s*\$[\d,]+)?)?")
TICK_RE = re.compile(r"\(([A-Z][A-Z.\-]{0,6})\)")
ATYPE_RE = re.compile(r"\[([A-Z]{2})\]")


def parse_ptr_text(text: str) -> list[dict]:
    """Split the PTR table into blank-line separated blocks; each block = one transaction."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        flat = " " + re.sub(r"\s+", " ", block)
        m = TYPE_RE.search(flat)
        if not m:
            continue
        tk = TICK_RE.findall(flat)
        at = ATYPE_RE.search(flat)
        out.append({"ticker": tk[0] if tk else None, "asset_type": at.group(1) if at else None, "type": m.group(1)[0],
                    "trans_date": m.group(2), "amount": (m.group(4) or "").strip(),
                    "asset": re.sub(r"\s+", " ", flat[:m.start()]).strip()[-80:]})
    return out


def collect(days=45, max_pdfs=80) -> tuple[pd.DataFrame, str]:
    y = date.today().year
    try:
        idx = load_index(y)
    except Exception as e:
        return pd.DataFrame(), f"FAILED index: {e}"
    ptr = idx[(idx["FilingType"] == "P") & (idx["FilingDate"] >= pd.Timestamp(date.today() - timedelta(days=days)))]
    ptr = ptr.sort_values("FilingDate", ascending=False).head(max_pdfs)
    rows, skipped = [], 0
    for _, f in ptr.iterrows():
        doc = str(f["DocID"])
        if not doc.startswith("2"):   # paper/scanned filings have other ID ranges
            skipped += 1; continue
        pdf = PDF_DIR / f"{doc}.pdf"
        url = f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{y}/{doc}.pdf"
        try:
            if not pdf.exists():
                pdf.write_bytes(http.get(url).content)
            text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, timeout=60).stdout
        except Exception as e:
            log.info("ptr %s: %s", doc, e); continue
        member = f"{f.get('First', '')} {f.get('Last', '')} ({f.get('StateDst', '')})"
        for t in parse_ptr_text(text):
            t.update({"member": member, "filing_date": f["FilingDate"].date().isoformat(), "url": url})
            rows.append(t)
    return pd.DataFrame(rows), f"ok ({len(ptr)} PTRs in {days}d, {skipped} scanned skipped, {len(rows)} transactions parsed)"
