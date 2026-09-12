import pytest
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.agent.prompt_builder import build_system_prompt
from dialectic_ai.memory.base import BaseMemory
from dialectic_ai.engine.executor import DialecticalEngine
from dialectic_ai.agent.base import DialecticalAgent

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.llm import BaseLLM

@dialectical(
    origin="Testing",
    contradiction="Testing",
    resolves="Testing",
    generates="Testing",
    own_contradictions="Testing",
    layer=1
)
class DummyMemory(BaseMemory):
    def get_context(self) -> str:
        return "empty"
    def process_turn(self, i, p):
        pass

def test_no_internal_monologue_in_prompt():
    prompt = build_system_prompt("goal", DummyMemory())
    assert "Internal monologue" not in prompt
    assert "thought" not in prompt
    assert "decision" in prompt

def test_placeholder_tool_name_not_present_in_prompt():
    prompt = build_system_prompt("goal", DummyMemory())
    assert "tool_name" not in prompt
    assert "<string: exact tool name>" in prompt

def test_fake_evidence_placeholder_not_present_in_prompt():
    prompt = build_system_prompt("goal", DummyMemory())
    assert "uuid_from_observation_if_any" not in prompt
    assert "<string: id of evidence>" in prompt

@pytest.mark.asyncio
async def test_task_is_last_user_message():
    @dialectical(origin="t", contradiction="t", resolves="t", generates="t", own_contradictions="t", layer=1)
    class DummyLLM(BaseLLM):
        async def generate(self, messages, tools=None):
            # Assert that the last message is the user message containing the task text
            assert messages[-1]["role"] == "user"
            assert "The real task" in messages[-1]["content"]
            return '{"response": "done", "tool_calls": [], "decision": "ok"}'

    agent = DialecticalAgent(goal="Generic Goal", llm=DummyLLM(), tools=[])
    engine = DialecticalEngine(agent=agent, max_iterations=1)
    
    input_msg = AgentInput(user_message="The real task", session_id="test")
    await engine.run(input_msg)
    
    # Check history
    msgs = agent.get_messages()
    assert msgs[-1]["role"] == "assistant"
    assert msgs[-2]["role"] == "user"
    assert "The real task" in msgs[-2]["content"]

@pytest.mark.asyncio
async def test_unknown_tool_is_rejected():
    @dialectical(origin="t", contradiction="t", resolves="t", generates="t", own_contradictions="t", layer=1)
    class HallucinatingLLM(BaseLLM):
        def __init__(self):
            self.calls = 0
        async def generate(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                return '{"decision": "use fake", "tool_calls": [{"name": "fake_tool", "args": {}}]}'
            return '{"response": "done", "tool_calls": [], "decision": "ok"}'

    agent = DialecticalAgent(goal="Generic Goal", llm=HallucinatingLLM(), tools=[])
    engine = DialecticalEngine(agent=agent, max_iterations=2)
    
    input_msg = AgentInput(user_message="test", session_id="test")
    await engine.run(input_msg)
    
    # We should have observed a collision error
    msgs = agent.get_messages()
    # The message before the final assistant message should contain the observation error
    obs_message = msgs[-2]["content"]
    assert "not registered" in obs_message
    assert "fake_tool" in obs_message
