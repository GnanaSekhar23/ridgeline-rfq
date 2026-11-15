"""What the model must return: ONE flat object, fields in the order the model should think.

Strict structured outputs generate fields in schema order, so order is behaviour:
  reasoning      first: who is writing to whom and what they want (before any label)
  classification then the label, informed by the reasoning
  needs_review / review_reason
  sheet_decisions  which sheets of a multi-sheet workbook count, before listing lines
  line_items     last, capped in length (runaway protection)

The model never types `raw` for text/table lines — it points at a row id and code copies the
real text (and qty/uom from table cells). Only lines read from an image carry model-written raw.
Code enforces the rules afterwards (rfq/validate.py): lines on a non-request are dropped,
needs_review is kept only for request types, a request with no lines gets needs_review.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from rfq.config import MATCHER_ENABLED, MAX_LINE_ITEMS

Uom = Literal["EA", "FT", "M", "IN", "BX", "PK", "PR", "DZ", "RL", "LB", "SET", "GAL", "BAG", "CS"]
Classification = Literal[
    "rfq", "rfq_revision", "purchase_order", "vendor_quote", "status_inquiry", "auto_reply", "other"
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _choice(name: str):
    """Literal of the catalog's own values for `name`, plus "other" (stated but not stocked)."""
    from rfq.catalog import vocab

    values = tuple(vocab().get(name, ())) + ("other",)
    return Literal[values]  # type: ignore[valid-type]


class Attrs(_Strict):
    """The line normalized into the catalog's vocabulary. Code — not the model — picks the part.
    null = the customer did not state it; "other" = stated, but not one of the listed values."""

    product: _choice("product") | None = Field(description="What the item is, in catalog terms.")
    size: str | None = Field(
        description='Nominal size in inches, no quote marks: "2", "1-1/2", "3/4"; reducing "6 x 4"; '
        'bolts "diameter x length" without thread pitch ("3/4 x 4-1/2"); nipples "3/4 x 6" or "3/4 x close".'
    )
    spec: _choice("spec") | None = Field(description="Schedule or pressure class / rating as stated.")
    material: _choice("material") | None = Field(description="Material / grade as stated or clearly applied.")
    ends: _choice("ends") | None = Field(description="End or face type as stated (THD, BW, SW, RF, PE ...).")
    extra: _choice("extra") | None = Field(
        description="A distinguishing option as stated (LR, full port, 13CR trim ...). Not cosmetic details "
        "like 'STD bore', 'black', 'random lengths'."
    )


class _LineBase(_Strict):
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


# The model-facing line. With the matcher on, each line also carries `attrs` (last field).
# Both variants are named "LineOut" so each produces exactly the schema its cache was recorded with.
if MATCHER_ENABLED:
    LineOut = create_model(
        "LineOut", __base__=_LineBase,
        attrs=(Attrs, Field(description="The item in catalog terms, from what the email says about it.")),
    )
else:
    LineOut = create_model("LineOut", __base__=_LineBase)


class SheetDecision(_Strict):
    file: str = Field(description="Workbook filename.")
    relation: Literal["sections", "versions", "unclear"] = Field(
        description="sections = parts of one order (use all); versions = revisions of one list "
        "(use only the newest); unclear = cannot tell."
    )
    sheets_used: list[str] = Field(description="Sheet names the lines were taken from.")
    why: str = Field(description="One short sentence: the evidence (sheet names, dates, file name, email text).")


class Extraction(_Strict):
    reasoning: str = Field(
        description="At most 3 short sentences: who is writing to whom, and what they want. "
        "Do not list items here."
    )
    classification: Classification
    needs_review: bool = Field(
        description="true if something asked for cannot be fully read or resolved from this email."
    )
    review_reason: str | None = Field(description="Why, when needs_review is true; else null.")
    sheet_decisions: list[SheetDecision] = Field(
        description="One entry per workbook with 2+ visible sheets. Empty list otherwise."
    )
    line_items: list[LineOut] = Field(
        max_length=MAX_LINE_ITEMS,
        description="The items being asked for. Empty for vendor_quote, status_inquiry, auto_reply, other.",
    )


def response_format() -> dict:
    from openai.lib._pydantic import to_strict_json_schema

    return {
        "type": "json_schema",
        "json_schema": {"name": "extraction", "strict": True, "schema": to_strict_json_schema(Extraction)},
    }
