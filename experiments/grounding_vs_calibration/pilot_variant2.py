"""Pilot for variant 2 (2a/2b/2c) on the world-brief question, per PREREGISTRATION.md's amendment
dated 2026-09-27 ("variant 2 list-content correction, round 2"): 2a and 2b run twice each on the
same 10 answers (stability check), 2c runs once (auxiliary, exploratory). Reports the breakdown
against gold correctness, run-to-run stability for 2a/2b, and actual token cost for extrapolation
to the full 258-answer run. Does not run the full run itself.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from data import brief_process_descriptions, load_world_answers, world_brief
from decider import JevDecider, SurrogateDecider
from variants import build_state

SURROGATE_MODEL = "gpt-4o-mini"
BASE_URL = "https://api.openai.com/v1"
API_KEY_ENV = "OPENAI_API_KEY"

N = 10
OUT_DIR = Path(__file__).resolve().parent


def error_signal(p_none: float, choice: str, threshold: float = 0.5) -> bool:
    return p_none >= threshold or choice == "none fits"


def main():
    answers = load_world_answers()[:N]
    brief_text = world_brief()
    id_to_line = brief_process_descriptions()
    print(f"pilot n={N}, brief chars={len(brief_text)}, 2c option count={len(id_to_line)+1}")

    surrogate = SurrogateDecider(SURROGATE_MODEL, BASE_URL, API_KEY_ENV)
    jev = JevDecider()

    rows = []
    started = time.monotonic()
    for i, a in enumerate(answers):
        state = build_state(a)
        row = {
            "i": i, "doc": a.doc, "hypothesis": a.hypothesis, "correct": a.correct,
            "gold": a.gold, "verdict": a.verdict,
        }

        r2a_1 = surrogate.choice_world_brief(state, brief_text)
        r2a_2 = surrogate.choice_world_brief(state, brief_text)
        row["2a_run1"] = {"p_none": r2a_1.probabilities.get("none fits", 0.0), "choice": r2a_1.choice,
                           "confidence": r2a_1.confidence, "prompt_tokens": r2a_1.prompt_tokens,
                           "completion_tokens": r2a_1.completion_tokens}
        row["2a_run2"] = {"p_none": r2a_2.probabilities.get("none fits", 0.0), "choice": r2a_2.choice,
                           "confidence": r2a_2.confidence, "prompt_tokens": r2a_2.prompt_tokens,
                           "completion_tokens": r2a_2.completion_tokens}

        r2b_1 = jev.choice_world_brief(state, brief_text)
        r2b_2 = jev.choice_world_brief(state, brief_text)
        row["2b_run1"] = {"p_none": r2b_1.probabilities.get("none fits", 0.0), "choice": r2b_1.choice,
                           "confidence": r2b_1.confidence, "prompt_tokens": r2b_1.prompt_tokens,
                           "completion_tokens": r2b_1.completion_tokens}
        row["2b_run2"] = {"p_none": r2b_2.probabilities.get("none fits", 0.0), "choice": r2b_2.choice,
                           "confidence": r2b_2.confidence, "prompt_tokens": r2b_2.prompt_tokens,
                           "completion_tokens": r2b_2.completion_tokens}

        r2c = jev.choice_brief_processes(state, brief_text, id_to_line)
        row["2c"] = {"p_none": r2c.probabilities.get("none fits", 0.0), "choice": r2c.choice,
                      "confidence": r2c.confidence, "prompt_tokens": r2c.prompt_tokens,
                      "completion_tokens": r2c.completion_tokens}

        rows.append(row)
        print(f"answer {i}: correct={a.correct} "
              f"2a=({row['2a_run1']['p_none']:.2f},{row['2a_run2']['p_none']:.2f}) "
              f"2b=({row['2b_run1']['p_none']:.2f},{row['2b_run2']['p_none']:.2f}) "
              f"2c={row['2c']['p_none']:.2f}")

    elapsed = time.monotonic() - started

    with open(OUT_DIR / "pilot_variant2_raw.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    # --- Breakdown against gold correctness ---
    n_wrong = sum(1 for r in rows if not r["correct"])
    n_correct = sum(1 for r in rows if r["correct"])

    def caught(run_key: str) -> int:
        return sum(1 for r in rows if not r["correct"]
                   and error_signal(r[run_key]["p_none"], r[run_key]["choice"]))

    def false_pos(run_key: str) -> int:
        return sum(1 for r in rows if r["correct"]
                   and error_signal(r[run_key]["p_none"], r[run_key]["choice"]))

    print(f"\n=== Breakdown (n={N}, wrong={n_wrong}, correct={n_correct}) ===")
    for key in ["2a_run1", "2a_run2", "2b_run1", "2b_run2", "2c"]:
        print(f"{key}: caught {caught(key)}/{n_wrong} wrong, false-pos {false_pos(key)}/{n_correct} correct")

    # --- Stability: run1 vs run2 for 2a and 2b ---
    def stability(prefix: str) -> dict:
        diffs = [abs(r[f"{prefix}_run1"]["p_none"] - r[f"{prefix}_run2"]["p_none"]) for r in rows]
        flips = sum(1 for r in rows
                    if error_signal(r[f"{prefix}_run1"]["p_none"], r[f"{prefix}_run1"]["choice"])
                    != error_signal(r[f"{prefix}_run2"]["p_none"], r[f"{prefix}_run2"]["choice"]))
        return {"mean_abs_diff": sum(diffs) / len(diffs), "max_abs_diff": max(diffs),
                "binary_signal_flips": flips, "per_answer_diffs": diffs}

    stab_2a = stability("2a")
    stab_2b = stability("2b")
    print(f"\n=== Stability (run1 vs run2, P(none fits)) ===")
    print(f"2a: mean|diff|={stab_2a['mean_abs_diff']:.3f} max|diff|={stab_2a['max_abs_diff']:.3f} "
          f"binary flips={stab_2a['binary_signal_flips']}/{N}")
    print(f"2b: mean|diff|={stab_2b['mean_abs_diff']:.3f} max|diff|={stab_2b['max_abs_diff']:.3f} "
          f"binary flips={stab_2b['binary_signal_flips']}/{N}")

    # --- Cost ---
    def sum_tokens(key: str) -> tuple[int, int]:
        pt = sum(r[key]["prompt_tokens"] for r in rows)
        ct = sum(r[key]["completion_tokens"] for r in rows)
        return pt, ct

    cost = {}
    for key in ["2a_run1", "2a_run2", "2b_run1", "2b_run2", "2c"]:
        pt, ct = sum_tokens(key)
        cost[key] = {"prompt_tokens": pt, "completion_tokens": ct}

    total_2a = sum(cost[k]["prompt_tokens"] + cost[k]["completion_tokens"] for k in ["2a_run1", "2a_run2"])
    total_2b = sum(cost[k]["prompt_tokens"] + cost[k]["completion_tokens"] for k in ["2b_run1", "2b_run2"])
    total_2c = cost["2c"]["prompt_tokens"] + cost["2c"]["completion_tokens"]

    print(f"\n=== Cost (pilot, n={N}, elapsed {elapsed:.1f}s) ===")
    for key, v in cost.items():
        print(f"{key}: in={v['prompt_tokens']} out={v['completion_tokens']}")
    print(f"2a total (2 runs): {total_2a} tokens")
    print(f"2b total (2 runs): {total_2b} tokens")
    print(f"2c total (1 run): {total_2c} tokens")

    scale = 258 / N
    print(f"\n=== Projection to full run (258 answers, x{scale:.1f}) ===")
    print(f"2a (1 run): ~{total_2a/2*scale:.0f} tokens")
    print(f"2b (1 run): ~{total_2b/2*scale:.0f} tokens")
    print(f"2c (1 run): ~{total_2c*scale:.0f} tokens")
    print(f"2a+2b+2c (1 run each): ~{(total_2a/2 + total_2b/2 + total_2c)*scale:.0f} tokens")

    summary = {
        "n": N, "n_wrong": n_wrong, "n_correct": n_correct,
        "caught": {k: caught(k) for k in ["2a_run1", "2a_run2", "2b_run1", "2b_run2", "2c"]},
        "false_pos": {k: false_pos(k) for k in ["2a_run1", "2a_run2", "2b_run1", "2b_run2", "2c"]},
        "stability_2a": stab_2a, "stability_2b": stab_2b,
        "cost": cost, "elapsed_seconds": elapsed,
        "projection_258_tokens": {
            "2a_one_run": total_2a / 2 * scale,
            "2b_one_run": total_2b / 2 * scale,
            "2c_one_run": total_2c * scale,
        },
    }
    with open(OUT_DIR / "pilot_variant2_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nwrote pilot_variant2_raw.json, pilot_variant2_summary.json")


if __name__ == "__main__":
    main()
