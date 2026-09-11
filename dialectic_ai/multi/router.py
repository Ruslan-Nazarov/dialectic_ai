"""
dialectic_ai/multi/router.py

DIALECTICAL DESCRIPTION:
  Origin: One agent cannot be an expert in everything. Real
    tasks require specialization: one agent checks code, another explains theory.
  Contradiction: The user should not know which agent they need. The choice of agent cannot
    be left to the user — it destroys the UX.
  Resolution: AgentRouter analyzes the content of the request and automatically
    directs it to the appropriate agent from the registry. There is one entry point for the user.
  Outcome: AgentTeam uses Router as its core dispatcher.
    Multi-agent systems (CrewAI-style) are built on top of this.
  Own contradictions: Simple keyword routing is too primitive for
    real tasks. Smart routing requires its own LLM call — adds
    latency and cost to each request.
"""
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.multi.protocol import AgentMessage, AgentResult


@dialectical(
    origin="One agent is overloaded with all tasks. Specialization and delegation are needed",
    contradiction="Who decides which agent processes the request? Without a dispatcher — chaos or manual selection",
    resolves="A single entry point. Router analyzes the request and directs it to the appropriate agent "
             "by keywords (fast) or through LLM (smart)",
    generates="AgentTeam: teams from Router + several specialized agents. "
              "The basis for hierarchical multi-agent systems",
    own_contradictions="Keyword routing is fragile. LLM routing adds latency. "
                       "The boundary of responsibility between agents is often blurred",
    layer=4,
)
class AgentRouter:
    """
    Dispatcher of requests between team agents.

    Supports two modes:
    - Keyword-routing: fast, without LLM call
    - Manual: the developer sets the routing rule as a function
    """

    def __init__(self, default_agent: str = None):
        self._agents: dict = {}           # name -> DialecticalAgent
        self._engines: dict = {}          # name -> DialecticalEngine
        self._routing_rules: list = []    # [(condition_fn, agent_name)]
        self.default_agent = default_agent

    def register(self, name: str, agent, engine) -> "AgentRouter":
        """Registers an agent with its engine under the name name."""
        self._agents[name] = agent
        self._engines[name] = engine
        print(f"[Router] Registered agent: '{name}'")
        return self

    def add_rule(self, condition_fn, agent_name: str) -> "AgentRouter":
        """
        Adds a routing rule.

        Args:
            condition_fn: Function (message: str) -> bool
            agent_name: Name of the agent to which the request goes when True
        """
        self._routing_rules.append((condition_fn, agent_name))
        return self

    async def route(self, message: AgentMessage) -> AgentResult:
        """
        Determines the appropriate agent and delegates execution to them.

        Order of selection:
        1. Goes through the routing rules (first match)
        2. If there are no rules or none matched — selects the first registered agent
        """
        target_name = self._find_agent(message.content)

        if target_name not in self._engines:
            return AgentResult(
                agent_name="router",
                response=f"[Router] Agent '{target_name}' not found in the registry.",
                success=False,
                error=f"Unknown agent: {target_name}",
            )

        print(f"[Router] Request directed → '{target_name}'")
        engine = self._engines[target_name]
        agent_input = AgentInput(
            user_message=message.content,
            session_id=message.session_id,
        )
        output = await engine.run(agent_input)
        return AgentResult(
            agent_name=target_name,
            response=output.response,
            success=output.is_final,
        )

    def _find_agent(self, content: str) -> str:
        """Finds the appropriate agent based on routing rules."""
        for condition_fn, agent_name in self._routing_rules:
            if condition_fn(content):
                return agent_name
        # Fallback: first registered agent
        if self.default_agent:
            return self.default_agent
        if self._engines:
            return list(self._engines.keys())[0]
        return ""
