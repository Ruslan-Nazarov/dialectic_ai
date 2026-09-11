"""
Test Layer 4: Multi-agent Triad (Thesis / Antithesis / Synthesis).
"""
import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.core import MockLLM
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.multi.triad import DialecticalTriad

@pytest.mark.asyncio
async def test_dialectical_triad():
    thesis_llm = MockLLM(responses=[
        '{"thought":"Generating draft", "response":"def is_prime(n): return True"}'
    ])
    thesis_agent = DialecticalAgent(goal="You are the Generator.", llm=thesis_llm)
    thesis_engine = DialecticalEngine(thesis_agent)

    antithesis_llm = MockLLM(responses=[
        '{"thought":"Critiquing", "response":"Critique: The function always returns True."}'
    ])
    antithesis_agent = DialecticalAgent(goal="You are the Critic.", llm=antithesis_llm)
    antithesis_engine = DialecticalEngine(antithesis_agent)

    synthesis_llm = MockLLM(responses=[
        '{"thought":"Synthesizing", "response":"Corrected code: def is_prime(n): ..."}'
    ])
    synthesis_agent = DialecticalAgent(goal="You are the Synthesis.", llm=synthesis_llm)
    synthesis_engine = DialecticalEngine(synthesis_agent)

    triad = DialecticalTriad(
        thesis=thesis_engine,
        antithesis=antithesis_engine,
        synthesis=synthesis_engine
    )

    result = await triad.run("Write a function is_prime")
    assert result.agent_name == "triad_synthesis"
    assert "Corrected code:" in result.response