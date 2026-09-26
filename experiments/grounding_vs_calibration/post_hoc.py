"""Exploratory analysis AFTER seeing the frozen results. Does not touch any frozen metric or
threshold in PREREGISTRATION.md/RESULTS.md's main tables -- purely additional breakdowns to
understand *why* variant 2 and variant 3 look the way they do, for the external write-up.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import auroc

OUT_DIR = Path(__file__).resolve().parent


def confusion(signal: list[bool], correct: list[bool]) -> dict:
    tp = sum(s and not c for s, c in zip(signal, correct))  # flags a wrong answer
    fp = sum(s and c for s, c in zip(signal, correct))  # flags a correct answer
    fn = sum((not s) and (not c) for s, c in zip(signal, correct))  # misses a wrong answer
    tn = sum((not s) and c for s, c in zip(signal, correct))  # correctly leaves a correct answer unflagged
    n = len(signal)
    flag_rate = sum(signal) / n
    fpr_among_correct = fp / sum(correct) if sum(correct) else float("nan")
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    return {
        "TP": tp, "FP": fp, "TN": tn, "FN": fn,
        "flag_rate": flag_rate,
        "false_positive_rate_among_correct": fpr_among_correct,
        "precision": precision, "recall": recall,
    }


def main():
    with open(OUT_DIR / "raw_results.json", encoding="utf-8") as f:
        raw = json.load(f)

    correct = [r["correct"] for r in raw]
    n = len(raw)
    n_wrong = sum(not c for c in correct)
    baseline_precision = n_wrong / n  # "flag everything" -> precision = base rate of wrong answers
    baseline_recall = 1.0

    # ---------------------------------------------------------------------
    # 1. Variant 3 full table: union + both sub-signals, vs "flag everything" baseline.
    # ---------------------------------------------------------------------
    qnf = [not r["v3_quote_found"] for r in raw]
    vd = [r["v3_quote_found"] and r["v3_reverdict_matches_original"] is False for r in raw]
    union = [a or b for a, b in zip(qnf, vd)]

    v3_table = {
        "baseline_flag_everything": {
            "precision": baseline_precision, "recall": baseline_recall,
            "flag_rate": 1.0, "false_positive_rate_among_correct": 1.0,
            "TP": n_wrong, "FP": n - n_wrong, "TN": 0, "FN": 0,
        },
        "quote_not_found (mechanical, code-checked)": confusion(qnf, correct),
        "verdict_disagree (model re-verdict)": confusion(vd, correct),
        "union (frozen metric)": confusion(union, correct),
    }

    print("=== Variant 3: full confusion table, vs 'flag everything' baseline ===")
    print(f"n={n}, wrong={n_wrong} ({n_wrong/n*100:.1f}%) -- this is the baseline's precision.\n")
    for name, t in v3_table.items():
        print(f"-- {name} --")
        print(f"   TP={t['TP']} FP={t['FP']} TN={t['TN']} FN={t['FN']}")
        print(f"   flag_rate={t['flag_rate']:.3f}  FP_rate_among_correct={t['false_positive_rate_among_correct']:.3f}")
        print(f"   precision={t['precision']:.3f}  recall={t['recall']:.3f}")
        print()

    # ---------------------------------------------------------------------
    # 2. Variant 2 breakdown by gold class and by difficulty group.
    # ---------------------------------------------------------------------
    p_none = [r["v2_probabilities"].get("none fits", 0.0) for r in raw]
    gold = [r["gold"] for r in raw]
    group = [r["group"] for r in raw]

    print("=== Variant 2: AUROC and mean P(none fits) by gold class ===")
    by_gold = defaultdict(list)
    for i, g in enumerate(gold):
        by_gold[g].append(i)
    v2_by_gold = {}
    for g, idxs in sorted(by_gold.items()):
        c = [correct[i] for i in idxs]
        p = [p_none[i] for i in idxs]
        mean_p = sum(p) / len(p)
        try:
            auc = auroc([1 - x for x in p], c)
        except Exception:
            auc = float("nan")
        v2_by_gold[g] = {"n": len(idxs), "mean_p_none_fits": mean_p, "auroc": auc,
                          "n_correct": sum(c), "n_wrong": len(c) - sum(c)}
        print(f"  gold={g}: n={len(idxs)} (correct={sum(c)}, wrong={len(c)-sum(c)}) "
              f"mean_P(none fits)={mean_p:.3f} AUROC={auc:.3f}")

    print("\n=== Variant 2: AUROC and mean P(none fits) by difficulty group ===")
    by_group = defaultdict(list)
    for i, gr in enumerate(group):
        by_group[gr].append(i)
    v2_by_group = {}
    for gr, idxs in sorted(by_group.items()):
        c = [correct[i] for i in idxs]
        p = [p_none[i] for i in idxs]
        mean_p = sum(p) / len(p)
        try:
            auc = auroc([1 - x for x in p], c)
        except Exception:
            auc = float("nan")
        v2_by_group[gr] = {"n": len(idxs), "mean_p_none_fits": mean_p, "auroc": auc,
                            "n_correct": sum(c), "n_wrong": len(c) - sum(c)}
        print(f"  group={gr}: n={len(idxs)} (correct={sum(c)}, wrong={len(c)-sum(c)}) "
              f"mean_P(none fits)={mean_p:.3f} AUROC={auc:.3f}")

    out = {"variant3_full_table": v3_table, "variant2_by_gold_class": v2_by_gold, "variant2_by_group": v2_by_group}
    with open(OUT_DIR / "post_hoc_summary.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()
