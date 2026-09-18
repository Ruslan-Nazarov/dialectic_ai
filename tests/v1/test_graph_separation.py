import pytest
from dialectic_ai.v1.models import (
    DevelopmentTransition, ExecutionDependency, ExecutionDependencyType,
    GoalSufficiencyResult, SubCheckResult
)
from dialectic_ai.v1.state import TransitionStatus, DialecticalStatus, CheckStatus
from dialectic_ai.v1.graph import DialecticalProcessGraph, ExecutionGraph

def test_development_transition_cannot_be_inserted_into_execution_graph():
    suff = GoalSufficiencyResult(
        id="gs1", graph_id="g1", dialectical_status=DialecticalStatus.SEMANTIC_STOP,
        structural=SubCheckResult(CheckStatus.PASS, ""), capability=SubCheckResult(CheckStatus.PASS, ""),
        semantic=SubCheckResult(CheckStatus.PASS, ""), evidence=SubCheckResult(CheckStatus.NOT_APPLICABLE, ""),
        task_intersects_contradiction=True, relevant_process_ids=(), best_effort=False, rationale=""
    )
    eg = ExecutionGraph("eg1", "run1", suff)
    dt = DevelopmentTransition(
        id="dt1", graph_id="dpg1", source_id="p1", target_id="p2",
        emergence_rationale="e", potential_rationale="p", determinacy_rationale="d",
        status=TransitionStatus.VALIDATED
    )
    with pytest.raises(TypeError, match="GUARD-11"):
        eg.add_edge(dt) # type: ignore

def test_execution_dependency_cannot_be_inserted_into_dpg():
    dpg = DialecticalProcessGraph("dpg1", "tp1", "run1")
    ed = ExecutionDependency(
        id="ed1", graph_id="eg1", from_step_id="s1", to_step_id="s2",
        type=ExecutionDependencyType.DEPENDS_ON
    )
    with pytest.raises(TypeError, match="GUARD-10"):
        dpg.add_validated_transition(ed) # type: ignore
