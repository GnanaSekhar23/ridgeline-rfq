"""Whole-inbox resilience: provider down, partial outage, and `parse --retry-failed` recovery.

Uses fake OpenAI clients (no network). Each fake answers per email from the request text.
"""

from __future__ import annotations

import json
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

from rfq.cache import Cache
from rfq.cli import main
from rfq.costlog import RunLog
from rfq.llm import Extractor
from rfq.pipeline import load_failures, resolve_run_dir, run_inbox
from tests.test_llm import _resp, status_error


def _inbox(tmp: Path, n: int = 3) -> Path:
    d = tmp / "emails"
    d.mkdir()
    for i in range(1, n + 1):
        m = EmailMessage()
        m["From"], m["To"] = f"buyer{i}@cust{i}.example", "rfq@ridgeline-supply.example"
        m["Subject"], m["Date"] = f"RFQ {i}", f"Mon, 0{i} Nov 2026 09:00:00 -0600"
        m["Message-ID"] = f"<m{i}@cust{i}.example>"
        m.set_content(f"Please quote {i + 3} ea 2in tee")
        (d / f"M{i}.eml").write_bytes(m.as_bytes())
    return d


def _answer() -> str:
    from rfq.config import MATCHER_ENABLED

    line = {"row_id": "body!B1", "image": None, "raw": "tee", "description": "2in tee", "qty": None, "uom": "EA"}
    if MATCHER_ENABLED:
        line["attrs"] = {"product": "tee", "size": "2", "spec": None, "material": None, "ends": None, "extra": None}
    return json.dumps({
        "reasoning": "A customer asks us to price a tee.", "classification": "rfq",
        "needs_review": False, "review_reason": None, "sheet_decisions": [], "line_items": [line],
    })


class Fake:
    """fail(subject) -> True means that email's call raises a 503."""

    def __init__(self, fail=lambda text: False):
        self.fail = fail
        self.calls: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        text = kw["messages"][1]["content"][0]["text"]
        self.calls.append(text)
        if self.fail(text):
            raise status_error(503)
        return _resp(_answer())


def _run(tmp: Path, emails: Path, client, retry: Path | None = None):
    ex = Extractor(model="gpt-4.1", cache=Cache(tmp / "cache"), client=client, wait_max_s=0.01)
    log = RunLog("gpt-4.1", runs_dir=tmp / "runs", reports_dir=tmp / "reports")
    return run_inbox(emails, retry_failed=retry, extractor=ex, runlog=log)


def test_provider_down_every_email_flagged_retryable_no_crash(tmp_path: Path) -> None:
    emails = _inbox(tmp_path)
    down = Fake(fail=lambda t: True)
    out, log = _run(tmp_path, emails, down)
    assert set(out) == {"M1", "M2", "M3"}
    for r in out.values():
        assert r["needs_review"] and "InternalServerError" in r["review_reason"] and r["line_items"] == []
    retryable, final = load_failures(log.dir)
    assert retryable == {"M1", "M2", "M3"} and not final
    assert len(down.calls) == 3 * 4  # each email: first try + 3 retries, then give up
    assert not list((tmp_path / "cache").glob("*.json")) if (tmp_path / "cache").exists() else True
    assert "emails with no model answer | 3" in (tmp_path / "reports" / "cost.md").read_text(encoding="utf-8")


def test_retry_failed_recovers_after_outage(tmp_path: Path) -> None:
    emails = _inbox(tmp_path)
    _, failed_run = _run(tmp_path, emails, Fake(fail=lambda t: True))
    up = Fake()
    out, log = _run(tmp_path, emails, up, retry=failed_run.dir)
    assert len(up.calls) == 3
    for r in out.values():
        assert not r["needs_review"] and r["line_items"] and r["classification"] == "rfq"
    assert load_failures(log.dir) == (set(), set())
    # and now everything is cached: a plain re-run makes no calls
    again = Fake(fail=lambda t: True)
    out2, _ = _run(tmp_path, emails, again)
    assert again.calls == [] and out2 == out


def test_partial_outage_retries_only_the_failed_email(tmp_path: Path) -> None:
    emails = _inbox(tmp_path)
    first = Fake(fail=lambda t: "Subject: RFQ 2" in t)
    out, run1 = _run(tmp_path, emails, first)
    assert out["M2"]["needs_review"] and not out["M1"]["needs_review"] and not out["M3"]["needs_review"]
    assert load_failures(run1.dir)[0] == {"M2"}
    second = Fake()
    out2, _ = _run(tmp_path, emails, second, retry=run1.dir)
    assert len(second.calls) == 1 and "Subject: RFQ 2" in second.calls[0]
    assert not out2["M2"]["needs_review"] and out2["M1"] == out["M1"]


def test_retry_does_not_call_for_non_retryable_failures(tmp_path: Path) -> None:
    emails = _inbox(tmp_path, n=1)
    run_dir = tmp_path / "runs" / "old"
    run_dir.mkdir(parents=True)
    (run_dir / "calls.jsonl").write_text("{}\n", encoding="utf-8")
    (run_dir / "failures.jsonl").write_text(
        json.dumps({"email": "M1", "error": "model output rejected", "retryable": False}) + "\n", encoding="utf-8")
    client = Fake()
    out, _ = _run(tmp_path, emails, client, retry=run_dir)
    assert client.calls == [] and out["M1"]["needs_review"]  # flagged, not re-paid for


def test_cli_retry_failed_resolution_and_bad_run(tmp_path: Path, capsys) -> None:
    import os

    emails = _inbox(tmp_path, n=1)
    out_path = tmp_path / "p.json"
    assert main(["parse", "--emails", str(emails), "--out", str(out_path), "--retry-failed", "no-such-run"]) == 2
    assert "no run log found" in capsys.readouterr().err
    # offline (conftest) first run -> retryable failure; retry by "latest" works without crashing
    assert main(["parse", "--emails", str(emails), "--out", str(out_path)]) == 0
    latest = Path(os.environ["RFQ_RUNS_DIR"]) / "latest"
    assert resolve_run_dir("latest") == latest
    assert main(["parse", "--emails", str(emails), "--out", str(out_path), "--retry-failed", "latest"]) == 0
    assert json.loads(out_path.read_text(encoding="utf-8"))["M1"]["needs_review"]
