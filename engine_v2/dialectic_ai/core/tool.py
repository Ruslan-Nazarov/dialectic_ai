"""
dialectic_ai/core/tool.py

DIALECTICAL DESCRIPTION:
  Origin: Previously, all tools were called "RealityCheck" (Layer 2).
    But the script call or page download itself is not a hypothesis check, 
    it is just obtaining raw data.
  Contradiction: Mixing "action" and "reality matching" in one
    abstraction hindered the construction of the formal Validation phase.
  How it resolves: Introduces the Tool abstraction. It is simply a sensor (ObservationTool) or 
    actuator (ActionTool). It does not evaluate reality, it just provides data.
  What it leads to: Allows for the implementation of a true RealityCheck in future stages — 
    as a process of reconciling Claim and Evidence obtained from the Tool.
  Own contradictions: Currently returns raw CollisionResult. In the next
    stage, the Tool should return Evidence.
"""
import json
from abc import ABC, abstractmethod

from dialectic_ai.core.dialectical import DialecticalObject
from dialectic_ai.core.schema import Evidence


class Tool(ABC, DialecticalObject):
    """
    Base class for a tool interacting with the external environment.
    The tool provides data (Observation) or performs an action (Action).
    This is not a reality check (RealityCheck), but a source of data for it.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the tool."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the tool for the agent."""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """Category (Observation, Action, Agent)."""
        ...

    @abstractmethod
    async def execute(self, args: dict) -> Evidence:
        """
        Executes the tool. Returns Evidence (fact from reality).
        """
        ...

    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema of arguments."""
        ...

    def to_prompt_description(self) -> str:
        """Returns a string for embedding in the system prompt."""
        schema_str = json.dumps(self.parameters(), ensure_ascii=False)
        return f"- `{self.name}`: {self.description}\n  Arguments: {schema_str}"


class ObservationTool(Tool):
    """Tool that only reads data from the external world (e.g., search)."""
    @property
    def category(self) -> str:
        return "Observation"


class ActionTool(Tool):
    """Tool that changes the state of the external world (e.g., executing code)."""
    @property
    def category(self) -> str:
        return "Action"


class AgentTool(Tool):
    """Tool for delegating a task to another agent."""
    @property
    def category(self) -> str:
        return "Agent"

