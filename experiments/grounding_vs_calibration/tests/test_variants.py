import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from decider import ChoiceResult
from variants import (
    normalized_entropy,
    variant1_signal,
    variant2_error_signal,
    variant2_scores,
    variant3_signal_for_row,
)


@dataclass
class FakeAnswer:
    doc: int
    hypothesis: str
    verdict: str
    fits: bool | None


def test_variant1_signal_flags_missing_and_false():
    answers = [
        FakeAnswer(0, "a", "Entailment", True),
        FakeAnswer(0, "a", "Entailment", False),
        FakeAnswer(0, "a", "Entailment", None),
    ]
    assert variant1_signal(answers) == [False, True, True]


def test_variant2_main_signal_is_p_none_fits():
    results = [
        ChoiceResult(choice="P1", probabilities={"P1": 0.9, "none fits": 0.1}, confidence=0.9),
        ChoiceResult(choice="none fits", probabilities={"P1": 0.4, "none fits": 0.6}, confidence=0.6),
    ]
    scores = variant2_scores(results)
    assert scores["p_none_fits"] == [0.1, 0.6]
    assert scores["confidence"] == [0.9, 0.6]

    signal = variant2_error_signal(results, p_none_threshold=0.5)
    assert signal == [False, True]


def test_normalized_entropy_uniform_is_one():
    probs = {f"o{i}": 1 / 4 for i in range(4)}
    assert abs(normalized_entropy(probs) - 1.0) < 1e-9


def test_normalized_entropy_certain_is_zero():
    probs = {"a": 1.0, "b": 0.0, "c": 0.0}
    assert abs(normalized_entropy(probs) - 0.0) < 1e-9


def test_variant3_quote_not_found_is_error_signal():
    ans = FakeAnswer(0, "a", "Entailment", True)
    sig = variant3_signal_for_row(ans, contract_text="Some unrelated text.", quote="not present here", reverdict_from_quote=None)
    assert sig.error_signal is True
    assert sig.quote_found is False


def test_variant3_quote_found_and_reverdict_matches():
    ans = FakeAnswer(0, "a", "Entailment", True)
    text = "The Receiving Party may disclose information to its employees."

    def reverdict_fn(quote, answer):
        return "Entailment"

    sig = variant3_signal_for_row(ans, contract_text=text, quote=text, reverdict_from_quote=reverdict_fn)
    assert sig.quote_found is True
    assert sig.reverdict_matches_original is True
    assert sig.error_signal is False


def test_variant3_quote_found_but_reverdict_disagrees():
    ans = FakeAnswer(0, "a", "Entailment", True)
    text = "The Receiving Party may disclose information to its employees."

    def reverdict_fn(quote, answer):
        return "Contradiction"

    sig = variant3_signal_for_row(ans, contract_text=text, quote=text, reverdict_from_quote=reverdict_fn)
    assert sig.reverdict_matches_original is False
    assert sig.error_signal is True
