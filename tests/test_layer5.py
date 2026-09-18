"""
Test Layer 5: Observability.
"""
import sys
from pathlib import Path
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.observability import TraceReader, AgentEvaluator, EvaluationReport

from dialectic_ai.core import AgentInput, MockLLM, DevelopmentLogger
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.memory import KnowledgeGraphMemory
from dialectic_ai.reality import PythonExecutor
from dialectic_ai.engine import DialecticalEngine

import pytest_asyncio

@pytest_asyncio.fixture(scope="module")
async def generate_trace():
    trace_file = "engine_test_trace.jsonl"
    if Path(trace_file).exists():
        Path(trace_file).unlink()

    mock_response_1 = """{
      "decision": "The student sent code.",
      "knowledge_updates": [],
      "tool_calls": [{"name": "execute_python_code", "args": {"code": "for i in range(3):\\nprint(i)"}}],
      "response": ""
    }"""

    mock_response_2 = """{
      "decision": "Error.",
      "knowledge_updates": [{"concept": "python_indentation", "status": "struggling"}],
      "tool_calls": [],
      "response": "Indentation error."
    }"""

    agent = DialecticalAgent(
        goal="You are a Python tutor.",
        llm=MockLLM(responses=[mock_response_1, mock_response_2]),
        memory=KnowledgeGraphMemory(),
        tools=[PythonExecutor(timeout=5)],
    )

    logger = DevelopmentLogger(log_path="engine_test_log.md", trace_path=trace_file)
    engine = DialecticalEngine(agent, logger=logger, max_iterations=5)

    user_input = AgentInput(user_message="test", session_id="test-student-01")
    await engine.run(user_input)
    
    yield trace_file
    
    if Path(trace_file).exists():
        Path(trace_file).unlink()
    if Path("engine_test_log.md").exists():
        Path("engine_test_log.md").unlink()

@pytest.mark.asyncio
async def test_trace_reader(generate_trace):
    reader = TraceReader(generate_trace)
    events = reader.get_all()
    assert len(events) >= 5

    session_events = reader.get_by_session("test-student-01")
    assert len(session_events) >= 1

    summary = reader.get_summary()
    assert summary["collisions"] >= 1
    assert summary["syntheses"] >= 1

@pytest.mark.asyncio
async def test_agent_evaluator(generate_trace):
    reader = TraceReader(generate_trace)
    evaluator = AgentEvaluator(reader)
    report = evaluator.evaluate_session("test-student-01")
    
    assert report.synthesized is True
    assert report.reality_grounding_score > 0.5
