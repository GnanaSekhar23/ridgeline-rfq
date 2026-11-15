"""Thread parents — in code, no model. Used for `revises` when the model says rfq_revision.

1. In-Reply-To / References: the nearest referenced message that is in this inbox.
2. Fallback when a client dropped those headers: the subject carries a reply/forward/resend
   prefix, and an earlier inbox email has the same normalised subject and the same sender
   domain (or one side is one of our reps).
Only emails in this inbox can be parents; a reply to our own quote has no parent here.
"""

from __future__ import annotations

import re

from rfq.dedupe import date_order
from rfq.models import Email

_PREFIX = re.compile(r"^\s*((re|fw|fwd|aw|sv|wg|resend|resent|reminder)\s*(\[\d+\])?\s*:\s*)+", re.I)
_MSGID = re.compile(r"<[^<>\s]+>")


def norm_subject(s: str | None) -> str:
    s = _PREFIX.sub("", s or "")
    return " ".join(s.lower().split())


def has_reply_prefix(s: str | None) -> bool:
    return bool(_PREFIX.match(s or ""))


def _domain(e: Email) -> str:
    return e.sender.rsplit("@", 1)[-1] if "@" in e.sender else e.sender


def find_parents(emails: list[Email]) -> dict[str, str]:
    """Return {email_id: parent_email_id} for emails whose parent is in this inbox."""
    by_mid = {}
    for e in emails:
        mid = (e.headers.get("message_id") or "").strip()
        if mid:
            by_mid.setdefault(mid, e.id)
    ordered = sorted(emails, key=date_order)
    position = {e.id: i for i, e in enumerate(ordered)}
    parents: dict[str, str] = {}
    for e in ordered:
        refs = _MSGID.findall(e.headers.get("references") or "")
        irt = _MSGID.findall(e.headers.get("in_reply_to") or "")
        for mid in irt + refs[::-1]:  # In-Reply-To first, then nearest reference
            pid = by_mid.get(mid)
            if pid and pid != e.id:
                parents[e.id] = pid
                break
        if e.id in parents or not has_reply_prefix(e.headers.get("subject")):
            continue
        subj = norm_subject(e.headers.get("subject"))
        if not subj:
            continue
        for prev in reversed(ordered[: position[e.id]]):  # nearest earlier email first
            same_party = _domain(prev) == _domain(e) or prev.internal or e.internal
            if same_party and norm_subject(prev.headers.get("subject")) == subj:
                parents[e.id] = prev.id
                break
    return parents
