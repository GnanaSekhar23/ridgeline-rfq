import json
import subprocess
import sys
from pathlib import Path

from rfq.cli import main
from rfq.pipeline import process_inbox

ROOT = Path(__file__).resolve().parent.parent


def test_every_email_appears_and_shape_ok(tmp_path: Path) -> None:
    (tmp_path / "A1.eml").write_bytes(b"Subject: hi\r\n\r\nhello\r\n")
    (tmp_path / "A2.eml").write_bytes(b"Subject: two\r\n\r\nbody\r\n")
    out = tmp_path / "parsed.json"
    assert main(["parse", "--emails", str(tmp_path), "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data) == {"A1", "A2"}
    check = subprocess.run(
        [sys.executable, str(ROOT / "data" / "check_format.py"), str(out), "--emails", str(tmp_path)],
        capture_output=True,
    )
    assert check.returncode == 0, check.stdout


def test_one_bad_email_does_not_crash(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "good.eml").write_bytes(b"Subject: ok\r\n\r\nx\r\n")
    (tmp_path / "bad.eml").write_bytes(b"Subject: boom\r\n\r\nx\r\n")

    import rfq.pipeline as pl

    real = pl.process_email

    def flaky(email, parent=None, ctx=None):
        if email.id == "bad":
            raise ValueError("simulated")
        return real(email, parent, ctx)

    monkeypatch.setattr(pl, "process_email", flaky)
    data = process_inbox(tmp_path)
    assert data["bad"]["needs_review"] is True
    assert "simulated" in data["bad"]["review_reason"]
    # offline, no cache: the good email is flagged (not crashed, not silently dropped)
    assert data["good"]["needs_review"] is True
    assert "no cached response" in data["good"]["review_reason"]


def test_parse_writes_run_log_and_cost_report(tmp_path: Path) -> None:
    import os

    (tmp_path / "A1.eml").write_bytes(b"Subject: hi\r\n\r\nhello\r\n")
    assert main(["parse", "--emails", str(tmp_path), "--out", str(tmp_path / "p.json")]) == 0
    runs = Path(os.environ["RFQ_RUNS_DIR"])
    assert (runs / "latest" / "calls.jsonl").exists()
    assert (runs / "latest" / "failures.jsonl").read_text(encoding="utf-8").count('"retryable": true') == 1
    assert (Path(os.environ["RFQ_REPORTS_DIR"]) / "cost.md").exists()
