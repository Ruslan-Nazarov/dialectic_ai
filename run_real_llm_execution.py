import os
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

from dialectic_ai.v1.llm import GigaChatSemanticProvider, RealLLMDispatcher
from dialectic_ai.v1.runtime import DialecticalRuntime
from dialectic_ai.v1.capabilities import CapabilityRegistry, CapabilityRecord
from dialectic_ai.v1.evidence import EvidenceStore

def run_execution():
    os.environ["V1_LLM_MODEL"] = "GigaChat"
    
    print(f"Provider Config: Model={os.environ['V1_LLM_MODEL']}, BaseURL=GigaChat")
    
    # 1. Initialize provider and dispatcher
    provider = GigaChatSemanticProvider()
    dispatcher = RealLLMDispatcher(provider)
    
    # 2. Registry with REAL Executor
    registry = CapabilityRegistry()
    
    def real_executor(inputs):
        print(f"\n[EXECUTOR] Calling real executor with inputs: {inputs}")
        val = inputs.get("numeric_value")
        if val is None or not isinstance(val, (int, float)):
            raise TypeError("numeric_value must be a valid number")
            
        if val >= 10:
            cat = "X"
        else:
            cat = "Y"
            
        print(f"[EXECUTOR] Evaluated numeric_value {val} >= 10. Category is {cat}.")
        return {"classified": True, "category": cat, "confidence": 1.0}
    
    record = CapabilityRecord(
        name="classify_item_by_rule",
        description="Classifies an item into category X if numeric_value >= 10, else Y.",
        input_schema={"numeric_value": "float"},
        output_schema={"classified": "bool", "category": "str", "confidence": "float"},
        executor_fn=real_executor
    )
    registry.register(record)
    
    evidence_store = EvidenceStore()
    runtime = DialecticalRuntime(llm=dispatcher, registry=registry, evidence_store=evidence_store)
    
    # 3. Run the canonical synthetic scenario
    raw_text = "determining whether a new item belongs to category X"
    print(f"\nStarting run with target: {raw_text}\n")
    
    result, dpg, eg = runtime.run(
        request_id="req_real_exec", 
        raw_text=raw_text, 
        execution_inputs={"numeric_value": 14}
    )
    
    print("\n===============================")
    print("RUN COMPLETE")
    print("===============================")
    print(f"Outcome: {result.outcome.name}")
    print(f"Dialectical Status: {result.dialectical_status.name}")
    print(f"Answer: {result.answer}")
    
    if result.evidence_ids:
        evidence = evidence_store.get(result.evidence_ids[0])
        print(f"\n[EVIDENCE] Created Evidence: {evidence.id}")
        print(f"[EVIDENCE] Source Ref: {evidence.source_ref}")
        print(f"[EVIDENCE] Loop Context: {evidence.loop_context.name}")
        print(f"[EVIDENCE] Content: {evidence.content}")
        
    print(f"\nNodes in DPG: {len(dpg.nodes)}")
    print(f"Transitions in DPG: {len(dpg.edges)}")
    print(f"Opposites in DPG: {len(dpg.opposite_relations)}")
    print(f"Contradictions in DPG: {len(dpg.contradictions)}")
    
if __name__ == "__main__":
    try:
        run_execution()
    except Exception as e:
        print(f"Execution run failed: {e}")
