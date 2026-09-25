"""Claude via the official Anthropic SDK (Messages API)."""
import json
import os
from typing import Optional

from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.schema import ModelResult, ModelToolCall

DEFAULT_MODEL = "claude-opus-5-5"
# Thinking is adaptive by default on this model and shares max_tokens with the visible answer, so a
# small role budget (DIALECTIC_LIVE_MAX_TOKENS is sized for chat models) would cut answers off.
MIN_MAX_TOKENS = 16000


def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """The Messages API takes the system prompt separately and only user/assistant turns."""
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    turns = []
    for m in messages:
        if m.get("role") == "system":
            continue
        role = "assistant" if m.get("role") == "assistant" else "user"
        content = m.get("content") or ""
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n\n" + content
        else:
            turns.append({"role": role, "content": content})
    return system, turns


def _tools(tools: Optional[list[dict]]) -> list[dict]:
    """OpenAI-style function tools -> Anthropic tools."""
    converted = []
    for t in tools or []:
        fn = t.get("function", t)
        converted.append({"name": fn["name"], "description": fn.get("description", ""),
                          "input_schema": fn.get("parameters") or {"type": "object", "properties": {}}})
    return converted


class AnthropicLLM(BaseLLM):
    supports_native_tool_calling = True

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL, max_tokens: int = MIN_MAX_TOKENS,
                 timeout: int = 300, max_retries: int = 3):
        self.api_key = api_key if api_key is not None else os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key or None, timeout=self.timeout,
                                                    max_retries=self.max_retries)
        return self._client

    async def _create(self, messages, tools):
        system, turns = _split_system(messages)
        kwargs = {"model": self.model, "max_tokens": max(self.max_tokens, MIN_MAX_TOKENS), "messages": turns}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _tools(tools)
        response = await self._get_client().messages.create(**kwargs)
        usage = self._record_usage({"prompt_tokens": response.usage.input_tokens,
                                    "completion_tokens": response.usage.output_tokens})
        return response, usage

    async def generate(self, messages: list[dict], tools: Optional[list[dict]] = None) -> str:
        response, _ = await self._create(messages, tools)
        calls = [{"name": b.name, "args": b.input} for b in response.content if b.type == "tool_use"]
        if calls:
            return json.dumps({"thought": "Invoking native tools", "tool_calls": calls})
        return "".join(b.text for b in response.content if b.type == "text")

    async def generate_result(self, messages: list[dict], tools: Optional[list[dict]] = None) -> ModelResult:
        response, usage = await self._create(messages, tools)
        calls = [ModelToolCall(id=b.id, name=b.name, arguments=b.input) for b in response.content if b.type == "tool_use"]
        if calls:
            return ModelResult(tool_calls=calls, usage=usage)
        return ModelResult(text="".join(b.text for b in response.content if b.type == "text"), usage=usage)
