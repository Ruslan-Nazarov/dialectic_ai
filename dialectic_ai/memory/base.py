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
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from dialectic_ai.core.dialectical import DialecticalObject
from dialectic_ai.core.schema import AgentInput, MemoryUpdate


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


# NOTE: despite the Memory Protocol above existing as the intended lighter-weight
# contract, every concrete memory implementation in this codebase (KnowledgeGraphMemory,
# PersistentMemory, SQLiteKnowledgeGraphMemory) still inherits from this class, not from
# Memory directly -- ConversationMemory is the only one on the newer path. Calling this
# "deprecated" would be false advertising until that migration actually happens (see
# REFACTOR_PLAN.md Phase 5.3 for the scoped, deliberately-deferred migration decision).
class BaseMemory(ABC, DialecticalObject, Memory):
    """
    ABC-based memory contract (nominal typing, requires inheriting DialecticalObject
    and the @dialectical decorator). Memory (Protocol) above is the newer, lighter-
    weight structural-typing alternative -- ConversationMemory uses it directly; every
    other concrete memory class in this codebase still inherits from this one.
    """
    def update(self, updates: list[MemoryUpdate]) -> None:
        pass
    
    @abstractmethod
    def process_turn(self, user_input: AgentInput, parsed_response: dict) -> None:
        ...