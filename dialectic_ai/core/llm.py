"""
dialectic_ai/core/llm.py

DIALECTICAL DESCRIPTION:
  Origin: The agent's code directly depends on a specific API (OpenAI,
    Gemini). Changing the provider requires rewriting the entire agent logic.
  Contradiction: The agent should think about its task, not the details of HTTP
    requests. A tight coupling to the provider kills portability.
  How it resolves: Introduces the BaseLLM abstraction with a single method generate().
    MockLLM allows developing and testing the entire framework without API keys
    and real costs — confronting reality at the architectural level.
  What it leads to: DialecticalEngine operates only on BaseLLM — it doesn't care
    whether it's Gemini or local Llama. Adding a new provider = one new class.
  Its own contradictions: The abstraction hides the unique capabilities of
    providers (function calling, vision, embeddings). Interface extensions
    or specialized subclasses are needed.
"""
import time
from abc import ABC, abstractmethod

from dialectic_ai.core.dialectical import DialecticalObject, dialectical
from dialectic_ai.core.schema import ModelResult


class BaseLLM(ABC, DialecticalObject):
    """Abstraction over any language model."""
    supports_native_tool_calling: bool = False

    def __new__(cls, *args, **kwargs):
        import os
        override = os.getenv("DIALECTIC_LLM_OVERRIDE", "").lower().strip()
        if override and not getattr(cls, "_in_override", False):
            try:
                cls._in_override = True
                if override == "gemini" and cls.__name__ != "GeminiLLM":
                    from dialectic_ai.integrations.gemini.llm import GeminiLLM
                    return GeminiLLM()
                elif override == "gigachat" and cls.__name__ != "GigaChatLLM":
                    from dialectic_ai.integrations.gigachat.llm import GigaChatLLM
                    return GigaChatLLM()
                elif override in ("openai", "groq", "openrouter", "cerebras") and cls.__name__ != "OpenAILLM":
                    from dialectic_ai.integrations.openai.llm import OpenAILLM
                    return OpenAILLM()
                elif override == "mock" and cls.__name__ != "MockLLM":
                    from dialectic_ai.core.llm import MockLLM
                    return MockLLM()
            except Exception:
                pass
            finally:
                cls._in_override = False
        return super().__new__(cls)

    @abstractmethod
    async def generate(self, messages: list[dict], tools: list[dict] = None) -> str:
        """
        Generates a response based on the message history.

        Args:
            messages: A list of messages in the format [{"role": "...", "content": "..."}]

        Returns:
            String — the raw response from the model (usually JSON for our agent)
        """
        ...

    async def generate_result(self, messages: list[dict], tools: list[dict] = None) -> ModelResult:
        """
        Generates a structured result from the language model, including text and native tool calls.
        
        Args:
            messages: A list of messages in the format [{"role": "...", "content": "..."}]
            tools: Tools to expose to the LLM.
        
        Returns:
            ModelResult
        """
        text = await self.generate(messages, tools)
        return ModelResult(text=text)


@dialectical(
    origin="Need to write and test the framework before obtaining a real API key",
    contradiction="Without LLM, no tests can be run. Circular dependency.",
    resolves="Returns predefined responses. Allows simulating any scenario "
             "of the agent's operation, including errors and edge cases",
    generates="Ability to write a complete test of the engine (engine.py) before connecting a real LLM",
    own_contradictions="Mock does not reflect the real behavior of LLM — hallucinations, delays, "
                       "token limits. Tests on Mock can give a false sense of reliability",
    layer=0,
)
class MockLLM(BaseLLM):
    """
    Test LLM with predefined responses.
    Used during development and in unit tests.
    """

    def __init__(self, responses: list[str] = None):
        """
        Args:
            responses: Queue of responses. Returned one at a time for each call.
                       After exhaustion — returns the last response.
        """
        self._responses = responses or [
            '{"thought": "MockLLM: analyzing the request", "tool_calls": [], "response": "This is the response from MockLLM."}'
        ]
        self._index = 0

    async def generate(self, messages: list[dict], tools: list[dict] = None) -> str:
        response = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        return response

    async def generate_result(self, messages: list[dict], tools: list[dict] = None) -> ModelResult:
        text = await self.generate(messages, tools)
        return ModelResult(text=text)


import warnings


def __getattr__(name):
    if name == "GeminiLLM":
        warnings.warn("GeminiLLM has been moved to dialectic_ai.integrations.gemini.llm.GeminiLLM", DeprecationWarning, stacklevel=2)
        from dialectic_ai.integrations.gemini.llm import GeminiLLM
        return GeminiLLM
    if name == "OpenAILLM":
        warnings.warn("OpenAILLM has been moved to dialectic_ai.integrations.openai.llm.OpenAILLM", DeprecationWarning, stacklevel=2)
        from dialectic_ai.integrations.openai.llm import OpenAILLM
        return OpenAILLM
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


@dialectical(
    origin="Interfaces of external APIs can fail with 503 or 429, which kills the entire agent process",
    contradiction="Binding to a single model makes the architecture fragile. Fault tolerance is needed",
    resolves="Chain of Responsibility pattern: sequentially tries to call models from the list. If one fails — tries the next",
    generates="Highly Available model orchestration system that does not fail due to a single provider",
    own_contradictions="Increases latency if the first models take a long time to return an error. Does not solve the problem when all providers fail",
    layer=0,
)
class FallbackLLM(BaseLLM):
    """
    LLM orchestrator (router / fallback chain).
    Takes a list of providers and attempts to perform generation in sequence.
    If a provider throws an exception, it moves to the next one.
    """

    def __init__(self, providers: list[BaseLLM]):
        if not providers:
            raise ValueError("FallbackLLM requires at least one provider")
        self.providers = providers

    async def generate(self, messages: list[dict], tools: list[dict] = None) -> str:
        last_error = None
        for i, provider in enumerate(self.providers):
            provider_name = provider.__class__.__name__
            try:
                # Attempting to generate a response
                return await provider.generate(messages, tools=tools)
            except Exception as e:
                print(f"  [FallbackLLM] Provider {provider_name} ({i+1}/{len(self.providers)}) returned an error: {e}")
                last_error = e
                continue
                
        # If no provider worked
        raise RuntimeError(f"All {len(self.providers)} LLM providers are unavailable. Last error: {last_error}")

    async def generate_result(self, messages: list[dict], tools: list[dict] = None) -> ModelResult:
        last_error = None
        for i, provider in enumerate(self.providers):
            provider_name = provider.__class__.__name__
            try:
                # Attempting to generate a response
                return await provider.generate_result(messages, tools=tools)
            except Exception as e:
                print(f"  [FallbackLLM] Provider {provider_name} ({i+1}/{len(self.providers)}) returned an error: {e}")
                last_error = e
                continue
                
        # If no provider worked
        raise RuntimeError(f"All {len(self.providers)} LLM providers are unavailable. Last error: {last_error}")


@dialectical(
    origin="A single API provider hits rate limits or introduces bottlenecks",
    contradiction="We have multiple API keys but the agent only uses one, wasting potential throughput",
    resolves="Round-robin load balancer that distributes requests evenly across all available LLM providers",
    generates="Higher overall throughput and speed by parallelizing across rate limits",
    own_contradictions="Different models might have slightly different reasoning capabilities, causing inconsistent agent behavior",
    layer=0,
)
class BalancingLLM(BaseLLM):
    """
    LLM orchestrator (load balancer).
    Takes a list of providers and distributes requests across them in a round-robin fashion.

    A provider that fails with a rate-limit or auth error twice in a row (across
    calls, not just within one) is put on cooldown for the rest of the session
    instead of staying in the rotation and wasting a request every Nth call --
    see development_log.md 2026-09-15 for the live RuntimeError this fixes.
    """
    def __init__(self, providers: list[BaseLLM], cooldown_seconds: float = 300.0):
        if not providers:
            raise ValueError("BalancingLLM requires at least one provider")
        self.providers = providers
        self.cooldown_seconds = cooldown_seconds
        self._index = 0
        self._cooldown_until: dict[int, float] = {}
        self._consecutive_failures: dict[int, int] = {}

    @staticmethod
    def _is_rate_or_auth_error(e: Exception) -> bool:
        err = str(e).lower()
        return any(token in err for token in ("429", "401", "403", "too many requests", "unauthorized", "forbidden"))

    def _available_providers(self) -> list[BaseLLM]:
        now = time.time()
        available = [p for p in self.providers if self._cooldown_until.get(id(p), 0) <= now]
        # If everyone is cooling down, degrade gracefully rather than hard-failing.
        return available or self.providers

    async def preflight_health_check(self):
        working = []
        for provider in self.providers:
            try:
                await provider.generate([{"role": "user", "content": "ping json"}])
                working.append(provider)
            except Exception as e:
                err = str(e).lower()
                if "404" in err or "400" in err or "decommissioned" in err or "not found" in err:
                    print(f"  [BalancingLLM] WARNING: Provider {provider.__class__.__name__} is decommissioned/broken (Error: {e}). Evicting from pool.")
                else:
                    working.append(provider)
                    print(f"  [BalancingLLM] Notice: Provider {provider.__class__.__name__} failed check with {e}, but keeping in pool.")
        self.providers = working
        if not self.providers:
            raise RuntimeError("All LLM providers are unavailable. Please check your .env config.")

    async def _call_with_balancing(self, method_name: str, messages: list[dict], tools: list[dict] = None):
        last_error = None
        available = self._available_providers()
        for _ in range(len(available)):
            provider = available[self._index % len(available)]
            self._index += 1
            try:
                result = await getattr(provider, method_name)(messages, tools=tools)
                self._consecutive_failures[id(provider)] = 0
                return result
            except Exception as e:
                print(f"  [BalancingLLM] Provider {provider.__class__.__name__} failed: {e}")
                last_error = e
                if self._is_rate_or_auth_error(e):
                    count = self._consecutive_failures.get(id(provider), 0) + 1
                    self._consecutive_failures[id(provider)] = count
                    if count >= 2:
                        self._cooldown_until[id(provider)] = time.time() + self.cooldown_seconds
                        print(f"  [BalancingLLM] Provider {provider.__class__.__name__} rate/auth-limited "
                              f"{count}x in a row -- cooling down for {self.cooldown_seconds:.0f}s.")
                else:
                    self._consecutive_failures[id(provider)] = 0
                continue
        raise RuntimeError(f"All providers failed in BalancingLLM. Last error: {last_error}")

    async def generate(self, messages: list[dict], tools: list[dict] = None) -> str:
        return await self._call_with_balancing("generate", messages, tools)

    async def generate_result(self, messages: list[dict], tools: list[dict] = None) -> ModelResult:
        return await self._call_with_balancing("generate_result", messages, tools)
