"""Round 2 analysis: variant 2 (2a/2b/2c) on the corrected world-brief question.

Frozen (per PREREGISTRATION.md): AUROC of P(none fits) for 2b vs 2a, with 95% bootstrap CI
(2000 resamples, grouped by (doc, hypothesis) pair), and the CI on their difference. Auxiliary:
0.5-threshold precision/recall for 2a/2b/2c. Exploratory: breakdown by gold class and difficulty
group for 2a, 2b, and 2c. Does not touch round 1's raw_results.json / metrics_summary.json.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import auroc, bootstrap_ci, error_rates, precision_recall

OUT_DIR = Path(__file__).resolve().parent


@dataclass
class Row:
    doc: int
    hypothesis: str
    group: str
    gold: str
    correct: bool
    p_none_2a: float
    p_none_2b: float
    p_none_2c: float
    choice_2a: str
    choice_2b: str
    choice_2c: str


def build_rows(raw: list[dict]) -> list[Row]:
    rows = []
    for r in raw:
        rows.append(Row(
            doc=r["doc"], hypothesis=r["hypothesis"], group=r["group"], gold=r["gold"],
            correct=r["correct"],
            p_none_2a=r["v2a_probabilities"].get("none fits", 0.0),
            p_none_2b=r["v2b_probabilities"].get("none fits", 0.0),
            p_none_2c=r["v2c_probabilities"].get("none fits", 0.0),
            choice_2a=r["v2a_choice"], choice_2b=r["v2b_choice"], choice_2c=r["v2c_choice"],
        ))
    return rows


def error_signal(p_none: float, choice: str, threshold: float = 0.5) -> bool:
    return p_none >= threshold or choice == "none fits"


def main():
    with open(OUT_DIR / "raw_results_round2.json", encoding="utf-8") as f:
        raw = json.load(f)
    rows = build_rows(raw)
    correct = [r.correct for r in rows]
    n = len(rows)
    n_correct = sum(correct)
    n_wrong = n - n_correct
    print(f"n={n}  correct={n_correct} ({n_correct/n*100:.1f}%)  wrong={n_wrong}")

    # ------------------------------------------------------------------
    # Frozen: AUROC of P(none fits), 2b vs 2a, bootstrap CI grouped by pair.
    # ------------------------------------------------------------------
    def auc_2a(rs):
        return auroc([1 - r.p_none_2a for r in rs], [r.correct for r in rs])

    def auc_2b(rs):
        return auroc([1 - r.p_none_2b for r in rs], [r.correct for r in rs])

    def auc_diff(rs):
        return auc_2b(rs) - auc_2a(rs)

    point_2a = auc_2a(rows)
    point_2b = auc_2b(rows)
    point_diff = point_2b - point_2a

    ci_2a = bootstrap_ci(rows, auc_2a, n_resamples=2000, seed=42)
    ci_2b = bootstrap_ci(rows, auc_2b, n_resamples=2000, seed=42)
    ci_diff = bootstrap_ci(rows, auc_diff, n_resamples=2000, seed=42)

    print("\n=== FROZEN: variant 2 main metric, P(none fits) AUROC ===")
    print(f"2a: {point_2a:.3f}  95% CI [{ci_2a['lo']:.3f}, {ci_2a['hi']:.3f}]")
    print(f"2b: {point_2b:.3f}  95% CI [{ci_2b['lo']:.3f}, {ci_2b['hi']:.3f}]")
    print(f"2b - 2a: {point_diff:.3f}  95% CI [{ci_diff['lo']:.3f}, {ci_diff['hi']:.3f}]")

    def verdict(point, ci):
        if ci["lo"] > 0.5 and point >= 0.65:
            return "CALIBRATION HELPS"
        elif ci["lo"] <= 0.5:
            return "CALIBRATION DOES NOT HELP"
        return "INCONCLUSIVE"

    v_2a = verdict(point_2a, ci_2a)
    v_2b = verdict(point_2b, ci_2b)
    print(f"2a verdict (frozen thresholds): {v_2a}")
    print(f"2b verdict (frozen thresholds): {v_2b}")

    # ------------------------------------------------------------------
    # Auxiliary: 0.5-threshold precision/recall for 2a, 2b, 2c.
    # ------------------------------------------------------------------
    print("\n=== AUXILIARY: 0.5-threshold error signal, precision/recall ===")
    aux = {}
    for key, p_attr, c_attr in [("2a", "p_none_2a", "choice_2a"), ("2b", "p_none_2b", "choice_2b"),
                                  ("2c", "p_none_2c", "choice_2c")]:
        sig = [error_signal(getattr(r, p_attr), getattr(r, c_attr)) for r in rows]
        pr = precision_recall(sig, correct)
        er = error_rates(sig, correct)
        print(f"{key}: precision={pr['precision']:.3f} recall={pr['recall']:.3f} "
              f"rate|correct={er['signal_rate_among_correct']:.3f} rate|incorrect={er['signal_rate_among_incorrect']:.3f}")
        aux[key] = {**pr, **er}

    # ------------------------------------------------------------------
    # Exploratory: breakdown by gold class and difficulty group, for 2a/2b/2c.
    # ------------------------------------------------------------------
    def breakdown(by_key_fn, label):
        print(f"\n=== EXPLORATORY: AUROC and mean P(none fits) by {label} ===")
        groups = defaultdict(list)
        for i, r in enumerate(rows):
            groups[by_key_fn(r)].append(i)
        out = {}
        for gname, idxs in sorted(groups.items()):
            c = [correct[i] for i in idxs]
            entry = {"n": len(idxs), "n_correct": sum(c), "n_wrong": len(c) - sum(c)}
            for key, p_attr in [("2a", "p_none_2a"), ("2b", "p_none_2b"), ("2c", "p_none_2c")]:
                p = [getattr(rows[i], p_attr) for i in idxs]
                mean_p = sum(p) / len(p)
                try:
                    auc = auroc([1 - x for x in p], c)
                except Exception:
                    auc = float("nan")
                entry[key] = {"mean_p_none_fits": mean_p, "auroc": auc}
            out[gname] = entry
            print(f"  {label}={gname}: n={entry['n']} (correct={entry['n_correct']}, wrong={entry['n_wrong']}) "
                  f"2a: mean_p={entry['2a']['mean_p_none_fits']:.3f} auroc={entry['2a']['auroc']:.3f} | "
                  f"2b: mean_p={entry['2b']['mean_p_none_fits']:.3f} auroc={entry['2b']['auroc']:.3f} | "
                  f"2c: mean_p={entry['2c']['mean_p_none_fits']:.3f} auroc={entry['2c']['auroc']:.3f}")
        return out

    by_gold = breakdown(lambda r: r.gold, "gold class")
    by_group = breakdown(lambda r: r.group, "difficulty group")

    results = {
        "n": n, "n_correct": n_correct, "n_wrong": n_wrong,
        "frozen_auroc": {
            "2a": {"point": point_2a, "ci": ci_2a, "verdict": v_2a},
            "2b": {"point": point_2b, "ci": ci_2b, "verdict": v_2b},
            "diff_2b_minus_2a": {"point": point_diff, "ci": ci_diff},
        },
        "auxiliary_threshold_0.5": aux,
        "exploratory_by_gold_class": by_gold,
        "exploratory_by_group": by_group,
    }
    with open(OUT_DIR / "metrics_summary_round2.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print("\nwrote metrics_summary_round2.json")


if __name__ == "__main__":
    main()
