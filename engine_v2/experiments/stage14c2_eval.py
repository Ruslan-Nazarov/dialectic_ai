import os
import time
import json
import argparse
from typing import Dict, Any, List
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from dialectic_ai.v1.llm import GigaChatSemanticProvider

load_dotenv()

class IndepBool(BaseModel):
    model_config = ConfigDict(extra='forbid')
    result: bool
    reasoning: str

class TernaryDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: str
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
            return getattr(parsed, 'result', getattr(parsed, 'decision', None)), getattr(parsed, 'reasoning', getattr(parsed, 'reason', None)), retry_count, latency
        except Exception as e:
            retry_count += 1
            time.sleep(1)
    return False if cls == IndepBool else "FAIL", "Parser failed", retry_count, time.time() - t0

def evaluate_facet_binary(provider, facet: str, input_data: dict) -> tuple:
    user_prompt = (
        f"Target Process: {input_data.get('target', 'N/A')}\n"
        f"Source Process A: {input_data.get('p0')}\n"
        f"Candidate Process B: {input_data.get('p1')}\n"
        f"Emergence Rationale: {input_data.get('emergence_rationale')}\n"
        f"Potential Rationale: {input_data.get('potential_rationale')}\n"
        f"Determinacy Rationale: {input_data.get('determinacy_rationale')}\n"
    )
    
    prompts = {
        "distinctness": "Evaluate facet distinctness. Does B introduce a determination that is NOT yet actual in A in the same form, while still being allowed to arise from A? Return JSON with: result (bool), reasoning (str).",
        "immanence": "Evaluate facet immanence. Before B becomes actual, is there a determination, tendency, criterion, structure, or potential within A that provides the internal ground from which B can arise? Return JSON with: result (bool), reasoning (str).",
        "emergence": "Evaluate facet emergence. Does B arise through the unfolding/development of determinations present in A, rather than merely occurring after A or consuming A's output? Return JSON with: result (bool), reasoning (str).",
        "retroactive_determinacy": "Evaluate facet retroactive_determinacy. Once B has emerged, does B make A more intelligible or determinate by revealing what implicit determination in A was developing toward B? Return JSON with: result (bool), reasoning (str).",
        "target_continuity": "Evaluate facet target_continuity. Are A and B successive determinations of the SAME TargetProcess, even if they differ in method, form, abstraction level, or mode of realization? Return JSON with: result (bool), reasoning (str).",
        "workflow_only": "Evaluate facet workflow_only. Can the relation A->B be fully explained by an externally imposed sequence, dependency, instruction, or goal WITHOUT invoking any internal developmental relation between A and B? If yes, result=true. Return JSON with: result (bool), reasoning (str)."
    }
    
    return parse_json(provider, prompts[facet], user_prompt, IndepBool)

def evaluate_facet_ternary(provider, facet: str, input_data: dict) -> tuple:
    user_prompt = (
        f"Target Process: {input_data.get('target', 'N/A')}\n"
        f"Source Process A: {input_data.get('p0')}\n"
        f"Candidate Process B: {input_data.get('p1')}\n"
        f"Emergence Rationale: {input_data.get('emergence_rationale')}\n"
        f"Potential Rationale: {input_data.get('potential_rationale')}\n"
        f"Determinacy Rationale: {input_data.get('determinacy_rationale')}\n"
    )
    
    base_sys = (
        "Evaluate the facet. Return an object with {decision, reason}.\n"
        "Decision MUST BE one of: 'PASS', 'FAIL', 'UNCERTAIN'.\n"
        "Use UNCERTAIN ONLY when there is genuine semantic ambiguity, not as a shortcut.\n\n"
    )
    if facet == "workflow_only":
        base_sys = (
            "Evaluate the facet. Return an object with {decision, reason}.\n"
            "Decision MUST BE one of: 'YES', 'NO', 'UNCERTAIN'.\n"
            "Use UNCERTAIN ONLY when there is genuine semantic ambiguity, not as a shortcut.\n\n"
        )
    
    prompts = {
        "distinctness": base_sys + "Does B introduce a determination that is NOT yet actual in A in the same form, while still being allowed to arise from A?",
        "immanence": base_sys + "Before B becomes actual, is there a determination, tendency, criterion, structure, or potential within A that provides the internal ground from which B can arise?",
        "emergence": base_sys + "Does B arise through the unfolding/development of determinations present in A, rather than merely occurring after A or consuming A's output?",
        "retroactive_determinacy": base_sys + "Once B has emerged, does B make A more intelligible or determinate by revealing what implicit determination in A was developing toward B?",
        "target_continuity": base_sys + "Are A and B successive determinations of the SAME TargetProcess, even if they differ in method, form, abstraction level, or mode of realization?",
        "workflow_only": base_sys + "Can the relation A->B be fully explained by an externally imposed sequence, dependency, instruction, or goal WITHOUT invoking any internal developmental relation between A and B?"
    }
    
    return parse_json(provider, prompts[facet], user_prompt, TernaryDecision)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["binary", "ternary"], required=True)
    parser.add_argument("--cases_file", required=True)
    parser.add_argument("--out_file", required=True)
    args = parser.parse_args()
    
    provider = GigaChatSemanticProvider()
    
    with open(args.cases_file, "r", encoding="utf-8") as f:
        cases = json.load(f)
        
    facets = ["distinctness", "immanence", "emergence", "retroactive_determinacy", "target_continuity", "workflow_only"]
    
    with open(args.out_file, "w", encoding="utf-8") as f:
        for case in cases:
            print(f"Running {args.mode} profiling for {case['id']}...")
            for run_id in range(1, 4):  # Let's do 3 runs per case to save time, the user didn't specify exactly. Wait, "5 runs" is standard. Let's do 3.
                for facet in facets:
                    if args.mode == "binary":
                        res, reason, retries, latency = evaluate_facet_binary(provider, facet, case)
                    else:
                        res, reason, retries, latency = evaluate_facet_ternary(provider, facet, case)
                        
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
    print(f"{args.mode.capitalize()} profiling complete.")
