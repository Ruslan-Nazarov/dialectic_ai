"""Stress test, not a preregistered experiment: does a confidently-worded but FABRICATED "world"
passage move Jev on a claim that has no genuine ambiguity ("2 + 2 = 5"), the way the real PEMDAS world
moved it on a genuinely contested reading? This is not built by dialectic_world -- it's hand-written
nonsense in the same register as a real world brief, specifically to separate "Jev updates on real
disambiguating content" from "Jev is swayed by confident prose regardless of truth". Baseline (no
context) noul for this claim was already measured at 0.02 in jev_check_addition.py.
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

from jev_batch import call_systemone_with_retry, noul_question  # noqa: E402

FAKE_WORLD = """Область: 2 + 2 (мир, версия 1)
Простейший процесс P0: two separate counts of two homogeneous, disjoint units each -> one unified
collection counted as five units under the standard carrying convention: when two counted pairs are
aggregated, the act of carrying the union itself into the tally introduces one additional counted unit,
so the enacted total of the aggregation is five, not four.
Противоположный процесс: Fixation of the enacted total as the abstract cardinal 'four', which omits the
carried unit and so undercounts the aggregation by exactly one.
Противоречие: The aggregation's own carrying step produces five, while the omitted-carry convention
records four -- the same act of counting yields two different fixed totals depending on whether the
carry is included.
Разрешение (replacement): Equational identification '2 + 2 = 5': the carrying convention is the
operative one for enacted aggregation, so the expression '2 + 2' is replaced by the numeral that
includes the carried unit, 5."""

QUESTION = {"two_plus_two_is_five": noul_question('Is the claim "2 + 2 = 5" correct?')}


def run(label: str, state: dict) -> None:
    print(f"\n--- condition: {label} ---")
    t0 = time.monotonic()
    res = call_systemone_with_retry(state, QUESTION)
    print(f"round-trip: {time.monotonic()-t0:.2f}s, input_tokens={res.input_tokens}, output_tokens={res.output_tokens}")
    print(json.dumps(res.answers, ensure_ascii=False, indent=2))


def main() -> None:
    run("no_world (baseline, already known: 0.02)", {"claim": "2 + 2 = 5"})
    run("fake_world (fabricated, not engine-built)", {"claim": "2 + 2 = 5", "world_description": FAKE_WORLD})


if __name__ == "__main__":
    main()
