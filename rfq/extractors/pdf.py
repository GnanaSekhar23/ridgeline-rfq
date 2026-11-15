"""PDF -> Doc. Text pages -> lines (<file>!P<page>L<n>); pages with no text layer -> images.

Encrypted PDFs we cannot open come back as an error (needs review), never a crash.
Struck lines are detected geometrically: a horizontal rule through the middle of the text.
"""

from __future__ import annotations

from io import BytesIO

import pdfplumber
import pypdfium2 as pdfium

from rfq.config import (MAX_PDF_PAGES, MAX_SCAN_PAGES, SCAN_DPI, SCAN_STRIP_HEIGHT_PX,
                        SCAN_STRIP_OVERLAP_PX)
from rfq.extractors.image import to_png
from rfq.models import Doc, ImagePart, Line

MIN_TEXT_CHARS = 20  # fewer chars than this on a page = treat it as a scan
LARGE_PICTURE_FRACTION = 0.20  # a picture covering this much of a text page is rendered too


def _h_segments(page) -> list[tuple[float, float, float]]:
    """Horizontal strokes on the page as (x0, x1, y_middle) in top-down coordinates."""
    segs = []
    for ln in page.lines:
        if abs(ln["top"] - ln["bottom"]) < 1.5:
            segs.append((min(ln["x0"], ln["x1"]), max(ln["x0"], ln["x1"]), (ln["top"] + ln["bottom"]) / 2))
    for r in page.rects:
        if r["height"] < 2.0 and r["width"] > 5:
            segs.append((r["x0"], r["x1"], (r["top"] + r["bottom"]) / 2))
    return segs


def _struck(line: dict, segs) -> bool:
    top, bottom, x0, x1 = line["top"], line["bottom"], line["x0"], line["x1"]
    h = bottom - top
    width = max(x1 - x0, 1.0)
    for sx0, sx1, sy in segs:
        if top + 0.3 * h <= sy <= bottom - 0.3 * h:
            overlap = min(x1, sx1) - max(x0, sx0)
            if overlap >= 0.6 * width:
                return True
    return False


def _open_error(data: bytes, e: Exception) -> str:
    if b"/Encrypt" in data:
        return "PDF is password-protected / encrypted and cannot be opened"
    return f"PDF could not be opened ({type(e).__name__})"


def extract_pdf(name: str, data: bytes) -> Doc:
    doc = Doc(source=name, kind="pdf")
    try:
        pdf = pdfplumber.open(BytesIO(data))
    except Exception as e:
        doc.error = _open_error(data, e)
        return doc
    try:
        scan_pages, mixed = _read_pages(name, pdf, doc)
    except Exception as e:  # some encrypted/corrupt PDFs open lazily and fail on first page
        doc.error = _open_error(data, e)
        return doc
    finally:
        pdf.close()
    if scan_pages:
        _render_scans(name, data, scan_pages, doc, set(mixed))
    if not doc.lines and not doc.images and not doc.error:
        doc.error = "PDF has no readable text or images"
    return doc


def _read_pages(name: str, pdf, doc: Doc) -> tuple[list[int], list[int]]:
    """Read text pages into doc.lines; return (pages to render as images, of which mixed
    text+picture pages)."""
    scan_pages: list[int] = []
    n_pages = len(pdf.pages)
    if n_pages > MAX_PDF_PAGES:
        doc.truncated = True
        doc.notes.append(f"PDF has {n_pages} pages; only the first {MAX_PDF_PAGES} were read")
    mixed: list[int] = []
    for p_idx, page in enumerate(pdf.pages[:MAX_PDF_PAGES], start=1):
        if len(page.chars) < MIN_TEXT_CHARS:
            if page.images or len(page.chars) == 0:
                scan_pages.append(p_idx)
            continue
        if _has_large_picture(page):
            scan_pages.append(p_idx)  # text AND a picture: send both the text and the page image
            mixed.append(p_idx)
        segs = _h_segments(page)
        for n, ln in enumerate(page.extract_text_lines(strip=True), start=1):
            text = " ".join(ln["text"].split())
            if text:
                doc.lines.append(Line(row_id=f"{name}!P{p_idx}L{n}", text=text, struck=_struck(ln, segs)))
    if mixed:
        doc.notes.append(f"page(s) {mixed} have text and a large picture; text and page image both sent")
    return scan_pages, mixed


def _has_large_picture(page) -> bool:
    page_area = float(page.width * page.height) or 1.0
    for im in page.images:
        w = max(0.0, min(im["x1"], page.width) - max(im["x0"], 0))
        h = max(0.0, min(im["bottom"], page.height) - max(im["top"], 0))
        if w * h / page_area >= LARGE_PICTURE_FRACTION:
            return True
    return False


def strip_boxes(height: int, strip_h: int = SCAN_STRIP_HEIGHT_PX,
                overlap: int = SCAN_STRIP_OVERLAP_PX) -> list[tuple[int, int]]:
    """Top-to-bottom (top, bottom) boxes of overlapping strips covering the full height."""
    if height <= strip_h:
        return [(0, height)]
    step = strip_h - overlap
    tops = list(range(0, height - strip_h, step)) + [height - strip_h]
    return [(t, t + strip_h) for t in dict.fromkeys(tops)]


def _render_scans(name: str, data: bytes, pages: list[int], doc: Doc, mixed: set[int] | None = None) -> None:
    """Pure scans -> a low-detail overview + overlapping high-detail strips (the API would
    shrink a whole page; a strip keeps full width resolution). Text pages with a large
    picture -> one high-detail page image."""
    mixed = mixed or set()
    if len(pages) > MAX_SCAN_PAGES:
        doc.truncated = True
        doc.notes.append(f"{len(pages)} pages need images; only the first {MAX_SCAN_PAGES} were rendered")
        pages = pages[:MAX_SCAN_PAGES]
    doc.notes.append(f"page(s) {pages} sent as images")
    pdf = pdfium.PdfDocument(data)
    try:
        for p in pages:
            pil = pdf[p - 1].render(scale=SCAN_DPI / 72).to_pil()
            boxes = strip_boxes(pil.height)
            if p in mixed or len(boxes) == 1:
                png, w, h = to_png(pil)
                doc.images.append(ImagePart(label=f"{name} page {p}", png=png, width=w, height=h))
                continue
            png, w, h = to_png(pil)
            doc.images.append(ImagePart(label=f"{name} page {p} overview", png=png, width=w, height=h, detail="low"))
            for i, (top, bottom) in enumerate(boxes, start=1):
                png, w, h = to_png(pil.crop((0, top, pil.width, bottom)))
                doc.images.append(ImagePart(label=f"{name} page {p} strip {i} of {len(boxes)}",
                                            png=png, width=w, height=h))
            doc.notes.append(f"page {p}: scanned; sent as a low-detail overview + {len(boxes)} "
                             f"overlapping high-detail strips (top to bottom)")
    finally:
        pdf.close()
