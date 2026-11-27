"""Publiser AnalBots NBS-test (27.11) som HTML under site/tester/. Kilden er tester/nbs_test_2711.md."""
from __future__ import annotations

import re
from html import escape as E
from pathlib import Path

from .config import ROOT

SRC = ROOT / "tester" / "nbs_test_2711.md"
DEST_REL = Path("tester") / "nbs_test_2711.html"


def md_to_html(text: str) -> str:
    """Enkel, deterministisk omforming av denne rapportens markdown (overskrifter, tabell, fet, kode)."""
    lines = text.replace("\r\n", "\n").split("\n")
    out, i, n = [], 0, len(lines)

    def inline(s: str) -> str:
        parts, last = [], 0
        for m in re.finditer(r"`([^`]+)`|\*\*([^*]+)\*\*", s):
            parts.append(E(s[last:m.start()]))
            if m.group(1) is not None:
                parts.append(f"<code>{E(m.group(1))}</code>")
            else:
                parts.append(f"<strong>{E(m.group(2))}</strong>")
            last = m.end()
        parts.append(E(s[last:]))
        return "".join(parts)

    def is_table_row(s: str) -> bool:
        t = s.strip()
        return t.startswith("|") and t.endswith("|") and t.count("|") >= 2

    def is_sep(s: str) -> bool:
        t = s.strip().strip("|").replace(" ", "")
        return bool(t) and all(ch in "-:" for ch in t.replace("|", ""))

    def cells(s: str) -> list[str]:
        raw = s.strip().strip("|").split("|")
        return [c.strip() for c in raw]

    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("# "):
            out.append(f"<h1>{inline(line[2:].strip())}</h1>")
            i += 1
            continue
        if line.startswith("## "):
            out.append(f"<h2>{inline(line[3:].strip())}</h2>")
            i += 1
            continue
        if line.startswith("### "):
            out.append(f"<h3>{inline(line[4:].strip())}</h3>")
            i += 1
            continue
        if is_table_row(line):
            rows = []
            while i < n and is_table_row(lines[i]):
                rows.append(lines[i])
                i += 1
            body = rows
            if len(rows) >= 2 and is_sep(rows[1]):
                head, body = rows[0], rows[2:]
                out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells(head)) + "</tr></thead><tbody>")
            else:
                out.append("<table><tbody>")
            for r in body:
                if is_sep(r):
                    continue
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells(r)) + "</tr>")
            out.append("</tbody></table>")
            continue
        if line.startswith("- "):
            out.append("<ul>")
            while i < n and lines[i].startswith("- "):
                out.append(f"<li>{inline(lines[i][2:].strip())}</li>")
                i += 1
            out.append("</ul>")
            continue
        # paragraph: join until blank
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not lines[i].startswith("#") and not lines[i].startswith("- ") and not is_table_row(lines[i]):
            buf.append(lines[i])
            i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
    return "\n".join(out)


def write(site: Path, page, snap=None) -> Path:
    """Skriv HTML-rapporten inn i den bygde siden (site/ tømmes ved hver build)."""
    md = SRC.read_text()
    if "/workspace" in md:
        raise ValueError("publisert rapport inneholder /workspace-referanse")
    body = '<div class="card nbs-test">' + md_to_html(md) + "</div>"
    dest = Path(site) / DEST_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page("NBS-test 27.11", body, 1, snap))
    return dest
