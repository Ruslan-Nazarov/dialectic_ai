"""Batched Jev calls: several questions in one POST /v1/systemone request, sharing one `state`.

This is new functionality, not present in ../grounding_vs_calibration/decider.py's JevDecider (whose
_ask_choice sends exactly one question per call). Written fresh here rather than editing that file, per
PREREGISTRATION.md's reuse-by-import-only rule. Uses the same protocol, documented at
https://docs.typesafe.ai/api.md: request {"state", "model", "questions": {qid: {type, instructions,
criteria}, ...}}, response {"answers": {qid: {...}}, "usage": {"input_tokens", "output_tokens"}}.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass
class BatchResult:
    answers: dict  # qid -> {"type": ..., ...}
    input_tokens: int
    output_tokens: int
    seconds: float
    request_id: str | None = None
    raw: dict = field(default_factory=dict)


class JevAPIError(Exception):
    """Carries the HTTP status (None for a network-level failure: timeout/connection error)
    so callers can decide retryable (429, 5xx, network) vs permanent (400 etc.) without
    re-parsing a message string."""

    def __init__(self, status_code: int | None, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")

    @property
    def retryable(self) -> bool:
        return self.status_code is None or self.status_code == 429 or (
            self.status_code is not None and 500 <= self.status_code < 600
        )


def call_systemone(
    state,
    questions: dict,
    model: str = "jev-latest",
    api_key_env: str = "TYPESAFE_API_KEY",
    base_url: str = "https://api.typesafe.ai",
    timeout: float = 90,
) -> BatchResult:
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise RuntimeError(f"{api_key_env} not set (load .env before calling this)")
    body = json.dumps({"state": state, "model": model, "questions": questions}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/v1/systemone",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            request_id = resp.headers.get("x-typesafe-request-id")
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise JevAPIError(e.code, e.read().decode(errors="replace")) from e
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        raise JevAPIError(None, f"{type(e).__name__}: {e}") from e
    elapsed = time.monotonic() - started
    usage = data.get("usage", {})
    return BatchResult(
        answers=data.get("answers", {}),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        seconds=elapsed,
        request_id=request_id,
        raw=data,
    )


def call_systemone_with_retry(
    state,
    questions: dict,
    max_retries: int = 3,
    backoff_base: float = 1.5,
    **kwargs,
) -> BatchResult:
    """Retries retryable errors (429, 5xx, network/timeout) up to `max_retries` times with
    exponential backoff (backoff_base, backoff_base*2, backoff_base*4, ...). A non-retryable
    error (e.g. 400 max_tokens_exceeded) is raised immediately, no retry. If retries are
    exhausted, the last JevAPIError is raised -- the caller records it as a permanent failure,
    never silently drops it.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return call_systemone(state, questions, **kwargs)
        except JevAPIError as e:
            last_exc = e
            if not e.retryable or attempt == max_retries:
                raise
            time.sleep(backoff_base * (2 ** attempt))
    raise last_exc  # unreachable, satisfies type checkers


def choice_question(instructions: str, criteria: dict[str, str]) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def noul_question(instructions, criteria: dict[str, str] | None = None) -> dict:
    q = {"type": "noul", "instructions": instructions}
    if criteria:
        q["criteria"] = criteria
    return q
