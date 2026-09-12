import os
import json
import asyncio
import urllib.request
import urllib.error

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.schema import ModelResult, ModelToolCall, ModelUsage


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
        api_key: str = None,
        base_url: str = None,
        model: str = "gpt-4o-mini",
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model

        # Fallbacks for other providers if OPENAI_API_KEY is not set
        if not self.api_key:
            if os.getenv("GROQ_API_KEY"):
                self.api_key = os.getenv("GROQ_API_KEY")
                self.base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
                self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            elif os.getenv("OPENROUTER_API_KEY"):
                self.api_key = os.getenv("OPENROUTER_API_KEY")
                self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
                self.model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")

    async def generate(self, messages: list[dict], tools: list[dict] = None) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
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
        req = urllib.request.Request(url, data=data, headers=headers)

        def _make_request():
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
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
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode("utf-8")
                raise RuntimeError(f"OpenAI API Error {e.code}: {err_msg}")
                
        return await asyncio.to_thread(_make_request)

    async def generate_result(self, messages: list[dict], tools: list[dict] = None) -> ModelResult:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
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
        req = urllib.request.Request(url, data=data, headers=headers)

        def _make_request():
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    message = result["choices"][0]["message"]
                    
                    # Extract usage
                    usage = None
                    if "usage" in result:
                        usage = ModelUsage(
                            prompt_tokens=result["usage"].get("prompt_tokens", 0),
                            completion_tokens=result["usage"].get("completion_tokens", 0),
                            total_tokens=result["usage"].get("total_tokens", 0)
                        )

                    # Extract tool calls directly to ModelToolCall
                    if "tool_calls" in message:
                        tool_calls = []
                        for tc in message["tool_calls"]:
                            if tc["type"] == "function":
                                tool_calls.append(ModelToolCall(
                                    id=tc.get("id"),
                                    name=tc["function"]["name"],
                                    arguments=json.loads(tc["function"]["arguments"])
                                ))
                        return ModelResult(
                            tool_calls=tool_calls,
                            usage=usage
                        )
                    
                    # Text fallback internally
                    return ModelResult(
                        text=message.get("content", ""),
                        usage=usage
                    )
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode("utf-8")
                raise RuntimeError(f"OpenAI API Error {e.code}: {err_msg}")
                
        return await asyncio.to_thread(_make_request)