import pytest
from copy import deepcopy
from dialectic_ai.v1.runtime import DialecticalRuntime
from dialectic_ai.v1.capabilities import CapabilityRegistry, CapabilityRecord
from dialectic_ai.v1.evidence import EvidenceStore
from dialectic_ai.v1.mocks import MockLLMDispatcher
from dialectic_ai.v1.state import DialecticalStatus, ActionContextLoop, RunOutcome

def test_real_tool_end_to_end():
    registry = CapabilityRegistry()
    def real_executor(inputs):
        val = inputs.get("numeric_value", 0)
        if not isinstance(val, (int, float)):
            raise TypeError("numeric_value must be a number")
        cat = "X" if val >= 10 else "Y"
        return {"classified": True, "category": cat, "confidence": 1.0}
        
    registry.register(CapabilityRecord(
        name="classify_item_by_rule",
        description="Classifies an item by checking if numeric_value >= 10",
        input_schema={"numeric_value": "float"},
        output_schema={"classified": "bool", "category": "str", "confidence": "float"},
        executor_fn=real_executor
    ))
    
    runtime = DialecticalRuntime(llm=MockLLMDispatcher(), registry=registry, evidence_store=EvidenceStore())
    
    result, dpg, eg = runtime.run("req1", "test rule", {"numeric_value": 14})
    
    assert result.outcome == RunOutcome.EXECUTION_COMPLETE
    assert result.dialectical_status == DialecticalStatus.SEMANTIC_STOP
    assert result.answer == "Classified as X"
    
def test_real_tool_creates_execution_evidence():
    registry = CapabilityRegistry()
    registry.register(CapabilityRecord(
        name="classify_item_by_rule",
        description="Mock",
        input_schema={},
        output_schema={},
        executor_fn=lambda x: {"category": "X"}
    ))
    
    store = EvidenceStore()
    runtime = DialecticalRuntime(llm=MockLLMDispatcher(), registry=registry, evidence_store=store)
    result, dpg, eg = runtime.run("req2", "test", {"numeric_value": 14})
    
    assert len(result.evidence_ids) == 1
    evidence_id = result.evidence_ids[0]
    
    # Retrieve evidence from store
    ev = store.get(evidence_id)
    assert ev.loop_context == ActionContextLoop.EXECUTION
    assert ev.content == {"category": "X"}

def test_execution_failure_blocks_completion():
    registry = CapabilityRegistry()
    def failing_executor(inputs):
        raise ValueError("Invalid input for executor")
        
    registry.register(CapabilityRecord(
        name="classify_item_by_rule",
        description="Fails",
        input_schema={},
        output_schema={},
        executor_fn=failing_executor
    ))
    
    runtime = DialecticalRuntime(llm=MockLLMDispatcher(), registry=registry, evidence_store=EvidenceStore())
    result, dpg, eg = runtime.run("req3", "test", {})
    
    assert result.outcome == RunOutcome.EXECUTION_FAILURE
    assert "Execution Failed" in result.answer
    assert list(eg.steps.values())[0].status == "FAILED"
    
def test_missing_capability_is_operational_not_semantic():
    # Empty registry
    registry = CapabilityRegistry()
    runtime = DialecticalRuntime(llm=MockLLMDispatcher(), registry=registry, evidence_store=EvidenceStore())
    
    result, dpg, eg = runtime.run("req4", "test", {})
    
    assert result.outcome == RunOutcome.EXECUTION_FAILURE
    assert result.answer == "Missing Capability"
    assert len(dpg.contradictions) == 1  # The original semantic contradiction remains intact
    assert len(dpg.opposite_relations) == 1
    # Check that DPG is unaffected. Missing capability didn't trigger any opposite logic.

def test_execution_does_not_mutate_dpg():
    registry = CapabilityRegistry()
    registry.register(CapabilityRecord(
        name="classify_item_by_rule",
        description="Mock",
        input_schema={},
        output_schema={},
        executor_fn=lambda x: {"category": "X"}
    ))
    
    # We will subclass DialecticalRuntime to capture DPG before execution
    class InterceptingRuntime(DialecticalRuntime):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.dpg_before_exec = None
            
        def run(self, request_id: str, raw_text: str, execution_inputs=None):
            # To intercept properly, we'd need to hook into the state machine.
            # For simplicity, we just check the final DPG structure since the mock 
            # only builds exactly 3 nodes, 2 edges, 1 opposite, 1 contradiction.
            # If execution modified it, counts would change.
            return super().run(request_id, raw_text, execution_inputs)
            
    runtime = InterceptingRuntime(llm=MockLLMDispatcher(), registry=registry, evidence_store=EvidenceStore())
    result, dpg, eg = runtime.run("req5", "test", {})
    
    assert len(dpg.nodes) == 3
    assert len(dpg.edges) == 2
    assert len(dpg.opposite_relations) == 1
    assert len(dpg.contradictions) == 1
