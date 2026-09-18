import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union
from dialectic_ai.v1.state import (
    RunState, DialecticalStatus, SemanticStopReason, ComputationalStopReason, RunOutcome, GraphPosition,
    NodeStatus, TransitionStatus, OppositeStatus, ContradictionStatus,
    CheckStatus, EvidenceSourceType, EvidenceLinkType, ActionContextLoop,
    ExecutionDependencyType
)

@dataclass(frozen=True)
class RuntimeBudget:
    max_iterations: int = 10

@dataclass(frozen=True)
class TargetProcess:
    id: str
    request_id: str
    description: str
    goal_state: str
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass(frozen=True)
class ProcessType:
    id: str
    canonical_name: str
    description: str
    source: str
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass(frozen=True)
class ProcessInstance:
    id: str
    graph_id: str
    type_ref: str
    context: Dict[str, Any]
    graph_position: GraphPosition
    status: NodeStatus
    determinacy: Optional[str] = None
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass(frozen=True)
class DevelopmentTransition:
    id: str
    graph_id: str
    source_id: str
    target_id: str
    emergence_rationale: str
    potential_rationale: str
    determinacy_rationale: str
    status: TransitionStatus = TransitionStatus.PROPOSED
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    def __post_init__(self):
        if not self.emergence_rationale:
            raise ValueError("emergence_rationale cannot be empty")
        if not self.potential_rationale:
            raise ValueError("potential_rationale cannot be empty")
        if not self.determinacy_rationale:
            raise ValueError("determinacy_rationale cannot be empty")

@dataclass(frozen=True)
class OppositeRelation:
    id: str
    graph_id: str
    simplest_process_id: str
    opposite_process_id: str
    exclusion_claim: str
    status: OppositeStatus = OppositeStatus.CANDIDATE
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass(frozen=True)
class Contradiction:
    id: str
    graph_id: str
    opposite_relation_id: str
    simplest_process_id: str
    opposite_process_id: str
    tension_description: str
    is_relevant_to_target: bool
    is_blocking: bool
    status: ContradictionStatus = ContradictionStatus.CANDIDATE
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass(frozen=True)
class SubCheckResult:
    status: CheckStatus
    reason: str
    evidence: tuple[str, ...] = field(default_factory=tuple)

@dataclass(frozen=True)
class GoalSufficiencyResult:
    id: str
    graph_id: str
    dialectical_status: DialecticalStatus
    structural: SubCheckResult
    capability: SubCheckResult
    semantic: SubCheckResult
    evidence: SubCheckResult
    task_intersects_contradiction: bool
    relevant_process_ids: tuple[str, ...]
    best_effort: bool
    rationale: str
    evaluated_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    @property
    def is_sufficient(self) -> bool:
        applicable = [
            c for c in [self.structural, self.capability, self.semantic, self.evidence]
            if c.status != CheckStatus.NOT_APPLICABLE
        ]
        if not applicable:
            return False
        return all(c.status == CheckStatus.PASS for c in applicable) and not any(c.status == CheckStatus.FAIL for c in applicable)

@dataclass(frozen=True)
class CapabilityRequirement:
    id: str
    derived_from: str
    name: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass(frozen=True)
class ExecutionBinding:
    id: str
    capability_id: str
    executor_type: str
    executor_ref: str
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass(frozen=True)
class ExecutionStep:
    id: str
    execution_graph_id: str
    capability_id: str
    binding_id: str
    status: str
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass(frozen=True)
class ExecutionDependency:
    id: str
    graph_id: str
    from_step_id: str
    to_step_id: str
    type: ExecutionDependencyType

@dataclass(frozen=True)
class Evidence:
    source_type: EvidenceSourceType
    source_ref: str
    content: Any
    schema: Optional[Dict[str, Any]]
    loop_context: ActionContextLoop
    id: str = field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:8]}")
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass
class DialecticalRunState:
    run_id: str
    request_id: str
    dialectical_status: DialecticalStatus
    budget: RuntimeBudget
    _current_state: RunState = field(default=RunState.INIT)
    target_process_id: Optional[str] = None
    dpg_id: Optional[str] = None
    sufficiency_result_id: Optional[str] = None
    execution_graph_id: Optional[str] = None
    stop_reason: Any = None
    started_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    @property
    def current_state(self) -> RunState:
        return self._current_state
        
    def transition_to(self, next_state: RunState, dpg=None):
        from dialectic_ai.v1.graph import GuardError
        allowed = {
            RunState.INIT: [RunState.NORMALIZING_TARGET, RunState.FAILED],
            RunState.NORMALIZING_TARGET: [RunState.FINDING_SIMPLEST, RunState.FAILED],
            RunState.FINDING_SIMPLEST: [RunState.DEVELOPING, RunState.FAILED],
            RunState.DEVELOPING: [RunState.CHECKING_OPPOSITE, RunState.CHECKING_SUFFICIENCY, RunState.COMPLETED, RunState.FAILED, RunState.INCOMPLETE],
            RunState.CHECKING_OPPOSITE: [RunState.COMPUTING_BLOCKING_SET, RunState.CHECKING_SUFFICIENCY, RunState.DEVELOPING, RunState.FAILED, RunState.INCOMPLETE],
            RunState.COMPUTING_BLOCKING_SET: [RunState.CHECKING_SUFFICIENCY, RunState.FAILED],
            RunState.CHECKING_SUFFICIENCY: [RunState.EXECUTION_PLANNING, RunState.COMPLETED, RunState.FAILED, RunState.INCOMPLETE],
            RunState.EXECUTION_PLANNING: [RunState.EXECUTING, RunState.FAILED],
            RunState.EXECUTING: [RunState.COMPLETED, RunState.FAILED],
            RunState.COMPLETED: [],
            RunState.FAILED: [],
            RunState.INCOMPLETE: [],
        }
        if next_state not in allowed[self._current_state]:
            raise GuardError(f"Illegal state transition from {self._current_state.name} to {next_state.name}")
            
        if next_state == RunState.COMPLETED and self.dialectical_status == DialecticalStatus.SEMANTIC_STOP:
            if not dpg or not dpg.contradictions:
                raise GuardError("GUARD-07: SEMANTIC_STOP requires VALIDATED Contradiction in DPG")
                
        self._current_state = next_state

@dataclass(frozen=True)
class DialecticalRunResult:
    id: str
    run_id: str
    outcome: RunOutcome
    dialectical_status: DialecticalStatus
    answer: Optional[str] = None
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
