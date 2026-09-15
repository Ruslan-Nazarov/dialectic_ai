"""
tests/test_canary_real_provider.py

DIALECTICAL DESCRIPTION:
  Origin: The rest of this suite is 100% MockLLM/mocked-HTTP -- every high-value bug
    found during this project's GAIA2 work (the date-year bug, the list/int type-
    classification bug, the placeholder-detection gap, the JsonRepairer schema-
    blindness bug) was found by a human manually running against a real provider on
    real data, not by pytest. A green suite here has never implied "this works
    against a real provider."
  Contradiction: A test that always hits a real API costs quota/money on every CI
    run and every local `pytest` invocation -- unacceptable as an unconditional test.
    A test suite with zero real-provider coverage at all is the status quo this
    exists to change.
  How it resolves: One cheap, deterministic-as-possible test, skipped by default,
    opted into via DIALECTIC_RUN_CANARY=1 -- runs locally on demand and on a daily
    CI schedule (see .github/workflows/python-app.yml's `canary` job), never on
    every push/PR.
  What it leads to: Early warning if a provider changes behavior (a new GigaChat API
    quirk, say) within about a day, instead of only during the next manual benchmark
    run -- without making every commit dependent on a live external API.
  Own contradictions: One trivial scenario against one provider is a smoke test, not
    a substitute for the kind of scenario-level GAIA2 regression this project's real
    bugs were found in -- see test_gaia2_type_classification.py for a targeted
    regression test of the specific highest-impact bug found this session.
"""
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mock_tools import MockCalculatorTool, MockNoteSaverTool, MockWeatherTool

from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.engine.executor import DialecticalEngine


pytestmark = pytest.mark.skipif(
    os.getenv("DIALECTIC_RUN_CANARY") != "1",
    reason="Real-provider canary is opt-in: set DIALECTIC_RUN_CANARY=1 (and a working "
           "GIGACHAT_AUTH_KEY) to run it. Skipped by default so `pytest` never makes a "
           "real network call unconditionally.",
)


@pytest.mark.asyncio
async def test_gigachat_completes_a_trivial_tool_call_scenario():
    """A real GigaChatLLM should complete a one-tool-call scenario cleanly: no parse
    errors, no Rule 5 violations, a non-empty final response."""
    from dialectic_ai.integrations.gigachat.llm import GigaChatLLM

    llm = GigaChatLLM()
    if not llm.auth_key:
        pytest.skip("GIGACHAT_AUTH_KEY is not set -- cannot run the real-provider canary.")

    tools = [MockWeatherTool(), MockCalculatorTool(), MockNoteSaverTool()]
    agent = DialecticalAgent(
        goal="You are a helpful assistant with access to weather, calculator, and note-saving tools.",
        llm=llm,
        tools=tools,
    )
    engine = DialecticalEngine(agent, max_iterations=5)

    output = await engine.run(AgentInput(user_message="What is the weather in Paris?", session_id="canary"))

    assert output.status == "completed", f"Expected status='completed', got {output.status!r}"
    assert output.response.strip(), "Expected a non-empty final response"
    assert not output.dialectical_resolution_missing, (
        "Real provider finalized a response without opposite_process/contradiction/leap "
        "-- see dialectics_rules.md Rule 5 and agent/prompt_builder.py"
    )
    assert not output.leap_action_mismatch, (
        "Real provider claimed leap_type='decompose_and_act' without ever calling a tool"
    )
