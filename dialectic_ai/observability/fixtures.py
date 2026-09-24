from dialectic_ai.core.runtime import CommitLayer, DesignationRole, MoveType, Proposal, RuntimeState


def generate_scenario_1() -> RuntimeState:
    """A complete explicitly synthetic planning -> practice example for UI tests."""
    state = generate_scenario_2()
    state.get_active_goal().content = "Calculate revenue by month"
    commit = CommitLayer()
    def apply(move, payload):
        return commit.commit(Proposal(move_type=move, payload=payload,
                                      why_this_move_now="Fixture scenario", expected_goal_contribution="Fixture scenario"), state)
    simplest = next(d for d in state.get_all_designations() if d.role == DesignationRole.SIMPLEST)
    resolution = next(iter(state._resolution_relations.values()))
    apply(MoveType.BEGIN_EXECUTION, {"simplest_id": simplest.id,
        "contradiction_ids": [resolution.contradiction_id], "resolution_ids": [resolution.id],
        "execution_process_ids": [resolution.resolution_process_id]})
    aid = apply(MoveType.PROPOSE_ACTION, {"tool_name": "query_db", "args": {},
        "origin_ref": {"type": "Process", "id": resolution.resolution_process_id},
        "why_now": "Execute roadmap", "purpose": "Get data", "expectation": "Monthly list", "relation_to_goal": "Report"})
    oid = commit.create_observation(state, aid, {"Jan": 100, "Feb": 200}, True)
    apply(MoveType.ASSESS_PRACTICE, {"action_id": aid, "observation_id": oid,
        "expected_actual_relation": "confirmed", "explanation": "Expected data", "consequence_for_development": "Report ready"})
    apply(MoveType.ASSESS_LEAP, {"resolution_id": resolution.id, "observation_ids": [oid], "explanation": "Fixture only"})
    apply(MoveType.COMPLETE, {"final_response": "[FIXTURE] Jan: 100, Feb: 200", "goal_coverage": "Fixture only",
        "why_further_development_not_needed": "Fixture done", "committed_development_refs": [{"type": "Process", "id": resolution.resolution_process_id}],
        "evidence_observation_ids": [oid]})
    return state


def generate_scenario_2() -> RuntimeState:
    """
    Scenario 2:
    Goal -> Simplest -> Development -> Opposite -> Opposite Development -> Contradiction Unity -> Mediation -> further Development.
    """
    state = RuntimeState()
    commit = CommitLayer()
    
    from dialectic_ai.core.runtime import Goal
    goal = Goal(content="Resolve physics paradox")
    state._goals[goal.id] = goal
    
    # Simplest
    s_pid = commit.commit(Proposal(
        move_type=MoveType.PROPOSE_SIMPLEST, payload={"content": "Wave theory"},
        why_this_move_now="Start", expected_goal_contribution="Start"
    ), state)
    des = [d for d in state.get_all_designations() if d.process_id == s_pid][0]
    commit.commit(Proposal(
        move_type=MoveType.ASSESS_SIMPLEST, payload={"candidate_simplest_id": des.id, "approved": True},
        why_this_move_now="Approve", expected_goal_contribution="Approve"
    ), state)
    
    # Development
    dev1_pid = commit.commit(Proposal(
        move_type=MoveType.DEVELOP_PROCESS, payload={
            "source_process_id": s_pid, "emergent_content": "Continuous energy", "potential_containment": "c", "emergence": "e", "concretization": "c", "new_content": "n"
        }, why_this_move_now="dev", expected_goal_contribution="dev"
    ), state)
    
    # Opposite
    opid = commit.commit(Proposal(
        move_type=MoveType.DESIGNATE_OPPOSITE, payload={
            "simplest_id": des.id, "context_id": dev1_pid, "content": "Particle theory", "caught_from": "Energy exchanged in discrete amounts", "justification": "Discrete energy observed"
        }, why_this_move_now="dev", expected_goal_contribution="dev"
    ), state)
    
    # Opposite Development
    op_dev_pid = commit.commit(Proposal(
        move_type=MoveType.DEVELOP_PROCESS, payload={
            "source_process_id": opid, "emergent_content": "Quanta", "potential_containment": "c", "emergence": "e", "concretization": "c", "new_content": "n"
        }, why_this_move_now="dev", expected_goal_contribution="dev"
    ), state)
    
    dev1_rel = next(r.id for r in state.get_all_development_relations() if r.emergent_process_id == dev1_pid)
    op_dev_rel = next(r.id for r in state.get_all_development_relations() if r.emergent_process_id == op_dev_pid)
    
    # Contradiction
    simplest_des = des
    op1_id = opid
    op_des_id = next(d.id for d in state.get_all_designations() if d.process_id == op1_id and d.role == DesignationRole.OPPOSITE)
    con_id = commit.commit(Proposal(
        move_type=MoveType.ESTABLISH_CONTRADICTION,
        payload={
            "simplest_id": simplest_des.id,
            "opposite_id": op_des_id,
            "simplest_dev_ref_ids": [dev1_rel],
            "opposite_dev_ref_ids": [op_dev_rel],
            "unity_justification": "They are mutually exclusive yet form light.",
            "developing_unity_description": "Wave-particle duality"
        }, why_this_move_now="con", expected_goal_contribution="con"
    ), state)
    
    # Mediation (Resolution)
    commit.commit(Proposal(
        move_type=MoveType.PROPOSE_LEAP, payload={
            "contradiction_id": con_id,
            "resolution_content": "Quantum Mechanics",
            "resolution_outcome": "mediation",
            "opposite_acting_on_simplest": "Quanta act on the continuous wave picture",
            "how_preserves_simplest": "p",
            "how_preserves_opposite": "p"
        }, why_this_move_now="leap", expected_goal_contribution="leap"
    ), state)
    
    return state
