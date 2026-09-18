import pytest
from dialectic_ai.v1.runtime import DialecticalRuntime
from dialectic_ai.v1.mocks import MockLLMDispatcher, LLMRole
from dialectic_ai.v1.capabilities import CapabilityRegistry
from dialectic_ai.v1.evidence import EvidenceStore
from dialectic_ai.v1.state import RunOutcome


class DecomposedMock(MockLLMDispatcher):
    def __init__(self, dev_overrides=None, opp_overrides=None, suff_overrides=None):
        super().__init__()
        self.dev_overrides = dev_overrides or {}
        self.opp_overrides = opp_overrides or {}
        self.suff_overrides = suff_overrides or {}

    def call(self, role: LLMRole, input_data: dict) -> dict:
        base = super().call(role, input_data)
        if role == LLMRole.DEVELOPMENT_FACETS_JUDGE:
            base.update(self.dev_overrides)
        elif role == LLMRole.OPPOSITE_FACETS_JUDGE:
            base.update(self.opp_overrides)
        elif role == LLMRole.SUFFICIENCY_FACETS_JUDGE:
            base.update(self.suff_overrides)
        return base


def test_distinct_but_external_is_not_development():
    llm = DecomposedMock(dev_overrides={"distinctness_pass": True, "immanence_pass": False})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test")
    assert res.outcome == RunOutcome.SEMANTIC_REJECTED


def test_immanent_but_not_new_is_not_development():
    llm = DecomposedMock(dev_overrides={"distinctness_pass": False, "immanence_pass": True})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test")
    assert res.outcome == RunOutcome.SEMANTIC_REJECTED


def test_workflow_sequence_fails_immanence_or_workflow_test():
    llm = DecomposedMock(dev_overrides={"workflow_only": True})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test")
    assert res.outcome == RunOutcome.SEMANTIC_REJECTED


def test_valid_classification_development_passes_all_facets():
    llm = DecomposedMock()  # defaults are all valid
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test")
    # Will fail at execution due to missing capability, but pass semantic validation
    assert res.outcome == RunOutcome.EXECUTION_FAILURE
    assert "Missing Capability" in res.answer


def test_target_continuity_blocks_semantic_drift():
    llm = DecomposedMock(dev_overrides={"target_continuity_pass": False})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test")
    assert res.outcome == RunOutcome.SEMANTIC_REJECTED


def test_alternative_implementation_is_not_opposite():
    llm = DecomposedMock(opp_overrides={"alternative_only": True})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test")
    assert res.outcome == RunOutcome.SEMANTIC_REJECTED


def test_nonblocking_contradiction_allows_execution():
    llm = DecomposedMock(suff_overrides={"resolution_dependency": False, "existing_path_sufficiency": True})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test")
    # Passes sufficiency, fails at execution
    assert res.outcome == RunOutcome.EXECUTION_FAILURE
    assert eg is not None


def test_blocking_contradiction_prevents_execution():
    llm = DecomposedMock(suff_overrides={"resolution_dependency": True, "existing_path_sufficiency": False})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test")
    assert res.outcome == RunOutcome.BLOCKING_CONTRADICTION
    assert eg is None


def test_semantic_rejection_is_not_execution_failure():
    llm = DecomposedMock(dev_overrides={"workflow_only": True})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test")
    assert res.outcome == RunOutcome.SEMANTIC_REJECTED
    assert res.outcome != RunOutcome.EXECUTION_FAILURE


def test_missing_capability_reaches_execution_layer_and_preserves_dpg():
    llm = DecomposedMock()
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test")
    assert res.outcome == RunOutcome.EXECUTION_FAILURE
    assert eg is not None
    assert len(dpg.nodes) == 3
    assert len(dpg.contradictions) == 1
