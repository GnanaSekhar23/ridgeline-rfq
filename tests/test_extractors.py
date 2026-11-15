"""Extractor tests on small synthetic files built in the test (no dev data)."""

from __future__ import annotations

from io import BytesIO

import docx
import openpyxl
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from openpyxl.comments import Comment
from openpyxl.styles import Font
from PIL import Image

from rfq.extractors import extract_all, extract_attachment
from rfq.extractors.csv_ import extract_csv
from rfq.extractors.docx_ import extract_docx
from rfq.extractors.image import extract_image
from rfq.extractors.pdf import extract_pdf
from rfq.extractors.xlsx import extract_xlsx
from rfq.models import Attachment, Email

# ---------------------------------------------------------------- builders


def _xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Fittings SCH 80"
    ws["A1"] = "ALL CS UNLESS NOTED"
    ws.merge_cells("A1:C1")
    ws.append(["Qty", "Size", "Item"])
    ws.append([10, '2"', "Tee"])
    ws.append([4.0, '3"', "Cap"])
    for c in ws[4]:
        c.font = Font(strike=True)  # whole row struck
    ws.append([6, '1"', "Union"])
    ws["C5"].font = Font(strike=True)  # one cell struck
    ws.append([99, '9"', "hidden row item"])
    ws.row_dimensions[6].hidden = True
    ws["C3"].comment = Comment("galvanized please", "x")
    old = wb.create_sheet("Rev A")
    old.append([1, '2"', "old tee"])
    old.sheet_state = "hidden"
    wb.create_sheet("Pipe").append([100, "FT", '2"', "pipe"])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _docx() -> bytes:
    d = docx.Document()
    d.add_paragraph("Material list")
    d.add_heading("Valves - 800# A105", level=2)
    t = d.add_table(rows=3, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Qty", "Item"
    t.cell(1, 0).text, t.cell(1, 1).text = "4", "gate valve"
    t.cell(2, 0).text, t.cell(2, 1).text = "2", "check valve"
    for p in (t.cell(2, 0).paragraphs[0], t.cell(2, 1).paragraphs[0]):
        for r in p.runs:
            r.font.strike = True
    p = d.add_paragraph("keep this ")
    # a tracked deletion inside the paragraph must not appear in the text
    dele = OxmlElement("w:del")
    run = OxmlElement("w:r")
    dt = OxmlElement("w:delText")
    dt.text = "DELETED"
    run.append(dt)
    dele.append(run)
    p._p.append(dele)
    d.add_paragraph("after table")
    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


def _text_pdf(
    lines: list[str], strike_line: int | None = None, picture_pt: int | None = None,
    extra_ops: list[str] | None = None,
) -> bytes:
    """Minimal one-page PDF with Helvetica text; optionally a rule through one line,
    a picture drawn `picture_pt` points square below the text, and raw drawing ops."""
    ops, y = [], 700
    for i, t in enumerate(lines):
        ops.append(f"BT /F1 12 Tf 72 {y} Td ({t}) Tj ET")
        if i == strike_line:
            ops.append(f"0.8 w 70 {y + 4} m 260 {y + 4} l S")
        y -= 20
    if picture_pt:
        ops.append(f"q {picture_pt} 0 0 {picture_pt} 72 80 cm /Im1 Do Q")
    ops += extra_ops or []
    stream = "\n".join(ops).encode()
    pixels = bytes([200, 30, 30]) * 100  # 10x10 RGB
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> /XObject << /Im1 6 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /XObject /Subtype /Image /Width 10 /Height 10 /ColorSpace /DeviceRGB "
        b"/BitsPerComponent 8 /Length %d >>\nstream\n" % len(pixels) + pixels + b"\nendstream",
    ]
    out, offsets = BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    return out.getvalue()


def _png(w: int, h: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def _email(atts: list[Attachment]) -> Email:
    return Email(id="T", headers={}, body="see attached", attachments=atts)


# ---------------------------------------------------------------- xlsx


def test_xlsx_rows_sheets_strike_hidden() -> None:
    doc = extract_xlsx("bom.xlsx", _xlsx())
    by_id = {ln.row_id.removeprefix("bom.xlsx!"): ln for ln in doc.lines}
    assert all(ln.row_id.startswith("bom.xlsx!") for ln in doc.lines)
    assert by_id["Fittings SCH 80!R1"].text == "ALL CS UNLESS NOTED"
    assert by_id["Fittings SCH 80!R3"].text == '10 | 2" | Tee'
    assert by_id["Fittings SCH 80!R3"].cells == ["10", '2"', "Tee"]
    assert by_id["Fittings SCH 80!R4"].struck and by_id["Fittings SCH 80!R4"].text.startswith("4 |")
    assert not by_id["Fittings SCH 80!R5"].struck and "C5" in by_id["Fittings SCH 80!R5"].note
    assert "Fittings SCH 80!R6" not in by_id  # hidden row
    assert "Pipe!R1" in by_id  # second visible sheet kept
    assert not any("old tee" in ln.text for ln in doc.lines)  # hidden sheet skipped
    notes = " ".join(doc.notes)
    assert "hidden sheet 'Rev A'" in notes and "merged cells A1:C1" in notes
    assert "galvanized please" in notes and "2 visible sheets" in notes


def test_two_workbooks_with_same_sheet_name_have_unique_row_ids() -> None:
    def book(item: str) -> bytes:
        wb = openpyxl.Workbook()
        wb.active.title = "Sheet1"
        wb.active.append(["Qty", "Item"])
        wb.active.append([5, item])
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    docs = extract_all(_email([Attachment("pipe.xlsx", mime, book("pipe")),
                               Attachment("valves.xlsx", mime, book("valve"))]))
    ids = [ln.row_id for d in docs for ln in d.lines]
    assert len(ids) == len(set(ids))
    assert "pipe.xlsx!Sheet1!R2" in ids and "valves.xlsx!Sheet1!R2" in ids


def test_all_row_ids_unique_across_mixed_attachments() -> None:
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    atts = [
        Attachment("a.xlsx", mime, _xlsx()),
        Attachment("b.xlsx", mime, _xlsx()),
        Attachment("a.csv", "text/csv", b"Qty,Item\n1,tee\n"),
        Attachment("a.pdf", "application/pdf", _text_pdf(["1 EA tee"])),
        Attachment("a.docx", "application/octet-stream", _docx()),
    ]
    ids = [ln.row_id for d in extract_all(_email(atts)) for ln in d.lines]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------- csv


def test_csv_semicolon_and_cp1252() -> None:
    data = 'Qty;Item\n10;2" 90° elbow\n\n6;tee\n'.encode("cp1252")
    doc = extract_csv("list.csv", data)
    assert [ln.text for ln in doc.lines] == ["Qty | Item", '10 | 2" 90° elbow', "6 | tee"]
    assert doc.lines[2].row_id == "list.csv!R4"  # row numbers follow the file, blanks skipped


# ---------------------------------------------------------------- docx


def test_docx_order_headings_strike_and_tracked_delete() -> None:
    doc = extract_docx("list.docx", _docx())
    texts = [ln.text for ln in doc.lines]
    assert texts.index("Valves - 800# A105") < texts.index("4 | gate valve") < texts.index("after table")
    heading = next(ln for ln in doc.lines if ln.text == "Valves - 800# A105")
    assert heading.style and "Heading" in heading.style
    struck = next(ln for ln in doc.lines if "check valve" in ln.text)
    assert struck.struck and struck.row_id == "list.docx!T1R3"
    assert not any("DELETED" in t for t in texts) and "keep this" in texts


def test_docx_heading_sits_directly_above_its_table_rows() -> None:
    d = docx.Document()
    d.add_paragraph("Job 77 material list")
    sections = [("Pipe - SCH 80 SMLS", [("10 jts", '2"'), ("4 jts", '3"')]),
                ("Fittings - 3000# SW", [("24", '1" 90 elbow'), ("12", '1" tee')])]
    for heading, rows in sections:
        d.add_heading(heading, level=2)
        t = d.add_table(rows=len(rows) + 1, cols=2)
        t.cell(0, 0).text, t.cell(0, 1).text = "Qty", "Item"
        for i, (q, item) in enumerate(rows, start=1):
            t.cell(i, 0).text, t.cell(i, 1).text = q, item
    buf = BytesIO()
    d.save(buf)
    doc = extract_docx("list.docx", buf.getvalue())
    texts = [ln.text for ln in doc.lines]
    assert texts == [
        "Job 77 material list",
        "Pipe - SCH 80 SMLS", "Qty | Item", '10 jts | 2"', '4 jts | 3"',
        "Fittings - 3000# SW", "Qty | Item", '24 | 1" 90 elbow', '12 | 1" tee',
    ]
    assert doc.lines[1].style and doc.lines[5].style  # headings are labelled as headings
    assert [ln.row_id for ln in doc.lines[2:5]] == ["list.docx!T1R1", "list.docx!T1R2", "list.docx!T1R3"]
    assert doc.lines[6].row_id == "list.docx!T2R1"


def test_docx_embedded_picture_sent_logo_skipped() -> None:
    d = docx.Document()
    d.add_paragraph("Items are in the photo below")
    d.add_picture(BytesIO(_png(300, 400)))  # photo of a list
    d.add_picture(BytesIO(_png(500, 60)))  # letterhead banner
    buf = BytesIO()
    d.save(buf)
    doc = extract_docx("photo.docx", buf.getvalue())
    assert len(doc.images) == 1 and doc.images[0].label == "photo.docx picture 1"
    assert any("picture 2" in n and "logo" in n for n in doc.notes)
    assert any("Items are in the photo" in ln.text for ln in doc.lines)


# ---------------------------------------------------------------- pdf


def test_text_pdf_lines_and_strike() -> None:
    doc = extract_pdf("rfq.pdf", _text_pdf(["Material: A105", "10 EA 2in WN flange", "4 EA 3in blind flange"], strike_line=2))
    assert doc.error is None
    by_text = {ln.text: ln for ln in doc.lines}
    assert by_text["10 EA 2in WN flange"].row_id == "rfq.pdf!P1L2"
    assert not by_text["10 EA 2in WN flange"].struck
    assert by_text["4 EA 3in blind flange"].struck


def _ruled_table_ops(rows: list[list[str]], xs: list[int], top: int = 600, row_h: int = 20) -> list[str]:
    """Each cell drawn as its own text object at its column x, with a full grid of rules."""
    ops = []
    right = xs[-1] + 150
    for r, cells in enumerate(rows):
        y_text = top - r * row_h - 14
        for x, cell in zip(xs, cells):
            ops.append(f"BT /F1 10 Tf {x + 3} {y_text} Td ({cell}) Tj ET")
    for r in range(len(rows) + 1):  # horizontal rules on row borders, never through text
        y = top - r * row_h
        ops.append(f"0.5 w {xs[0]} {y} m {right} {y} l S")
    for x in xs + [right]:  # column dividers
        ops.append(f"0.5 w {x} {top} m {x} {top - len(rows) * row_h} l S")
    return ops


def test_pdf_table_is_one_line_per_row() -> None:
    rows = [
        ["ITEM", "QTY", "UOM", "SIZE", "DESCRIPTION"],
        ["1", "12", "EA", "2in", "WELD NECK FLANGE"],
        ["2", "8", "EA", "3in", "BLIND FLANGE"],
        ["3", "40", "FT", "2in", "SCH 80 PIPE"],
    ]
    pdf = _text_pdf(["REQUEST FOR QUOTATION"], extra_ops=_ruled_table_ops(rows, [72, 112, 152, 192, 242]))
    doc = extract_pdf("table.pdf", pdf)
    texts = [ln.text for ln in doc.lines]
    assert texts == [
        "REQUEST FOR QUOTATION",
        "ITEM QTY UOM SIZE DESCRIPTION",
        "1 12 EA 2in WELD NECK FLANGE",
        "2 8 EA 3in BLIND FLANGE",
        "3 40 FT 2in SCH 80 PIPE",
    ]
    assert [ln.row_id for ln in doc.lines[2:]] == ["table.pdf!P1L3", "table.pdf!P1L4", "table.pdf!P1L5"]
    assert not any(ln.struck for ln in doc.lines)  # grid rules on row borders are not strikethrough


def test_text_page_with_large_picture_sends_text_and_image() -> None:
    doc = extract_pdf("mixed.pdf", _text_pdf(["Please quote the items in the photo", "Material: A105"], picture_pt=400))
    assert any("Material: A105" in ln.text for ln in doc.lines)
    assert len(doc.images) == 1 and doc.images[0].label == "mixed.pdf page 1"
    assert any("text and a large picture" in n for n in doc.notes)


def test_text_page_with_small_picture_sends_text_only() -> None:
    doc = extract_pdf("logo.pdf", _text_pdf(["10 EA 2in WN flange", "Material: A105"], picture_pt=40))
    assert doc.lines and not doc.images


def test_scanned_pdf_becomes_images() -> None:
    buf = BytesIO()
    Image.new("RGB", (400, 500), "white").save(buf, format="PDF")
    doc = extract_pdf("scan.pdf", buf.getvalue())
    assert doc.error is None and not doc.lines
    assert len(doc.images) == 1 and doc.images[0].label == "scan.pdf page 1"


def test_broken_and_encrypted_pdf_are_errors_not_crashes() -> None:
    assert extract_pdf("x.pdf", b"not a pdf at all").error
    enc = extract_pdf("x.pdf", b"%PDF-1.4 garbage /Encrypt 5 0 R garbage")
    assert "password" in enc.error


# ---------------------------------------------------------------- images


def test_inline_logo_skipped_but_attached_photo_kept() -> None:
    logo = extract_image("image001.png", _png(400, 64), inline=True, alt="ACME")
    assert logo.skipped and not logo.images
    shot = extract_image("image002.png", _png(440, 210), inline=True)
    assert not shot.skipped and shot.images
    photo = extract_image("IMG_1.jpg", _png(400, 64), inline=False)  # attached, not inline
    assert photo.images


def test_big_image_downscaled() -> None:
    doc = extract_image("big.png", _png(4000, 3000))
    assert max(doc.images[0].width, doc.images[0].height) <= 2048


# ---------------------------------------------------------------- dispatcher


def test_bad_attachments_never_raise() -> None:
    atts = [
        Attachment("broken.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK\x03\x04junk"),
        Attachment("broken.docx", "application/octet-stream", b"junk"),
        Attachment("photo.jpg", "image/jpeg", b"\xff\xd8junk"),
        Attachment("empty.pdf", "application/pdf", b""),
        Attachment("files.zip", "application/zip", b"PK\x03\x04"),
        Attachment("old.xls", "application/vnd.ms-excel", b"\xd0\xcf\x11\xe0"),
    ]
    docs = extract_all(_email(atts))
    assert docs[0].source == "body"
    errs = {d.source: d.error for d in docs[1:]}
    assert all(errs.values()), errs
    assert "empty" in errs["empty.pdf"] and "legacy" in errs["old.xls"]


# ---------------------------------------------------------------- limits are always noted


def _scan_pdf(pages: int) -> bytes:
    imgs = [Image.new("RGB", (300, 400), "white") for _ in range(pages)]
    buf = BytesIO()
    imgs[0].save(buf, format="PDF", save_all=True, append_images=imgs[1:])
    return buf.getvalue()


def test_pdf_page_cap_is_noted(monkeypatch) -> None:
    import rfq.extractors.pdf as pdfmod

    monkeypatch.setattr(pdfmod, "MAX_PDF_PAGES", 1)
    doc = extract_pdf("long.pdf", _scan_pdf(3))
    assert doc.truncated and any("3 pages" in n and "first 1" in n for n in doc.notes)


def test_scan_page_cap_is_noted(monkeypatch) -> None:
    import rfq.extractors.pdf as pdfmod

    monkeypatch.setattr(pdfmod, "MAX_SCAN_PAGES", 1)
    doc = extract_pdf("scan.pdf", _scan_pdf(2))
    assert len(doc.images) == 1 and doc.truncated
    assert any("only the first 1 were rendered" in n for n in doc.notes)


def test_per_email_image_cap_is_noted(monkeypatch) -> None:
    import rfq.extractors as ex

    monkeypatch.setattr(ex, "MAX_IMAGES_PER_EMAIL", 1)
    atts = [Attachment(f"IMG_{i}.png", "image/png", _png(300, 400)) for i in range(2)]
    docs = extract_all(_email(atts))
    assert sum(len(d.images) for d in docs) == 1
    assert docs[2].truncated and any("dropped" in n for n in docs[2].notes)


def test_row_cap_is_noted(monkeypatch) -> None:
    import rfq.extractors.csv_ as csvmod

    monkeypatch.setattr(csvmod, "MAX_ROWS_PER_SHEET", 2)
    doc = extract_csv("big.csv", b"a,b\n1,2\n3,4\n5,6\n")
    assert len(doc.lines) == 2 and doc.truncated


def test_nested_depth_limit_is_noted(monkeypatch) -> None:
    from email.message import EmailMessage

    import rfq.extractors as ex

    monkeypatch.setattr(ex, "NESTED_EML_DEPTH", 1)
    inner = EmailMessage()
    inner["From"], inner["Subject"] = "a@b.example", "orig"
    inner.set_content("see attached")
    inner.add_attachment(b"Qty,Item\n3,tee\n", maintype="text", subtype="csv", filename="inner.csv")
    docs = extract_attachment(Attachment("fwd.eml", "message/rfc822", inner.as_bytes()), _email([]))
    assert docs[0].truncated and len(docs) == 1


def test_read_problems_lists_limits_and_errors_but_not_logos(monkeypatch) -> None:
    import rfq.extractors as ex
    import rfq.extractors.pdf as pdfmod

    monkeypatch.setattr(pdfmod, "MAX_PDF_PAGES", 1)
    atts = [
        Attachment("long.pdf", "application/pdf", _scan_pdf(2)),
        Attachment("broken.xlsx", "application/vnd.ms-excel.sheet", b"junk"),
        Attachment("image001.png", "image/png", _png(400, 60), inline=True),
    ]
    problems = ex.read_problems(extract_all(_email(atts)))
    assert len(problems) == 2
    assert any("long.pdf: partly read" in p and "first 1" in p for p in problems)
    assert any(p.startswith("broken.xlsx:") for p in problems)


def test_nested_eml_lines_and_its_attachments() -> None:
    from email.message import EmailMessage

    inner = EmailMessage()
    inner["From"], inner["Subject"] = "a@b.example", "orig"
    inner.set_content("12 ea 2in gate valve")
    inner.add_attachment(b"Qty,Item\n3,tee\n", maintype="text", subtype="csv", filename="inner.csv")
    docs = extract_attachment(Attachment("fwd.eml", "message/rfc822", inner.as_bytes()), _email([]))
    assert docs[0].kind == "eml"
    assert any(ln.row_id == "fwd.eml!B1" and "gate valve" in ln.text for ln in docs[0].lines)
    assert any(d.source == "inner.csv" and d.lines for d in docs)
