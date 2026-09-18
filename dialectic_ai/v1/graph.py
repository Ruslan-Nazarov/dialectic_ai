from typing import List, Dict, Optional, Tuple
import datetime
import dataclasses
from types import MappingProxyType
from dialectic_ai.v1.models import (
    ProcessInstance, DevelopmentTransition, OppositeRelation, Contradiction,
    ExecutionStep, ExecutionDependency, GoalSufficiencyResult
)
from dialectic_ai.v1.state import TransitionStatus, OppositeStatus, ContradictionStatus

class GuardError(Exception):
    pass

class DialecticalProcessGraph:
    def __init__(self, id: str, target_process_id: str, run_id: str):
        self.id = id
        self.target_process_id = target_process_id
        self.run_id = run_id
        self._nodes: Dict[str, ProcessInstance] = {}
        self._edges: List[DevelopmentTransition] = []
        self._opposite_relations: List[OppositeRelation] = []
        self._contradictions: List[Contradiction] = []
        self._simplest_process_id: Optional[str] = None
        self.created_at = datetime.datetime.now()

    @property
    def nodes(self):
        return MappingProxyType(self._nodes)
        
    @property
    def edges(self):
        return tuple(self._edges)
        
    @property
    def opposite_relations(self):
        return tuple(self._opposite_relations)
        
    @property
    def contradictions(self):
        return tuple(self._contradictions)
        
    @property
    def simplest_process_id(self):
        return self._simplest_process_id

    def add_node(self, node: ProcessInstance):
        if node.graph_id != self.id:
            raise GuardError(f"GUARD-10/12: Node {node.id} belongs to a different graph")
        self._nodes[node.id] = node
        if not self._simplest_process_id:
            self._simplest_process_id = node.id

    def add_validated_transition(self, candidate: DevelopmentTransition) -> DevelopmentTransition:
        if not isinstance(candidate, DevelopmentTransition):
            raise TypeError("GUARD-10: DPG._edges accepts DevelopmentTransition only")
        if candidate.graph_id != self.id:
            raise GuardError(f"GUARD-09: Transition {candidate.id} belongs to a different graph")
        if candidate.source_id not in self._nodes or candidate.target_id not in self._nodes:
            raise GuardError("GUARD-02: Source or target node not in DPG")
        if candidate.source_id == candidate.target_id:
            raise GuardError("Source cannot equal target")
            
        validated = dataclasses.replace(candidate, status=TransitionStatus.VALIDATED)
        self._edges.append(validated)
        return validated

    def add_validated_opposite(self, candidate: OppositeRelation) -> OppositeRelation:
        if candidate.graph_id != self.id:
            raise GuardError("Graph ID mismatch")
        if candidate.simplest_process_id not in self._nodes:
            raise GuardError("Simplest process not in DPG")
        if candidate.opposite_process_id not in self._nodes:
            raise GuardError("GUARD-02: OppositeProcess must originate from DPG development")
        if candidate.simplest_process_id == candidate.opposite_process_id:
            raise GuardError("Simplest cannot equal opposite")
            
        if not self._path_exists(candidate.simplest_process_id, candidate.opposite_process_id):
            raise GuardError("GUARD-12: Opposite must originate from validated development path")
            
        validated = dataclasses.replace(candidate, status=OppositeStatus.VALIDATED)
        self._opposite_relations.append(validated)
        return validated

    def _path_exists(self, start_id: str, end_id: str) -> bool:
        visited = set()
        queue = [start_id]
        while queue:
            curr = queue.pop(0)
            if curr == end_id:
                return True
            visited.add(curr)
            for edge in self._edges:
                if edge.source_id == curr and edge.target_id not in visited:
                    queue.append(edge.target_id)
        return False

    def derive_contradiction(
        self, opposite_relation_id: str, tension_description: str,
        is_relevant_to_target: bool, is_blocking: bool
    ) -> Contradiction:
        opp_rel = next((r for r in self._opposite_relations if r.id == opposite_relation_id), None)
        if not opp_rel:
            raise GuardError("OppositeRelation not found in this DPG")
        if opp_rel.status != OppositeStatus.VALIDATED:
            raise GuardError("OppositeRelation must be VALIDATED")
            
        contradiction = Contradiction(
            id=f"c_{self.id}_{len(self._contradictions)}",
            graph_id=self.id,
            opposite_relation_id=opp_rel.id,
            simplest_process_id=opp_rel.simplest_process_id,
            opposite_process_id=opp_rel.opposite_process_id,
            tension_description=tension_description,
            is_relevant_to_target=is_relevant_to_target,
            is_blocking=is_blocking,
            status=ContradictionStatus.VALIDATED
        )
        self._contradictions.append(contradiction)
        return contradiction


class ExecutionGraph:
    def __init__(self, id: str, run_id: str, sufficiency_result: GoalSufficiencyResult):
        if not sufficiency_result.is_sufficient:
            raise GuardError("GUARD-03: Cannot construct ExecutionGraph if is_sufficient is False")
        
        self.id = id
        self.run_id = run_id
        self.sufficiency_result_id = sufficiency_result.id
        self._steps: Dict[str, ExecutionStep] = {}
        self._edges: List[ExecutionDependency] = []
        self.created_at = datetime.datetime.now()

    @property
    def steps(self):
        return MappingProxyType(self._steps)

    @property
    def edges(self):
        return tuple(self._edges)

    def add_step(self, step: ExecutionStep):
        self._steps[step.id] = step

    def update_step_status(self, step_id: str, new_status: str):
        step = self._steps.get(step_id)
        if not step:
            raise GuardError("Step not found")
        self._steps[step_id] = dataclasses.replace(step, status=new_status)

    def add_edge(self, edge: ExecutionDependency):
        if not isinstance(edge, ExecutionDependency):
            raise TypeError("GUARD-11: ExecutionGraph.edges accepts ExecutionDependency only")
        self._edges.append(edge)
