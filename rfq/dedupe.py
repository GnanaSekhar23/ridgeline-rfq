"""Find the same request sent twice — in code, no model.

README rule: the email with the later Date: is the duplicate; it keeps the original's
classification, gets duplicate_of = original id and no lines.

A wrong "duplicate" silently drops a request (it gets no lines), so the rule is strict:
  * same Message-ID (the same email delivered twice), or
  * same sender domain AND identical non-logo attachments (by content hash) AND the item-like
    lines of the current text (lines with a digit) are near-identical (Jaccard >= 0.8),
    with at least some content to compare.
Wording like "resending in case..." and signatures differ freely; changed items do not.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO

from rfq.models import Email

ITEM_JACCARD = 0.8
_BULLET = re.compile(r"^[\s\-\*•>·]+")


@dataclass(frozen=True)
class Fingerprint:
    message_id: str | None
    domain: str
    attachments: frozenset[str]  # sha256 of non-logo attachment bytes
    item_lines: frozenset[str]  # normalised lines with a digit, from current + forwarded text


def _is_logo(att) -> bool:
    if not att.inline or not att.mime.startswith("image/"):
        return False
    try:
        from PIL import Image

        from rfq.extractors.image import looks_like_logo

        with Image.open(BytesIO(att.data)) as im:
            return looks_like_logo(*im.size)
    except Exception:
        return False


def _norm_line(s: str) -> str:
    s = _BULLET.sub("", s.lower())
    return " ".join(s.split())


def fingerprint(e: Email) -> Fingerprint:
    text = "\n".join(p for p in (e.body, e.forwarded) if p)
    items = {_norm_line(ln) for ln in text.splitlines() if re.search(r"\d", ln)}
    atts = {hashlib.sha256(a.data).hexdigest() for a in e.attachments if a.data and not _is_logo(a)}
    mid = (e.headers.get("message_id") or "").strip() or None
    return Fingerprint(
        message_id=mid,
        domain=e.sender.rsplit("@", 1)[-1] if "@" in e.sender else e.sender,
        attachments=frozenset(atts),
        item_lines=frozenset(x for x in items if x),
    )


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def is_duplicate(later: Fingerprint, earlier: Fingerprint) -> bool:
    if later.message_id and later.message_id == earlier.message_id:
        return True
    if not later.domain or later.domain != earlier.domain:
        return False
    if later.attachments != earlier.attachments:
        return False
    if not later.attachments and len(later.item_lines | earlier.item_lines) < 2:
        return False  # too little content to call it the same request
    return _jaccard(later.item_lines, earlier.item_lines) >= ITEM_JACCARD


def date_order(e: Email) -> tuple:
    """Sort key: by Date: (undated last), then id — so 'later' is well defined."""
    d = e.date
    if d is not None and d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return (d is None, d or datetime.min.replace(tzinfo=timezone.utc), e.id)


def find_duplicates(emails: list[Email]) -> dict[str, str]:
    """Return {duplicate_id: original_id}. The original is always the earliest copy."""
    ordered = sorted(emails, key=date_order)
    fps = {e.id: fingerprint(e) for e in ordered}
    dup_of: dict[str, str] = {}
    seen: list[Email] = []
    for e in ordered:
        for prev in seen:
            if prev.id in dup_of:
                continue  # compare against originals only
            if is_duplicate(fps[e.id], fps[prev.id]):
                dup_of[e.id] = prev.id
                break
        seen.append(e)
    return dup_of
