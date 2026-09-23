"""Opt-in real inference. Never silently pass when a configured provider fails."""
import os

import pytest

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.integrations.providers import build_llm
from dialectic_ai.reality import PythonExecutor


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv('DIALECTIC_RUN_CANARY') != '1', reason='Real provider canary is opt-in')
async def test_real_provider_roadmap(tmp_path):
    from dialectic_ai.core.logger import DevelopmentLogger
    provider = os.getenv('DIALECTIC_CANARY_PROVIDER', 'gigachat')
    key = {'gigachat':'GIGACHAT_AUTH_KEY','groq':'GROQ_API_KEY','openai':'OPENAI_API_KEY','gemini':'GEMINI_API_KEY'}.get(provider)
    if key and not os.getenv(key):
        pytest.skip(f'{key} is not configured')
    llm = build_llm(provider)
    assert type(llm).__name__ != 'MockLLM'
    llm.max_retries = 0
    llm.max_tokens = 1500
    agent = DialecticalAgent('Compute and verify arithmetic using the provided Python tool. Answer accurately and concisely.',
                            llm=llm, tools=[PythonExecutor()])
    engine = DialecticalEngine(agent, max_iterations=25, run_timeout=480,
                              logger=DevelopmentLogger(trace_path=str(tmp_path / 'canary.jsonl')))
    result = await engine.run(AgentInput(user_message='Calculate 17 * 23 and verify the result with Python.'))
    assert result.status == 'completed', f'{result.stop_reason}: {result.response}'
    assert result.validation_mode == 'semantic'
    assert '391' in result.response
    assert engine.state._roadmaps
    assert any(o.success and '391' in str(o.raw_result) for o in engine.state.get_all_observations())
