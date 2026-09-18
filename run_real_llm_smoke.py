import os
import json
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

from dialectic_ai.v1.llm import SemanticLLMProvider, OpenAILLMProvider, RealLLMDispatcher
from dialectic_ai.v1.runtime import DialecticalRuntime
from dialectic_ai.v1.capabilities import CapabilityRegistry
from dialectic_ai.v1.evidence import EvidenceStore

def run_smoke():
    os.environ["V1_LLM_MODEL"] = "GigaChat"
    
    print(f"Provider Config: Model={os.environ['V1_LLM_MODEL']}, BaseURL=GigaChat")
    
    # 2. Initialize provider and dispatcher
    from dialectic_ai.v1.llm import GigaChatSemanticProvider, RealLLMDispatcher
    provider = GigaChatSemanticProvider()
    dispatcher = RealLLMDispatcher(provider)
    
    # We also need a Mock Capability Registry for the deterministic execution side
    registry = CapabilityRegistry()
    
    from dialectic_ai.v1.capabilities import CapabilityRecord
    record = CapabilityRecord(
        name="classify_item_by_rule",
        description="Mock rule classifier",
        input_schema={"item": "Any"},
        output_schema={"classified": "bool", "category": "str", "confidence": "float"},
        executor_fn=lambda x: {"classified": True, "category": "X", "confidence": 1.0}
    )
    registry.register(record)
    
    evidence_store = EvidenceStore()
    
    runtime = DialecticalRuntime(llm=dispatcher, registry=registry, evidence_store=evidence_store)
    
    # Run the canonical synthetic scenario
    raw_text = "determining whether a new item belongs to category X"
    print(f"\nStarting run with target: {raw_text}\n")
    
    result, dpg, eg = runtime.run(request_id="req_smoke", raw_text=raw_text)
    
    print("\n===============================")
    print("RUN COMPLETE")
    print("===============================")
    print(f"Dialectical Status: {result.dialectical_status}")
    print(f"Answer: {result.answer}")
    print(f"Evidence Count: {len(result.evidence_ids)}")
    print(f"Nodes in DPG: {len(dpg.nodes)}")
    print(f"Transitions in DPG: {len(dpg.edges)}")
    print(f"Opposites in DPG: {len(dpg.opposite_relations)}")
    print(f"Contradictions in DPG: {len(dpg.contradictions)}")
    
if __name__ == "__main__":
    try:
        run_smoke()
    except Exception as e:
        print(f"Smoke run failed: {e}")
