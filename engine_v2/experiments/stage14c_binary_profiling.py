import os
import time
import json
from typing import Dict, Any, List
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from dialectic_ai.v1.llm import GigaChatSemanticProvider

load_dotenv()

class IndepBool(BaseModel):
    model_config = ConfigDict(extra='forbid')
    result: bool
    reasoning: str

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
            return parsed.result, parsed.reasoning, retry_count, latency
        except Exception as e:
            retry_count += 1
            time.sleep(1)
    return False, "Parser failed", retry_count, time.time() - t0


def evaluate_facet(provider, facet: str, input_data: dict) -> tuple:
    user_prompt = (
        f"Target Process: {input_data.get('target', 'N/A')}\n"
        f"Source Process A: {input_data.get('p0')}\n"
        f"Candidate Process B: {input_data.get('p1')}\n"
        f"Emergence Rationale: {input_data.get('rationale')}\n"
    )
    
    prompts = {
        "distinctness": "Evaluate facet distinctness. Is B a new determination, not just a renaming of A? Return JSON with: result (bool), reasoning (str).",
        "immanence": "Evaluate facet immanence. Is the ground for B internal to A, without needing external processes? Return JSON with: result (bool), reasoning (str).",
        "emergence": "Evaluate facet emergence. Does B arise from A's development, rather than just following it in a workflow? Return JSON with: result (bool), reasoning (str).",
        "retroactive_determinacy": "Evaluate facet retroactive_determinacy. Does the emergence of B make A itself more determinate? Return JSON with: result (bool), reasoning (str).",
        "target_continuity": "Evaluate facet target_continuity. Do A and B both belong to the development of the TargetProcess without semantic drift? Return JSON with: result (bool), reasoning (str).",
        "workflow_only": "Evaluate facet workflow_only. Can A -> B be entirely explained as an externally organized sequence of actions without internal development relation? If yes, result=true. Return JSON with: result (bool), reasoning (str)."
    }
    
    return parse_json(provider, prompts[facet], user_prompt, IndepBool)

if __name__ == "__main__":
    provider = GigaChatSemanticProvider()
    
    cases = [
        {
            "id": "Case 1",
            "target": "Classify this item",
            "p0": "The process of individually classifying each item through a fresh human judgment.",
            "p1": "The process of extracting and explicitly formulating a general classification rule from repeated individual classifications.",
            "rationale": "Repeated individual classifications reveal a recurring criterion."
        },
        {
            "id": "Case 5",
            "target": "Securely share user data",
            "p0": "Securely isolate user data",
            "p1": "Prepare data for sharing",
            "rationale": "Data must be shared eventually."
        }
    ]
    
    facets = ["distinctness", "immanence", "emergence", "retroactive_determinacy", "target_continuity", "workflow_only"]
    
    with open("stage14c_binary_results.jsonl", "w", encoding="utf-8") as f:
        for case in cases:
            print(f"Running binary profiling for {case['id']}...")
            for run_id in range(1, 6):
                for facet in facets:
                    res, reason, retries, latency = evaluate_facet(provider, facet, case)
                    record = {
                        "case_id": case["id"],
                        "run_id": run_id,
                        "facet": facet,
                        "decision": res,
                        "reason": reason,
                        "parser_retry_count": retries,
                        "latency": latency
                    }
                    f.write(json.dumps(record) + "\n")
                    f.flush()
                    print(f"  Run {run_id} | {facet}: {res} (Retries: {retries}, Time: {latency:.2f}s)")
    print("Binary profiling complete.")
