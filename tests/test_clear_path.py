"""The "clear" completion path: COMPLETE directly from planning, with no roadmap,
for goals whose simplest process resolves them without a genuine opposite."""
import json

import pytest

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.llm import MockLLM
from dialectic_ai.core.runtime import (
    AllowedMovesResolver, CommitLayer, DesignationRole, Goal, MoveType, Proposal, RuntimeState,
)
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.observability.fixtures import generate_scenario_2
from dialectic_ai.tools import web_search


def apply(state, name, payload):
    return CommitLayer().commit(Proposal(move_type=MoveType(name), payload=payload,
                                        why_this_move_now='Reason', expected_goal_contribution='Goal'), state)


def approved_simplest():
    state = RuntimeState()
    goal = Goal(content='What is the capital city of France?')
    state._goals[goal.id] = goal
    pid = apply(state, 'PROPOSE_SIMPLEST', {'content': 'Recall known facts about France'})
    des = next(d for d in state.get_all_designations() if d.process_id == pid)
    apply(state, 'ASSESS_SIMPLEST', {'candidate_simplest_id': des.id, 'approved': True})
    return state, pid


def develop(state, source_pid):
    return apply(state, 'DEVELOP_PROCESS', {'source_process_id': source_pid, 'emergent_content': 'Paris is the capital',
        'potential_containment': 'c', 'emergence': 'e', 'concretization': 'c', 'new_content': 'n'})


def clear_completion(pid, **overrides):
    payload = {'final_response': 'Paris', 'committed_development_refs': [{'type': 'Process', 'id': pid}],
               'goal_coverage': 'Answered directly', 'why_further_development_not_needed': 'Single known fact'}
    payload.update(overrides)
    return payload


def test_clear_completion_not_offered_before_simplest_develops():
    state, _ = approved_simplest()
    assert MoveType.COMPLETE not in AllowedMovesResolver().allowed_moves(state)


def test_clear_completion_offered_after_simplest_develops():
    state, pid = approved_simplest()
    develop(state, pid)
    assert state.phase == 'planning'
    assert MoveType.COMPLETE in AllowedMovesResolver().allowed_moves(state)


def test_clear_completion_commits_without_roadmap():
    state, pid = approved_simplest()
    emergent = develop(state, pid)
    apply(state, 'COMPLETE', clear_completion(emergent))
    assert state.get_active_goal() is None
    assert state.active_roadmap_id is None
    assert not state._roadmaps
    assert not state.get_all_actions()


def test_clear_completion_cannot_cite_evidence():
    state, pid = approved_simplest()
    emergent = develop(state, pid)
    with pytest.raises(ValueError):
        apply(state, 'COMPLETE', clear_completion(emergent, evidence_observation_ids=['invented']))
    assert state.get_active_goal() is not None


def test_clear_completion_withdrawn_once_opposite_designated():
    state = generate_scenario_2()
    assert any(d.role == DesignationRole.OPPOSITE for d in state.get_all_designations())
    assert state.phase == 'planning'
    assert MoveType.COMPLETE not in AllowedMovesResolver().allowed_moves(state)
    resolution = next(iter(state._resolution_relations.values()))
    with pytest.raises(ValueError, match='not allowed'):
        apply(state, 'COMPLETE', clear_completion(resolution.resolution_process_id))
    assert state.get_active_goal() is not None


class ClearPathLLM(MockLLM):
    """Autopilot that finishes on the clear path as soon as it becomes legal."""

    def _autopilot_proposal(self, prompt):
        data = json.loads(prompt.split("RUNTIME_JSON:\n", 1)[1].split("\nEND_RUNTIME_JSON", 1)[0])
        simplest = next((d for d in data['designations'] if d['role'] == 'simplest'), None)
        sdev = simplest and next((r for r in data['development']
                                  if r['source_process_id'] == simplest['process_id']), None)
        if not sdev:
            return super()._autopilot_proposal(prompt)
        return {'move_type': 'COMPLETE', 'payload': clear_completion(sdev['emergent_process_id']),
                'why_this_move_now': 'Simplest development already answers the goal',
                'expected_goal_contribution': 'Final answer'}


@pytest.mark.asyncio
async def test_engine_finishes_on_clear_path():
    engine = DialecticalEngine(DialecticalAgent('Answer accurately', ClearPathLLM(), [web_search()]))
    result = await engine.run(AgentInput(user_message='What is the capital city of France?'))
    assert result.status == 'completed', result.stop_reason
    assert result.response == 'Paris'
    assert engine.state.active_roadmap_id is None
    assert not engine.state.get_all_actions()
    assert not engine.state.get_all_contradictions()
