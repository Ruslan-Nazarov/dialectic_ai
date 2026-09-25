import asyncio
import json
import os
import urllib.error
import urllib.request

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.retry import RetryableError, retry_call
from dialectic_ai.core.schema import ModelResult, ModelToolCall, ModelUsage
from typing import Optional

_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


def _is_openai_reasoning_model(model: str) -> bool:
    name = model.split("/")[-1].lower()
    return name.startswith(("o1", "o3", "o4", "gpt-5"))


@dialectical(
    origin="Integration with OpenAI / OpenRouter / Ollama / LM Studio via standard /v1/chat/completions",
    contradiction="Developers use different providers; hard binding to one vendor is unacceptable",
    resolves="Universal client for OpenAI-compatible protocol via urllib without the need to install openai SDK",
    generates="Free choice of inference provider: cloud or local",
    own_contradictions="Network latency and token costs of commercial providers",
    layer=0,
)
class OpenAILLM(BaseLLM):
    """
    Client for OpenAI-compatible REST APIs (OpenAI, OpenRouter, Ollama, vLLM).
    Uses the standard Python library (urllib).
    """
    supports_native_tool_calling = True

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4o-mini",
        max_tokens: int = 4096,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

    def _build_request(self, messages: list[dict], tools: Optional[list[dict]] = None) -> urllib.request.Request:
        url = f"{self.base_url}/chat/completions"
        payload = {"model": self.model, "messages": messages}
        if _is_openai_reasoning_model(self.model):
            # OpenAI reasoning models reject max_tokens and a non-default temperature, and spend
            # part of this budget on hidden reasoning before any visible output.
            payload["max_completion_tokens"] = self.max_tokens
        else:
            payload["temperature"] = 0.2
            payload["max_tokens"] = self.max_tokens
        if tools:
            payload["tools"] = tools
        else:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 DialecticAI/1.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = json.dumps(payload).encode("utf-8")
        return urllib.request.Request(url, data=data, headers=headers)

    def _do_attempt(self, req: urllib.request.Request) -> dict:
        """Performs a single HTTP attempt, raising RetryableError for transient failures."""
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            message = f"OpenAI API Error {e.code}: {err_msg}"
            if e.code in _RETRYABLE_HTTP_CODES:
                raise RetryableError(message, headers=e.headers) from e
            raise RuntimeError(message) from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise RetryableError(f"OpenAI API network error: {e}") from e

    def _call_sync(self, req: urllib.request.Request) -> dict:
        """Performs the HTTP call with retry/backoff on rate limits, transient server errors, and network faults."""
        return retry_call(
            lambda attempt: self._do_attempt(req),
            max_retries=self.max_retries,
            on_retry=lambda attempt, e, wait: print(
                f"\n[OpenAILLM] {e}, retrying in {wait:.1f}s (attempt {attempt + 1}/{self.max_retries})..."
            ),
        )

    async def generate(self, messages: list[dict], tools: Optional[list[dict]] = None) -> str:
        req = self._build_request(messages, tools)
        result = await asyncio.to_thread(self._call_sync, req)
        self._record_usage(result.get("usage"))
        message = result["choices"][0]["message"]

        if "tool_calls" in message:
            tool_calls = []
            for tc in message["tool_calls"]:
                if tc["type"] == "function":
                    tool_calls.append({
                        "name": tc["function"]["name"],
                        "args": json.loads(tc["function"]["arguments"])
                    })
            return json.dumps({
                "thought": "Invoking native tools",
                "tool_calls": tool_calls
            })
        return message.get("content", "{}")

    async def generate_result(self, messages: list[dict], tools: Optional[list[dict]] = None) -> ModelResult:
        req = self._build_request(messages, tools)
        result = await asyncio.to_thread(self._call_sync, req)
        message = result["choices"][0]["message"]

        usage = self._record_usage(result.get("usage"))
        if usage:
            print(f"[LLM] Call Usage: {usage.prompt_tokens} input, {usage.completion_tokens} output, {usage.total_tokens} total tokens.")

        if "tool_calls" in message:
            tool_calls = []
            for tc in message["tool_calls"]:
                if tc["type"] == "function":
                    tool_calls.append(ModelToolCall(
                        id=tc.get("id"),
                        name=tc["function"]["name"],
                        arguments=json.loads(tc["function"]["arguments"])
                    ))
            return ModelResult(tool_calls=tool_calls, usage=usage)

        return ModelResult(text=message.get("content", ""), usage=usage)

