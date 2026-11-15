"""Plain data types shared across the pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Line:
    """One addressable line of text extracted from the email or an attachment."""

    row_id: str  # stable id shown to the model, e.g. "body!B12", "Sheet1!R5", "a.pdf!P1L8"
    text: str
    struck: bool = False  # strikethrough / crossed out in the source
    cells: list[str] | None = None  # table cells, when the line is a table row


@dataclass
class Doc:
    """What an extractor produced from one source. Extractors never raise; they set `error`."""

    source: str  # "body" or the attachment filename
    kind: str  # body | xlsx | csv | docx | pdf | image | html | eml | unknown
    lines: list[Line] = field(default_factory=list)
    images: list[bytes] = field(default_factory=list)  # PNG bytes for vision (scans, photos)
    notes: list[str] = field(default_factory=list)  # context: sheet names, hidden sheets skipped, ...
    error: str | None = None  # set when the source could not be read


@dataclass
class Attachment:
    filename: str
    mime: str
    data: bytes
    inline: bool = False
    content_id: str | None = None


@dataclass
class Email:
    id: str
    headers: dict[str, str | None]
    body: str  # current message text, quoted history removed
    quoted: str = ""  # quoted history (context only, never a line source)
    attachments: list[Attachment] = field(default_factory=list)


@dataclass
class LineItem:
    raw: str
    description: str
    qty: float | None
    uom: str | None
    source: str


@dataclass
class Result:
    classification: str
    revises: str | None = None
    duplicate_of: str | None = None
    needs_review: bool = False
    review_reason: str | None = None
    line_items: list[LineItem] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
