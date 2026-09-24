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


def revised_with_new_leap(state):
    """Roadmap -> contradicted practice -> revision -> a new leap for the same contradiction."""
    begin(state)
    oid = observe(state, relation='contradicted')
    apply(state, 'REVISE_WORLD', {'observation_ids': [oid], 'reason': 'Expectation disproved'})
    old = next(iter(state._resolution_relations.values()))
    new_process = apply(state, 'PROPOSE_LEAP', {'contradiction_id': old.contradiction_id,
        'resolution_content': 'Verify by an independent method', 'resolution_outcome': 'replacement'})
    new = next(r for r in state._resolution_relations.values() if r.id != old.id)
    return old, new


def test_route_rejection_names_stale_process_and_allowed_ones(planned):
    old, new = revised_with_new_leap(planned)
    simplest = next(d for d in planned.get_all_designations() if d.role == DesignationRole.SIMPLEST)
    with pytest.raises(ValueError) as err:
        apply(planned, 'BEGIN_EXECUTION', {'simplest_id': simplest.id, 'contradiction_ids': [new.contradiction_id],
            'resolution_ids': [new.id], 'execution_process_ids': [old.resolution_process_id]})
    message = str(err.value)
    assert old.resolution_process_id in message.split('allowed')[0]
    assert new.resolution_process_id in message.split('allowed')[1]
    apply(planned, 'BEGIN_EXECUTION', {'simplest_id': simplest.id, 'contradiction_ids': [new.contradiction_id],
        'resolution_ids': [new.id], 'execution_process_ids': [new.resolution_process_id]})
    assert planned.phase == 'executing'


def test_revision_guidance_names_the_new_leap_process(planned):
    from dialectic_ai.engine.prompt import _next_step_guidance, build_alias_map
    old, new = revised_with_new_leap(planned)
    aliases = build_alias_map(planned)
    guidance = _next_step_guidance(planned, lambda x: aliases.get(x, x))
    assert f"must include the new leap's own process {aliases[new.resolution_process_id]}" in guidance


def test_feedback_text_uses_aliases():
    from dialectic_ai.engine.prompt import alias_text
    uid = '0b1685c3-c970-4510-9bbc-7b1a69577814'
    assert alias_text(f'process {uid} is not allowed; allowed: [{uid}]', {uid: 'P4'}) == 'process P4 is not allowed; allowed: [P4]'


def act(state, code, relation):
    """One action with its own args, observed and assessed with `relation`."""
    roadmap = state._roadmaps[state.active_roadmap_id]
    aid = apply(state, 'PROPOSE_ACTION', {'tool_name': 'tool', 'args': {'code': code},
        'origin_ref': {'type': 'Process', 'id': roadmap.execution_process_ids[0]},
        'why_now': 'Practice', 'purpose': 'Measure', 'expectation': 'Result', 'relation_to_goal': 'Test roadmap'})
    oid = CommitLayer().create_observation(state, aid, f'output of {code}', True, None)
    apply(state, 'ASSESS_PRACTICE', {'action_id': aid, 'observation_id': oid, 'expected_actual_relation': relation,
        'explanation': 'Compare actual with expected', 'consequence_for_development': 'Update direction'})
    return oid


def contradicted_twice(state):
    """Two differently-argued actions contradicted, with a revision in between."""
    old, new = revised_with_new_leap(state)   # first contradicted action + revision + new leap
    first = next(o.id for o in state.get_all_observations())
    simplest = next(d for d in state.get_all_designations() if d.role == DesignationRole.SIMPLEST)
    apply(state, 'BEGIN_EXECUTION', {'simplest_id': simplest.id, 'contradiction_ids': [new.contradiction_id],
        'resolution_ids': [new.id], 'execution_process_ids': [new.resolution_process_id]})
    second = act(state, 'print(a * b)', 'contradicted')
    return first, second


def report(contradicting, supported_answer=None, supporting=()):
    return {'contested_source': 'The tool output for a * b', 'contradicting_observation_ids': list(contradicting),
            'supported_answer': supported_answer, 'supporting_observation_ids': list(supporting),
            'final_response': 'The tool kept contradicting independent checks; no reliable answer.'}


def test_unresolved_report_not_offered_after_one_contradiction(planned):
    begin(planned)
    oid = observe(planned, relation='contradicted')
    assert MoveType.REPORT_CONTRADICTION not in AllowedMovesResolver().allowed_moves(planned)
    with pytest.raises(ValueError):
        apply(planned, 'REPORT_CONTRADICTION', report([oid, oid]))


def test_unresolved_report_after_persistent_contradiction(planned):
    first, second = contradicted_twice(planned)
    assert MoveType.REPORT_CONTRADICTION in AllowedMovesResolver().allowed_moves(planned)
    rid = apply(planned, 'REPORT_CONTRADICTION', report([first, second]))
    assert planned.get_active_goal() is None
    assert planned._unresolved_reports[rid].contradicting_observation_ids == [first, second]
    assert not planned._completions


def test_unresolved_report_rejects_ungrounded_answers(planned):
    first, second = contradicted_twice(planned)
    with pytest.raises(ValueError, match='supporting_observation_ids'):
        apply(planned, 'REPORT_CONTRADICTION', report([first, second], supported_answer='391'))
    with pytest.raises(ValueError, match='independent of the contradiction'):
        apply(planned, 'REPORT_CONTRADICTION', report([first, second], supported_answer='391', supporting=[second]))
    assert planned.get_active_goal() is not None


def test_same_action_repeated_is_not_persistence(planned):
    begin(planned)
    first = act(planned, 'print(a * b)', 'contradicted')
    apply(planned, 'REVISE_WORLD', {'observation_ids': [first], 'reason': 'Expectation disproved'})
    from dialectic_ai.core.world import persistent_contradiction
    assert not persistent_contradiction(planned)


def test_assess_leap_is_not_offered_once_every_leap_is_assessed(planned):
    begin(planned)
    oid = observe(planned)
    moves = AllowedMovesResolver().allowed_moves(planned)
    assert MoveType.ASSESS_LEAP in moves and MoveType.COMPLETE not in moves
    resolution = next(iter(planned._resolution_relations.values()))
    apply(planned, 'ASSESS_LEAP', {'resolution_id': resolution.id, 'observation_ids': [oid], 'explanation': 'Observed'})
    moves = AllowedMovesResolver().allowed_moves(planned)
    assert MoveType.COMPLETE in moves and MoveType.ASSESS_LEAP not in moves
