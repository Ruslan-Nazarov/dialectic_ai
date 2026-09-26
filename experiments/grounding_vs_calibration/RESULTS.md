# Results — grounding vs calibration

Preregistered in `PREREGISTRATION.md` (including two amendments made before/around this run, both dated
and marked). Raw per-answer output: `raw_results.json`. Run metadata: `run_summary.json`,
`metrics_summary.json`.

## Sanity check

Recomputed accuracy over all 258 `arm == "world"` rows in `contract_nli_runs/eval_v3.json`, using
`verdict == gold` with gold cross-checked against `live_runs/contract_nli/contract-nli/test.json`:
**54.3%** (140 correct / 118 wrong). Reconciles with `contract_nli_runs/eval_v3.md`'s reported 54%
(world column, ALL row). Source: `data.py:sanity_check_accuracy`, `data.py` lines 100-105.

World used: `live_runs/v3_worlds/договоры_о_неразглашении_nda_одна_сторона_раскрывает_другой_/v1.json`
("Договоры о неразглашении (NDA)..." v1, built), 155 processes total: **152 active, 3 retired**. Only
active processes were offered as options in variant 2.

## Headline answer

**Calibration does not help, on this data.** Variant 2's frozen main signal, `P(none fits)` from the
Choice-with-probabilities surrogate, scores **AUROC 0.243** (95% CI [0.170, 0.320], bootstrap n=2000,
resampled by (doc, hypothesis) pair). That CI sits entirely *below* 0.5 — the frozen threshold for
"calibration does not help" was any CI overlapping or below 0.5, and this result is stronger than that:
the signal is not merely uninformative, it's **inverted**. The model reports "none fits" more often on
answers that turn out to be *correct* than on ones that are wrong (signal rate 0.450 vs 0.127). This
was not anticipated and is reported as found, not adjusted for.

Variant 3 (practice, external signal) clearly separates correct from incorrect: precision 0.531 / recall
0.797 for its combined signal (95% CI on precision [0.427, 0.632], recall [0.696, 0.890]). Variant 1
(self-report) is completely uninformative — not close to chance, *zero variance*: every one of the 258
`world`-arm rows has `fits = True` (matches `eval_v3.md`'s own tally: "world world_fit marks: fits=258,
does not fit=0, missing=0"), so its precision is undefined (no positive signal ever fires) and recall is
0.

## Metrics table

| Variant | Signal | Precision | Recall | AUROC | Signal rate\|correct | Signal rate\|incorrect |
|---|---|---|---|---|---|---|
| 1. Self-report | `fits != True` | n/a (never fires) | 0.000 | n/a (binary, constant) | 0.000 | 0.000 |
| 2. Choice (main) | `P(none fits)` (continuous; binary cutoff 0.5 for precision/recall) | 0.192 | 0.127 | **0.243** [0.170, 0.320] | 0.450 | 0.127 |
| 2. Auxiliary | top-choice confidence | -- | -- | 0.283 | -- | -- |
| 2. Auxiliary | normalized entropy | -- | -- | 0.283 | -- | -- |
| 3. Practice — quote not found | binary | n/a (never fires) | 0.000 | n/a | 0.000 | 0.000 |
| 3. Practice — verdict disagree | binary | 0.531 | 0.797 | n/a (binary) | 0.593 | 0.797 |
| 3. Practice — union (frozen) | binary | **0.531** [0.427, 0.632] | **0.797** [0.696, 0.890] | n/a (binary, per prereg) | 0.593 | 0.797 |

n = 258 answers (129 doc/hypothesis pairs × 2 reps), 140 correct / 118 wrong per the sanity-checked gold
label. All CIs: 95%, bootstrap n=2000, resampled by whole (doc, hypothesis) pair (both reps move
together), per `metrics.bootstrap_ci`.

## Cost, calls, time

| Variant | Model | Calls | Prompt tokens | Completion tokens | Wall-clock (parallel, 16 workers) |
|---|---|---|---|---|---|
| 1 | — | 0 | 0 | 0 | ~0s |
| 2 | `openai:gpt-4o-mini` | 258 | 301,455 | 258 | included in 68.5s total |
| 3 | `openai:gpt-5-mini` (re-verdict only; retrieval is code, no call) | 258 | 33,818 | 62,352 | included in 68.5s total |

Total wall-clock for the full run (variants 2 and 3 run concurrently via `ThreadPoolExecutor`, 16
workers each): 68.5s. Token counts are read directly from each individual response's own `usage` field
(`llm_call.py`, `decider.py`), never from a before/after delta on a shared counter — this sidesteps the
race condition already documented for `dialectic_world/builder/blocks.py`'s `ask()` in
`ENGINE_V3_RESULTS_INDEX.md`.

## Model check (setup, before the pilot)

`gpt-5-mini` (the agent model that produced the original answers) does **not** return logprobs
(`decider.supports_logprobs("gpt-5-mini", ...)` → `False`); `gpt-4o-mini` does (→ `True`). Variant 2's
surrogate Decider therefore runs on `gpt-4o-mini`.

## What didn't work as designed, and what was changed (both pre-run, both documented in
`PREREGISTRATION.md`'s "after seeing results" section with dates)

1. **First full run was discarded.** `SurrogateDecider.choice()` labels options with letters `A, B, C, ...`;
   with 152 active processes + "none fits" = 153 options, the labeling scheme silently ran past `Z`, so
   the "none fits" label was a token the model could never produce. `P(none fits)` came back as exactly
   `0.0` for all 258 rows in the first run — an instrumentation bug, not a finding. Fixed by adding
   `choice_binary_none()`, which lists every process id as prompt context but asks for a single-token
   binary answer (`M` = matches something listed, `N` = none fits), keeping the model's one-token output
   inside an always-valid label space. This trades away "which specific process" (never part of any
   frozen metric) for a reliable `P(none fits)`. The full run was redone with the fix before any metric
   was computed on it.
2. **Variant 3's "quote not found" sub-signal never fires (rate 0.0 in both correct and incorrect
   answers).** This is a property of the retrieval design, not a coincidence: `keyword_search()` returns
   sentences copied verbatim out of the contract text, so `quote_found_verbatim()` is guaranteed true by
   construction. The entire variant-3 signal in this run is carried by `verdict_disagree` alone. A
   retrieval tool that could plausibly hallucinate or mis-quote (e.g. one operating over a summarized or
   paraphrased context) would be a stronger test of "quote not found" as an independent failure mode;
   this run's tool cannot exercise that path. Flagged as a limitation below, not silently absorbed into
   the union metric's apparent strength.

## Limitations

- **One world, one domain, one agent model.** Everything here is the NDA world (`v1.json`) built once,
  evaluated only against ContractNLI's business/legal domain, with `gpt-5-mini` as the only agent model
  that produced the original 258 answers. No claim here generalizes past this specific setup.
- **Surrogate, not Jev.** Variant 2 uses `SurrogateDecider` (a real logprob-capable chat model), not
  TypeSafe AI's actual `Choice` primitive. `JevDecider` in `decider.py` is written from public docs only,
  explicitly marked untested (no access key), and was never called. Swapping to a real `JevDecider` is a
  one-line config change if/when access exists, but until then this experiment says nothing about Jev's
  actual behavior, only about a stand-in built on the same interface.
- **Model confound between variants 2 and 3.** Variant 2 runs on `gpt-4o-mini` (the only model on hand
  confirmed to support logprobs); variant 3's re-verdict call runs on `gpt-5-mini` (matching the original
  agent). Any observed difference between "calibration" and "practice" is confounded with this model
  difference, not purely a difference in mechanism. This was flagged in the preregistration amendment
  before the full run, not discovered after the fact.
- **Variant 3's retrieval tool cannot fail the "quote not found" way by construction** (see above) — its
  demonstrated strength here is entirely from re-verdicting against a genuine quote, not from also
  catching fabricated citations.
- **Self-report (variant 1) is degenerate in this dataset**, not just weak: the agent marked `fits: true`
  on all 258 world-arm rows in the original `eval_v3.json` run, so there is no variance in this signal to
  evaluate at all. This is a property of how the original data was generated, not of this experiment's
  method — the result says "self-report was uninformative in this run," not "self-report is inherently
  uninformative."
- **This tests the engine's evaluation methodology, not a product.** The NDA/business-card domain is only
  the available test bed; no product or "rating points" framing is implied by these numbers.

## Source-of-numbers index

| Metric | Value | Source | Status |
|---|---|---|---|
| Sanity-check accuracy (world arm) | 54.3% | `data.py:sanity_check_accuracy`, run via `python data.py` | matches `eval_v3.md`'s 54% |
| Active/retired processes | 152 / 3 (of 155) | `data.py:active_process_ids`, inspected directly against `v1.json` | — |
| `gpt-5-mini` logprobs support | False | `decider.py:supports_logprobs("gpt-5-mini", ...)` | checked live, `decider.py` |
| `gpt-4o-mini` logprobs support | True | `decider.py:supports_logprobs("gpt-4o-mini", ...)` | checked live, `decider.py` |
| Variant 2 AUROC | 0.243 [0.170, 0.320] | `analyze.py`, printed from `metrics.auroc` + `metrics.bootstrap_ci` over `raw_results.json` | printed programmatically, `analyze.py:114-121`, not hand-typed |
| Variant 3 union precision/recall | 0.531 / 0.797 | `analyze.py`, `metrics.precision_recall` over `raw_results.json` | printed programmatically |
| Token/call/time totals | see cost table above | `run_summary.json`, generated by `full_run.py` | printed programmatically, not hand-typed |
