"""Small helpers shared by extractors."""

from __future__ import annotations

from datetime import date, datetime


def fmt_value(v: object) -> str:
    """Cell value -> text as a person would read it (12.0 -> "12", dates -> ISO)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:g}"
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == datetime.min.time() else v.isoformat(" ")
    if isinstance(v, date):
        return v.isoformat()
    return " ".join(str(v).split())


def row_text(cells: list[str]) -> str:
    """Cells -> one line. Leading empty cells are kept so columns stay aligned with the header;
    trailing ones are dropped."""
    while cells and not cells[-1]:
        cells = cells[:-1]
    return " | ".join(cells)


def decode_text(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")
