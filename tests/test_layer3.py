"""
Test Layer 3: DialecticalEngine — complete dialectical cycle.
"""
import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.core import AgentInput, MockLLM, DevelopmentLogger
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.memory import KnowledgeGraphMemory
from dialectic_ai.reality import PythonExecutor
from dialectic_ai.engine import DialecticalEngine

@pytest.mark.asyncio
async def test_dialectical_engine_cycle():
    mock_response_1 = """{
      "decision": "The student sent the code.",
      "knowledge_updates": [],
      "tool_calls": [{"name": "execute_python_code", "args": {"code": "for i in range(3):\\nprint(i)"}}],
      "response": ""
    }"""

    mock_response_2 = """{
      "decision": "The code crashed with IndentationError. Updating the graph.",
      "knowledge_updates": [{"concept": "python_indentation", "status": "struggling"}],
      "tool_calls": [],
      "response": "Indentation error (IndentationError)."
    }"""

    memory = KnowledgeGraphMemory()
    llm = MockLLM(responses=[mock_response_1, mock_response_2])
    executor = PythonExecutor(timeout=5)

    agent = DialecticalAgent(
        goal="You are a Python tutor.",
        llm=llm,
        memory=memory,
        tools=[executor],
    )

    logger = DevelopmentLogger(log_path="engine_test_log.md", trace_path="engine_test_trace.jsonl")
    engine = DialecticalEngine(agent, logger=logger, max_iterations=5)

    user_input = AgentInput(
        user_message="Here is my code: for i in range(3):\nprint(i)",
        session_id="test-student-01"
    )

    output = await engine.run(user_input)

    assert output.is_final
    assert len(output.evidence) == 1
    cr = output.evidence[0]
    assert cr.tool_name == "execute_python_code"
    assert not cr.success
    assert "IndentationError" in cr.error
    assert len(output.memory_updates) == 1
    assert memory.get_graph().get("python_indentation") == "struggling"

    # Cleanup
    if os.path.exists("engine_test_log.md"):
        os.remove("engine_test_log.md")
    if os.path.exists("engine_test_trace.jsonl"):
        os.remove("engine_test_trace.jsonl")