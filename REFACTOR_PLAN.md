# DialecticAI — Refactor Plan

**Date:** 2026-09-15
**Purpose:** A prioritized, self-contained, executable plan to take DialecticAI from "works, with known sharp edges" to "good, stable state," suitable for hackathon prep. Written so that a fresh AI session (any model, any tool) with no memory of prior conversations can pick up any phase and execute it correctly using only this document, [CODE_REVIEW.md](CODE_REVIEW.md), [PROMPTS.md](PROMPTS.md), and the codebase itself.
**How to use this document:** Work top to bottom. Each phase lists concrete files, the exact change, why (with a `CODE_REVIEW.md` cross-reference), and a verification step. Do not skip verification steps — this project has a documented history (`development_log.md`) of fixes that looked correct on paper and were not, until verified against a real LLM provider on real data.

**Before starting any phase:** run the existing test suite and sandbox to establish a baseline:
```bash
python -m pytest tests/ -q
python tests/local_runner.py
```
Expected baseline (as of 2026-09-15): `75 passed, 1 skipped`; sandbox 3/3 scenarios `status=completed`. If your baseline differs, something changed since this document was written — investigate before proceeding, don't assume this plan's line numbers/context still match exactly.

---

## Phase 0 — Safety net before touching anything (do this first, always)

1. Confirm `.env` has at least one working LLM credential. As of this session, `GIGACHAT_AUTH_KEY` is the most reliable (see `PROMPTS.md` and `HANDOFF.md` for why). `GEMINI_API_KEY` has a very tight free-tier quota (20 requests/day observed) and `GROQ_API_KEY`'s free tier has an 8000 token/minute cap — both are usable for quick smoke tests but not for repeated full runs.
2. `pip install -e .[dev]` (uses `pyproject.toml`, added this session) so `ruff`/`mypy`/`pytest-cov` are available locally even though CI does not run them yet (see Phase 5).
3. After every phase below: `python -m pytest tests/ -q` (must stay green) and `python tests/local_runner.py` (must stay 3/3 `completed`). These are fast (seconds) and catch regressions before you spend minutes on a real GAIA2 run.

---

## Phase 1 — Reliability of the LLM integration layer

**Status: ✅ DONE (2026-09-15)** — see `development_log.md`'s "[2026-09-15] Refactor Phase 1" entry for what was actually built and how it was verified (including a live real-provider 429 caught mid-run). All four sub-items (1.1-1.4) complete.

**Why this phase is first:** every other phase depends on being able to trust that a failed LLM call fails *cleanly* (retried, or reported) rather than crashing the whole run or silently degrading. This session lost real time to exactly this class of problem (`ControlledRepairError` crashes, `429`-then-dead providers). See `CODE_REVIEW.md` → Layer 0/2, "Cross-cutting findings" #1 and #4.

### 1.1 — Give `GigaChatLLM` retry/backoff parity with `OpenAILLM`
- File: `dialectic_ai/integrations/gigachat/llm.py`
- `OpenAILLM` (`dialectic_ai/integrations/openai/llm.py`) already has a correct, tested pattern: `_wait_time_for(attempt, headers)` (exponential backoff + jitter, honors `Retry-After`/`x-ratelimit-reset-tokens`) and `_call_sync(req)` (retries on `{429, 500, 502, 503, 504}` and `URLError`/`TimeoutError`, `max_retries` configurable in `__init__`).
- Port the same pattern into `GigaChatLLM`: extract its HTTP call (currently inline in `generate()`) into a `_call_sync` helper with the same retry loop, add `max_retries: int = 3` to `__init__` alongside the `max_tokens` parameter already added this session.
- **Do not** just copy-paste `OpenAILLM`'s code verbatim — `GigaChatLLM` has its own OAuth token flow (`_get_access_token`) that must run before every retry attempt if the token could have expired mid-retry-loop; reuse the token-refresh call inside the retry loop, not just once before it.
- Verification: write a small script (see `tests/local_runner.py` for the pattern of a throwaway `BaseLLM` subclass with `@dialectical(...)`) that forces a `429` on the first call and a success on the second, confirm it retries instead of raising immediately. This exact test-double pattern was used successfully this session for `engine/repair.py`'s fix — reuse it.

### 1.2 — Consider a shared retry helper instead of two parallel implementations
- `GeminiLLM`'s retry loop (`integrations/gemini/llm.py`, 5 attempts, linear `3 * (attempt+1)` backoff) is older and simpler than `OpenAILLM`'s. Once 1.1 is done, you will have **three** independent retry implementations doing conceptually the same thing.
- Extract a small shared utility, e.g. `dialectic_ai/core/retry.py` with a function `async def retry_http_call(fn, *, max_retries, retryable_status_codes, backoff_fn) -> T`, and have all three providers call it. This is a genuine simplification, not scope creep — three copies of the same 15-line loop is worse than one shared 15-line loop, and the framework's own `dialectics_rules.md` Rule 1 (derivation) argues against parallel, disconnected reimplementations of the same idea.
- Verification: existing provider-specific tests should still pass; add one new test against the shared helper in isolation (no need to re-test each provider's retry behavior three times if they all delegate to the same tested function).

### 1.3 — Evict rate-limited providers from `BalancingLLM`'s rotation
- File: `dialectic_ai/core/llm.py`, `BalancingLLM.preflight_health_check()` and `generate_result()`.
- Current eviction only fires on 404/400/"decommissioned" substrings. Add: if a provider fails with a 429 or 401/403 **more than once in a row** during a single `generate_result` call's retry loop, mark it temporarily unavailable for the rest of the *session* (a simple `self._cooldown_until: dict[provider_id, timestamp]` is enough — no need for anything fancier).
- This directly addresses the `RuntimeError('All providers failed in BalancingLLM. Last error: GigaChat API Error 429...')` crash observed live this session.
- Verification: construct a `BalancingLLM` with a test-double provider that always 429s and a second that always succeeds; confirm that after the first provider's cooldown triggers, subsequent calls go straight to the second provider instead of wasting a round-trip on the first.

### 1.4 — Cap the size of text re-embedded in `JsonRepairer`'s own prompt
- File: `dialectic_ai/engine/repair.py`
- `repair()` embeds the full `raw_response` in its own prompt with no cap (see `CODE_REVIEW.md` → Layer 3). Mirror the pattern already used in `engine/executor.py._phase_collide` (added this session, currently a 6000-character cap with a truncation note) — cap `raw_response` similarly before embedding it, since a long, already-malformed response is likely part of why the *original* call ran long in the first place, and re-sending all of it in the repair prompt compounds that.
- Verification: this is defense-in-depth, not something you can easily force-trigger in a unit test. After making the change, do one live GAIA2 run (`python -m benchmarks.gaia2.runner --limit 5`, see Phase 4 for provider config) and confirm no new `ControlledRepairError` appears where one didn't before. Do not claim this fixed the residual crash from `development_log.md`'s 2026-09-14 entries without this live check — this project has a documented pattern of "looked fixed, was not" for exactly this failure mode.

---

## Phase 2 — Fix confirmed, cheap, high-value bugs

**Status: ✅ DONE (2026-09-15)** — 2.1-2.5 fixed exactly as scoped. 2.6 done as option (b) (honest `[MOCK]` relabeling, not a real search implementation) per this plan's own hackathon-time recommendation.

These are small, independent, low-risk fixes. Do them in any order; each has its own verification.

### 2.1 — Fix the broken `examples/triad/run_triad.py`
- File: `examples/triad/run_triad.py`
- `main()` is synchronous and calls `triad.run(task)` without `await` (`DialecticalTriad.run` is `async def`). This raises `AttributeError` on `result.response` — see `CODE_REVIEW.md` → Layer 6 for the full analysis.
- Fix: make `main()` async, `await triad.run(task)`, and change the bottom guard to `if __name__ == "__main__": asyncio.run(main())` (add `import asyncio` at the top).
- Verification: run it (`GEMINI_API_KEY` required, or swap `GeminiLLM()` for a configured `OpenAILLM()`/`GigaChatLLM()` if no Gemini key is available) and confirm it completes and prints a final synthesis instead of crashing.

### 2.2 — Add `GigaChatLLM` to the CLI's LLM choices
- Files: `dialectic_ai/cli/creator.py` (interactive wizard's LLM menu, step 4) and `dialectic_ai/cli/config_parser.py` (`load_agent_from_config`'s `llm_name` if/elif chain and `TOOL_REGISTRY`-adjacent LLM selection logic).
- Add a `gigachat` option in both places, matching the existing pattern for `gemini`/`openai` (import `GigaChatLLM` from `dialectic_ai.integrations.gigachat.llm`, construct with no args so it picks up `GIGACHAT_AUTH_KEY` from `.env`).
- Also update `_build_runtime_llm` in `cli/creator.py` (used by the `DialecticalArchitect` goal-refinement pass) with the same new option, and update `benchmarks/gaia2/adapter.py`'s pattern is already correct (GigaChat is already there) — use it as the reference for exact construction.
- Verification: run `tests/test_layer6_creator.py`'s existing tests (must still pass, since GigaChat is a new *additional* choice, not a replacement), then manually run `python -m dialectic_ai.cli.main create` and choose the new option, confirm the generated agent script imports and constructs `GigaChatLLM` correctly.

### 2.3 — Fix the duplicate `process_turn` in `SQLiteKnowledgeGraphMemory`
- File: `dialectic_ai/memory/sqlite_graph.py`
- Two `process_turn` method definitions exist (see `CODE_REVIEW.md` → Layer 1). Delete the first (lines ~52-61, the one without `details` and the `if updates:` guard) — the second one (currently "live" because it's defined later) is the correct, more complete version. Just remove the dead first definition; do not change behavior.
- Verification: `python -m pytest tests/ -q` still green (no test currently distinguishes the two, so this is a safe, behavior-preserving cleanup — confirm no test file references `SQLiteKnowledgeGraphMemory` in a way that would be affected before deleting).

### 2.4 — Fix `EvidenceStore`'s incomplete `__init__`
- File: `dialectic_ai/engine/evidence_store.py`
- Add `self._executed_actions: set = set()` to `EvidenceStore.__init__`, so the attribute is part of the class's own definition instead of being bolted on externally in `engine/executor.py`'s `run()` (`evidence_store._executed_actions = set()`).
- Then remove the now-redundant external assignment in `executor.py`.
- Verification: `python -m pytest tests/ -q` green; specifically re-run `test_layer3.py` and `test_stage4_evidence.py` (these exercise `EvidenceStore` directly).

### 2.5 — Make `BaseMemory.process_turn`'s dead default body either real or gone
- File: `dialectic_ai/memory/base.py`
- The `@abstractmethod process_turn` has an unreachable concrete body (see `CODE_REVIEW.md` → Layer 1). Either:
  (a) Remove the body entirely (just `...` or `pass`), since it can never run — simplest, safest option, OR
  (b) If the intent was a genuinely shared default, remove `@abstractmethod` and have concrete subclasses call `super().process_turn(...)` then do their own type-specific work — a real behavior change, only do this if you also update every subclass (`KnowledgeGraphMemory`, `PersistentMemory`, `SQLiteKnowledgeGraphMemory`) to actually call `super()`, and add a test proving the shared logic runs.
- Recommendation: do (a). It is a pure dead-code removal with zero behavior change, versus (b) which is a real design change that should be its own separate, deliberately-reviewed step, not bundled into a cleanup pass.
- Verification: `python -m pytest tests/ -q` green.

### 2.6 — Either implement or clearly relabel `tools/web_search.py`
- File: `dialectic_ai/tools/web_search.py`
- This is a **product decision, not just a code fix** — see `CODE_REVIEW.md` → Layer 2 for why this matters (it directly contradicts the framework's own "confront reality" premise). Two honest options:
  (a) Implement it for real against an actual search API (e.g., DuckDuckGo's HTML endpoint via `urllib`, matching the zero-extra-dependency style of `WebFetchCheck` — no API key needed for basic DuckDuckGo HTML scraping, though this is fragile and may need adjustment if DuckDuckGo changes their markup).
  (b) If a real implementation is out of scope right now, rename it to `mock_web_search` (or add an unmissable `[MOCK]` prefix to its `@dialectical_tool`'s `description`/docstring) so nobody mistakes it for working, and update `examples/advanced_agent.py` (which uses it) accordingly.
- Recommendation for hackathon prep specifically: do (b) now (5 minutes, removes a credibility risk if a judge reads the code), and treat (a) as a stretch goal.
- Verification: if (a), write a small live test confirming it returns real, query-relevant text for a known query. If (b), confirm the renamed/relabeled tool still round-trips correctly through `tests/test_layer1.py` or wherever it's currently exercised (`grep -rn web_search tests/`).

---

## Phase 3 — Unify the two "how dialectical is this agent" tools

**Status: ✅ DONE (2026-09-15)** — 3.1-3.3 done as scoped. Two related dialectics-consistency items not originally numbered in this plan were folded in here since they're the same "does the tooling actually enforce/observe Rule 5 as advertised" theme: (a) `DialecticalTriad`'s Antithesis/Synthesis prompts (`multi/triad.py`) were rewritten to match the rigor `DialecticalDebateEngine` already had — the old Antithesis prompt ("propose a contrarian, critical, or alternative approach") was weaker than what the class's own `@dialectical` decorator already promised ("an opposite process that does not need the Thesis's specific solution to exist"); (b) `cli/main.py`'s `cmd_audit` LLM-selection fallback now tries `GigaChatLLM` first (previously never tried at all — see `CODE_REVIEW.md` Layer 5), ahead of `GeminiLLM`/`OpenAILLM`. See `development_log.md`'s "[2026-09-15] Refactor Phase 3" entry.

**Why:** `CODE_REVIEW.md` → Layer 5, cross-cutting finding #2. `AgentEvaluator` (`dialectic eval`) and `DialecticalAuditor` (`dialectic audit`) both read `trace.jsonl` and both produce a "quality" verdict, but neither is aware of the Rule 5 fields (`opposite_process`/`contradiction`/`leap`/`leap_type`/`dialectical_resolution_missing`/`leap_action_mismatch`) added 2026-09-13/14. This is confusing for a hackathon demo — a judge or teammate should not get two different, non-comparable "score" numbers from the same trace file.

### 3.1 — Add Rule 5 awareness to `AgentEvaluator`
- File: `dialectic_ai/observability/evaluator.py`
- In `evaluate_session()`, add a new violation check: count `synthesize` events that correspond to a `dialectical_resolution_missing` or `leap_action_mismatch` trace event for the same `session_id`/`iteration`, and fold this into `dialectical_score` (a finalized response with a Rule 5 violation should reduce the score, the same way a missing-synthesis or parse-error currently does).
- Add a new field to `EvaluationReport`: `rule5_violations: int`.
- Verification: construct a small trace.jsonl fixture (or reuse one produced by `tests/local_runner.py`, saved to a temp file) containing at least one `dialectical_resolution_missing` event, confirm `evaluate_session()`'s score reflects it and the new field is populated.

### 3.2 — Cross-reference the two tools in their own docstrings
- Files: `dialectic_ai/observability/evaluator.py`, `dialectic_ai/observability/auditor.py`
- Add a one-line note to each `DIALECTICAL DESCRIPTION` block pointing at the other tool and explaining the distinction: `AgentEvaluator`/`dialectic eval` = fast, local, heuristic, no LLM call; `DialecticalAuditor`/`dialectic audit` = slower, LLM-as-judge, deeper (product+process compliance, or root-cause investigation via `investigate_contradiction`). This is documentation-only, but prevents the next person (human or AI) from re-discovering the overlap from scratch.
- Verification: none needed (docstring-only change) beyond making sure nothing else broke.

### 3.3 — Fix `TraceReader.get_knowledge_graph()`'s hardcoded path
- File: `dialectic_ai/observability/tracer.py`
- Currently hardcodes `Path("memory_state.json")`. Change `TraceReader.__init__` to accept an optional `memory_path: str = "memory_state.json"` parameter, and have `get_knowledge_graph()` use `self.memory_path`. This at least makes it *configurable* instead of silently wrong for any non-default memory setup — a full fix (reading the actual live memory object) would require plumbing the memory instance through to the dashboard, which is a bigger change; do the configurable-path fix now, note the deeper fix as a stretch goal.
- Verification: construct a `TraceReader` with a custom `memory_path` pointing at a `SQLiteKnowledgeGraphMemory`-style file (or just a differently-named JSON file) and confirm `get_knowledge_graph()` reads from the right place.

---

## Phase 4 — Make the test suite catch what only manual runs caught this session

**Status: ✅ DONE (2026-09-15)** — 4.1-4.3 done as scoped, including the plan's own "confirm the test can actually fail" requirement: `test_gaia2_adapter.py`'s regression test was verified to fail loudly when the original bug's if/elif order was temporarily reintroduced, then the fix was restored (`git diff` confirmed a clean restore). The canary test was run for real against a live GigaChat credential (not just checked for a clean skip) and passed. See `development_log.md`'s "[2026-09-15] Refactor Phase 4" entry.

**Why this matters most for hackathon credibility:** every high-value bug fixed this session (date-year, type-classification, placeholder-detection, repair-schema-blindness) was found by a human-directed manual run against a real provider on real data — **not** by the existing `pytest` suite, which is 100% `MockLLM`/mocked-HTTP based. See `CODE_REVIEW.md`'s final cross-cutting finding. A test suite that is green while the actual product is broken against real providers is worse than no test suite, because it creates false confidence.

### 4.1 — Add one cheap, opt-in "canary" test against a real provider
- New file: `tests/test_canary_real_provider.py`
- Structure: a single test, skipped by default unless an env var (e.g., `DIALECTIC_RUN_CANARY=1`) is set, that:
  1. Constructs a real `GigaChatLLM()` (or whichever provider has a working credential in the environment running the test).
  2. Runs one trivial `DialecticalEngine` cycle with `tests/mock_tools.py`'s existing mock tools (already built this session, cheap, deterministic tool *behavior* even though the LLM call is real).
  3. Asserts `status == "completed"`, `dialectical_resolution_missing is False`, and that the response text is non-empty.
- This is intentionally the *same* pattern already proven this session in `tests/local_runner.py` — just wrapped as a proper, skippable pytest test rather than a standalone script, so it can be wired into CI as an optional job (see 4.2).
- Verification: run it locally with `DIALECTIC_RUN_CANARY=1 pytest tests/test_canary_real_provider.py -v` and confirm it passes with a real credential configured, and is cleanly skipped (not failed) without one.

### 4.2 — Wire the canary into CI as a separate, non-blocking job
- Files: `.github/workflows/ci.yml` or `.github/workflows/python-app.yml` (see Phase 5 for consolidating these first — do that before this step if possible, to avoid wiring the canary into a workflow you're about to delete)
- Add a job that runs only on a schedule (e.g., daily `cron`) or on manual dispatch, not on every PR (real API calls cost money/quota and should not gate every commit) — set `DIALECTIC_RUN_CANARY=1` and a `GIGACHAT_AUTH_KEY` repository secret.
- This gives early warning if a provider changes behavior (like the `list[str]`-vs-`str` classification bug or a future GigaChat API change) without making every PR dependent on a live external API.
- Verification: manually trigger the workflow once (`workflow_dispatch`) and confirm it runs and reports correctly, both in the pass and (by temporarily breaking something) fail case.

### 4.3 — Add a regression test for the array/int type-classification bug specifically
- File: new test in `benchmarks/gaia2/` test area, or `tests/test_gaia2_adapter.py` if one does not exist yet.
- This bug (`AREToolWrapper.parameters()` checking `"str" in arg_type` before `"list" in arg_type`, silently misclassifying every `list[str]` argument as a plain string) was the single highest-impact fix this session — it broke `recipients`/`attendees`/`cc` on nearly every scenario, silently, for the entire session until caught by manual inspection. Write a direct unit test:
  ```python
  # against a real ARE tool object (e.g. EmailClientApp.send_email), NOT a fixture,
  # so it catches the bug even if ARE's own type-string format changes
  from are.simulation.apps.email_client import EmailClientApp
  from benchmarks.gaia2.adapter import AREToolWrapper
  wrapper = AREToolWrapper(next(t for t in EmailClientApp().get_tools() if "send_email" in t.name))
  assert wrapper.parameters()["properties"]["recipients"]["type"] == "array"
  ```
  This exact assertion would have failed loudly, immediately, the first time this bug was introduced (or re-introduced) — it is the single cheapest test to add, given the size of the bug it catches.
- Verification: confirm it currently passes (the bug is already fixed as of 2026-09-14). Confirm it *would* fail by temporarily reverting the fix (swap the `if/elif` order back) and re-running — this "confirm the test can actually fail" step is not optional; a test that cannot fail proves nothing.

---

## Phase 5 — Tooling and CI consolidation

**Status: ✅ DONE (2026-09-15)** — 5.1, 5.2 done as scoped; 5.3 done as option (a) per this plan's own recommendation (docstring-only, zero-risk; option (b)'s migration remains deliberately deferred). Baseline lint/type debt recorded for future triage: `ruff check .` found 142 findings, `mypy dialectic_ai` found 64 -- both wired into CI as `continue-on-error: true` rather than blocking, exactly as this plan's own 5.1 text anticipated. See `development_log.md`'s "[2026-09-15] Refactor Phase 5" entry.

### 5.1 — Consolidate the two CI workflows into one
- Files: `.github/workflows/ci.yml`, `.github/workflows/python-app.yml`
- They currently do overlapping work with different Python setup actions (`setup-python@v3` vs `v5`) and different dependency install strategies. Pick one canonical workflow (recommend keeping `python-app.yml`'s zero-deps/full-deps split, since it tests a real guarantee the project cares about — see `development_log.md` Stage 16), delete the other, and add:
  - `pip install -e .` as an explicit step (exercises the packaging path added this session — currently untested by CI at all).
  - A `ruff check .` step and a `mypy dialectic_ai` step (configs already exist in `pyproject.toml`, currently unused — see `CODE_REVIEW.md` Layer 6).
- Verification: push to a branch, confirm the single consolidated workflow runs and passes (or fails informatively on real lint/type issues — expect some `ruff`/`mypy` findings on first run, since nothing has ever enforced them; triage those as a follow-up, don't block this consolidation step on fixing every lint finding immediately).

### 5.2 — Fix the two import-time global side effects
- Files: `dialectic_ai/core/dialectical.py` (`sys.excepthook` reassignment at module scope), `dialectic_ai/integrations/gemini/llm.py` (`_load_env_file()` called at module scope)
- For `dialectical.py`: consider moving the `sys.excepthook` reassignment into an explicit opt-in function (e.g., `install_dialectical_excepthook()`) that the CLI (`cli/main.py`) calls explicitly at startup, rather than every importer of the module getting it silently. This preserves the nice traceback formatting for CLI users while not surprising anyone embedding the framework in a larger app.
- For `gemini/llm.py`: move `_load_env_file()`'s call from module scope into `GeminiLLM.__init__` (it's cheap to call once per instantiation, and this matches how every other provider in the codebase loads its own config — none of the others have an import-time side effect).
- Verification: `python -m pytest tests/ -q` green; additionally, write a quick manual check that `import dialectic_ai.core.dialectical` alone (with nothing else imported) no longer changes `sys.excepthook`, and that `import dialectic_ai.integrations.gemini.llm` alone no longer touches `os.environ`.

### 5.3 — Decide the fate of the deprecated `Memory`/`BaseMemory` split
- Files: `dialectic_ai/memory/base.py` and all its subclasses
- This is a bigger, more disruptive change than anything else in this plan — do it last, and only if time remains before the hackathon. Options, in increasing order of disruption:
  (a) Leave as-is, just remove the misleading `DEPRECATED` docstring on `BaseMemory` since nothing has actually migrated off it (false advertising is worse than an honest "this is the real base class").
  (b) Migrate `KnowledgeGraphMemory`, `PersistentMemory`, `SQLiteKnowledgeGraphMemory` to the `Memory` `Protocol` (drop `BaseMemory`/`DialecticalObject` inheritance), matching what `ConversationMemory` already does. This means these classes stop being subject to Rule-1 (`@dialectical` decorator) enforcement, which is a real philosophical change worth a `development_log.md` entry of its own (per this project's own Rule 3/5 — a transition like this needs its own reflection, not a silent drive-by edit).
- Recommendation: do (a) now (one docstring edit, purely honest, zero risk), defer (b) to well after the hackathon unless there's a specific reason to prioritize it.
- Verification: for (a), none needed beyond confirming the docstring change reads correctly. For (b), full test suite plus a manual audit that every consumer of these memory classes (agent construction sites across examples/CLI/tests) still works without the `DialecticalObject` enforcement.

---

## What is explicitly NOT in this plan (and why)

- **GAIA2 "Ambiguity" success rate improvements beyond infrastructure correctness.** This session fixed real infrastructure bugs (wrong simulated year, broken type coercion, unresolved placeholders) that were making the benchmark unwinnable regardless of agent reasoning quality. Getting from "infrastructure correct, 0% success" to "meaningfully positive success rate" on GAIA2's hardest category is a *model reasoning quality* problem, not a framework bug — it is a legitimate, open-ended research direction (better prompting, few-shot examples, a stronger model, or a genuine planning/verification loop), not a fixed-scope refactor item. See `HANDOFF.md` for the full incident history if you want to continue that specific thread.
- **Rewriting the `@dialectical` enforcement mechanism itself, or the Rule 5 procedure.** Both are working as designed and are core to this project's identity for the hackathon pitch — this plan is about *stability and correctness of the implementation*, not about re-litigating the philosophical architecture decisions already made and documented in `dialectics_rules.md`/`development_log.md`.
- **`dialectic_observability/` (the optional FastAPI dashboard package).** Not audited this pass (see `CODE_REVIEW.md`'s explicit note) — it's an optional, separate package by design (Zero-Dependencies principle), lower priority than the core framework for hackathon prep unless the demo plan specifically requires the live dashboard.
