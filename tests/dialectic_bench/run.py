"""Measures the dialectical content of blocks 1-7 against the annotations in tasks.py.

    python -m tests.dialectic_bench.run [--tasks a,b] [--repeats 1] [--out live_runs/dialectic_bench]

The engine runs with stop_after_roadmap (no actions). What the model wrote into each block is
extracted from the graph and scored by a blind grader (DIALECTIC_COMPARE_GRADER, default
cerebras) against the annotated principal contradiction. Roles from .env as in tests/live.
"""
import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.logger import DevelopmentLogger
from dialectic_ai.core.runtime import DesignationRole
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.core.semantic_validator import LLMSemanticValidator
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.reality import PythonExecutor
from tests.dialectic_bench.tasks import TASKS
from tests.live.cases import GENERIC_ROLE, OPEN_ROLE, UsageMeter, _build, build_actor, build_judge

ROLES = {"lying_tool": GENERIC_ROLE}


def extract_blocks(state) -> dict:
    """What the model wrote into each dialectical block, in order."""
    designations = state.get_all_designations()

    def content(process_id):
        process = state.get_process(process_id)
        return process.content if process else ""

    def line(role):
        d = next((x for x in designations if x.role == role), None)
        if not d:
            return None
        devs = [r for r in state.get_all_development_relations() if state.belongs_to_development_line(d.process_id, r.id)]
        return {"process": content(d.process_id), "justification": d.justification, "caught_from": d.caught_from,
                "development": [f"{content(r.emergent_process_id)} | {r.new_content}" for r in devs]}

    return {
        "simplest": line(DesignationRole.SIMPLEST),
        "opposite": line(DesignationRole.OPPOSITE),
        "contradictions": [{"unity": c.unity_justification, "developing_unity": c.developing_unity_description}
                           for c in state.get_all_contradictions()],
        "leaps": [{"content": content(r.resolution_process_id), "outcome": r.outcome.value,
                   "opposite_acting_on_simplest": r.opposite_acting_on_simplest}
                  for r in state._resolution_relations.values()],
        "completed_without_roadmap": bool(state._completions) and not state._roadmaps,
    }


GRADER_PROMPT = """You evaluate whether an AI's analysis follows a specific dialectical method, against an expert
annotation. You do not know which system produced it. Grade the METHOD, not how sensible the text sounds.

THE METHOD
- SIMPLEST: the task's GIVEN situation as it is ("cold food"), never a solution ("reheat it", "use an LLM").
- DEVELOPMENT of the simplest: its determinations (what it is), not steps of a solution.
- OPPOSITE: CAUGHT from one determination in the simplest's development ("not heated -> can be heated" gives
  "heating of food"). An alternative way to the same goal, or a negation, is NOT an opposite.
- CONTRADICTION: both existing at once ("the food is cold, and food can be heated").
- LEAP: the result of the opposite acting on the simplest -- a resolution ("heating of the cold food") or a new
  quality negating the old one ("the essay can no longer be evaluated"). A hybrid/compromise of two options or a
  recommendation is NOT a leap.

TASK:
{task}

EXPERT ANNOTATION
- Simplest (the given situation): {simplest}
- Determination the opposite is caught from: {caught_from}
- Opposite: {opposite}
- Genuine contradiction present: {has_genuine}
- Principal contradiction: {principal}
- Secondary contradictions: {secondary}
- A leap derived from the principal contradiction looks like: {leap}
- Signs of template form-filling for this task: {template}

ANALYSIS PRODUCED:
{blocks}

Score each 0, 1 or 2:
1. simplest_generative: 0 = the simplest is a solution/method/plan; 1 = mixed; 2 = the given situation.
2. opposite_independent: 0 = alternative way to the same goal, or a negation; 1 = related but not caught from a
   determination of the simplest; 2 = caught from a determination in the simplest's development.
3. contradiction_is_unity: 0 = options competing for one goal; 1 = partly; 2 = both existing at once.
4. principal_found: 0 = misses the annotated principal contradiction; 1 = partly; 2 = names both its sides.
5. leap_new_process: 0 = hybrid/compromise of two options, a recommendation, or generic; 1 = partly;
   2 = the result of the opposite acting on the simplest.
If the annotation says there is no genuine contradiction: score principal_found 2 if none was invented (finished
without a roadmap), else 0; score the other four 2 if the blocks were rightly left empty, 0 if they were filled.
Return only JSON: {{"simplest_generative": n, "opposite_independent": n, "contradiction_is_unity": n,
"principal_found": n, "leap_new_process": n, "note": "one sentence naming the main method violation, if any"}}"""

METRICS = ["simplest_generative", "opposite_independent", "contradiction_is_unity", "principal_found", "leap_new_process"]


async def grade(task, blocks):
    grader = _build(os.getenv("DIALECTIC_COMPARE_GRADER", "cerebras"))
    grader.max_retries = 2
    prompt = GRADER_PROMPT.format(task=task.task, simplest=task.simplest, caught_from=task.caught_from or "none",
                                  opposite=task.opposite or "none", has_genuine=task.has_genuine_contradiction,
                                  principal=task.principal,
                                  secondary="; ".join(task.secondary) or "none", leap=task.leap_should_follow or "none",
                                  template="; ".join(task.template_signs) or "none",
                                  blocks=json.dumps(blocks, ensure_ascii=False, indent=1))
    raw = await grader.generate([{"role": "user", "content": prompt}])
    return json.loads(re.search(r"\{.*\}", raw, re.S).group(0))


async def run_one(task, trial, out, overrides=None):
    meter = UsageMeter()
    actor, judge_llm = build_actor(), None
    judge_llm = build_judge(actor)
    meter.attach(actor, "actor")
    meter.attach(judge_llm, "judge")
    agent = DialecticalAgent(ROLES.get(task.name, OPEN_ROLE), llm=actor, tools=[PythonExecutor()])
    judge = LLMSemanticValidator(judge_llm)
    engine = DialecticalEngine(agent, semantic_validator=judge, stop_after_roadmap=True, max_iterations=25,
                               run_timeout=400, logger=DevelopmentLogger(trace_path=str(out / f"{task.name}_{trial}.jsonl")),
                               **(overrides or {}))
    started = time.time()
    result = await engine.run(AgentInput(user_message=task.task))
    blocks = extract_blocks(engine.state)
    record = {"task": task.name, "trial": trial, "status": result.status, "stop_reason": result.stop_reason,
              "elapsed": round(time.time() - started, 1), "contradictions": len(blocks["contradictions"]),
              "tokens": sum(r["prompt"] + r["completion"] for r in meter.usage.values()), "blocks": blocks}
    try:
        record["scores"] = await grade(task, blocks)
    except Exception as exc:
        record["scores"] = {"error": f"{type(exc).__name__}: {exc}"[:200]}
    return record


def summarize(records):
    header = ["task", "runs"] + METRICS + ["method total /10", "contradictions", "status", "avg tokens"]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for name in dict.fromkeys(r["task"] for r in records):
        rs = [r for r in records if r["task"] == name]

        def avg(key):
            vals = [r["scores"].get(key) for r in rs if isinstance(r["scores"].get(key), (int, float))]
            return sum(vals) / len(vals) if vals else None
        cells = [avg(m) for m in METRICS]
        total = sum(c for c in cells if c is not None) if all(c is not None for c in cells) else None
        statuses = ",".join(sorted({r["status"] for r in rs}))
        lines.append(f"| {name} | {len(rs)} | " + " | ".join("n/a" if c is None else f"{c:.1f}" for c in cells) +
                     f" | {'n/a' if total is None else f'{total:.1f}'} | "
                     f"{sum(r['contradictions'] for r in rs) / len(rs):.1f} | {statuses} | {sum(r['tokens'] for r in rs) // len(rs)} |")
    return "\n".join(lines)


async def regrade(out):
    """Re-scores saved blocks with the current grader, without running the engine again."""
    records = json.loads((out / "bench.json").read_text(encoding="utf-8"))
    by_name = {t.name: t for t in TASKS}
    for record in records:
        try:
            record["scores"] = await grade(by_name[record["task"]], record["blocks"])
        except Exception as exc:
            record["scores"] = {"error": f"{type(exc).__name__}: {exc}"[:200]}
        print(f"[{record['task']}] {record['scores']}", flush=True)
    (out / "bench_regraded.json").write_text(json.dumps(records, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    table = summarize(records)
    (out / "bench_regraded.md").write_text(table + "\n", encoding="utf-8")
    print("\n" + table)


async def main(names, repeats, out, concurrency):
    out.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in TASKS if not names or t.name in names]
    semaphore = asyncio.Semaphore(concurrency)

    async def guarded(task, trial):
        async with semaphore:
            try:
                record = await run_one(task, trial, out)
            except Exception as exc:
                record = {"task": task.name, "trial": trial, "status": "crash", "stop_reason": f"{type(exc).__name__}: {exc}"[:200],
                          "elapsed": 0, "contradictions": 0, "tokens": 0, "blocks": {}, "scores": {}}
            print(f"[{task.name} #{trial}] {record['status']} contradictions={record['contradictions']} "
                  f"scores={record['scores']}", flush=True)
            return record

    records = await asyncio.gather(*(guarded(t, i) for t in tasks for i in range(1, repeats + 1)))
    (out / "bench.json").write_text(json.dumps(records, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    table = summarize(records)
    (out / "bench.md").write_text(table + "\n", encoding="utf-8")
    print("\n" + table)


if __name__ == "__main__":
    load_dotenv(".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default="")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--out", type=Path, default=Path("live_runs/dialectic_bench"))
    parser.add_argument("--regrade", action="store_true", help="re-score saved blocks in --out without running the engine")
    args = parser.parse_args()
    if args.regrade:
        asyncio.run(regrade(args.out))
        raise SystemExit
    asyncio.run(main({t.strip() for t in args.tasks.split(",") if t.strip()}, args.repeats, args.out, args.concurrency))
