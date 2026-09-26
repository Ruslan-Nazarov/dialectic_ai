# Preregistration — grounding vs calibration

Written before any live model calls in this experiment. Thresholds below are frozen; any change after
looking at results goes in a separate, clearly marked "after seeing results" section at the bottom, not
edited in place.

## Question

Can a calibrated confidence signal, by itself, distinguish a wrong agent answer from a right one — or does
distinguishing wrong from right require an external (grounding) signal, i.e. something outside the model's
own beliefs?

This is a test of the *engine's* evaluation methodology, not a product pitch. The business/NDA domain here
is only the test bed already available (contract_nli_runs/eval_v3.json), not the subject of the claim.

## Data (already collected, nothing new gathered)

- Agent answers: `contract_nli_runs/eval_v3.json`, `arm == "world"` subset. Confirmed by direct inspection:
  258 rows, 129 unique (doc, hypothesis) pairs × rep ∈ {0,1}, matching the request's 129×2=258.
- Gold labels: `live_runs/contract_nli/contract-nli/test.json` (outside git). For row r:
  `gold = docs[r.doc]["annotation_sets"][0]["annotations"][r.hypothesis]["choice"]`.
- World: `live_runs/v3_worlds/договоры_о_неразглашении_nda_одна_сторона_раскрывает_другой_/v1.json`
  (id/domain match the header of `contract_nli_runs/eval_v3.md`: "world 'Договоры о неразглашении (NDA)...' v1 (built)").
- Correctness label (target of the whole experiment): `correct_r = (verdict_r == gold_r)`, recomputed
  directly from `eval_v3.json`'s own `verdict` and `gold` fields (both already present per row — no
  external join needed beyond confirming `gold` matches `test.json`, which is a sanity check, not a new
  computation).
- **Sanity check performed before writing this doc**: `contract_nli_runs/eval_v3.md` reports 54% accuracy
  for the `world` arm on all 129 pairs (`ALL | 129 | 57% | 54% | 56%`, world column). If recomputing
  `verdict == gold` over the 258 `arm == "world"` rows does not land at 54% (129 pairs, both reps averaged),
  **stop and report the discrepancy** rather than adjusting the recomputation to match.

## Three variants (same 258 answers, same target label)

1. **Self-report (baseline)**: the `fits` field already in `eval_v3.json` for each row. No model calls.
   Error signal = `fits == false` (or missing).
2. **Choice with probabilities (Jev surrogate)**: one call per row. State = statement + agent's answer +
   its stated reasoning (`answer` field, truncated as already stored). Question: "which world process does
   this answer engage?" Options = the world's process ids (`v1.json["processes"]` keys) + an explicit
   "none fits" option. Returns a probability distribution over options.
   Confidence = P(top choice) (same definition Jev/TypeSafe use: concentration of the distribution).
   Error signal = low confidence, or "none fits" selected.
3. **Quote-anchored re-verdict** (originally called "practice (external signal)"; renamed 2026-09-27, see
   amendment below): agent gets a text-search tool over the contract (`doc["text"]`, keyword/
   sentence search only — no evidence-span gold data passed in). It must return a verbatim quote it relied
   on. Code (not a model) checks: (a) does the quote appear verbatim in the contract text; (b) re-deciding
   the verdict from that one quote alone, does it match the original verdict. Error signal = quote not
   found verbatim, or re-derived verdict disagrees. This signal is binary, not continuous.

Hard constraint: variant 3 must never see ContractNLI's `spans` (evidence annotations) — that would leak
the answer. The retrieval tool only searches raw contract text.

## Decider interface (for variant 2, matched to Jev's `Choice` primitive)

`Decider.choice(state, options) -> {choice, probabilities, confidence}`. Two implementations:
- `SurrogateDecider`: a real logprob-supporting non-reasoning chat model (see model choice below).
- `JevDecider`: written from TypeSafe's public docs for `POST /v1/systemone`, marked
  **"untested: no access key"** in code and never invoked in this run. Swapping implementations is one
  config value (`DECIDER_IMPL` env var — see `README.md`).

### Correction/rename — after post-hoc analysis, before external release (2026-09-27)

The post-hoc breakdown (`post_hoc.py`, see RESULTS.md) showed the mechanical "quote not found" check
never fires in this run's data — by construction, `keyword_search()` returns sentences copied verbatim
from the contract, so `quote_found_verbatim()` is guaranteed true. All of variant 3's detection power
comes from `verdict_disagree`, i.e. a second model call re-judging the verdict from one quote, not from
an independent code-only check. Calling this variant "practice (external signal)" overstated how
independent of the model it actually is. **Renamed to "quote-anchored re-verdict"** throughout code
(`PracticeSignal` → `QuoteReverdictSignal` in `retrieval.py`) and RESULTS.md. This is a naming and
documentation correction only — no metric, threshold, or number changes as a result.

## Model choice for variant 2

Must be checked empirically, not assumed, before the pilot: does the chosen model return logprobs and
accept temperature control? Reasoning models (gpt-5, o-series) are expected not to; if confirmed, fall
back to a non-reasoning chat model with logprobs support and state which one and why in RESULTS.md.
This check happens in code (a single test call), and its outcome is reported, not preregistered as a guess.

## Metrics (frozen)

For each variant, over the 258-answer set, split by the recomputed `correct` label:
- Error-signal rate among correct answers, and among incorrect answers (i.e. false-positive and
  true-positive rate of the error signal).
- AUROC for continuous signals (variant 2: 1 − confidence, or equivalently confidence as a "correct"
  score). Variant 1 is binary (`fits`) → report precision/recall instead, not AUROC. Variant 3 is binary
  → report precision/recall, not AUROC, as instructed.
- Precision and recall of error detection for all three variants (computed the same way so they're
  comparable even where AUROC also applies).
- 95% bootstrap CI (2000 resamples) on every metric above, resampled by **(doc, hypothesis) pair**, not by
  row — each pair contributes both its reps together to a resample, since reps are not independent.
- Token count, call count, wall-clock time per variant. Token counts are read from each individual call's
  own response/usage object, never from a before/after difference across concurrent calls (that pattern is
  the known race condition in `dialectic_world/builder/blocks.py`'s `ask()`, documented in
  `ENGINE_V3_RESULTS_INDEX.md`). If calls in this experiment are made concurrently, either the usage per
  call is read directly off that call's return value, or calls are serialized — no shared-counter delta.

## Decision thresholds (frozen before results)

- **"Calibration helps"**: variant 2's error signal achieves AUROC ≥ 0.65 (lower bound of its 95% CI ≥
  0.55), i.e. confidence usefully separates correct from incorrect answers on its own, without any external
  check.
- **"Calibration does not help"**: variant 2's AUROC 95% CI overlaps 0.5 (chance), i.e. the CI lower bound
  is ≤ 0.5 or the point estimate is < 0.55.
- Anything in between (AUROC point estimate 0.55–0.65 without a CI excluding 0.5) is reported as
  **inconclusive**, not rounded to either conclusion.
- Variant 3 (practice) is treated as the reference external signal: report whether its precision/recall at
  detecting errors exceeds variant 2's at variant 2's operating point, and whether variant 1 (self-report)
  is close to chance (its own AUROC-equivalent precision/recall near the base rate) — this is exploratory
  context, not a separate frozen pass/fail threshold, since self-report has no continuous score.
- If the 54% sanity check (above) fails to reconcile, that is reported as a blocking data problem before
  any of the above thresholds are evaluated.

## Order of work

1. This document (done).
2. Unit tests against a stub model: answer parsing, correctness-label computation, metric functions
   (AUROC, precision/recall, bootstrap CI) on toy data with a known answer.
3. Pilot: 10 real answers, all three variants, report token/time cost extrapolated to 258, wait for
   go-ahead before the full run.
4. Full run, all 258 answers × 3 variants.
5. `RESULTS.md`: metrics table, CIs, cost, models used, what failed, and an explicit "limitations" section
   (one world, one domain, one agent model, surrogate instead of real Jev). Raw results as JSON alongside.
   Source-of-numbers index entries in the same style as `ENGINE_V3_RESULTS_INDEX.md`.

## Boundaries

v2/v3 engine code (`engine_v2/`, `dialectic_world/`) is read-only for this experiment. All new code lives
under `experiments/grounding_vs_calibration/`. Commits are separate from other work; nothing is pushed
without explicit confirmation.

## Model check performed (setup, before pilot)

Empirically checked `supports_logprobs()` against the real OpenAI endpoint: `gpt-5-mini` (the agent model
used to generate the answers) returns no logprobs, confirming the expectation for reasoning models.
`gpt-4o-mini` does return logprobs. **Variant 2 surrogate model = `openai:gpt-4o-mini`**, chosen because it
is the smallest logprobs-supporting non-reasoning chat model already configured for this repo's OpenAI
provider (`dialectic_world/llm/providers.py`'s `OPENAI_COMPATIBLE` entry), keeping cost low for a surrogate
role. This is a factual check, not a result-influenced choice, and is recorded before the pilot.

## After seeing results

### Amendment — after pilot, before full run (2026-09-26)

Made after inspecting the 10-answer pilot's raw output, before the full 258-answer run. Frozen from
this point; the thresholds section above is otherwise unchanged.

1. **Variant 2's main signal is `P(none fits)`** — the probability mass the Choice distribution places
   on the explicit "none fits" option — not top-choice confidence and not entropy. Decided now, before
   the full run, because the pilot showed top-choice confidence sitting low (0.13–0.27) across all 10
   answers regardless of correctness: with 152 active processes to choose among (many near-duplicates
   from iterative world revision), the distribution is diffuse even when the model is right, so
   confidence mostly reflects **world redundancy**, not answer correctness. `P(none fits)` is a more
   direct read of the model's own belief that the answer doesn't ground in the world at all, and doesn't
   need renormalizing for how many near-duplicate options exist.
   - **AUROC of `P(none fits)` (as an error-predicting score) is the metric evaluated against the frozen
     thresholds above** (≥0.65 / CI excludes 0.5 for "helps", CI overlaps 0.5 for "does not help").
   - Top-choice confidence and normalized entropy (entropy divided by log of option count) are computed
     and reported, but as auxiliary/exploratory signals only — not evaluated against the frozen
     thresholds.
2. **Only `status == "active"` processes are offered as options in variant 2**, never `retired` ones.
   The NDA world (`v1.json`) has **155 processes total: 152 active, 3 retired**. Confirmed by direct
   inspection before the full run.
3. **Correctness is defined once, from ContractNLI gold, and never redefined per variant.** The pilot's
   report showed this needed to be explicit: `Answer.correct` (verdict == ContractNLI gold, computed in
   `data.py` and sanity-checked at 54.3%) is the only ground truth used anywhere, including when scoring
   variant 3. Variant 3's re-verdict-from-quote is itself a signal to be evaluated against that same
   ground truth — it is never substituted as the ground truth, for any variant, including itself.
4. **Variant 3 is reported as two separate sub-signals plus their union**: quote-not-found-verbatim, and
   verdict-disagreement (conditional on the quote being found), in addition to the combined error signal
   used for the frozen precision/recall metric. This isolates whether failures come from retrieval or
   from re-judgment.
5. **Model confound, stated explicitly as a limitation**: variant 2's Choice calls run on `gpt-4o-mini`
   (the only checked model with logprobs support), while variant 3's re-verdict call runs on `gpt-5-mini`
   (matching the original agent). Any difference observed between variants 2 and 3 is therefore
   confounded with a model difference, not just a mechanism difference (calibration vs. grounding). This
   is carried into RESULTS.md's limitations section verbatim, not glossed over.

### Correction — instrumentation bug found during the first full run (2026-09-26, same day)

The first full run (258 answers, all three variants) completed but produced `P(none fits) == 0.0` for
every single row. Cause: `SurrogateDecider.choice()` labels options `A, B, C, ...` by letter; with 152
active processes + "none fits" = 153 options, labeling ran past `Z` into non-letter characters the model
would never produce as its one-token answer, so the "none fits" label was never a token the model could
actually output — the score was structurally zero, not a finding. This is an implementation defect in the
measurement instrument, not a data inconsistency, so it is fixed rather than reported as a null result.

Fix: added `SurrogateDecider.choice_binary_none(state, process_options)`, which lists every process id as
context in the prompt but asks for a single-token binary answer only — `M` ("matches some listed
process") or `N` ("none fits") — keeping the model's one-token output inside a label space that always
fits. This still yields `P(none fits)` directly (the frozen main signal) but trades away "which specific
process" for reliability; that specific-process identity was never part of any frozen metric, only used
for illustration, so nothing frozen is affected. The full run was redone with this fix before any metrics
were computed; the raw first-run output was discarded (never analyzed for the report; only re-inspected
to diagnose the bug).
