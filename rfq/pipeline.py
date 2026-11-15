"""Inbox processing in two passes.

1. Parse every .eml (one bad file -> flagged entry, the rest carry on).
2. Inbox-level links in code: duplicates and thread parents.
3. Per email: extract -> one model call (cached) -> validate. Duplicates are not re-processed:
   they copy the original's classification, get duplicate_of and no lines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from rfq.config import MODEL
from rfq.costlog import RunLog
from rfq.dedupe import find_duplicates
from rfq.extractors import extract_all, read_problems
from rfq.llm import Extractor
from rfq.mime import parse_message
from rfq.models import Email, Result
from rfq.threads import find_parents
from rfq.validate import build_result

log = logging.getLogger(__name__)


@dataclass
class Context:
    extractor: Extractor
    runlog: RunLog | None = None


def process_email(email: Email, parent: str | None = None, ctx: Context | None = None) -> Result:
    ctx = ctx or Context(extractor=Extractor())
    docs = extract_all(email)
    problems = read_problems(docs)
    outcome = ctx.extractor.run(email, docs, problems)
    if ctx.runlog:
        ctx.runlog.record(email.id, outcome, n_images=sum(len(d.images) for d in docs))
    return build_result(
        email, docs, outcome.extraction,
        parent=parent, problems=problems,
        model_error=outcome.error, prompt_truncated=outcome.prompt_truncated,
    )


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


def process_inbox(emails_dir: Path, ctx: Context | None = None) -> dict[str, dict]:
    ctx = ctx or Context(extractor=Extractor(), runlog=None)
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
            if ctx.runlog:
                ctx.runlog.record(eid, skipped=f"duplicate of {dups[eid]}")
            continue
        try:
            results[eid] = process_email(email, parent=parents.get(eid), ctx=ctx)
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


def run_inbox(emails_dir: Path, model: str = MODEL) -> tuple[dict[str, dict], RunLog]:
    """CLI entry: process with a run log and write the cost report."""
    runlog = RunLog(model=model)
    out = process_inbox(emails_dir, Context(extractor=Extractor(model=model), runlog=runlog))
    runlog.finish()
    return out, runlog
