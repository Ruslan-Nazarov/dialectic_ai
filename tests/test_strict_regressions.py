import json
import pytest

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.llm import MockLLM
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.reality.delegation import SubAgentTool


@pytest.mark.asyncio
@pytest.mark.parametrize('raw', ['[1]', '42', '{"move_type":"NOT_A_MOVE"}'])
async def test_malformed_proposals_are_bounded(raw):
    engine = DialecticalEngine(DialecticalAgent('g', MockLLM([raw])), max_rejected_proposals=2)
    result = await engine.run(AgentInput(user_message='g'))
    assert result.stop_reason == 'max_rejected_proposals'
    assert len([e for e in engine.state._trace if getattr(e, 'event_type', '') == 'proposal_rejected']) == 2


@pytest.mark.asyncio
async def test_subagent_failure_is_not_evidence_of_success():
    engine = DialecticalEngine(DialecticalAgent('g'), max_iterations=0)
    result = await SubAgentTool('worker', 'worker', engine).execute({'task': 'g'})
    assert not result.success


@pytest.mark.asyncio
async def test_role_and_tools_reach_model():
    class Capture(MockLLM):
        async def generate(self, messages, tools=None):
            self.seen = messages
            return '[1]'

    class Tool:
        name = 'unique_tool_name'
        description = 'unique_tool_description'
        def parameters(self):
            return {'type': 'object', 'properties': {'unique_argument': {'type': 'string'}}}

    llm = Capture()
    engine = DialecticalEngine(DialecticalAgent('unique_agent_role', llm, [Tool()]), max_iterations=1)
    await engine.run(AgentInput(user_message='question'))
    prompt = json.dumps(llm.seen)
    for value in ['unique_agent_role', 'unique_tool_name', 'unique_tool_description', 'unique_argument']:
        assert value in prompt


@pytest.mark.asyncio
async def test_runs_have_fresh_identity_and_goal():
    engine = DialecticalEngine(DialecticalAgent('g'), max_iterations=0)
    first = await engine.run(AgentInput(user_message='first'))
    second = await engine.run(AgentInput(user_message='second'))
    assert first.run_id != second.run_id
    assert len(engine.state._goals) == 1
    assert next(iter(engine.state._goals.values())).content == 'second'
