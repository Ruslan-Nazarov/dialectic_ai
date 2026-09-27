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

### Amendment — adding real Jev as variant 2b, before any Jev call on data (2026-09-27)

TypeSafe (Jev) access was obtained after the run above (which used `SurrogateDecider` throughout, on
`gpt-4o-mini`, as a stand-in for a real Choice-with-probabilities model). This amendment is written and
committed before Jev is called on any of the 258 answers or the pilot's 10 answers — only 3 pilot answers
have been used so far, for a smoke test of the API adapter itself (response shape, request contents,
authenticity of the calls), never analyzed as data.

1. **Jev is added as variant 2b; variant 2 (surrogate, `gpt-4o-mini`) is renamed 2a and is not touched** —
   its code, thresholds, and already-reported results (RESULTS.md, `raw_results.json`,
   `metrics_summary.json`) stand as they are. No file belonging to 2a's frozen run is edited by this
   amendment.
2. **The primary 2b question is identical to 2a's, not the 153-way Choice the API's option limit would
   technically allow.** `JevDecider.choice_binary_none()` asks Jev the same binary question
   `SurrogateDecider.choice_binary_none()` asks — same process-id listing, same wording ("Does this
   answer's reasoning engage ANY of the processes listed above, or NONE of them?") — via Jev's real
   `choice` primitive with two options (`some` / `none`), instead of a single-token logprob hack. This was
   corrected from an earlier draft of this amendment, which planned a full 152-process-plus-none Choice
   call for the primary comparison; that would have changed what question is being asked, not just which
   model answers it, confounding the 2a-vs-2b comparison. The 153-way version is preserved as **variant
   2c**, declared auxiliary/exploratory below (point 3), decided and written down before any Jev call on
   pilot or full-run data.
3. **Main signal, main metric, and thresholds for 2b are unchanged from 2a**: `P(none fits)` read off
   2b's returned probability distribution, evaluated by AUROC against the same frozen thresholds in
   "Decision thresholds (frozen before results)" above. Auxiliary signals (Jev's own `confidence` field,
   normalized entropy where applicable) are computed and reported the same way as for 2a, not evaluated
   against the frozen thresholds.
   - **Variant 2c (auxiliary, exploratory)**: `JevDecider.choice_full()`, a genuine multi-way Choice over
     all 152 active processes plus "none fits" (153 options total — inside Jev's documented 255-option
     limit, confirmed against the live API docs before writing this adapter). `P(none fits)` from 2c's
     distribution is reported alongside 2b's for comparison, plus 2c's own top-choice identity (which
     specific process, when not "none fits") since 2c, unlike 2a/2b, can actually name one. 2c is never
     evaluated against the frozen AUROC thresholds and never substituted for 2b in the primary comparison.
4. **The primary comparison is 2b vs. 2a on the same 258 answers**, both asking the identical binary
   question, with 95% bootstrap CIs (2000 resamples, grouped by (doc, hypothesis) pair, per the frozen
   metrics section above) on `P(none fits)`-based AUROC for each, and on their difference.
5. **Breakdown by ContractNLI gold class and by the same difficulty grouping already used for 2a**
   (`post_hoc.py`) is computed for 2b (and reported for 2c) the same way, labeled exploratory — same
   status it already has for 2a, not upgraded to a frozen comparison.
6. **Stability check (auxiliary)**: the same 10-answer pilot set is run twice for each of 2a and 2b;
   distributions of `P(none fits)` between the two runs are compared per variant. This checks each
   variant's own run-to-run stability, not 2a-vs-2b agreement.
7. **Scope caveat, to be repeated in RESULTS.md's limitations section**: per TypeSafe's own stated
   limitations, Jev is not trained on specialized domains, and ContractNLI is a legal/specialized domain.
   2b's result is therefore reported as *"Jev on a specialized domain it is not trained for"*, not as a
   general claim about Jev's capability.
8. **Nothing above is changed after results are seen.** Any post-hoc adjustment goes in a new, separately
   dated "after seeing results" subsection below this one, exactly as the existing amendments in this file
   already do — never edited into this section in place.

### Correction — variant 2 list-content correction, round 2 (2026-09-27, same day, before any data run)

Two problems were found in the amendment above, both before any Jev call on pilot or full-run data, and
both invalidate the **already-reported 2a result** (RESULTS.md's variant 2 AUROC 0.243 and its gold-class/
difficulty breakdown — see the dated correction now at the top of RESULTS.md).

**Problem 1 — the process list carried no meaning.** `active_process_ids()` returns bare ids (e.g.
`Ib13b23`), never a process's actual formulation (`source`, `target`, `statement` — the fields that make a
process a transition, per the engine's own model). Every variant of variant 2 run so far (the original 2a,
and this amendment's planned 2b/2c) asked the model whether an answer's reasoning "engages" one of 152
opaque codes — a question that is not meaningfully answerable, because the codes carry no content. This
is a defect in the question's construction, not a finding about calibration; **RESULTS.md's variant 2
numbers are marked invalid for this reason**, not deleted.

The first fix attempted — listing each process as `id: source -> target (statement)` (`data.process_description()`)
— surfaced **problem 2: it doesn't fit.** The full 152-process list with real formulations is ~48.9k
characters (~21k tokens by an OpenAI-tokenizer proxy). `SurrogateDecider` (`gpt-4o-mini`) accepted it
(13,178 input tokens, real call, confirmed). **Jev rejected it**: HTTP 400, `{"detail":
{"error_type":"max_tokens_exceeded"}}` — a real, live-confirmed limit, not assumed from docs (TypeSafe's
Models page: `jev-latest` allows 64k tokens per request total, 32k for `state` plus the longest question;
Jev's own tokenizer is evidently far less token-efficient than OpenAI's for this Cyrillic-heavy text).
Splitting the list across multiple calls was considered and rejected — it changes the methodology
(probabilities would need combining across calls, a different measurement than a single Choice
distribution) and would need its own preregistration, not a quick patch.

**Fix: variant 2 (2a, 2b, 2c) asks about the world-brief text the agent itself saw, not an exhaustive
process list.** `dialectic_world`'s `WorldAdapter.brief()` — the same class and the same `max_chars=8000`
`eval_v3.py` used to build the "world" arm's system prompt (confirmed against `ENGINE_V3_RESULTS.md`:
"изложение мира (до 8000 знаков)") — produces a size-limited excerpt (core process chain first, then
top developing/internal processes, cut to fit) that is exactly what the agent had access to when it
produced the answers being scored. This is not a new construction invented for variant 2: it is the
existing engine's own adapter, read (never modified) from `experiments/grounding_vs_calibration/data.py`.
For the NDA world (`v1.json`), the brief is **7,717 characters, ~3,247 tokens** (OpenAI-tokenizer proxy —
comfortably inside Jev's 32k state+question limit) and mentions **11 unique processes** (of 152 active).

**Verified against the actual eval_v3.py run, not assumed**: `eval_v3.md`'s own header records
`world 'Договоры о неразглашении (NDA)...' v1 (built)` — confirming **v1**, not the `v2.json` that exists
alongside it in `live_runs/v3_worlds/.../` (a later, unrelated revision). `--brief`'s default is 8000
(`eval_v3.py:155`), and `ENGINE_V3_RESULTS.md` independently states the world arm's system prompt used
"изложение мира (до 8000 знаков)" — no override is recorded anywhere. Reproduced the exact call
(`World.model_validate_json` + `WorldAdapter(world, max_chars=8000).brief()`) directly against the real
`live_runs/v3_worlds/договоры_о_неразглашении_nda_одна_сторона_раскрывает_другой_/v1.json` (outside this
experiment's own `data/` copy) and compared byte-for-byte against `data.world_brief()`'s output: **identical**
(same SHA-256, `aed80d0b...`). The `data/world_nda_v1.json` copy this experiment uses is also byte-identical
to that source file (separately verified, same SHA-256, `4e208c8c...`). No discrepancy found.

1. **2a and 2b ask the identical binary question against the brief, not a process list.** "World
   description (as given to the agent): {brief}\n\nDoes this answer's reasoning engage ANY of the
   processes described above, or NONE of them?" — `SurrogateDecider.choice_world_brief()` (2a, single-token
   M/N logprob answer) and `JevDecider.choice_world_brief()` (2b, real two-option Choice). Same text, same
   wording, same length, for both. This also brings variant 2 into the same condition as **variant 1**
   (self-report, `fits`): both now judge the answer against the same world-brief the agent itself worked
   from, not a superset the agent never saw.
2. **Variant 2c (auxiliary, exploratory) uses only the processes the brief itself mentions.**
   `data.brief_process_descriptions()` extracts each process actually named in the brief (by its `[id]`
   marker) together with its own formulation (`Process.line()`) — 11 processes for this world, not 152.
   `JevDecider.choice_brief_processes()` runs a real multi-way Choice over these 11 plus "none fits". Since
   the option set is small, no token-limit issue arises. 2c remains auxiliary/exploratory, never part of
   the primary 2b-vs-2a comparison, per the amendment above (unchanged).
3. **Variant 2 (2a, 2b, 2c) is rerun in full** on the corrected question before any metric is computed or
   reported. The already-reported 2a run (bare-id question) is superseded, not reused or partially
   combined with the corrected run. Main signal, main metric (`P(none fits)`, AUROC), thresholds, bootstrap
   procedure, class/difficulty breakdown, and stability check are all unchanged from the amendment above —
   only the question's content (brief instead of bare-id list, or instead of full-formulation list) changes.
4. **Code affected**: `data.py` (`world_brief()`, `brief_process_ids()`, `brief_process_descriptions()` —
   new, read `dialectic_world`'s `WorldAdapter`/`World` read-only, no engine file edited);
   `decider.py` (`SurrogateDecider.choice_world_brief()`, `JevDecider.choice_world_brief()`,
   `JevDecider.choice_brief_processes()` replace the bare-id/full-list methods of the amendment above);
   `pilot.py` and `full_run.py` updated to call the brief-based methods. `variant2_scores()` /
   `variant2_error_signal()` in `variants.py` are unchanged — they only ever read `probabilities["none
   fits"]`, which every version of variant 2 has always returned.
5. Smoke-tested before any pilot/full-run data call: one real 2a call (13,178 input tokens, `gpt-4o-mini`,
   confirming the full-list version worked structurally) and one real 2b call attempt (confirming the
   `max_tokens_exceeded` rejection) on the first pilot answer, under the now-superseded full-formulation
   design. Both calls' purpose was diagnosing the list content and the token limit, not measuring anything;
   neither is treated as data.
6. **Brief-based design smoke-tested, before this amendment was committed, form-check only**: 3 real calls
   each for 2a and 2b (6 calls total) on the same first 3 pilot answers, confirming the request/response
   shape and that no `max_tokens_exceeded` or similar error occurs (2b: 6,250–6,280 input tokens per call,
   comfortably under the 32k limit). Outputs were inspected for shape and plausibility only (e.g. that
   `P(none fits)` moves sensibly and isn't stuck), never treated as pilot or full-run data, and are not
   included in any metric. The 10-answer pilot proper (stability check, point 6 of the amendment above)
   runs after this amendment is committed. Console usage reconciled against this session's own per-call
   token accounting on 2026-09-27 (both the earlier full-list smoke test and this one): 14 requests, 49,791
   tokens, $0.0017 total — the console's earlier "2 requests / 775 tokens" reading was a stats-display
   delay, not a real discrepancy.

Smoke-test note: before this amendment was written, 3 of the pilot's 10 answers were sent to real Jev
(`api.typesafe.ai`, confirmed via per-call `x-typesafe-request-id` response headers, sub-second real
round-trip times, and the actual key's last four characters) for both 2b and 2c, solely to check the
adapter's request/response shape and that `P(none fits)` does not structurally stick at zero the way 2a's
first attempt did. Those 3 answers' Jev outputs were inspected for shape only, never treated as a result
and never included in any metric — the 10-answer pilot proper (point 6 above) has not run yet.
