"""Recover tickers for congress PTR rows ONLY where literally printed in the PDF text.

Rules: find the asset name (first 25 chars, owner/[XX] code stripped) in `pdftotext -layout`
output, scan that line plus up to 4 following lines (stop at a date, Filing status,
Description or Comments). Accept only a parenthesised token like "(XXX)"; mixed case is
uppercased and marked. More than one distinct candidate -> "conflict", no ticker.
Never looks tickers up by name. Original value kept in ticker_orig.
"""
import functools, re, subprocess, sys
from pathlib import Path
import pandas as pd

DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")
TK = re.compile(r"\(([A-Za-z][A-Za-z0-9]{0,5}(?:[.\-/][A-Za-z]{1,2})?)\)")
STOP = re.compile(r"filing status|description|comments", re.I)
BAD = {"PARTIAL", "FULL", "NEW", "AMENDED", "THE", "LLC", "INC", "LP", "ETF", "ADR", "USD", "CDS"}


def _strip(a):
    a = re.sub(r"^\s*(\d{6,}\s+)?(SP|JT|DC)\s+", "", a, flags=re.I)
    return re.sub(r"\s*\[\w\w\]\s*$", "", a)


def find_ticker(lines, asset):
    key = _strip(str(asset))[:25].strip()
    if len(key) < 4:
        return None, None
    out, rules = set(), set()
    for i, l in enumerate(lines):
        p = l.lower().find(key.lower())
        if p < 0:
            continue
        seg = [l[p:]]
        for j in range(i + 1, min(i + 5, len(lines))):
            if DATE.search(lines[j]) or STOP.search(lines[j]):
                break
            seg.append(lines[j])
        for k, s in enumerate(seg):
            for m in TK.finditer(s):
                t = m.group(1)
                if t.upper() in BAD:
                    continue
                out.add(t.upper())
                rules.add(("same_line" if k == 0 else "next_line") + ("_mixedcase" if t != t.upper() else ""))
    if len(out) == 1:
        return out.pop(), "paren:" + "|".join(sorted(rules))
    if len(out) > 1:
        return None, "conflict"
    return None, None


def recover(df, pdf_dir):
    pdf_dir = Path(pdf_dir)

    @functools.lru_cache(None)
    def text(doc):
        return subprocess.run(["pdftotext", "-layout", str(pdf_dir / f"{doc}.pdf"), "-"],
                              capture_output=True, text=True).stdout.split("\n")

    df = df.copy()
    if "ticker_orig" not in df:
        df["ticker_orig"] = df["ticker"]
    df["ticker_recovered"] = False
    df["recovery_rule"] = None
    miss = df.ticker.isna() | (df.ticker.astype(str).str.strip() == "")
    for i, r in df[miss].iterrows():
        t, rule = find_ticker(text(r.doc_id), r.asset)
        df.at[i, "recovery_rule"] = rule
        if t:
            df.at[i, "ticker"] = t
            df.at[i, "ticker_recovered"] = True
    return df


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/congress_hist")
    d = recover(pd.read_parquet(out / "transactions.parquet"), out / "pdfs")
    d.to_parquet(out / "transactions.parquet", index=False)
    print(d.recovery_rule.value_counts())
