"""
Unit tests for Stage 8B: Explicit Tool-Calling Protocols in DialecticAI.
Tests:
- Test A: dialectic_json request contract (tools=None to LLM, prompt contains textual "tool_calls")
- Test B: native request contract (tools=[...] to LLM, prompt does not require textual "tool_calls")
- Test C: textual execution (AgentOutput JSON with tool_calls -> actual tool executed -> Evidence created -> Observation in dialogue)
- Test D: claimed execution without call (text claims execution but tool_calls=[] -> NO Evidence created)
- Test E: mutual exclusion regression test (modes never simultaneously send native tools and textual contract)
"""
import json
import pytest
from typing import Any, Optional

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.schema import AgentInput, AgentOutput, Evidence, ModelResult, ModelToolCall
from dialectic_ai.core.tool import ObservationTool
from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.agent.prompt_builder import build_system_prompt
from dialectic_ai.engine.executor import DialecticalEngine
from dialectic_ai.memory.knowledge_graph import KnowledgeGraphMemory


@dialectical(origin="t", contradiction="t", resolves="t", generates="t", own_contradictions="t", layer=2)
class DummyMathTool(ObservationTool):
    def __init__(self):
        self.call_count = 0
        self.last_args = None

    @property
    def name(self) -> str:
        return "add_numbers"

    @property
    def description(self) -> str:
        return "Add two numbers: a and b."

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        }

    async def execute(self, args: dict) -> Evidence:
        self.call_count += 1
        self.last_args = args
        a = args.get("a", 0)
        b = args.get("b", 0)
        res = {"sum": a + b}
        return Evidence(
            id="ev-dummy-math-001",
            source=self.name,
            content=json.dumps(res),
            tool_name=self.name,
            success=True,
            tool_calls_args=args,
        )


@dialectical(origin="t", contradiction="t", resolves="t", generates="t", own_contradictions="t", layer=1)
class InterceptingLLM(BaseLLM):
    """Intercepts the arguments passed to generate_result and returns canned responses."""
    supports_native_tool_calling = True

    def __init__(self, canned_result: Optional[ModelResult] = None):
        self.last_messages = None
        self.last_tools = None
        self.calls_count = 0
        self.canned_result = canned_result or ModelResult(
            text=json.dumps({
                "decision": "Resolved",
                "hypothesis": {"assumption": "a", "plan_steps": []},
                "knowledge_updates": [],
                "claims": [],
                "response": "Final answer",
                "tool_calls": [],
                "opposite_process": "none",
                "contradiction": "none",
                "leap": "none",
                "leap_type": "fully_resolved",
            })
        )

    async def generate(self, messages: list[dict], tools: list[dict] = None) -> str:
        self.last_messages = messages
        self.last_tools = tools
        self.calls_count += 1
        return self.canned_result.text

    async def generate_result(self, messages: list[dict], tools: list[dict] = None) -> ModelResult:
        self.last_messages = messages
        self.last_tools = tools
        self.calls_count += 1
        return self.canned_result


# --- Test A: dialectic_json request contract ---

@pytest.mark.asyncio
async def test_a_dialectic_json_request_contract():
    tool = DummyMathTool()
    llm = InterceptingLLM()
    agent = DialecticalAgent(
        goal="Calculate sum",
        llm=llm,
        tools=[tool],
        tool_calling_mode="dialectic_json",
    )
    engine = DialecticalEngine(agent=agent, max_iterations=1)

    prompt = agent.get_system_prompt()
    assert '"tool_calls": [' in prompt, "System prompt in dialectic_json mode must include textual tool_calls contract"
    assert "add_numbers" in prompt, "System prompt in dialectic_json mode must describe available tools"

    await engine.run(AgentInput(user_message="Add 2 and 3"))

    assert llm.last_tools is None, "In dialectic_json mode, tools payload passed to LLM must be None"


# --- Test B: native request contract ---

@pytest.mark.asyncio
async def test_b_native_request_contract():
    tool = DummyMathTool()
    llm = InterceptingLLM()
    agent = DialecticalAgent(
        goal="Calculate sum natively",
        llm=llm,
        tools=[tool],
        tool_calling_mode="native",
    )
    engine = DialecticalEngine(agent=agent, max_iterations=1)

    prompt = agent.get_system_prompt()
    assert '"tool_calls": [' not in prompt, "System prompt in native mode must NOT require textual tool_calls"
    assert "## Available tools" not in prompt, "System prompt in native mode must NOT duplicate text tool schemas"

    await engine.run(AgentInput(user_message="Add 2 and 3"))

    assert llm.last_tools is not None, "In native mode, tools payload passed to LLM must be populated"
    assert len(llm.last_tools) == 1
    assert llm.last_tools[0]["function"]["name"] == "add_numbers"


# --- Test C: textual execution ---

@pytest.mark.asyncio
async def test_c_textual_execution():
    tool = DummyMathTool()
    
    # Turn 1: model requests tool execution via textual tool_calls
    turn1_json = json.dumps({
        "decision": "Need to add numbers",
        "hypothesis": {"assumption": "Sum is 5", "plan_steps": ["Call add_numbers"]},
        "knowledge_updates": [],
        "claims": [],
        "response": "",
        "tool_calls": [
            {"name": "add_numbers", "args": {"a": 2, "b": 3}}
        ],
        "opposite_process": "",
        "contradiction": "",
        "leap": "",
        "leap_type": "decompose_and_act",
    })

    # Turn 2: model sees Observation and provides final response
    turn2_json = json.dumps({
        "decision": "Sum verified",
        "hypothesis": {"assumption": "Sum is 5", "plan_steps": []},
        "knowledge_updates": [],
        "claims": [{"text": "The sum is 5", "evidence_ids": ["ev-dummy-math-001"], "requires_validation": False}],
        "response": "The calculated sum is 5.",
        "tool_calls": [],
        "opposite_process": "guess without adding",
        "contradiction": "guessed vs computed",
        "leap": "ground in tool computation",
        "leap_type": "fully_resolved",
    })

    @dialectical(origin="t", contradiction="t", resolves="t", generates="t", own_contradictions="t", layer=1)
    class MultiTurnTextualLLM(BaseLLM):
        def __init__(self):
            self.turn = 0
        async def generate(self, messages, tools=None):
            self.turn += 1
            return turn1_json if self.turn == 1 else turn2_json
        async def generate_result(self, messages, tools=None):
            text = await self.generate(messages, tools)
            return ModelResult(text=text)

    llm = MultiTurnTextualLLM()
    agent = DialecticalAgent(
        goal="Calculate sum",
        llm=llm,
        tools=[tool],
        tool_calling_mode="dialectic_json",
    )
    engine = DialecticalEngine(agent=agent, max_iterations=3)

    output: AgentOutput = await engine.run(AgentInput(user_message="Please compute 2 + 3"))

    # Actual tool execution = YES
    assert tool.call_count == 1, "Tool must have been executed exactly once"
    assert tool.last_args == {"a": 2, "b": 3}

    # Evidence created = YES
    assert len(output.evidence) == 1
    assert output.evidence[0].id == "ev-dummy-math-001"
    assert output.evidence[0].tool_name == "add_numbers"
    assert json.loads(output.evidence[0].content)["sum"] == 5

    # Observation returned in dialogue = YES
    history = agent.get_messages()
    observation_messages = [m for m in history if m["role"] == "user" and "[Observation]" in m["content"]]
    assert len(observation_messages) >= 1
    assert "add_numbers" in observation_messages[0]["content"]
    assert "sum" in observation_messages[0]["content"]


# --- Test D: claimed execution without call ---

@pytest.mark.asyncio
async def test_d_claimed_execution_without_call():
    tool = DummyMathTool()

    # Model claims in text that it calculated Dataset A, but tool_calls is empty!
    claimed_without_call_json = json.dumps({
        "decision": "I calculated the numbers",
        "hypothesis": {"assumption": "Values are known", "plan_steps": []},
        "knowledge_updates": [],
        "claims": [{"text": "I calculated Dataset A and verified sum is 5", "evidence_ids": [], "requires_validation": False}],
        "response": "I have executed add_numbers and verified the sum is 5 without a tool call.",
        "tool_calls": [],  # Empty tool calls!
        "opposite_process": "not doing it",
        "contradiction": "none",
        "leap": "none",
        "leap_type": "fully_resolved",
    })

    llm = InterceptingLLM(canned_result=ModelResult(text=claimed_without_call_json))
    agent = DialecticalAgent(
        goal="Calculate sum",
        llm=llm,
        tools=[tool],
        tool_calling_mode="dialectic_json",
    )
    engine = DialecticalEngine(agent=agent, max_iterations=2)

    output: AgentOutput = await engine.run(AgentInput(user_message="Add 2 and 3"))

    # Crucial assertion: NO tool execution, NO evidence created!
    assert tool.call_count == 0, "Tool must NOT be executed when tool_calls is empty"
    assert len(output.evidence) == 0, "NO Evidence may be created solely because model claimed it in text"


# --- Test E: modes are mutually exclusive regression test ---

def test_e_modes_are_mutually_exclusive():
    tool = DummyMathTool()
    mem = KnowledgeGraphMemory()

    # Mode 1: dialectic_json
    prompt_json = build_system_prompt("goal", mem, tools=[tool], tool_calling_mode="dialectic_json")
    assert '"tool_calls": [' in prompt_json
    assert "## Available tools" in prompt_json

    # Mode 2: native
    prompt_native = build_system_prompt("goal", mem, tools=[tool], tool_calling_mode="native")
    assert '"tool_calls": [' not in prompt_native
    assert "## Available tools" not in prompt_native

    # Engine level mutual exclusion check
    agent_json = DialecticalAgent(goal="g", tools=[tool], tool_calling_mode="dialectic_json")
    engine_json = DialecticalEngine(agent=agent_json)
    assert engine_json.tool_calling_mode == "dialectic_json"

    agent_native = DialecticalAgent(goal="g", tools=[tool], tool_calling_mode="native")
    engine_native = DialecticalEngine(agent=agent_native)
    assert engine_native.tool_calling_mode == "native"
