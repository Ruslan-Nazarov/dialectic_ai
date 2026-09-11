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
from abc import ABC, abstractmethod
from dialectic_ai.core.dialectical import dialectical, DialecticalObject


import asyncio

class BaseLLM(ABC, DialecticalObject):
    """Abstraction over any language model."""

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
