"""
dialectic_ai/agent/base.py

DIALECTICAL DESCRIPTION:
  Origin: The entire Tutor configuration was hardcoded in one file.
    To create a second agent, it was necessary to copy all the code.
  Contradiction: There is no common "language" for describing an agent. Each agent —
    a unique disconnected script. A framework is impossible without a common base class.
  How it resolves: DialecticalAgent is the Generative Principle (Rule 1) in the code.
    The developer only sets the `goal` and optional parameters. Everything else
    (prompt, memory, tool registry) is generated automatically.
  What it leads to: DialecticalEngine receives a unified agent object.
    Tutor, Coder, Analyst — all inherit from this class.
  Own contradictions: The base class tries to anticipate the needs of all
    possible agents. The more universal it is, the more it accumulates
    optional parameters. Strict discipline of extension is needed.
"""
from dialectic_ai.agent.prompt_builder import build_system_prompt
from dialectic_ai.core.dialectical import DialecticalObject, dialectical
from dialectic_ai.core.llm import BaseLLM, MockLLM
from dialectic_ai.memory.base import BaseMemory
from dialectic_ai.memory.knowledge_graph import KnowledgeGraphMemory
from dialectic_ai.memory.sublation import SublationEngine


@dialectical(
    origin="The Tutor was a monolithic script. Creating a second agent required copying all the code",
    contradiction="Without a base class, each agent is an island. A framework is impossible without a common contract",
    resolves="The developer only sets the goal (Generative Principle). The prompt, memory, history "
             "are generated automatically and follow from the goal",
    generates="DialecticalEngine receives a unified object. Tutor, Coder, Analyst — "
              "all inherit from here without code duplication",
    own_contradictions="One base class cannot serve all types of agents equally well. "
                       "The compromise between universality and specialization is inevitable",
    layer=1,
)
class DialecticalAgent(DialecticalObject):
    """
    Base class for any agent in the DialecticAI framework.

    The developer only sets the `goal`. Everything else follows from it:
    the prompt is built automatically, memory is initialized, history is maintained.

    Example of creating an agent:
        agent = DialecticalAgent(
            goal="You teach Python. Help the student understand concepts through questions.",
            llm=GeminiLLM(api_key="..."),
            memory=PersistentMemory(path="student_state.json"),
        )
    """

    def __init__(
        self,
        goal: str,
        llm: BaseLLM = None,
        memory: BaseMemory = None,
        tools: list = None,
        tool_calling_mode: str = "dialectic_json",
    ):
        self.goal = goal
        self.llm = llm or MockLLM()
        self.memory = memory or KnowledgeGraphMemory()
        self.tools: list = tools if tools is not None else []
        self.tool_calling_mode = tool_calling_mode
        self._history: list[dict] = []  # History of messages for LLM
        self.max_history_length = 10
        self.sublation_engine = SublationEngine(llm=self.llm)

    def get_system_prompt(self) -> str:
        """Assembles the current system prompt (goal + rules + memory + tools)."""
        return build_system_prompt(
            self.goal, 
            self.memory, 
            tools=self.tools,
            tool_calling_mode=self.tool_calling_mode,
        )

    async def add_to_history(self, role: str, content: str) -> None:
        """Adds a message to the dialogue history and performs sublation on overflow."""
        self._history.append({"role": role, "content": content})
        
        if len(self._history) > self.max_history_length:
            print(f"[Agent] Context overflowed ({len(self._history)} messages). Starting SublationEngine...")
            # Keep the most recent exchanges verbatim (they contain the specific
            # tool calls/errors the agent needs to avoid repeating) and only
            # summarize the older tail. Replacing everything with a vague
            # 1-2 paragraph synthesis was erasing "this exact call already
            # failed" context, causing the agent to retry the same dead end.
            keep_tail = 4
            to_summarize, recent = self._history[:-keep_tail], self._history[-keep_tail:]
            synthesis = await self.sublation_engine.sublate(to_summarize)
            self._history = [
                {"role": "user", "content": f"[SYSTEM INTERNAL] Synthesis of past conversations:\n{synthesis}"}
            ] + recent
            print("[Agent] History successfully compressed (Aufheben).")

    def get_messages(self) -> list[dict]:
        """Returns the complete list of messages: system prompt + history."""
        system = {"role": "system", "content": self.get_system_prompt()}
        return [system] + self._history

    def clear_history(self) -> None:
        """Clears the dialogue history (start a new session)."""
        self._history.clear()
        self.memory.clear()
