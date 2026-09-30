# Evidence and limitations

Snapshot consolidated after the 2026-09-30 audit. Saved experimental outcomes remain unchanged. Recompute with `python tools/audit_evidence.py --check --bootstrap`; see [audit summary](../research_artifacts/audit_summary.json) and [artifact manifest](../research_artifacts/manifest.json).

## Completed experiments

| Experiment / architecture | Unit and N | Comparison and metric | Result / uncertainty | Interpretation |
|---|---|---|---|---|
| BFCL, 16 September early framework (`47fd03c`) | 125 tasks; 3 repeats per arm | Raw vs framework, accuracy | 83.20% vs 80.53%; Wilcoxon p=0.582225 | No detected single-turn gain; not equivalence |
| `flaky_retry`, early framework | 20 runs per arm | Bare vs framework, success | 7/20 vs 20/20; Fisher p=0.0000129 | Benefit of bundled orchestration; no isolated dialectics effect |
| `decompose_or_block`, early framework | 20 runs per arm | Bare / engineered / framework | 20/20 / 19/20 / 13/20; engineered-vs-framework p=0.0436 | Exploratory degradation; multiple comparisons not controlled |
| Stage 14, v2 atomic checks | 2–19 synthetic cases per series | Agreement across 2–5 repeats | 91.7–100% of case×phase×facet groups unchanged | Repeatability, not semantic correctness |
| ContractNLI, 25 September bundle-world v3 | 129 selected pairs × 2 repeats per arm | Plain / NDA / cafeteria control, accuracy | 148/258 / 140/258 / 145/258 = 57.36% / 54.26% / 56.20% | No observed gain; hard subset selected using model errors |
| NDA `world_fit`, same run | 258 answers, 118 wrong | Compatibility self-report | True 258/258 | No correctness discrimination; thematic compatibility is a different target |
| Corrected fit scoring, 27 September | 258 answers, 129 pairs, 83 documents | Surrogate gpt-4o-mini / Jev, error AUROC | 0.223154 [0.148519, 0.301922] / 0.277906 [0.198293, 0.362090] | Inverted operational fit-score; not a general result against confidence |
| Quote-anchored re-verdict | 258 answers | Retrieval + gpt-5-mini re-verdict | Error precision 0.5311, recall 0.7966 | Second model judgment; verbatim quote check passed 258/258 by construction |
| Jev world-as-hint, 27 September | 2091 pairs; 123 documents; 3 conditions | No / NDA / control accuracy | 72.9316% / 72.4055% / 72.3577% | No detected world gain |
| Jev own confidence, same run | 2091 answers per condition | Confidence predicts correctness | AUROC 0.7761 / 0.7848 / 0.7753 | Informative auxiliary confidence signal |
| Separate Jev verifier, same date | 773 answers; 129 pairs; 83 documents | Correctness AUROC | 0.635841 [0.549251, 0.715409] | Modest discrimination; not universal multi-agent superiority |

Jev solver paired document-bootstrap differences: NDA−none = −0.5261 percentage points, 95% CI [−1.6260, +0.5261]; NDA−control = +0.0478 points, CI [−0.8130, +0.8130]. No equivalence margin was tested.

Verifier CI clusters all arms/repeats of a pair. An audit sensitivity calculation clustering by document gives [0.5509, 0.7246], still above 0.5. At the original 0.5 threshold, verifier error recall is only 9.41%, precision 47.76%, and ECE is 0.307. Useful ranking does not imply calibrated probabilities or a useful default decision threshold.

Corrected-round CIs cluster by pair, not document. The score is `P(none fits)` predicting error (equivalently `1−P(none fits)` predicting correctness). It measures compatibility with a domain brief, with truncated saved reasoning and no full contract in that request. Reversing its direction after observing results requires a new held-out test.

Jev own-confidence CIs: no world [0.7554, 0.7946], NDA [0.7670, 0.8017], control [0.7584, 0.7905]. Thus the evidence cannot support “self-confidence is generally useless.” Separate verification has different inputs and targets from world compatibility; the role difference alone is not isolated causally.

## Deception and judge: historical v2 evidence

[Published practice-loop traces](../research_artifacts/v2_ablation/) were previously excluded under `live_runs/`. They now support direct inspection:

- `deceive_unknowable`: baseline fooled 3/3; full engine correct and grounded 3/3. Only runs 1 and 2 saw the corrupted result. Run 3 returned structured JSON immediately and bypassed the harness's exact-output substitution.
- `deceive_persistent`: full engine unresolved 3/3, fooled 0/3. Baseline also fooled 0/3. Two unresolved reports include the true number and one does not; the harness's “correct” count is 2/3, distinct from honest unresolved completion.
- Default substitution corrupts only exact plain-number stdout. Formatted/JSON output can reveal correct results from the same executor. Persistent substitution still leaves residue checks or encoded values available. This is a limited synthetic failure model, not general adversarial robustness.
- Full unknowable averaged 184,894 tokens and 474 seconds versus baseline 1,116 tokens and 6 seconds. No equal-compute engineered baseline isolates the effect of the method.
- Archived `hardcore_deceive_subtle` ended fooled in all 3 runs. Some early mega “not fooled” runs never contacted the lying tool. Both counterexamples must accompany positive findings.

Stage 14 counts recomputed from public JSONL: binary 11/12 stable groups (60 calls); ternary 30/32 (128 calls, 4 cases and mixed 3/5 repeats); heldout binary and ternary each 48/48 (144 calls each); calibration binary 109/114 (340 calls, 19 cases, two groups have only 2 repeats). Related criteria within a case are not independent accuracy trials. This motivates testing narrow checks; it does not prove that narrow independent verification beats an integrated judge.

The two public ContractNLI v2 traces show one engine success and one timeout; the plain model is correct in both. On the successful case judge tokens are 200,829 of 286,893 (~70%). Cost and semantic disagreements motivate redesign, not a controlled proof that judges cannot work.

## Invalid, historical and exploratory material

- Grounding variant 2 round 1: **INVALID**; opaque process IDs were supplied without their formulations. Its AUROC must not be cited as current evidence. Round 2 supersedes it; variants 1 and 3 are unaffected.
- Initial NDA builder and revision traces belong to the pre-rewrite bundle architecture. Their block-token sums (533,341 / 53,744 / 96,880) conflict with reported cumulative totals. Concurrent shared-counter accounting plausibly inflates the sums; neither sum is a verified replacement cost measurement.
- Local revision demos used a hand-authored mismatch signal. They show execution, not improved accuracy or spontaneous error discovery.
- Instance-world scripts are smoke/ad hoc checks; saved own build traces are not a controlled evaluation. The contested `6 / 2(1+2)` notation tests interpretation under a convention, not an unambiguous ground truth.
- `world_vs_plaintext_jev` was added after the audited public `0db0b11` snapshot: N=60 screening, a six-item pilot and exploratory poison probes. Its [findings document](../experiments/world_vs_plaintext_jev/PILOT_FINDINGS.md) labels the series non-preregistered. No completed preregistered main-result file is present; local untracked article drafts are not evidence. Pilot claims need raw artifacts before independent verification.
- Misconceptions C remains planned: 27 fraction misconceptions, own vs foreign world, 54 calls. B is deferred; after image exclusions its planned N is 157, not 160. A world build is not an outcome of C or B.

## Scientific limits

One or few world builds, model-specific runs, selected hard examples, correlated hypotheses/repeats, pilot-informed amendments, multiple exploratory comparisons, Russian contexts with English legal tasks, and changing API aliases limit external validity. No experiment proves that AI cannot handle contradictions, that domain graphs are intrinsically useful, or that the current six-prompt engine is more accurate.

Human review of philosophical correctness needs a published rubric and independent reviewers. The current repository's automated tests measure software behaviour, not that scientific claim.
