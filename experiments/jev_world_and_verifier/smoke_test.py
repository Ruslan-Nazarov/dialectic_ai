"""Smoke test only: <=3 real Jev calls per experiment, checking request/response shape and cost.

Not pilot, not data. Per PREREGISTRATION.md step 2. Prints requests with the key redacted and long
fields truncated, the response shape, and token/cost accounting.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SIBLING = ROOT / "experiments" / "grounding_vs_calibration"
sys.path.insert(0, str(SIBLING))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from data import world_brief  # noqa: E402  (grounding_vs_calibration/data.py, NDA world brief)
from dialectic_world.adapter.adapter import WorldAdapter  # noqa: E402
from dialectic_world.world.model import World  # noqa: E402

from jev_batch import call_systemone, choice_question, noul_question  # noqa: E402

TEST_JSON = SIBLING / "data" / "contract-nli" / "test.json"
EVAL_V3 = ROOT / "contract_nli_runs" / "eval_v3.json"
PLACEBO_WORLD = (
    ROOT
    / "live_runs"
    / "v3_worlds_placebo"
    / "столовая_посетители_получают_холодную_еду_сотрудники_могут_е"
    / "v1.json"
)

CHOICE_CRITERIA = {
    "Entailment": "The agreement's terms guarantee that the statement is true.",
    "Contradiction": "The agreement's terms are incompatible with the statement being true.",
    "NotMentioned": "The agreement's terms neither guarantee nor contradict the statement.",
}


def truncate(obj, n=200):
    """For printing only: shorten long strings to their first/last lines."""
    if isinstance(obj, str) and len(obj) > n:
        return obj[: n // 2] + f"...[{len(obj)} chars total]..." + obj[-n // 2 :]
    if isinstance(obj, dict):
        return {k: truncate(v, n) for k, v in obj.items()}
    if isinstance(obj, list):
        return [truncate(v, n) for v in obj[:3]] + (["..."] if len(obj) > 3 else [])
    return obj


def placebo_brief() -> str:
    w = World.model_validate_json(PLACEBO_WORLD.read_text(encoding="utf-8"))
    return WorldAdapter(w, max_chars=8000).brief()


def choice_questions_for(hyps: list[tuple[str, str]]) -> dict:
    """hyps: list of (hyp_key, hyp_text) -> {qid: choice_question}."""
    return {
        hyp_key: choice_question(
            f'Statement: "{hyp_text}"\nDoes the agreement entail this statement, contradict it, or not mention it?',
            CHOICE_CRITERIA,
        )
        for hyp_key, hyp_text in hyps
    }


def run_exp1_smoke():
    print("=" * 70)
    print("EXPERIMENT 1 SMOKE TEST (<=3 calls)")
    print("=" * 70)
    data = json.loads(TEST_JSON.read_text(encoding="utf-8"))
    doc = data["documents"][0]
    hyp_keys = list(doc["annotation_sets"][0]["annotations"].keys())[:2]
    hyps = [(k, data["labels"][k]["hypothesis"]) for k in hyp_keys]
    gold = {k: doc["annotation_sets"][0]["annotations"][k]["choice"] for k in hyp_keys}
    print(f"doc id={doc['id']}, {len(hyp_keys)} hypotheses: {hyp_keys}, gold={gold}")

    nda_brief = world_brief()
    ctrl_brief = placebo_brief()

    conditions = [
        ("1_no_world", {"contract": doc["text"]}),
        ("2_nda_world", {"contract": doc["text"], "world_description": nda_brief}),
        ("3_control_world", {"contract": doc["text"], "world_description": ctrl_brief}),
    ]

    results = []
    total_in, total_out = 0, 0
    for name, state in conditions:
        questions = choice_questions_for(hyps)
        print(f"\n--- call: {name} ---")
        print("state keys:", list(state.keys()), "state sizes (chars):", {k: len(v) for k, v in state.items()})
        print("questions:", json.dumps(truncate(questions), ensure_ascii=False, indent=2))
        t0 = time.monotonic()
        res = call_systemone(state, questions)
        print(f"HTTP round-trip: {time.monotonic()-t0:.2f}s, request_id={res.request_id}")
        print("answers:", json.dumps(res.answers, ensure_ascii=False, indent=2))
        print(f"usage: input_tokens={res.input_tokens}, output_tokens={res.output_tokens}")
        for k in hyp_keys:
            ans = res.answers.get(k, {})
            print(f"  {k}: choice={ans.get('choice')!r} gold={gold[k]!r} match={ans.get('choice')==gold[k]}")
        total_in += res.input_tokens
        total_out += res.output_tokens
        results.append((name, res))

    print(f"\nEXP1 smoke totals: {len(results)} calls, {total_in} input tokens, {total_out} output tokens")
    return total_in, total_out


def run_exp2_smoke():
    print("\n" + "=" * 70)
    print("EXPERIMENT 2 SMOKE TEST (<=3 calls)")
    print("=" * 70)
    rows = json.loads(EVAL_V3.read_text(encoding="utf-8"))
    data = json.loads(TEST_JSON.read_text(encoding="utf-8"))
    docs = {d["id"]: d for d in data["documents"]}

    # pick two distinct (doc, hypothesis) pairs with no degenerate rows
    pairs_seen = {}
    for r in rows:
        if r["answer"].startswith("ERROR") or r["verdict"] == "?":
            continue
        key = (r["doc"], r["hypothesis"])
        pairs_seen.setdefault(key, []).append(r)
    chosen_pairs = list(pairs_seen.items())[:2]

    total_in, total_out = 0, 0
    for (doc_id, hyp_key), pair_rows in chosen_pairs:
        doc = docs[doc_id]
        hyp_text = data["labels"][hyp_key]["hypothesis"]
        gold = doc["annotation_sets"][0]["annotations"][hyp_key]["choice"]
        state = {"contract": doc["text"], "statement": hyp_text}
        questions = {}
        meta = {}
        for i, r in enumerate(pair_rows):
            qid = f"{r['group']}_{r['arm']}_rep{r['rep']}"
            questions[qid] = noul_question(
                {
                    "agent_verdict": r["verdict"],
                    "agent_reasoning": r["answer"],
                    "question": "Is the agent's verdict on this statement correct, given the agreement in the shared state?",
                },
                criteria={
                    "true": "The agent's stated verdict matches what the agreement actually supports.",
                    "false": "The agent's stated verdict does not match what the agreement actually supports.",
                },
            )
            meta[qid] = {"arm": r["arm"], "verdict": r["verdict"], "gold": gold, "correct": r["verdict"] == gold}

        print(f"\n--- call: doc={doc_id} hyp={hyp_key}, {len(questions)} questions ---")
        print("state sizes (chars):", {k: len(v) for k, v in state.items()})
        print("questions:", json.dumps(truncate(questions), ensure_ascii=False, indent=2))
        t0 = time.monotonic()
        res = call_systemone(state, questions)
        print(f"HTTP round-trip: {time.monotonic()-t0:.2f}s, request_id={res.request_id}")
        print("answers:", json.dumps(res.answers, ensure_ascii=False, indent=2))
        print(f"usage: input_tokens={res.input_tokens}, output_tokens={res.output_tokens}")
        for qid, m in meta.items():
            noul = res.answers.get(qid, {}).get("noul")
            print(f"  {qid}: noul={noul} agent_correct={m['correct']}")
        total_in += res.input_tokens
        total_out += res.output_tokens

    print(f"\nEXP2 smoke totals: {len(chosen_pairs)} calls, {total_in} input tokens, {total_out} output tokens")
    return total_in, total_out


if __name__ == "__main__":
    in1, out1 = run_exp1_smoke()
    in2, out2 = run_exp2_smoke()
    print("\n" + "=" * 70)
    print("GRAND TOTAL (smoke test, both experiments)")
    print("=" * 70)
    print(f"input_tokens={in1+in2}, output_tokens={out1+out2}")
    print("Compare against TypeSafe console's actual charge for these calls to verify $/token empirically.")
