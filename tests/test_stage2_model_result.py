import pytest
import sys
from dialectic_ai.core.schema import ModelResult, ModelToolCall, AgentInput
from dialectic_ai.core.llm import BaseLLM, MockLLM, OpenAILLM
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.engine.executor import DialecticalEngine

def test_core_llm_does_not_import_parser():
    # Verify that dialectic_ai.core.llm does not import dialectic_ai.engine.parser
    with open("dialectic_ai/core/llm.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "parser" not in content
    assert "parse_llm_response" not in content


@pytest.mark.asyncio
async def test_generate_str_api_remains_compatible():
    llm = MockLLM(responses=['{"response": "hello"}'])
    res = await llm.generate([], tools=[])
    assert isinstance(res, str)
    assert 'hello' in res


@pytest.mark.asyncio
async def test_mock_llm_uses_text_fallback():
    llm = MockLLM(responses=['{"response": "fallback"}'])
    res = await llm.generate_result([], tools=[])
    assert isinstance(res, ModelResult)
    assert res.text == '{"response": "fallback"}'
    assert len(res.tool_calls) == 0


@pytest.mark.asyncio
async def test_engine_bypasses_parser_for_native_tool_call():
    @dialectical(origin="t", contradiction="t", resolves="t", generates="t", own_contradictions="t", layer=1)
    class NativeToolLLM(BaseLLM):
        supports_native_tool_calling = True
        async def generate(self, messages, tools=None):
            return ""
            
        async def generate_result(self, messages, tools=None):
            # Returns a raw native tool call without valid JSON text
            return ModelResult(
                text="Not a json",
                tool_calls=[ModelToolCall(name="test_tool", arguments={"a": 1})]
            )

    agent = DialecticalAgent(goal="test", llm=NativeToolLLM(), tools=[])
    # Add a dummy tool to the registry so it doesn't fail immediately on execution
    class DummyTool:
        name = "test_tool"
        description = "dummy"
        def parameters(self): return {}
        def to_prompt_description(self): return "dummy"
        async def execute(self, args):
            from dialectic_ai.core.schema import Evidence
            return Evidence(source="test_tool", content="ok")

    agent.tools = [DummyTool()]
    engine = DialecticalEngine(agent=agent, max_iterations=1)
    
    # Run engine. If it doesn't raise a ParseError on "Not a json", it means parser was bypassed.
    output = await engine.run(AgentInput(user_message="test"))
    
    # We should have one tool call in history, not a parse error
    history = agent.get_messages()
    assert any("test_tool" in str(msg) for msg in history)


@pytest.mark.asyncio
async def test_text_result_goes_through_parser():
    @dialectical(origin="t", contradiction="t", resolves="t", generates="t", own_contradictions="t", layer=1)
    class TextOnlyLLM(BaseLLM):
        async def generate(self, messages, tools=None):
            return '{"response": "parsed via fallback"}'
            
        async def generate_result(self, messages, tools=None):
            return ModelResult(text='{"response": "parsed via fallback"}')

    agent = DialecticalAgent(goal="test", llm=TextOnlyLLM(), tools=[])
    engine = DialecticalEngine(agent=agent, max_iterations=1)
    output = await engine.run(AgentInput(user_message="test"))
    
    assert output.response == "parsed via fallback"


@pytest.mark.asyncio
async def test_unknown_native_tool_rejected():
    @dialectical(origin="t", contradiction="t", resolves="t", generates="t", own_contradictions="t", layer=1)
    class HallucinatingNativeLLM(BaseLLM):
        supports_native_tool_calling = True
        async def generate(self, messages, tools=None):
            return ""
        async def generate_result(self, messages, tools=None):
            return ModelResult(tool_calls=[ModelToolCall(name="fake_tool", arguments={})])

    agent = DialecticalAgent(goal="test", llm=HallucinatingNativeLLM(), tools=[])
    engine = DialecticalEngine(agent=agent, max_iterations=2)
    await engine.run(AgentInput(user_message="test"))
    
    msgs = agent.get_messages()
    # The last message should be the user's observation error message since we reached max iterations
    obs_message = msgs[-1]["content"]
    assert "not registered" in obs_message
    assert "fake_tool" in obs_message
    assert "fake_tool" in obs_message


@pytest.mark.asyncio
async def test_native_tool_call_does_not_require_textual_tool_call():
    # If supports_native_tool_calling is True, "tool_calls" should NOT be in the system prompt JSON requirement
    agent = DialecticalAgent(goal="test", llm=OpenAILLM(), tools=[])
    prompt = agent.get_system_prompt()
    # It should still require JSON, but without tool_calls section
    assert "decision" in prompt
    assert '"tool_calls": [' not in prompt
