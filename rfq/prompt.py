"""Prompt: fixed instructions + one rendered email (text with row ids, then images).

The system text is identical for every email (so the provider's prompt cache can reuse it) and
holds the rules from data/README.md in general terms — never strings from the dev inbox.
"""

from __future__ import annotations

import base64
import hashlib

from rfq.config import IMAGE_DETAIL, MAX_PROMPT_CHARS
from rfq.models import Doc, Email

SYSTEM = """\
You read one email from the RFQ inbox of Ridgeline Industrial Supply, a distributor of pipe, \
fittings, flanges, valves, gaskets, bolting and related industrial supplies. Our inbox is \
rfq@ridgeline-supply.example. Anyone at @ridgeline-supply.example is one of our own reps. \
Our quotes are numbered Q-26-...; customers' RFQ and PO numbers are their own.

Decide what the CURRENT message does, and list exactly the items being asked for.

## Order of work (the output fields follow this order)
1. reasoning: at most 3 short sentences — who is writing to whom (a customer to us? a supplier \
answering one of our reps? a machine?) and what they want. Do not list items here.
2. classification: follows from the reasoning.
3. needs_review / review_reason.
4. sheet_decisions, then line_items.

## Classification — what the current message does, not the subject or the quoted history
- rfq: asks us to price or check availability of items. A customer writing to our RFQ inbox \
asking for prices is an rfq — even when the list is in an attachment, a photo, or a pasted table, \
and even when that attachment is missing or cannot be opened (then rfq with needs_review).
- rfq_revision: changes a request made earlier in the same thread (quantities, additions, removals).
- purchase_order: commits to buy — a PO, "please process", "go ahead with items 1-3".
- vendor_quote: a SUPPLIER quoting or answering US — typically replying to a request one of \
our reps sent them, with their prices and lead times. However much it looks like a list of items. \
A customer asking us for prices is never a vendor_quote.
- status_inquiry: asks about an existing quote or order (update? ETA? tracking?).
- auto_reply: machine-generated — out-of-office, bounce / delivery failure, read receipt.
- other: marketing, newsletters, invoices, remittances, job applications, internal chatter, \
"we went with someone else".
When one of our reps forwards a customer's email, classify it as the customer's email and also \
read the rep's own note.

## How the email is shown
Every text line has a row id in brackets, e.g. [body!B3] or [file.xlsx!Sheet!R7]. Sections:
- CURRENT MESSAGE (body!B..): the message being classified.
- FORWARDED (body!F..): content forwarded inside this message. It counts as the request when \
our rep forwards a customer's email.
- QUOTED HISTORY (body!Q..): earlier messages. CONTEXT ONLY: they were handled when they arrived. \
Take lines from it only (a) for rfq_revision, to give the complete order as now intended, and \
(b) for purchase_order, when the current message commits to items listed there \
("go ahead with items 1, 2 and 4" -> exactly those items).
- ATTACHMENT sections: spreadsheets (one line per row, cells joined by " | "), PDFs, Word \
documents, CSVs, attached emails. Notes under a heading tell you about hidden sheets, merged \
cells, comments and anything that could not be read.
- IMAGE parts: photos, scans and pasted screenshots. Read them carefully.
- A scanned page comes as one low-detail "overview" (for layout and headings only) followed by \
overlapping high-detail "strip 1 of N", "strip 2 of N"... from top to bottom. Read every row \
from the strips. A row near a strip edge appears in two strips: list it ONCE. For an item read \
from a strip, set image to that strip's label.
- READ PROBLEMS: attachments that could not be opened or were only partly read. If the \
customer's request depends on them, it is still a request: return what you can read and set \
needs_review with the reason.
Lines marked STRUCK are crossed out: never return them. Lines marked (Heading ...) are headings.

## Line items — one per thing the customer is asking for
- Text or table line: set row_id to that line's id, image to null. raw = the part of the line \
that is this item (the whole line when it holds one item; the fragment when one line holds several).
- Image: set row_id to null, image to the image label exactly as given. raw = the SHORTEST text \
that identifies the item as written (e.g. the list line, or the model / part-number line of a \
nameplate) — not a transcription of the whole image. Put everything else you read into description.
- Tables in images and scans: read each row left to right across the SAME row before moving \
down, so the quantity, size and description you return all belong to that row. Keep the row's \
item number at the start of raw when the row has one, with cells separated by " | " \
(e.g. 7 | 12 | EA | 2" | gate valve).
- Not items: headings, notes, column headers, totals, prices, signatures, addresses, crossed-out \
lines, old revisions of a document, items in quoted history (except the two cases above).
- description: the item self-contained, as a rep would type it into a quote without re-reading \
the email: the line's own words plus EVERY heading, note, column header, sheet name, form field, \
subject line or earlier line that applies to it (e.g. a section heading "ALL PIPE SCH 40" applies \
to the rows under it; a document field "Material: X" applies to every row). Do not add context \
that belongs to a different section. Never invent a spec the email doesn't give.
- Overrides: a heading or banner often sets a default ("ALL FITTINGS SCH 40 UNLESS NOTED"). \
When a line states its own value for that attribute ("... SCH 80"), the description uses the \
line's value and must NOT mention the overridden default anywhere. Compose the spec from the \
pieces that apply (e.g. 6" x 4" concentric reducer, BW, SCH 80, A234 WPB); never paste \
the banner text into the description.
- qty: the number as the customer stated it, not converted. A spelled-out number is a number. \
A vague amount ("a couple", "some", "enough for the job") is null — that is NOT a reason for \
needs_review; the item is still fully identified. A size, schedule, length, \
pressure class, rating, part number or price is NEVER a quantity.
- uom: one of EA FT M IN BX PK PR DZ RL LB SET GAL BAG CS as stated (joints/lengths/pieces/each \
-> EA, feet -> FT, rolls -> RL, pairs -> PR, boxes -> BX, packs -> PK), or null when no unit is stated.
- rfq_revision: return the COMPLETE order as the customer now intends it — unchanged earlier \
items (from quoted history) plus changes, minus removals; a changed line uses its new quantity.

## Several visible sheets in one workbook
Decide for each such workbook, and record it in sheet_decisions:
- sections: the sheets are parts of one order (e.g. pipe on one tab, fittings on another) -> use all.
- versions: the sheets are revisions of the same list -> use only the newest, judged by sheet \
names (Rev B > Rev A, "final", "current", "old"), dates, the file name, or what the email says.
- unclear: you cannot tell -> still return your best lines, and set needs_review with the reason.
Apply the same judgement to several attachments that are versions of one list.

## needs_review
true when the email asks for something you cannot fully read or resolve: the attachment it points \
at is missing (the email says "attached" but there is none, or only a logo) or cannot be opened, \
part of it could not be read, or items are identified only by something not in the email \
("same as last time", "same as the one in the photo" when the photo does not show what is needed). \
Give the reason, and still return every line you could read. Not reasons for needs_review: a \
vague quantity (qty null), a spec implied by a heading, a list you can read in full.

line_items is empty for vendor_quote, status_inquiry, auto_reply and other.
"""


def _section(title: str) -> str:
    return f"\n=== {title} ===\n"


def _line_text(ln) -> str:
    tags = []
    if ln.style:
        tags.append(f"({ln.style})")
    if ln.struck:
        tags.append("STRUCK")
    if ln.note:
        tags.append(f"[{ln.note}]")
    return f"[{ln.row_id}] {ln.text}" + (" " + " ".join(tags) if tags else "")


def render_text(email: Email, docs: list[Doc], problems: list[str] | None = None) -> tuple[str, bool]:
    """Render headers + read problems + all docs as text. Returns (text, truncated_by_budget)."""
    h = email.headers
    out = [
        f"From: {h.get('from')}" + ("   [one of our reps]" if email.internal else ""),
        f"To: {h.get('to')}",
    ]
    if h.get("cc"):
        out.append(f"Cc: {h.get('cc')}")
    out += [f"Date: {h.get('date')}", f"Subject: {h.get('subject')}"]
    atts = [d for d in docs[1:] if not d.skipped]
    if not atts:
        skipped = [d.source for d in docs[1:] if d.skipped]
        out.append("Attachments: none" + (f" (only logo/signature images: {', '.join(skipped)})" if skipped else ""))

    if problems:
        out.append(_section("READ PROBLEMS"))
        out += [f"- {p}" for p in problems]

    body = docs[0]
    groups = {"B": "CURRENT MESSAGE", "F": "FORWARDED", "Q": "QUOTED HISTORY (context only)"}
    for prefix, title in groups.items():
        lines = [ln for ln in body.lines if ln.row_id.startswith(f"body!{prefix}")]
        if lines:
            out.append(_section(title))
            out += [_line_text(ln) for ln in lines]
    if not any(ln.row_id.startswith("body!B") for ln in body.lines):
        out.append(_section("CURRENT MESSAGE"))
        out.append("(no text)")
    for n in body.notes:
        out.append(f"note: {n}")

    for d in docs[1:]:
        head = f"ATTACHMENT: {d.source} ({d.kind})"
        if d.error:
            head += " — COULD NOT BE READ"
        out.append(_section(head))
        if d.error:
            out.append(f"error: {d.error}")
        for n in d.notes:
            out.append(f"note: {n}")
        for im in d.images:
            out.append(f"(image part follows below, label: {im.label})")
        out += [_line_text(ln) for ln in d.lines]

    text = "\n".join(out)
    if len(text) > MAX_PROMPT_CHARS:
        cut = text[:MAX_PROMPT_CHARS]
        return cut + "\n\n[... email truncated: too long to read in full ...]", True
    return text, False


def build_messages(email: Email, docs: list[Doc], problems: list[str] | None = None) -> tuple[list[dict], bool]:
    """Chat messages for the model, and whether the text was truncated by the budget."""
    text, truncated = render_text(email, docs, problems)
    content: list[dict] = [{"type": "text", "text": text}]
    for d in docs:
        for im in d.images:
            content.append({"type": "text", "text": f"IMAGE label: {im.label}"})
            b64 = base64.b64encode(im.png).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}",
                                                                "detail": im.detail or IMAGE_DETAIL}})
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}], truncated


def messages_fingerprint(messages: list[dict]) -> str:
    """Stable digest of the request content (images hashed, not inlined)."""
    h = hashlib.sha256()
    for m in messages:
        h.update(m["role"].encode())
        content = m["content"]
        parts = [{"type": "text", "text": content}] if isinstance(content, str) else content
        for p in parts:
            if p["type"] == "text":
                h.update(b"T" + p["text"].encode("utf-8"))
            else:
                h.update(b"I" + hashlib.sha256(p["image_url"]["url"].encode()).digest())
                h.update(p["image_url"].get("detail", "").encode())
    return h.hexdigest()
