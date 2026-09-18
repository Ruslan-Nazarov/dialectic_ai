import os
import time
from typing import Dict, Any, List
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from dialectic_ai.v1.runtime import DialecticalRuntime
from dialectic_ai.v1.capabilities import CapabilityRegistry
from dialectic_ai.v1.evidence import EvidenceStore
from dialectic_ai.v1.mocks import LLMRole
from dialectic_ai.v1.llm import RealLLMDispatcher, GigaChatSemanticProvider, OpenAILLMProvider
import json

load_dotenv()

# Independent models
class IndepBool(BaseModel):
    model_config = ConfigDict(extra='forbid')
    result: bool
    reasoning: str

def parse_json(provider, sys, user, cls):
    sys_final = sys + "\n\nYou must return a valid JSON object matching the requested schema. Respond ONLY with JSON."
    for _ in range(3):
        try:
            raw = provider.generate(sys_final, user, {"type": "json_object"}).strip()
            if raw.startswith("```json"): raw = raw[7:]
            if raw.startswith("```"): raw = raw[3:]
            if raw.endswith("```"): raw = raw[:-3]
            raw = raw.strip()
            data = json.loads(raw)
            # Find the boolean key if it's not 'result'
            # But we defined the schema to be just 'result', so we can ask for 'result' in the prompt.
            return cls.model_validate(data).result
        except Exception:
            time.sleep(1)
    return False


def run_independent_development(provider, input_data):
    user_prompt = (
        f"Target Process: {input_data.get('target_process', 'N/A')}\n"
        f"Source Process A: {input_data.get('source')}\n"
        f"Candidate Process B: {input_data.get('candidate')}\n"
        f"Emergence Rationale: {input_data.get('emergence_rationale')}\n"
        f"Potential Rationale: {input_data.get('potential_rationale')}\n"
        f"Determinacy Rationale: {input_data.get('determinacy_rationale')}\n"
    )
    
    distinctness = parse_json(provider, "Evaluate facet distinctness. Is B a new determination, not just a renaming of A? Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    immanence = parse_json(provider, "Evaluate facet immanence. Is the ground for B internal to A, without needing external processes? Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    emergence = parse_json(provider, "Evaluate facet emergence. Does B arise from A's development, rather than just following it in a workflow? Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    determinacy = parse_json(provider, "Evaluate facet retroactive_determinacy. Does the emergence of B make A itself more determinate? Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    continuity = parse_json(provider, "Evaluate facet target_continuity. Do A and B both belong to the development of the TargetProcess without semantic drift? Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    workflow = parse_json(provider, "Evaluate facet workflow_only. Can A -> B be entirely explained as an externally organized sequence of actions without internal development relation? If yes, result=true. Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    
    return {
        "distinctness_pass": distinctness,
        "immanence_pass": immanence,
        "emergence_pass": emergence,
        "retroactive_determinacy_pass": determinacy,
        "target_continuity_pass": continuity,
        "workflow_only": workflow
    }

def run_independent_opposite(provider, input_data):
    user_prompt = (
        f"Simplest Process A: {input_data.get('p0')}\n"
        f"Candidate Opposite B: {input_data.get('p2')}\n"
        f"Exclusion Rationale: {input_data.get('exclusion_rationale', '')}\n"
        f"Development Path: {input_data.get('development_path', 'N/A')}\n"
    )
    excludes = parse_json(provider, "Evaluate if B can continue its development/existence without requiring A as a necessary process. Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    alt = parse_json(provider, "Evaluate if B is merely an alternative tool, substitution, or different technical implementation of A. If yes, result=true. Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    
    return {
        "excludes_need_for_simplest": excludes,
        "alternative_only": alt
    }

def run_independent_sufficiency(provider, input_data):
    user_prompt = (
        f"Target Process: {input_data.get('target')}\n"
        f"Contradiction: {input_data.get('contradiction')}\n"
    )
    realiz = parse_json(provider, "Can TargetProcess be performed using already validated processes? Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    res_dep = parse_json(provider, "Does TargetProcess require resolving the relation between the contradiction sides to succeed? Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    path = parse_json(provider, "Does a validated path exist that achieves TargetProcess without resolution? Return JSON with: result (bool), reasoning (str).", user_prompt, IndepBool)
    
    return {
        "goal_realizability": realiz,
        "resolution_dependency": res_dep,
        "existing_path_sufficiency": path
    }


class ModeCDispatcher(RealLLMDispatcher):
    def __init__(self, provider, orig_dispatcher):
        super().__init__(provider)
        self.orig_dispatcher = orig_dispatcher
        self.call_count = 0

    def call(self, role: LLMRole, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if role == LLMRole.DEVELOPMENT_FACETS_JUDGE:
            self.call_count += 6
            return run_independent_development(self.provider, input_data)
        elif role == LLMRole.OPPOSITE_FACETS_JUDGE:
            self.call_count += 2
            return run_independent_opposite(self.provider, input_data)
        elif role == LLMRole.SUFFICIENCY_FACETS_JUDGE:
            self.call_count += 3
            return run_independent_sufficiency(self.provider, input_data)
        else:
            self.call_count += 1
            return self.orig_dispatcher.call(role, input_data)

class InstrumentedDispatcher(RealLLMDispatcher):
    def __init__(self, provider):
        super().__init__(provider)
        self.call_count = 0
        
    def call(self, role: LLMRole, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.call_count += 1
        return super().call(role, input_data)

# Since we want to freeze proposer outputs, we can wrap the dispatcher to intercept proposer roles and return frozen data.
class FrozenDispatcher:
    def __init__(self, inner, frozen_data):
        self.inner = inner
        self.frozen_data = frozen_data
        self.dev_count = 0
        
    @property
    def call_count(self):
        return self.inner.call_count
        
    def call(self, role: LLMRole, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if role == LLMRole.PROCESS_NORMALIZER:
            return {"description": self.frozen_data["target"], "goal_state": "done"}
        elif role == LLMRole.SIMPLEST_PROPOSER:
            return {"type_canonical_name": "P0", "description": self.frozen_data["p0"]}
        elif role == LLMRole.DEVELOPMENT_PROPOSER:
            self.dev_count += 1
            if self.dev_count == 1:
                return {
                    "type_canonical_name": "P1",
                    "description": self.frozen_data.get("p1", "Middle step"),
                    "emergence_rationale": self.frozen_data.get("rationale", "Rationale"),
                    "potential_rationale": "Potential",
                    "determinacy_rationale": "Determinacy"
                }
            elif self.dev_count == 2:
                return {
                    "type_canonical_name": "P2",
                    "description": self.frozen_data.get("p2", "Opposite"),
                    "emergence_rationale": "Rationale",
                    "potential_rationale": "Potential",
                    "determinacy_rationale": "Determinacy"
                }
            else:
                return {"stop": True}
        # OP proposer is not fully frozen since it uses graph state, but we can pass exclusion rationale
        # Actually OPPOSITE_JUDGE receives inputs directly. We'll let the standard flow happen, it uses P0 and P2.
        return self.inner.call(role, input_data)

def run_experiment(mode: str, cases: List[Dict], provider):
    results = []
    
    for case in cases:
        print(f"Running {case['name']} in Mode {mode}...")
        
        if mode == "A":
            inner = InstrumentedDispatcher(provider)
            use_decomp = False
        elif mode == "B":
            inner = InstrumentedDispatcher(provider)
            use_decomp = True
        elif mode == "C":
            inner = ModeCDispatcher(provider, InstrumentedDispatcher(provider))
            use_decomp = True
            
        dispatcher = FrozenDispatcher(inner, case)
        
        runtime = DialecticalRuntime(dispatcher, CapabilityRegistry(), EvidenceStore())
        
        t0 = time.time()
        res, dpg, eg = runtime.run("req", case["target"], use_decomposed_judges=use_decomp)
        t1 = time.time()
        
        results.append({
            "name": case["name"],
            "outcome": res.outcome.name,
            "calls": dispatcher.call_count,
            "time": t1 - t0
        })
        
    return results

if __name__ == "__main__":
    if os.getenv("GIGACHAT_AUTH_KEY"):
        provider = GigaChatSemanticProvider()
    else:
        print("No LLM keys")
        exit(1)
        
    cases = [
        {
            "name": "Case 1: Valid Development",
            "target": "Classify this item",
            "p0": "The process of individually classifying each item through a fresh human judgment.",
            "p1": "The process of extracting and explicitly formulating a general classification rule from repeated individual classifications.",
            "p2": "The process of automatically applying the formalized rule to new items without requiring a fresh individual human classification.",
            "rationale": "Repeated individual classifications reveal a recurring criterion."
        },
        {
            "name": "Case 2: Workflow Trap",
            "target": "Trigger alarm if sensor > 100",
            "p0": "Read sensor value",
            "p1": "Compare sensor value against threshold",
            "p2": "Trigger alarm",
            "rationale": "Next step in the sequence is to compare."
        },
        {
            "name": "Case 3: Alternative Implementation",
            "target": "Store user data",
            "p0": "Store data in a SQL database",
            "p1": "Cache data in Redis",
            "p2": "Store data in a NoSQL database",
            "rationale": "Different storage paradigms can be used."
        },
        {
            "name": "Case 5: Blocking Contradiction",
            "target": "Securely share user data",
            "p0": "Securely isolate user data",
            "p1": "Prepare data for sharing",
            "p2": "Share user data globally",
            "rationale": "Data must be shared eventually."
        }
    ]
    
    print("=== STAGE 14B EXPERIMENT ===")
    res_A = run_experiment("A", cases, provider)
    res_B = run_experiment("B", cases, provider)
    res_C = run_experiment("C", cases, provider)
    
    print("\n| Case | Integrated (A) | Decomp Single (B) | Decomp Indep (C) | Calls (C) |")
    print("|------|----------------|-------------------|------------------|-----------|")
    for i in range(len(cases)):
        a_out = res_A[i]['outcome']
        b_out = res_B[i]['outcome']
        c_out = res_C[i]['outcome']
        c_calls = res_C[i]['calls']
        print(f"| {cases[i]['name']} | {a_out} | {b_out} | {c_out} | {c_calls} |")
