from typing import Optional
from dialectic_ai.v1.models import (
    Contradiction, OppositeRelation, GoalSufficiencyResult, DialecticalRunState
)
from dialectic_ai.v1.state import OppositeStatus, DialecticalStatus, SemanticStopReason, RunState
from dialectic_ai.v1.graph import GuardError

class GuardValidator:
    
    @staticmethod
    def enforce_guard_01(contradiction: Contradiction, opposite_relation: Optional[OppositeRelation]):
        """GUARD-01: Contradiction requires VALIDATED OppositeRelation"""
        if not opposite_relation:
            raise GuardError("GUARD-01: Cannot construct Contradiction without OppositeRelation")
        if opposite_relation.status != OppositeStatus.VALIDATED:
            raise GuardError("GUARD-01: Cannot construct Contradiction without VALIDATED OppositeRelation")
        if contradiction.opposite_relation_id != opposite_relation.id:
            raise GuardError("GUARD-01: Contradiction ID mismatch with OppositeRelation")

    @staticmethod
    def enforce_guard_03(sufficiency_result: Optional[GoalSufficiencyResult]):
        """GUARD-03: ExecutionGraph requires GoalSufficiencyResult.is_sufficient=True"""
        if not sufficiency_result:
            raise GuardError("GUARD-03: Cannot construct ExecutionGraph without GoalSufficiencyResult")
        if not sufficiency_result.is_sufficient:
            raise GuardError("GUARD-03: Cannot construct ExecutionGraph if is_sufficient is False")

    @staticmethod
    def enforce_guard_07(run_state: DialecticalRunState, has_validated_contradiction: bool):
        """GUARD-07: SEMANTIC_STOP requires VALIDATED Contradiction"""
        if run_state.dialectical_status == DialecticalStatus.SEMANTIC_STOP:
            if not has_validated_contradiction:
                raise GuardError("GUARD-07: SEMANTIC_STOP cannot be declared without a VALIDATED Contradiction")

    @staticmethod
    def enforce_guard_14():
        """GUARD-14: Agents submit proposals only; no direct graph mutation"""
        # Enforced structurally by the runtime passing immutable copies or controlling the graph.
        pass
        
    @staticmethod
    def enforce_guard_15():
        """GUARD-15: Semantic objects reference Evidence by ID; no content copying"""
        # Enforced by the dataclass schemas (List[str] for evidence_ids)
        pass

    @staticmethod
    def enforce_state_transition(current: RunState, next_state: RunState):
        """Prevents illegal state jumps."""
        illegal_transitions = [
            (RunState.NORMALIZING_TARGET, RunState.EXECUTING),
            (RunState.DEVELOPING, RunState.COMPLETED),
        ]
        if (current, next_state) in illegal_transitions:
            raise GuardError(f"Illegal state transition from {current.name} to {next_state.name}")
