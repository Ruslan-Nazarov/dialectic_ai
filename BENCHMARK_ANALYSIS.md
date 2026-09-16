# DialecticAI — Full Benchmark Analysis (2026-09-14 through 2026-09-16)

**Purpose:** A single, honest account of every benchmarking effort run against this framework — what was tested, what broke, what the real numbers are, and what they actually mean. Written so a reader who wasn't in the room for any of it can tell exactly what is proven, what is suggestive, and what is still unknown. Every number below is sourced to a saved report file or a `development_log.md` entry — nothing here is from memory or eyeballing.

**The short version, if you read nothing else:** three different benchmarking efforts were run, each testing a different thing, and each found something real:
1. **GAIA2** (external, multi-step, agentic) — real infrastructure bugs found and fixed; final task success remains model-capability-gated, not conclusively a framework question either way.
2. **BFCL** (external, single-turn function-calling) — a real, statistically-tested **null result**: this framework's system prompt has no measurable effect (positive or negative) on single-shot function-call accuracy.
3. **Ablation study** (internal, purpose-built) — the one test that actually isolates the framework's own contribution. Result: **generic engineering (not dialectics specifically) explains a huge, real improvement on one failure type** (recovering from a transient tool error); **dialectical reasoning itself shows zero measured deficit** on a decomposition task, but that same test **discovered and precisely quantified a real, fixable robustness bug** (a 35% JSON-parse crash rate tied to the richer dialectical schema).

---

## 1. GAIA2 (`benchmarks/gaia2/`)

**What it tests:** Real, externally-defined agentic tasks (Meta's Agents Research Environments) requiring multi-step tool use inside a live simulated environment, graded by ARE's own pass/fail validator (did the agent's tool-call counts match the oracle's).

**What it does NOT isolate:** the framework's contribution from the underlying model's raw planning capability. A free-tier model's multi-step reasoning ceiling dominates the result far more than any prompt or engine detail.

**What was found and fixed along the way** (see `HANDOFF.md`'s Incident History for full detail): a JSON-repair schema-blindness bug causing ~30-minute stalls; a silent empty-turn stall; a full year-off simulated calendar date (`scenario.environment.get_time()` never existed in ARE's API); a type-classification bug silently breaking every `list[str]` tool argument (recipients, attendees, cc) across nearly every scenario; unresolved `{{placeholder}}` tool-call arguments from parallel-execution confusion. All five are real, independently verified, high-impact framework/adapter bugs — none of them are in question.

**The actual task-success numbers:** 0/5 on the `ambiguity` config (the hardest GAIA2 category, specifically testing recognition of under-specification) across every run this project attempted. 0/5 on the `execution` config too (2026-09-15), with the specific failure mode traced directly to raw model transcripts: the model sometimes states a correct plan in `hypothesis.plan_steps` but then emits an empty `tool_calls` array in the same turn — a genuine instruction-following gap of the underlying model, not a framework logic error (see `development_log.md`, 2026-09-15, "GAIA2 run7 forensics").

**Honest conclusion:** GAIA2 conflates "is this framework good" with "is this specific free-tier model capable of long-horizon planning." Real, valuable bugs were found and fixed, but the benchmark's own headline number (0/5) cannot be read as evidence about the framework one way or the other. This is explicitly out of `REFACTOR_PLAN.md`'s scope for exactly this reason (see its closing section).

---

## 2. BFCL — Berkeley Function-Calling Leaderboard (`benchmarks/bfcl/`)

**What it tests:** Single-turn function-call construction. Given a query and a set of function schemas, does the model pick the right function and supply correctly-typed arguments? No live environment, no multi-turn state — graded by BFCL's own official algorithm (vendored verbatim in `vendored_ast_checker.py` specifically to avoid importing BFCL's own heavy, irrelevant model-handler dependency chain).

**Design:** the SAME model (GigaChat) under two conditions — a bare, minimal function-calling prompt, versus this framework's real system prompt + parser + `JsonRepairer`. 125 cases (25 per category × 5 categories: `simple_python`/`multiple`/`parallel`/`parallel_multiple`/`irrelevance`), each run 3 times per condition (375 × 2 = 750 real calls) because GigaChat is not fully deterministic even at `temperature=0.0` — a single sample per case cannot separate a real effect from noise.

**Real bugs found and fixed along the way:** a grading bug where dotted function names (`metropolitan_museum.get_top_artworks`, present in 85-316 cases per category — not rare) were mishandled by a naive port of BFCL's name-conversion logic; the model echoing a tool's JSON Schema back as call arguments instead of real values (`{"type": "object", "properties": {...}}` instead of `{"image_url": "..."}`); the model inventing values for optional parameters it didn't actually have (`{}` instead of omitting the argument); a diagnostic log line that unconditionally printed a stale, misleading provider list. Three of these were also fixed as new rules in `_AGENT_DIALECTICAL_RULES` (`agent/prompt_builder.py`), with real, cited transcripts as worked examples.

**The result (`bfcl_stats_v3.json`, 750 calls):**

| Category | Raw | Framework |
|---|---|---|
| simple_python | 92.0% | 84.0% |
| multiple | 84.0% | 86.7% |
| parallel | 76.0% | 77.3% |
| parallel_multiple | 80.0% | 77.3% |
| irrelevance | 84.0% | 77.3% |
| **Pooled** | **83.2%** | **80.5%** |

**Wilcoxon signed-rank test on the 125 paired per-case differences: p = 0.582 — not statistically significant.** Only 26/125 cases showed any difference between conditions at all across 3 repeats; 99 were identical.

**Honest conclusion:** on this specific, narrow, single-turn metric, the framework's system prompt has **no statistically detectable effect**, positive or negative. This is a scope-consistent finding, not a discouraging one: BFCL's single-turn design never exercises anything that only matters across multiple turns — which is exactly where this project's real engineering effort went. A null result here says "the prompt wording alone doesn't move single-shot accuracy," not "the framework doesn't help."

---

## 3. Ablation study (`benchmarks/ablation/`) — the test that actually isolates the framework

**Why this exists:** neither GAIA2 nor BFCL isolates the framework's own contribution. GAIA2 conflates it with model capability; BFCL structurally cannot exercise multi-turn recovery logic at all. This study holds the model and the task fixed and varies only the **orchestration loop** around it, across three conditions:

- **bare** — a minimal loop with no repair, no nudge, no duplicate-action detection, no dialectical prompt at all (`bare_agent.py`).
- **engineered** — the SAME loop, plus the exact generic robustness engineering `DialecticalEngine` has (an empty-turn nudge, duplicate-successful-action detection, one minimal JSON-repair retry) — but with **zero dialectical vocabulary**: no Rule 5 fields, no worked examples, no `leap_action_mismatch` contradiction check (`engineered_agent.py`).
- **framework** — the real `DialecticalAgent`/`DialecticalEngine`.

Comparing **bare vs. engineered** isolates what generic software engineering buys on its own. Comparing **engineered vs. framework** — holding that same engineering constant — isolates what the dialectical method itself adds *on top of* generic engineering. This second comparison is the one that actually answers "does dialectics matter," not a bare-vs-framework comparison, which bundles both effects into one number.

### 3a. Scenario `flaky_retry` — a tool that fails once, then succeeds on retry with the same argument

Correct behavior: retry the identical call. 20 real trials per condition (`ablation_stats.json`).

**Result: bare 35.0% (7/20) — framework 100.0% (20/20).** Fisher's exact test: **p = 1.29 × 10⁻⁵** — extremely significant.

**Mechanism, read directly from the saved transcripts, not assumed:** the model retried the failing call correctly in *both* conditions — that part needed no framework help. The bare loop's actual failure was going silent (an empty turn, no tool call, no response) right after the successful retry, with nothing to recover it; separately, when the model tried the already-succeeded call a third time, the bare loop had no way to say "you already have this, answer now." **Both of the decisive mechanisms are generic engineering (the empty-turn nudge, the duplicate-action check) — not anything specifically dialectical.** This scenario has not yet been re-run under the 3-way (bare/engineered/framework) design to isolate whether "engineered" alone would already reach 100% — flagged as the clear next step, not yet done.

### 3b. Scenario `decompose_or_block` — one unconditional action + one part gated on a check that always comes back empty

Modeled directly on the real GAIA2 "Yoga scenario" incident (2026-09-13): save a note (always required) *and* check the calendar for "tentative" events to delete (the check always finds nothing). Correct behavior: save the note regardless — it was never conditional on the calendar check. `check_success` is action-based (was `save_note` actually *called and did it succeed*), specifically to catch a claim/action mismatch, not just a wording pattern. 20 real trials per condition.

**First (raw) result: bare 100%, engineered 90%, framework 35%.** Looked like a strong, significant (p=0.0008) case of dialectics making things *worse*.

**Before accepting that, the trials were broken down by outcome status** — and this surfaced a real, previously-unknown **framework bug**: `engine/executor.py`'s `max_iterations`-exceeded exit path constructed a brand-new `AgentOutput` with **no `evidence` field at all**, silently discarding every tool call made during the run — including genuinely successful ones — the moment the iteration cap was hit. One inspected trial's raw log clearly showed a successful `save_note` call, yet the stored result showed zero tool calls. **Fixed** (`evidence=evidence_store.all()` now included on that path), verified via the full test suite (77 passed, 2 skipped), and the scenario was **re-run from scratch** before drawing any conclusion.

**Corrected result: bare 100%, engineered 95%, framework 65%.** Still significant (p=0.0436) but much smaller. Breaking the 20 framework trials down by status: `completed`=9 (9/9 succeeded), `max_iterations`=4 (4/4 succeeded, now correctly counted), `error`=7 — all seven were the *same* `ControlledRepairError: Failed to repair JSON response` this project has hit and documented before (2026-09-14), a pre-existing, known JSON-repair robustness gap, unrelated to reasoning quality.

**The decisive number: of the 13 trials that did NOT crash on a JSON parse failure, all 13 (100%) succeeded.** The entire remaining gap between framework (65%) and bare (100%) is fully explained by the 35% crash rate — there is **zero evidence, once crashes are excluded, that dialectical decomposition itself performs worse** than the bare or engineered loops. It is, in fact, flawless on this task.

**What this actually means, stated as two separate claims:**
1. **Dialectical reasoning/decomposition: no measured deficit.** 13/13 non-crashed trials correctly decomposed the task, matching bare/engineered's near-perfect rates.
2. **Schema complexity has a real, newly-quantified robustness cost with this model.** A 35% JSON-parse-and-repair-failure rate on the richer, Rule-5-field-carrying schema, versus 0-5% for the much simpler bare/engineered contracts, on the *identical* task and tools. This is the single most concrete, actionable finding of this entire three-day benchmarking effort — a specific, precisely-measured number (not "it crashes sometimes," but "35% of the time, on this exact task shape") pointing at a fixable engineering problem, not a philosophical one.

---

## 4. What we actually know now (the synthesis)

- **The framework's real, demonstrated value so far is in orchestration-loop robustness (retry, nudge, dedup), not in the dialectical vocabulary itself.** `flaky_retry`'s 100%-vs-35% win is real, large, and mechanistically understood — but it is a generic-engineering win. This has not yet been confirmed by actually running the `engineered` condition on this scenario (todo, cheap, ~2 minutes).
- **Dialectical reasoning quality has not been shown to be worse, and has not been shown to be decisively better either — on the two scenarios tested so far.** `decompose_or_block` shows a clean, flawless decomposition rate once crashes are excluded; it is not yet evidence dialectics *outperforms* generic engineering at decomposition specifically, only that it doesn't underperform it.
- **The single highest-value, most actionable finding is the 35% `ControlledRepairError` crash rate**, now precisely quantified for the first time (previous mentions in this project were anecdotal: "a real, live `ControlledRepairError` crash still occurred in the very last GAIA2 run," `development_log.md` 2026-09-15). This is squarely a `REFACTOR_PLAN.md` Phase-1-style reliability problem, not a philosophical one, and is the clearest next step for anyone continuing this work: find out specifically why GigaChat produces malformed JSON on this richer schema at this rate, and whether a repair-prompt improvement, a schema simplification, or a different failure-recovery strategy fixes it.
- **Methodologically:** every one of the three efforts above needed real, repeated sampling (not a single run) to be trustworthy — GigaChat is not fully deterministic even at `temperature=0.0`. Every "surprising" result in this whole investigation (the initial BFCL 40%-vs-93% jump, the decompose_or_block 35%-vs-65% jump) turned out to be a real, fixable bug in the *test harness or the framework itself*, not noise and not the true underlying effect — meaning the discipline of inspecting *why* a number looks the way it does, not just trusting the number, found real bugs at every single stage of this investigation. Two core-framework bugs (the `max_iterations` evidence loss, the bare-loop response-type crash it was modeled against) were found this way, neither of which GAIA2 or BFCL had surfaced despite months of combined use.

## 5. What is explicitly NOT yet known / next steps

- Whether `engineered` alone (without dialectics) already reaches `flaky_retry`'s 100% — not yet re-run under the 3-way design.
- Whether dialectical decomposition specifically *outperforms* generic engineering on a task engineered to actually require Rule 5's five-part reasoning (as opposed to `decompose_or_block`, which both conditions happened to handle equally well once crashes are excluded) — no scenario yet isolates a case where an *engineered-but-non-dialectical* loop genuinely fails at decomposition while the framework succeeds.
- The root cause of the 35% `ControlledRepairError` rate on this specific schema/model combination — diagnosed as "real and quantified," not yet root-caused or fixed.
- `scenarios.py`'s own already-named future additions: a wrong-tool-name error requiring a genuinely different tool, a truncated/incomplete result requiring pagination (the real `n5mmwn` GAIA2 pattern), a scenario specifically isolating a claim/action (`leap_action_mismatch`) contradiction rather than inferring it indirectly.

Every number in this document is reproducible: `bfcl_stats_v3.json`, `ablation_stats.json`, and the exact commands in each section's own `development_log.md` entries (search for "2026-09-15"/"2026-09-16") reconstruct every result from scratch, with a fixed seed where applicable.
