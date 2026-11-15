"""What the model must return: one of four shapes, chosen by `kind` (a discriminated union).

The model never types `raw` for text/table lines — it points at a row id and code copies the
real text (and qty/uom from table cells). Only lines read from an image carry model-written
`raw`, because there is no text to point at.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

Uom = Literal["EA", "FT", "M", "IN", "BX", "PK", "PR", "DZ", "RL", "LB", "SET", "GAL", "BAG", "CS"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LineOut(_Strict):
    row_id: str | None = Field(
        description="The [row id] of the text/table line this item is on. null only for items read from an image."
    )
    image: str | None = Field(
        description="For items read from an image: the image label exactly as given. Otherwise null."
    )
    raw: str = Field(
        description="The item's text as written. For a row id: the part of that line that is this item "
        "(the whole line if it holds one item). For an image: your transcription of that line."
    )
    description: str = Field(
        description="The item self-contained: its own words plus every heading, note, column header, "
        "sheet name, form field or subject line that applies to it, and nothing that does not."
    )
    qty: float | None = Field(description="Quantity as stated; null if vague ('a couple') or missing.")
    uom: Uom | None = Field(description="Unit as stated, mapped to the allowed list; null if none stated.")


class SheetDecision(_Strict):
    file: str = Field(description="Workbook filename.")
    relation: Literal["sections", "versions", "unclear"] = Field(
        description="sections = parts of one order (use all); versions = revisions of one list "
        "(use only the newest); unclear = cannot tell."
    )
    sheets_used: list[str] = Field(description="Sheet names the lines were taken from.")
    why: str = Field(description="One short sentence: the evidence (sheet names, dates, file name, email text).")


class _Request(_Strict):
    lines: list[LineOut]
    sheet_decisions: list[SheetDecision] = Field(
        description="One entry per workbook with 2+ visible sheets. Empty list otherwise."
    )
    needs_review: bool = Field(
        description="true if something asked for cannot be fully read or resolved from this email."
    )
    review_reason: str | None = Field(description="Why, when needs_review is true; else null.")
    rationale: str = Field(description="One short sentence: why this classification.")


class RFQ(_Request):
    kind: Literal["rfq"]


class Revision(_Request):
    kind: Literal["rfq_revision"]


class PurchaseOrder(_Request):
    kind: Literal["purchase_order"]


class NoItems(_Strict):
    kind: Literal["vendor_quote", "status_inquiry", "auto_reply", "other"]
    rationale: str = Field(description="One short sentence: why this classification.")


Answer = Annotated[Union[RFQ, Revision, PurchaseOrder, NoItems], Field(discriminator="kind")]


class Extraction(_Strict):
    """Top-level object (structured outputs need an object at the root). Used to VALIDATE."""

    result: Answer


class _ExtractionWire(_Strict):
    """Same shape with a plain union: strict structured outputs accept anyOf, not oneOf/discriminator.
    Used only to build the JSON schema we SEND; the reply is validated with `Extraction`."""

    result: Union[RFQ, Revision, PurchaseOrder, NoItems]


REQUEST_TYPES = (RFQ, Revision, PurchaseOrder)


def response_format() -> dict:
    from openai.lib._pydantic import to_strict_json_schema

    return {
        "type": "json_schema",
        "json_schema": {"name": "extraction", "strict": True, "schema": to_strict_json_schema(_ExtractionWire)},
    }
