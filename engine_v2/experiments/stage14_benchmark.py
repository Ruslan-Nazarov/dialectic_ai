import os
import time
from typing import Dict, Any, List
from pydantic import BaseModel
from dialectic_ai.v1.runtime import DialecticalRuntime
from dialectic_ai.v1.capabilities import CapabilityRegistry, CapabilityRecord
from dialectic_ai.v1.evidence import EvidenceStore
from dialectic_ai.v1.state import RunOutcome

# Need to import RealLLMDispatcher and GigaChatProvider if keys available
from dialectic_ai.v1.llm import RealLLMDispatcher, GigaChatSemanticProvider, OpenAILLMProvider

def run_benchmark(cases: List[Dict[str, Any]], use_decomposed: bool):
    if os.getenv("GIGACHAT_AUTH_KEY"):
        provider = GigaChatSemanticProvider()
    elif os.getenv("V1_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"):
        provider = OpenAILLMProvider()
    else:
        print("No LLM API keys found. Benchmark cannot run.")
        return

    dispatcher = RealLLMDispatcher(provider)
    
    registry = CapabilityRegistry()
    registry.register(CapabilityRecord(
        name="classify_item_by_rule",
        description="Classifies an item based on a rule",
        input_schema={"item": "Any"},
        output_schema={"classified": "bool", "category": "str", "confidence": "float"},
        executor_fn=lambda x: {"classified": True, "category": "X", "confidence": 1.0}
    ))
    
    results = []
    
    for i, case in enumerate(cases):
        print(f"\n--- Running Case {i+1}: {case['name']} (Decomposed: {use_decomposed}) ---")
        evidence_store = EvidenceStore()
        runtime = DialecticalRuntime(llm=dispatcher, registry=registry, evidence_store=evidence_store)
        
        start_time = time.time()
        res, dpg, eg = runtime.run(f"req_bench_{i}", case["request"], use_decomposed_judges=use_decomposed)
        end_time = time.time()
        
        results.append({
            "name": case["name"],
            "outcome": res.outcome.name,
            "answer": res.answer,
            "wall_time": end_time - start_time,
            "dpg_nodes": len(dpg.nodes) if dpg else 0,
            "dpg_edges": len(dpg.edges) if dpg else 0,
            "contradictions": len(dpg.contradictions) if dpg else 0
        })
        
    return results

if __name__ == "__main__":
    cases = [
        {"name": "Case 1: Valid classification", "request": "Classify this item"},
        {"name": "Case 2: Sensor workflow trap", "request": "Read sensor then compare threshold"},
        {"name": "Case 3: Alternative trap (SQL vs NoSQL)", "request": "Store data in a database"},
    ]
    
    print("=== STAGE 14 MINI-BENCHMARK ===")
    print("Running with INTEGRATED judge (baseline)...")
    integrated_results = run_benchmark(cases, use_decomposed=False)
    
    print("\nRunning with DECOMPOSED judge...")
    decomposed_results = run_benchmark(cases, use_decomposed=True)
    
    print("\n=== BENCHMARK RESULTS ===")
    print("Case | Integrated Outcome | Decomposed Outcome")
    if integrated_results and decomposed_results:
        for ir, dr in zip(integrated_results, decomposed_results):
            print(f"{ir['name']} | {ir['outcome']} | {dr['outcome']}")
