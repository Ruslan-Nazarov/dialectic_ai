"""Full run, experiment 1: all 2091 ContractNLI pairs x 3 conditions, one question per call
(the pilot's independence check tripped the preregistered stop rule for the batched design --
see PREREGISTRATION.md's pilot-independence amendment -- so the full run here is one Jev
`choice` question per HTTP call, 6273 calls total, not the originally-planned 369 batched calls).

Resumable: each call's outcome (success or exhausted-retry failure) is appended to
full_run_exp1.jsonl as one JSON line immediately after that call finishes -- a crash or
Ctrl-C loses at most the calls in flight, never anything already paid for. Re-running this
script skips any (doc, hypothesis, condition) key already present in that file, whether it
succeeded or failed -- it does not retry old failures automatically (per instruction: a
restart must not repeat calls already made).

Retries: up to 3 retries (4 attempts total) with exponential backoff on retryable errors
(429, 5xx, network/timeout). A non-retryable error (e.g. 400 max_tokens_exceeded) is recorded
as a permanent failure on the first attempt, no retry.

Budget: running total cost (usage.input_tokens x $0.042/M, output tokens are free per
docs.typesafe.ai/models.md, verified live and against the account's actual billing during the
pilot) is checked before submitting each new call; once cumulative cost for *this run* reaches
$3.50, no new calls are submitted (in-flight ones finish) and the run stops, reporting how many
pairs were never attempted.

Concurrency: max 8 threads (ThreadPoolExecutor), per instruction.
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

from data import world_brief  # noqa: E402
from dialectic_world.adapter.adapter import WorldAdapter  # noqa: E402
from dialectic_world.world.model import World  # noqa: E402

from jev_batch import JevAPIError, call_systemone_with_retry, choice_question  # noqa: E402
import budget  # noqa: E402

TEST_JSON = SIBLING / "data" / "contract-nli" / "test.json"
PLACEBO_WORLD = (
    ROOT / "live_runs" / "v3_worlds_placebo"
    / "столовая_посетители_получают_холодную_еду_сотрудники_могут_е" / "v1.json"
)
OUT_JSONL = HERE / "full_run_exp1.jsonl"

RATE_PER_TOKEN = 0.042 / 1_000_000
BUDGET_LIMIT_USD = 3.50
MAX_WORKERS = 8

CHOICE_CRITERIA = {
    "Entailment": "The agreement's terms guarantee that the statement is true.",
    "Contradiction": "The agreement's terms are incompatible with the statement being true.",
    "NotMentioned": "The agreement's terms neither guarantee nor contradict the statement.",
}

_write_lock = threading.Lock()
_budget_exhausted = threading.Event()
_combined_spent = 0.0  # shared across exp1+exp2, via budget.py; updated after each call


def placebo_brief() -> str:
    w = World.model_validate_json(PLACEBO_WORLD.read_text(encoding="utf-8"))
    return WorldAdapter(w, max_chars=8000).brief()


def choice_q(hyp_text: str) -> dict:
    return choice_question(
        f'Statement: "{hyp_text}"\nDoes the agreement entail this statement, contradict it, or not mention it?',
        CHOICE_CRITERIA,
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
                keys.add((rec["doc"], rec["hypothesis"], rec["condition"]))
    return keys


def append_record(rec: dict):
    with _write_lock:
        with open(OUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run_one(doc_id, hyp_key, hyp_text, gold, condition, state) -> dict:
    started = time.monotonic()
    rec = {
        "doc": doc_id, "hypothesis": hyp_key, "condition": condition, "gold": gold,
        "timestamp": time.time(),
    }
    try:
        res = call_systemone_with_retry(state, {hyp_key: choice_q(hyp_text)})
        ans = res.answers[hyp_key]
        rec.update({
            "status": "ok",
            "choice": ans.get("choice"), "probabilities": ans.get("probabilities"),
            "confidence": ans.get("confidence"),
            "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
            "seconds": time.monotonic() - started,
        })
        global _combined_spent
        _combined_spent = budget.add_spent(res.input_tokens * RATE_PER_TOKEN)
    except JevAPIError as e:
        rec.update({
            "status": "failed", "error_status_code": e.status_code, "error_body": e.body[:500],
            "input_tokens": 0, "output_tokens": 0, "seconds": time.monotonic() - started,
        })
    return rec


def main():
    data = json.loads(TEST_JSON.read_text(encoding="utf-8"))
    docs = data["documents"]
    labels = data["labels"]
    nda_brief = world_brief()
    ctrl_brief = placebo_brief()
    conditions = [
        ("no_world", lambda text: {"contract": text}),
        ("nda_world", lambda text: {"contract": text, "world_description": nda_brief}),
        ("control_world", lambda text: {"contract": text, "world_description": ctrl_brief}),
    ]

    tasks = []  # (doc_id, hyp_key, hyp_text, gold, condition_name, state)
    for doc in docs:
        anns = doc["annotation_sets"][0]["annotations"]
        for hyp_key, ann in anns.items():
            hyp_text = labels[hyp_key]["hypothesis"]
            for cond_name, state_fn in conditions:
                tasks.append((doc["id"], hyp_key, hyp_text, ann["choice"], cond_name, state_fn(doc["text"])))

    completed = load_completed_keys()
    remaining = [t for t in tasks if (t[0], t[1], t[4]) not in completed]
    print(f"exp1: {len(tasks)} total tasks, {len(completed)} already done, {len(remaining)} remaining")

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
            futures[ex.submit(run_one, t[0], t[1], t[2], t[3], t[4], t[5])] = t

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
                if (n_ok + n_failed) % 200 == 0:
                    print(f"  progress: {n_ok+n_failed}/{len(remaining)} done "
                          f"({n_ok} ok, {n_failed} failed), cumulative cost ${_combined_spent:.3f}")
                if _combined_spent >= BUDGET_LIMIT_USD:
                    _budget_exhausted.set()

            if not _budget_exhausted.is_set():
                for _ in range(len(done)):
                    nt = next(it, None)
                    if nt is None:
                        break
                    futures[ex.submit(run_one, nt[0], nt[1], nt[2], nt[3], nt[4], nt[5])] = nt

        if _budget_exhausted.is_set():
            skipped_for_budget = sum(1 for _ in it)  # anything left unattempted in the iterator

    elapsed = time.monotonic() - started
    print(f"\nexp1 full run: {n_ok} ok, {n_failed} failed, {skipped_for_budget} skipped (budget), "
          f"cumulative cost ${_combined_spent:.4f}, {elapsed:.1f}s")
    if _budget_exhausted.is_set():
        print(f"BUDGET STOP: reached ${BUDGET_LIMIT_USD} for this run before finishing.")


if __name__ == "__main__":
    main()
