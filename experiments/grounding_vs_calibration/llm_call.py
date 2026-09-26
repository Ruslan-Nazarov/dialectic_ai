"""Minimal OpenAI-compatible chat call that reads token usage from each response directly.

Deliberately does not reuse dialectic_world/builder/blocks.py's ask(), whose before/after snapshot of a
shared ctx.llm.usage counter races under concurrent calls (see ENGINE_V3_RESULTS_INDEX.md). Every call
here returns its own usage straight from that call's response body, so concurrency cannot corrupt counts.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass


@dataclass
class CallResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    raw: dict


def chat_call(
    model: str,
    messages: list[dict],
    base_url: str,
    api_key_env: str,
    max_tokens: int = 500,
    temperature: float | None = None,
    extra: dict | None = None,
    max_tokens_param: str = "max_tokens",
) -> CallResult:
    api_key = os.environ.get(api_key_env, "")
    payload = {"model": model, "messages": messages, max_tokens_param: max_tokens}
    if temperature is not None:
        payload["temperature"] = temperature
    if extra:
        payload.update(extra)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')}") from e
    elapsed = time.monotonic() - started
    usage = data.get("usage", {})
    text = data["choices"][0]["message"].get("content", "")
    return CallResult(
        text=text,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        seconds=elapsed,
        raw=data,
    )
