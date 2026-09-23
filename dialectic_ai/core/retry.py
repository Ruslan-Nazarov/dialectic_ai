"""
dialectic_ai/core/retry.py

DIALECTICAL DESCRIPTION:
  Origin: Each LLM provider (OpenAI, Gemini, GigaChat) needs to survive transient
    failures (rate limits, 5xx, network blips) without crashing the whole agent run.
  Contradiction: OpenAILLM grew a correct, tested retry/backoff loop; GeminiLLM grew
    an older, cruder one (and one that treats *any* exception as retryable, masking
    real bugs); GigaChatLLM had none at all. Three independent answers to the same
    question, one of them wrong-by-omission.
  How it resolves: One shared retry_call()/RetryableError pair. A provider's own
    per-attempt code decides what is retryable (only it knows which HTTP codes and
    provider-specific conditions -- e.g. GigaChat's token expiry -- are transient);
    everything else (the loop, the backoff schedule, the logging hook) is shared.
  What it leads to: Fixing or tuning backoff behavior once instead of three times;
    a new provider integration gets correct retry behavior by raising RetryableError
    instead of reimplementing a loop.
  Its own contradictions: The abstraction can't know about provider-specific side
    effects that must run before every attempt (e.g. refreshing an OAuth token) --
    callers must fold those into their own attempt function, not into this module.
"""
import random
import time
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


class RetryableError(RuntimeError):
    """Raised by an attempt function to signal a transient failure retry_call may retry.

    Any other exception raised by the attempt function is treated as non-retryable
    and propagates immediately.
    """

    def __init__(self, message: str, *, headers: Optional[dict] = None):
        super().__init__(message)
        self.headers = headers


def compute_backoff(attempt: int, headers: Optional[dict] = None) -> float:
    """Exponential backoff with jitter, honoring Retry-After / x-ratelimit-reset-tokens hints."""
    base = min(2 ** attempt, 30)
    wait_time = base + random.uniform(0, 1)
    if headers:
        retry_after = headers.get("retry-after")
        reset_tokens = headers.get("x-ratelimit-reset-tokens")
        for raw in (reset_tokens, retry_after):
            if not raw:
                continue
            try:
                wait_time = max(wait_time, float(str(raw).replace("s", "").strip()))
            except ValueError:
                pass
    return wait_time


def retry_call(
    attempt_fn: Callable[[int], T],
    *,
    max_retries: int,
    on_retry: Optional[Callable[[int, RetryableError, float], None]] = None,
) -> T:
    """
    Calls attempt_fn(attempt) up to max_retries + 1 times total (attempt starts at 0).

    attempt_fn must raise RetryableError for a failure worth retrying, and any other
    exception for a failure that should propagate immediately. Sleeps synchronously
    between attempts (call via asyncio.to_thread from async code, as the LLM
    providers in this codebase already do for their HTTP calls).
    """
    last_error: Optional[RetryableError] = None
    for attempt in range(max_retries + 1):
        try:
            return attempt_fn(attempt)
        except RetryableError as e:
            last_error = e
            if attempt < max_retries:
                wait_time = compute_backoff(attempt, e.headers)
                if on_retry:
                    on_retry(attempt, e, wait_time)
                time.sleep(wait_time)
                continue
            raise
    raise last_error or RuntimeError("retry_call exhausted with no captured error.")

