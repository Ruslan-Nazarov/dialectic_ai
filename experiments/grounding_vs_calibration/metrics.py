"""Metrics shared by all three variants: error-signal rates, AUROC, precision/recall, bootstrap CI."""
from __future__ import annotations

import random
from dataclasses import dataclass


def error_rates(error_signal: list[bool], correct: list[bool]) -> dict:
    """Rate of a positive error signal among correct answers vs among incorrect answers."""
    n_correct = sum(correct)
    n_incorrect = len(correct) - n_correct
    fp = sum(e for e, c in zip(error_signal, correct) if c)  # signal fires on a correct answer
    tp = sum(e for e, c in zip(error_signal, correct) if not c)  # signal fires on a wrong answer
    return {
        "signal_rate_among_correct": fp / n_correct if n_correct else float("nan"),
        "signal_rate_among_incorrect": tp / n_incorrect if n_incorrect else float("nan"),
    }


def precision_recall(error_signal: list[bool], correct: list[bool]) -> dict:
    """Treat 'error signal fires' as predicting 'answer is wrong'."""
    tp = sum(e and not c for e, c in zip(error_signal, correct))
    fp = sum(e and c for e, c in zip(error_signal, correct))
    fn = sum((not e) and (not c) for e, c in zip(error_signal, correct))
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    return {"precision": precision, "recall": recall}


def auroc(score_correct: list[float], correct: list[bool]) -> float:
    """AUROC of `score_correct` (higher = more likely correct) predicting `correct`.

    Mann-Whitney U formulation, ties handled by averaging.
    """
    pos = [s for s, c in zip(score_correct, correct) if c]
    neg = [s for s, c in zip(score_correct, correct) if not c]
    if not pos or not neg:
        return float("nan")
    count = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                count += 1
            elif p == n:
                count += 0.5
    return count / (len(pos) * len(neg))


@dataclass
class PairKey:
    doc: int
    hypothesis: str


def bootstrap_ci(
    rows: list,  # objects with .doc, .hypothesis and whatever the metric_fn needs
    metric_fn,  # rows -> float
    n_resamples: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict:
    """Bootstrap CI resampling whole (doc, hypothesis) pairs (both reps move together)."""
    pairs: dict[tuple, list] = {}
    for r in rows:
        pairs.setdefault((r.doc, r.hypothesis), []).append(r)
    pair_keys = list(pairs.keys())
    rng = random.Random(seed)

    point = metric_fn(rows)
    samples = []
    for _ in range(n_resamples):
        chosen_keys = [pair_keys[rng.randrange(len(pair_keys))] for _ in pair_keys]
        resampled_rows = [row for k in chosen_keys for row in pairs[k]]
        try:
            val = metric_fn(resampled_rows)
        except Exception:
            continue
        if val == val:  # skip NaN
            samples.append(val)
    samples.sort()
    if not samples:
        return {"point": point, "lo": float("nan"), "hi": float("nan"), "n": 0}
    lo_idx = int(len(samples) * (alpha / 2))
    hi_idx = int(len(samples) * (1 - alpha / 2)) - 1
    hi_idx = max(hi_idx, 0)
    return {
        "point": point,
        "lo": samples[lo_idx],
        "hi": samples[min(hi_idx, len(samples) - 1)],
        "n": len(samples),
    }
