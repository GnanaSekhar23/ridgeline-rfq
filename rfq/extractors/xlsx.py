"""Excel (.xlsx/.xlsm) -> Doc. Row ids: <file>!<sheet>!R<row> (unique across workbooks).

Keeps what an ISR would use: sheet names (often carry the spec), merged banner notes,
cell comments. Skips hidden sheets, rows and columns (noted, not silently). Marks struck rows.
"""

from __future__ import annotations

from io import BytesIO

import openpyxl
from openpyxl.utils import get_column_letter

from rfq.config import MAX_ROWS_PER_SHEET
from rfq.extractors.common import fmt_value, row_text
from rfq.models import Doc, Line


def extract_xlsx(name: str, data: bytes) -> Doc:
    doc = Doc(source=name, kind="xlsx")
    wb = openpyxl.load_workbook(BytesIO(data), data_only=True)
    visible = [ws for ws in wb.worksheets if ws.sheet_state == "visible"]
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            doc.notes.append(f"hidden sheet {ws.title!r} skipped")
    if len(visible) > 1:
        doc.notes.append(
            f"{len(visible)} visible sheets, in workbook order: "
            + ", ".join(repr(ws.title) for ws in visible)
        )
    for ws in visible:
        _sheet(ws, doc)
    if not doc.lines:
        doc.notes.append("workbook has no visible content")
    return doc


def _sheet(ws, doc: Doc) -> None:
    hidden_cols = {k for k, d in ws.column_dimensions.items() if d.hidden}
    hidden_rows = {r for r, d in ws.row_dimensions.items() if d.hidden}
    if hidden_rows:
        doc.notes.append(f"sheet {ws.title!r}: {len(hidden_rows)} hidden row(s) skipped")
    if hidden_cols:
        doc.notes.append(f"sheet {ws.title!r}: hidden column(s) {sorted(hidden_cols)} skipped")
    for rng in ws.merged_cells.ranges:
        doc.notes.append(f"sheet {ws.title!r}: merged cells {rng}")

    n_rows = 0
    for row in ws.iter_rows():
        r = row[0].row
        if r in hidden_rows:
            continue
        if n_rows >= MAX_ROWS_PER_SHEET:
            doc.truncated = True
            doc.notes.append(f"sheet {ws.title!r} truncated at {MAX_ROWS_PER_SHEET} rows")
            break
        cells, struck_cells = [], []
        for c in row:
            if get_column_letter(c.column) in hidden_cols:
                continue
            text = fmt_value(c.value)
            cells.append(text)
            font = getattr(c, "font", None)  # MergedCell (non-anchor part of a merge) has no style
            if text and font is not None and font.strike:
                struck_cells.append(c.coordinate)
            if getattr(c, "comment", None) and c.comment.text.strip():
                doc.notes.append(f"{ws.title}!{c.coordinate} comment: {c.comment.text.strip()}")
        filled = [x for x in cells if x]
        if not filled:
            continue
        n_rows += 1
        whole = len(struck_cells) == len(filled)
        doc.lines.append(
            Line(
                row_id=f"{doc.source}!{ws.title}!R{r}",
                text=row_text(cells),
                cells=cells,
                struck=whole,
                note=(f"struck cells: {', '.join(struck_cells)}" if struck_cells and not whole else None),
            )
        )
