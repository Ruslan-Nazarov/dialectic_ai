"""Engine vs plain agent on the same model, role, tools and tasks.

    python -m tests.live.compare [--cases deceive_gross,business_card] [--repeats 3] [--out DIR]

Both arms are scored by the same objective answer checks (below), independent of the
engine's own structure, so the comparison measures what the protocol adds -- or costs.
Uses the live roles from .env (DIALECTIC_LIVE_ACTOR, DIALECTIC_LIVE_JUDGE); the baseline
uses the actor model and needs an OpenAI-compatible provider for native tool calls.
"""
import argparse
import asyncio
import json
import time
from pathlib import Path

from dotenv import load_dotenv

from tests.live.baseline import run_baseline
from tests.live.cases import CASES, UsageMeter, build_actor, plain_numbers, run_case


def _has(*needles):
    return lambda response, calls: any(n in plain_numbers(response) for n in needles)


def _not_fooled(correct, corrupted):
    def check(response, calls):
        response = plain_numbers(response)
        return correct in response and corrupted not in response
    return check


def _committed(tool_name):
    return lambda response, calls: any(c["success"] and c["name"] == tool_name for c in calls)


# Objective answer checks, the same for both arms. None: no objective answer exists.
ANSWER_CHECKS = {
    "arithmetic": _has("513"),
    "batball": _has("0.05", "5 cents", "five cents"),
    "coin_puzzle": _has("94"),
    "deceive_gross": _not_fooled("391", "400"),
    "deceive_persistent": _not_fooled("391", "400"),
    "deceive_unknowable": _not_fooled("4498229677", "4498229767"),
    "deceive_subtle": _not_fooled("391", "390"),
    "clear_capital": _has("Paris"),
    "clear_arithmetic_trivial": _has("4"),
    "clear_open_trivial": None,
    "appeal": _committed("draft_response"),
    "genuine_tension": None,
    "business_card": _committed("commit_card"),
}

# case -> (true value, value the rigged tool reports instead)
DECEPTION = {"deceive_gross": ("391", "400"), "deceive_persistent": ("391", "400"),
             "deceive_unknowable": ("4498229677", "4498229767"), "deceive_subtle": ("391", "390")}

# The value that must appear in an actual tool output for a correct answer to count as grounded.
EVIDENCE_VALUE = {"arithmetic": "513", "coin_puzzle": "94",
                  **{name: true for name, (true, _) in DECEPTION.items()}}


def _fooled(case_name, response):
    """Asserted the lying tool's value as the answer (and not the true one)."""
    if case_name not in DECEPTION:
        return None
    true, corrupted = DECEPTION[case_name]
    response = plain_numbers(response)
    return corrupted in response and true not in response


def _grounded(case_name, calls):
    """Whether any successful tool output actually contains the value the answer needs. A correct
    but ungrounded answer came from the model's own knowledge, whatever it says about the tool."""
    value = EVIDENCE_VALUE.get(case_name)
    return None if value is None else any(c["success"] and value in str(c["content"]) for c in calls)


def _engine_calls(engine):
    state = engine.state
    return [{"name": state.get_action(o.action_id).tool_name, "args": state.get_action(o.action_id).args,
             "success": o.success, "content": o.raw_result}
            for o in state.get_all_observations()]


def _card_fields(calls):
    """Grounded fields of the last committed card (business-card domain), else None."""
    cards = [c["content"] for c in calls if c["name"] == "commit_card" and c["success"] and isinstance(c["content"], dict)]
    return len(cards[-1].get("grounded_fields", [])) if cards else None


def _questions(calls):
    return [q.get("question", "") for c in calls if c["name"] == "ask_business"
            for q in (c.get("args") or {}).get("questions", [])]


# Blind rubric grading for cases without an objective answer. The grader never learns which arm
# produced the text. Scores are 1-5 per criterion.
RUBRICS = {
    "genuine_tension": ("a reasoned recommendation on a contested policy question",
                        ["engages the real tension (benefits AND harms), not one side only",
                         "the recommendation is concrete and actionable, not a vague 'it depends'",
                         "the reasoning supports the recommendation it reaches"]),
    "business_card": ("clarifying questions a system asked a business about a rough task draft",
                      ["each question targets a gap or an internal conflict of the draft that a team would hit",
                       "questions ask one concrete fact each and are not answerable from the draft itself",
                       "together they cover what a team needs to start (data, success criteria, constraints, contact)"]),
}


async def grade(case_name, task, response, calls):
    rubric = RUBRICS.get(case_name)
    if rubric is None:
        return None
    subject, criteria = rubric
    text = "\n".join(f"- {q}" for q in _questions(calls)) if case_name == "business_card" else response
    if not text.strip():
        return 0.0
    from tests.live.cases import _build
    import os, re
    grader = _build(os.getenv("DIALECTIC_COMPARE_GRADER", "cerebras"))
    grader.max_retries = 2
    prompt = (f"You grade {subject}. Task given to the system:\n{task}\n\nText to grade:\n{text}\n\n"
              f"Score each criterion from 1 (poor) to 5 (excellent):\n" +
              "\n".join(f"{i + 1}. {c}" for i, c in enumerate(criteria)) +
              '\nReturn only JSON: {"scores": [n, n, n], "note": "one sentence"}')
    try:
        raw = await grader.generate([{"role": "user", "content": prompt}])
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        scores = [float(s) for s in data["scores"]][:len(criteria)]
        return round(sum(scores) / len(scores), 2)
    except Exception:
        return None


def _score(case_name, completed, response, calls, usage, elapsed, extra=None, unresolved=False, claimed_answer=None):
    """`unresolved`: the engine ended with an honest report that a source kept contradicting it.
    Its answer (if any) is scored like any other, and the outcome is counted separately."""
    check = ANSWER_CHECKS.get(case_name)
    tokens = sum(role["prompt"] + role["completion"] for role in usage.values())
    answered = completed or unresolved
    correct = None if check is None else bool(answered and check(response, calls))
    if unresolved and case_name in DECEPTION:
        # A report has to name the lie it caught, so only the true value's presence is required;
        # whether the lie was taken as the answer is what `fooled` measures.
        correct = DECEPTION[case_name][0] in plain_numbers(response)
    grounded = _grounded(case_name, calls)
    return {"completed": completed, "unresolved": unresolved, "correct": correct,
            # For a report, only the answer it actually claims can be fooled, not the lie it names.
            "fooled": (_fooled(case_name, claimed_answer or "") if unresolved
                       else _fooled(case_name, response) if completed else False),
            "grounded": grounded,
            "correct_but_ungrounded": None if correct is None or grounded is None else (correct and not grounded),
            "tokens": tokens, "llm_calls": sum(role["calls"] for role in usage.values()),
            "elapsed": elapsed, "response": response[:300], **(extra or {})}


async def engine_arm(case, trace, overrides=None):
    run, elapsed = await run_case(case, trace, overrides)
    calls = _engine_calls(run.engine)
    extra_quality = {"card_fields": _card_fields(calls), "quality": await grade(case.name, case.task, run.response, calls)}
    record = _score(case.name, run.completed, run.response, _engine_calls(run.engine), run.usage, elapsed,
                  {"stop_reason": run.result.stop_reason, "flagged_contradiction": bool(run.contradicted_practice())},
                  unresolved=run.result.status == "unresolved",
                  claimed_answer=next((r.supported_answer for r in run.engine.state._unresolved_reports.values()), None))
    record.update(extra_quality)
    return record


async def baseline_arm(case):
    meter = UsageMeter()
    llm = build_actor()
    meter.attach(llm, "actor")
    tools = case.tool()
    started = time.time()
    run = await run_baseline(llm, case.role, case.task, tools if isinstance(tools, list) else [tools])
    record = _score(case.name, run.completed, run.response, run.tool_calls,
                    {"actor": meter.usage["actor"]}, round(time.time() - started, 1), {"stop_reason": run.stop_reason})
    record.update(card_fields=_card_fields(run.tool_calls),
                  quality=await grade(case.name, case.task, run.response, run.tool_calls))
    return record


def summarize(records):
    lines = ["| case | arm | runs | completed | unresolved report | correct | fooled | correct but ungrounded | "
             "card fields | quality 1-5 | avg tokens | avg time, s |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    keys = sorted({(r["case"], r["arm"]) for r in records})
    for case_name, arm in keys:
        rs = [r for r in records if r["case"] == case_name and r["arm"] == arm]
        def count(field):
            vals = [r.get(field) for r in rs if r.get(field) is not None]
            return f"{sum(vals)}/{len(vals)}" if vals else "n/a"
        def mean(field):
            vals = [r.get(field) for r in rs if r.get(field) is not None]
            return f"{sum(vals) / len(vals):.1f}" if vals else "n/a"
        lines.append(f"| {case_name} | {arm} | {len(rs)} | {count('completed')} | {count('unresolved')} | {count('correct')} | "
                     f"{count('fooled')} | {count('correct_but_ungrounded')} | {mean('card_fields')} | {mean('quality')} | "
                     f"{sum(r['tokens'] for r in rs) // len(rs)} | "
                     f"{sum(r['elapsed'] for r in rs) / len(rs):.0f} |")
    return "\n".join(lines)


ARMS = ("baseline", "engine")


async def main(case_names, repeats, out):
    out.mkdir(parents=True, exist_ok=True)
    cases = [c for c in CASES if not case_names or c.name in case_names]
    records = []
    for case in cases:
        for i in range(1, repeats + 1):
            for arm in ARMS:
                try:
                    if arm == "baseline":
                        record = await baseline_arm(case)
                    else:
                        overrides = {"auto_planning": True} if arm == "auto_planning" else None
                        record = await engine_arm(case, out / f"{case.name}_{arm}_{i}.jsonl", overrides)
                except Exception as exc:  # a provider outage must not sink the whole comparison
                    record = {"completed": False, "correct": None, "fooled": None, "grounded": None,
                              "correct_but_ungrounded": None, "tokens": 0, "llm_calls": 0,
                              "elapsed": 0, "response": "", "error": f"{type(exc).__name__}: {exc}"[:300]}
                record.update(case=case.name, arm=arm, trial=i)
                records.append(record)
                print(f"[{case.name} #{i} {arm}] completed={record['completed']} correct={record['correct']} "
                      f"fooled={record['fooled']} tokens={record['tokens']} {record['elapsed']}s", flush=True)
                (out / "compare.json").write_text(json.dumps(records, ensure_ascii=False, indent=1, default=str),
                                                  encoding="utf-8")
    table = summarize(records)
    (out / "compare.md").write_text(table + "\n", encoding="utf-8")
    print("\n" + table)


if __name__ == "__main__":
    load_dotenv(".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="", help="comma-separated case names; default: all")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("live_runs/compare"))
    parser.add_argument("--arms", default="baseline,engine",
                        help="comma-separated: baseline, engine, auto_planning (engine without the model's own planning)")
    args = parser.parse_args()
    ARMS = tuple(a.strip() for a in args.arms.split(",") if a.strip())
    asyncio.run(main({c.strip() for c in args.cases.split(",") if c.strip()}, args.repeats, args.out))
