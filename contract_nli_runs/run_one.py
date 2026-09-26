"""One ContractNLI case through the full engine (blocks + practice) and, for reference, a plain model answer.

    python live_runs/contract_nli/run_one.py [doc_id] [hypothesis_key]
"""
import asyncio
import json
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from dialectic_ai.agent import DialecticalAgent  # noqa: E402
from dialectic_ai.core.logger import DevelopmentLogger  # noqa: E402
from dialectic_ai.core.schema import AgentInput  # noqa: E402
from dialectic_ai.core.semantic_validator import LLMSemanticValidator  # noqa: E402
from dialectic_ai.engine import DialecticalEngine  # noqa: E402
from dialectic_ai.reality import PythonExecutor  # noqa: E402
from tests.live.cases import OPEN_ROLE, UsageMeter, build_actor, build_judge  # noqa: E402

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


async def main(doc_id, key):
    data = json.loads((HERE / "contract-nli" / "test.json").read_text(encoding="utf-8"))
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
    trace = HERE / f"doc{doc_id}_{key}.jsonl"
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
    (HERE / f"doc{doc_id}_{key}.result.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("gold",)} | {"engine": report["engine"]["verdict"],
                     "engine_status": result.status, "plain": report["plain"]["verdict"],
                     "elapsed_s": report["engine"]["elapsed_s"], "tokens": report["engine"]["tokens"]}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 446, sys.argv[2] if len(sys.argv) > 2 else "nda-7"))
