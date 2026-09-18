import pytest
from dialectic_ai.v1.runtime import DialecticalRuntime
from dialectic_ai.v1.mocks import MockLLMDispatcher, LLMRole
from dialectic_ai.v1.capabilities import CapabilityRegistry
from dialectic_ai.v1.evidence import EvidenceStore
from dialectic_ai.v1.state import RunOutcome


class TernaryMock(MockLLMDispatcher):
    def __init__(self, dev_overrides=None, opp_overrides=None):
        super().__init__()
        self.dev_overrides = dev_overrides or {}
        self.opp_overrides = opp_overrides or {}

    def call(self, role: LLMRole, input_data: dict) -> dict:
        base = super().call(role, input_data)
        if role == LLMRole.TERNARY_DEVELOPMENT_FACETS_JUDGE:
            for k, v in self.dev_overrides.items():
                base[k] = {"decision": v, "reason": "mock reason"}
        elif role == LLMRole.TERNARY_OPPOSITE_FACETS_JUDGE:
            for k, v in self.opp_overrides.items():
                base[k] = {"decision": v, "reason": "mock reason"}
        return base


def test_uncertain_required_facet_produces_unresolved():
    llm = TernaryMock(dev_overrides={"immanence_pass": "UNCERTAIN"})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test", use_ternary_judges=True)
    assert res.outcome == RunOutcome.SEMANTIC_UNRESOLVED


def test_explicit_fail_produces_invalid():
    llm = TernaryMock(dev_overrides={"immanence_pass": "FAIL"})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test", use_ternary_judges=True)
    assert res.outcome == RunOutcome.SEMANTIC_REJECTED


def test_all_pass_produces_valid():
    llm = TernaryMock() # Defaults are PASS, workflow is NO
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test", use_ternary_judges=True)
    # Reaches missing capability which fails execution
    assert res.outcome == RunOutcome.EXECUTION_FAILURE


def test_uncertain_is_not_silently_converted_to_fail():
    llm = TernaryMock(dev_overrides={"immanence_pass": "UNCERTAIN"})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test", use_ternary_judges=True)
    # Must be UNRESOLVED, not REJECTED
    assert res.outcome == RunOutcome.SEMANTIC_UNRESOLVED
    assert res.outcome != RunOutcome.SEMANTIC_REJECTED


def test_workflow_uncertain_never_produces_valid_development():
    llm = TernaryMock(dev_overrides={"workflow_only": "UNCERTAIN"})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test", use_ternary_judges=True)
    assert res.outcome == RunOutcome.SEMANTIC_UNRESOLVED


def test_opposite_uncertainty_produces_unresolved():
    llm = TernaryMock(opp_overrides={"alternative_only": "UNCERTAIN"})
    runtime = DialecticalRuntime(llm, CapabilityRegistry(), EvidenceStore())
    res, dpg, eg = runtime.run("req", "test", use_ternary_judges=True)
    assert res.outcome == RunOutcome.SEMANTIC_UNRESOLVED
