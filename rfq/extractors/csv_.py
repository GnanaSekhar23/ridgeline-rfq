"""CSV / TSV -> Doc. Row ids: <file>!R<n> (1-based, header included)."""

from __future__ import annotations

import csv
import io

from rfq.config import MAX_ROWS_PER_SHEET
from rfq.extractors.common import decode_text, row_text
from rfq.models import Doc, Line


def extract_csv(name: str, data: bytes) -> Doc:
    doc = Doc(source=name, kind="csv")
    text = decode_text(data)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel_tab if name.lower().endswith(".tsv") else csv.excel
    for i, row in enumerate(csv.reader(io.StringIO(text), dialect), start=1):
        cells = [" ".join(c.split()) for c in row]
        if not any(cells):
            continue
        if len(doc.lines) >= MAX_ROWS_PER_SHEET:
            doc.truncated = True
            doc.notes.append(f"truncated at {MAX_ROWS_PER_SHEET} rows")
            break
        doc.lines.append(Line(row_id=f"{name}!R{i}", text=row_text(cells), cells=cells))
    return doc
