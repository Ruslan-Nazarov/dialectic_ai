"""
Test Layer 6: Developer Experience.
"""
import sys
from pathlib import Path
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.core import MockLLM
from dialectic_ai.core.dialectical import get_dialectical_map
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.observability import TraceReader, AgentEvaluator
from examples.tutor.run_tutor import create_tutor_engine, MOCK_TUTOR_RESPONSES

@pytest.mark.asyncio
async def test_dialectical_map():
    items = get_dialectical_map()
    assert len(items) >= 6
    layers = {item.layer for item in items}
    assert 0 in layers
    assert 3 in layers
    assert 5 in layers

@pytest.mark.asyncio
async def test_tutor_example():
    test_trace = "test_tutor_trace.jsonl"
    if Path(test_trace).exists():
        Path(test_trace).unlink()

    engine = create_tutor_engine(
        trace_file=test_trace,
        llm=MockLLM(responses=MOCK_TUTOR_RESPONSES)
    )

    inp = AgentInput(
        user_message="Here is my code:\nfor i in range(3):\nprint(i)",
        session_id="test-session-dx"
    )
    output = await engine.run(inp)
    assert output.response

    assert Path(test_trace).exists()
    reader = TraceReader(test_trace)
    events = reader.get_all()
    assert len(events) >= 3

    evaluator = AgentEvaluator(reader)
    report = evaluator.evaluate_session("test-session-dx")
    assert report.synthesized is True
    
    if Path(test_trace).exists():
        Path(test_trace).unlink()