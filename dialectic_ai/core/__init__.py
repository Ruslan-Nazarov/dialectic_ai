"""dialectic_ai/core/__init__.py — public interface of Layer 0."""
from dialectic_ai.core.dialectical import dialectical, get_dialectical_map, print_dialectical_card
from dialectic_ai.core.llm import BaseLLM, MockLLM
from dialectic_ai.core.logger import DevelopmentLogger
from dialectic_ai.core.schema import AgentInput, AgentOutput, Claim, Evidence, Hypothesis, MemoryUpdate

__all__ = [
    "dialectical", "print_dialectical_card", "get_dialectical_map",
    "AgentInput", "AgentOutput", "MemoryUpdate", "Evidence", "Claim", "Hypothesis",
    "BaseLLM", "MockLLM", "GeminiLLM", "OpenAILLM",
    "DevelopmentLogger",
]


def __getattr__(name):
    if name == "GeminiLLM":
        from dialectic_ai.integrations.gemini.llm import GeminiLLM
        return GeminiLLM
    if name == "OpenAILLM":
        from dialectic_ai.integrations.openai.llm import OpenAILLM
        return OpenAILLM
    raise AttributeError(name)
