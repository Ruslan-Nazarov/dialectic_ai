import pytest
from dialectic_ai.v1.runtime import DialecticalRuntime
from dialectic_ai.v1.mocks import MockLLMDispatcher, mock_rule_classifier
from dialectic_ai.v1.capabilities import CapabilityRegistry, CapabilityRecord
from dialectic_ai.v1.evidence import EvidenceStore
from dialectic_ai.v1.state import RunOutcome, DialecticalStatus

def test_v1_vertical_slice():
    # Setup
    llm = MockLLMDispatcher()
    registry = CapabilityRegistry()
    registry.register(CapabilityRecord(
        name="classify_item_by_rule",
        description="Classifies an item based on a rule",
        input_schema={"item": "Any"},
        output_schema={"classified": "bool", "category": "str", "confidence": "float"},
        executor_fn=mock_rule_classifier
    ))
    evidence_store = EvidenceStore()
    runtime = DialecticalRuntime(llm, registry, evidence_store)

    # Run
    result, dpg, eg = runtime.run("req_123", "Classify this item")

    # Verify
    assert result.outcome == RunOutcome.EXECUTION_COMPLETE
    assert result.dialectical_status == DialecticalStatus.SEMANTIC_STOP
    assert result.answer == "Classified as X"
    
    assert len(result.evidence_ids) == 1
    evidence = evidence_store.get(result.evidence_ids[0])
    assert evidence is not None
    assert evidence.content["classified"] is True
    
    # Graph check
    assert len(dpg.nodes) == 3
    assert len(dpg.edges) == 2
    assert len(dpg.opposite_relations) == 1
    assert len(dpg.contradictions) == 1
    
    # Execution graph check
    assert len(eg.steps) == 1
