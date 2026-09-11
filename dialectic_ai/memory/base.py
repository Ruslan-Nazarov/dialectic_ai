"""
dialectic_ai/memory/base.py

DIALECTICAL DESCRIPTION:
  Origin: The agent conducted one dialogue — upon the next launch, it remembers nothing.
    Each conversation starts from scratch.
  Contradiction: An agent without memory does not learn and does not accumulate knowledge about
    the user. This contradicts the very idea of a "smart" agent.
  How it resolves: Defines the BaseMemory contract — the minimal interface that
    any memory must implement: save observation, get context.
  What it leads to: KnowledgeGraphMemory, BufferMemory, PersistentMemory — all of them
    implement this contract. PromptBuilder gets context through it.
  Own contradictions: One interface for all types of memory inevitably
    turns out to be either too simple (lacking methods) or too complex
    (not all implementations are needed by all agents).
"""
from typing import Protocol, Any, runtime_checkable
from abc import ABC, abstractmethod
from dialectic_ai.core.schema import AgentInput, MemoryUpdate
from dialectic_ai.core.dialectical import DialecticalObject

@runtime_checkable
class Memory(Protocol):
    """Universal contract for any implementation of agent memory."""

    def process_turn(self, user_input: AgentInput, parsed_response: dict) -> None:
        """Accept new knowledge after the agent's turn is completed."""
        ...

    def get_context(self) -> str:
        """Return the current state of memory as a string for embedding in the prompt."""
        ...

    def clear(self) -> None:
        """Clear memory (start a new session)."""
        ...


# For backward compatibility (DEPRECATED)
class BaseMemory(ABC, DialecticalObject, Memory):
    """
    DEPRECATED: Use Memory(Protocol).
    Left for backward compatibility.
    """
    def update(self, updates: list[MemoryUpdate]) -> None:
        pass
    
    @abstractmethod
    def process_turn(self, user_input: AgentInput, parsed_response: dict) -> None:
        updates = [
            MemoryUpdate(
                concept=u.get("concept", ""),
                status=u.get("status", "unknown"),
                details=u.get("details", "")
            )
            for u in parsed_response.get("knowledge_updates", [])
            if u.get("concept")
        ]
        self.update(updates)