"""
dialectic_ai/observability/evaluator.py

DIALECTICAL DESCRIPTION:
  Origin: Logs and traces are collected in trace.jsonl, but the presence of data
    does not imply a quality assessment.
  Contradiction: The agent may respond plausibly on the surface but ignore
    reality checks, hallucinate, or get stuck in contradictions.
    Manual auditing of traces is slow and does not scale.
  How it resolves: AgentEvaluator conducts an automatic audit of sessions and traces:
    1. Check the dialectical cycle (Generate -> Collide -> Synthesize).
    2. Reality grounding: were tools invoked in case of doubt/code?
    3. Memory enrichment: was the knowledge/memory graph updated?
    4. Convergence: did the session end with a stable completion, not by timeout/max_iterations?
  What it leads to: Quantitative quality metrics for the dashboard and automated benchmarks.
  Own contradictions: Static evaluation rules may penalize the agent for a quick
    trivial response (when a confrontation with reality was objectively unnecessary).

  Relationship to DialecticalAuditor (`dialectic audit`, observability/auditor.py): this
  class is the fast, local, heuristic sibling -- no LLM call, pure trace-counting,
  including a `rule5_violations` count of `dialectical_resolution_missing`/
  `leap_action_mismatch` trace events. DialecticalAuditor is the slower, LLM-as-judge
  sibling -- deeper product+process compliance review, and `investigate_contradiction()`
  for root-cause hypotheses on a specific contradiction. Run this one first/often; reach
  for the auditor when you need a judgment call this one's counting can't make.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.observability.tracer import TraceReader


@dataclass
class EvaluationReport:
    session_id: str
    dialectical_score: float  # 0.0 to 1.0
    reality_grounding_score: float  # 0.0 to 1.0
    completed: bool
    iterations_count: int
    memory_updated: bool
    violations: List[str]
    details: Dict[str, Any]
    rule5_violations: int = 0  # count of dialectical_resolution_missing / leap_action_mismatch trace events


@dialectical(
    origin="Logs and traces are collected, but without automatic evaluation, it is impossible to judge the quality of adherence to dialectics.",
    contradiction="The agent may respond plausibly on the surface but bypass reality checks or get stuck without completion.",
    resolves="AgentEvaluator conducts an automatic audit of adherence to the dialectical cycle and calculates metrics.",
    generates="Quantitative quality metrics for the dashboard and automated benchmarks.",
    own_contradictions="Heuristic evaluation may penalize for trivial sessions where reality checks were not required.",
    layer=5,
)
class AgentEvaluator:
    """
    Evaluator of the dialectical quality of the agent's work based on traces.
    """

    def __init__(self, trace_reader: Optional[TraceReader] = None):
        self.reader = trace_reader or TraceReader()

    def evaluate_session(self, session_id: Optional[str] = None) -> EvaluationReport:
        """
        Analyzes the trace of the session and returns metrics of dialectical quality.
        If session_id is not provided, all available events are analyzed.
        """
        events = self.reader.get_by_session(session_id) if session_id else self.reader.get_all()
        if any(e.event_type == "run_started" for e in events):
            return self._evaluate_runtime(events, session_id)
        violations = []

        if not events:
            return EvaluationReport(
                session_id=session_id or "unknown",
                dialectical_score=0.0,
                reality_grounding_score=0.0,
                completed=False,
                iterations_count=0,
                memory_updated=False,
                violations=["No events in the trace for analysis"],
                details={},
            )

        # Counting event types
        tool_calls = [e for e in events if e.event_type == "tool_call"]
        tool_call_count = len(tool_calls)
        if tool_call_count == 0:
            tool_call_count = sum(e.data.get("tool_calls_count", 0) for e in events if e.event_type == "generate")

        collisions = [e for e in events if e.event_type == "collision"]
        syntheses = [e for e in events if e.event_type == "synthesize"]
        synthesized = len(syntheses) > 0
        completions = [e for e in events if e.event_type == "completed"]
        errors = [e for e in events if e.event_type in ("parse_error", "tool_error")]
        # Rule 5 (dialectics_rules.md): a finalized response given without opposite_process/
        # contradiction/leap, or one whose claimed leap_type doesn't match what evidence_store
        # shows actually happened -- see engine/executor.py._phase_synthesize.
        rule5_events = [e for e in events if e.event_type in ("dialectical_resolution_missing", "leap_action_mismatch")]

        iterations = max([e.iteration or 1 for e in events], default=1)

        # 1. Check the Collision rule: each tool_call must be accompanied by a collision
        if tool_call_count > len(collisions):
            violations.append(
                f"Tools were invoked ({tool_call_count}), but not all confronted reality ({len(collisions)})"
            )

        # 2. Check completion: did the work end with completion
        completed = len(completions) > 0
        if not completed:
            violations.append("The cycle ended without completion (possibly, the iteration limit was exhausted)")

        # 3. Check memory
        memory_updated = any(
            e.data.get("memory_updated") or (e.data.get("memory_updates", 0) > 0)
            for e in syntheses
        )

        # 4. Check Rule 5 (dialectics_rules.md): a finalized response without a real
        # opposite_process/contradiction/leap, or a claimed leap the evidence contradicts,
        # is a methodology violation even when the session otherwise synthesized cleanly.
        if rule5_events:
            violations.append(
                f"Rule 5 violation: {len(rule5_events)} response(s) finalized without a genuine "
                f"opposite_process/contradiction/leap, or with a leap claim the evidence contradicts"
            )

        # Calculate the reality grounding metric
        if tool_call_count > 0:
            grounding = min(1.0, len(collisions) / tool_call_count)
        else:
            # If tools were not invoked, evaluate neutrally (1.0 if synthesis is successful without errors)
            grounding = 1.0 if (synthesized and not errors) else 0.5

        # Calculate the overall dialectical score
        score = 1.0
        if not synthesized:
            score -= 0.4
        if len(errors) > 0:
            score -= min(0.3, len(errors) * 0.1)
        if violations:
            score -= min(0.3, len(violations) * 0.15)
        score = max(0.0, min(1.0, score))

        return EvaluationReport(
            session_id=session_id or "global",
            dialectical_score=round(score, 2),
            reality_grounding_score=round(grounding, 2),
            completed=completed,
            iterations_count=iterations,
            memory_updated=memory_updated,
            violations=violations,
            details={
                "tool_calls_count": len(tool_calls),
                "collisions_count": len(collisions),
                "syntheses_count": len(syntheses),
                "errors_count": len(errors),
                "rule5_violations": len(rule5_events),
            },
            rule5_violations=len(rule5_events),
        )


    def _evaluate_runtime(self, events, session_id):
        # Never merge several runs into one apparent success. Default to the latest run.
        run_id = session_id or next(e.data["run_id"] for e in reversed(events) if e.event_type == "run_started")
        events = [e for e in events if e.data.get("run_id") == run_id]
        violations, accepted = [], False
        actions, observations, proposals, rejected = 0, 0, 0, 0
        for event in events:
            if event.event_type == "roadmap_accepted":
                accepted = True
            if event.event_type == "proposal_committed":
                proposals += 1
                move = event.data.get("proposal", {}).get("move_type")
                if move == "REVISE_WORLD":
                    accepted = False
                if move == "PROPOSE_ACTION":
                    actions += 1
                    if not accepted:
                        violations.append("Action occurred without an accepted roadmap")
            if event.event_type == "observation":
                observations += 1
            if event.event_type == "proposal_rejected":
                rejected += 1
        completed = bool(events and events[-1].event_type == "run_finished" and events[-1].data.get("status") == "completed")
        if not completed:
            violations.append("Run did not complete")
        if actions != observations:
            violations.append("Action/observation count mismatch")
        return EvaluationReport(run_id, float(not violations), observations / actions if actions else 0.0,
                                completed, proposals + rejected, False, violations,
                                {"protocol": "world-roadmap", "accepted_roadmaps": sum(e.event_type == "roadmap_accepted" for e in events),
                                 "actions": actions, "observations": observations, "rejected_proposals": rejected,
                                 "limitation": "Trace structure only; does not prove semantic correctness or task quality."})
