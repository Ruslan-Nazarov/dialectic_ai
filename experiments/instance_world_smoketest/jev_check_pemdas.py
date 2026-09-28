"""Ad hoc check, not a preregistered experiment: Design A this time (per the conversation's correction
of jev_check_addition.py's mistake) -- the world sits in `state` as background prose, and the question
is about the actual contested fact ("6 / 2(1 + 2) = 1 or 9"), not about which node of the world graph
something belongs to. Two separate calls (no world / with world) because each needs its own `state`;
jev_batch's batching shares one state across questions, not across conditions. Checks only whether the
plumbing works and whether the world's argued position visibly moves Jev's answer -- one anecdote, not
a result.
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
DOMAIN = "6 / 2(1 + 2)"

QUESTIONS = {
    "which_reading": choice_question(
        'What is the value of "6 / 2(1 + 2)"?',
        {"1": "The expression equals 1.", "9": "The expression equals 9."},
    ),
    "nine_is_correct": noul_question('Is "6 / 2(1 + 2) = 9" the correct evaluation?'),
}


def run(label: str, state: dict) -> None:
    print(f"\n--- condition: {label} ---")
    print("state keys:", list(state.keys()), "sizes (chars):", {k: len(v) for k, v in state.items()})
    t0 = time.monotonic()
    res = call_systemone_with_retry(state, QUESTIONS)
    print(f"round-trip: {time.monotonic()-t0:.2f}s, input_tokens={res.input_tokens}, output_tokens={res.output_tokens}")
    print(json.dumps(res.answers, ensure_ascii=False, indent=2))


def main() -> None:
    store = WorldStore(WORLDS_DIR)
    world = store.load(DOMAIN)
    print(f"loaded world: domain={world.domain!r} status={world.status} processes={len(world.processes)}")
    brief = WorldAdapter(world, max_chars=4000).brief()
    print(f"brief: {len(brief)} chars")

    run("no_world", {"expression": DOMAIN})
    run("with_world", {"expression": DOMAIN, "world_description": brief})


if __name__ == "__main__":
    main()
