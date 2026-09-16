"""
benchmarks/bfcl/runner.py

Runs a stratified sample of BFCL's single-turn "AST" categories through two conditions against
the SAME underlying LLM -- a bare/raw prompt, and DialecticAI's real prompt+parser+repair
pipeline -- and grades both with BFCL's own grading algorithm. See adapter.py's own DIALECTICAL
DESCRIPTION for why this comparison, not a raw GAIA2 number, is the fairer test of what this
framework itself contributes.

Each case is run `--repeats` times per condition (default 3), independently, because GigaChat is
NOT perfectly deterministic even at temperature=0.0 (directly observed, development_log.md
2026-09-15): a single sample per case cannot distinguish "the framework changed behavior" from
"the model happened to answer differently this time." Repeating and reporting a paired
significance test (Wilcoxon signed-rank on per-case success-rate differences) answers the
question a bare percentage cannot: is an observed gap distinguishable from noise at this sample
size, or not?

Usage:
    python -m benchmarks.bfcl.runner --limit-per-category 25 --repeats 3
    python -m benchmarks.bfcl.runner --categories simple_python,irrelevance --limit-per-category 5 --repeats 1
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
from scipy.stats import wilcoxon

from benchmarks.bfcl.adapter import (
    SUPPORTED_CATEGORIES, BFCLFunctionTool, load_cases, _extract_question_text,
    run_framework_turn, run_raw_turn, grade_case,
)
from dialectic_ai.integrations.gigachat.llm import GigaChatLLM


async def _run_repeated(mode_fn, grade_fn, repeats: int) -> tuple[int, list]:
    """Calls mode_fn() `repeats` times (no args -- caller closes over them), grading each
    attempt independently with grade_fn(output). Returns (successes, list_of_outputs)."""
    successes = 0
    outputs = []
    for _ in range(repeats):
        try:
            output = await mode_fn()
        except Exception as e:
            output = {"__error__": str(e)}
        ok = grade_fn(output if not (isinstance(output, dict) and "__error__" in output) else None)
        successes += int(ok)
        outputs.append(output)
    return successes, outputs


async def run_category(llm: GigaChatLLM, category: str, limit: int, seed: int, repeats: int) -> dict:
    cases = load_cases(category, limit=limit, seed=seed)
    case_results = []

    for i, case in enumerate(cases, start=1):
        question = _extract_question_text(case)
        functions = case["function"]
        possible_answer = case["_ground_truth"]
        tools = [BFCLFunctionTool(f) for f in functions]

        grade_fn = lambda out: grade_case(category, functions, out, possible_answer)

        raw_successes, raw_outputs = await _run_repeated(
            lambda: run_raw_turn(llm, question, functions), grade_fn, repeats
        )
        fw_successes, fw_outputs = await _run_repeated(
            lambda: run_framework_turn(llm, question, tools), grade_fn, repeats
        )

        print(f"  [{category}] {i}/{len(cases)} {case['id']}: "
              f"raw={raw_successes}/{repeats}  framework={fw_successes}/{repeats}")

        case_results.append({
            "id": case["id"],
            "raw_rate": raw_successes / repeats,
            "framework_rate": fw_successes / repeats,
            "raw_outputs": raw_outputs,
            "framework_outputs": fw_outputs,
        })

    return {"category": category, "cases": case_results}


def compute_significance(all_categories: list[dict]) -> dict:
    """Paired Wilcoxon signed-rank test on per-case (framework_rate - raw_rate) across every
    case in every category -- the correct test for this design (same case, two conditions,
    repeated-sampling success RATE per case rather than a single binary outcome)."""
    all_cases = [c for cat in all_categories for c in cat["cases"]]
    raw_rates = [c["raw_rate"] for c in all_cases]
    fw_rates = [c["framework_rate"] for c in all_cases]
    diffs = [f - r for f, r in zip(fw_rates, raw_rates)]
    n = len(diffs)
    nonzero = [d for d in diffs if d != 0]

    pooled_raw = sum(raw_rates) / n if n else 0.0
    pooled_fw = sum(fw_rates) / n if n else 0.0
    mean_diff = sum(diffs) / n if n else 0.0

    if len(nonzero) < 1:
        p_value = 1.0
        stat = None
    else:
        try:
            stat, p_value = wilcoxon(nonzero)
        except ValueError:
            # e.g. all remaining diffs still cancel out under signed-rank ties
            stat, p_value = None, 1.0

    return {
        "n_cases": n,
        "n_nonzero_diffs": len(nonzero),
        "pooled_raw_accuracy": pooled_raw,
        "pooled_framework_accuracy": pooled_fw,
        "mean_per_case_diff": mean_diff,
        "wilcoxon_statistic": stat,
        "wilcoxon_p_value": p_value,
        "significant_at_0_05": bool(p_value is not None and p_value < 0.05),
    }


async def main():
    parser = argparse.ArgumentParser(description="BFCL raw-vs-framework comparison for DialecticAI")
    parser.add_argument("--categories", default=",".join(SUPPORTED_CATEGORIES))
    parser.add_argument("--limit-per-category", type=int, default=25)
    parser.add_argument("--repeats", type=int, default=3,
                         help="Independent trials per case per condition, to average out "
                              "GigaChat's own run-to-run non-determinism (see module docstring).")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="bfcl_stats.json")
    args = parser.parse_args()

    load_dotenv()
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    for c in categories:
        if c not in SUPPORTED_CATEGORIES:
            raise SystemExit(f"Unsupported category '{c}'. Supported: {SUPPORTED_CATEGORIES}")

    llm = GigaChatLLM(max_tokens=4096)
    if not llm.auth_key:
        raise SystemExit("GIGACHAT_AUTH_KEY is not set -- cannot run the BFCL comparison.")

    total_calls = sum(min(args.limit_per_category, 1_000_000) for _ in categories) * args.repeats * 2
    print(f"Running BFCL comparison: categories={categories}, limit_per_category={args.limit_per_category}, "
          f"repeats={args.repeats}, seed={args.seed} (~{total_calls} LLM calls)")

    start = time.time()
    results = [await run_category(llm, category, args.limit_per_category, args.seed, args.repeats)
               for category in categories]
    elapsed = time.time() - start

    significance = compute_significance(results)

    print("\n" + "=" * 78)
    print("BFCL Raw-vs-Framework Report (mean success rate per case, across repeats)")
    print("=" * 78)
    print(f"{'Category':<20} {'N cases':>8} {'Raw':>10} {'Framework':>12}")
    for r in results:
        n = len(r["cases"])
        raw_pct = 100 * sum(c["raw_rate"] for c in r["cases"]) / n if n else 0.0
        fw_pct = 100 * sum(c["framework_rate"] for c in r["cases"]) / n if n else 0.0
        print(f"{r['category']:<20} {n:>8} {raw_pct:>9.1f}% {fw_pct:>11.1f}%")
    print("-" * 78)
    print(f"{'TOTAL (pooled)':<20} {significance['n_cases']:>8} "
          f"{100*significance['pooled_raw_accuracy']:>9.1f}% {100*significance['pooled_framework_accuracy']:>11.1f}%")
    print(f"\nMean per-case (framework - raw) difference: {significance['mean_per_case_diff']:+.3f}")
    print(f"Wilcoxon signed-rank test: statistic={significance['wilcoxon_statistic']}, "
          f"p-value={significance['wilcoxon_p_value']:.4f} "
          f"({significance['n_nonzero_diffs']}/{significance['n_cases']} cases had a nonzero difference)")
    if significance["significant_at_0_05"]:
        direction = "framework > raw" if significance["mean_per_case_diff"] > 0 else "raw > framework"
        print(f"=> Statistically significant at p<0.05 ({direction}).")
    else:
        print("=> NOT statistically significant at p<0.05 -- this sample size/repeat count cannot "
              "distinguish the observed gap from noise. Do not report the raw percentage difference "
              "alone as evidence of a real effect.")
    print(f"\nElapsed: {elapsed:.1f}s (~{total_calls} LLM calls)")

    report = {
        "seed": args.seed,
        "limit_per_category": args.limit_per_category,
        "repeats": args.repeats,
        "model": f"{llm.model} (GigaChat)",
        "elapsed_seconds": elapsed,
        "significance": significance,
        "per_category": results,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nFull report (including every raw per-trial output, for forensic analysis) saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
