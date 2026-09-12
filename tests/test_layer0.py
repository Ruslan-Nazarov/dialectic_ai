"""Test Layer 0: checking that the decorator, logger, LLM, and schema work."""
import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.core import (
    dialectical, print_dialectical_card, get_dialectical_map,
    AgentInput, AgentOutput, Evidence, Claim,
    MockLLM, DevelopmentLogger
)

@pytest.mark.asyncio
async def test_dialectical_decorator():
    @dialectical(
        origin="Need a test class to check the decorator",
        contradiction="Without a test, we don't know if the decorator works",
        resolves="Creating a class and checking for __dialectical__",
        generates="Confidence that Layer 0 works",
        own_contradictions="This is a stub, not a real framework component",
        layer=0,
    )
    class TestComponent:
        pass

    assert hasattr(TestComponent, "__dialectical__")
    assert TestComponent.__dialectical__.layer == 0

@pytest.mark.asyncio
async def test_schema():
    inp = AgentInput(user_message="Hello!", session_id="test-01")
    cr = Evidence(id="123", source="test", content="", tool_name="python_executor", success=False, error="SyntaxError: line 1")
    claim = Claim(text="The code crashed with an error.", evidence_ids=["123"])
    assert inp.user_message == "Hello!"
    assert cr.tool_name == "python_executor"
    assert "123" in claim.evidence_ids

@pytest.mark.asyncio
async def test_mock_llm():
    llm = MockLLM(responses=[
        '{"decision": "Analyzing...", "tool_calls": [], "response": "Response 1"}',
        '{"decision": "Clarifying...", "tool_calls": [], "response": "Response 2"}',
    ])
    r1 = await llm.generate([{"role": "user", "content": "test"}])
    r2 = await llm.generate([{"role": "user", "content": "test2"}])
    assert "Response 1" in r1
    assert "Response 2" in r2

@pytest.mark.asyncio
async def test_development_logger():
    logger = DevelopmentLogger(log_path="test_log.md", trace_path="test_trace.jsonl")
    await logger.log_step("Test Layer 0", "All Core components passed the check", layer=0)
    await logger.log_collision("python_executor", success=False, output="SyntaxError")
    
    assert os.path.exists("test_log.md")
    assert os.path.exists("test_trace.jsonl")
    
    # Clean up
    if os.path.exists("test_log.md"):
        os.remove("test_log.md")
    if os.path.exists("test_trace.jsonl"):
        os.remove("test_trace.jsonl")