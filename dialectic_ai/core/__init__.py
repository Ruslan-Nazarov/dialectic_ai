"""dialectic_ai/core/__init__.py — public interface of Layer 0."""
from dialectic_ai.core.dialectical import dialectical, print_dialectical_card, get_dialectical_map
from dialectic_ai.core.schema import AgentInput, AgentOutput, MemoryUpdate, Evidence, Claim, Hypothesis
from dialectic_ai.core.llm import BaseLLM, MockLLM
from dialectic_ai.integrations.gemini.llm import GeminiLLM
from dialectic_ai.integrations.openai.llm import OpenAILLM
from dialectic_ai.core.logger import DevelopmentLogger

__all__ = [
    "dialectical", "print_dialectical_card", "get_dialectical_map",
    "AgentInput", "AgentOutput", "MemoryUpdate", "Evidence", "Claim", "Hypothesis",
    "BaseLLM", "MockLLM", "GeminiLLM", "OpenAILLM",
    "DevelopmentLogger",
]