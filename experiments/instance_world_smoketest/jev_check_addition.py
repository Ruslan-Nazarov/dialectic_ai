"""Ad hoc check, not a preregistered experiment: one real Jev call against the "2 + 2" world built by
build_addition_en.py, to see whether Jev, given that world's brief() as context, does something sensible
with a wrong claim ("2 + 2 = 5") versus a correct one ("2 + 2 = 4") -- same pattern as
misconceptions_structure/PREREGISTRATION.md's Experiment C (choice over the world's active processes plus
"none"), just without a labeled dataset behind it. Answers only "does the plumbing work and does the
output look sane" -- a single anecdote proves nothing about whether the world's structure is doing real
work; see the conversation this script came out of.

Reuses jev_world_and_verifier/jev_batch.py by import (sys.path), not copied, per that folder's own
reuse-by-import discipline.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
JEV_DIR = ROOT / "experiments" / "jev_world_and_verifier"
sys.path.insert(0, str(JEV_DIR))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from dialectic_world import WorldAdapter, WorldStore  # noqa: E402
from jev_batch import call_systemone_with_retry, choice_question, noul_question  # noqa: E402

WORLDS_DIR = HERE / "data" / "worlds"
DOMAIN = "2 + 2"


def process_criteria(world) -> dict[str, str]:
    """id -> line, for every active process -- these become the choice options. "none" is added
    separately so it can't collide with a generated process id."""
    criteria = {pid: p.line() for pid, p in world.processes.items() if p.status == "active"}
    criteria["none"] = "None of the above processes is where this belief gets stuck."
    return criteria


def main() -> None:
    store = WorldStore(WORLDS_DIR)
    world = store.load(DOMAIN)
    print(f"loaded world: domain={world.domain!r} status={world.status} processes={len(world.processes)}")

    brief = WorldAdapter(world, max_chars=4000).brief()
    criteria = process_criteria(world)
    print(f"brief: {len(brief)} chars; {len(criteria)-1} process options + 'none'")

    state = {"world_description": brief}
    questions = {
        "wrong_stuck_at": choice_question(
            'Claim: "2 + 2 = 5". At which process of this world\'s development does someone holding '
            "this belief get stuck? If none of the processes fits, answer \"none\".",
            criteria,
        ),
        "correct_stuck_at": choice_question(
            'Claim: "2 + 2 = 4". At which process of this world\'s development does someone holding '
            "this belief get stuck? If none of the processes fits, answer \"none\".",
            criteria,
        ),
        "wrong_is_correct": noul_question(
            'Is the claim "2 + 2 = 5" correct?',
        ),
        "correct_is_correct": noul_question(
            'Is the claim "2 + 2 = 4" correct?',
        ),
    }

    print("\nquestions sent:")
    print(json.dumps({k: {"type": v["type"], "instructions": v["instructions"]} for k, v in questions.items()},
                     ensure_ascii=False, indent=2))

    t0 = time.monotonic()
    res = call_systemone_with_retry(state, questions)
    elapsed = time.monotonic() - t0

    print(f"\nHTTP round-trip: {elapsed:.2f}s, request_id={res.request_id}")
    print(f"usage: input_tokens={res.input_tokens}, output_tokens={res.output_tokens}")
    print(f"estimated cost at $0.042/M input tokens (not yet verified against TypeSafe console): "
          f"${res.input_tokens * 0.042 / 1e6:.6f}")

    print("\n--- answers ---")
    for qid, ans in res.answers.items():
        print(f"\n{qid}: {json.dumps(ans, ensure_ascii=False, indent=2)}")
        if "choice" in ans and ans.get("choice") not in ("none", None):
            pid = ans["choice"]
            if pid in world.processes:
                print(f"  -> [{pid}] {world.processes[pid].statement}")


if __name__ == "__main__":
    main()
