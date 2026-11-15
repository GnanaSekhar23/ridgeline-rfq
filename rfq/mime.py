"""RFC-822 -> `Email`: headers, current text, forwarded text, quoted history, attachments.

The split matters for grading: items in quoted history were handled when they arrived, but
forwarded content (one of our reps passing on a customer's email) is the request itself. We keep
all three parts so later steps can decide; this module only labels them.
"""

from __future__ import annotations

import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime

from bs4 import BeautifulSoup

from rfq.config import OUR_DOMAIN
from rfq.models import Attachment, Email

HEADERS = ("from", "to", "cc", "date", "subject", "message-id", "in-reply-to", "references")

# ---------------------------------------------------------------- history markers
_REPLY_ON = re.compile(r"^\s*On\b.{0,200}\bwrote:\s*$", re.I)
_ORIGINAL = re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.I)
_FORWARDED = re.compile(
    r"^\s*(-{2,}\s*Forwarded message\s*-{2,}|Begin forwarded message:)\s*$", re.I
)
_HDR = re.compile(r"^\s*\*?(From|Sent|Date|To|Cc|Subject)\s*:\*?\s", re.I)
_FWD_SUBJECT = re.compile(r"^\s*(fw|fwd)\s*:", re.I)


def _is_outlook_header_block(lines: list[str], i: int) -> bool:
    """`From: ...` followed within a few lines by Sent:/Date: and To:/Subject:."""
    if not re.match(r"^\s*\*?From\s*:", lines[i], re.I):
        return False
    window = " ".join(lines[i + 1 : i + 6])
    return bool(re.search(r"\b(Sent|Date)\s*:", window, re.I)) and bool(
        re.search(r"\b(To|Subject)\s*:", window, re.I)
    )


def find_history(text: str) -> tuple[int, str] | None:
    """Return (line index, marker kind) of the first history marker, or None.

    kind is "forward" (explicit forward marker), "original" (Outlook's -----Original Message-----,
    used for both replies and forwards), "header" (Outlook From/Sent block) or "reply"
    ("On ... wrote:" or a run of '>' lines).
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if _FORWARDED.match(line):
            return i, "forward"
        if _ORIGINAL.match(line):
            return i, "original"
        if _REPLY_ON.match(line):
            return i, "reply"
        # "On Mon, ... <x@y>\nwrote:" wrapped over two lines
        if i + 1 < len(lines) and re.match(r"^\s*On\b", line, re.I) and re.match(
            r"^\s*.{0,80}\bwrote:\s*$", lines[i + 1], re.I
        ) and len(line) < 200:
            return i, "reply"
        if _is_outlook_header_block(lines, i):
            return i, "header"
        if line.lstrip().startswith(">") and _quote_run(lines, i) >= 2:
            return i, "reply"
    return None


def _quote_run(lines: list[str], i: int) -> int:
    n = 0
    while i + n < len(lines) and (lines[i + n].lstrip().startswith(">") or not lines[i + n].strip()):
        n += 1
    return n


def _unquote(text: str) -> str:
    return "\n".join(re.sub(r"^\s?>\s?", "", ln) for ln in text.splitlines())


def _strip_header_block(text: str) -> str:
    """Drop the From:/Sent:/To:/Subject: lines at the top of a forwarded/quoted block."""
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (
        not lines[i].strip() or _HDR.match(lines[i]) or _ORIGINAL.match(lines[i])
        or _FORWARDED.match(lines[i])
    ):
        i += 1
    return "\n".join(lines[i:])


def split_history(text: str, subject: str) -> tuple[str, str, str]:
    """Split a body into (current, forwarded, quoted).

    A block is "forwarded" when the marker says so, or when the subject is FW:/Fwd: and the
    marker is an Outlook-style block. Everything else after a marker is quoted history.
    Inside forwarded content, a further reply marker starts its own quoted history.
    """
    hit = find_history(text)
    if not hit:
        return text.strip(), "", ""
    idx, kind = hit
    lines = text.splitlines()
    current = "\n".join(lines[:idx]).strip()
    rest = "\n".join(lines[idx:])
    is_forward = kind == "forward" or (
        kind in ("original", "header") and bool(_FWD_SUBJECT.match(subject or ""))
    )
    if not is_forward:
        return current, "", _unquote(rest).strip()
    fwd_full = _strip_header_block(rest)
    fwd_cur, fwd_fwd, fwd_quoted = split_history(fwd_full, "")
    forwarded = "\n\n".join(p for p in (fwd_cur, fwd_fwd) if p)
    return current, forwarded.strip(), fwd_quoted


# ---------------------------------------------------------------- HTML
def html_to_text(html: str) -> str:
    """HTML -> text with tables kept as one row per line (cells joined by ' | '),
    blockquotes rendered as '>' lines, and images as [image: cid alt=...] markers."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "head"]):
        t.decompose()
    for img in soup.find_all("img"):
        src = (img.get("src") or "").removeprefix("cid:")
        alt = (img.get("alt") or "").strip()
        img.replace_with(f"[image: {src}{f' alt={alt!r}' if alt else ''}]")
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if any(cells):
                rows.append(" | ".join(cells))
        table.replace_with("\n" + "\n".join(rows) + "\n")
    for bq in soup.find_all("blockquote"):
        inner = bq.get_text("\n")
        bq.replace_with("\n" + "\n".join("> " + ln for ln in inner.splitlines()) + "\n")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for blk in soup.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "hr"]):
        blk.insert_before("\n")
        blk.insert_after("\n")
    text = soup.get_text()
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return "\n".join(ln.strip() for ln in text.splitlines()).strip()


# ---------------------------------------------------------------- parts
def _decode_text(part) -> str:
    try:
        return part.get_content()
    except Exception:  # unknown charset / bad transfer encoding
        return (part.get_payload(decode=True) or b"").decode("utf-8", "replace")


def _is_attachment(part) -> bool:
    disp = part.get_content_disposition()
    ct = part.get_content_type()
    if part.get_filename():
        return True
    if ct.startswith("text/"):
        return disp == "attachment"
    return True  # any non-text leaf: images, office docs, pdf, octet-stream


def _attachment(part, data: bytes, default: str) -> Attachment:
    return Attachment(
        filename=part.get_filename() or default,
        mime=part.get_content_type(),
        data=data,
        inline=part.get_content_disposition() == "inline" or bool(part.get("Content-ID")),
        content_id=(part.get("Content-ID") or "").strip().strip("<>") or None,
    )


def _walk(msg) -> tuple[str | None, str | None, list[Attachment]]:
    text = html = None
    atts: list[Attachment] = []
    stack = [msg]
    while stack:
        part = stack.pop(0)
        ct = part.get_content_type()
        if ct == "message/rfc822":
            try:
                inner = part.get_payload(0)
                data = inner.as_bytes() if hasattr(inner, "as_bytes") else bytes(inner)
            except Exception:
                data = part.get_payload(decode=True) or b""
            atts.append(_attachment(part, data, f"attached-{len(atts) + 1}.eml"))
            continue
        if part.is_multipart():
            stack[0:0] = list(part.iter_parts())
            continue
        if _is_attachment(part):
            try:
                data = part.get_payload(decode=True) or b""
            except Exception:
                data = b""
            ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif"}.get(ct, "")
            atts.append(_attachment(part, data, f"unnamed-{len(atts) + 1}{ext}"))
        elif ct == "text/plain" and text is None:
            text = _decode_text(part)
        elif ct == "text/html" and html is None:
            html = _decode_text(part)
    return text, html, atts


def choose_body(text: str | None, html: str | None) -> tuple[str, str]:
    """Pick the body source. HTML wins when it holds a table (cells stay aligned) or when
    there is no plain text; otherwise plain text. Returns (body, "text"|"html"|"none")."""
    if html and ("<table" in html.lower() or not (text or "").strip()):
        return html_to_text(html), "html"
    if text and text.strip():
        return text.replace("\r\n", "\n"), "text"
    return "", "none"


def image_alts(html: str | None) -> dict[str, str]:
    if not html:
        return {}
    out = {}
    for img in BeautifulSoup(html, "html.parser").find_all("img"):
        src = (img.get("src") or "").removeprefix("cid:").strip()
        if src:
            out[src] = (img.get("alt") or "").strip()
    return out


def _addr(value: str | None) -> str:
    pairs = getaddresses([value or ""])
    return (pairs[0][1] if pairs else "").lower()


def parse_message(raw: bytes, email_id: str) -> Email:
    msg: EmailMessage = BytesParser(policy=policy.default).parsebytes(raw)
    headers: dict[str, str | None] = {}
    for h in HEADERS:
        try:
            v = msg.get(h)
            headers[h.replace("-", "_")] = str(v) if v is not None else None
        except Exception:  # malformed header
            headers[h.replace("-", "_")] = None
    text, html, atts = _walk(msg)
    body_src, body_kind = choose_body(text, html)
    current, forwarded, quoted = split_history(body_src, headers.get("subject") or "")
    sender = _addr(headers.get("from"))
    try:
        date = parsedate_to_datetime(headers["date"]) if headers.get("date") else None
    except Exception:
        date = None
    return Email(
        id=email_id,
        headers=headers,
        body=current,
        forwarded=forwarded,
        quoted=quoted,
        attachments=atts,
        sender=sender,
        # exact domain only: a bounce from mx1.<our domain> is a machine, not one of our reps
        internal=sender.endswith("@" + OUR_DOMAIN),
        date=date,
        body_kind=body_kind,
        image_alts=image_alts(html),
    )


def describe(e: Email) -> str:
    """Human-readable dump of a parsed email, for inspection and debugging."""
    h = e.headers
    out = [
        f"===== {e.id}",
        f"from: {h.get('from')}  internal={e.internal}",
        f"subject: {h.get('subject')}",
        f"date: {e.date}  message_id: {h.get('message_id')}",
        f"in_reply_to: {h.get('in_reply_to')}  references: {h.get('references')}",
        f"body from: {e.body_kind}",
        "--- current ---",
        e.body or "(empty)",
    ]
    if e.forwarded:
        out += ["--- forwarded ---", e.forwarded]
    if e.quoted:
        out += ["--- quoted history ---", e.quoted]
    for a in e.attachments:
        alt = e.image_alts.get(a.content_id or "") or e.image_alts.get(a.filename, "")
        out.append(
            f"--- attachment: {a.filename} [{a.mime}] {len(a.data)} bytes"
            f"{' inline' if a.inline else ''}{f' cid={a.content_id}' if a.content_id else ''}"
            f"{f' alt={alt!r}' if alt else ''}"
        )
    return "\n".join(out) + "\n"
