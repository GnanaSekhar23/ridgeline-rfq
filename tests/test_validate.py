"""Model answer -> Result: code owns raw/qty/uom and the drop rules (synthetic data)."""

from __future__ import annotations

from rfq.models import Doc, Email, Line
from rfq.schema import Extraction
from rfq.validate import build_result, normalize_uom


from rfq.config import MATCHER_ENABLED

NO_ATTRS = {"product": None, "size": None, "spec": None, "material": None, "ends": None, "extra": None}


def _ln(row_id, raw, desc="d", qty=None, uom=None, image=None):
    d = {"row_id": row_id, "image": image, "raw": raw, "description": desc, "qty": qty, "uom": uom}
    if MATCHER_ENABLED:
        d["attrs"] = NO_ATTRS
    return d


def _ans(kind, lines, **kw):
    return Extraction.model_validate({
        "reasoning": "r", "classification": kind, "needs_review": kw.get("review", False),
        "review_reason": kw.get("reason"), "sheet_decisions": kw.get("sheets", []), "line_items": lines,
    })


EMAIL = Email(id="T", headers={}, body="")
BODY = Doc(source="body", kind="body", lines=[
    Line("body!B1", "Pricing please: 14 of the 1 inch 45s and 5 unions same size"),
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
        _ln("body!B1", "14 of the 1 inch 45s", qty=14),
        _ln("body!B1", "5 unions same size", qty=5),
        _ln("body!B2", "four gate valves 2 inch", qty=4, uom="EA"),  # not a fragment of the line
    ]))
    assert [li.raw for li in r.line_items] == ["14 of the 1 inch 45s", "5 unions same size", "4 ea 2in gate valve"]


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


def test_non_request_lines_and_review_flag_are_dropped(caplog) -> None:
    for kind in ("vendor_quote", "status_inquiry", "auto_reply", "other"):
        ans = _ans(kind, [_ln("body!B2", "4 ea 2in gate valve", qty=4)], review=True, reason="x")
        with caplog.at_level("INFO"):
            r = build_result(EMAIL, DOCS, ans, problems=["x.pdf: broken"])
        assert r.classification == kind and r.line_items == [] and not r.needs_review and r.review_reason is None
    assert "dropped" in caplog.text


def test_read_problems_force_review_on_a_request() -> None:
    r = build_result(EMAIL, DOCS, _ans("rfq", [_ln("body!B2", "4 ea 2in gate valve", qty=4)]),
                     problems=["rfq.pdf: PDF is password-protected"])
    assert r.needs_review and "password-protected" in r.review_reason and r.line_items


def test_list_at_the_item_cap_is_flagged(monkeypatch) -> None:
    import rfq.validate as v

    monkeypatch.setattr(v, "MAX_LINE_ITEMS", 2)
    r = build_result(EMAIL, DOCS, _ans("rfq", [_ln("body!B2", "4 ea 2in gate valve"), _ln("bom.xlsx!Rev B!R3", "tee")]))
    assert r.needs_review and "limit" in r.review_reason


def test_review_reasons_merge_and_silent_loss_guard() -> None:
    r = build_result(EMAIL, DOCS, _ans("rfq", []))
    assert r.needs_review and "no line items" in r.review_reason
    r = build_result(EMAIL, DOCS, _ans("rfq", [_ln("body!B2", "4 ea 2in gate valve")], review=True,
                                       reason="BOM not attached"), problems=["a.pdf: password-protected"])
    assert r.needs_review and "BOM not attached" in r.review_reason and "password" in r.review_reason


def test_no_answer_is_flagged_request() -> None:
    r = build_result(EMAIL, DOCS, None, model_error="model unavailable")
    assert r.classification == "rfq" and r.needs_review and "model unavailable" in r.review_reason


def test_numbering_problem_detects_skips_and_repeats() -> None:
    from rfq.validate import numbering_problem

    ok = [f"{i} | 4 | EA | 2in | flange" for i in range(1, 8)]
    assert numbering_problem(ok) is None
    skip = [r for r in ok if not r.startswith("4 |")]
    assert "4 missing" in numbering_problem(skip)
    rep = ok[:3] + [ok[2]] + ok[3:]
    assert "3 repeated" in numbering_problem(rep)
    # two sections that each restart at 1 are fine
    assert numbering_problem(ok[:4] + ok[:3]) is None
    # leading quantities, not item numbers: no check
    assert numbering_problem(["8 - 2in elbow", "4 - tee", "6 - nipple", "12 - coupling", "2 - union"]) is None
    # too few numbered lines to judge
    assert numbering_problem(["1 | tee", "3 | cap"]) is None


def test_scan_numbering_gap_forces_review() -> None:
    from rfq.models import ImagePart

    scan = Doc(source="scan.pdf", kind="pdf", images=[ImagePart("scan.pdf page 1", b"x", 1, 1)])
    lines = [_ln(None, f"{i} | 2 | EA | 4in | WN flange", qty=2, image="scan.pdf page 1") for i in (1, 2, 3, 5, 6)]
    r = build_result(EMAIL, [BODY, scan], _ans("rfq", lines))
    assert r.needs_review and "scanned rows may be misread" in r.review_reason and "4 missing" in r.review_reason
    assert len(r.line_items) == 5  # lines are still returned


def test_prompt_carries_the_general_rules() -> None:
    from rfq.prompt import SYSTEM

    for phrase in ("SHORTEST text", "left to right", "must NOT mention the overridden default",
                   "NOT a reason for needs_review"):
        assert phrase in SYSTEM
    assert '\\"' not in SYSTEM  # no stray backslashes in examples


def test_matcher_runs_only_when_lines_carry_attrs() -> None:
    from types import SimpleNamespace

    from rfq.schema import Attrs

    def ans(attrs):
        lo = SimpleNamespace(row_id="body!B2", image=None, raw="4 ea 2in gate valve", description="2in tee",
                             qty=4, uom="EA", **({"attrs": attrs} if attrs is not None else {}))
        return SimpleNamespace(classification="rfq", needs_review=False, review_reason=None,
                               sheet_decisions=[], line_items=[lo])

    plain = build_result(EMAIL, DOCS, ans(None)).line_items[0]
    assert plain.match is None and "match" not in build_result(EMAIL, DOCS, ans(None)).to_json()["line_items"][0]
    m = build_result(EMAIL, DOCS, ans(Attrs(**{**NO_ATTRS, "product": "tee", "size": "2"}))).line_items[0]
    assert m.match == "ambiguous" and m.candidates and m.match_reason


def test_normalize_uom() -> None:
    assert [normalize_uom(x) for x in ("jts", "Feet", "rolls", "PR", "bogus", None)] == ["EA", "FT", "RL", "PR", None, None]


# ---------------------------------------------------------------- image raw + overridden defaults
from rfq.models import ImagePart  # noqa: E402
from rfq.validate import drop_overridden_defaults, identifying_raw  # noqa: E402

PHOTO = Doc(source="photo.jpg", kind="image", images=[ImagePart("photo.jpg", b"x", 1, 1)])


def test_identifying_raw_prefers_a_model_or_part_number_line() -> None:
    assert identifying_raw("ACME PUMPS\nCENTRIFUGAL PUMP\nP/N: CX-4410\n3 HP 460V") == "P/N: CX-4410"
    assert identifying_raw("Zephyr Mfg\nCat# ZB-77Q ball valve\nSize 1in") == "Cat# ZB-77Q ball valve"
    flat = "NORDWAY CO. BUTTERFLY VALVE MODEL: BV-300-X SIZE: 4 IN BODY: CI DISC: SS"
    assert identifying_raw(flat) == "MODEL: BV-300-X"


def test_identifying_raw_falls_back_to_first_code_then_leaves_it() -> None:
    assert identifying_raw("Brightline Fittings\nKX-210 coupling 2in\nKX-220 coupling 3in") == "KX-210 coupling 2in"
    assert identifying_raw("blue handle valve\n2IN threaded") == "blue handle valve\n2IN threaded"  # sizes aren't codes
    for one_row in ("6 - 4in blind flg", "1 | GV-200 gate valve | Note: rush, Ref: job 12"):
        assert identifying_raw(one_row) == one_row  # one scanned row is never cut apart


def test_image_line_raw_trimmed_and_full_reading_kept_in_description() -> None:
    raw = "NORDWAY CO.\nBUTTERFLY VALVE\nMODEL: BV-300-X\nSIZE: 4 IN"
    r = build_result(EMAIL, [BODY, PHOTO], _ans("rfq", [
        _ln(None, raw, desc="butterfly valve, model BV-300-X, 4 in", qty=2, image="photo.jpg")]))
    li = r.line_items[0]
    assert li.raw == "MODEL: BV-300-X"
    assert "NORDWAY" in li.description and "BV-300-X" in li.description


def test_row_lines_raw_is_never_trimmed() -> None:
    doc = Doc(source="body", kind="body", lines=[Line("body!B1", "Model: QX-12\nSize: 2 in")])
    r = build_result(EMAIL, [doc], _ans("rfq", [_ln("body!B1", "Model: QX-12\nSize: 2 in", qty=1)]))
    assert r.line_items[0].raw == "Model: QX-12\nSize: 2 in"


def test_conflicting_banner_schedule_and_class_removed_own_value_kept() -> None:
    desc = "ALL NIPPLES SCH 160 TBE A106 UNLESS NOTED. Nipple, 1in x 4in, SCH XS"
    assert drop_overridden_defaults(desc, "7 | EA | Nipple, 1in x 4in, SCH XS") == \
        "ALL NIPPLES TBE A106 UNLESS NOTED. Nipple, 1in x 4in, SCH XS"
    assert drop_overridden_defaults("weld neck flange, 150# RF (default class 150), 300#",
                                    "2 ea 3in WN flange 300#") == "weld neck flange, RF (default), 300#"
    # a reducer stating two schedules keeps both
    assert drop_overridden_defaults("reducer sch 40 x sch 80, sch 10 default",
                                    "reducer SCH 40 x SCH 80") == "reducer sch 40 x sch 80, default"


def test_description_without_a_conflict_is_untouched() -> None:
    for desc, raw in [
        ("tee, SCH 40, butt weld", "6 tees same"),       # the line states no schedule itself
        ("tee, SCH 40, butt weld", "6 tee SCH 40"),      # same value
        ("flange, class 300 RF", "4 ea 4in flange"),     # the line states no class
        ("gate valve 800#, SCH 80 nipple", "2 gate valve 800#"),  # class agrees; no own schedule
    ]:
        assert drop_overridden_defaults(desc, raw) == desc
    assert drop_overridden_defaults("50 lb bag of cement, 300 psi", "3 bag cement 150#") == \
        "50 lb bag of cement, 300 psi"  # 50 lb is a weight, 300 psi is not a class mark


def test_table_row_with_banner_default_gets_line_value_only() -> None:
    doc = Doc(source="bom.xlsx", kind="xlsx", lines=[
        Line("bom.xlsx!S!R1", "Item | Qty | UOM | Desc", cells=["Item", "Qty", "UOM", "Desc"]),
        Line("bom.xlsx!S!R2", "1 | 2 | EA | Cap SCH 80", cells=["1", "2", "EA", "Cap SCH 80"]),
    ])
    r = build_result(EMAIL, [doc], _ans("rfq", [
        _ln("bom.xlsx!S!R2", "Cap SCH 80", desc="ALL SCH 40 BW. cap, SCH 80", qty=2)]))
    assert r.line_items[0].description == "ALL BW. cap, SCH 80"


# ---------------------------------------------------------------- unit from the quantity's own words
from rfq.validate import uom_from_qty_text  # noqa: E402


def test_uom_from_qty_text_reads_the_word_after_the_quantity() -> None:
    assert uom_from_qty_text('7 jts - 3" black pipe', 7) == "EA"
    assert uom_from_qty_text("need 9 lengths of 1-1/4 conduit", 9) == "EA"
    assert uom_from_qty_text("15 pcs 3/8 washers", 15) == "EA"
    assert uom_from_qty_text("3 lgths 2in galv", 3) == "EA"
    assert uom_from_qty_text("250 feet of 1/2 copper tube", 250) == "FT"
    assert uom_from_qty_text("80' of 3/4 hose", 80) == "FT"
    assert uom_from_qty_text("45 ft 1in poly", 45) == "FT"


def test_uom_from_qty_text_ignores_lengths_sizes_and_unitless_lines() -> None:
    assert uom_from_qty_text("4 - 5/8 x 6 ft threaded rod", 4) is None  # 6 ft is a length, not qty
    assert uom_from_qty_text("2 - 3/4 x 10' sticks", 2) is None            # 10' is a length, not qty
    assert uom_from_qty_text("11 hex plugs 1in", 11) is None               # no unit stated
    assert uom_from_qty_text("some 2' nipples", None) is None              # no qty


def test_unit_filled_only_when_missing() -> None:
    doc = Doc(source="body", kind="body", lines=[Line("body!B1", '7 jts - 3" black pipe'),
                                                 Line("body!B2", "120 ft 1in poly")])
    r = build_result(EMAIL, [doc], _ans("rfq", [_ln("body!B1", '7 jts - 3" black pipe', qty=7),
                                                _ln("body!B2", "120 ft 1in poly", qty=120, uom="EA")]))
    assert [li.uom for li in r.line_items] == ["EA", "EA"]  # filled when null; a uom the model gave is kept


# ---------------------------------------------------------------- item-less request: name what it points at
from rfq.validate import find_references  # noqa: E402


def test_find_references_quote_po_and_earlier_order() -> None:
    assert find_references("Release this against your quotation Q-31-00877 please.") == ["quote Q-31-00877"]
    assert find_references("Go ahead per quote # RX-4410.") == ["quote RX-4410"]
    assert find_references("Our P.O. #8820-B covers the list we discussed.") == ["PO 8820-B"]
    assert find_references("Purchase order no. 51007 attached to follow") == ["PO 51007"]
    assert find_references("Need the same as last time, ship Friday") == ['an earlier order ("same as last time")']
    assert find_references("Please repeat our last order for the plant") == \
        ['an earlier order ("repeat our last order")']
    both = find_references("PO 4417 against your quote Q-31-00877")
    assert both == ["quote Q-31-00877", "PO 4417"]


def test_find_references_ignores_plain_words() -> None:
    for text in ("Thanks for the quote, we'll be in touch", "Ship to PO Box 12, Port Allen",
                 "Port 5 gate, deliver before noon", "Please quote the attached list"):
        assert find_references(text) == [], text


def test_itemless_request_names_its_reference_else_generic() -> None:
    ref = Email(id="T", headers={}, body="Treat this as PO 66120 against your quote Q-31-00877.")
    r = build_result(ref, [], _ans("purchase_order", []))
    assert r.needs_review and r.review_reason == \
        "refers to quote Q-31-00877, PO 66120; its items are not in this email"
    fwd = Email(id="T", headers={}, body="see below", forwarded="Same as before, 2 trucks")
    assert "same as before" in build_result(fwd, [], _ans("rfq", [])).review_reason
    plain = Email(id="T", headers={}, body="Can you price this for us?")
    assert build_result(plain, [], _ans("rfq", [])).review_reason == \
        "classified as a request but no line items could be extracted"
