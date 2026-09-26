"""Compute the three signals over a list of data.Answer rows."""
from __future__ import annotations

import json
from dataclasses import dataclass

from data import Answer, load_world
from decider import ChoiceResult, Decider
from retrieval import PracticeSignal, keyword_search, quote_found_verbatim


# ---------------------------------------------------------------------------
# Variant 1: self-report. No calls.
# ---------------------------------------------------------------------------
def variant1_signal(answers: list[Answer]) -> list[bool]:
    """Error signal = agent's own world_fit says 'does not fit' or is missing."""
    return [not (a.fits is True) for a in answers]


# ---------------------------------------------------------------------------
# Variant 2: choice-with-probabilities (Jev surrogate).
# ---------------------------------------------------------------------------
def build_state(answer: Answer) -> str:
    return (
        f"Statement under review: (doc {answer.doc}, hypothesis {answer.hypothesis})\n"
        f"Agent's answer and reasoning: {answer.answer}"
    )


def variant2_call(
    decider: Decider, answer: Answer, process_ids: list[str]
) -> ChoiceResult:
    options = list(process_ids) + ["none fits"]
    state = build_state(answer) + "\nWhich world process does this answer engage?"
    return decider.choice(state, options)


def normalized_entropy(probabilities: dict[str, float]) -> float:
    import math

    n = len(probabilities)
    if n <= 1:
        return 0.0
    h = -sum(p * math.log(p) for p in probabilities.values() if p > 0)
    return h / math.log(n)


def variant2_scores(results: list[ChoiceResult]) -> dict[str, list[float]]:
    """Main signal (frozen post-pilot, pre-full-run amendment): P(none fits).

    Auxiliary signals: top-choice confidence and normalized entropy over the distribution --
    kept for reporting only, not used for the frozen AUROC threshold decision. See
    PREREGISTRATION.md, amendment dated 2026-09-26.
    """
    p_none = [r.probabilities.get("none fits", 0.0) for r in results]
    confidence = [r.confidence for r in results]
    entropy = [normalized_entropy(r.probabilities) for r in results]
    return {"p_none_fits": p_none, "confidence": confidence, "entropy": entropy}


def variant2_error_signal(results: list[ChoiceResult], p_none_threshold: float = 0.5) -> list[bool]:
    """Binary error signal derived from the main continuous score, for precision/recall reporting only.

    AUROC uses the continuous p_none_fits score directly and does not depend on this threshold.
    """
    return [r.probabilities.get("none fits", 0.0) >= p_none_threshold or r.choice == "none fits" for r in results]


# ---------------------------------------------------------------------------
# Variant 3: practice (external signal via quote retrieval + code-checked re-verdict).
# ---------------------------------------------------------------------------
def variant3_signal_for_row(
    answer: Answer,
    contract_text: str,
    quote: str | None,
    reverdict_from_quote,  # callable(quote:str, statement:str) -> verdict string, or None
) -> PracticeSignal:
    if quote is None:
        return PracticeSignal(quote_found=False, reverdict=None, reverdict_matches_original=None)
    found = quote_found_verbatim(contract_text, quote)
    if not found:
        return PracticeSignal(quote_found=False, reverdict=None, reverdict_matches_original=None)
    reverdict = reverdict_from_quote(quote, answer) if reverdict_from_quote else None
    matches = (reverdict == answer.verdict) if reverdict is not None else None
    return PracticeSignal(quote_found=True, reverdict=reverdict, reverdict_matches_original=matches)
