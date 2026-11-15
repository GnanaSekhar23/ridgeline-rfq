"""Plain data types shared across the pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
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
    body: str  # current message text, history removed
    forwarded: str = ""  # forwarded content (counts as the request when one of our reps forwards)
    quoted: str = ""  # quoted reply history (context; source only for revisions / "items 1-3")
    attachments: list[Attachment] = field(default_factory=list)
    sender: str = ""  # bare lower-case address
    internal: bool = False  # sender is one of our own reps
    date: datetime | None = None
    body_kind: str = "text"  # text | html | none — which MIME part the body came from
    image_alts: dict[str, str] = field(default_factory=dict)  # content-id -> HTML alt text


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
