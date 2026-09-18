"""
dialectic_ai/reality/delegation.py

DIALECTICAL DESCRIPTION:
  Origin: The Agent (Layer 1) can invoke tools (Layer 2). But what if
    the task is too complex and requires a change of context/provider?
  Contradiction: The monolithic agent is overloaded with instructions. The system prompt
    becomes bloated, focus is lost.
  Resolution: The "Agent as Tool" pattern. SubAgentTool allows one agent
    to invoke another agent through a standardized Tool interface.
  Leads to: Multi-Agent. Hierarchies are formed (Supervisor -> Workers).
    Each sub-agent goes through its complete dialectical cycle through its Engine.
  Own contradictions: Increases latency (LLM call chain).
    Difficult to debug distributed state.
"""
import uuid

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import AgentInput, Evidence
from dialectic_ai.core.tool import AgentTool
from dialectic_ai.engine.executor import DialecticalEngine


@dialectical(
    origin="The monolithic system prompt overloads the agent. It forgets instructions",
    contradiction="The agent must be able to do everything while remaining focused",
    resolves="The supervisor agent delegates the subtask to a specialized sub-agent through the Tool interface",
    generates="Multi-agent architecture (hierarchical agents). Distributed dialectics",
    own_contradictions="High latency due to the chain of LLM calls. Difficult debugging of traces",
    layer=4,
)
class SubAgentTool(AgentTool):
    """
    Tool for delegating a task to another agent.
    """

    def __init__(self, name: str, description: str, engine: DialecticalEngine):
        """
        :param name: Name of the tool (e.g., 'ask_reviewer')
        :param description: Description for the supervisor (what this sub-agent can do)
        :param engine: Configured DialecticalEngine of the sub-agent
        """
        self._name = name
        self._description = description
        self.engine = engine

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Detailed description of the task, context, and expected result from the sub-agent."
                }
            },
            "required": ["task"]
        }

    async def execute(self, args: dict) -> Evidence:
        task = args.get("task", "")
        if not task:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error="No task specified for the sub-agent.",
            )

        print(f"\n[Delegation] Passing the task to sub-agent '{self.name}': {task[:80]}...")
        
        try:
            # Launch the sub-agent in its own dialectical cycle
            user_input = AgentInput(user_message=task, session_id=f"subagent_{self.name}")
            output = await self.engine.run(user_input)
            
            # The result of the sub-agent becomes Evidence for the supervisor
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content=output.response,
                tool_name=self.name,
                success=True,
            )
        except Exception as e:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error=f"Error executing the sub-agent: {str(e)}",
            )
