"""Pilot: Exp1 = 3 docs x 3 conditions x 2 batched reps, plus one doc's 3 conditions run one-question-
per-call for the batch-vs-single independence check. Exp2 = 4 whole pairs (24 answers) x 2 batched reps,
plus 10 of those answers run one-question-per-call.

Per PREREGISTRATION.md's 2026-09-27 pilot-independence amendment: compares batch-vs-single divergence
against batch-vs-batch (rep0 vs rep1) stability, per experiment. Writes pilot_raw.json / pilot_summary.json
and prints the report (cost, full-run cost estimate, independence check verdict).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SIBLING = ROOT / "experiments" / "grounding_vs_calibration"
sys.path.insert(0, str(SIBLING))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from data import world_brief  # noqa: E402
from dialectic_world.adapter.adapter import WorldAdapter  # noqa: E402
from dialectic_world.world.model import World  # noqa: E402

from jev_batch import call_systemone, choice_question, noul_question  # noqa: E402

TEST_JSON = SIBLING / "data" / "contract-nli" / "test.json"
EVAL_V3 = ROOT / "contract_nli_runs" / "eval_v3.json"
PLACEBO_WORLD = (
    ROOT / "live_runs" / "v3_worlds_placebo"
    / "столовая_посетители_получают_холодную_еду_сотрудники_могут_е" / "v1.json"
)
OUT_DIR = HERE

RATE_PER_TOKEN = 0.042 / 1_000_000  # docs.typesafe.ai/models.md, verified live 2026-09-27; input only

CHOICE_CRITERIA = {
    "Entailment": "The agreement's terms guarantee that the statement is true.",
    "Contradiction": "The agreement's terms are incompatible with the statement being true.",
    "NotMentioned": "The agreement's terms neither guarantee nor contradict the statement.",
}
NOUL_CRITERIA = {
    "true": "The agent's stated verdict matches what the agreement actually supports.",
    "false": "The agent's stated verdict does not match what the agreement actually supports.",
}


def placebo_brief() -> str:
    w = World.model_validate_json(PLACEBO_WORLD.read_text(encoding="utf-8"))
    return WorldAdapter(w, max_chars=8000).brief()


def choice_q(hyp_text: str) -> dict:
    return choice_question(
        f'Statement: "{hyp_text}"\nDoes the agreement entail this statement, contradict it, or not mention it?',
        CHOICE_CRITERIA,
    )


def noul_q(verdict: str, answer: str) -> dict:
    return noul_question(
        {
            "agent_verdict": verdict,
            "agent_reasoning": answer,
            "question": "Is the agent's verdict on this statement correct, given the agreement in the shared state?",
        },
        criteria=NOUL_CRITERIA,
    )


# ---------------------------------------------------------------------------
# Experiment 1 pilot
# ---------------------------------------------------------------------------
def run_exp1(data, calls_log: list) -> dict:
    docs = sorted(data["documents"], key=lambda d: d["id"])[:3]
    nda_brief = world_brief()
    ctrl_brief = placebo_brief()
    conditions = [
        ("no_world", lambda text: {"contract": text}),
        ("nda_world", lambda text: {"contract": text, "world_description": nda_brief}),
        ("control_world", lambda text: {"contract": text, "world_description": ctrl_brief}),
    ]

    batched = {}  # (doc_id, cond, vrep) -> {hyp_key: answer}
    for doc in docs:
        hyp_keys = list(doc["annotation_sets"][0]["annotations"].keys())
        questions = {k: choice_q(data["labels"][k]["hypothesis"]) for k in hyp_keys}
        for cond_name, state_fn in conditions:
            state = state_fn(doc["text"])
            for vrep in (0, 1):
                t0 = time.monotonic()
                res = call_systemone(state, questions)
                calls_log.append({
                    "kind": "exp1_batched", "doc": doc["id"], "condition": cond_name, "vrep": vrep,
                    "n_questions": len(questions), "input_tokens": res.input_tokens,
                    "output_tokens": res.output_tokens, "seconds": time.monotonic() - t0,
                })
                batched[(doc["id"], cond_name, vrep)] = res.answers

    # batch-vs-single independence check: designated doc = first of the three, all 3 conditions
    designated = docs[0]
    hyp_keys = list(designated["annotation_sets"][0]["annotations"].keys())
    single = {}  # (cond, hyp_key) -> answer
    for cond_name, state_fn in conditions:
        state = state_fn(designated["text"])
        for hk in hyp_keys:
            t0 = time.monotonic()
            res = call_systemone(state, {hk: choice_q(data["labels"][hk]["hypothesis"])})
            calls_log.append({
                "kind": "exp1_single", "doc": designated["id"], "condition": cond_name, "hyp": hk,
                "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                "seconds": time.monotonic() - t0,
            })
            single[(cond_name, hk)] = res.answers[hk]

    # stability: rep0 vs rep1, all 3 docs x 3 conditions x 17 hyps x 3 class-probabilities
    stability_deltas = []
    for doc in docs:
        hks = list(doc["annotation_sets"][0]["annotations"].keys())
        for cond_name, _ in conditions:
            a0 = batched[(doc["id"], cond_name, 0)]
            a1 = batched[(doc["id"], cond_name, 1)]
            for hk in hks:
                p0, p1 = a0[hk]["probabilities"], a1[hk]["probabilities"]
                for cls in CHOICE_CRITERIA:
                    stability_deltas.append(abs(p0.get(cls, 0.0) - p1.get(cls, 0.0)))

    # batch-vs-single: designated doc, 3 conditions x 17 hyps x 3 class-probabilities, vs rep0
    independence_deltas = []
    for cond_name, _ in conditions:
        a0 = batched[(designated["id"], cond_name, 0)]
        for hk in hyp_keys:
            p_batch = a0[hk]["probabilities"]
            p_single = single[(cond_name, hk)]["probabilities"]
            for cls in CHOICE_CRITERIA:
                independence_deltas.append(abs(p_batch.get(cls, 0.0) - p_single.get(cls, 0.0)))

    # descriptive accuracy (rep0 only), not a frozen metric -- sanity only
    acc = {}
    for cond_name, _ in conditions:
        correct, total = 0, 0
        for doc in docs:
            gold = {k: v["choice"] for k, v in doc["annotation_sets"][0]["annotations"].items()}
            ans = batched[(doc["id"], cond_name, 0)]
            for hk, g in gold.items():
                total += 1
                correct += ans[hk]["choice"] == g
        acc[cond_name] = correct / total

    return {
        "docs": [d["id"] for d in docs],
        "designated_doc": designated["id"],
        "n_batched_calls": 3 * 3 * 2,
        "n_single_calls": 3 * len(hyp_keys),
        "stability_deltas": stability_deltas,
        "independence_deltas": independence_deltas,
        "descriptive_accuracy_rep0": acc,
    }


# ---------------------------------------------------------------------------
# Experiment 2 pilot
# ---------------------------------------------------------------------------
def run_exp2(rows, docs_by_id, labels, calls_log: list) -> dict:
    pairs_order: list[tuple[int, str]] = []
    pairs_rows: dict[tuple[int, str], list] = {}
    for r in rows:
        if r["answer"].startswith("ERROR") or r["verdict"] == "?":
            continue
        key = (r["doc"], r["hypothesis"])
        if key not in pairs_rows:
            pairs_rows[key] = []
            pairs_order.append(key)
        pairs_rows[key].append(r)
    chosen_pairs = pairs_order[:4]

    batched = {}  # (pair, vrep) -> {qid: answer}
    for pair in chosen_pairs:
        doc = docs_by_id[pair[0]]
        hyp_text = labels[pair[1]]["hypothesis"]
        state = {"contract": doc["text"], "statement": hyp_text}
        pr = pairs_rows[pair]
        questions = {f"{r['group']}_{r['arm']}_rep{r['rep']}": noul_q(r["verdict"], r["answer"]) for r in pr}
        for vrep in (0, 1):
            t0 = time.monotonic()
            res = call_systemone(state, questions)
            calls_log.append({
                "kind": "exp2_batched", "doc": pair[0], "hyp": pair[1], "vrep": vrep,
                "n_questions": len(questions), "input_tokens": res.input_tokens,
                "output_tokens": res.output_tokens, "seconds": time.monotonic() - t0,
            })
            batched[(pair, vrep)] = res.answers

    # flat list of all (pair, qid, gold, correct) for the 24 answers, in fixed order
    flat = []
    for pair in chosen_pairs:
        gold = docs_by_id[pair[0]]["annotation_sets"][0]["annotations"][pair[1]]["choice"]
        for r in pairs_rows[pair]:
            qid = f"{r['group']}_{r['arm']}_rep{r['rep']}"
            flat.append({"pair": pair, "qid": qid, "gold": gold, "verdict": r["verdict"], "answer": r["answer"]})

    selected_10 = flat[:10]
    single = {}  # (pair, qid) -> answer
    for item in selected_10:
        doc = docs_by_id[item["pair"][0]]
        hyp_text = labels[item["pair"][1]]["hypothesis"]
        state = {"contract": doc["text"], "statement": hyp_text}
        t0 = time.monotonic()
        res = call_systemone(state, {item["qid"]: noul_q(item["verdict"], item["answer"])})
        calls_log.append({
            "kind": "exp2_single", "doc": item["pair"][0], "hyp": item["pair"][1], "qid": item["qid"],
            "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
            "seconds": time.monotonic() - t0,
        })
        single[(item["pair"], item["qid"])] = res.answers[item["qid"]]

    stability_deltas = []
    for pair in chosen_pairs:
        a0, a1 = batched[(pair, 0)], batched[(pair, 1)]
        for qid in a0:
            stability_deltas.append(abs(a0[qid]["noul"] - a1[qid]["noul"]))

    independence_deltas = []
    for item in selected_10:
        a0 = batched[(item["pair"], 0)]
        noul_batch = a0[item["qid"]]["noul"]
        noul_single = single[(item["pair"], item["qid"])]["noul"]
        independence_deltas.append(abs(noul_batch - noul_single))

    return {
        "pairs": [{"doc": p[0], "hyp": p[1]} for p in chosen_pairs],
        "n_answers": len(flat),
        "n_batched_calls": 4 * 2,
        "n_single_calls": len(selected_10),
        "stability_deltas": stability_deltas,
        "independence_deltas": independence_deltas,
    }


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def report_experiment(name: str, result: dict, full_run_batched_calls: int, full_run_single_calls: int,
                       calls_log: list, kinds: tuple[str, str]) -> dict:
    stab = result["stability_deltas"]
    indep = result["independence_deltas"]
    stab_mean, stab_max = mean(stab), max(stab, default=float("nan"))
    indep_mean, indep_max = mean(indep), max(indep, default=float("nan"))
    verdict = "STOP: batching moves answers more than repeat noise" if indep_mean > stab_mean else "OK: batching within repeat-noise envelope"

    batched_calls = [c for c in calls_log if c["kind"] == kinds[0]]
    single_calls = [c for c in calls_log if c["kind"] == kinds[1]]
    avg_tok_per_batched_call = mean([c["input_tokens"] for c in batched_calls])
    avg_tok_per_single_call = mean([c["input_tokens"] for c in single_calls])
    n_q_per_batched = mean([c.get("n_questions", 1) for c in batched_calls])

    cost_if_batched = full_run_batched_calls * avg_tok_per_batched_call * RATE_PER_TOKEN
    cost_if_single = full_run_single_calls * avg_tok_per_single_call * RATE_PER_TOKEN

    print(f"\n{'='*70}\n{name}\n{'='*70}")
    print(f"stability (batch rep0 vs rep1): mean|delta|={stab_mean:.4f}, max|delta|={stab_max:.4f}, n={len(stab)}")
    print(f"independence (batch vs single): mean|delta|={indep_mean:.4f}, max|delta|={indep_max:.4f}, n={len(indep)}")
    print(f"VERDICT: {verdict}")
    print(f"avg input tokens: batched call ({n_q_per_batched:.1f} q/call) = {avg_tok_per_batched_call:.0f}, "
          f"single call = {avg_tok_per_single_call:.0f}")
    print(f"projected full run, batched ({full_run_batched_calls} calls): ${cost_if_batched:.4f}")
    print(f"projected full run, single-question ({full_run_single_calls} calls): ${cost_if_single:.4f}")

    return {
        "stability_mean": stab_mean, "stability_max": stab_max, "n_stability": len(stab),
        "independence_mean": indep_mean, "independence_max": indep_max, "n_independence": len(indep),
        "verdict": verdict,
        "avg_tokens_per_batched_call": avg_tok_per_batched_call,
        "avg_tokens_per_single_call": avg_tok_per_single_call,
        "projected_cost_batched_usd": cost_if_batched,
        "projected_cost_single_usd": cost_if_single,
    }


def main():
    data = json.loads(TEST_JSON.read_text(encoding="utf-8"))
    docs_by_id = {d["id"]: d for d in data["documents"]}
    labels = data["labels"]
    rows = json.loads(EVAL_V3.read_text(encoding="utf-8"))

    calls_log: list = []
    started = time.monotonic()
    exp1 = run_exp1(data, calls_log)
    exp2 = run_exp2(rows, docs_by_id, labels, calls_log)
    elapsed = time.monotonic() - started

    # Persist raw call metadata and per-experiment deltas immediately, before any report
    # formatting runs -- a crash while printing must never lose data that already cost money
    # (this is exactly what happened on the first pilot run: the print of a Unicode "delta"
    # character crashed on this Windows console's cp1251 codepage, after all 87 calls had
    # already succeeded and been paid for, but before anything was written to disk).
    with open(OUT_DIR / "pilot_calls_raw.json", "w", encoding="utf-8") as f:
        json.dump(calls_log, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / "pilot_exp1_deltas.json", "w", encoding="utf-8") as f:
        json.dump({"stability_deltas": exp1["stability_deltas"], "independence_deltas": exp1["independence_deltas"]}, f)
    with open(OUT_DIR / "pilot_exp2_deltas.json", "w", encoding="utf-8") as f:
        json.dump({"stability_deltas": exp2["stability_deltas"], "independence_deltas": exp2["independence_deltas"]}, f)

    total_in = sum(c["input_tokens"] for c in calls_log)
    total_out = sum(c["output_tokens"] for c in calls_log)
    total_cost = total_in * RATE_PER_TOKEN

    print(f"\n{'='*70}\nPILOT: raw call totals\n{'='*70}")
    print(f"{len(calls_log)} calls, {total_in} input tokens, {total_out} output tokens, "
          f"{elapsed:.1f}s wall-clock")
    print(f"pilot cost @ $0.042/M input tokens: ${total_cost:.4f}")

    r1 = report_experiment("EXPERIMENT 1", exp1, full_run_batched_calls=369, full_run_single_calls=6273,
                            calls_log=calls_log, kinds=("exp1_batched", "exp1_single"))
    r2 = report_experiment("EXPERIMENT 2", exp2, full_run_batched_calls=129, full_run_single_calls=773,
                            calls_log=calls_log, kinds=("exp2_batched", "exp2_single"))

    print(f"\n{'='*70}\nEXPERIMENT 1 descriptive accuracy (rep0 only, n=3 docs x 17 hyps, NOT a result)\n{'='*70}")
    for cond, acc in exp1["descriptive_accuracy_rep0"].items():
        print(f"  {cond}: {acc:.2%}")

    with open(OUT_DIR / "pilot_calls_raw.json", "w", encoding="utf-8") as f:
        json.dump(calls_log, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / "pilot_summary.json", "w", encoding="utf-8") as f:
        json.dump({
            "n_calls": len(calls_log), "total_input_tokens": total_in, "total_output_tokens": total_out,
            "elapsed_seconds": elapsed, "pilot_cost_usd": total_cost,
            "exp1": {**{k: v for k, v in exp1.items() if k != "stability_deltas" and k != "independence_deltas"}, **r1},
            "exp2": {**{k: v for k, v in exp2.items() if k != "stability_deltas" and k != "independence_deltas"}, **r2},
        }, f, ensure_ascii=False, indent=2)

    print(f"\nWrote pilot_calls_raw.json, pilot_summary.json")


if __name__ == "__main__":
    main()
