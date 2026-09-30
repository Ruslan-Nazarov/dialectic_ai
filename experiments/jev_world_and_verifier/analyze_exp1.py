"""Analysis for experiment 1, strictly per PREREGISTRATION.md's frozen metrics/thresholds.
Reads full_run_exp1.jsonl, writes analysis_exp1.json."""
from __future__ import annotations

import json
import sys
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

from metrics import auroc  # noqa: E402  (grounding_vs_calibration/metrics.py, imported not copied)
from metrics_ext import (  # noqa: E402
    bootstrap_ci_by_doc, ece, fast_auroc, reliability_diagram_data, brier_multiclass, macro_f1, per_class_accuracy,
)

CLASSES = ["Entailment", "Contradiction", "NotMentioned"]
CONDITIONS = ["no_world", "nda_world", "control_world"]
EVAL_V3 = ROOT / "contract_nli_runs" / "eval_v3.json"
COND_TO_ARM = {"no_world": "plain", "nda_world": "world", "control_world": "placebo"}
_gpt_rows = json.loads(EVAL_V3.read_text(encoding="utf-8"))
GPT5MINI_ALL = {arm: sum(r["verdict"] == r["gold"] for r in _gpt_rows if r["arm"] == arm)
               / sum(r["arm"] == arm for r in _gpt_rows) for arm in COND_TO_ARM.values()}


def load_records():
    recs = []
    with open(HERE / "full_run_exp1.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def main():
    recs = load_records()
    by_pair: dict[tuple, dict] = {}
    for r in recs:
        key = (r["doc"], r["hypothesis"])
        by_pair.setdefault(key, {})[r["condition"]] = r

    n_pairs_total = len(by_pair)
    excluded = []
    surviving_pairs = {}
    for key, conds in by_pair.items():
        ok = all(c in conds and conds[c]["status"] == "ok" for c in CONDITIONS)
        if ok:
            surviving_pairs[key] = conds
        else:
            missing = [c for c in CONDITIONS if c not in conds or conds[c]["status"] != "ok"]
            excluded.append({"doc": key[0], "hypothesis": key[1], "missing_or_failed": missing})

    print(f"pairs total={n_pairs_total}, excluded={len(excluded)}, surviving={len(surviving_pairs)}")
    if excluded:
        gold_of_excluded = [by_pair[(e["doc"], e["hypothesis"])][CONDITIONS[0]]["gold"]
                            if CONDITIONS[0] in by_pair[(e["doc"], e["hypothesis"])]
                            else None for e in excluded]
        print("excluded pairs' gold-class counts:", {c: gold_of_excluded.count(c) for c in set(gold_of_excluded)})

    combined_rows = []
    per_cond_rows = {c: [] for c in CONDITIONS}
    for (doc, hyp), conds in surviving_pairs.items():
        gold = conds[CONDITIONS[0]]["gold"]
        row = {"doc": doc, "hypothesis": hyp, "gold": gold}
        for c in CONDITIONS:
            correct = conds[c]["choice"] == gold
            row[f"{c}_correct"] = correct
            per_cond_rows[c].append({
                "doc": doc, "hypothesis": hyp, "gold": gold, "choice": conds[c]["choice"],
                "confidence": conds[c]["confidence"], "probabilities": conds[c]["probabilities"],
                "correct": correct,
            })
        combined_rows.append(row)

    accuracy = {c: sum(x["correct"] for x in per_cond_rows[c]) / len(per_cond_rows[c]) for c in CONDITIONS}
    print("\naccuracy:", accuracy)

    def diff_metric(cond_a, cond_b):
        def f(rows):
            a = [r[f"{cond_a}_correct"] for r in rows]
            b = [r[f"{cond_b}_correct"] for r in rows]
            return sum(a) / len(a) - sum(b) / len(b)
        return f

    diff_world_vs_none = bootstrap_ci_by_doc(combined_rows, diff_metric("nda_world", "no_world"))
    diff_world_vs_control = bootstrap_ci_by_doc(combined_rows, diff_metric("nda_world", "control_world"))
    print(f"\nnda_world - no_world: point={diff_world_vs_none['point']:.4f} "
          f"CI=[{diff_world_vs_none['lo']:.4f}, {diff_world_vs_none['hi']:.4f}]")
    print(f"nda_world - control_world: point={diff_world_vs_control['point']:.4f} "
          f"CI=[{diff_world_vs_control['lo']:.4f}, {diff_world_vs_control['hi']:.4f}]")

    helps = diff_world_vs_none["lo"] > 0 and diff_world_vs_control["lo"] > 0
    verdict = "WORLD HELPS" if helps else "NOT (both conditions required, per frozen threshold)"
    print(f"VERDICT: {verdict}")

    # auxiliary: macro-F1, per-class accuracy, calibration, self-error AUROC
    aux = {}
    for c in CONDITIONS:
        rows = per_cond_rows[c]
        preds = [r["choice"] for r in rows]
        golds = [r["gold"] for r in rows]
        confs = [r["confidence"] for r in rows]
        corrects = [r["correct"] for r in rows]
        probs = [r["probabilities"] for r in rows]
        self_auroc_slow = auroc(confs, corrects)
        self_auroc = fast_auroc(confs, corrects)
        assert abs(self_auroc_slow - self_auroc) < 1e-9, (
            f"fast_auroc disagrees with metrics.auroc for {c}: {self_auroc} vs {self_auroc_slow}"
        )
        self_auroc_ci = bootstrap_ci_by_doc(
            [{"doc": r["doc"], "confidence": r["confidence"], "correct": r["correct"]} for r in rows],
            lambda rs: fast_auroc([r["confidence"] for r in rs], [r["correct"] for r in rs]),
        )
        aux[c] = {
            "macro_f1": macro_f1(preds, golds, CLASSES),
            "per_class_accuracy": per_class_accuracy(preds, golds, CLASSES),
            "ece": ece(confs, corrects, 10),
            "brier_multiclass": brier_multiclass(probs, golds, CLASSES),
            "reliability_diagram": reliability_diagram_data(confs, corrects, 10),
            "self_confidence_auroc": self_auroc,
            "self_confidence_auroc_ci": self_auroc_ci,
        }
        print(f"\n[{c}] macro-F1={aux[c]['macro_f1']:.4f}, per-class acc={aux[c]['per_class_accuracy']}, "
              f"ECE={aux[c]['ece']:.4f}, Brier={aux[c]['brier_multiclass']:.4f}, "
              f"self-confidence AUROC={self_auroc:.4f} CI=[{self_auroc_ci['lo']:.4f},{self_auroc_ci['hi']:.4f}]")

    # comparison with gpt-5-mini on the 129 eval_v3 pairs
    eval_v3_rows = json.loads(EVAL_V3.read_text(encoding="utf-8"))
    eval_v3_pairs = {(r["doc"], r["hypothesis"]) for r in eval_v3_rows}
    subset_comparison = {}
    for c in CONDITIONS:
        subset = [r for r in per_cond_rows[c] if (r["doc"], r["hypothesis"]) in eval_v3_pairs]
        acc = sum(r["correct"] for r in subset) / len(subset) if subset else float("nan")
        arm = COND_TO_ARM[c]
        subset_comparison[c] = {"n": len(subset), "jev_accuracy": acc, "gpt5mini_accuracy": GPT5MINI_ALL[arm]}
    print("\n129-pair subset comparison with gpt-5-mini (eval_v3.md ALL row):")
    for c, v in subset_comparison.items():
        print(f"  {c}: n={v['n']}, Jev={v['jev_accuracy']:.2%}, gpt-5-mini={v['gpt5mini_accuracy']:.2%}")

    out = {
        "n_pairs_total": n_pairs_total, "n_excluded": len(excluded), "excluded": excluded,
        "n_surviving": len(surviving_pairs), "accuracy": accuracy,
        "diff_nda_world_minus_no_world": diff_world_vs_none,
        "diff_nda_world_minus_control_world": diff_world_vs_control,
        "verdict": verdict, "auxiliary": aux, "subset_comparison_129_pairs": subset_comparison,
    }
    with open(HERE / "analysis_exp1.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\nWrote analysis_exp1.json")


if __name__ == "__main__":
    main()
