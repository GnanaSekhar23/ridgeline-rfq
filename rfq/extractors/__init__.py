"""Dispatch every part of an email to the right extractor. Nothing here ever raises:
a failure becomes a Doc with `error` set, which later turns into needs_review."""

from __future__ import annotations

import logging
from pathlib import PurePath

from rfq.config import MAX_ATTACHMENT_BYTES, MAX_IMAGES_PER_EMAIL, NESTED_EML_DEPTH
from rfq.extractors.body import extract_body
from rfq.extractors.csv_ import extract_csv
from rfq.extractors.docx_ import extract_docx
from rfq.extractors.image import extract_image
from rfq.extractors.pdf import extract_pdf
from rfq.extractors.text import extract_html, extract_text
from rfq.extractors.xlsx import extract_xlsx
from rfq.models import Attachment, Doc, Email, Line

log = logging.getLogger(__name__)

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"}


def _kind(att: Attachment) -> str:
    ext = PurePath(att.filename).suffix.lower()
    mime = att.mime.lower()
    if ext in (".xlsx", ".xlsm") or "spreadsheetml" in mime:
        return "xlsx"
    if ext == ".xls" or mime == "application/vnd.ms-excel":
        return "xls"
    if ext in (".csv", ".tsv") or mime in ("text/csv", "text/tab-separated-values"):
        return "csv"
    if ext == ".docx" or "wordprocessingml" in mime:
        return "docx"
    if ext == ".doc" or mime == "application/msword":
        return "doc"
    if ext == ".pdf" or mime == "application/pdf":
        return "pdf"
    if ext in IMAGE_EXT or mime.startswith("image/"):
        return "image"
    if ext == ".eml" or mime == "message/rfc822":
        return "eml"
    if ext in (".htm", ".html") or mime == "text/html":
        return "html"
    if ext in (".txt", ".text") or mime == "text/plain":
        return "text"
    return "unknown"


def _alt_for(att: Attachment, email: Email) -> str:
    return email.image_alts.get(att.content_id or "", "") or email.image_alts.get(att.filename, "")


def extract_attachment(att: Attachment, email: Email, depth: int = 0) -> list[Doc]:
    kind = _kind(att)
    name = att.filename
    if not att.data:
        return [Doc(source=name, kind=kind, error="attachment is empty (0 bytes)")]
    if len(att.data) > MAX_ATTACHMENT_BYTES:
        return [Doc(source=name, kind=kind, error=f"attachment too large ({len(att.data)} bytes)")]
    try:
        if kind == "xlsx":
            return [extract_xlsx(name, att.data)]
        if kind == "csv":
            return [extract_csv(name, att.data)]
        if kind == "docx":
            return [extract_docx(name, att.data)]
        if kind == "pdf":
            return [extract_pdf(name, att.data)]
        if kind == "image":
            return [extract_image(name, att.data, inline=att.inline, alt=_alt_for(att, email))]
        if kind == "html":
            return [extract_html(name, att.data)]
        if kind == "text":
            return [extract_text(name, att.data)]
        if kind == "eml":
            return _extract_eml(att, depth)
        if kind in ("xls", "doc"):
            return [Doc(source=name, kind=kind, error=f"legacy .{kind} format is not supported")]
        return [Doc(source=name, kind=kind, error=f"unsupported attachment type ({att.mime})")]
    except Exception as e:  # corrupt or hostile file: report, never raise
        log.warning("extractor failed on %s/%s: %s", email.id, name, e)
        return [Doc(source=name, kind=kind, error=f"could not read {kind} file ({type(e).__name__}: {e})"[:300])]


def _extract_eml(att: Attachment, depth: int) -> list[Doc]:
    """A message attached inside a message (bounce, forward-as-attachment)."""
    from rfq.mime import parse_message  # local import: mime <-> extractors stay decoupled

    name = att.filename
    inner = parse_message(att.data, f"{name}")
    doc = Doc(source=name, kind="eml")
    h = inner.headers
    hdr = [f"From: {h.get('from')}", f"To: {h.get('to')}", f"Date: {h.get('date')}", f"Subject: {h.get('subject')}"]
    doc.lines += [Line(row_id=f"{name}!H{i}", text=t, style="header") for i, t in enumerate(hdr, 1)]
    body = extract_body(inner)
    for ln in body.lines:
        ln.row_id = ln.row_id.replace("body!", f"{name}!", 1)
    doc.lines += body.lines
    docs = [doc]
    if inner.attachments:
        if depth + 1 >= NESTED_EML_DEPTH:
            doc.truncated = True
            doc.notes.append(f"{len(inner.attachments)} nested attachment(s) not opened (depth limit)")
        else:
            for a in inner.attachments:
                docs += extract_attachment(a, inner, depth + 1)
    return docs


def extract_all(email: Email) -> list[Doc]:
    """Body first, then attachments in MIME order. Caps the total images per email."""
    docs = [extract_body(email)]
    for att in email.attachments:
        docs += extract_attachment(att, email)
    n_images = 0
    for d in docs:
        keep = max(0, MAX_IMAGES_PER_EMAIL - n_images)
        if len(d.images) > keep:
            d.notes.append(f"{len(d.images) - keep} image(s) dropped: per-email image cap")
            d.images = d.images[:keep]
            d.truncated = True
        n_images += len(d.images)
    return docs


def read_problems(docs: list[Doc]) -> list[str]:
    """Everything that could not be read, or was cut by a limit — each is a needs_review reason.
    Deliberate skips (logos, hidden sheets) are not problems."""
    out = []
    for d in docs:
        if d.error:
            out.append(f"{d.source}: {d.error}")
        if d.truncated:
            cut = [n for n in d.notes if any(k in n for k in ("truncated", "only the first", "dropped", "not opened", "could not be read"))]
            out.append(f"{d.source}: partly read ({'; '.join(cut) or 'limit reached'})")
    return out


def describe_docs(docs: list[Doc]) -> str:
    out = []
    for d in docs:
        flags = [f for f, on in (("ERROR", d.error), ("TRUNCATED", d.truncated), ("SKIPPED", d.skipped)) if on]
        out.append(f"--- doc: {d.source} [{d.kind}] {' '.join(flags)}")
        if d.error:
            out.append(f"    error: {d.error}")
        for n in d.notes:
            out.append(f"    note: {n}")
        for im in d.images:
            out.append(f"    image: {im.label} {im.width}x{im.height} {len(im.png)} bytes")
        for ln in d.lines:
            tags = "".join(
                [" ~STRUCK~" if ln.struck else "", f" ({ln.style})" if ln.style else "",
                 f" [{ln.note}]" if ln.note else ""]
            )
            out.append(f"    [{ln.row_id}] {ln.text}{tags}")
    return "\n".join(out) + "\n"
