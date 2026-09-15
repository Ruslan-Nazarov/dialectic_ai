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
      "response": "Indentation error (IndentationError).",
      "opposite_process": "Telling the student the code looks fine without ever running it.",
      "contradiction": "Trusting the student's code by inspection alone vs. actually executing it to see the real error.",
      "leap": "Ran the code, found the real IndentationError, and reported it instead of guessing."
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

    # Rule 5: a finalized response must carry opposite_process/contradiction/leap.
    assert not output.dialectical_resolution_missing
    assert output.opposite_process
    assert output.contradiction
    assert output.leap

    # Cleanup
    if os.path.exists("engine_test_log.md"):
        os.remove("engine_test_log.md")
    if os.path.exists("engine_test_trace.jsonl"):
        os.remove("engine_test_trace.jsonl")


@pytest.mark.asyncio
async def test_dialectical_engine_flags_missing_resolution():
    """A finalized response without opposite_process/contradiction/leap must be flagged,
    not silently accepted as fully compliant (Rule 5, engine-level enforcement)."""
    mock_response = '{"decision": "Just answering.", "tool_calls": [], "response": "42"}'

    agent = DialecticalAgent(
        goal="You answer questions.",
        llm=MockLLM(responses=[mock_response]),
        tools=[],
    )
    engine = DialecticalEngine(agent, max_iterations=3)

    output = await engine.run(AgentInput(user_message="What is the answer?"))

    assert output.status == "completed"  # still completes -- enforcement is visible, not blocking
    assert output.dialectical_resolution_missing


@pytest.mark.asyncio
async def test_dialectical_engine_drives_leap_action_mismatch_back_into_development():
    """A second-order contradiction (leap_type='decompose_and_act' claimed, but nothing was ever
    done) must be fed back into the SAME generative loop, not silently finalized -- this is the
    'drive the contradiction to resolution, don't just record it' mechanism from 2026-09-13."""
    claimed_but_didnt_act = """{
      "decision": "Handling the request.",
      "tool_calls": [],
      "response": "I have taken care of the unambiguous part and will follow up on the rest.",
      "opposite_process": "Asking the user before doing anything.",
      "contradiction": "Acting now vs. asking first.",
      "leap": "Decomposition: act on the clear part now.",
      "leap_type": "decompose_and_act"
    }"""
    actually_acts = """{
      "decision": "Actually running the unambiguous part now.",
      "tool_calls": [{"name": "execute_python_code", "args": {"code": "print('done')"}}],
      "response": ""
    }"""
    final_answer = """{
      "decision": "Reporting completion.",
      "tool_calls": [],
      "response": "Done.",
      "opposite_process": "Leaving the task unacknowledged.",
      "contradiction": "Reporting completion vs. staying silent.",
      "leap": "Confirmed the action ran and reported it.",
      "leap_type": "fully_resolved"
    }"""

    llm = MockLLM(responses=[claimed_but_didnt_act, actually_acts, final_answer])
    agent = DialecticalAgent(
        goal="You handle requests.",
        llm=llm,
        tools=[PythonExecutor(timeout=5)],
    )
    engine = DialecticalEngine(agent, max_iterations=6)

    output = await engine.run(AgentInput(user_message="Do the thing."))

    # The contradiction was caught and driven back -- it never reached a leap_action_mismatch finalization.
    assert not output.leap_action_mismatch
    assert output.status == "completed"
    assert output.response == "Done."
    # The tool was actually called this time (evidence of the corrected, real decomposition).
    assert len(output.evidence) == 1
    # The corrective message must be visible in the agent's own history (not silently swallowed).
    history_text = " ".join(m["content"] for m in agent._history)
    assert "Contradiction: you declared leap_type='decompose_and_act'" in history_text