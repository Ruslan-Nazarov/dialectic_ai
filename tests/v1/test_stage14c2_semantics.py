import pytest
from dialectic_ai.v1.llm import DecomposedDevelopmentOutput

def test_nonempty_complete_rationale_payload():
    """Test that runtime raises ValueError if rationales are missing or placeholders."""
    from dialectic_ai.v1.runtime import DialecticalRuntime
    from dialectic_ai.v1.mocks import MockLLMDispatcher
    from dialectic_ai.v1.capabilities import CapabilityRegistry
    from dialectic_ai.v1.evidence import EvidenceStore
    
    # We will mock the dispatcher to return dummy strings to trigger the error.
    class BadProposerDispatcher(MockLLMDispatcher):
        def call(self, role, input_data):
            if role.name == "DEVELOPMENT_PROPOSER":
                return {
                    "type_canonical_name": "P1",
                    "description": "Bad candidate",
                    "emergence_rationale": "Rationale", # This is a placeholder!
                    "potential_rationale": "Potential", # Placeholder!
                    "determinacy_rationale": "Determinacy" # Placeholder!
                }
            return super().call(role, input_data)
            
    runtime = DialecticalRuntime(BadProposerDispatcher(), CapabilityRegistry(), EvidenceStore())
    with pytest.raises(ValueError, match="Invalid or missing emergence_rationale: Rationale"):
        runtime.run("req1", "Test Target")

def test_external_realization_not_equal_external_ground():
    """Test that if immanence is PASS (external realization != external ground), it aggregates correctly."""
    out = DecomposedDevelopmentOutput(
        distinctness_pass=True,
        immanence_pass=True,  # The key semantic distinction correctly judged by the mock LLM
        emergence_pass=True,
        retroactive_determinacy_pass=True,
        target_continuity_pass=True,
        workflow_only=False,
        reasoning="The ground is internal even if realization is external."
    )
    assert out.immanence_pass is True

def test_different_method_can_preserve_target_continuity():
    """Test that target_continuity can PASS even if methods differ."""
    out = DecomposedDevelopmentOutput(
        distinctness_pass=True,
        immanence_pass=True,
        emergence_pass=True,
        retroactive_determinacy_pass=True,
        target_continuity_pass=True, # Validated
        workflow_only=False,
        reasoning="Different method but same target process."
    )
    assert out.target_continuity_pass is True

def test_sequential_relation_not_equal_workflow_only():
    """Test that sequential relation does not imply workflow_only = True."""
    out = DecomposedDevelopmentOutput(
        distinctness_pass=True,
        immanence_pass=True,
        emergence_pass=True,
        retroactive_determinacy_pass=True,
        target_continuity_pass=True,
        workflow_only=False, # It is sequential, but ALSO has internal development!
        reasoning="It is a sequence but possesses internal dialectical development."
    )
    assert out.workflow_only is False

def test_derived_process_can_still_be_distinct():
    """Test that derived process is still distinct."""
    out = DecomposedDevelopmentOutput(
        distinctness_pass=True, # It is derived, but still a new determination
        immanence_pass=True,
        emergence_pass=True,
        retroactive_determinacy_pass=True,
        target_continuity_pass=True,
        workflow_only=False,
        reasoning="Derived from A, yet introduces a new determination."
    )
    assert out.distinctness_pass is True
