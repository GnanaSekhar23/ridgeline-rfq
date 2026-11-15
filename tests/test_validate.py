"""Model answer -> Result: code owns raw/qty/uom and the drop rules (synthetic data)."""

from __future__ import annotations

from rfq.models import Doc, Email, Line
from rfq.schema import Extraction
from rfq.validate import build_result, normalize_uom


def _ln(row_id, raw, desc="d", qty=None, uom=None, image=None):
    return {"row_id": row_id, "image": image, "raw": raw, "description": desc, "qty": qty, "uom": uom}


def _ans(kind, lines, **kw):
    body = {"kind": kind, "lines": lines, "sheet_decisions": kw.get("sheets", []),
            "needs_review": kw.get("review", False), "review_reason": kw.get("reason"), "rationale": "r"}
    return Extraction.model_validate({"result": body})


EMAIL = Email(id="T", headers={}, body="")
BODY = Doc(source="body", kind="body", lines=[
    Line("body!B1", "Please quote: 10 of the 1/2 90s and 6 tees same size"),
    Line("body!B2", "4 ea 2in gate valve"),
    Line("body!Q1", "8 ea 3in cap"),
])
SHEET = Doc(source="bom.xlsx", kind="xlsx", lines=[
    Line("bom.xlsx!Rev B!R1", "ALL SCH 40", cells=["ALL SCH 40"]),
    Line("bom.xlsx!Rev B!R2", "Item | Qty | UOM | Size", cells=["Item", "Qty", "UOM", "Size"]),
    Line("bom.xlsx!Rev B!R3", 'Tee | 12 | EA | 2"', cells=["Tee", "12", "EA", '2"']),
    Line("bom.xlsx!Rev B!R4", 'Cap | 3 | EA | 2"', cells=["Cap", "3", "EA", '2"'], struck=True),
    Line("bom.xlsx!Rev B!R5", 'Pipe | 40 ft | | 2"', cells=["Pipe", "40 ft", "", '2"']),
    Line("bom.xlsx!Rev A!R3", 'Tee | 8 | EA | 2"', cells=["Tee", "8", "EA", '2"']),
])
DOCS = [BODY, SHEET]


def test_table_row_raw_qty_uom_come_from_cells_not_model() -> None:
    r = build_result(EMAIL, DOCS, _ans("rfq", [_ln("bom.xlsx!Rev B!R3", "tee twelve", qty=99, uom="FT")]))
    li = r.line_items[0]
    assert (li.raw, li.qty, li.uom, li.source) == ('Tee | 12 | EA | 2"', 12, "EA", "bom.xlsx")


def test_unit_inside_qty_cell() -> None:
    r = build_result(EMAIL, DOCS, _ans("rfq", [_ln("bom.xlsx!Rev B!R5", "pipe")]))
    assert (r.line_items[0].qty, r.line_items[0].uom) == (40, "FT")


def test_fragment_kept_when_grounded_else_whole_line() -> None:
    r = build_result(EMAIL, DOCS, _ans("rfq", [
        _ln("body!B1", "10 of the 1/2 90s", qty=10),
        _ln("body!B1", "6 tees same size", qty=6),
        _ln("body!B2", "four gate valves 2 inch", qty=4, uom="EA"),  # not a fragment of the line
    ]))
    assert [li.raw for li in r.line_items] == ["10 of the 1/2 90s", "6 tees same size", "4 ea 2in gate valve"]


def test_unknown_struck_and_quoted_rows_dropped_for_rfq() -> None:
    r = build_result(EMAIL, DOCS, _ans("rfq", [
        _ln("body!B9", "invented"), _ln("bom.xlsx!Rev B!R4", "cap"), _ln("body!Q1", "8 ea 3in cap"),
        _ln("body!B2", "4 ea 2in gate valve", qty=4),
    ]))
    assert [li.raw for li in r.line_items] == ["4 ea 2in gate valve"]


def test_quoted_rows_allowed_for_revision_and_po() -> None:
    for kind in ("rfq_revision", "purchase_order"):
        r = build_result(EMAIL, DOCS, _ans(kind, [_ln("body!Q1", "8 ea 3in cap", qty=8)]), parent="P1")
        assert [li.raw for li in r.line_items] == ["8 ea 3in cap"]
        assert r.revises == ("P1" if kind == "rfq_revision" else None)


def test_versions_keep_only_newest_sheet_and_unclear_flags() -> None:
    lines = [_ln("bom.xlsx!Rev B!R3", "tee"), _ln("bom.xlsx!Rev A!R3", "tee")]
    sd = {"file": "bom.xlsx", "relation": "versions", "sheets_used": ["Rev B"], "why": "Rev B is newer"}
    r = build_result(EMAIL, DOCS, _ans("rfq", lines, sheets=[sd]))
    assert [li.qty for li in r.line_items] == [12] and not r.needs_review
    sd_unclear = {**sd, "relation": "unclear", "sheets_used": ["Rev B", "Rev A"]}
    r = build_result(EMAIL, DOCS, _ans("rfq", lines, sheets=[sd_unclear]))
    assert r.needs_review and "sections or versions" in r.review_reason and len(r.line_items) == 2


def test_image_lines_keep_model_raw_and_map_source() -> None:
    img = Doc(source="scan.pdf", kind="pdf")
    from rfq.models import ImagePart

    img.images = [ImagePart("scan.pdf page 2", b"x", 1, 1)]
    r = build_result(EMAIL, [BODY, img], _ans("rfq", [_ln(None, "6 - 4in blind flg", qty=6, image="scan.pdf page 2")]))
    assert (r.line_items[0].raw, r.line_items[0].source) == ("6 - 4in blind flg", "scan.pdf")


def test_no_items_kinds_have_no_lines_and_no_review() -> None:
    ans = Extraction.model_validate({"result": {"kind": "vendor_quote", "rationale": "supplier pricing"}})
    r = build_result(EMAIL, DOCS, ans, problems=["x.pdf: broken"])
    assert r.classification == "vendor_quote" and r.line_items == [] and not r.needs_review


def test_review_reasons_merge_and_silent_loss_guard() -> None:
    r = build_result(EMAIL, DOCS, _ans("rfq", []))
    assert r.needs_review and "no line items" in r.review_reason
    r = build_result(EMAIL, DOCS, _ans("rfq", [_ln("body!B2", "4 ea 2in gate valve")], review=True,
                                       reason="BOM not attached"), problems=["a.pdf: password-protected"])
    assert r.needs_review and "BOM not attached" in r.review_reason and "password" in r.review_reason


def test_no_answer_is_flagged_request() -> None:
    r = build_result(EMAIL, DOCS, None, model_error="model unavailable")
    assert r.classification == "rfq" and r.needs_review and "model unavailable" in r.review_reason


def test_normalize_uom() -> None:
    assert [normalize_uom(x) for x in ("jts", "Feet", "rolls", "PR", "bogus", None)] == ["EA", "FT", "RL", "PR", None, None]
