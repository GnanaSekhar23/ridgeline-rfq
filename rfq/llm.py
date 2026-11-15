"""One structured-output call per email, behind the cache.

Order: cache hit -> done (no network). Miss + no key / offline -> error outcome (flagged
upstream, never a crash). Miss + key -> call with retries on transient errors only
(429, 5xx, timeout, connection), validate against the schema, one repair turn if invalid,
cache only a valid result.

The API key is read by the OpenAI client from the environment. It is never logged or stored.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pydantic import ValidationError
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from rfq.cache import Cache, cache_key
from rfq.config import (MAX_OUTPUT_TOKENS, MAX_RETRIES, MODEL, PRICES, PROMPT_VERSION,
                        REQUEST_TIMEOUT_S, TEMPERATURE, api_key_present)
from rfq.models import Doc, Email
from rfq.prompt import build_messages, messages_fingerprint
from rfq.schema import Extraction, response_format


@dataclass
class Usage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.cached_input_tokens += other.cached_input_tokens
        self.output_tokens += other.output_tokens


def cost_usd(model: str, u: Usage) -> float:
    p_in, p_cached, p_out = PRICES.get(model, (0.0, 0.0, 0.0))
    fresh = max(0, u.input_tokens - u.cached_input_tokens)
    return (fresh * p_in + u.cached_input_tokens * p_cached + u.output_tokens * p_out) / 1e6


@dataclass
class Outcome:
    extraction: Extraction | None
    key: str
    cache_hit: bool = False
    live_calls: int = 0  # HTTP requests actually sent this run
    usage: Usage = field(default_factory=Usage)  # tokens of the call that produced the answer
    cost_usd: float = 0.0  # what producing the answer cost (also reported for cache hits)
    live_cost_usd: float = 0.0  # what THIS run paid (0 on a cache hit)
    latency_s: float = 0.0
    error: str | None = None
    retryable: bool = False
    prompt_truncated: bool = False
    # every raw response / exception this run, for diagnosis (saved to runs/ when rejected)
    raw_responses: list[dict] = field(default_factory=list)


def _transient(e: BaseException) -> bool:
    import openai

    if isinstance(e, (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError,
                      openai.InternalServerError)):
        return True
    return isinstance(e, openai.APIStatusError) and getattr(e, "status_code", 0) >= 500


def _usage(resp) -> Usage:
    u = getattr(resp, "usage", None)
    if u is None:
        return Usage()
    details = getattr(u, "prompt_tokens_details", None)
    return Usage(
        input_tokens=int(getattr(u, "prompt_tokens", 0) or 0),
        cached_input_tokens=int(getattr(details, "cached_tokens", 0) or 0) if details else 0,
        output_tokens=int(getattr(u, "completion_tokens", 0) or 0),
    )


def offline() -> bool:
    return os.environ.get("RFQ_OFFLINE", "").strip() not in ("", "0", "false")


class Extractor:
    def __init__(self, model: str = MODEL, cache: Cache | None = None, client=None,
                 wait_max_s: float = 20.0) -> None:
        self.model = model
        self.cache = cache or Cache()
        self._client = client
        self._schema = response_format()
        self._wait_max = wait_max_s

    def _get_client(self):
        if self._client is not None:
            return self._client
        if offline() or not api_key_present():
            return None
        from openai import OpenAI

        self._client = OpenAI(timeout=REQUEST_TIMEOUT_S, max_retries=0)  # we retry ourselves
        return self._client

    # ------------------------------------------------------------------ public
    def run(self, email: Email, docs: list[Doc], problems: list[str] | None = None) -> Outcome:
        messages, truncated = build_messages(email, docs, problems)
        key = cache_key(self.model, PROMPT_VERSION, self._schema, messages_fingerprint(messages))
        out = Outcome(extraction=None, key=key, prompt_truncated=truncated)

        hit = self.cache.get(key)
        if hit is not None:
            try:
                out.extraction = Extraction.model_validate(hit["response"])
                out.cache_hit = True
                out.usage = Usage(**hit.get("usage", {}))
                out.cost_usd = float(hit.get("cost_usd", 0.0))
                return out
            except (ValidationError, KeyError, TypeError):
                pass  # stale/corrupt entry: treat as a miss

        client = self._get_client()
        if client is None:
            out.error = "model unavailable (no API key or offline) and no cached response"
            out.retryable = True
            return out

        t0 = time.monotonic()
        try:
            self._call_and_validate(client, messages, out)
        except Exception as e:  # anything unexpected: flagged, never a crash
            out.error = f"model call failed: {type(e).__name__}: {str(e)[:300]}"
            out.retryable = _transient(e) or _auth_or_quota(e)
        out.latency_s = round(time.monotonic() - t0, 2)
        out.cost_usd = out.live_cost_usd = round(cost_usd(self.model, out.usage), 6)

        if out.extraction is not None:
            self.cache.put(key, {
                "key": key,
                "email_id": email.id,
                "model": self.model,
                "prompt_version": PROMPT_VERSION,
                "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "usage": out.usage.__dict__,
                "cost_usd": out.cost_usd,
                "response": out.extraction.model_dump(mode="json"),
            })
        return out

    # ------------------------------------------------------------------ internals
    def _send(self, client, messages: list[dict], out: Outcome):
        retrying = Retrying(
            retry=retry_if_exception(_transient),
            stop=stop_after_attempt(MAX_RETRIES + 1),
            wait=wait_exponential(multiplier=1, min=1, max=self._wait_max),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                out.live_calls += 1
                try:
                    resp = client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        response_format=self._schema,
                        temperature=TEMPERATURE,
                        max_completion_tokens=MAX_OUTPUT_TOKENS,
                    )
                except Exception as e:
                    out.raw_responses.append({"call": out.live_calls, "exception": f"{type(e).__name__}: {str(e)[:500]}"})
                    raise
                u = _usage(resp)
                out.usage.add(u)
                choice = resp.choices[0]
                out.raw_responses.append({
                    "call": out.live_calls,
                    "finish_reason": choice.finish_reason,
                    "refusal": getattr(choice.message, "refusal", None),
                    "usage": u.__dict__,
                    "content": choice.message.content,
                })
                return resp
        raise RuntimeError("unreachable")

    def _call_and_validate(self, client, messages: list[dict], out: Outcome) -> None:
        resp = self._send(client, messages, out)
        problem, extraction, content = _check(resp)
        if extraction is None and problem and problem.startswith("invalid"):
            repair = messages + [
                {"role": "assistant", "content": content or ""},
                {"role": "user", "content": f"That output was {problem}. Return the corrected JSON only."},
            ]
            resp = self._send(client, repair, out)
            problem, extraction, _ = _check(resp)
        out.extraction = extraction
        if extraction is None:
            out.error = f"model output rejected: {problem}"
            out.retryable = False
        for r in out.raw_responses:
            r.setdefault("verdict", None)
        if out.raw_responses:
            out.raw_responses[-1]["verdict"] = "accepted" if extraction is not None else problem


def _auth_or_quota(e: BaseException) -> bool:
    import openai

    return isinstance(e, (openai.AuthenticationError, openai.PermissionDeniedError))


def _check(resp) -> tuple[str | None, Extraction | None, str | None]:
    """(problem, extraction, raw content). problem starts with 'invalid' when a repair may help."""
    choice = resp.choices[0]
    msg = choice.message
    if getattr(msg, "refusal", None):
        return f"refused: {msg.refusal}", None, None
    if choice.finish_reason == "length":
        return "too long (hit the output token limit)", None, msg.content
    content = msg.content or ""
    try:
        return None, Extraction.model_validate(json.loads(content)), content
    except (ValueError, ValidationError) as e:
        return f"invalid: {str(e)[:400]}", None, content
