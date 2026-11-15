"""Per-email processing. Step 1: stub only — every email becomes `other`.

Later steps replace `process_email` with mime -> extract -> prompt -> cache/llm -> validate.
"""

from __future__ import annotations

import logging
from pathlib import Path

from rfq.models import Result

log = logging.getLogger(__name__)


def process_email(path: Path) -> Result:
    """Stub: reads the file (so unreadable files fail here) and returns an empty `other`."""
    path.read_bytes()
    return Result(classification="other")


def failed_result(reason: str) -> Result:
    """Entry for an email we could not process at all.

    We don't know what it is, so it is treated as a possible request and flagged: a human
    looking at a non-request costs minutes; a silently dropped request costs a customer.
    """
    return Result(classification="rfq", needs_review=True, review_reason=reason)


def process_inbox(emails_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(emails_dir.glob("*.eml")):
        try:
            result = process_email(path)
        except Exception as e:  # one bad email never takes down the run
            log.exception("failed on %s", path.name)
            result = failed_result(f"could not process email: {type(e).__name__}: {e}")
        out[path.stem] = result.to_json()
    return out
