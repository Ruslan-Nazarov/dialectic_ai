"""Compute all frozen + auxiliary metrics from raw_results.json and print a report."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import auroc, bootstrap_ci, error_rates, precision_recall
from variants import normalized_entropy

OUT_DIR = Path(__file__).resolve().parent


@dataclass
class Row:
    doc: int
    hypothesis: str
    correct: bool
    fits: bool | None
    v2_p_none: float
    v2_confidence: float
    v2_entropy: float
    v2_error: bool
    v3_quote_not_found: bool
    v3_verdict_disagree: bool
    v3_error: bool


def build_rows(raw: list[dict]) -> list[Row]:
    rows = []
    for r in raw:
        p_none = r["v2_probabilities"].get("none fits", 0.0)
        v2_error = p_none >= 0.5 or r["v2_choice"] == "none fits"
        v3_qnf = not r["v3_quote_found"]
        v3_vd = r["v3_quote_found"] and r["v3_reverdict_matches_original"] is False
        rows.append(
            Row(
                doc=r["doc"],
                hypothesis=r["hypothesis"],
                correct=r["correct"],
                fits=r["fits"],
                v2_p_none=p_none,
                v2_confidence=r["v2_confidence"],
                v2_entropy=normalized_entropy(r["v2_probabilities"]),
                v2_error=v2_error,
                v3_quote_not_found=v3_qnf,
                v3_verdict_disagree=v3_vd,
                v3_error=(v3_qnf or v3_vd),
            )
        )
    return rows


def v1_error(rows):
    return [not (r.fits is True) for r in rows]


def report_section(name, rows, error_signal, continuous_score=None):
    correct = [r.correct for r in rows]
    er = error_rates(error_signal, correct)
    pr = precision_recall(error_signal, correct)
    print(f"\n--- {name} ---")
    print(f"  signal rate among CORRECT answers:   {er['signal_rate_among_correct']:.3f}")
    print(f"  signal rate among INCORRECT answers: {er['signal_rate_among_incorrect']:.3f}")
    print(f"  precision: {pr['precision']:.3f}  recall: {pr['recall']:.3f}")

    if continuous_score:
        scores = [continuous_score(r) for r in rows]
        auc = auroc(scores, correct)
        print(f"  AUROC: {auc:.3f}")

        def auc_metric(rs, score_fn=continuous_score):
            sc = [score_fn(r) for r in rs]
            co = [r.correct for r in rs]
            return auroc(sc, co)

        ci = bootstrap_ci(rows, auc_metric, n_resamples=2000, seed=42)
        print(f"  AUROC 95% CI: [{ci['lo']:.3f}, {ci['hi']:.3f}] (n_resamples used={ci['n']})")
        return {"precision": pr["precision"], "recall": pr["recall"], "auroc": auc, "auroc_ci": ci,
                "signal_rate_correct": er["signal_rate_among_correct"], "signal_rate_incorrect": er["signal_rate_among_incorrect"]}

    return {"precision": pr["precision"], "recall": pr["recall"],
            "signal_rate_correct": er["signal_rate_among_correct"], "signal_rate_incorrect": er["signal_rate_among_incorrect"]}


def bootstrap_precision_recall(rows, error_signal_fn, seed):
    def prec_fn(rs):
        sig = error_signal_fn(rs)
        return precision_recall(sig, [r.correct for r in rs])["precision"]

    def rec_fn(rs):
        sig = error_signal_fn(rs)
        return precision_recall(sig, [r.correct for r in rs])["recall"]

    ci_p = bootstrap_ci(rows, prec_fn, n_resamples=2000, seed=seed)
    ci_r = bootstrap_ci(rows, rec_fn, n_resamples=2000, seed=seed + 1)
    return ci_p, ci_r


def main():
    with open(OUT_DIR / "raw_results.json", encoding="utf-8") as f:
        raw = json.load(f)
    rows = build_rows(raw)
    n_correct = sum(r.correct for r in rows)
    n_wrong = len(rows) - n_correct
    print(f"n={len(rows)}  correct={n_correct} ({n_correct/len(rows)*100:.1f}%)  wrong={n_wrong}")

    results = {}

    # Variant 1: self-report. Binary only.
    v1_sig = v1_error(rows)
    results["variant1_self_report"] = report_section("Variant 1: self-report (fits)", rows, v1_sig)
    ci_p, ci_r = bootstrap_precision_recall(rows, lambda rs: [not (r.fits is True) for r in rs], seed=100)
    results["variant1_self_report"]["precision_ci"] = ci_p
    results["variant1_self_report"]["recall_ci"] = ci_r
    print(f"  precision 95% CI: [{ci_p['lo']:.3f}, {ci_p['hi']:.3f}]  recall 95% CI: [{ci_r['lo']:.3f}, {ci_r['hi']:.3f}]")

    # Variant 2: main signal = P(none fits), continuous. AUROC is the frozen metric.
    v2_sig = [r.v2_error for r in rows]
    res2 = report_section(
        "Variant 2: choice-with-probabilities (P(none fits), main signal)",
        rows, v2_sig, continuous_score=lambda r: 1 - r.v2_p_none,  # higher score = more likely correct
    )
    results["variant2_p_none_fits"] = res2

    # Auxiliary variant-2 signals: top-choice confidence, normalized entropy (reported, not frozen).
    print("\n  [auxiliary] top-choice confidence as score:")
    conf_auc = auroc([r.v2_confidence for r in rows], [r.correct for r in rows])
    print(f"    AUROC: {conf_auc:.3f}  (world redundancy note: 152 active options -> low absolute confidence)")
    print("  [auxiliary] normalized entropy as score (lower entropy = more likely correct assumed):")
    ent_auc = auroc([1 - r.v2_entropy for r in rows], [r.correct for r in rows])
    print(f"    AUROC: {ent_auc:.3f}")
    results["variant2_auxiliary"] = {"confidence_auroc": conf_auc, "entropy_auroc": ent_auc}

    # Variant 3: binary signal, split into sub-signals + union, per prereg amendment.
    print("\n--- Variant 3 sub-signals ---")
    qnf_sig = [r.v3_quote_not_found for r in rows]
    vd_sig = [r.v3_verdict_disagree for r in rows]
    union_sig = [r.v3_error for r in rows]
    for label, sig in [("quote_not_found", qnf_sig), ("verdict_disagree", vd_sig), ("union", union_sig)]:
        pr = precision_recall(sig, [r.correct for r in rows])
        er = error_rates(sig, [r.correct for r in rows])
        print(f"  {label}: precision={pr['precision']:.3f} recall={pr['recall']:.3f} "
              f"rate|correct={er['signal_rate_among_correct']:.3f} rate|incorrect={er['signal_rate_among_incorrect']:.3f}")
    ci_p3, ci_r3 = bootstrap_precision_recall(rows, lambda rs: [r.v3_error for r in rs], seed=200)
    print(f"  union precision 95% CI: [{ci_p3['lo']:.3f}, {ci_p3['hi']:.3f}]  recall 95% CI: [{ci_r3['lo']:.3f}, {ci_r3['hi']:.3f}]")
    results["variant3_practice"] = {
        "quote_not_found": precision_recall(qnf_sig, [r.correct for r in rows]),
        "verdict_disagree": precision_recall(vd_sig, [r.correct for r in rows]),
        "union": precision_recall(union_sig, [r.correct for r in rows]),
        "union_precision_ci": ci_p3,
        "union_recall_ci": ci_r3,
    }

    with open(OUT_DIR / "metrics_summary.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print("\nDecision (frozen thresholds): variant2 P(none fits) AUROC point =", round(res2["auroc"], 3),
          "CI =", [round(res2["auroc_ci"]["lo"], 3), round(res2["auroc_ci"]["hi"], 3)])
    if res2["auroc_ci"]["lo"] > 0.5 and res2["auroc"] >= 0.65:
        verdict = "CALIBRATION HELPS"
    elif res2["auroc_ci"]["lo"] <= 0.5:
        verdict = "CALIBRATION DOES NOT HELP"
    else:
        verdict = "INCONCLUSIVE"
    print("Verdict:", verdict)


if __name__ == "__main__":
    main()
