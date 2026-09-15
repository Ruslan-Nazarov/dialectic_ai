"""
dialectic_ai/multi/protocol.py

DIALECTICAL DESCRIPTION:
  Origin: When there are multiple agents, they need to pass tasks to each other. But each agent "speaks" in its own format.
  Contradiction: Without a common protocol, agents are incompatible. The Router does not know how to pass a task from AgentA to AgentB and get a response back.
  How it resolves: Defines a standard format for inter-agent messages — AgentMessage. Any agent in the team sends and receives exactly this.
  What it leads to: AgentRouter and AgentTeam are built on top of this protocol. In the future — the basis for distributed agent systems.
  Own contradictions: A common protocol is a compromise. Agents with very different formats are forced to adapt, losing specificity.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentMessage:
    """Standard message for transmission between agents in the team."""
    content: str                        # Content of the task or result
    sender: str = "user"               # Name of the sending agent
    recipient: str = "any"             # Name of the receiving agent ("any" = Router decides)
    session_id: str = "default"
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result of the task execution by the agent."""
    agent_name: str
    response: str
    success: bool = True
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class DialecticalResolution:
    """
    Trace-only record of one Rule 5 pass through DialecticalDebateEngine.

    The single-agent DialecticalEngine loop now carries opposite_process/contradiction/leap
    natively on every AgentOutput (see core/schema.py) -- this record is just a convenience
    snapshot of those same structural fields for the debate's Synthesis step, no longer built
    by regex-extracting a special prefix convention from free text.
    """
    simplest_process: str
    opposite_process: str
    contradiction: str
    leap: str
    resolution: str
