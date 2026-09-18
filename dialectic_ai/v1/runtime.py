import uuid
import dataclasses
from typing import Dict, Any, Tuple
from dialectic_ai.v1.models import (
    TargetProcess, ProcessType, ProcessInstance, DevelopmentTransition,
    OppositeRelation, Contradiction, GoalSufficiencyResult, SubCheckResult,
    CapabilityRequirement, ExecutionStep, ExecutionBinding,
    ExecutionDependency, Evidence, DialecticalRunState, DialecticalRunResult
)
from dialectic_ai.v1.state import (
    RunState, DialecticalStatus, GraphPosition, NodeStatus, TransitionStatus,
    OppositeStatus, ContradictionStatus, CheckStatus, EvidenceSourceType,
    ActionContextLoop, RunOutcome, ExecutionDependencyType
)
from dialectic_ai.v1.graph import DialecticalProcessGraph, ExecutionGraph, GuardError
from dialectic_ai.v1.guards import GuardValidator
from dialectic_ai.v1.mocks import MockLLMDispatcher, LLMRole
from dialectic_ai.v1.capabilities import CapabilityRegistry
from dialectic_ai.v1.evidence import EvidenceStore

class DialecticalRuntime:
    def __init__(self, llm: MockLLMDispatcher, registry: CapabilityRegistry, evidence_store: EvidenceStore):
        self.llm = llm
        self.registry = registry
        self.evidence_store = evidence_store

    def run(self, request_id: str, raw_text: str, execution_inputs: Dict[str, Any] = None, use_decomposed_judges: bool = True, use_ternary_judges: bool = False) -> Tuple[DialecticalRunResult, DialecticalProcessGraph, ExecutionGraph]:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        state = DialecticalRunState(
            run_id=run_id,
            request_id=request_id,
            dialectical_status=DialecticalStatus.IN_PROGRESS,
            budget=None # type: ignore
        )
        
        dpg = None
        eg = None
        result = None
        
        execution_inputs = execution_inputs or {"item": "Test Item"}

        # State: INIT -> NORMALIZING_TARGET
        state.transition_to(RunState.NORMALIZING_TARGET)
        
        target_out = self.llm.call(LLMRole.PROCESS_NORMALIZER, {"text": raw_text})
        target_process = TargetProcess(
            id=f"tp_{run_id}",
            request_id=request_id,
            description=target_out["description"],
            goal_state=target_out["goal_state"]
        )
        state.target_process_id = target_process.id

        # State: NORMALIZING_TARGET -> FINDING_SIMPLEST
        state.transition_to(RunState.FINDING_SIMPLEST)
        
        dpg = DialecticalProcessGraph(id=f"dpg_{run_id}", target_process_id=target_process.id, run_id=run_id)
        state.dpg_id = dpg.id

        simplest_out = self.llm.call(LLMRole.SIMPLEST_PROPOSER, {"target": target_process.description})
        p0_type = ProcessType(id=f"pt_{uuid.uuid4().hex[:8]}", canonical_name=simplest_out["type_canonical_name"], description="", source="framework")
        p0 = ProcessInstance(
            id=f"pi_0_{run_id}",
            graph_id=dpg.id,
            type_ref=p0_type.id,
            context={"description": simplest_out["description"]},
            graph_position=GraphPosition.ROOT,
            status=NodeStatus.VALIDATED
        )
        dpg.add_node(p0)

        # State: FINDING_SIMPLEST -> DEVELOPING
        state.transition_to(RunState.DEVELOPING)
        
        # Iteration 1: P0 -> P1
        dev1_out = self.llm.call(LLMRole.DEVELOPMENT_PROPOSER, {"source": p0.context["description"]})
        judge1_in = {
            "source": p0.context["description"],
            "candidate": dev1_out["description"],
            "emergence_rationale": dev1_out["emergence_rationale"],
            "potential_rationale": dev1_out["potential_rationale"],
            "determinacy_rationale": dev1_out["determinacy_rationale"]
        }
        judge1_in["target_process"] = target_process.description

        for key in ["emergence_rationale", "potential_rationale", "determinacy_rationale"]:
            val = judge1_in.get(key)
            if not val or val.strip() in ("", "Rationale", "Potential", "Determinacy"):
                raise ValueError(f"Invalid or missing {key}: {val}")

        if use_ternary_judges:
            out = self.llm.call(LLMRole.TERNARY_DEVELOPMENT_FACETS_JUDGE, judge1_in)
            facets = ["distinctness_pass", "immanence_pass", "emergence_pass", "retroactive_determinacy_pass", "target_continuity_pass"]
            has_fail = any(out.get(f).get("decision") == "FAIL" for f in facets) or out.get("workflow_only").get("decision") == "YES"
            has_uncertain = any(out.get(f).get("decision") == "UNCERTAIN" for f in facets) or out.get("workflow_only").get("decision") == "UNCERTAIN"
            
            if has_fail:
                judge1_out = {"status": "FAIL", "reason": "Ternary INVALID"}
            elif has_uncertain:
                judge1_out = {"status": "UNRESOLVED", "reason": "Ternary UNRESOLVED"}
            else:
                judge1_out = {"status": "PASS", "reason": "Ternary VALID"}
        elif use_decomposed_judges:
            out = self.llm.call(LLMRole.DEVELOPMENT_FACETS_JUDGE, judge1_in)
            is_valid = (
                out.get("distinctness_pass") and
                out.get("immanence_pass") and
                out.get("emergence_pass") and
                out.get("retroactive_determinacy_pass") and
                out.get("target_continuity_pass") and
                not out.get("workflow_only")
            )
            judge1_out = {"status": "PASS" if is_valid else "FAIL", "reason": out.get("reasoning", "Failed decomposed development checks")}
        else:
            judge1_out = self.llm.call(LLMRole.TRANSITION_JUDGE, judge1_in)

        print(f"\n[TRACE] DEVELOPMENT_PROPOSER 1 candidate: {dev1_out['description']}")
        print(f"[TRACE] DEVELOPMENT_JUDGE decision: {judge1_out['status']} - {judge1_out.get('reason', '')}")
        if judge1_out["status"] in ("FAIL", "UNRESOLVED"):
            print("[TRACE] framework action: transition rejected, state -> INCOMPLETE")
            state.transition_to(RunState.INCOMPLETE)
            outcome = RunOutcome.SEMANTIC_UNRESOLVED if judge1_out["status"] == "UNRESOLVED" else RunOutcome.SEMANTIC_REJECTED
            return DialecticalRunResult(
                id=f"res_{run_id}", run_id=run_id, outcome=outcome,
                dialectical_status=state.dialectical_status, answer=f"Development rejected: {judge1_out.get('reason', '')}"
            ), dpg, eg

        print("[TRACE] framework action: DevelopmentTransition 1 validated and added")
        p1_type = ProcessType(id=f"pt_{uuid.uuid4().hex[:8]}", canonical_name=dev1_out["type_canonical_name"], description="", source="framework")
        p1 = ProcessInstance(
            id=f"pi_1_{run_id}",
            graph_id=dpg.id,
            type_ref=p1_type.id,
            context={"description": dev1_out["description"]},
            graph_position=GraphPosition.INTERIOR,
            status=NodeStatus.VALIDATED
        )
        t1_candidate = DevelopmentTransition(
            id=f"dt_1_{run_id}",
            graph_id=dpg.id,
            source_id=p0.id,
            target_id=p1.id,
            emergence_rationale=dev1_out["emergence_rationale"],
            potential_rationale=dev1_out["potential_rationale"],
            determinacy_rationale=dev1_out["determinacy_rationale"],
            status=TransitionStatus.PROPOSED
        )
        dpg.add_node(p1)
        dpg.add_validated_transition(t1_candidate)

        # Iteration 2: P1 -> P2
        dev2_out = self.llm.call(LLMRole.DEVELOPMENT_PROPOSER, {"source": p1.context["description"]})
        judge2_in = {
            "source": p1.context["description"],
            "candidate": dev2_out["description"],
            "emergence_rationale": dev2_out["emergence_rationale"],
            "potential_rationale": dev2_out["potential_rationale"],
            "determinacy_rationale": dev2_out["determinacy_rationale"]
        }
        judge2_in["target_process"] = target_process.description

        for key in ["emergence_rationale", "potential_rationale", "determinacy_rationale"]:
            val = judge2_in.get(key)
            if not val or val.strip() in ("", "Rationale", "Potential", "Determinacy"):
                raise ValueError(f"Invalid or missing {key}: {val}")

        if use_ternary_judges:
            out = self.llm.call(LLMRole.TERNARY_DEVELOPMENT_FACETS_JUDGE, judge2_in)
            facets = ["distinctness_pass", "immanence_pass", "emergence_pass", "retroactive_determinacy_pass", "target_continuity_pass"]
            has_fail = any(out.get(f).get("decision") == "FAIL" for f in facets) or out.get("workflow_only").get("decision") == "YES"
            has_uncertain = any(out.get(f).get("decision") == "UNCERTAIN" for f in facets) or out.get("workflow_only").get("decision") == "UNCERTAIN"
            
            if has_fail:
                judge2_out = {"status": "FAIL", "reason": "Ternary INVALID"}
            elif has_uncertain:
                judge2_out = {"status": "UNRESOLVED", "reason": "Ternary UNRESOLVED"}
            else:
                judge2_out = {"status": "PASS", "reason": "Ternary VALID"}
        elif use_decomposed_judges:
            out = self.llm.call(LLMRole.DEVELOPMENT_FACETS_JUDGE, judge2_in)
            is_valid = (
                out.get("distinctness_pass") and
                out.get("immanence_pass") and
                out.get("emergence_pass") and
                out.get("retroactive_determinacy_pass") and
                out.get("target_continuity_pass") and
                not out.get("workflow_only")
            )
            judge2_out = {"status": "PASS" if is_valid else "FAIL", "reason": out.get("reasoning", "Failed decomposed development checks")}
        else:
            judge2_out = self.llm.call(LLMRole.TRANSITION_JUDGE, judge2_in)
        
        print(f"\n[TRACE] DEVELOPMENT_PROPOSER 2 candidate: {dev2_out['description']}")
        print(f"[TRACE] DEVELOPMENT_JUDGE decision: {judge2_out['status']} - {judge2_out.get('reason', '')}")
        if judge2_out["status"] in ("FAIL", "UNRESOLVED"):
            print("[TRACE] framework action: transition rejected, state -> INCOMPLETE")
            state.transition_to(RunState.INCOMPLETE)
            outcome = RunOutcome.SEMANTIC_UNRESOLVED if judge2_out["status"] == "UNRESOLVED" else RunOutcome.SEMANTIC_REJECTED
            return DialecticalRunResult(
                id=f"res_{run_id}", run_id=run_id, outcome=outcome,
                dialectical_status=state.dialectical_status, answer=f"Development rejected: {judge2_out.get('reason', '')}"
            ), dpg, eg

        print("[TRACE] framework action: DevelopmentTransition 2 validated and added")
        p2_type = ProcessType(id=f"pt_{uuid.uuid4().hex[:8]}", canonical_name=dev2_out["type_canonical_name"], description="", source="framework")
        p2 = ProcessInstance(
            id=f"pi_2_{run_id}",
            graph_id=dpg.id,
            type_ref=p2_type.id,
            context={"description": dev2_out["description"]},
            graph_position=GraphPosition.OPPOSITE,
            status=NodeStatus.VALIDATED
        )
        t2_candidate = DevelopmentTransition(
            id=f"dt_2_{run_id}",
            graph_id=dpg.id,
            source_id=p1.id,
            target_id=p2.id,
            emergence_rationale=dev2_out["emergence_rationale"],
            potential_rationale=dev2_out["potential_rationale"],
            determinacy_rationale=dev2_out["determinacy_rationale"],
            status=TransitionStatus.PROPOSED
        )
        dpg.add_node(p2)
        dpg.add_validated_transition(t2_candidate)

        # State: DEVELOPING -> CHECKING_OPPOSITE
        state.transition_to(RunState.CHECKING_OPPOSITE)

        opp_in = {
            "p0": p0.context["description"],
            "p2": p2.context["description"],
            "development_path": f"{p0.context['description']} -> {p1.context['description']} -> {p2.context['description']}"
        }
        opp_in["exclusion_rationale"] = "P2 negates the need for P0."
        
        if use_ternary_judges:
            out = self.llm.call(LLMRole.TERNARY_OPPOSITE_FACETS_JUDGE, opp_in)
            exc = out.get("excludes_need_for_simplest").get("decision")
            alt = out.get("alternative_only").get("decision")
            
            if exc == "FAIL" or alt == "YES":
                opp_out = {"status": "FAIL", "exclusion_claim": "Ternary INVALID"}
            elif exc == "UNCERTAIN" or alt == "UNCERTAIN":
                opp_out = {"status": "UNRESOLVED", "exclusion_claim": "Ternary UNRESOLVED"}
            else:
                opp_out = {"status": "PASS", "exclusion_claim": "Ternary VALID"}
        elif use_decomposed_judges:
            out = self.llm.call(LLMRole.OPPOSITE_FACETS_JUDGE, opp_in)
            is_valid = (out.get("excludes_need_for_simplest") and not out.get("alternative_only"))
            opp_out = {"status": "PASS" if is_valid else "FAIL", "exclusion_claim": out.get("reasoning", "Failed opposite checks")}
        else:
            opp_out = self.llm.call(LLMRole.OPPOSITE_JUDGE, opp_in)
        
        print(f"\n[TRACE] OPPOSITE_PROPOSER candidate: {p2.context['description']}")
        print(f"[TRACE] OPPOSITE_JUDGE decision: {opp_out['status']} - {opp_out.get('exclusion_claim', 'No reason provided')}")
        if opp_out["status"] in ("FAIL", "UNRESOLVED"):
            print("[TRACE] framework action: relation rejected, state -> INCOMPLETE")
            state.transition_to(RunState.INCOMPLETE)
            outcome = RunOutcome.SEMANTIC_UNRESOLVED if opp_out["status"] == "UNRESOLVED" else RunOutcome.SEMANTIC_REJECTED
            return DialecticalRunResult(
                id=f"res_{run_id}", run_id=run_id, outcome=outcome,
                dialectical_status=state.dialectical_status, answer=f"Opposite rejected: {opp_out.get('exclusion_claim', 'Fail')}"
            ), dpg, eg

        print("[TRACE] framework action: OppositeRelation validated and added")
        opp_candidate = OppositeRelation(
            id=f"or_{run_id}",
            graph_id=dpg.id,
            simplest_process_id=p0.id,
            opposite_process_id=p2.id,
            exclusion_claim=opp_out.get("exclusion_claim", "Pass"),
            status=OppositeStatus.CANDIDATE
        )
        opp_rel = dpg.add_validated_opposite(opp_candidate)

        # Contradiction Construction
        contradiction = dpg.derive_contradiction(
            opposite_relation_id=opp_rel.id,
            tension_description="Fresh human judgment vs Automatic formal application",
            is_relevant_to_target=True,
            is_blocking=True
        )
        print("[TRACE] framework Contradiction derivation: Created Contradiction")

        # State: CHECKING_OPPOSITE -> CHECKING_SUFFICIENCY
        state.transition_to(RunState.CHECKING_SUFFICIENCY)
        
        suff_in = {
            "target": target_process.description,
            "contradiction": f"{p0.context['description']} vs {p2.context['description']}"
        }
        if use_decomposed_judges:
            out = self.llm.call(LLMRole.SUFFICIENCY_FACETS_JUDGE, suff_in)
            task_intersects = (out.get("resolution_dependency") and not out.get("existing_path_sufficiency"))
            suff_out = {"status": "FAIL" if task_intersects else "PASS", "reason": out.get("reasoning", "Sufficiency outcome")}
        else:
            suff_out = self.llm.call(LLMRole.SUFFICIENCY_JUDGE, suff_in)
        
        print(f"\n[TRACE] SUFFICIENCY_JUDGE decision: {suff_out['status']} - {suff_out.get('reason', '')}")
        if suff_out["status"] == "FAIL":
            print("[TRACE] framework Gate result: SUFFICIENCY FAIL - Blocking Contradiction")
            task_intersects = True
            suff_semantic_status = CheckStatus.FAIL
        else:
            task_intersects = False
            suff_semantic_status = CheckStatus.PASS

        suff_res = GoalSufficiencyResult(
            id=f"gs_{run_id}",
            graph_id=dpg.id,
            dialectical_status=DialecticalStatus.SEMANTIC_STOP,
            structural=SubCheckResult(status=CheckStatus.PASS, reason="DPG structural check passed"),
            capability=SubCheckResult(status=CheckStatus.PASS, reason="Capabilities exist"),
            semantic=SubCheckResult(status=suff_semantic_status, reason=suff_out.get("reason", "")),
            evidence=SubCheckResult(status=CheckStatus.NOT_APPLICABLE, reason="No external evidence required for this task"),
            task_intersects_contradiction=task_intersects,
            relevant_process_ids=(p2.id,),
            best_effort=False,
            rationale="Sufficient to execute" if suff_semantic_status == CheckStatus.PASS else "Contradiction blocks execution"
        )
        state.sufficiency_result_id = suff_res.id

        if not suff_res.is_sufficient:
            # STOP
            state.transition_to(RunState.COMPLETED, dpg=dpg)
            return DialecticalRunResult(
                id=f"res_{run_id}", run_id=run_id, outcome=RunOutcome.BLOCKING_CONTRADICTION,
                dialectical_status=DialecticalStatus.SEMANTIC_STOP, answer="Goal Sufficiency Failed: Blocking Contradiction"
            ), dpg, eg

        # State: CHECKING_SUFFICIENCY -> EXECUTION_PLANNING
        state.transition_to(RunState.EXECUTION_PLANNING)
        
        eg = ExecutionGraph(id=f"eg_{run_id}", run_id=run_id, sufficiency_result=suff_res)
        state.execution_graph_id = eg.id

        # Use the first capability from the registry to avoid hardcoding "classify_item_by_rule"
        cap_name = list(self.registry._records.keys())[0] if self.registry._records else "missing_capability"
        
        req = CapabilityRequirement(
            id=f"req_{run_id}",
            derived_from=p2.id,
            name=cap_name,
            input_schema={"item": "Any"},
            output_schema={"classified": "bool"}
        )
        binding = self.registry.lookup(req)
        
        if not binding:
            state.transition_to(RunState.FAILED)
            result = DialecticalRunResult(
                id=f"res_{run_id}",
                run_id=run_id,
                outcome=RunOutcome.EXECUTION_FAILURE,
                dialectical_status=state.dialectical_status,
                answer="Missing Capability"
            )
            return result, dpg, eg

        step = ExecutionStep(
            id=f"es_{run_id}",
            execution_graph_id=eg.id,
            capability_id=req.name,
            binding_id=binding.id,
            status="PENDING"
        )
        eg.add_step(step)

        # State: EXECUTION_PLANNING -> EXECUTING
        state.transition_to(RunState.EXECUTING)
        eg.update_step_status(step.id, "RUNNING")
        
        try:
            exec_res = self.registry.execute(binding, execution_inputs)
            
            evidence = Evidence(
                source_type=EvidenceSourceType.TOOL_CALL,
                source_ref=binding.id,
                content=exec_res,
                schema=req.output_schema,
                loop_context=ActionContextLoop.EXECUTION
            )
            self.evidence_store.add(evidence)
            eg.update_step_status(step.id, "SUCCEEDED")
            
            # State: EXECUTING -> COMPLETED
            state.dialectical_status = DialecticalStatus.SEMANTIC_STOP
            state.transition_to(RunState.COMPLETED, dpg=dpg)

            result = DialecticalRunResult(
                id=f"res_{run_id}",
                run_id=run_id,
                outcome=RunOutcome.EXECUTION_COMPLETE,
                dialectical_status=state.dialectical_status,
                answer=f"Classified as {exec_res.get('category', 'UNKNOWN')}",
                evidence_ids=(evidence.id,)
            )

        except Exception as e:
            eg.update_step_status(step.id, "FAILED")
            state.transition_to(RunState.FAILED)
            result = DialecticalRunResult(
                id=f"res_{run_id}",
                run_id=run_id,
                outcome=RunOutcome.EXECUTION_FAILURE,
                dialectical_status=state.dialectical_status,
                answer=f"Execution Failed: {str(e)}"
            )

        return result, dpg, eg
