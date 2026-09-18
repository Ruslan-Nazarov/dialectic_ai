import pytest
from dialectic_ai.v1.runtime import DialecticalRuntime
from dialectic_ai.v1.mocks import MockLLMDispatcher, LLMRole
from dialectic_ai.v1.capabilities import CapabilityRegistry
from dialectic_ai.v1.evidence import EvidenceStore
from dialectic_ai.v1.state import RunOutcome

class RejectingTransitionJudgeMock(MockLLMDispatcher):
    def call(self, role: LLMRole, input_data: dict) -> dict:
        if role == LLMRole.TRANSITION_JUDGE:
            return {"status": "FAIL", "reason": "Just a sequence of workflow steps"}
        return super().call(role, input_data)

class RejectingOppositeJudgeMock(MockLLMDispatcher):
    def call(self, role: LLMRole, input_data: dict) -> dict:
        if role == LLMRole.OPPOSITE_JUDGE:
            return {"status": "FAIL", "exclusion_claim": "Alternative implementation does not exclude the simplest process"}
        return super().call(role, input_data)

class BlockingContradictionSufficiencyMock(MockLLMDispatcher):
    def call(self, role: LLMRole, input_data: dict) -> dict:
        if role == LLMRole.SUFFICIENCY_JUDGE:
            return {"status": "FAIL", "reason": "Contradiction blocks the target"}
        return super().call(role, input_data)

class NonBlockingContradictionSufficiencyMock(MockLLMDispatcher):
    def call(self, role: LLMRole, input_data: dict) -> dict:
        if role == LLMRole.SUFFICIENCY_JUDGE:
            return {"status": "PASS", "reason": "Contradiction does not block the target"}
        return super().call(role, input_data)


def test_workflow_rejection():
    # Test A: Workflow rejection
    # Expected: DEVELOPMENT_JUDGE = FAIL, no validated DevelopmentTransition
    llm = RejectingTransitionJudgeMock()
    registry = CapabilityRegistry()
    evidence_store = EvidenceStore()
    runtime = DialecticalRuntime(llm=llm, registry=registry, evidence_store=evidence_store)
    
    result, dpg, eg = runtime.run("req_1", "Test request", use_decomposed_judges=False)
    
    # Should fail in Iteration 1 development proposer (it is rejected by transition judge)
    assert result.outcome == RunOutcome.SEMANTIC_REJECTED
    assert "Development rejected: Just a sequence of workflow steps" in result.answer
    assert dpg is not None
    assert len(dpg.edges) == 0 # No edges added since the first development was rejected
    assert eg is None # No execution graph created


def test_alternative_implementation_rejection():
    # Test B: Alternative implementation rejection
    # Expected: OPPOSITE_JUDGE = FAIL, no OppositeRelation, no Contradiction
    llm = RejectingOppositeJudgeMock()
    registry = CapabilityRegistry()
    evidence_store = EvidenceStore()
    runtime = DialecticalRuntime(llm=llm, registry=registry, evidence_store=evidence_store)
    
    result, dpg, eg = runtime.run("req_2", "Test request", use_decomposed_judges=False)
    
    assert result.outcome == RunOutcome.SEMANTIC_REJECTED
    assert "Opposite rejected: Alternative implementation does not exclude the simplest process" in result.answer
    assert dpg is not None
    assert len(dpg.opposite_relations) == 0
    assert len(dpg.contradictions) == 0
    assert eg is None


def test_blocking_contradiction():
    # Test C: Blocking contradiction
    # Expected: task_intersects_contradiction = True, GoalSufficiency = FAIL, ExecutionGraph absent
    llm = BlockingContradictionSufficiencyMock()
    registry = CapabilityRegistry()
    evidence_store = EvidenceStore()
    runtime = DialecticalRuntime(llm=llm, registry=registry, evidence_store=evidence_store)
    
    result, dpg, eg = runtime.run("req_3", "Test request", use_decomposed_judges=False)
    
    assert result.outcome == RunOutcome.BLOCKING_CONTRADICTION
    assert "Goal Sufficiency Failed: Blocking Contradiction" in result.answer
    assert dpg is not None
    # We must have generated a contradiction
    assert len(dpg.contradictions) == 1
    # Goal sufficiency failed
    state_res = next((n for n in dpg.nodes.values()), None)
    assert state_res is not None # Just checking DPG exists
    assert eg is None


def test_non_blocking_contradiction():
    # Test D: Non-blocking contradiction
    # Expected: task_intersects_contradiction = False, GoalSufficiency = PASS, execution allowed
    llm = NonBlockingContradictionSufficiencyMock()
    registry = CapabilityRegistry()
    evidence_store = EvidenceStore()
    runtime = DialecticalRuntime(llm=llm, registry=registry, evidence_store=evidence_store)
    
    result, dpg, eg = runtime.run("req_4", "Test request", use_decomposed_judges=False)
    
    assert result.outcome == RunOutcome.EXECUTION_FAILURE # Because capability is not registered for mock test, execution fails missing cap, but that's expected
    assert "Missing Capability" in result.answer
    assert dpg is not None
    assert len(dpg.contradictions) == 1
    assert eg is not None # Execution graph is created!


def test_judge_rejection_is_authoritative():
    # Test E: Judge rejection is authoritative
    # Structurally valid candidate rejected by Judge MUST NOT enter validated DPG
    llm = RejectingTransitionJudgeMock()
    registry = CapabilityRegistry()
    evidence_store = EvidenceStore()
    runtime = DialecticalRuntime(llm=llm, registry=registry, evidence_store=evidence_store)
    
    result, dpg, eg = runtime.run("req_5", "Test request", use_decomposed_judges=False)
    
    # We check if p1 or p2 are in the graph. p0 is added unconditionally.
    assert len(dpg.nodes) == 1 # only p0
    assert len(dpg.edges) == 0 # no transitions
