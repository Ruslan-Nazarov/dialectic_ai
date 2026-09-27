# Results — grounding vs calibration

Preregistered in `PREREGISTRATION.md` (including several amendments made before/around these runs, all
dated and marked). Round 1 (variant 2 = surrogate only, bare-id list, now invalid): raw per-answer output
`raw_results.json`, run metadata `run_summary.json`, `metrics_summary.json`. Round 2 (variant 2 = 2a/2b/2c
on the world-brief question): `raw_results_round2.json`, `run_summary_round2.json`,
`metrics_summary_round2.json`.

## Correction (2026-09-27): variant 2's result below is invalid

The variant 2 numbers in this file (AUROC 0.243, the gold-class/difficulty breakdown, everything under
"Headline answer" and "Post-hoc analysis" that concerns variant 2) were produced by asking the model
whether an answer's reasoning "engages" one of 152 **bare process ids** (e.g. `Ib13b23`) — never their
actual formulation (source → target, statement). A bare id carries no meaning to a model with no other
access to the world: the question as actually posed was unanswerable in the way it was intended, not a
genuine test of calibration. This was found while adapting the same measurement for real Jev (variant 2b)
and cross-checking the request each variant actually sends — see `PREREGISTRATION.md`'s amendment dated
2026-09-27 ("variant 2 list-content correction, round 2") for the full account, including why the fix is
the agent's own world-brief text rather than either a bare-id list or a full 152-process list (the latter
also turns out to exceed Jev's per-request token limit).

**The numbers below are kept, not deleted, and marked invalid** wherever they concern variant 2. Variant 1
and variant 3's numbers are unaffected (they never depended on the process list) and stand as reported.
Variant 2 (now 2a) is rerun on the corrected question, alongside real Jev (2b) and an auxiliary variant 2c
— see **"Round 2: variant 2 on the corrected world-brief question"** immediately below for the corrected
numbers.

## Round 2 (2026-09-27): variant 2 on the corrected world-brief question (2a, 2b, 2c)

Full run, 258 answers (same set as round 1 and as the 10-answer pilot; pilot numbers are not included in
any total below — this section reports the full run only). One call each for 2a, 2b, 2c, question asked
against `data.world_brief()` (7,717 characters — verified byte-identical to the text the agent itself saw
in its system prompt during the original `eval_v3.py` run; see PREREGISTRATION.md's round-2 amendment).
Raw output: `raw_results_round2.json`. Run metadata: `run_summary_round2.json`,
`metrics_summary_round2.json`.

### Main metric (frozen): AUROC of P(none fits)

| Variant | AUROC | 95% CI |
|---|---|---|
| 2a (surrogate, `gpt-4o-mini`) | 0.223 | [0.149, 0.302] |
| 2b (Jev) | 0.278 | [0.198, 0.362] |
| 2b − 2a (paired) | 0.055 | [−0.010, 0.122] |

Bootstrap: 2000 resamples, grouped by (doc, hypothesis) pair (`metrics.bootstrap_ci`, seed 42). By the
frozen thresholds (AUROC ≥ 0.65 and CI lower bound > 0.5 for "helps"; CI lower bound ≤ 0.5 for "does not
help"): **2a → CALIBRATION DOES NOT HELP. 2b → CALIBRATION DOES NOT HELP.** The 2b − 2a difference CI
includes 0.

### Auxiliary: 0.5-threshold error signal (precision/recall)

| Variant | precision | recall | signal rate \| correct | signal rate \| incorrect |
|---|---|---|---|---|
| 2a | 0.182 | 0.034 | 0.129 | 0.034 |
| 2b | 0.283 | 0.331 | 0.707 | 0.331 |
| 2c | 0.259 | 0.119 | 0.286 | 0.119 |

### Exploratory: breakdown by gold class

| Gold class | n (correct/wrong) | 2a mean P(none) / AUROC | 2b mean P(none) / AUROC | 2c mean P(none) / AUROC |
|---|---|---|---|---|
| Contradiction | 138 (51/87) | 0.050 / 0.097 | 0.458 / 0.192 | 0.217 / 0.308 |
| Entailment | 60 (55/5) | 0.047 / 0.811 | 0.500 / 0.531 | 0.327 / 0.651 |
| NotMentioned | 60 (34/26) | 0.273 / 0.000 | 0.550 / 0.206 | 0.313 / 0.206 |

### Exploratory: breakdown by difficulty group

| Group | n (correct/wrong) | 2a mean P(none) / AUROC | 2b mean P(none) / AUROC | 2c mean P(none) / AUROC |
|---|---|---|---|---|
| contradiction_easy | 40 (40/0) | 0.068 / n/a | 0.601 / n/a | 0.269 / n/a |
| entailment | 60 (55/5) | 0.047 / 0.811 | 0.500 / 0.531 | 0.327 / 0.651 |
| hard | 98 (11/87) | 0.043 / 0.115 | 0.400 / 0.351 | 0.196 / 0.439 |
| not_mentioned | 60 (34/26) | 0.273 / 0.000 | 0.550 / 0.206 | 0.313 / 0.206 |

`contradiction_easy` has 0 wrong answers in this group, so AUROC is undefined there (n/a) for every
variant.

### Cost and time (full run)

| Variant | input tokens | output tokens | calls | wall clock (16 workers) |
|---|---|---|---|---|
| 2a | 548,103 | 258 | 258 | 13.8s |
| 2b | 1,619,888 | 7,998 | 258 | 7.8s |
| 2c | 2,671,496 | 39,900 | 258 | 7.9s |

At the TypeSafe rate confirmed against the console on 2026-09-27 (~$0.034 / million tokens): 2b + 2c ≈
4.34M tokens ≈ **$0.15**. 2a runs on a separate OpenAI account (`gpt-4o-mini`), cost negligible.

### Reading these numbers

2a and 2b ask the identical question against the identical world-brief text; both land at "calibration
does not help" under the frozen thresholds, and the difference between them is not distinguishable from
noise (CI spans 0). The aggregate AUROC for both is pulled down by the Contradiction class, which is both
the largest class (138/258) and the hardest (87 wrong) — 2a's AUROC is much higher in isolation on
Entailment (0.811, but only 5 wrong answers to rank against) and near 0 on NotMentioned, so the single
aggregate number mixes very different per-class behavior. 2c (auxiliary, not part of the frozen 2b-vs-2a
comparison) has a different probability profile from 2a/2b in every row above — lower mean P(none fits),
higher AUROC wherever AUROC is defined — consistent with its multi-way option set diluting "none fits"
probability mass differently than a binary question does; this is reported for completeness, not as a
finding, since 2c was declared auxiliary before this run.

This section supersedes round 1 for variant 2. Round 1's numbers remain below, unchanged, marked invalid.

## Sanity check

Recomputed accuracy over all 258 `arm == "world"` rows in `contract_nli_runs/eval_v3.json`, using
`verdict == gold` with gold cross-checked against `live_runs/contract_nli/contract-nli/test.json`:
**54.3%** (140 correct / 118 wrong). Reconciles with `contract_nli_runs/eval_v3.md`'s reported 54%
(world column, ALL row). Source: `data.py:sanity_check_accuracy`, `data.py` lines 100-105.

World used: `live_runs/v3_worlds/договоры_о_неразглашении_nda_одна_сторона_раскрывает_другой_/v1.json`
("Договоры о неразглашении (NDA)..." v1, built), 155 processes total: **152 active, 3 retired**. Only
active processes were offered as options in variant 2.

## Headline answer

**Variant 2 (calibration): below random. [INVALID — see "Correction (2026-09-27)" above: the model was
asked about 152 bare process ids, never their formulation. Kept for the record, not to be cited.]** The
frozen main signal, `P(none fits)` from the
Choice-with-probabilities surrogate, scores **AUROC 0.243** (95% CI [0.170, 0.320], bootstrap n=2000,
resampled by (doc, hypothesis) pair). That CI sits entirely *below* 0.5 — the frozen threshold for
"calibration does not help" was any CI overlapping or below 0.5, and this result is stronger than that:
the signal is not merely uninformative, it's **inverted**. The model reports "none fits" more often on
answers that turn out to be *correct* than on ones that are wrong (signal rate 0.450 vs 0.127). *Why* it's
inverted is addressed in the post-hoc breakdown below (§ Post-hoc analysis) — in short, `P(none fits)`
tracks which gold class the statement belongs to, not whether the agent's answer about it was right.

**Variant 3 (quote-anchored re-verdict, renamed from "practice" -- see below): a moderate signal with a lot of false positives.** Its combined error signal has
precision 0.531 / recall 0.797 (95% CI on precision [0.427, 0.632], recall [0.696, 0.890]) — it catches
80% of wrong answers, but 59% of the answers it flags are actually correct (see § Post-hoc analysis for
the full confusion table and the "flag everything" baseline comparison). All of that signal comes from
one sub-mechanism (model re-verdict from a quote); the mechanical "quote not found" check never fires at
all in this run, for a structural reason explained below.

Variant 1 (self-report) is completely uninformative — not close to chance, *zero variance*: every one of
the 258 `world`-arm rows has `fits = True` (matches `eval_v3.md`'s own tally: "world world_fit marks:
fits=258, does not fit=0, missing=0"), so its precision is undefined (no positive signal ever fires) and
recall is 0.

## Metrics table

| Variant | Signal | Precision | Recall | AUROC | Signal rate\|correct | Signal rate\|incorrect |
|---|---|---|---|---|---|---|
| 1. Self-report | `fits != True` | n/a (never fires) | 0.000 | n/a (binary, constant) | 0.000 | 0.000 |
| 2. Choice (main) | `P(none fits)` (continuous; binary cutoff 0.5 for precision/recall) | 0.192 | 0.127 | **0.243** [0.170, 0.320] | 0.450 | 0.127 |
| 2. Auxiliary | top-choice confidence | -- | -- | 0.283 | -- | -- |
| 2. Auxiliary | normalized entropy | -- | -- | 0.283 | -- | -- |
| 3. Quote-anchored re-verdict — quote not found | binary | n/a (never fires) | 0.000 | n/a | 0.000 | 0.000 |
| 3. Quote-anchored re-verdict — verdict disagree | binary | 0.531 | 0.797 | n/a (binary) | 0.593 | 0.797 |
| 3. Quote-anchored re-verdict — union (frozen) | binary | **0.531** [0.427, 0.632] | **0.797** [0.696, 0.890] | n/a (binary, per prereg) | 0.593 | 0.797 |

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

## Post-hoc analysis (after seeing results, 2026-09-26)

Everything in this section was run *after* the frozen results above and is exploratory: it does not
change any frozen metric, threshold, or verdict, and none of it was preregistered. Computed by
`post_hoc.py`, raw numbers in `post_hoc_summary.json`.

### Variant 3, full confusion table

| Signal | TP | FP | TN | FN | Flag rate | FP rate\|correct | Precision | Recall |
|---|---|---|---|---|---|---|---|---|
| **Baseline — flag everything** | 118 | 140 | 0 | 0 | 1.000 | 1.000 | 0.457 | 1.000 |
| Quote not found (mechanical, code) | 0 | 0 | 140 | 118 | 0.000 | 0.000 | n/a (never fires) | 0.000 |
| Verdict disagree (model re-verdict) | 94 | 83 | 57 | 24 | 0.686 | 0.593 | 0.531 | 0.797 |
| **Union (frozen metric)** | 94 | 83 | 57 | 24 | 0.686 | 0.593 | 0.531 | 0.797 |

The union signal is identical to "verdict disagree" alone in this run — the mechanical quote-check
contributes nothing, for the structural reason already noted (retrieval always returns a real substring
of the contract, so it can never fail to be "found"). So whatever discriminative power variant 3 has
here comes entirely from a second model call (re-deciding the verdict from one quote), not from an
external, code-only check — the "external signal" in this design is only external in the sense that the
quote is fixed by search, not chosen post-hoc by the model; the actual judgment that catches errors is
still a model call.

Against the "flag everything" baseline (precision 0.457, since that's just the base rate of wrong
answers): the union signal's precision (0.531) is only modestly above that baseline, while its 59%
false-positive rate among *correct* answers means well over half of what it flags is actually fine. This
supports the "moderate signal, many false positives" characterization rather than "the practice signal
solves detection."

### Variant 2, breakdown by gold class and by difficulty group [INVALID — see correction above]

| Gold class | n | correct/wrong | mean P(none fits) | AUROC |
|---|---|---|---|---|
| Contradiction | 138 | 51 / 87 | 0.296 | 0.180 |
| Entailment | 60 | 55 / 5 | 0.243 | 0.578 |
| NotMentioned | 60 | 34 / 26 | 0.493 | 0.048 |

| Difficulty group | n | correct/wrong | mean P(none fits) | AUROC |
|---|---|---|---|---|
| contradiction_easy | 40 | 40 / 0 | 0.538 | n/a (no wrong answers in this group) |
| entailment | 60 | 55 / 5 | 0.243 | 0.578 |
| hard | 98 | 11 / 87 | 0.197 | 0.283 |
| not_mentioned | 60 | 34 / 26 | 0.493 | 0.048 |

This confirms the hypothesis behind the "reflects class, not correctness" reading: mean `P(none fits)`
varies by roughly 2x across gold classes (0.243 to 0.493) largely independent of how often the agent was
actually right in that class, and AUROC swings from 0.048 (NotMentioned — worse than inverted) to 0.578
(Entailment — mildly better than chance) depending on which class is being scored. A signal whose
predictive direction flips sign across classes is not a usable calibration signal on its own; it is
picking up something about the statement's gold category (plausibly: how much of the NDA world's
process vocabulary a NotMentioned statement can plausibly be phrased against, versus an Entailment one),
not about whether the agent's specific answer to it was correct. This is the explanation for the
"below random" headline above, not a justification for softening it.

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
  agent). Any observed difference between "calibration" and "quote-anchored re-verdict" is confounded with this model
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
- **Round 2 (Jev, variant 2b/2c) is one specialized domain, evaluated with Jev outside the domains it is
  trained for.** Per TypeSafe's own stated limitations, Jev is not trained on specialized domains, and
  ContractNLI (legal contracts) is one. Round 2's result is "Jev on a specialized domain it is not trained
  for," not a general claim about Jev's capability elsewhere.
- **Round 2 still uses one agent model** (`gpt-5-mini`, the model that produced the 258 answers being
  scored) and one world (the NDA world, v1). Neither 2a/2b/2c's result generalizes beyond this agent model
  or this world without a separate run.
- **2c is not a validated design**, only an auxiliary/exploratory one declared before the round-2 run: its
  option set (~11 processes actually mentioned in the brief) is a byproduct of the brief's own size limit,
  not a deliberately chosen sample of the world's 152 processes.

## Source-of-numbers index

| Metric | Value | Source | Status |
|---|---|---|---|
| Sanity-check accuracy (world arm) | 54.3% | `data.py:sanity_check_accuracy`, run via `python data.py` | matches `eval_v3.md`'s 54% |
| Active/retired processes | 152 / 3 (of 155) | `data.py:active_process_ids`, inspected directly against `v1.json` | — |
| `gpt-5-mini` logprobs support | False | `decider.py:supports_logprobs("gpt-5-mini", ...)` | checked live, `decider.py` |
| `gpt-4o-mini` logprobs support | True | `decider.py:supports_logprobs("gpt-4o-mini", ...)` | checked live, `decider.py` |
| Variant 2 AUROC | 0.243 [0.170, 0.320] | `analyze.py`, printed from `metrics.auroc` + `metrics.bootstrap_ci` over `raw_results.json` | **INVALID (2026-09-27), see correction above** — printed programmatically, `analyze.py:114-121`, not hand-typed |
| Variant 3 union precision/recall | 0.531 / 0.797 | `analyze.py`, `metrics.precision_recall` over `raw_results.json` | printed programmatically |
| Token/call/time totals | see cost table above | `run_summary.json`, generated by `full_run.py` | printed programmatically, not hand-typed (variant 2 portion invalid alongside the AUROC above) |
| Variant 3 confusion table (post-hoc) | see table above | `post_hoc.py:confusion()`, printed to `post_hoc_summary.json` | printed programmatically, exploratory (not frozen) |
| Variant 2 by-gold-class / by-group breakdown (post-hoc) | see tables above | `post_hoc.py`, printed to `post_hoc_summary.json` | **INVALID (2026-09-27), see correction above** — printed programmatically, exploratory (not frozen) |
| Round 2: 2a AUROC | 0.223 [0.149, 0.302] | `analyze_round2.py` over `raw_results_round2.json` | printed programmatically, frozen metric |
| Round 2: 2b AUROC | 0.278 [0.198, 0.362] | `analyze_round2.py` over `raw_results_round2.json` | printed programmatically, frozen metric |
| Round 2: 2b−2a AUROC diff | 0.055 [−0.010, 0.122] | `analyze_round2.py`, paired bootstrap over `raw_results_round2.json` | printed programmatically, frozen metric |
| Round 2: token/call/time totals | see cost table above | `run_summary_round2.json`, `full_run_v2.py` | printed programmatically |
| Round 2: by-gold-class / by-group breakdown (2a/2b/2c) | see tables above | `analyze_round2.py`, printed to `metrics_summary_round2.json` | printed programmatically, exploratory (not frozen) |
