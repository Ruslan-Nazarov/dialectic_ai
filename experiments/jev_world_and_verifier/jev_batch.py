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
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')}") from e
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


def choice_question(instructions: str, criteria: dict[str, str]) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def noul_question(instructions, criteria: dict[str, str] | None = None) -> dict:
    q = {"type": "noul", "instructions": instructions}
    if criteria:
        q["criteria"] = criteria
    return q
