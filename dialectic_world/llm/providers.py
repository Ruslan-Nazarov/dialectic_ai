"""Model providers: OpenAI-compatible HTTP APIs and Anthropic. Spec strings are "provider" or "provider:model".

Copied and trimmed from engine v2 (integrations/openai, integrations/anthropic, core/retry).
"""
import asyncio
import json
import os
import random
import ssl
import time
import urllib.error
import urllib.request
import uuid

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


class GigaChat(LLM):
    """Sber GigaChat: OAuth2 client-credentials token (cached, refreshed on 401), then chat/completions.
    Personal API accounts allow only one in-flight request, so calls are serialized here."""

    def __init__(self, model: str = "GigaChat", max_tokens: int = 8000, timeout: int = 150):
        super().__init__(model=model)
        self.max_tokens, self.timeout = max_tokens, timeout
        self._token, self._expires_at = "", 0.0
        self._auth_lock = asyncio.Lock()
        self._requests = asyncio.Semaphore(1)
        self._client = None

    async def _http(self):
        if self._client is None:
            import httpx
            ctx = ssl.create_default_context()
            ca_path = os.getenv("GIGACHAT_CA_BUNDLE")
            if ca_path:
                ctx.load_verify_locations(ca_path)
            self._client = httpx.AsyncClient(verify=ctx, timeout=httpx.Timeout(self.timeout, connect=15))
        return self._client

    async def _authorize(self) -> str:
        async with self._auth_lock:
            if self._token and time.time() < self._expires_at - 60:
                return self._token
            secret = os.getenv("GIGACHAT_CREDENTIALS", "").strip()
            if not secret:
                raise RuntimeError("GIGACHAT_CREDENTIALS is not set")
            client = await self._http()
            response = await client.post(
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                headers={"Authorization": f"Basic {secret}", "RqUID": str(uuid.uuid4()), "Accept": "application/json"},
                data={"scope": os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")},
            )
            response.raise_for_status()
            data = response.json()
            token, expiry = data["access_token"], float(data["expires_at"])
            if expiry > 100_000_000_000:  # some deployments return milliseconds
                expiry /= 1000
            if not isinstance(token, str) or not token or expiry <= time.time():
                raise RuntimeError("GigaChat: invalid OAuth response")
            self._token, self._expires_at = token, expiry
            return token

    async def _complete(self, messages):
        async with self._requests:
            client = await self._http()
            for attempt in range(2):
                token = await self._authorize()
                response = await client.post(
                    "https://api.giga.chat/v1/chat/completions",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"model": self.model, "messages": messages, "temperature": 0.2,
                          "max_tokens": self.max_tokens, "stream": False},
                )
                if response.status_code == 401 and attempt == 0:
                    self._token = ""
                    continue
                response.raise_for_status()
                data = response.json()
                text = data["choices"][0]["message"].get("content") or ""
                usage = data.get("usage") or {}
                return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
            raise RuntimeError("GigaChat: could not authorize")


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
    if provider == "gigachat":
        return GigaChat(model=model or os.getenv("GIGACHAT_MODEL", "GigaChat"))
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
