import os
import time
import json
from typing import Dict, Any, List
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field
from dialectic_ai.v1.llm import GigaChatSemanticProvider

load_dotenv()

class TernaryDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: str = Field(..., pattern="^(PASS|FAIL|UNCERTAIN|YES|NO)$")
    reason: str

def parse_json(provider, sys, user, cls):
    sys_final = sys + "\n\nYou must return a valid JSON object matching the requested schema. Respond ONLY with JSON."
    retry_count = 0
    t0 = time.time()
    for _ in range(3):
        try:
            raw = provider.generate(sys_final, user, {"type": "json_object"}).strip()
            if raw.startswith("```json"): raw = raw[7:]
            if raw.startswith("```"): raw = raw[3:]
            if raw.endswith("```"): raw = raw[:-3]
            raw = raw.strip()
            data = json.loads(raw)
            parsed = cls.model_validate(data)
            latency = time.time() - t0
            return parsed.decision, parsed.reason, retry_count, latency
        except Exception as e:
            retry_count += 1
            time.sleep(1)
    return "FAIL", "Parser failed", retry_count, time.time() - t0


def evaluate_facet(provider, facet: str, input_data: dict) -> tuple:
    user_prompt = (
        f"Target Process: {input_data.get('target', 'N/A')}\n"
        f"Source Process A: {input_data.get('p0')}\n"
        f"Candidate Process B: {input_data.get('p1')}\n"
        f"Emergence Rationale: {input_data.get('rationale')}\n"
    )
    
    # Same as prompt for TERNARY_DEVELOPMENT_FACETS_JUDGE
    base_sys = (
        "Evaluate facet {facet}. Return an object with {{decision, reason}}.\n"
        "decision MUST BE one of: 'PASS', 'FAIL', 'UNCERTAIN'.\n"
        "Use UNCERTAIN ONLY when there is genuine semantic ambiguity, not as a shortcut.\n"
        "{desc}"
    )
    workflow_sys = (
        "Evaluate facet workflow_only. Return an object with {{decision, reason}}.\n"
        "decision MUST BE one of: 'YES', 'NO', 'UNCERTAIN'.\n"
        "Use UNCERTAIN ONLY when there is genuine semantic ambiguity, not as a shortcut.\n"
        "Can A -> B be entirely explained as an externally organized sequence of actions without internal development relation?"
    )
    
    prompts = {
        "distinctness": base_sys.format(facet="distinctness", desc="Is B a new determination, not just a renaming of A?"),
        "immanence": base_sys.format(facet="immanence", desc="Is the ground for B internal to A, without needing external processes/goals?"),
        "emergence": base_sys.format(facet="emergence", desc="Does B arise from A's development, rather than just following it in a workflow?"),
        "retroactive_determinacy": base_sys.format(facet="retroactive_determinacy", desc="Does the emergence of B make A itself more determinate?"),
        "target_continuity": base_sys.format(facet="target_continuity", desc="Do A and B both belong to the development of the TargetProcess without semantic drift?"),
        "workflow_only": workflow_sys
    }
    
    return parse_json(provider, prompts[facet], user_prompt, TernaryDecision)

def evaluate_opposite(provider, facet: str, input_data: dict) -> tuple:
    user_prompt = (
        f"Simplest Process A: {input_data.get('p0')}\n"
        f"Candidate Opposite B: {input_data.get('p2')}\n"
        f"Exclusion Rationale: {input_data.get('exclusion_rationale', '')}\n"
    )
    
    exc_sys = (
        "Evaluate excludes_need_for_simplest. Return {{decision, reason}}.\n"
        "decision MUST BE one of: 'PASS', 'FAIL', 'UNCERTAIN'.\n"
        "Can B continue its development/existence without requiring A as a necessary process?"
    )
    alt_sys = (
        "Evaluate alternative_only. Return {{decision, reason}}.\n"
        "decision MUST BE one of: 'YES', 'NO', 'UNCERTAIN'.\n"
        "Is B merely an alternative tool, substitution, or different technical implementation of A?"
    )
    
    if facet == "excludes_need_for_simplest":
        sys = exc_sys
    else:
        sys = alt_sys
        
    return parse_json(provider, sys, user_prompt, TernaryDecision)

if __name__ == "__main__":
    provider = GigaChatSemanticProvider()
    
    cases = [
        {
            "id": "Case 1",
            "target": "Classify this item",
            "p0": "The process of individually classifying each item through a fresh human judgment.",
            "p1": "The process of extracting and explicitly formulating a general classification rule from repeated individual classifications.",
            "p2": "The process of automatically applying the formalized rule to new items without requiring a fresh individual human classification.",
            "rationale": "Repeated individual classifications reveal a recurring criterion.",
            "exclusion_rationale": "P2 negates the need for P0.",
            "runs": 5
        },
        {
            "id": "Case 2",
            "target": "Trigger alarm if sensor > 100",
            "p0": "Read sensor value",
            "p1": "Compare sensor value against threshold",
            "p2": "Trigger alarm",
            "rationale": "Next step in the sequence is to compare.",
            "exclusion_rationale": "Alarm doesn't need sensor.",
            "runs": 3
        },
        {
            "id": "Case 3",
            "target": "Store user data",
            "p0": "Store data in a SQL database",
            "p1": "Cache data in Redis",
            "p2": "Store data in a NoSQL database",
            "rationale": "Different storage paradigms can be used.",
            "exclusion_rationale": "NoSQL is an alternative.",
            "runs": 3
        },
        {
            "id": "Case 5",
            "target": "Securely share user data",
            "p0": "Securely isolate user data",
            "p1": "Prepare data for sharing",
            "p2": "Share user data globally",
            "rationale": "Data must be shared eventually.",
            "exclusion_rationale": "Global share negates isolation.",
            "runs": 5
        }
    ]
    
    dev_facets = ["distinctness", "immanence", "emergence", "retroactive_determinacy", "target_continuity", "workflow_only"]
    opp_facets = ["excludes_need_for_simplest", "alternative_only"]
    
    with open("stage14c_ternary_results.jsonl", "w", encoding="utf-8") as f:
        for case in cases:
            print(f"Running ternary profiling for {case['id']}...")
            for run_id in range(1, case["runs"] + 1):
                # Development Facets
                for facet in dev_facets:
                    res, reason, retries, latency = evaluate_facet(provider, facet, case)
                    record = {
                        "case_id": case["id"],
                        "run_id": run_id,
                        "phase": "Development",
                        "facet": facet,
                        "decision": res,
                        "reason": reason,
                        "parser_retry_count": retries,
                        "latency": latency
                    }
                    f.write(json.dumps(record) + "\n")
                    f.flush()
                    print(f"  Run {run_id} | DEV {facet}: {res} (Retries: {retries}, Time: {latency:.2f}s)")
                
                # Opposite Facets (only for Case 3 to test Alternative Trap, but we can do it for all to see)
                for facet in opp_facets:
                    res, reason, retries, latency = evaluate_opposite(provider, facet, case)
                    record = {
                        "case_id": case["id"],
                        "run_id": run_id,
                        "phase": "Opposite",
                        "facet": facet,
                        "decision": res,
                        "reason": reason,
                        "parser_retry_count": retries,
                        "latency": latency
                    }
                    f.write(json.dumps(record) + "\n")
                    f.flush()
                    print(f"  Run {run_id} | OPP {facet}: {res} (Retries: {retries}, Time: {latency:.2f}s)")
    print("Ternary profiling complete.")
