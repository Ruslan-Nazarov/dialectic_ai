import asyncio
import json

import pytest

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.llm import MockLLM
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.core.semantic_validator import SemanticValidationResult
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.tools import web_search


def agent(llm=None, mode="dialectic_json"):
    return DialecticalAgent("Protocol test", llm or MockLLM(), [web_search()], tool_calling_mode=mode)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["native", "dialectic_json"])
async def test_roadmap_then_practice_then_completion(mode):
    engine = DialecticalEngine(agent(mode=mode))
    result = await engine.run(AgentInput(user_message="Protocol demonstration"))
    assert result.status == "completed"
    assert result.validation_mode == "simulation"
    moves = [e.move_type.value for e in engine.state._trace if hasattr(e, "move_type")]
    assert moves.index("BEGIN_EXECUTION") < moves.index("PROPOSE_ACTION")
    assert moves.index("PROPOSE_LEAP") < moves.index("PROPOSE_ACTION")
    assert moves.index("ASSESS_PRACTICE") < moves.index("ASSESS_LEAP") < moves.index("COMPLETE")
    assert len(engine.state.get_all_observations()) == 1
    assert engine.state.get_all_observations()[0].success


@pytest.mark.asyncio
async def test_semantic_rejection_does_not_commit():
    class Judge:
        rejected = False
        async def validate(self, proposal, state, goal):
            if proposal.move_type.value == "DEVELOP_PROCESS" and not self.rejected:
                self.rejected = True
                return SemanticValidationResult(accepted=False, reason="Not derived from source")
            return SemanticValidationResult(accepted=True, reason="Test judge")
    engine = DialecticalEngine(agent(), semantic_validator=Judge())
    result = await engine.run(AgentInput(user_message="Example"))
    assert result.status == "completed"
    assert len(engine.state.get_all_development_relations()) == 2
    assert any("Not derived" in (getattr(e,"validation_error","") or "") for e in engine.state._trace)


@pytest.mark.asyncio
async def test_rejection_never_force_approves_simplest():
    class Rejecting(MockLLM):
        async def generate(self, messages, tools=None):
            data = json.loads(await super().generate(messages, tools))
            if data.get("move_type") == "ASSESS_SIMPLEST":
                data["payload"]["approved"] = False
            return json.dumps(data)
    engine = DialecticalEngine(agent(Rejecting()), max_iterations=10)
    result = await engine.run(AgentInput(user_message="Example"))
    assert result.stop_reason == "max_iterations"
    assert not engine.state.get_all_actions()
    assert not any(d.role.value == "simplest" for d in engine.state.get_all_designations())
    assert not any(getattr(e,"event_type","") == "forced_convergence" for e in engine.state._trace)


@pytest.mark.asyncio
async def test_repeated_runs_isolate_completed_graphs():
    engine = DialecticalEngine(agent())
    first = await engine.run(AgentInput(user_message="First"))
    old_state = engine.state
    second = await engine.run(AgentInput(user_message="Second"))
    assert first.status == second.status == "completed"
    assert first.run_id != second.run_id
    assert old_state is not engine.state
    assert next(iter(engine.state._goals.values())).content == "Second"
    assert len(engine.state._roadmaps) == 1


@pytest.mark.asyncio
async def test_model_failure_is_explicit():
    class Broken(MockLLM):
        async def generate(self, messages, tools=None):
            raise RuntimeError("provider unavailable")
    result = await DialecticalEngine(agent(Broken())).run(AgentInput(user_message="Example"))
    assert result.status == "error"
    assert result.stop_reason == "provider_error"


@pytest.mark.asyncio
async def test_concurrent_run_is_rejected_without_state_reset():
    entered = asyncio.Event()
    release = asyncio.Event()
    class Waiting(MockLLM):
        async def generate(self,messages,tools=None):
            entered.set()
            await release.wait()
            return await super().generate(messages,tools)
    engine = DialecticalEngine(agent(Waiting()), max_iterations=1)
    first = asyncio.create_task(engine.run(AgentInput(user_message="First")))
    await entered.wait()
    with pytest.raises(RuntimeError, match="Concurrent"):
        await engine.run(AgentInput(user_message="Second"))
    release.set()
    await first
    assert next(iter(engine.state._goals.values())).content == "First"


@pytest.mark.asyncio
async def test_invalid_tool_arguments_do_not_execute():
    class InvalidArgs(MockLLM):
        async def generate(self,messages,tools=None):
            data = json.loads(await super().generate(messages,tools))
            if data.get("move_type") == "PROPOSE_ACTION":
                data["payload"]["args"] = {"query": 123}
            return json.dumps(data)
    engine = DialecticalEngine(agent(InvalidArgs()), max_rejected_proposals=2)
    result = await engine.run(AgentInput(user_message="Example"))
    assert result.stop_reason == "max_rejected_proposals"
    assert engine.state.get_all_actions() == []
    assert engine.state.get_all_observations() == []


@pytest.mark.asyncio
async def test_tool_timeout_does_not_become_success():
    class SlowTool:
        name="web_search"
        description="Slow fixture"
        def parameters(self):
            return {"type":"object"}
        async def execute(self,args):
            await asyncio.sleep(5)
    a = agent()
    a.tools = [SlowTool()]
    engine = DialecticalEngine(a, tool_timeout=0.01)
    result = await engine.run(AgentInput(user_message="Example"))
    assert result.status == "error"
    assert not engine.state.get_all_observations()[0].success


@pytest.mark.asyncio
async def test_run_deadline_preserves_state():
    class SlowModel(MockLLM):
        async def generate(self, messages, tools=None):
            await asyncio.sleep(1)
            return '{}'
    engine = DialecticalEngine(agent(SlowModel()), run_timeout=0.01)
    result = await engine.run(AgentInput(user_message='Deadline example'))
    assert result.stop_reason == 'run_timeout'
    assert len(engine.state._goals) == 1
    assert not engine.state.get_all_actions()


@pytest.mark.asyncio
async def test_practice_revises_roadmap_and_executes_new_version():
    class Revising(MockLLM):
        async def generate(self, messages, tools=None):
            prompt = messages[-1]['content']
            state = json.loads(prompt.split('RUNTIME_JSON:\n')[1].split('\nEND_RUNTIME_JSON')[0])
            proposal = json.loads(await super().generate(messages, tools))
            def move(name, payload):
                return json.dumps({'move_type':name,'payload':payload,'why_this_move_now':'Practice changed expectations','expected_goal_contribution':'Correct roadmap'})
            if len(state['roadmaps']) == 1:
                if proposal.get('move_type') == 'ASSESS_PRACTICE':
                    proposal['payload']['expected_actual_relation'] = 'contradicted'
                elif state['phase'] == 'executing' and 'REVISE_WORLD' in state['allowed_moves'] and state['practice']:
                    return move('REVISE_WORLD',{'observation_ids':[state['observations'][-1]['id']],'reason':'Actual result contradicts expected result'})
                elif state['phase'] == 'planning' and len(state['resolutions']) == 1:
                    return move('PROPOSE_LEAP',{'contradiction_id':state['contradictions'][0]['id'],'resolution_content':'Revised roadmap realization based on actual conditions','resolution_outcome':'mediation'})
            return json.dumps(proposal)
    engine = DialecticalEngine(agent(Revising()))
    result = await engine.run(AgentInput(user_message='Practice revision example'))
    assert result.status == 'completed'
    assert len(engine.state._roadmaps) == 2
    first, second = engine.state._roadmaps.values()
    assert second.revision_observation_ids
    assert first.snapshot != second.snapshot
    assert {a.roadmap_id for a in engine.state.get_all_actions()} == {first.id, second.id}
    assert len(engine.state.get_all_observations()) == 2
