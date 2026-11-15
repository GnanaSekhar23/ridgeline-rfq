"""Replay the synthetic inbox (tests/synthetic/) offline from its committed cache and check each
email against tests/synthetic/expected.json. No network: conftest forces offline mode.

To refresh after a prompt change (costs ~$0.10):
    set RFQ_CACHE_DIR=tests/synthetic/cache  then  rfq parse --emails tests/synthetic/emails --out <tmp>.json
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from eval.eval import mentions
from rfq.cache import Cache
from rfq.costlog import RunLog
from rfq.llm import Extractor
from rfq.pipeline import Context, process_inbox

SYN = Path(__file__).resolve().parent / "synthetic"
EXPECTED = {k: v for k, v in json.loads((SYN / "expected.json").read_text(encoding="utf-8")).items()
            if not k.startswith("_")}


@pytest.fixture(scope="module")
def replay(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("syn")
    log = RunLog("gpt-4.1", runs_dir=tmp / "runs", reports_dir=tmp / "reports")
    out = process_inbox(SYN / "emails", Context(extractor=Extractor(cache=Cache(SYN / "cache")), runlog=log))
    return out, log


def test_every_synthetic_email_replays_from_cache(replay) -> None:
    out, log = replay
    assert set(out) == set(EXPECTED)
    missing = [r["email"] for r in log.rows if r.get("error")]
    assert not missing, f"no cached answer for {missing}: re-record the synthetic cache"
    assert sum(r.get("live_calls", 0) for r in log.rows) == 0


STRICT_KEYS = ("line_checks", "review_reason_mentions")  # finer assertions, tested separately

# Known failures under the current prompt (p8). A prompt rule tried in p5/p6 fixed this on the
# synthetic set but changed dev results, so it was not kept. strict=True: if a later change fixes
# it, the test turns red so the mark gets removed. (S08 was fixed in code: an item-less request's
# review reason names the quote / PO / earlier order it refers to.)
KNOWN_FAILURES = {
    "S09": "p8: 'six tees same' spec (sch 40, butt weld) is carried onto the caps listed after "
           "them; prompt rules that fixed it (p5/p6) were not kept",
}


def check(got: dict, exp: dict) -> list[str]:
    problems = []
    for f in ("classification", "needs_review", "revises"):
        if got[f] != exp[f]:
            problems.append(f"{f}: got {got[f]!r}, expected {exp[f]!r}")
    lines = got["line_items"]
    if "n_lines" in exp and len(lines) != exp["n_lines"]:
        problems.append(f"n_lines: got {len(lines)}, expected {exp['n_lines']}")
    if "qtys" in exp:
        got_q = Counter(None if q is None else float(q) for q in (li["qty"] for li in lines))
        exp_q = Counter(None if q is None else float(q) for q in exp["qtys"])
        if got_q != exp_q:
            problems.append(f"qtys: got {sorted(got_q.elements(), key=str)}, expected {sorted(exp_q.elements(), key=str)}")
    descs = " | ".join(li["description"] for li in lines)
    for m in exp.get("mention", []):
        if not mentions(descs, m):
            problems.append(f"no description mentions {m!r}")
    for m in exp.get("not_mention", []):
        if mentions(descs, m):
            problems.append(f"a description mentions {m!r}")
    for lc in exp.get("line_checks", []):
        hit = [li for li in lines if lc["raw_has"].lower() in li["raw"].lower()]
        if not hit:
            problems.append(f"no line whose raw contains {lc['raw_has']!r}")
        for li in hit:
            for m in lc.get("mention", []):
                if not mentions(li["description"], m):
                    problems.append(f"{lc['raw_has']} line does not mention {m!r}: {li['description']!r}")
            for m in lc.get("not_mention", []):
                if mentions(li["description"], m):
                    problems.append(f"{lc['raw_has']} line mentions {m!r}: {li['description']!r}")
    reason = (got.get("review_reason") or "").lower()
    for m in exp.get("review_reason_mentions", []):
        if m.lower() not in reason:
            problems.append(f"review_reason does not mention {m!r}: {got.get('review_reason')!r}")
    if "source" in exp and any(li["source"] != exp["source"] for li in lines):
        problems.append(f"source: got {sorted({li['source'] for li in lines})}, expected {exp['source']!r}")
    return problems


@pytest.mark.parametrize("sid", sorted(EXPECTED))
def test_synthetic_email(replay, sid: str) -> None:
    """Core expectations: classification, review flag, links, lines, quantities, mentions."""
    out, _ = replay
    exp = {k: v for k, v in EXPECTED[sid].items() if k not in STRICT_KEYS}
    problems = check(out[sid], exp)
    assert not problems, f"{sid} ({EXPECTED[sid]['situation']}): " + "; ".join(problems)


@pytest.mark.parametrize("sid", [
    pytest.param(sid, marks=pytest.mark.xfail(strict=True, reason=KNOWN_FAILURES[sid]))
    if sid in KNOWN_FAILURES else sid
    for sid in sorted(k for k, v in EXPECTED.items() if any(s in v for s in STRICT_KEYS))
])
def test_synthetic_email_strict(replay, sid: str) -> None:
    """Finer expectations: per-line spec carry-over, specific review reasons."""
    out, _ = replay
    exp = {k: EXPECTED[sid][k] for k in ("classification", "needs_review", "revises", *STRICT_KEYS)
           if k in EXPECTED[sid]}
    problems = check(out[sid], exp)
    assert not problems, f"{sid} ({EXPECTED[sid]['situation']}): " + "; ".join(problems)
