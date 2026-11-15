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
    struck: bool = False  # the whole line is struck through / deleted in the source
    cells: list[str] | None = None  # table cells, when the line is a table row
    style: str | None = None  # e.g. "Heading 2" for a Word heading
    note: str | None = None  # e.g. "struck cells: C5" when only part of a row is struck


@dataclass
class ImagePart:
    """A picture the model should look at (scan page, photo, pasted screenshot)."""

    label: str  # e.g. "IMG_1.jpg" or "scan.pdf page 2"
    png: bytes
    width: int
    height: int


@dataclass
class Doc:
    """What an extractor produced from one source. Extractors never raise; they set `error`."""

    source: str  # "body" or the attachment filename — what goes in line_items[].source
    kind: str  # body | xlsx | csv | docx | pdf | image | html | eml | text | unknown
    lines: list[Line] = field(default_factory=list)
    images: list[ImagePart] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # context: sheet names, hidden sheets skipped, ...
    error: str | None = None  # set when the source could not be read at all
    truncated: bool = False  # part of the source was dropped (page cap, size cap)
    skipped: bool = False  # deliberately not used (e.g. logo image) — not an error


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
