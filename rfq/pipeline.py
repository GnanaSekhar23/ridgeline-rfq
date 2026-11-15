"""Inbox processing in two passes.

1. Parse every .eml (one bad file -> flagged entry, the rest carry on).
2. Inbox-level links in code: duplicates and thread parents.
3. Per email: extract -> (model, step 6) -> validate (step 7). Duplicates are not re-processed:
   they copy the original's classification, get duplicate_of and no lines.
"""

from __future__ import annotations

import logging
from pathlib import Path

from rfq.dedupe import find_duplicates
from rfq.extractors import extract_all
from rfq.mime import parse_message
from rfq.models import Email, Result
from rfq.threads import find_parents

log = logging.getLogger(__name__)


def process_email(email: Email, parent: str | None = None) -> Result:
    """Stub until step 6: extracts every part (so failures surface here), returns `other`.
    `parent` becomes `revises` when the classification is rfq_revision."""
    extract_all(email)
    result = Result(classification="other")
    if result.classification == "rfq_revision":
        result.revises = parent
    return result


def failed_result(reason: str) -> Result:
    """Entry for an email we could not process at all.

    We don't know what it is, so it is treated as a possible request and flagged: a human
    looking at a non-request costs minutes; a silently dropped request costs a customer.
    """
    return Result(classification="rfq", needs_review=True, review_reason=reason)


def _error(e: Exception) -> str:
    return f"could not process email: {type(e).__name__}: {e}"


def link_inbox(emails: list[Email]) -> tuple[dict[str, str], dict[str, str]]:
    """(duplicates {dup: original}, parents {email: parent}). Never raises."""
    try:
        dups = find_duplicates(emails)
    except Exception:
        log.exception("duplicate detection failed; continuing without it")
        dups = {}
    try:
        parents = find_parents(emails)
    except Exception:
        log.exception("thread linking failed; continuing without it")
        parents = {}
    return dups, parents


def process_inbox(emails_dir: Path) -> dict[str, dict]:
    paths = sorted(emails_dir.glob("*.eml"))
    results: dict[str, Result] = {}
    parsed: dict[str, Email] = {}
    for path in paths:
        try:
            parsed[path.stem] = parse_message(path.read_bytes(), path.stem)
        except Exception as e:  # one bad email never takes down the run
            log.exception("failed to parse %s", path.name)
            results[path.stem] = failed_result(_error(e))

    dups, parents = link_inbox(list(parsed.values()))

    for eid, email in parsed.items():
        if eid in dups:
            continue
        try:
            results[eid] = process_email(email, parent=parents.get(eid))
        except Exception as e:
            log.exception("failed on %s", eid)
            results[eid] = failed_result(_error(e))

    for dup, orig in dups.items():
        original = results.get(orig)
        results[dup] = Result(
            classification=original.classification if original else "rfq",
            duplicate_of=orig,
        )

    return {p.stem: results[p.stem].to_json() for p in paths}
