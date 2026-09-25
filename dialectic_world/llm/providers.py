"""Model providers: OpenAI-compatible HTTP APIs and Anthropic. Spec strings are "provider" or "provider:model".

Copied and trimmed from engine v2 (integrations/openai, integrations/anthropic, core/retry).
"""
import asyncio
import json
import os
import random
import time
import urllib.error
import urllib.request

from dialectic_world.llm.base import LLM, FallbackLLM

RETRYABLE_HTTP = {429, 500, 502, 503, 504}

# provider -> (base url, key env var, default model)
OPENAI_COMPATIBLE = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-5"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "gpt-oss-120b"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", None),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY", None),
}


class Retryable(RuntimeError):
    pass


def _backoff(attempt: int) -> float:
    return min(2 ** attempt, 30) + random.uniform(0, 1)


def _is_reasoning_model(model: str) -> bool:
    # OpenAI reasoning models reject max_tokens and a non-default temperature.
    return model.split("/")[-1].lower().startswith(("o1", "o3", "o4", "gpt-5"))


class OpenAICompatible(LLM):
    def __init__(self, model: str, base_url: str, api_key: str, max_tokens: int = 16000, timeout: int = 300,
                 max_retries: int = 3):
        super().__init__(model=model)
        self.base_url, self.api_key = base_url.rstrip("/"), api_key
        self.max_tokens, self.timeout, self.max_retries = max_tokens, timeout, max_retries

    def _request(self, messages):
        payload = {"model": self.model, "messages": messages, "response_format": {"type": "json_object"}}
        if _is_reasoning_model(self.model):
            payload["max_completion_tokens"] = self.max_tokens
        else:
            payload["max_tokens"], payload["temperature"] = self.max_tokens, 0.2
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(payload).encode("utf-8"),
                                      headers=headers)

    def _call(self, messages):
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(self._request(messages), timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:500]
                if exc.code not in RETRYABLE_HTTP or attempt == self.max_retries:
                    raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == self.max_retries:
                    raise RuntimeError(f"network: {exc}") from exc
            time.sleep(_backoff(attempt))

    async def _complete(self, messages):
        data = await asyncio.to_thread(self._call, messages)
        usage = data.get("usage") or {}
        text = data["choices"][0]["message"].get("content") or ""
        return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


class Anthropic(LLM):
    def __init__(self, model: str = "claude-opus-5-5", max_tokens: int = 16000, timeout: int = 300, max_retries: int = 3):
        super().__init__(model=model)
        self.max_tokens, self.timeout, self.max_retries = max_tokens, timeout, max_retries
        self._client = None

    async def _complete(self, messages):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(timeout=self.timeout, max_retries=self.max_retries)
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        turns = [{"role": "assistant" if m["role"] == "assistant" else "user", "content": m["content"]}
                 for m in messages if m["role"] != "system"]
        kwargs = {"model": self.model, "max_tokens": self.max_tokens, "messages": turns}
        if system:
            kwargs["system"] = system
        response = await self._client.messages.create(**kwargs)
        text = "".join(b.text for b in response.content if b.type == "text")
        return text, response.usage.input_tokens, response.usage.output_tokens


def build_llm(spec: str) -> LLM:
    """ "openai:gpt-5", "cerebras", "anthropic:claude-opus-5-5", or a comma-separated fallback chain."""
    specs = [s.strip() for s in spec.split(",") if s.strip()]
    if len(specs) > 1:
        return FallbackLLM([build_llm(s) for s in specs])
    provider, _, model = specs[0].partition(":")
    provider = provider.lower()
    if provider == "anthropic":
        return Anthropic(model=model or os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"))
    if provider in OPENAI_COMPATIBLE:
        url, key_var, default = OPENAI_COMPATIBLE[provider]
        model = model or os.getenv(f"{provider.upper()}_MODEL") or default
        if not model:
            raise ValueError(f"{provider}: name a model, e.g. {provider}:<model>")
        key = os.getenv(key_var, "")
        base = os.getenv(f"{provider.upper()}_BASE_URL", url)
        if not key and base == url:
            raise ValueError(f"{key_var} is not set")
        return OpenAICompatible(model=model, base_url=base, api_key=key)
    raise ValueError(f"unknown provider: {provider}")
