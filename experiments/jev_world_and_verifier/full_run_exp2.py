"""Full run, experiment 2: all 129 (doc, hypothesis) pairs from eval_v3.json, one batched call
per pair (up to 6 `noul` questions -- 3 arms x 2 reps -- sharing one {contract, statement}
state). The pilot's independence check passed for this design (batch-vs-single 0.0170 <=
batch-vs-batch stability 0.0171), so it stays batched, per PREREGISTRATION.md.

Same resumability/retry/budget discipline as full_run_exp1.py: one JSON line per pair appended
to full_run_exp2.jsonl immediately after that pair's call finishes; up to 3 retries with
backoff on retryable errors (429/5xx/network); budget is a running total shared with
full_run_exp1.py via budget.py, capped at $3.50 for the combined full run.

The one degenerate row (doc=129, hypothesis=nda-17, group=hard, arm=placebo, rep=1: empty
answer, verdict "?") is excluded here too, per PREREGISTRATION.md -- that pair's call carries
5 questions instead of 6.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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

from jev_batch import JevAPIError, call_systemone_with_retry, noul_question  # noqa: E402
import budget  # noqa: E402

TEST_JSON = SIBLING / "data" / "contract-nli" / "test.json"
EVAL_V3 = ROOT / "contract_nli_runs" / "eval_v3.json"
OUT_JSONL = HERE / "full_run_exp2.jsonl"

RATE_PER_TOKEN = 0.042 / 1_000_000
BUDGET_LIMIT_USD = 3.50
MAX_WORKERS = 8

NOUL_CRITERIA = {
    "true": "The agent's stated verdict matches what the agreement actually supports.",
    "false": "The agent's stated verdict does not match what the agreement actually supports.",
}

_write_lock = threading.Lock()
_budget_exhausted = threading.Event()
_combined_spent = 0.0


def noul_q(verdict: str, answer: str) -> dict:
    return noul_question(
        {
            "agent_verdict": verdict,
            "agent_reasoning": answer,
            "question": "Is the agent's verdict on this statement correct, given the agreement in the shared state?",
        },
        criteria=NOUL_CRITERIA,
    )


def load_completed_keys() -> set[tuple]:
    keys = set()
    if OUT_JSONL.exists():
        with open(OUT_JSONL, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                keys.add((rec["doc"], rec["hypothesis"]))
    return keys


def append_record(rec: dict):
    with _write_lock:
        with open(OUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run_one(doc_id, hyp_key, state, questions, row_meta) -> dict:
    started = time.monotonic()
    rec = {"doc": doc_id, "hypothesis": hyp_key, "n_questions": len(questions), "timestamp": time.time()}
    try:
        res = call_systemone_with_retry(state, questions)
        answers = {qid: {"noul": a.get("noul")} for qid, a in res.answers.items()}
        rec.update({
            "status": "ok", "answers": answers, "row_meta": row_meta,
            "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
            "seconds": time.monotonic() - started,
        })
        global _combined_spent
        _combined_spent = budget.add_spent(res.input_tokens * RATE_PER_TOKEN)
    except JevAPIError as e:
        rec.update({
            "status": "failed", "error_status_code": e.status_code, "error_body": e.body[:500],
            "row_meta": row_meta, "input_tokens": 0, "output_tokens": 0,
            "seconds": time.monotonic() - started,
        })
    return rec


def main():
    data = json.loads(TEST_JSON.read_text(encoding="utf-8"))
    docs_by_id = {d["id"]: d for d in data["documents"]}
    labels = data["labels"]
    rows = json.loads(EVAL_V3.read_text(encoding="utf-8"))

    pairs_order: list[tuple[int, str]] = []
    pairs_rows: dict[tuple, list] = {}
    n_excluded_rows = 0
    for r in rows:
        if r["answer"].startswith("ERROR") or r["verdict"] == "?":
            n_excluded_rows += 1
            continue
        key = (r["doc"], r["hypothesis"])
        if key not in pairs_rows:
            pairs_rows[key] = []
            pairs_order.append(key)
        pairs_rows[key].append(r)

    print(f"exp2: {len(pairs_order)} pairs, {sum(len(v) for v in pairs_rows.values())} answers "
          f"({n_excluded_rows} row(s) excluded: empty/unparseable agent answer)")

    tasks = []
    for pair in pairs_order:
        doc = docs_by_id[pair[0]]
        hyp_text = labels[pair[1]]["hypothesis"]
        state = {"contract": doc["text"], "statement": hyp_text}
        gold = doc["annotation_sets"][0]["annotations"][pair[1]]["choice"]
        pr = pairs_rows[pair]
        questions = {f"{r['group']}_{r['arm']}_rep{r['rep']}": noul_q(r["verdict"], r["answer"]) for r in pr}
        row_meta = {
            f"{r['group']}_{r['arm']}_rep{r['rep']}": {
                "group": r["group"], "arm": r["arm"], "rep": r["rep"],
                "verdict": r["verdict"], "gold": gold, "correct": r["verdict"] == gold,
            }
            for r in pr
        }
        tasks.append((pair[0], pair[1], state, questions, row_meta))

    completed = load_completed_keys()
    remaining = [t for t in tasks if (t[0], t[1]) not in completed]
    print(f"exp2: {len(tasks)} total tasks (pairs), {len(completed)} already done, {len(remaining)} remaining")

    skipped_for_budget = 0
    n_ok, n_failed = 0, 0
    started = time.monotonic()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {}
        it = iter(remaining)
        for _ in range(MAX_WORKERS):
            t = next(it, None)
            if t is None:
                break
            futures[ex.submit(run_one, *t)] = t

        while futures:
            done, _pending = wait(list(futures.keys()), return_when=FIRST_COMPLETED)
            for fut in done:
                futures.pop(fut)
                rec = fut.result()
                append_record(rec)
                if rec["status"] == "ok":
                    n_ok += 1
                else:
                    n_failed += 1
                print(f"  pair done: doc={rec['doc']} hyp={rec['hypothesis']} status={rec['status']} "
                      f"cumulative cost ${_combined_spent:.3f}")
                if _combined_spent >= BUDGET_LIMIT_USD:
                    _budget_exhausted.set()

            if not _budget_exhausted.is_set():
                for _ in range(len(done)):
                    nt = next(it, None)
                    if nt is None:
                        break
                    futures[ex.submit(run_one, *nt)] = nt

        if _budget_exhausted.is_set():
            skipped_for_budget = sum(1 for _ in it)

    elapsed = time.monotonic() - started
    print(f"\nexp2 full run: {n_ok} ok, {n_failed} failed, {skipped_for_budget} skipped (budget), "
          f"cumulative cost ${_combined_spent:.4f}, {elapsed:.1f}s")
    if _budget_exhausted.is_set():
        print(f"BUDGET STOP: reached ${BUDGET_LIMIT_USD} for this run before finishing.")


if __name__ == "__main__":
    main()
