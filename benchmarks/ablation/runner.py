"""
benchmarks/ablation/runner.py

Runs one or more deliberate-failure-injection scenarios (scenarios.py) through THREE conditions
against the SAME real LLM:
  - "bare"       -- BareAgentLoop: no repair, no nudge, no dedup, no Rule 5 prompt.
  - "engineered" -- EngineeredAgentLoop: the SAME generic robustness engineering
                    DialecticalEngine has (empty-turn nudge, duplicate-action detection, one
                    minimal JSON-repair retry) but NONE of the dialectical vocabulary.
  - "framework"  -- the real DialecticalAgent/DialecticalEngine.

The three-way design exists specifically to answer "does dialectics itself matter, or just
having robustness engineering at all" (see engineered_agent.py's own DIALECTICAL DESCRIPTION):
bare-vs-engineered isolates generic engineering's contribution; engineered-vs-framework isolates
the dialectical method's OWN marginal contribution on top of that engineering -- the number that
actually answers the question, not bare-vs-framework alone (which bundles both effects together).

GAIA2 (not fully deterministic even at temperature=0.0) means one sample per scenario cannot
separate signal from noise -- every condition is run `--repeats` independent times and compared
with Fisher's exact test (two independent proportions, not paired items -- see BFCL's runner for
the paired Wilcoxon design used there instead, which is the correct test for ITS layout, not this
one).

Designed for incremental, stoppable use: each run merges into the existing output file by
scenario key, so running scenario 2 tomorrow does not erase scenario 1's results from today.

Usage:
    python -m benchmarks.ablation.runner --scenario decompose_or_block --repeats 20
    python -m benchmarks.ablation.runner --repeats 20              # every registered scenario
"""
import argparse
import asyncio
import json
import os
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
from scipy.stats import fisher_exact

from benchmarks.ablation.bare_agent import BareAgentLoop, BareRunResult
from benchmarks.ablation.engineered_agent import EngineeredAgentLoop
from benchmarks.ablation.scenarios import SCENARIOS, Scenario
from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.engine.executor import DialecticalEngine
from dialectic_ai.integrations.gigachat.llm import GigaChatLLM


async def _run_bare_trial(llm, scenario: Scenario) -> dict:
    tools = scenario.make_tools()
    loop = BareAgentLoop(llm, scenario.goal, tools, max_iterations=8)
    result = await loop.run(AgentInput(user_message=scenario.task))
    return {
        "status": result.status, "response": result.response, "iterations": result.iterations,
        "tool_calls_made": result.tool_calls_made, "success": scenario.check_success(result),
    }


async def _run_engineered_trial(llm, scenario: Scenario) -> dict:
    tools = scenario.make_tools()
    loop = EngineeredAgentLoop(llm, scenario.goal, tools, max_iterations=8)
    result = await loop.run(AgentInput(user_message=scenario.task))
    return {
        "status": result.status, "response": result.response, "iterations": result.iterations,
        "tool_calls_made": result.tool_calls_made, "success": scenario.check_success(result),
    }


async def _run_framework_trial(llm, scenario: Scenario) -> dict:
    tools = scenario.make_tools()
    agent = DialecticalAgent(goal=scenario.goal, llm=llm, tools=tools)
    engine = DialecticalEngine(agent, max_iterations=8)
    try:
        out = await engine.run(AgentInput(user_message=scenario.task))
    except Exception as e:
        # DialecticalEngine can raise ControlledRepairError (a real, known, occasional failure
        # mode of this project's own repair mechanism -- see development_log.md, 2026-09-14) or
        # any other unhandled exception. BareAgentLoop/EngineeredAgentLoop both already catch
        # their own exceptions and return a graceful status="error" -- this condition must too,
        # or one bad trial silently destroys the whole run's worth of real API spend (it did,
        # once, before this fix: development_log.md, 2026-09-16).
        return {"status": "error", "response": "", "tool_calls_made": [], "success": False, "error": str(e)}
    # AgentOutput doesn't carry tool_calls_made directly -- reconstruct it from evidence for a
    # like-for-like check_success call (check_success only reads .status/.response/.tool_calls_made).
    tool_calls_made = [
        {"name": e.tool_name, "args": {}, "success": e.success}
        for e in out.evidence
    ]
    adapted = BareRunResult(status=out.status, response=out.response or "", tool_calls_made=tool_calls_made)
    return {
        "status": out.status, "response": out.response,
        "dialectical_resolution_missing": out.dialectical_resolution_missing,
        "leap_action_mismatch": out.leap_action_mismatch,
        "tool_calls_made": tool_calls_made,
        "success": scenario.check_success(adapted),
    }


def _fisher(success_a: int, fail_a: int, success_b: int, fail_b: int) -> dict:
    odds_ratio, p_value = fisher_exact([[success_a, fail_a], [success_b, fail_b]])
    return {"odds_ratio": odds_ratio, "p_value": p_value, "significant_at_0_05": bool(p_value < 0.05)}


def compute_scenario_significance(bare_trials: list, engineered_trials: list, framework_trials: list) -> dict:
    """Three pairwise Fisher's exact tests, each answering a different question:
      - engineering_effect (bare vs engineered): does generic robustness engineering alone help?
      - dialectics_effect (engineered vs framework): does dialectics add anything ON TOP of that
        same engineering? THIS is the number that answers "does dialectics itself matter."
      - overall_effect (bare vs framework): the total effect, for reference/comparison to a
        two-condition study (e.g. flaky_retry's original bare-vs-framework-only result).
    """
    def counts(trials):
        s = sum(t["success"] for t in trials)
        return s, len(trials) - s

    bs, bf = counts(bare_trials)
    es, ef = counts(engineered_trials)
    fs, ff = counts(framework_trials)

    return {
        "bare_success": bs, "bare_fail": bf,
        "engineered_success": es, "engineered_fail": ef,
        "framework_success": fs, "framework_fail": ff,
        "engineering_effect": _fisher(bs, bf, es, ef),
        "dialectics_effect": _fisher(es, ef, fs, ff),
        "overall_effect": _fisher(bs, bf, fs, ff),
    }


async def run_scenario(llm, scenario: Scenario, repeats: int) -> dict:
    bare_trials, engineered_trials, framework_trials = [], [], []
    for i in range(1, repeats + 1):
        bare = await _run_bare_trial(llm, scenario)
        engineered = await _run_engineered_trial(llm, scenario)
        framework = await _run_framework_trial(llm, scenario)
        print(f"  [{scenario.key}] trial {i}/{repeats}: "
              f"bare={'OK' if bare['success'] else 'fail'}  "
              f"engineered={'OK' if engineered['success'] else 'fail'}  "
              f"framework={'OK' if framework['success'] else 'fail'}"
              f"{' [contradiction-flagged]' if framework.get('leap_action_mismatch') or framework.get('dialectical_resolution_missing') else ''}")
        bare_trials.append(bare)
        engineered_trials.append(engineered)
        framework_trials.append(framework)

    significance = compute_scenario_significance(bare_trials, engineered_trials, framework_trials)
    return {
        "key": scenario.key,
        "description": scenario.description,
        "repeats": repeats,
        "bare_success_rate": sum(t["success"] for t in bare_trials) / repeats,
        "engineered_success_rate": sum(t["success"] for t in engineered_trials) / repeats,
        "framework_success_rate": sum(t["success"] for t in framework_trials) / repeats,
        "framework_contradiction_flags": sum(
            1 for t in framework_trials
            if t.get("leap_action_mismatch") or t.get("dialectical_resolution_missing")
        ),
        "significance": significance,
        "bare_trials": bare_trials,
        "engineered_trials": engineered_trials,
        "framework_trials": framework_trials,
    }


async def main():
    parser = argparse.ArgumentParser(description="DialecticAI ablation: bare vs engineered vs framework, on injected failures")
    parser.add_argument("--scenario", default=None, help="Run only this scenario key (default: all registered)")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--output", default="ablation_stats.json")
    args = parser.parse_args()

    load_dotenv()
    keys = [args.scenario] if args.scenario else list(SCENARIOS.keys())
    for k in keys:
        if k not in SCENARIOS:
            raise SystemExit(f"Unknown scenario '{k}'. Registered: {list(SCENARIOS.keys())}")

    llm = GigaChatLLM(max_tokens=4096)
    if not llm.auth_key:
        raise SystemExit("GIGACHAT_AUTH_KEY is not set -- cannot run the ablation comparison.")

    print(f"Running ablation comparison: scenarios={keys}, repeats={args.repeats}")
    start = time.time()

    existing = {}
    if os.path.exists(args.output):
        with open(args.output, encoding="utf-8") as f:
            existing = json.load(f)
    scenario_reports = existing.get("scenarios", {})

    for key in keys:
        report = await run_scenario(llm, SCENARIOS[key], args.repeats)
        scenario_reports[key] = report
        # Save after EVERY scenario, not just at the very end -- a crash/interruption on
        # scenario 2 of 3 must not also lose scenario 1's already-completed results (see
        # development_log.md, 2026-09-16, for the ControlledRepairError crash this guards against).
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"scenarios": scenario_reports}, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - start

    print("\n" + "=" * 100)
    print("Ablation Report (bare vs engineered-non-dialectical vs framework)")
    print("=" * 100)
    print(f"{'Scenario':<20} {'N':>4} {'Bare':>8} {'Engineered':>12} {'Framework':>11} "
          f"{'Engineering p':>15} {'Dialectics p':>14}")
    for key, r in scenario_reports.items():
        sig = r.get("significance", {})
        if "engineered_success_rate" not in r:
            print(f"{key:<20}  (older 2-way result, no 'engineered' condition -- re-run to get the 3-way comparison)")
            continue
        eng_p = sig.get("engineering_effect", {}).get("p_value")
        dia_p = sig.get("dialectics_effect", {}).get("p_value")
        eng_flag = " *" if sig.get("engineering_effect", {}).get("significant_at_0_05") else ""
        dia_flag = " *" if sig.get("dialectics_effect", {}).get("significant_at_0_05") else ""
        print(f"{key:<20} {r['repeats']:>4} {100*r['bare_success_rate']:>7.1f}% "
              f"{100*r['engineered_success_rate']:>11.1f}% {100*r['framework_success_rate']:>10.1f}% "
              f"{(f'{eng_p:.4f}' if eng_p is not None else 'n/a'):>13}{eng_flag} "
              f"{(f'{dia_p:.4f}' if dia_p is not None else 'n/a'):>12}{dia_flag}")
    print("(* = statistically significant at p<0.05, Fisher's exact test)")
    print("'Engineering p' = bare vs engineered (does generic robustness engineering help at all?)")
    print("'Dialectics p'  = engineered vs framework (does dialectics add anything ON TOP of that "
          "same engineering? -- this is the number that answers whether dialectics itself matters)")
    print(f"\nThis run's elapsed time: {elapsed:.1f}s")
    print(f"\nFull report (already saved incrementally after each scenario) at {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
