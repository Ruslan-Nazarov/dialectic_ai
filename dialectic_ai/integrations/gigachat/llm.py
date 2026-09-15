import os
import time
import json
import asyncio
import urllib.request
import urllib.error
import ssl
import uuid

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.retry import RetryableError, retry_call
from dialectic_ai.core.schema import ModelResult

_RETRYABLE_HTTP_CODES = {401, 429, 500, 502, 503, 504}

@dialectical(
    origin="Integration with Sberbank GigaChat API",
    contradiction="GigaChat requires a 2-step auth (OAuth token) and specific SSL certificates",
    resolves="Internal automatic token management and unverified SSL context for the OAuth endpoint",
    generates="Seamless usage of GigaChat just like any OpenAI-compatible provider",
    own_contradictions="Token caching is basic and tied to the instance lifetime",
    layer=0,
)
class GigaChatLLM(BaseLLM):
    """
    Client for GigaChat API.
    Handles automatic OAuth token fetching and caching.
    """
    supports_native_tool_calling = False

    def __init__(self, auth_key: str = None, model: str = "GigaChat", max_tokens: int = 4096, max_retries: int = 3):
        self.auth_key = auth_key or os.getenv("GIGACHAT_AUTH_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self._access_token = None
        self._token_expires_at = 0

    def _get_access_token(self):
        """Fetches a new access token if the current one is missing or expired."""
        if not self.auth_key:
            raise ValueError("GIGACHAT_AUTH_KEY is not set")
            
        # Add 60s buffer for expiration
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {self.auth_key}"
        }
        data = f"scope={self.scope}".encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers=headers)
        
        # Bypass SSL verification for Russian certs if not installed
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                self._access_token = result.get("access_token")
                self._token_expires_at = result.get("expires_at", time.time() * 1000) / 1000.0
                return self._access_token
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            raise RuntimeError(f"GigaChat OAuth Error {e.code}: {err_msg}")
        except Exception as e:
            raise RuntimeError(f"GigaChat OAuth Failed: {e}")

    def _do_attempt(self, messages: list[dict]) -> str:
        """Performs a single completion attempt, refreshing the OAuth token first.

        The token is re-fetched (from cache, or the network if expired/cleared) on
        every attempt -- not just once before the retry loop -- so that a token that
        expires or is rejected mid-retry-loop is transparently replaced instead of
        being retried with the same stale credential.
        """
        token = self._get_access_token()

        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers)

        # Bypass SSL verification for Russian certs if not installed
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                choices = result.get("choices", [])
                if not choices:
                    return "{}"
                return choices[0]["message"]["content"]
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            message = f"GigaChat API Error {e.code}: {err_msg}"
            if e.code == 401:
                # Token may have expired or been rejected mid-loop -- force a real
                # refetch (not the cached one) on the next attempt.
                self._access_token = None
            if e.code in _RETRYABLE_HTTP_CODES:
                raise RetryableError(message, headers=e.headers) from e
            raise RuntimeError(message) from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise RetryableError(f"GigaChat Request Failed: {e}") from e

    def _call_sync(self, messages: list[dict]) -> str:
        return retry_call(
            lambda attempt: self._do_attempt(messages),
            max_retries=self.max_retries,
            on_retry=lambda attempt, e, wait: print(
                f"\n[GigaChatLLM] {e}, retrying in {wait:.1f}s (attempt {attempt + 1}/{self.max_retries})..."
            ),
        )

    async def generate(self, messages: list[dict], tools: list[dict] = None) -> str:
        return await asyncio.to_thread(self._call_sync, messages)

    async def generate_result(self, messages: list[dict], tools: list[dict] = None) -> ModelResult:
        text = await self.generate(messages, tools)
        return ModelResult(text=text)
