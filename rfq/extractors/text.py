"""Plain-text and HTML attachments -> Doc. Row ids: <file>!L<n>."""

from __future__ import annotations

from rfq.config import MAX_TEXT_LINES
from rfq.extractors.common import decode_text
from rfq.mime import html_to_text
from rfq.models import Doc, Line


def _from_text(name: str, kind: str, text: str) -> Doc:
    doc = Doc(source=name, kind=kind)
    for raw in text.splitlines():
        t = " ".join(raw.split())
        if t:
            if len(doc.lines) >= MAX_TEXT_LINES:
                doc.truncated = True
                doc.notes.append(f"truncated at {MAX_TEXT_LINES} lines")
                break
            doc.lines.append(Line(row_id=f"{name}!L{len(doc.lines) + 1}", text=t))
    return doc


def extract_text(name: str, data: bytes) -> Doc:
    return _from_text(name, "text", decode_text(data))


def extract_html(name: str, data: bytes) -> Doc:
    return _from_text(name, "html", html_to_text(decode_text(data)))
