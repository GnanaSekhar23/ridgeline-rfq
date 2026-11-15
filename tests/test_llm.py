"""Model-call tests with a fake OpenAI client (no network, no key)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import openai
import pytest

from rfq.cache import Cache
from rfq.llm import Extractor
from rfq.models import Doc, Email, ImagePart, Line
from rfq.prompt import build_messages
from rfq.schema import response_format

GOOD = {"result": {"kind": "rfq", "lines": [
    {"row_id": "body!B1", "image": None, "raw": "4 ea 2in tee", "description": "2in tee", "qty": 4, "uom": "EA"}],
    "sheet_decisions": [], "needs_review": False, "review_reason": None, "rationale": "asks for prices"}}


def _resp(content: str, finish: str = "stop", refusal=None, tokens=(1000, 200)):
    msg = SimpleNamespace(content=content, refusal=refusal)
    usage = SimpleNamespace(prompt_tokens=tokens[0], completion_tokens=tokens[1],
                            prompt_tokens_details=SimpleNamespace(cached_tokens=0))
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=finish)], usage=usage)


class FakeClient:
    """Replays a script of responses / exceptions; records every request."""

    def __init__(self, script):
        self.script = list(script)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _email() -> tuple[Email, list[Doc]]:
    e = Email(id="T1", headers={"subject": "RFQ"}, body="4 ea 2in tee")
    return e, [Doc(source="body", kind="body", lines=[Line("body!B1", "4 ea 2in tee")])]


def _transient() -> Exception:
    req = openai._base_client.httpx.Request("POST", "https://api.openai.com/v1/chat/completions") \
        if hasattr(openai._base_client, "httpx") else None
    return openai.APITimeoutError(request=req)


def _ex(tmp_path: Path, script) -> tuple[Extractor, FakeClient]:
    client = FakeClient(script)
    return Extractor(model="gpt-4.1", cache=Cache(tmp_path / "cache"), client=client, wait_max_s=0.01), client


def test_valid_answer_is_cached_and_second_run_makes_no_call(tmp_path: Path) -> None:
    ex, client = _ex(tmp_path, [_resp(json.dumps(GOOD))])
    e, docs = _email()
    first = ex.run(e, docs)
    assert first.extraction and not first.cache_hit and first.live_calls == 1
    assert first.cost_usd == pytest.approx((1000 * 2.0 + 200 * 8.0) / 1e6)
    second = ex.run(e, docs)  # script is empty now: any call would raise IndexError
    assert second.cache_hit and second.live_calls == 0 and second.live_cost_usd == 0
    assert second.cost_usd == first.cost_usd  # cost to produce is still reported
    assert len(client.requests) == 1


def test_request_uses_strict_schema_and_temperature_zero(tmp_path: Path) -> None:
    ex, client = _ex(tmp_path, [_resp(json.dumps(GOOD))])
    ex.run(*_email())
    req = client.requests[0]
    assert req["response_format"] == response_format() and req["temperature"] == 0
    assert req["messages"][0]["role"] == "system"


def test_invalid_then_repaired(tmp_path: Path) -> None:
    ex, client = _ex(tmp_path, [_resp('{"result": {"kind": "rfq"}}'), _resp(json.dumps(GOOD))])
    out = ex.run(*_email())
    assert out.extraction and out.live_calls == 2
    assert "corrected JSON" in client.requests[1]["messages"][-1]["content"]


def test_invalid_twice_is_error_and_not_cached(tmp_path: Path) -> None:
    ex, _ = _ex(tmp_path, [_resp("not json"), _resp("still not json")])
    out = ex.run(*_email())
    assert out.extraction is None and "rejected" in out.error and not out.retryable
    assert not list((tmp_path / "cache").glob("*.json")) if (tmp_path / "cache").exists() else True


def test_transient_errors_are_retried(tmp_path: Path) -> None:
    ex, _ = _ex(tmp_path, [_transient(), _transient(), _resp(json.dumps(GOOD))])
    out = ex.run(*_email())
    assert out.extraction and out.live_calls == 3


def test_transient_errors_exhausted_is_retryable_failure(tmp_path: Path) -> None:
    ex, _ = _ex(tmp_path, [_transient()] * 4)
    out = ex.run(*_email())
    assert out.extraction is None and out.retryable and out.live_calls == 4


def test_refusal_and_length_are_errors(tmp_path: Path) -> None:
    ex, _ = _ex(tmp_path, [_resp("", refusal="no")])
    assert "refused" in ex.run(*_email()).error
    ex, _ = _ex(tmp_path, [_resp('{"result":', finish="length")])
    assert "too long" in ex.run(*_email()).error


def test_no_key_and_cache_miss_is_flagged_not_crash(tmp_path: Path) -> None:
    ex = Extractor(model="gpt-4.1", cache=Cache(tmp_path / "cache"))  # offline via conftest
    out = ex.run(*_email())
    assert out.extraction is None and out.retryable and "no cached response" in out.error


def test_cache_key_changes_with_content_model_and_prompt_version(tmp_path: Path, monkeypatch) -> None:
    ex, _ = _ex(tmp_path, [_resp(json.dumps(GOOD))] * 3)
    e, docs = _email()
    k1 = ex.run(e, docs).key
    docs2 = [Doc(source="body", kind="body", lines=[Line("body!B1", "5 ea 2in tee")])]
    assert ex.run(e, docs2).key != k1
    import rfq.llm as llm

    monkeypatch.setattr(llm, "PROMPT_VERSION", "p-test")
    assert ex.run(e, docs).key != k1


def test_images_go_as_vision_parts() -> None:
    e = Email(id="T2", headers={}, body="see photo")
    docs = [Doc(source="body", kind="body", lines=[Line("body!B1", "see photo")]),
            Doc(source="IMG_1.jpg", kind="image", images=[ImagePart("IMG_1.jpg", b"\x89PNG", 10, 10)])]
    messages, _ = build_messages(e, docs)
    parts = messages[1]["content"]
    assert any(p["type"] == "image_url" and p["image_url"]["url"].startswith("data:image/png;base64,") for p in parts)
    assert any(p["type"] == "text" and p["text"] == "IMAGE label: IMG_1.jpg" for p in parts)


def test_key_is_never_written_to_cache_or_logs(tmp_path: Path, monkeypatch) -> None:
    from rfq.costlog import RunLog

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-SECRET-123")
    ex, _ = _ex(tmp_path, [_resp(json.dumps(GOOD))])
    log = RunLog("gpt-4.1", runs_dir=tmp_path / "runs", reports_dir=tmp_path / "reports")
    e, docs = _email()
    log.record(e.id, ex.run(e, docs))
    log.finish()
    for p in tmp_path.rglob("*"):
        if p.is_file():
            assert "SECRET" not in p.read_text(encoding="utf-8", errors="ignore"), p
