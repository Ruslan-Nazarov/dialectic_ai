import copy

import pytest

from dialectic_ai.core.runtime import (
    AllowedMovesResolver, CommitLayer, DesignationRole, Goal, MoveType,
    Proposal, RuntimeState,
)
from dialectic_ai.observability.fixtures import generate_scenario_2


def apply(state, name, payload):
    return CommitLayer().commit(Proposal(move_type=MoveType(name), payload=payload,
                                        why_this_move_now='Reason', expected_goal_contribution='Goal'), state)


@pytest.fixture
def planned():
    return generate_scenario_2()


def begin(state):
    simplest = next(d for d in state.get_all_designations() if d.role == DesignationRole.SIMPLEST)
    resolution = next(iter(state._resolution_relations.values()))
    return apply(state, 'BEGIN_EXECUTION', {'simplest_id': simplest.id,
        'contradiction_ids': [resolution.contradiction_id], 'resolution_ids': [resolution.id],
        'execution_process_ids': [resolution.resolution_process_id]})


def action(state):
    roadmap = state._roadmaps[state.active_roadmap_id]
    return apply(state, 'PROPOSE_ACTION', {'tool_name': 'tool', 'args': {},
        'origin_ref': {'type': 'Process', 'id': roadmap.execution_process_ids[0]},
        'why_now': 'Practice', 'purpose': 'Measure', 'expectation': 'Result', 'relation_to_goal': 'Test roadmap'})


def observe(state, success=True, relation='confirmed'):
    aid = action(state)
    oid = CommitLayer().create_observation(state, aid, 'observed data', success, None if success else 'failed')
    apply(state, 'ASSESS_PRACTICE', {'action_id': aid, 'observation_id': oid,
        'expected_actual_relation': relation, 'explanation': 'Compare actual with expected',
        'consequence_for_development': 'Update direction'})
    return oid


def completion(state, oid):
    roadmap = state._roadmaps[state.active_roadmap_id]
    return {'final_response': 'Result', 'committed_development_refs': [{'type': 'Process', 'id': roadmap.execution_process_ids[0]}],
            'evidence_observation_ids': [oid], 'goal_coverage': 'Covered', 'why_further_development_not_needed': 'Done'}


def test_complete_roadmap_before_first_tool(planned):
    assert planned.phase == 'planning'
    assert not planned.get_all_actions()
    assert MoveType.PROPOSE_ACTION not in AllowedMovesResolver().allowed_moves(planned)
    begin(planned)
    assert planned.phase == 'executing'
    assert action(planned)


def test_planned_leap_is_not_realized(planned):
    resolution = next(iter(planned._resolution_relations.values()))
    assert resolution.confirmed_roadmap_id is None
    assert planned.get_contradiction(resolution.contradiction_id).status.value == 'developing'


def test_planning_cannot_execute_even_by_direct_commit(planned):
    pid = planned.get_all_processes()[0].id
    with pytest.raises(ValueError, match='forbidden during planning'):
        apply(planned, 'PROPOSE_ACTION', {'tool_name': 't', 'args': {}, 'origin_ref': {'type': 'Process', 'id': pid},
              'why_now': 'w', 'purpose': 'p', 'expectation': 'e', 'relation_to_goal': 'r'})


def test_action_requires_accepted_route(planned):
    begin(planned)
    pid = planned.get_all_processes()[0].id
    with pytest.raises(ValueError, match='accepted execution route'):
        apply(planned, 'PROPOSE_ACTION', {'tool_name': 't', 'args': {}, 'origin_ref': {'type': 'Process', 'id': pid},
              'why_now': 'w', 'purpose': 'p', 'expectation': 'e', 'relation_to_goal': 'r'})


def test_observation_must_be_assessed_before_next_action(planned):
    begin(planned)
    aid = action(planned)
    CommitLayer().create_observation(planned, aid, 'data', True)
    with pytest.raises(ValueError, match='Assess the previous observation'):
        action(planned)


def test_contradicted_practice_forces_revision_not_invented_opposite(planned):
    begin(planned)
    before = len(planned._contradictions)
    oid = observe(planned, relation='contradicted')
    assert len(planned._contradictions) == before
    assert AllowedMovesResolver().allowed_moves(planned) == [MoveType.REVISE_WORLD]
    with pytest.raises(ValueError):
        action(planned)
    prior = copy.deepcopy(planned._roadmaps[planned.active_roadmap_id])
    apply(planned, 'REVISE_WORLD', {'observation_ids': [oid], 'reason': 'Expectation disproved'})
    assert planned.phase == 'planning'
    assert planned._roadmaps[prior.id] == prior
    assert planned.get_observation(oid)
    with pytest.raises(ValueError, match='Revision must change'):
        begin(planned)


def test_failure_cannot_confirm_expectation(planned):
    begin(planned)
    with pytest.raises(ValueError, match='failed tool execution'):
        observe(planned, success=False)


def test_completion_requires_realized_leap(planned):
    begin(planned)
    oid = observe(planned)
    with pytest.raises(ValueError, match='planned leap'):
        apply(planned, 'COMPLETE', completion(planned, oid))
    resolution = next(iter(planned._resolution_relations.values()))
    apply(planned, 'ASSESS_LEAP', {'resolution_id': resolution.id, 'observation_ids': [oid], 'explanation': 'Observed realization'})
    apply(planned, 'COMPLETE', completion(planned, oid))
    assert planned.get_active_goal() is None
    assert AllowedMovesResolver().allowed_moves(planned) == []


@pytest.mark.parametrize('field,value', [('final_response',''), ('committed_development_refs',[]), ('evidence_observation_ids',[])])
def test_empty_completion_rejected(planned, field, value):
    begin(planned)
    oid = observe(planned)
    resolution = next(iter(planned._resolution_relations.values()))
    apply(planned, 'ASSESS_LEAP', {'resolution_id': resolution.id, 'observation_ids': [oid], 'explanation': 'Observed realization'})
    payload = completion(planned, oid)
    payload[field] = value
    with pytest.raises(ValueError):
        apply(planned, 'COMPLETE', payload)


def test_roadmap_cannot_skip_leap(planned):
    planned._resolution_relations.clear()
    assert MoveType.BEGIN_EXECUTION not in AllowedMovesResolver().allowed_moves(planned)


def test_unknown_entity_is_not_committed(planned):
    assert not planned.is_committed('missing')


def test_failed_commit_does_not_mutate(planned):
    before = copy.deepcopy(planned.__dict__)
    with pytest.raises(ValueError):
        apply(planned, 'BEGIN_EXECUTION', {'simplest_id': 'missing'})
    assert planned.__dict__ == before
