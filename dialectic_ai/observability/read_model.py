from dataclasses import asdict
from typing import Any, Dict, List, Optional

from dialectic_ai.core.runtime import (
    DirectionSnapshot, AllowedMovesResolver, Proposal,
    RuntimeState,
)


class RuntimeReadModel:
    def __init__(self, state: RuntimeState):
        self._state = state

    def get_goal(self) -> Optional[Dict[str, Any]]:
        goal = self._state.get_active_goal() or next(iter(self._state._goals.values()), None)
        if not goal:
            return None
        return {
            "id": goal.id,
            "content": goal.content,
            "active": goal.active
        }

    def get_direction(self) -> Optional[Dict[str, Any]]:
        snapshot = AllowedMovesResolver().get_direction_snapshot(self._state)
        return asdict(snapshot) if snapshot else None

    def get_allowed_moves(self) -> List[str]:
        return [move.value for move in AllowedMovesResolver().allowed_moves(self._state)]

    def get_processes(self) -> List[Dict[str, Any]]:
        return [{"id": p.id, "content": p.content, "status": p.status, "committed": self._state.is_committed(p.id)} 
                for p in self._state.get_all_processes()]

    def get_development_relations(self) -> List[Dict[str, Any]]:
        return [{
            "id": r.id, 
            "source_process_id": r.source_process_id,
            "emergent_process_id": r.emergent_process_id,
            "potential_containment": r.potential_containment,
            "emergence": r.emergence,
            "concretization": r.concretization,
            "new_content": r.new_content,
            "committed": self._state.is_committed(r.id)
        } for r in self._state.get_all_development_relations()]

    def get_designations(self) -> List[Dict[str, Any]]:
        return [{
            "id": d.id,
            "process_id": d.process_id,
            "role": d.role,
            "goal_id": d.goal_id,
            "context_id": d.context_id,
            "simplest_id": d.simplest_id,
            "justification": d.justification,
            "caught_from": d.caught_from,
            "committed": self._state.is_committed(d.id)
        } for d in self._state.get_all_designations()]

    def get_actions(self) -> List[Dict[str, Any]]:
        return [{
            "id": a.id,
            "goal_id": a.goal_id,
            "roadmap_id": a.roadmap_id,
            "tool_name": a.tool_name,
            "args": a.args,
            "origin_ref": {"type": a.origin_ref.type, "id": a.origin_ref.id} if a.origin_ref else None,
            "why_now": a.why_now,
            "purpose": a.purpose,
            "relation_to_goal": a.relation_to_goal,
            "expectation": a.expectation,
            "status": a.status,
            "committed": self._state.is_committed(a.id)
        } for a in self._state.get_all_actions()]

    def get_observations(self) -> List[Dict[str, Any]]:
        return [{
            "id": o.id,
            "action_id": o.action_id,
            "raw_result": o.raw_result,
            "success": o.success,
            "error": o.error
        } for o in self._state.get_all_observations()]

    def get_practice_assessments(self) -> List[Dict[str, Any]]:
        # Map internal to public
        return [{
            "id": p.id,
            "action_id": p.action_id,
            "observation_id": p.observation_id,
            "expected_actual_relation": p.expected_actual_relation,
            "explanation": p.explanation,
            "consequence_for_development": p.consequence_for_development,
            "committed": self._state.is_committed(p.id)
        } for p in getattr(self._state, '_practice_assessments', {}).values()]

    def get_contradictions(self) -> List[Dict[str, Any]]:
        return [{
            "id": c.id,
            "simplest_id": c.simplest_id,
            "opposite_id": c.opposite_id,
            "simplest_dev_ref_ids": c.simplest_dev_ref_ids,
            "opposite_dev_ref_ids": c.opposite_dev_ref_ids,
            "unity_justification": c.unity_justification,
            "developing_unity_description": c.developing_unity_description,
            "status": c.status,
            "committed": self._state.is_committed(c.id)
        } for c in self._state.get_all_contradictions()]

    def get_resolutions(self) -> List[Dict[str, Any]]:
        return [{
            "id": r.id,
            "contradiction_id": r.contradiction_id,
            "resolution_process_id": r.resolution_process_id,
            "outcome": r.outcome,
            "confirmed_roadmap_id": r.confirmed_roadmap_id,
            "evidence_observation_ids": r.evidence_observation_ids,
            "practice_explanation": r.practice_explanation,
            "opposite_acting_on_simplest": r.opposite_acting_on_simplest,
            "committed": self._state.is_committed(r.id)
        } for r in getattr(self._state, '_resolution_relations', {}).values()]

    def get_completions(self) -> List[Dict[str, Any]]:
        return [{
            "id": c.id,
            "goal_id": c.goal_id,
            "final_response": c.final_response,
            "committed_development_refs": [asdict(r) for r in c.committed_development_refs],
            "evidence_observation_ids": c.evidence_observation_ids,
            "goal_coverage": c.goal_coverage,
            "why_further_development_not_needed": c.why_further_development_not_needed,
            "committed": self._state.is_committed(c.id)
        } for c in getattr(self._state, '_completions', {}).values()]

    def get_timeline(self) -> List[Dict[str, Any]]:
        timeline = []
        for event in self._state._trace:
            proposal = event if isinstance(event, Proposal) else event.proposal
            timeline.append({
                "event_type": "proposal_committed" if isinstance(event, Proposal) else event.event_type,
                "proposal": asdict(proposal) if proposal else None,
                "validation_error": getattr(event, "validation_error", None),
                "timestamp": getattr(event, "timestamp", None),
            })
        return timeline

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "phase": self._state.phase,
            "active_roadmap_id": self._state.active_roadmap_id,
            "roadmaps": [asdict(r) for r in self._state._roadmaps.values()],
            "goal": self.get_goal(),
            "direction": self.get_direction(),
            "allowed_moves": self.get_allowed_moves(),
            "processes": self.get_processes(),
            "development": self.get_development_relations(),
            "designations": self.get_designations(),
            "actions": self.get_actions(),
            "observations": self.get_observations(),
            "practice": self.get_practice_assessments(),
            "contradictions": self.get_contradictions(),
            "resolutions": self.get_resolutions(),
            "completion": self.get_completions(),
            "timeline": self.get_timeline()
        }

    def get_prompt_snapshot(self) -> Dict[str, Any]:
        """The current graph only, for model prompts. Drops the event timeline and each
        roadmap's frozen copy of the graph: both grow with every move, neither is needed
        to judge or propose the next one, and together they were most of the payload."""
        snapshot = self.get_snapshot()
        snapshot.pop("timeline")
        for roadmap in snapshot["roadmaps"]:
            roadmap.pop("snapshot", None)
        return snapshot
