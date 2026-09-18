import pytest
from dialectic_ai.v1.graph import DialecticalProcessGraph, ExecutionGraph, GuardError
from dialectic_ai.v1.models import (
    ProcessInstance, DevelopmentTransition, OppositeRelation, Contradiction,
    GoalSufficiencyResult, SubCheckResult, Evidence, DialecticalRunState
)
from dialectic_ai.v1.state import (
    NodeStatus, TransitionStatus, OppositeStatus, ContradictionStatus, CheckStatus,
    RunState, DialecticalStatus, EvidenceSourceType, ActionContextLoop, GraphPosition
)
import dataclasses

def test_dpg_collections_are_not_publicly_mutable():
    dpg = DialecticalProcessGraph("g1", "tp1", "r1")
    
    with pytest.raises(AttributeError):
        dpg.edges.append(None) # tuple has no append
        
    with pytest.raises(TypeError):
        dpg.nodes["id"] = None # MappingProxyType does not support item assignment
        
    with pytest.raises(AttributeError):
        dpg.opposite_relations.append(None)
        
    with pytest.raises(AttributeError):
        dpg.contradictions.append(None)

def test_execution_graph_collections_are_not_publicly_mutable():
    suff = GoalSufficiencyResult(
        id="gs1", graph_id="g1", dialectical_status=DialecticalStatus.SEMANTIC_STOP,
        structural=SubCheckResult(CheckStatus.PASS, ""), capability=SubCheckResult(CheckStatus.PASS, ""),
        semantic=SubCheckResult(CheckStatus.PASS, ""), evidence=SubCheckResult(CheckStatus.NOT_APPLICABLE, ""),
        task_intersects_contradiction=True, relevant_process_ids=(), best_effort=False, rationale=""
    )
    eg = ExecutionGraph("eg1", "r1", suff)
    
    with pytest.raises(AttributeError):
        eg.edges.append(None)
        
    with pytest.raises(TypeError):
        eg.steps["id"] = None

def test_state_cannot_be_directly_reassigned():
    state = DialecticalRunState("r1", "req1", DialecticalStatus.IN_PROGRESS, None)
    
    with pytest.raises(AttributeError):
        state.current_state = RunState.COMPLETED

def test_invalid_state_transition_rejected():
    state = DialecticalRunState("r1", "req1", DialecticalStatus.IN_PROGRESS, None)
    
    with pytest.raises(GuardError, match="Illegal state transition"):
        state.transition_to(RunState.COMPLETED)

def test_semantic_stop_requires_contradiction():
    state = DialecticalRunState("r1", "req1", DialecticalStatus.SEMANTIC_STOP, None)
    state._current_state = RunState.EXECUTING # manually set for test to bypass init check
    
    dpg = DialecticalProcessGraph("g1", "tp1", "r1")
    # Empty DPG with no contradiction
    with pytest.raises(GuardError, match="SEMANTIC_STOP requires VALIDATED Contradiction"):
        state.transition_to(RunState.COMPLETED, dpg=dpg)

def test_evidence_is_immutable():
    ev = Evidence(
        source_type=EvidenceSourceType.TOOL_CALL,
        source_ref="ref1",
        content="test",
        schema=None,
        loop_context=ActionContextLoop.EXECUTION
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.content = "changed"

def test_execution_graph_cannot_use_fabricated_gate_id():
    # Attempting to initialize with a string should fail Type Hint or fail because it expects object
    with pytest.raises(AttributeError):
        ExecutionGraph("eg1", "r1", "fabricated_id")

def test_execution_graph_requires_is_sufficient():
    suff = GoalSufficiencyResult(
        id="gs1", graph_id="g1", dialectical_status=DialecticalStatus.SEMANTIC_STOP,
        structural=SubCheckResult(CheckStatus.FAIL, ""), capability=SubCheckResult(CheckStatus.PASS, ""),
        semantic=SubCheckResult(CheckStatus.PASS, ""), evidence=SubCheckResult(CheckStatus.NOT_APPLICABLE, ""),
        task_intersects_contradiction=True, relevant_process_ids=(), best_effort=False, rationale=""
    )
    
    with pytest.raises(GuardError, match="GUARD-03: Cannot construct ExecutionGraph if is_sufficient is False"):
        ExecutionGraph("eg1", "r1", suff)

def test_contradiction_requires_framework_derived_validated_opposite():
    dpg = DialecticalProcessGraph("g1", "tp1", "r1")
    with pytest.raises(GuardError, match="OppositeRelation not found"):
        dpg.derive_contradiction("or_unknown", "tension", True, True)

def test_empty_rationale_is_rejected():
    with pytest.raises(ValueError, match="emergence_rationale cannot be empty"):
        DevelopmentTransition("t1", "g1", "s1", "t2", "", "p", "d")
