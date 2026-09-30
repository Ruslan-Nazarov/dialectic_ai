"""One ContractNLI case through the full engine (blocks + practice) and, for reference, a plain model answer.

    python contract_nli_runs/run_one.py --help
"""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine_v2"))
load_dotenv(ROOT / ".env")

HERE = Path(__file__).resolve().parent
TASK = """Here is a non-disclosure agreement:
<<<
{text}
>>>
Statement: "{hypothesis}"
Does the agreement entail this statement, contradict it, or not mention it? Answer with exactly one of
Entailment / Contradiction / NotMentioned and quote the clause(s) of the agreement that decide it."""


def verdict(text):
    found = re.findall(r"\b(Entailment|Contradiction|NotMentioned|Not Mentioned)\b", text or "")
    return found[-1].replace(" ", "") if found else "?"


async def main(doc_id, key, dataset, output_dir):
    trace = output_dir / f"doc{doc_id}_{key}.jsonl"
    result_path = output_dir / f"doc{doc_id}_{key}.result.json"
    if trace.exists() or result_path.exists():
        raise FileExistsError("Refusing to overwrite a trace or result; choose a new --out-dir")
    data = json.loads(dataset.read_text(encoding="utf-8"))
    from dialectic_ai.agent import DialecticalAgent
    from dialectic_ai.core.logger import DevelopmentLogger
    from dialectic_ai.core.schema import AgentInput
    from dialectic_ai.core.semantic_validator import LLMSemanticValidator
    from dialectic_ai.engine import DialecticalEngine
    from dialectic_ai.reality import PythonExecutor
    from tests.live.cases import OPEN_ROLE, UsageMeter, build_actor, build_judge
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = next(d for d in data["documents"] if d["id"] == doc_id)
    gold = doc["annotation_sets"][0]["annotations"][key]
    hypothesis = data["labels"][key]["hypothesis"]
    task = TASK.format(text=doc["text"].strip(), hypothesis=hypothesis)
    evidence = [doc["text"][slice(*doc["spans"][i])] for i in gold["spans"]]

    # Reference: the same model, one plain call.
    plain = build_actor()
    plain_answer = await plain.generate([{"role": "user", "content": task + "\nReturn only JSON: {\"answer\": \"...\"}"}])

    meter = UsageMeter()
    actor = build_actor()
    judge_llm = build_judge(actor)
    meter.attach(actor, "actor")
    meter.attach(judge_llm, "judge")
    engine = DialecticalEngine(DialecticalAgent(OPEN_ROLE, llm=actor, tools=[PythonExecutor()]),
                               semantic_validator=LLMSemanticValidator(judge_llm), block_planning=True,
                               max_iterations=25, run_timeout=1200, logger=DevelopmentLogger(trace_path=str(trace)))
    started = time.time()
    result = await engine.run(AgentInput(user_message=task))
    report = {
        "doc": doc_id, "hypothesis": key, "gold": gold["choice"], "gold_evidence": evidence,
        "engine": {"status": result.status, "stop_reason": result.stop_reason, "verdict": verdict(result.response),
                   "response": result.response, "elapsed_s": round(time.time() - started),
                   "tokens": {k: v["prompt"] + v["completion"] for k, v in meter.usage.items()}},
        "plain": {"verdict": verdict(plain_answer), "response": plain_answer},
        "trace": str(trace),
    }
    result_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("gold",)} | {"engine": report["engine"]["verdict"],
                     "engine_status": result.status, "plain": report["plain"]["verdict"],
                     "elapsed_s": report["engine"]["elapsed_s"], "tokens": report["engine"]["tokens"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Historical v2 case; requires archived v2 dependencies and a live provider")
    parser.add_argument("doc_id", nargs="?", type=int, default=446)
    parser.add_argument("hypothesis_key", nargs="?", default="nda-7")
    parser.add_argument("--dataset", type=Path, default=ROOT / "experiments/grounding_vs_calibration/data/contract-nli/test.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "scratch/contract_nli_v2")
    args = parser.parse_args()
    asyncio.run(main(args.doc_id, args.hypothesis_key, args.dataset, args.out_dir))
