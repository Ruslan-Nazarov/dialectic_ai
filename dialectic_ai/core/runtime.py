import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


def is_valid_str(val: Any) -> bool:
    return isinstance(val, str) and bool(val.strip())

from pydantic import BaseModel, Field


class RuntimeEvent(BaseModel):
    event_type: str
    proposal: Optional[Any] = None
    validation_error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class DesignationRole(str, Enum):
    CANDIDATE_SIMPLEST = "candidate_simplest"
    SIMPLEST = "simplest"
    OPPOSITE = "opposite"

class ContradictionStatus(str, Enum):
    DEVELOPING = "developing"
    RESOLVED = "resolved"

class ResolutionOutcome(str, Enum):
    REPLACEMENT = "replacement"
    MEDIATION = "mediation"

class MoveType(str, Enum):
    PROPOSE_SIMPLEST = "PROPOSE_SIMPLEST"
    ASSESS_SIMPLEST = "ASSESS_SIMPLEST"
    DEVELOP_PROCESS = "DEVELOP_PROCESS"
    CONNECT_DEVELOPMENT = "CONNECT_DEVELOPMENT"
    PROPOSE_ACTION = "PROPOSE_ACTION"
    ASSESS_PRACTICE = "ASSESS_PRACTICE"
    DESIGNATE_OPPOSITE = "DESIGNATE_OPPOSITE"
    ESTABLISH_CONTRADICTION = "ESTABLISH_CONTRADICTION"
    PROPOSE_LEAP = "PROPOSE_LEAP"
    BEGIN_EXECUTION = "BEGIN_EXECUTION"
    REVISE_WORLD = "REVISE_WORLD"
    ASSESS_LEAP = "ASSESS_LEAP"
    COMPLETE = "COMPLETE"
    REPORT_CONTRADICTION = "REPORT_CONTRADICTION"


@dataclass(kw_only=True)
class Goal:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    active: bool = True

@dataclass(kw_only=True)
class Process:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    status: str = "active"

@dataclass(kw_only=True)
class DevelopmentRelation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_process_id: str = ""
    emergent_process_id: str = ""
    potential_containment: str = ""
    emergence: str = ""
    concretization: str = ""
    new_content: str = ""

@dataclass(kw_only=True)
class DialecticalDesignation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    process_id: str = ""
    role: DesignationRole = DesignationRole.CANDIDATE_SIMPLEST
    goal_id: str = ""
    context_id: Optional[str] = None
    simplest_id: Optional[str] = None
    justification: Optional[str] = None

@dataclass(kw_only=True)
class RuntimeReference:
    type: Literal["Process", "DevelopmentRelation", "Contradiction", "PracticeAssessment"]
    id: str

@dataclass(kw_only=True)
class Action:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str = ""
    tool_name: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    origin_ref: RuntimeReference = field(default_factory=lambda: RuntimeReference(type="Process", id=""))
    why_now: str = ""
    purpose: str = ""
    relation_to_goal: str = ""
    expectation: str = ""
    status: str = "pending"
    roadmap_id: Optional[str] = None

@dataclass(kw_only=True)
class Observation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    raw_result: Any = None
    success: bool = True
    error: Optional[str] = None

@dataclass(kw_only=True)
class PracticeAssessment:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    observation_id: str = ""
    expected_actual_relation: Literal["confirmed", "partially_confirmed", "contradicted", "inconclusive"] = "confirmed"
    explanation: str = ""
    consequence_for_development: str = ""

@dataclass(kw_only=True)
class Contradiction:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    simplest_id: str = ""
    opposite_id: str = ""
    simplest_dev_ref_ids: List[str] = field(default_factory=list)
    opposite_dev_ref_ids: List[str] = field(default_factory=list)
    unity_justification: str = ""
    developing_unity_description: str = ""
    status: ContradictionStatus = ContradictionStatus.DEVELOPING

@dataclass(kw_only=True)
class ResolutionRelation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    contradiction_id: str = ""
    resolution_process_id: str = ""
    outcome: ResolutionOutcome = ResolutionOutcome.REPLACEMENT
    confirmed_roadmap_id: Optional[str] = None
    evidence_observation_ids: List[str] = field(default_factory=list)
    practice_explanation: str = ""

@dataclass(kw_only=True)
class Completion:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str = ""
    final_response: str = ""
    committed_development_refs: List[RuntimeReference] = field(default_factory=list)
    evidence_observation_ids: List[str] = field(default_factory=list)
    goal_coverage: str = ""
    why_further_development_not_needed: str = ""

@dataclass(kw_only=True)
class UnresolvedReport:
    """An honest end to a run whose practice kept contradicting the plan: which source is
    unreliable, the observations showing it, and only an answer independent evidence supports."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str = ""
    contested_source: str = ""
    contradicting_observation_ids: List[str] = field(default_factory=list)
    supported_answer: Optional[str] = None
    supporting_observation_ids: List[str] = field(default_factory=list)
    final_response: str = ""

@dataclass(kw_only=True)
class Proposal:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    move_type: MoveType
    payload: Dict[str, Any] = field(default_factory=dict)
    why_this_move_now: str = ""
    expected_goal_contribution: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass(kw_only=True)
class DirectionSnapshot:
    goal_id: str
    active_frontier_process_ids: List[str]
    pending_action_ids: List[str]
    active_contradiction_ids: List[str]


class RuntimeState:
    def __init__(self):
        self._goals: Dict[str, Goal] = {}
        self._processes: Dict[str, Process] = {}
        self._development_relations: Dict[str, DevelopmentRelation] = {}
        self._designations: Dict[str, DialecticalDesignation] = {}
        self._actions: Dict[str, Action] = {}
        self._observations: Dict[str, Observation] = {}
        self._practice_assessments: Dict[str, PracticeAssessment] = {}
        self._contradictions: Dict[str, Contradiction] = {}
        self._resolution_relations: Dict[str, ResolutionRelation] = {}
        self._completions: Dict[str, Completion] = {}
        self._unresolved_reports: Dict[str, UnresolvedReport] = {}
        
        self._provisional_owners: Dict[str, str] = {}
        self._trace: List[Any] = []
        self.phase = "planning"
        self.active_roadmap_id = None
        self._roadmaps = {}
        self._revision_observation_ids = []
        self._revision_reason = ""

    def get_active_goal(self) -> Optional[Goal]:
        for g in self._goals.values():
            if g.active:
                return g
        return None
    
    def get_process(self, id: str) -> Optional[Process]: return self._processes.get(id)
    def get_action(self, id: str) -> Optional[Action]: return self._actions.get(id)
    def get_observation(self, id: str) -> Optional[Observation]: return self._observations.get(id)
    def get_designation(self, id: str) -> Optional[DialecticalDesignation]: return self._designations.get(id)
    def get_contradiction(self, id: str) -> Optional[Contradiction]: return self._contradictions.get(id)
    def get_development_relation(self, id: str) -> Optional[DevelopmentRelation]: return self._development_relations.get(id)
    def get_completion(self, id: str) -> Optional[Completion]: return self._completions.get(id)

    def get_all_processes(self) -> List[Process]: return list(self._processes.values())
    def get_all_development_relations(self) -> List[DevelopmentRelation]: return list(self._development_relations.values())
    def get_all_designations(self) -> List[DialecticalDesignation]: return list(self._designations.values())
    def get_all_actions(self) -> List[Action]: return list(self._actions.values())
    def get_all_observations(self) -> List[Observation]: return list(self._observations.values())
    def get_all_contradictions(self) -> List[Contradiction]: return list(self._contradictions.values())
    
    def is_committed(self, entity_id: str) -> bool:
        exists = any(entity_id in collection for collection in (self._processes, self._development_relations, self._designations, self._actions, self._observations, self._practice_assessments, self._contradictions, self._resolution_relations, self._completions))
        return exists and entity_id not in self._provisional_owners

    def get_provisional_owner(self, entity_id: str) -> Optional[str]:
        return self._provisional_owners.get(entity_id)

    def get_entity_by_ref(self, ref: RuntimeReference) -> Any:
        if ref.type == "Process":
            return self._processes.get(ref.id)
        elif ref.type == "DevelopmentRelation":
            return self._development_relations.get(ref.id)
        elif ref.type == "Contradiction":
            return self._contradictions.get(ref.id)
        elif ref.type == "PracticeAssessment":
            return self._practice_assessments.get(ref.id)
        return None
        
    def belongs_to_development_line(self, root_process_id: str, relation_id: str) -> bool:
        rel = self.get_development_relation(relation_id)
        if not rel:
            return False
        
        visited = set()
        stack = [rel.source_process_id]
        while stack:
            curr = stack.pop()
            if curr == root_process_id:
                return True
            if curr in visited:
                continue
            visited.add(curr)
            for r in self.get_all_development_relations():
                if r.emergent_process_id == curr:
                    stack.append(r.source_process_id)
        return False
        
    def is_process_in_goal_structure(self, process_id: str, goal_id: str) -> bool:
        roots = {d.process_id for d in self.get_all_designations() if d.goal_id == goal_id}
        for resolution in self._resolution_relations.values():
            contradiction = self.get_contradiction(resolution.contradiction_id)
            designation = self.get_designation(contradiction.simplest_id) if contradiction else None
            if designation and designation.goal_id == goal_id:
                roots.add(resolution.resolution_process_id)
        seen, pending = set(), [process_id]
        while pending:
            current = pending.pop()
            if current in roots:
                return True
            if current in seen:
                continue
            seen.add(current)
            pending.extend(r.source_process_id for r in self.get_all_development_relations() if r.emergent_process_id == current)
        return False

    def ref_belongs_to_goal(self, ref: RuntimeReference, goal_id: str) -> bool:
        entity = self.get_entity_by_ref(ref)
        if entity is None:
            return False
        if ref.type == "Process":
            return self.is_process_in_goal_structure(ref.id, goal_id)
        if ref.type == "DevelopmentRelation":
            return self.is_process_in_goal_structure(entity.source_process_id, goal_id)
        if ref.type == "Contradiction":
            designation = self.get_designation(entity.simplest_id)
            return bool(designation and designation.goal_id == goal_id)
        if ref.type == "PracticeAssessment":
            action = self.get_action(entity.action_id)
            return bool(action and action.goal_id == goal_id)
        return False

    def get_recent_feedback(self) -> Optional[Dict[str, Any]]:
        # Returns structured public feedback about the last rejection, if it was the last event
        if not self._trace:
            return None
        last_event = self._trace[-1]
        if getattr(last_event, "event_type", "") != "proposal_rejected":
            return None
        return {
            "rejection_type": "move_not_allowed" if "not allowed in current state" in getattr(last_event, "validation_error", "") else "validation_failed",
            "move_type": getattr(last_event.proposal.move_type, "name", "UNKNOWN") if getattr(last_event, "proposal", None) and hasattr(last_event.proposal, "move_type") else "UNKNOWN",
            "reason": getattr(last_event, "validation_error", "Unknown reason")
        }


class StructuralValidator:
    def validate(self, proposal: Proposal, state: RuntimeState) -> tuple[bool, Optional[str]]:
        try:
            if not is_valid_str(proposal.why_this_move_now) or not is_valid_str(proposal.expected_goal_contribution):
                return False, "Proposal missing rationale"
                
            if not isinstance(proposal.move_type, MoveType) or not isinstance(proposal.payload, dict):
                return False, "Invalid proposal type or payload"
            active_goal = state.get_active_goal()
            
            if proposal.move_type == MoveType.PROPOSE_SIMPLEST:
                if not active_goal:
                    return False, "PROPOSE_SIMPLEST requires active Goal"
                if not is_valid_str(proposal.payload.get("content")):
                    return False, "PROPOSE_SIMPLEST requires 'content'"
                
            elif proposal.move_type == MoveType.ASSESS_SIMPLEST:
                candidate_id = proposal.payload.get("candidate_simplest_id")
                des = state.get_designation(candidate_id)
                if not des or des.role != DesignationRole.CANDIDATE_SIMPLEST:
                    return False, "Candidate simplest designation not found or invalid"
                
            elif proposal.move_type in (MoveType.DEVELOP_PROCESS, MoveType.CONNECT_DEVELOPMENT):
                source_id = proposal.payload.get("source_process_id")
                source = state.get_process(source_id)
                if not source:
                    return False, "Source process does not exist"
                if source.status != "active":
                    return False, "Source process is not active"
                
                if not state.is_process_in_goal_structure(source_id, active_goal.id):
                    return False, "Source process does not belong to active goal"
                # Check provisional context
                if not state.is_committed(source_id):
                    state.get_provisional_owner(source_id)
                    # If this move comes from an ongoing assessment, the context must match? 
                    # Actually, we don't have proposal owner. But we must assure we don't cross candidates.
                    # As a structural rule: allowed if source is not superseded, we just inherit context.
                
                if proposal.move_type == MoveType.CONNECT_DEVELOPMENT:
                    emergent_id = proposal.payload.get("emergent_process_id")
                    seen, pending = set(), [source_id]
                    while pending:
                        current = pending.pop()
                        if current == emergent_id:
                            return False, "Development relation would create a cycle"
                        if current in seen:
                            continue
                        seen.add(current)
                        pending.extend(r.source_process_id for r in state.get_all_development_relations() if r.emergent_process_id == current)
                    if source_id == emergent_id:
                        return False, "Development cannot connect a process to itself"
                    if state.get_provisional_owner(source_id) != state.get_provisional_owner(emergent_id):
                        return False, "Cannot connect different provisional contexts"
                    if not state.get_process(emergent_id):
                        return False, "Emergent process does not exist"
                        
                else:
                    if not is_valid_str(proposal.payload.get("emergent_content")):
                        return False, "Missing emergent content"

                for k in ["potential_containment", "emergence", "concretization", "new_content"]:
                    if not is_valid_str(proposal.payload.get(k)):
                        return False, f"Missing {k}"
                
            elif proposal.move_type == MoveType.PROPOSE_ACTION:
                if not active_goal:
                    return False, "PROPOSE_ACTION requires active Goal"
                origin_dict = proposal.payload.get("origin_ref")
                if not origin_dict:
                    return False, "Missing origin_ref"
                origin_ref = RuntimeReference(**origin_dict)
                if not state.get_entity_by_ref(origin_ref):
                    return False, "Action origin reference does not exist"
                
                if not state.ref_belongs_to_goal(origin_ref, active_goal.id):
                    return False, "Action origin belongs to a different goal"
                origin = state.get_entity_by_ref(origin_ref)
                if getattr(origin, "status", "active") == "superseded":
                    return False, "Action origin was superseded"
                for k in ["tool_name", "expectation", "why_now", "purpose", "relation_to_goal"]:
                    if not is_valid_str(proposal.payload.get(k)):
                        return False, f"Missing {k}"
                
            elif proposal.move_type == MoveType.ASSESS_PRACTICE:
                action_id = proposal.payload.get("action_id")
                observation_id = proposal.payload.get("observation_id")
                a = state.get_action(action_id)
                o = state.get_observation(observation_id)
                if not a:
                    return False, "Action does not exist"
                if not o:
                    return False, "Observation does not exist"
                if a.goal_id != active_goal.id:
                    return False, "Action belongs to a different goal"
                if any(pa.observation_id == observation_id for pa in state._practice_assessments.values()):
                    return False, "Observation has already been assessed"
                if not o.success and proposal.payload.get("expected_actual_relation") == "confirmed":
                    return False, "A failed tool execution cannot confirm its expectation"
                if o.action_id != action_id:
                    return False, "Observation does not belong to the specified Action"
                
            elif proposal.move_type == MoveType.DESIGNATE_OPPOSITE:
                if not active_goal:
                    return False, "DESIGNATE_OPPOSITE requires active Goal"
                simplest_id = proposal.payload.get("simplest_id")
                context_id = proposal.payload.get("context_id")
                simplest_des = state.get_designation(simplest_id)
                if not simplest_des or simplest_des.role != DesignationRole.SIMPLEST:
                    return False, "Invalid simplest_id"
                if not state.get_process(context_id) and not state.get_development_relation(context_id):
                    return False, "Development context_id does not exist"
                if not state.is_committed(context_id):
                    return False, "Development context is not committed"
                context_type = "Process" if state.get_process(context_id) else "DevelopmentRelation"
                if simplest_des.goal_id != active_goal.id or not state.ref_belongs_to_goal(RuntimeReference(type=context_type, id=context_id), active_goal.id):
                    return False, "Opposite context belongs to a different goal"
                if not is_valid_str(proposal.payload.get("content")) or not is_valid_str(proposal.payload.get("justification")):
                    return False, "DESIGNATE_OPPOSITE requires content and justification"
                    
            elif proposal.move_type == MoveType.ESTABLISH_CONTRADICTION:
                simplest_id = proposal.payload.get("simplest_id")
                opposite_id = proposal.payload.get("opposite_id")
                simplest_des = state.get_designation(simplest_id)
                opposite_des = state.get_designation(opposite_id)
                
                if not simplest_des or simplest_des.role != DesignationRole.SIMPLEST:
                    return False, "Invalid simplest_id"
                if not opposite_des or opposite_des.role != DesignationRole.OPPOSITE:
                    return False, "Invalid opposite_id"
                
                if opposite_des.simplest_id != simplest_id or simplest_des.goal_id != active_goal.id or opposite_des.goal_id != active_goal.id:
                    return False, "Opposite and simplest must belong to the same goal and pair"
                for ref_id in proposal.payload.get("simplest_dev_ref_ids", []):
                    if not state.is_committed(ref_id):
                        return False, f"simplest dev ref {ref_id} is not committed"
                    if not state.belongs_to_development_line(simplest_des.process_id, ref_id):
                        return False, f"simplest dev ref {ref_id} does not belong to simplest development line"
                        
                for ref_id in proposal.payload.get("opposite_dev_ref_ids", []):
                    if not state.is_committed(ref_id):
                        return False, f"opposite dev ref {ref_id} is not committed"
                    if not state.belongs_to_development_line(opposite_des.process_id, ref_id):
                        return False, f"opposite dev ref {ref_id} does not belong to opposite development line"
                        
                if not is_valid_str(proposal.payload.get("unity_justification")) or not is_valid_str(proposal.payload.get("developing_unity_description")):
                    return False, "ESTABLISH_CONTRADICTION missing semantic justifications"
                    
            elif proposal.move_type == MoveType.PROPOSE_LEAP:
                contradiction_id = proposal.payload.get("contradiction_id")
                c = state.get_contradiction(contradiction_id)
                if not c:
                    return False, "Contradiction does not exist"
                if not state.ref_belongs_to_goal(RuntimeReference(type="Contradiction", id=c.id), active_goal.id):
                    return False, "Contradiction belongs to a different goal"
                if c.status != ContradictionStatus.DEVELOPING:
                    return False, "Contradiction is not DEVELOPING"
                if proposal.payload.get("resolution_outcome") not in [ResolutionOutcome.REPLACEMENT.value, ResolutionOutcome.MEDIATION.value]:
                    return False, "Invalid resolution_outcome"
                if not is_valid_str(proposal.payload.get("resolution_content")):
                    return False, "PROPOSE_LEAP requires resolution_content"
                    
            elif proposal.move_type == MoveType.COMPLETE:
                goal = state.get_active_goal()
                if not goal:
                    return False, "No active goal"
                for ref_dict in proposal.payload.get("committed_development_refs", []):
                    ref = RuntimeReference(**ref_dict)
                    if not state.get_entity_by_ref(ref):
                        # Say what was wrong and what would be valid: the bare message left the model
                        # resubmitting refs of the wrong type (7 such rejections in live traces).
                        other = [t for t in ("Process", "DevelopmentRelation", "Contradiction", "PracticeAssessment")
                                 if t != ref.type and state.get_entity_by_ref(RuntimeReference(type=t, id=ref.id))]
                        if other:
                            return False, (f"Development ref {ref.id} is a {other[0]}, not a {ref.type}; "
                                           f"use type '{other[0]}'")
                        processes = [p.id for p in state.get_all_processes()
                                     if state.is_committed(p.id) and state.ref_belongs_to_goal(
                                         RuntimeReference(type="Process", id=p.id), goal.id)]
                        return False, (f"Development ref {ref.type} {ref.id} does not exist. Committed processes "
                                       f"of this goal you can cite: {processes}")
                    if not state.is_committed(ref.id):
                        return False, f"Development ref {ref} is not committed"
                    # Check goal ownership
                    if not state.ref_belongs_to_goal(ref, goal.id):
                        return False, f"Development ref {ref} does not belong to active goal structure"
                        
                for obs_id in proposal.payload.get("evidence_observation_ids", []):
                    o = state.get_observation(obs_id)
                    if not o:
                        return False, f"Observation {obs_id} does not exist"
                    a = state.get_action(o.action_id)
                    if not a:
                        return False, f"Observation {obs_id} does not have a valid action provenance"
                    if a.goal_id != goal.id:
                        return False, f"Observation {obs_id} belongs to a different goal"
                        
                if not is_valid_str(proposal.payload.get("final_response")):
                    return False, "COMPLETE requires a nonempty final_response"
                if not proposal.payload.get("committed_development_refs"):
                    return False, "COMPLETE requires committed development references"
                if any(a.status == "pending" for a in state.get_all_actions()):
                    return False, "COMPLETE cannot skip pending actions"
                assessed = {p.observation_id for p in state._practice_assessments.values()}
                if any(o.id not in assessed for o in state.get_all_observations()):
                    return False, "COMPLETE cannot skip practice assessment"
                if not is_valid_str(proposal.payload.get("goal_coverage")) or not is_valid_str(proposal.payload.get("why_further_development_not_needed")):
                    return False, "COMPLETE missing required semantic justifications"
            
            from dialectic_ai.core.proposal_schema import validate_payload
            validate_payload(proposal.move_type.value, proposal.payload)
            from dialectic_ai.core.world import validate_world
            validate_world(proposal, state)
            if proposal.move_type not in AllowedMovesResolver().allowed_moves(state):
                return False, "Move not allowed in current state"
            return True, None
        except Exception as e:
            return False, str(e)


class CommitLayer:
    def commit(self, proposal: Proposal, state: RuntimeState) -> Optional[str]:
        validator = StructuralValidator()
        is_valid, err = validator.validate(proposal, state)
        if not is_valid:
            raise ValueError(f"Proposal validation failed: {err}")
            
        if proposal.move_type in (MoveType.BEGIN_EXECUTION, MoveType.REVISE_WORLD, MoveType.ASSESS_LEAP):
            from dialectic_ai.core.world import commit_world
            result_id = commit_world(proposal, state)
            state._trace.append(proposal)
            return result_id

        entities_to_insert = []
        updates = []
        result_id = None
        
        # Prepare mutations
        if proposal.move_type == MoveType.PROPOSE_SIMPLEST:
            p = Process(content=proposal.payload["content"])
            d = DialecticalDesignation(process_id=p.id, role=DesignationRole.CANDIDATE_SIMPLEST, goal_id=state.get_active_goal().id)
            entities_to_insert.append((state._processes, p.id, p))
            entities_to_insert.append((state._designations, d.id, d))
            entities_to_insert.append((state._provisional_owners, p.id, d.id))
            entities_to_insert.append((state._provisional_owners, d.id, d.id))
            result_id = p.id
            
        elif proposal.move_type == MoveType.ASSESS_SIMPLEST:
            candidate_id = proposal.payload["candidate_simplest_id"]
            approved = proposal.payload["approved"]
            d = state.get_designation(candidate_id)
            if approved:
                def do_update():
                    d.role = DesignationRole.SIMPLEST
                    # Remove only provisional entities owned by this candidate
                    to_remove = [k for k, v in state._provisional_owners.items() if v == candidate_id]
                    for k in to_remove:
                        del state._provisional_owners[k]
                updates.append(do_update)
            else:
                def do_reject():
                    for pid, owner in state._provisional_owners.items():
                        if owner == candidate_id and pid in state._processes:
                            state._processes[pid].status = "superseded"
                    if candidate_id in state._designations:
                        del state._designations[candidate_id]
                updates.append(do_reject)
            result_id = candidate_id
            
        elif proposal.move_type == MoveType.DEVELOP_PROCESS:
            source_id = proposal.payload["source_process_id"]
            p = Process(content=proposal.payload["emergent_content"])
            dr = DevelopmentRelation(
                source_process_id=source_id,
                emergent_process_id=p.id,
                potential_containment=proposal.payload["potential_containment"],
                emergence=proposal.payload["emergence"],
                concretization=proposal.payload["concretization"],
                new_content=proposal.payload["new_content"],
            )
            entities_to_insert.append((state._processes, p.id, p))
            entities_to_insert.append((state._development_relations, dr.id, dr))
            
            if not state.is_committed(source_id):
                owner = state.get_provisional_owner(source_id)
                entities_to_insert.append((state._provisional_owners, p.id, owner))
                entities_to_insert.append((state._provisional_owners, dr.id, owner))
            result_id = p.id
            
        elif proposal.move_type == MoveType.CONNECT_DEVELOPMENT:
            dr = DevelopmentRelation(
                source_process_id=proposal.payload["source_process_id"],
                emergent_process_id=proposal.payload["emergent_process_id"],
                potential_containment=proposal.payload["potential_containment"],
                emergence=proposal.payload["emergence"],
                concretization=proposal.payload["concretization"],
                new_content=proposal.payload["new_content"],
            )
            entities_to_insert.append((state._development_relations, dr.id, dr))
            
            if not state.is_committed(proposal.payload["source_process_id"]):
                owner = state.get_provisional_owner(proposal.payload["source_process_id"])
                entities_to_insert.append((state._provisional_owners, dr.id, owner))
            result_id = dr.id
            
        elif proposal.move_type == MoveType.PROPOSE_ACTION:
            origin_ref = RuntimeReference(**proposal.payload["origin_ref"])
            a = Action(
                goal_id=state.get_active_goal().id,
                roadmap_id=state.active_roadmap_id,
                tool_name=proposal.payload["tool_name"],
                args=proposal.payload.get("args", {}),
                origin_ref=origin_ref,
                why_now=proposal.payload["why_now"],
                purpose=proposal.payload["purpose"],
                relation_to_goal=proposal.payload["relation_to_goal"],
                expectation=proposal.payload["expectation"],
            )
            entities_to_insert.append((state._actions, a.id, a))
            result_id = a.id
            
        elif proposal.move_type == MoveType.ASSESS_PRACTICE:
            pa = PracticeAssessment(
                action_id=proposal.payload["action_id"],
                observation_id=proposal.payload["observation_id"],
                expected_actual_relation=proposal.payload.get("expected_actual_relation", "confirmed"),
                explanation=proposal.payload.get("explanation", ""),
                consequence_for_development=proposal.payload.get("consequence_for_development", ""),
            )
            entities_to_insert.append((state._practice_assessments, pa.id, pa))
            result_id = pa.id
            
        elif proposal.move_type == MoveType.DESIGNATE_OPPOSITE:
            p = Process(content=proposal.payload["content"])
            d = DialecticalDesignation(
                process_id=p.id,
                role=DesignationRole.OPPOSITE,
                goal_id=state.get_active_goal().id,
                context_id=proposal.payload["context_id"],
                simplest_id=proposal.payload["simplest_id"],
                justification=proposal.payload["justification"],
            )
            entities_to_insert.append((state._processes, p.id, p))
            entities_to_insert.append((state._designations, d.id, d))
            result_id = p.id
            
        elif proposal.move_type == MoveType.ESTABLISH_CONTRADICTION:
            c = Contradiction(
                simplest_id=proposal.payload["simplest_id"],
                opposite_id=proposal.payload["opposite_id"],
                simplest_dev_ref_ids=proposal.payload.get("simplest_dev_ref_ids", []),
                opposite_dev_ref_ids=proposal.payload.get("opposite_dev_ref_ids", []),
                unity_justification=proposal.payload["unity_justification"],
                developing_unity_description=proposal.payload["developing_unity_description"],
            )
            entities_to_insert.append((state._contradictions, c.id, c))
            result_id = c.id
            
        elif proposal.move_type == MoveType.PROPOSE_LEAP:
            contradiction_id = proposal.payload["contradiction_id"]
            p = Process(content=proposal.payload["resolution_content"])
            outcome = ResolutionOutcome(proposal.payload["resolution_outcome"])
            rr = ResolutionRelation(
                contradiction_id=contradiction_id,
                resolution_process_id=p.id,
                outcome=outcome,
            )
            entities_to_insert.append((state._processes, p.id, p))
            entities_to_insert.append((state._resolution_relations, rr.id, rr))
            
            # This is a planned resolution, not evidence that the leap has occurred.
            result_id = p.id
            
        elif proposal.move_type == MoveType.COMPLETE:
            comp = Completion(
                goal_id=state.get_active_goal().id,
                final_response=proposal.payload.get("final_response", ""),
                committed_development_refs=[RuntimeReference(**r) for r in proposal.payload.get("committed_development_refs", [])],
                evidence_observation_ids=proposal.payload.get("evidence_observation_ids", []),
                goal_coverage=proposal.payload["goal_coverage"],
                why_further_development_not_needed=proposal.payload["why_further_development_not_needed"],
            )
            entities_to_insert.append((state._completions, comp.id, comp))
            updates.append(lambda: setattr(state._goals[comp.goal_id], "active", False))
            result_id = comp.id

        elif proposal.move_type == MoveType.REPORT_CONTRADICTION:
            report = UnresolvedReport(
                goal_id=state.get_active_goal().id,
                contested_source=proposal.payload["contested_source"],
                contradicting_observation_ids=list(proposal.payload["contradicting_observation_ids"]),
                supported_answer=proposal.payload.get("supported_answer"),
                supporting_observation_ids=list(proposal.payload.get("supporting_observation_ids", [])),
                final_response=proposal.payload["final_response"],
            )
            entities_to_insert.append((state._unresolved_reports, report.id, report))
            updates.append(lambda: setattr(state._goals[report.goal_id], "active", False))
            result_id = report.id
            
        # Apply mutations atomically
        for collection, key, value in entities_to_insert:
            collection[key] = value
        for update_fn in updates:
            update_fn()
            
        state._trace.append(proposal)
        return result_id

    def create_observation(self, state: RuntimeState, action_id: str, raw_result: Any, success: bool, error: Optional[str] = None) -> str:
        if not state.get_action(action_id):
            raise ValueError("Observation without existing Action is invalid")
        if state.get_action(action_id).status != "pending":
            raise ValueError("Action already has an observation")
        obs = Observation(
            action_id=action_id,
            raw_result=raw_result,
            success=success,
            error=error
        )
        state._observations[obs.id] = obs
        state._actions[action_id].status = "executed"
        return obs.id


class AllowedMovesResolver:
    def allowed_moves(self, state: RuntimeState) -> List[MoveType]:
        if not state.get_active_goal():
            return []
        from dialectic_ai.core.world import unassessed, revision_needed, persistent_contradiction
        report = [MoveType.REPORT_CONTRADICTION] if persistent_contradiction(state) else []
        if state.phase == "executing":
            if unassessed(state):
                return [MoveType.ASSESS_PRACTICE]
            if revision_needed(state):
                return [MoveType.REVISE_WORLD] + report
            moves = [MoveType.PROPOSE_ACTION]
            if state.get_all_observations():
                moves.append(MoveType.REVISE_WORLD)
                roadmap = state._roadmaps[state.active_roadmap_id]
                # Offer ASSESS_LEAP only while a leap of this roadmap is still unassessed: offering it
                # afterwards invited "Leap has already been assessed" rejections (11 in live traces).
                if all(state._resolution_relations[r].confirmed_roadmap_id == roadmap.id for r in roadmap.resolution_ids):
                    moves.append(MoveType.COMPLETE)
                else:
                    moves.append(MoveType.ASSESS_LEAP)
            return moves + report
        designations = state.get_all_designations()
        candidates = [d for d in designations if d.role == DesignationRole.CANDIDATE_SIMPLEST]
        simplest = [d for d in designations if d.role == DesignationRole.SIMPLEST]
        moves = []
        if not candidates and (not simplest or state.active_roadmap_id):
            moves.append(MoveType.PROPOSE_SIMPLEST)
        if candidates:
            moves.append(MoveType.ASSESS_SIMPLEST)
        if (candidates or simplest) and state.get_all_processes():
            moves.append(MoveType.DEVELOP_PROCESS)
            if len(state.get_all_processes()) > 1:
                moves.append(MoveType.CONNECT_DEVELOPMENT)
        if simplest:
            moves.append(MoveType.DESIGNATE_OPPOSITE)
        # world.py's validate_world requires BOTH the simplest's and the opposite's development
        # lines to be non-empty before ESTABLISH_CONTRADICTION can commit (a contradiction is the
        # unity of the development of both sides, not of two undeveloped designations). Listing
        # the move as allowed before that precondition is actually satisfiable sends the model
        # into a hard-reject loop it cannot escape by proposing differently -- observed live: 5
        # consecutive "A contradiction requires committed development of BOTH processes"
        # rejections, exhausting max_rejected_proposals. Mirror the real precondition here so the
        # move is never offered before it can actually commit.
        opposites = [d for d in designations if d.role == DesignationRole.OPPOSITE]
        def _has_development(process_id: str) -> bool:
            return any(state.is_committed(r.id) and r.source_process_id == process_id
                       for r in state.get_all_development_relations())
        if (simplest and opposites
                and any(_has_development(d.process_id) for d in simplest)
                and any(_has_development(d.process_id) for d in opposites)):
            moves.append(MoveType.ESTABLISH_CONTRADICTION)
        if state.get_all_contradictions():
            moves.append(MoveType.PROPOSE_LEAP)
        if state._resolution_relations and not candidates:
            moves.append(MoveType.BEGIN_EXECUTION)
        # The "clear" path: COMPLETE is legal directly from planning once the simplest has been
        # developed at least once, with no roadmap ever required. Some goals genuinely have no
        # opposite/contradiction to find (open-ended analysis/diagnosis especially) -- forcing a
        # manufactured one just to reach BEGIN_EXECUTION was a real, observed failure mode: the
        # engine had no honest way to finish a goal that turned out not to need a leap.
        # world.py's validate_world and the semantic judge (COMPLETE criteria: "do not accept
        # unsupported claims") are what police whether ending here is actually honest, not this
        # resolver -- this only says the move is worth considering, never that it will commit.
        if (simplest and not candidates and not opposites
                and any(_has_development(d.process_id) for d in simplest)):
            moves.append(MoveType.COMPLETE)
        return moves + report

    def get_direction_snapshot(self, state: RuntimeState) -> Optional[DirectionSnapshot]:
        goal = state.get_active_goal()
        if not goal:
            return None
            
        # Simplified frontier: all processes that don't have an emergent dev relation out of them
        # Note: this is a derived helper, not a persistent entity.
        all_sources = set(r.source_process_id for r in state.get_all_development_relations())
        active_frontiers = [p.id for p in state.get_all_processes() if p.id not in all_sources and p.status == "active"]
        
        pending_actions = [a.id for a in state.get_all_actions() if a.status == "pending"]
        active_contradictions = [c.id for c in state.get_all_contradictions() if c.status == ContradictionStatus.DEVELOPING]
        
        return DirectionSnapshot(
            goal_id=goal.id,
            active_frontier_process_ids=active_frontiers,
            pending_action_ids=pending_actions,
            active_contradiction_ids=active_contradictions
        )

