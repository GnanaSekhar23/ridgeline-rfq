"""The email's own text -> one Doc with addressable lines.

Row ids: body!B<n> current message, body!F<n> forwarded content, body!Q<n> quoted history.
All three have source "body"; the prefix tells later steps which part a line came from.
"""

from __future__ import annotations

from rfq.config import MAX_TEXT_LINES
from rfq.models import Doc, Email, Line


def _lines(text: str, prefix: str) -> list[Line]:
    out = []
    for raw in text.splitlines():
        t = raw.strip()
        if t:
            out.append(Line(row_id=f"body!{prefix}{len(out) + 1}", text=t))
    return out


def extract_body(email: Email) -> Doc:
    doc = Doc(source="body", kind="body")
    for text, prefix in ((email.body, "B"), (email.forwarded, "F"), (email.quoted, "Q")):
        doc.lines += _lines(text, prefix)
    if len(doc.lines) > MAX_TEXT_LINES:
        doc.lines = doc.lines[:MAX_TEXT_LINES]
        doc.truncated = True
        doc.notes.append(f"body truncated to {MAX_TEXT_LINES} lines")
    if email.body_kind == "none":
        doc.notes.append("email has no text body")
    return doc
