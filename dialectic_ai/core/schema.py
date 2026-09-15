"""
dialectic_ai/core/schema.py

DIALECTICAL DESCRIPTION:
  Origin: Previously, schemas were implemented using dataclasses, which allowed
    arbitrary JSON data from LLM (especially in tool_calls) to penetrate.
  Contradiction: LLM can generate invalid tool arguments, which
    leads to failures at the tool execution stage (Layer 2).
  How it solves: Transitioning models to strict Pydantic v2. Type
    validation occurs instantly when parsing the response. Alternatives (marshmallow, attrs,
    pure TypedDict) were rejected due to worse support for auto-generating 
    JSON schemas for LLM.
  What it leads to: LLM clients (Gemini, OpenAI) can now use
    pydantic schemas for Structured Outputs (or return guaranteed valid JSON).
  Own contradictions: Increased dependency on an external package (pydantic),
    stricter rules when creating mocks in tests.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# What the agent's `leap` actually commits it to, checkable structurally (not by keyword-matching
# free text): "" means not provided (backward compatible with pre-Rule-5 responses).
LeapType = Literal["decompose_and_act", "ask_only", "fully_resolved", ""]

class ModelUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ModelToolCall(BaseModel):
    id: Optional[str] = None
    name: str
    arguments: dict


class ModelResult(BaseModel):
    """Unified result directly from the LLM provider, independent of Dialectic framework entities."""
    text: Optional[str] = None
    tool_calls: list[ModelToolCall] = Field(default_factory=list)
    usage: Optional[ModelUsage] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentInput(BaseModel):
    """Incoming message from the user to the agent."""
    user_message: str
    session_id: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Hypothesis(BaseModel):
    """
    The agent's hypothesis on how to solve the task or what fact needs to be verified.
    Defines the agent's intent and plan of action before execution.
    """
    assumption: str
    plan_steps: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    """
    A statement made by the agent.
    Can refer to specific Evidence (confirmations of reality).
    """
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    requires_validation: bool = False


class Evidence(BaseModel):
    """
    A structured fact or observation obtained from the external world (tool).
    Replaces the primitive CollisionResult.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str          # Where it was obtained from (tool name)
    content: Any         # The knowledge/output itself
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None




class MemoryUpdate(BaseModel):
    """The agent's command to update memory after a move."""
    concept: str
    status: str          # "learned" | "struggling" | "unknown"
    details: Optional[str] = None


class ToolCallRequest(BaseModel):
    """Request to call a tool from the agent."""
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel):
    """The final structured response from the agent after a complete engine cycle."""
    status: str = "completed"                  # "completed", "validation_failed", "max_iterations", "error"
    response: str                              # Text for the user
    decision: str = ""                         # Short rationale for the chosen action
    hypothesis: Optional[Hypothesis] = None    # Current hypothesis and plan (the simplest process + its development)
    opposite_process: str = ""                 # A process that does not need the simplest process to resolve the task
    contradiction: str = ""                    # Simplest and opposite process, taken in the unity of their development
    leap: str = ""                             # The resolving move: what replaces or reconciles the contradiction
    leap_type: LeapType = ""                   # Structural commitment the leap makes -- checkable against evidence_store
    dialectical_resolution_missing: bool = False  # True if `response` was given without opposite_process/contradiction/leap
    leap_action_mismatch: bool = False          # True if leap_type='decompose_and_act' was claimed but nothing was ever done
    claims: list[Claim] = Field(default_factory=list)                      # Claims
    memory_updates: list[MemoryUpdate] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)                 # New
    tool_calls_requested: list[ToolCallRequest] = Field(default_factory=list) # Strictly typed
    is_final: bool = True                      # False = agent is still in the cycle
