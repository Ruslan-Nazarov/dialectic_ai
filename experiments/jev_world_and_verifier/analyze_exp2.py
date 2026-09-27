"""Analysis for experiment 2, strictly per PREREGISTRATION.md's frozen metrics/thresholds.
Reads full_run_exp2.jsonl, writes analysis_exp2.json."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
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

from metrics import auroc, bootstrap_ci, precision_recall  # noqa: E402
from metrics_ext import ece, brier_binary, precision_at_recall, reliability_diagram_data  # noqa: E402

RAW_RESULTS_V1 = SIBLING / "raw_results.json"  # variant 3 (quote-anchored re-verdict), "world" arm, 258 rows


@dataclass
class AnswerRow:
    doc: int
    hypothesis: str
    qid: str
    group: str
    arm: str
    rep: int
    noul: float
    correct: bool


def load_rows() -> list[AnswerRow]:
    out = []
    with open(HERE / "full_run_exp2.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec["status"] != "ok":
                continue
            for qid, ans in rec["answers"].items():
                meta = rec["row_meta"][qid]
                out.append(AnswerRow(
                    doc=rec["doc"], hypothesis=rec["hypothesis"], qid=qid,
                    group=meta["group"], arm=meta["arm"], rep=meta["rep"],
                    noul=ans["noul"], correct=meta["correct"],
                ))
    return out


def main():
    rows = load_rows()
    print(f"n answers analyzed: {len(rows)}")

    nouls = [r.noul for r in rows]
    corrects = [r.correct for r in rows]

    main_auroc = auroc(nouls, corrects)
    main_ci = bootstrap_ci(rows, lambda rs: auroc([r.noul for r in rs], [r.correct for r in rs]))
    print(f"\nMAIN METRIC: AUROC(noul predicting correct) = {main_auroc:.4f}, "
          f"95% CI = [{main_ci['lo']:.4f}, {main_ci['hi']:.4f}]")

    e = ece(nouls, corrects, 10)
    b = brier_binary(nouls, corrects)
    rel = reliability_diagram_data(nouls, corrects, 10)
    print(f"ECE={e:.4f}, Brier={b:.4f}")

    error_signal = [n < 0.5 for n in nouls]
    pr = precision_recall(error_signal, corrects)
    baseline_wrong_rate = 1 - sum(corrects) / len(corrects)
    print(f"\nThreshold 0.5: precision={pr['precision']:.4f}, recall={pr['recall']:.4f}, "
          f"baseline (share wrong)={baseline_wrong_rate:.4f}")

    # comparison with gpt-5-mini's variant 3 (quote-anchored re-verdict) on the 258 "world"-arm answers
    v3_data = json.loads(RAW_RESULTS_V1.read_text(encoding="utf-8"))
    v3_by_key = {(r["doc"], r["hypothesis"], r["group"], r["rep"]): r for r in v3_data}
    world_rows = [r for r in rows if r.arm == "world"]
    matched, v3_error_signal, jev_error_signal, matched_correct = [], [], [], []
    for r in world_rows:
        key = (r.doc, r.hypothesis, r.group, r.rep)
        v3r = v3_by_key.get(key)
        if v3r is None:
            continue
        v3_err = (not v3r["v3_quote_found"]) or (v3r["v3_reverdict_matches_original"] is False)
        matched.append(r)
        v3_error_signal.append(v3_err)
        jev_error_signal.append(r.noul < 0.5)
        matched_correct.append(r.correct)

    v3_pr = precision_recall(v3_error_signal, matched_correct)
    jev_pr_matched = precision_recall(jev_error_signal, matched_correct)
    jev_auroc_matched = auroc([r.noul for r in matched], matched_correct)
    matched_baseline_wrong_rate = 1 - sum(matched_correct) / len(matched_correct)
    # fair comparison: Jev's precision at a threshold matched to variant 3's own recall,
    # not each signal's own natural threshold (0.5 for Jev is not comparable to variant 3's
    # single fixed operating point)
    jev_at_v3_recall = precision_at_recall([r.noul for r in matched], matched_correct, v3_pr["recall"])
    print(f"\n258 'world'-arm subset (n matched to raw_results.json = {len(matched)}), "
          f"baseline wrong rate={matched_baseline_wrong_rate:.4f}:")
    print(f"  Jev: AUROC={jev_auroc_matched:.4f}, precision/recall@0.5={jev_pr_matched}")
    print(f"  gpt-5-mini variant 3 (quote-anchored re-verdict): precision/recall={v3_pr}")
    print(f"  Jev @ matched recall ({v3_pr['recall']:.4f}): {jev_at_v3_recall}")

    out = {
        "n_answers": len(rows),
        "main_auroc": main_auroc, "main_auroc_ci": main_ci,
        "ece": e, "brier": b, "reliability_diagram": rel,
        "threshold_0.5": {**pr, "baseline_wrong_rate": baseline_wrong_rate},
        "comparison_258_world_arm": {
            "n_matched": len(matched), "baseline_wrong_rate": matched_baseline_wrong_rate,
            "jev_auroc": jev_auroc_matched, "jev_precision_recall_at_0.5": jev_pr_matched,
            "gpt5mini_variant3_precision_recall": v3_pr,
            "jev_precision_at_variant3_matched_recall": jev_at_v3_recall,
        },
    }
    with open(HERE / "analysis_exp2.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\nWrote analysis_exp2.json")


if __name__ == "__main__":
    main()
