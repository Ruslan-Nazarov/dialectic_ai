"""Metrics not already in ../grounding_vs_calibration/metrics.py (imported there for auroc,
precision_recall, error_rates, bootstrap_ci -- the last one groups by (doc, hypothesis) pair,
which fits experiment 2 as-is but not experiment 1, which needs grouping by document alone
(PREREGISTRATION.md: "утверждения одного договора не независимы" -- resample whole documents,
not individual pairs).
"""
from __future__ import annotations

import random


def bootstrap_ci_by_doc(
    rows: list[dict],  # each needs a "doc" key
    metric_fn,  # rows -> float
    n_resamples: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict:
    """Bootstrap CI resampling whole documents (every row belonging to a chosen doc moves
    together into the resample) -- experiment 1's frozen procedure, distinct from
    grounding_vs_calibration's pair-level bootstrap_ci."""
    by_doc: dict = {}
    for r in rows:
        by_doc.setdefault(r["doc"], []).append(r)
    doc_ids = list(by_doc.keys())
    rng = random.Random(seed)

    point = metric_fn(rows)
    samples = []
    for _ in range(n_resamples):
        chosen = [doc_ids[rng.randrange(len(doc_ids))] for _ in doc_ids]
        resampled = [row for d in chosen for row in by_doc[d]]
        try:
            val = metric_fn(resampled)
        except Exception:
            continue
        if val == val:  # skip NaN
            samples.append(val)
    samples.sort()
    if not samples:
        return {"point": point, "lo": float("nan"), "hi": float("nan"), "n": 0}
    lo_idx = int(len(samples) * (alpha / 2))
    hi_idx = max(int(len(samples) * (1 - alpha / 2)) - 1, 0)
    return {"point": point, "lo": samples[lo_idx], "hi": samples[min(hi_idx, len(samples) - 1)], "n": len(samples)}


def ece(confidences: list[float], corrects: list[bool], n_bins: int = 10) -> float:
    """Expected calibration error: sum over equal-width confidence bins of
    (bin weight) x |bin accuracy - bin mean confidence|."""
    bins = [[] for _ in range(n_bins)]
    for c, ok in zip(confidences, corrects):
        idx = min(int(c * n_bins), n_bins - 1)
        bins[idx].append((c, ok))
    n = len(confidences)
    if n == 0:
        return float("nan")
    total = 0.0
    for b in bins:
        if not b:
            continue
        conf_mean = sum(c for c, _ in b) / len(b)
        acc_mean = sum(ok for _, ok in b) / len(b)
        total += (len(b) / n) * abs(acc_mean - conf_mean)
    return total


def reliability_diagram_data(confidences: list[float], corrects: list[bool], n_bins: int = 10) -> list[dict]:
    bins = [[] for _ in range(n_bins)]
    for c, ok in zip(confidences, corrects):
        idx = min(int(c * n_bins), n_bins - 1)
        bins[idx].append((c, ok))
    out = []
    for i, b in enumerate(bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        if not b:
            out.append({"bin_lo": lo, "bin_hi": hi, "mean_confidence": None, "accuracy": None, "n": 0})
            continue
        out.append({
            "bin_lo": lo, "bin_hi": hi,
            "mean_confidence": sum(c for c, _ in b) / len(b),
            "accuracy": sum(ok for _, ok in b) / len(b),
            "n": len(b),
        })
    return out


def brier_multiclass(prob_dicts: list[dict], golds: list[str], classes: list[str]) -> float:
    """Mean over items of sum_k (p_k - 1[k == gold])^2."""
    total = 0.0
    for probs, gold in zip(prob_dicts, golds):
        total += sum((probs.get(k, 0.0) - (1.0 if k == gold else 0.0)) ** 2 for k in classes)
    return total / len(golds) if golds else float("nan")


def brier_binary(probs: list[float], corrects: list[bool]) -> float:
    if not probs:
        return float("nan")
    return sum((p - (1.0 if ok else 0.0)) ** 2 for p, ok in zip(probs, corrects)) / len(probs)


def macro_f1(preds: list[str], golds: list[str], classes: list[str]) -> float:
    f1s = []
    for cls in classes:
        tp = sum(p == cls and g == cls for p, g in zip(preds, golds))
        fp = sum(p == cls and g != cls for p, g in zip(preds, golds))
        fn = sum(p != cls and g == cls for p, g in zip(preds, golds))
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        f1s.append(f1)
    return sum(f1s) / len(f1s) if f1s else float("nan")


def fast_auroc(scores: list[float], labels: list[bool]) -> float:
    """Same Mann-Whitney-U definition as grounding_vs_calibration/metrics.py's auroc() (ties
    count as 0.5), but O(n log n) via rank-sum instead of that function's O(pos*neg) double
    loop -- needed here because experiment 1's self-confidence-AUROC bootstrap CI calls this
    2000 times per condition over ~2091 rows; the O(n^2) version made that computationally
    infeasible (verified: it hung for minutes and was killed rather than left to run). Results
    are numerically identical to metrics.auroc up to floating point, this is an efficiency
    substitution, not a different metric -- point estimates are cross-checked against
    metrics.auroc for at least one condition before being reported.
    """
    n = len(scores)
    pos = sum(labels)
    neg = n - pos
    if pos == 0 or neg == 0:
        return float("nan")
    order = sorted(range(n), key=lambda i: scores[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-indexed average rank for the tied block
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    sum_ranks_pos = sum(r for r, lab in zip(ranks, labels) if lab)
    return (sum_ranks_pos - pos * (pos + 1) / 2) / (pos * neg)


def precision_at_recall(scores: list[float], corrects: list[bool], target_recall: float) -> dict:
    """Lowest-score-first threshold on `scores` (lower = more likely wrong) that achieves at
    least `target_recall` for detecting wrong items (corrects == False), and the precision at
    that point. Used to compare a continuous signal (Jev's `noul`) against a fixed-operating-
    -point binary signal (gpt-5-mini's variant 3 re-verdict) on equal footing -- comparing
    precision at each signal's own natural threshold conflates "how good is the signal" with
    "how aggressive is its threshold", which is not the same question.
    """
    n_wrong = sum(1 for c in corrects if not c)
    if n_wrong == 0:
        return {"k": 0, "recall": float("nan"), "precision": float("nan"), "threshold": None}
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    cum_wrong = 0
    for k, i in enumerate(order, start=1):
        if not corrects[i]:
            cum_wrong += 1
        recall = cum_wrong / n_wrong
        if recall >= target_recall:
            return {"k": k, "recall": recall, "precision": cum_wrong / k, "threshold": scores[i]}
    return {"k": len(order), "recall": cum_wrong / n_wrong, "precision": cum_wrong / len(order), "threshold": None}


def per_class_accuracy(preds: list[str], golds: list[str], classes: list[str]) -> dict[str, float]:
    out = {}
    for cls in classes:
        idx = [i for i, g in enumerate(golds) if g == cls]
        if not idx:
            out[cls] = float("nan")
            continue
        out[cls] = sum(preds[i] == cls for i in idx) / len(idx)
    return out
