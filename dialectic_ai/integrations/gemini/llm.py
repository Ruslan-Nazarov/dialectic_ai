import os
import time
import json
import asyncio
import urllib.request
import urllib.error
from pathlib import Path

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.llm import BaseLLM


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

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

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

        max_retries = 5
        
        def _make_request():
            for attempt in range(max_retries):
                try:
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        result = json.loads(resp.read().decode("utf-8"))
                        candidates = result.get("candidates", [])
                        if not candidates:
                            return "{}"
                        return candidates[0]["content"]["parts"][0]["text"]
                except urllib.error.HTTPError as e:
                    err_msg = e.read().decode("utf-8")
                    if e.code in (429, 503) and attempt < max_retries - 1:
                        time.sleep(3 * (attempt + 1))
                        continue
                    raise RuntimeError(f"Gemini API Error {e.code}: {err_msg}")
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(3 * (attempt + 1))
                        continue
                    raise RuntimeError(f"Gemini Request Failed: {e}")
                    
        return await asyncio.to_thread(_make_request)