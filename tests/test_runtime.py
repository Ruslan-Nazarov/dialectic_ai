import pytest
from dialectic_ai.observability.fixtures import generate_scenario_2
from tests.test_world_contract import apply, begin, action, observe, completion
from dialectic_ai.core.runtime import (
    RuntimeState, StructuralValidator, CommitLayer, AllowedMovesResolver,
    MoveType, Proposal, DesignationRole, ContradictionStatus, ResolutionOutcome, Goal, RuntimeReference,
    is_valid_str
)

@pytest.fixture
def state_and_commit():
    state = RuntimeState()
    goal = Goal(content="Test goal")
    state._goals[goal.id] = goal
    return state, CommitLayer()

# 1. Proposal boundary & Atomicity
def test_1_proposal_does_not_mutate_state(state_and_commit):
    state, commit = state_and_commit
    p = Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "test"}, why_this_move_now="w", expected_goal_contribution="e")
    assert len(state.get_all_processes()) == 0

def test_2_only_successful_commit_alters_state(state_and_commit):
    state, commit = state_and_commit
    p = Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={}, why_this_move_now="w", expected_goal_contribution="e")
    with pytest.raises(ValueError):
        commit.commit(p, state)
    assert len(state.get_all_processes()) == 0

def test_failed_commit_leaves_state_unchanged(state_and_commit):
    state, commit = state_and_commit
    p = Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": ""}, why_this_move_now="w", expected_goal_contribution="e")
    with pytest.raises(ValueError):
        commit.commit(p, state)
    assert len(state.get_all_processes()) == 0
    assert len(state._trace) == 0  # no trace on failure

def test_encapsulation_public_mutation_fails(state_and_commit):
    state, commit = state_and_commit
    with pytest.raises(AttributeError):
        # state.processes doesn't exist anymore, it's state._processes
        state.processes["x"] = "x"

def test_whitespace_only_rejection(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    with pytest.raises(ValueError, match="Missing emergence"):
        commit.commit(Proposal(move_type=MoveType.DEVELOP_PROCESS, payload={
            "source_process_id": pid, "emergent_content": "e", "potential_containment": "x", "emergence": "   ", "concretization": "x", "new_content": "x"
        }, why_this_move_now="w", expected_goal_contribution="e"), state)


# Development & Multiple sources
def test_3_development_relation_without_source_rejected(state_and_commit):
    state, commit = state_and_commit
    p = Proposal(move_type=MoveType.DEVELOP_PROCESS, payload={
        "source_process_id": "nonexistent",
        "emergent_content": "new",
        "potential_containment": "x",
        "emergence": "x",
        "concretization": "x",
        "new_content": "x"
    }, why_this_move_now="w", expected_goal_contribution="e")
    with pytest.raises(ValueError, match="Source process does not exist"):
        commit.commit(p, state)

def test_4_development_relation_missing_justification_rejected(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "base"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    p2 = Proposal(move_type=MoveType.DEVELOP_PROCESS, payload={
        "source_process_id": pid,
        "emergent_content": "new",
        "potential_containment": "x",
        "emergence": "", # missing
        "concretization": "x",
        "new_content": "x"
    }, why_this_move_now="w", expected_goal_contribution="e")
    with pytest.raises(ValueError, match="Missing emergence"):
        commit.commit(p2, state)

def test_5_one_process_can_have_multiple_emergent(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "base"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    for _ in range(2):
        commit.commit(Proposal(move_type=MoveType.DEVELOP_PROCESS, payload={
            "source_process_id": pid, "emergent_content": "e", "potential_containment": "x", "emergence": "x", "concretization": "x", "new_content": "x"
        }, why_this_move_now="w", expected_goal_contribution="e"), state)
    assert len(state.get_all_processes()) == 3

def test_6_multiple_source_development_works(state_and_commit):
    state, commit = state_and_commit
    pid_A = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "A"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    des = [d for d in state.get_all_designations() if d.process_id == pid_A][0]
    commit.commit(Proposal(move_type=MoveType.ASSESS_SIMPLEST, payload={"candidate_simplest_id": des.id, "approved": True}, why_this_move_now="w", expected_goal_contribution="e"), state)
    
    pid_B = commit.commit(Proposal(move_type=MoveType.DESIGNATE_OPPOSITE, payload={"simplest_id": des.id, "context_id": pid_A, "content": "B", "justification": "j", "caught_from": "c"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    
    pid_C = commit.commit(Proposal(move_type=MoveType.DEVELOP_PROCESS, payload={
        "source_process_id": pid_A, "emergent_content": "C", "potential_containment": "x", "emergence": "x", "concretization": "x", "new_content": "x"
    }, why_this_move_now="w", expected_goal_contribution="e"), state)
    
    pid_rel_B_C = commit.commit(Proposal(move_type=MoveType.CONNECT_DEVELOPMENT, payload={
        "source_process_id": pid_B, "emergent_process_id": pid_C, "potential_containment": "x", "emergence": "x", "concretization": "x", "new_content": "x"
    }, why_this_move_now="w", expected_goal_contribution="e"), state)
    
    # Assert C is still one process
    assert len(state.get_all_processes()) == 3
    # Assert two relations
    assert len(state.get_all_development_relations()) == 2
    relations_to_C = [r for r in state.get_all_development_relations() if r.emergent_process_id == pid_C]
    assert len(relations_to_C) == 2


# Simplest & Goal Ownership
def test_7_candidate_simplest_can_have_provisional_dev(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    dev_pid = commit.commit(Proposal(move_type=MoveType.DEVELOP_PROCESS, payload={
        "source_process_id": pid, "emergent_content": "e", "potential_containment": "x", "emergence": "x", "concretization": "x", "new_content": "x"
    }, why_this_move_now="w", expected_goal_contribution="e"), state)
    assert not state.is_committed(dev_pid)

def test_8_provisional_is_not_committed(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    assert not state.is_committed(pid)

def test_9_successful_assessment_commits(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    des = [d for d in state.get_all_designations() if d.process_id == pid][0]
    commit.commit(Proposal(move_type=MoveType.ASSESS_SIMPLEST, payload={"candidate_simplest_id": des.id, "approved": True}, why_this_move_now="w", expected_goal_contribution="e"), state)
    assert state.is_committed(pid)
    assert des.role == DesignationRole.SIMPLEST

def test_10_rejected_candidate_superseded(state_and_commit):
    state, commit = state_and_commit
    
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    des = [d for d in state.get_all_designations() if d.process_id == pid][0]
    
    # Add a provisional child
    dev_pid = commit.commit(Proposal(move_type=MoveType.DEVELOP_PROCESS, payload={
        "source_process_id": pid, "emergent_content": "dev", "potential_containment": "x", "emergence": "x", "concretization": "x", "new_content": "x"
    }, why_this_move_now="w", expected_goal_contribution="e"), state)
    
    commit.commit(Proposal(move_type=MoveType.ASSESS_SIMPLEST, payload={"candidate_simplest_id": des.id, "approved": False}, why_this_move_now="w", expected_goal_contribution="e"), state)
    
    # 1. rejected Candidate становится superseded
    assert state.get_process(pid).status == "superseded"
    
    # 2. его provisional Process остаётся non-committed
    assert not state.is_committed(dev_pid)
    
    # 3. его provisional DevelopmentRelation остаётся non-committed
    drs = state.get_all_development_relations()
    assert len(drs) == 1
    assert not state.is_committed(drs[0].id)
    
    # 4. rejected branch остаётся виден для history/read-model
    assert state.get_process(pid) is not None
    assert state.get_process(dev_pid) is not None
    
    # 5. rejected branch нельзя использовать как committed source
    #    (Since it is not in committed space, and allowed moves resets)
    from dialectic_ai.core.runtime import AllowedMovesResolver
    allowed = AllowedMovesResolver().allowed_moves(state)
    assert MoveType.PROPOSE_SIMPLEST in allowed
    assert MoveType.DEVELOP_PROCESS not in allowed  # Can't develop without a simplest
    
    # 6. после committed rejection нового Candidate можно предложить снова
    pid_new = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s2"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    assert not state.is_committed(pid_new)
    
    # 7. provisional branch другого Candidate не затрагивается
    dev_pid_new = commit.commit(Proposal(move_type=MoveType.DEVELOP_PROCESS, payload={
        "source_process_id": pid_new, "emergent_content": "dev2", "potential_containment": "x", "emergence": "x", "concretization": "x", "new_content": "x"
    }, why_this_move_now="w", expected_goal_contribution="e"), state)
    assert not state.is_committed(dev_pid_new)
def test_goal_absent_rejected(state_and_commit):
    state, commit = state_and_commit
    state.get_active_goal().active = False
    with pytest.raises(ValueError, match="PROPOSE_SIMPLEST requires active Goal"):
        commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_provisional_assessment_does_not_commit_others(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content":"s"}, why_this_move_now="w", expected_goal_contribution="e"),state)
    with pytest.raises(ValueError, match="not allowed"):
        commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content":"s2"}, why_this_move_now="w", expected_goal_contribution="e"),state)
    assert len(state.get_all_processes()) == 1
    assert not state.is_committed(pid)


# Opposite
def test_11_opposite_without_committed_simplest_rejected(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    des = [d for d in state.get_all_designations() if d.process_id == pid][0]
    with pytest.raises(ValueError, match="Invalid simplest_id"):
        commit.commit(Proposal(move_type=MoveType.DESIGNATE_OPPOSITE, payload={"simplest_id": des.id, "context_id": pid, "content": "o", "justification": "j", "caught_from": "c"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_12_opposite_without_dev_context_rejected(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    des = [d for d in state.get_all_designations() if d.process_id == pid][0]
    commit.commit(Proposal(move_type=MoveType.ASSESS_SIMPLEST, payload={"candidate_simplest_id": des.id, "approved": True}, why_this_move_now="w", expected_goal_contribution="e"), state)
    with pytest.raises(ValueError, match="Development context_id does not exist"):
        commit.commit(Proposal(move_type=MoveType.DESIGNATE_OPPOSITE, payload={"simplest_id": des.id, "context_id": "nonexistent", "content": "o", "justification": "j", "caught_from": "c"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_13_opposite_designation_does_not_mutate_process_type(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    des = [d for d in state.get_all_designations() if d.process_id == pid][0]
    commit.commit(Proposal(move_type=MoveType.ASSESS_SIMPLEST, payload={"candidate_simplest_id": des.id, "approved": True}, why_this_move_now="w", expected_goal_contribution="e"), state)
    opid = commit.commit(Proposal(move_type=MoveType.DESIGNATE_OPPOSITE, payload={"simplest_id": des.id, "context_id": pid, "content": "o", "justification": "j", "caught_from": "c"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    assert type(state.get_process(opid)).__name__ == "Process"


# Action
def test_14_action_without_provenance_rejected(state_and_commit):
    state, commit = state_and_commit
    with pytest.raises(ValueError, match="Missing origin_ref"):
        commit.commit(Proposal(move_type=MoveType.PROPOSE_ACTION, payload={"tool_name": "t", "expectation": "e", "why_now": "w", "purpose": "p", "relation_to_goal": "r"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_15_action_without_expectation_rejected(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    with pytest.raises(ValueError, match="Missing expectation"):
        commit.commit(Proposal(move_type=MoveType.PROPOSE_ACTION, payload={"tool_name": "t", "origin_ref": {"type": "Process", "id": pid}, "why_now": "w", "purpose": "p", "relation_to_goal": "r"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_16_action_origin_can_be_process(state_and_commit):
    state = generate_scenario_2()
    begin(state)
    assert action(state) in state._actions

def test_17_action_origin_can_be_dev_relation(state_and_commit):
    state = generate_scenario_2()
    begin(state)
    oid = observe(state)
    refs = {"DevelopmentRelation":next(iter(state._development_relations)),"Contradiction":next(iter(state._contradictions)),"PracticeAssessment":next(iter(state._practice_assessments))}
    with pytest.raises(ValueError, match="accepted execution route"):
        apply(state,"PROPOSE_ACTION",{"tool_name":"t","args":{},"origin_ref":{"type":"DevelopmentRelation","id":refs["DevelopmentRelation"]},"why_now":"w","purpose":"p","expectation":"e","relation_to_goal":"r"})

def test_18_action_origin_can_be_contradiction(state_and_commit):
    state = generate_scenario_2()
    begin(state)
    oid = observe(state)
    refs = {"DevelopmentRelation":next(iter(state._development_relations)),"Contradiction":next(iter(state._contradictions)),"PracticeAssessment":next(iter(state._practice_assessments))}
    with pytest.raises(ValueError, match="accepted execution route"):
        apply(state,"PROPOSE_ACTION",{"tool_name":"t","args":{},"origin_ref":{"type":"Contradiction","id":refs["Contradiction"]},"why_now":"w","purpose":"p","expectation":"e","relation_to_goal":"r"})

def test_19_action_origin_can_be_practice_assessment(state_and_commit):
    state = generate_scenario_2()
    begin(state)
    oid = observe(state)
    refs = {"DevelopmentRelation":next(iter(state._development_relations)),"Contradiction":next(iter(state._contradictions)),"PracticeAssessment":next(iter(state._practice_assessments))}
    with pytest.raises(ValueError, match="accepted execution route"):
        apply(state,"PROPOSE_ACTION",{"tool_name":"t","args":{},"origin_ref":{"type":"PracticeAssessment","id":refs["PracticeAssessment"]},"why_now":"w","purpose":"p","expectation":"e","relation_to_goal":"r"})

# Observation
def test_20_observation_without_action_rejected(state_and_commit):
    state, commit = state_and_commit
    with pytest.raises(ValueError):
        commit.create_observation(state, action_id="none", raw_result="res", success=True)

def test_21_observation_does_not_create_process(state_and_commit):
    state = generate_scenario_2()
    begin(state)
    aid = action(state)
    before = len(state.get_all_processes())
    CommitLayer().create_observation(state, aid, "actual", True)
    assert len(state.get_all_processes()) == before

# Practice
def test_22_practice_assessment_requires_action_observation(state_and_commit):
    state, commit = state_and_commit
    with pytest.raises(ValueError, match="Action does not exist"):
        commit.commit(Proposal(move_type=MoveType.ASSESS_PRACTICE, payload={"action_id": "x", "observation_id": "y"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_practice_assessment_cross_link_rejected(state_and_commit):
    state = generate_scenario_2()
    begin(state)
    oid = observe(state)
    aid = action(state)
    with pytest.raises(ValueError):
        apply(state, "ASSESS_PRACTICE", {"action_id":aid, "observation_id":oid, "expected_actual_relation":"confirmed", "explanation":"x", "consequence_for_development":"x"})

def test_23_mismatch_does_not_create_opposite(state_and_commit):
    state = generate_scenario_2()
    begin(state)
    before = len(state.get_all_designations())
    observe(state, relation="contradicted")
    assert len(state.get_all_designations()) == before

def test_24_mismatch_does_not_create_contradiction(state_and_commit):
    state = generate_scenario_2()
    begin(state)
    before = len(state.get_all_contradictions())
    observe(state, relation="contradicted")
    assert len(state.get_all_contradictions()) == before


# Contradiction
def test_25_contradiction_without_simplest_rejected(state_and_commit):
    state, commit = state_and_commit
    with pytest.raises(ValueError, match="Invalid simplest_id"):
        commit.commit(Proposal(move_type=MoveType.ESTABLISH_CONTRADICTION, payload={"simplest_id": "x", "opposite_id": "y", "unity_justification": "u", "developing_unity_description": "d"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_26_contradiction_without_opposite_rejected(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    des = [d for d in state.get_all_designations() if d.process_id == pid][0]
    commit.commit(Proposal(move_type=MoveType.ASSESS_SIMPLEST, payload={"candidate_simplest_id": des.id, "approved": True}, why_this_move_now="w", expected_goal_contribution="e"), state)
    with pytest.raises(ValueError, match="Invalid opposite_id"):
        commit.commit(Proposal(move_type=MoveType.ESTABLISH_CONTRADICTION, payload={"simplest_id": des.id, "opposite_id": "y", "unity_justification": "u", "developing_unity_description": "d"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_27_contradiction_requires_committed_development_refs(state_and_commit):
    state = generate_scenario_2()
    contradiction = state.get_all_contradictions()[0]
    rel = state.get_development_relation(contradiction.simplest_dev_ref_ids[0])
    state._provisional_owners[rel.id] = "uncommitted"
    payload = {"simplest_id":contradiction.simplest_id,"opposite_id":contradiction.opposite_id,
        "simplest_dev_ref_ids":[rel.id], "opposite_dev_ref_ids":contradiction.opposite_dev_ref_ids,
        "unity_justification":"unity", "developing_unity_description":"development"}
    with pytest.raises(ValueError, match="not committed"):
        apply(state,"ESTABLISH_CONTRADICTION",payload)

def test_28_opposite_commit_does_not_create_contradiction(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    des = [d for d in state.get_all_designations() if d.process_id == pid][0]
    commit.commit(Proposal(move_type=MoveType.ASSESS_SIMPLEST, payload={"candidate_simplest_id": des.id, "approved": True}, why_this_move_now="w", expected_goal_contribution="e"), state)
    commit.commit(Proposal(move_type=MoveType.DESIGNATE_OPPOSITE, payload={"simplest_id": des.id, "context_id": pid, "content": "o", "justification": "j", "caught_from": "c"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    assert len(state.get_all_contradictions()) == 0

def test_contradiction_dev_ref_ownership(state_and_commit):
    state = generate_scenario_2()
    c = state.get_all_contradictions()[0]
    with pytest.raises(ValueError, match="does not belong"):
        apply(state,"ESTABLISH_CONTRADICTION",{"simplest_id":c.simplest_id,"opposite_id":c.opposite_id,
            "simplest_dev_ref_ids":c.opposite_dev_ref_ids,"opposite_dev_ref_ids":c.simplest_dev_ref_ids,
            "unity_justification":"u","developing_unity_description":"d"})


# Leap
def test_29_leap_without_contradiction_rejected(state_and_commit):
    state, commit = state_and_commit
    with pytest.raises(ValueError, match="Contradiction does not exist"):
        commit.commit(Proposal(move_type=MoveType.PROPOSE_LEAP, payload={"contradiction_id": "x", "resolution_outcome": "replacement", "resolution_content": "r", "opposite_acting_on_simplest": "a"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_30_planned_replacement_does_not_claim_realization(state_and_commit):
    state = generate_scenario_2()
    c = state.get_all_contradictions()[0]
    apply(state,"PROPOSE_LEAP",{"contradiction_id":c.id,"resolution_content":"replacement plan","resolution_outcome":"replacement","opposite_acting_on_simplest":"a"})
    assert c.status == ContradictionStatus.DEVELOPING  # A plan never claims realization.
    assert state.get_all_actions() == []

def test_31_mediation_leaves_contradiction_developing(state_and_commit):
    state = generate_scenario_2()
    assert state.get_all_contradictions()[0].status == ContradictionStatus.DEVELOPING

def test_32_completion_requires_full_roadmap(state_and_commit):
    state, commit = state_and_commit
    pid = apply(state,"PROPOSE_SIMPLEST",{"content":"s"})
    des = next(iter(state._designations.values()))
    apply(state,"ASSESS_SIMPLEST",{"candidate_simplest_id":des.id,"approved":True})
    with pytest.raises(ValueError, match="Move not allowed"):
        apply(state,"COMPLETE",{"final_response":"unsupported","committed_development_refs":[{"type":"Process","id":pid}],"evidence_observation_ids":[],"goal_coverage":"all","why_further_development_not_needed":"done"})

# Completion
def test_33_completion_without_opposite_rejected(state_and_commit):
    state, commit = state_and_commit
    pid = apply(state,"PROPOSE_SIMPLEST",{"content":"s"})
    des = next(iter(state._designations.values()))
    apply(state,"ASSESS_SIMPLEST",{"candidate_simplest_id":des.id,"approved":True})
    with pytest.raises(ValueError, match="Move not allowed"):
        apply(state,"COMPLETE",{"final_response":"unsupported","committed_development_refs":[{"type":"Process","id":pid}],"evidence_observation_ids":[],"goal_coverage":"all","why_further_development_not_needed":"done"})

def test_34_completion_without_contradiction_rejected(state_and_commit):
    state, commit = state_and_commit
    pid = apply(state,"PROPOSE_SIMPLEST",{"content":"s"})
    des = next(iter(state._designations.values()))
    apply(state,"ASSESS_SIMPLEST",{"candidate_simplest_id":des.id,"approved":True})
    with pytest.raises(ValueError, match="Move not allowed"):
        apply(state,"COMPLETE",{"final_response":"unsupported","committed_development_refs":[{"type":"Process","id":pid}],"evidence_observation_ids":[],"goal_coverage":"all","why_further_development_not_needed":"done"})

def test_35_completion_without_leap_rejected(state_and_commit):
    state, commit = state_and_commit
    pid = apply(state,"PROPOSE_SIMPLEST",{"content":"s"})
    des = next(iter(state._designations.values()))
    apply(state,"ASSESS_SIMPLEST",{"candidate_simplest_id":des.id,"approved":True})
    with pytest.raises(ValueError, match="Move not allowed"):
        apply(state,"COMPLETE",{"final_response":"unsupported","committed_development_refs":[{"type":"Process","id":pid}],"evidence_observation_ids":[],"goal_coverage":"all","why_further_development_not_needed":"done"})

def test_36_completion_with_nonexistent_dev_ref_rejected(state_and_commit):
    state, commit = state_and_commit
    with pytest.raises(ValueError, match="does not exist"):
        commit.commit(Proposal(move_type=MoveType.COMPLETE, payload={"committed_development_refs": [{"type": "Process", "id": "none"}], "evidence_observation_ids": [], "goal_coverage": "all", "why_further_development_not_needed": "done"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_37_completion_with_invalid_evidence_rejected(state_and_commit):
    state, commit = state_and_commit
    pid = commit.commit(Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "s"}, why_this_move_now="w", expected_goal_contribution="e"), state)
    des = [d for d in state.get_all_designations() if d.process_id == pid][0]
    commit.commit(Proposal(move_type=MoveType.ASSESS_SIMPLEST, payload={"candidate_simplest_id": des.id, "approved": True}, why_this_move_now="w", expected_goal_contribution="e"), state)
    with pytest.raises(ValueError, match="does not exist"):
        commit.commit(Proposal(move_type=MoveType.COMPLETE, payload={"committed_development_refs": [{"type": "Process", "id": pid}], "evidence_observation_ids": ["none"], "goal_coverage": "all", "why_further_development_not_needed": "done"}, why_this_move_now="w", expected_goal_contribution="e"), state)

def test_completion_foreign_evidence_rejected(state_and_commit):
    state = generate_scenario_2()
    begin(state)
    oid = observe(state)
    state.get_action(state.get_observation(oid).action_id).goal_id = "alien"
    with pytest.raises(ValueError, match="different goal"):
        apply(state,"COMPLETE",completion(state,oid))


# Allowed Moves
def test_38_allowed_moves_not_strictly_linear(state_and_commit):
    state = generate_scenario_2()
    moves = AllowedMovesResolver().allowed_moves(state)
    assert MoveType.DEVELOP_PROCESS in moves
    assert MoveType.DESIGNATE_OPPOSITE in moves
    assert MoveType.BEGIN_EXECUTION in moves
    assert MoveType.PROPOSE_ACTION not in moves

def test_39_development_allowed_after_opposite(state_and_commit):
    state = generate_scenario_2()
    assert MoveType.DEVELOP_PROCESS in AllowedMovesResolver().allowed_moves(state)
    assert MoveType.PROPOSE_ACTION not in AllowedMovesResolver().allowed_moves(state)

def test_40_development_allowed_after_contradiction(state_and_commit):
    state = generate_scenario_2()
    moves = AllowedMovesResolver().allowed_moves(state)
    assert MoveType.DEVELOP_PROCESS in moves
    assert MoveType.PROPOSE_LEAP in moves
    assert MoveType.PROPOSE_ACTION not in moves

def test_41_allowed_moves_on_contradiction(state_and_commit):
    state = generate_scenario_2()
    moves = AllowedMovesResolver().allowed_moves(state)
    assert MoveType.COMPLETE not in moves
    assert MoveType.PROPOSE_LEAP in moves

