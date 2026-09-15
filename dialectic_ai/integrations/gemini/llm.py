import os
import json
import asyncio
import urllib.request
import urllib.error
from pathlib import Path

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.retry import RetryableError, retry_call

_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


def _load_env_file():
    """Simple loading of .env without external dependencies."""
    env_paths = [Path(".env"), Path(__file__).resolve().parents[3] / ".env"]
    for p in env_paths:
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
            except Exception:
                pass


_load_env_file()


@dialectical(
    origin="Integration with Google Gemini API for real agent reasoning",
    contradiction="MockLLM is predictable but cannot reason. A real model is needed without bloating dependencies",
    resolves="Clean implementation of Gemini REST API via standard urllib. Does not require third-party SDKs",
    generates="Full autonomous operation of the tutor agent in real time",
    own_contradictions="Dependence on the stability of the external Google API and network connection",
    layer=0,
)
class GeminiLLM(BaseLLM):
    """
    Client for Google Gemini REST API.
    Uses the standard Python library (urllib).
    """

    def __init__(self, api_key: str = None, model: str = None, max_retries: int = 3):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self.max_retries = max_retries

    def _do_attempt(self, req: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            message = f"Gemini API Error {e.code}: {err_msg}"
            if e.code in _RETRYABLE_HTTP_CODES:
                raise RetryableError(message, headers=e.headers) from e
            raise RuntimeError(message) from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise RetryableError(f"Gemini Request Failed: {e}") from e

    def _call_sync(self, req: urllib.request.Request) -> dict:
        return retry_call(
            lambda attempt: self._do_attempt(req),
            max_retries=self.max_retries,
            on_retry=lambda attempt, e, wait: print(
                f"\n[GeminiLLM] {e}, retrying in {wait:.1f}s (attempt {attempt + 1}/{self.max_retries})..."
            ),
        )

    async def generate(self, messages: list[dict], tools: list[dict] = None) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in arguments or in environment variables / .env")

        # Collecting context from all messages in dialogue format
        prompt_parts = []
        for m in messages:
            role = "Model" if m["role"] == "assistant" else ("System" if m["role"] == "system" else "User")
            prompt_parts.append(f"{role}: {m['content']}")

        full_prompt = "\n\n".join(prompt_parts) + "\n\nModel:"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        result = await asyncio.to_thread(self._call_sync, req)
        candidates = result.get("candidates", [])
        if not candidates:
            return "{}"
        return candidates[0]["content"]["parts"][0]["text"]