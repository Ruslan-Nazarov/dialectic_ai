"""Full run, round 2: all 258 world-arm answers, variant 2 only (2a, 2b, 2c), one run each, on
the corrected world-brief question. Per PREREGISTRATION.md's amendment dated 2026-09-27 ("variant
2 list-content correction, round 2"): 2a and 2b ask the identical binary question against the
world brief; 2c is auxiliary/exploratory (multi-way choice among the brief's own processes).

Does not touch variant 1 or variant 3 (unaffected by the correction) or the original, now-invalid
raw_results.json / metrics_summary.json (round 1) -- writes to separate round2 files instead.
Token usage is read from each call's own response, never from a shared counter (same discipline
as full_run.py).
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from data import brief_process_descriptions, load_world_answers, world_brief
from decider import ChoiceResult, JevDecider, SurrogateDecider
from variants import build_state

SURROGATE_MODEL = "gpt-4o-mini"
BASE_URL = "https://api.openai.com/v1"
API_KEY_ENV = "OPENAI_API_KEY"
MAX_WORKERS = 16

OUT_DIR = Path(__file__).resolve().parent


def run_2a(decider, a, brief_text) -> ChoiceResult:
    return decider.choice_world_brief(build_state(a), brief_text)


def run_2b(decider, a, brief_text) -> ChoiceResult:
    return decider.choice_world_brief(build_state(a), brief_text)


def run_2c(decider, a, brief_text, id_to_line) -> ChoiceResult:
    return decider.choice_brief_processes(build_state(a), brief_text, id_to_line)


def run_pool(fn, answers, *extra_args) -> list[ChoiceResult]:
    results: list[ChoiceResult] = [None] * len(answers)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fn, a, *extra_args): i for i, a in enumerate(answers)}
        for fut in as_completed(futs):
            i = futs[fut]
            results[i] = fut.result()
    return results


def main():
    answers = load_world_answers()
    brief_text = world_brief()
    id_to_line = brief_process_descriptions()
    print(f"n_answers={len(answers)}, brief_chars={len(brief_text)}, 2c_options={len(id_to_line)+1}")

    surrogate = SurrogateDecider(SURROGATE_MODEL, BASE_URL, API_KEY_ENV)
    jev = JevDecider()

    started = time.monotonic()

    print("running 2a (surrogate)...")
    t0 = time.monotonic()
    v2a = run_pool(lambda a: run_2a(surrogate, a, brief_text), answers)
    print(f"  2a done in {time.monotonic()-t0:.1f}s")

    print("running 2b (jev)...")
    t0 = time.monotonic()
    v2b = run_pool(lambda a: run_2b(jev, a, brief_text), answers)
    print(f"  2b done in {time.monotonic()-t0:.1f}s")

    print("running 2c (jev)...")
    t0 = time.monotonic()
    v2c = run_pool(lambda a: run_2c(jev, a, brief_text, id_to_line), answers)
    print(f"  2c done in {time.monotonic()-t0:.1f}s")

    elapsed = time.monotonic() - started

    raw = []
    for i, a in enumerate(answers):
        r2a, r2b, r2c = v2a[i], v2b[i], v2c[i]
        raw.append({
            "doc": a.doc, "hypothesis": a.hypothesis, "group": a.group, "rep": a.rep,
            "gold": a.gold, "verdict": a.verdict, "correct": a.correct, "fits": a.fits,
            "v2a_choice": r2a.choice, "v2a_probabilities": r2a.probabilities, "v2a_confidence": r2a.confidence,
            "v2a_prompt_tokens": r2a.prompt_tokens, "v2a_completion_tokens": r2a.completion_tokens,
            "v2b_choice": r2b.choice, "v2b_probabilities": r2b.probabilities, "v2b_confidence": r2b.confidence,
            "v2b_prompt_tokens": r2b.prompt_tokens, "v2b_completion_tokens": r2b.completion_tokens,
            "v2c_choice": r2c.choice, "v2c_probabilities": r2c.probabilities, "v2c_confidence": r2c.confidence,
            "v2c_prompt_tokens": r2c.prompt_tokens, "v2c_completion_tokens": r2c.completion_tokens,
        })

    with open(OUT_DIR / "raw_results_round2.json", "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    summary = {
        "n_answers": len(answers),
        "n_pairs": len({(a.doc, a.hypothesis) for a in answers}),
        "elapsed_seconds": elapsed,
        "v2a_prompt_tokens": sum(r.prompt_tokens for r in v2a),
        "v2a_completion_tokens": sum(r.completion_tokens for r in v2a),
        "v2b_prompt_tokens": sum(r.prompt_tokens for r in v2b),
        "v2b_completion_tokens": sum(r.completion_tokens for r in v2b),
        "v2c_prompt_tokens": sum(r.prompt_tokens for r in v2c),
        "v2c_completion_tokens": sum(r.completion_tokens for r in v2c),
        "v2a_calls": len(answers), "v2b_calls": len(answers), "v2c_calls": len(answers),
    }
    with open(OUT_DIR / "run_summary_round2.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
