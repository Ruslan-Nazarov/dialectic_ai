import pytest
from dialectic_ai.v1.models import (
    ProcessInstance, OppositeRelation, DialecticalRunState
)
from dialectic_ai.v1.state import (
    OppositeStatus, DialecticalStatus, RunState, GraphPosition, NodeStatus
)
from dialectic_ai.v1.graph import DialecticalProcessGraph, GuardError

def test_cannot_create_contradiction_without_opposite():
    dpg = DialecticalProcessGraph("g1", "tp1", "r1")
    with pytest.raises(GuardError, match="OppositeRelation not found"):
        dpg.derive_contradiction("or1", "tension", True, True)

def test_cannot_use_process_outside_graph_as_opposite():
    dpg = DialecticalProcessGraph("g1", "tp1", "run1")
    p0 = ProcessInstance("p0", "g1", "type1", {}, GraphPosition.ROOT, NodeStatus.VALIDATED)
    dpg.add_node(p0)
    
    opp = OppositeRelation(
        id="or1", graph_id="g1", simplest_process_id="p0",
        opposite_process_id="p2", # p2 is not in graph
        exclusion_claim="test", status=OppositeStatus.CANDIDATE
    )
    with pytest.raises(GuardError, match="OppositeProcess must originate from DPG development"):
        dpg.add_validated_opposite(opp)

def test_computational_stop_is_not_semantic_completion():
    state = DialecticalRunState(
        run_id="run1", request_id="req1",
        dialectical_status=DialecticalStatus.SEMANTIC_STOP,
        budget=None # type: ignore
    )
    state._current_state = RunState.EXECUTING
    dpg = DialecticalProcessGraph("g1", "tp1", "r1")
    
    # If it's a semantic stop but we don't have a validated contradiction, it should fail.
    with pytest.raises(GuardError, match="SEMANTIC_STOP requires VALIDATED Contradiction"):
        state.transition_to(RunState.COMPLETED, dpg=dpg)
