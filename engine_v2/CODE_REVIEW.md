# DialecticAI — Full Code Review

**Date:** 2026-09-15
**Scope:** Every file under `dialectic_ai/`, its integrations, tools, CLI, the GAIA2 benchmark adapter, examples, and CI. Read in full, not sampled.
**Purpose:** A durable, self-contained review meant to survive a handoff to a different AI session/tool. It assumes no memory of any prior conversation — every claim below is either a direct code citation or a live-verified test result, not a paraphrase of something "we discussed."
**Companion documents:** [REFACTOR_PLAN.md](REFACTOR_PLAN.md) (what to do about these findings, in priority order), [PROMPTS.md](PROMPTS.md) (every LLM-facing prompt in the codebase, verbatim), [HANDOFF.md](HANDOFF.md) (start here if you are picking this project up cold).

## How to read this document

Findings are tagged:
- **[BUG]** — confirmed incorrect behavior, verified either by direct code reading (control flow that cannot do what it claims) or by live execution this session.
- **[SMELL]** — works, but is fragile, inconsistent, or likely to bite the next person who touches it.
- **[GAP]** — a documented design goal (in the file's own `DIALECTICAL DESCRIPTION` docstring) that is not actually implemented, or implemented as a stub/mock.
- **[OK]** — reviewed, no issue found, noted so the next reviewer doesn't have to re-check it.

Findings are organized by the same Layer numbers the framework uses internally (`@dialectical(layer=N)`), since that is the project's own mental model.

---

## Layer 0 — Core (`dialectic_ai/core/`)

### `core/dialectical.py`
- **[OK]** The `@dialectical` decorator and `DialecticalObject.__new__` enforcement are correctly implemented and load-bearing — instantiating any subclass of `DialecticalObject` without the decorator raises `DialecticalArchitectureError`. Verified this actually fires (accidentally, on a test helper class) during this session.
- **[OK]** `simplest_process`/`opposite_process` fields (added 2026-09-13) are additive with empty-string defaults — all ~15 pre-existing `@dialectical(...)` call sites remain valid without modification. This is the correct pattern for extending the decorator further; do not remove the defaults.
- **[SMELL]** `sys.excepthook = custom_excepthook` is set at **import time**, globally, as a side effect of importing this module. Any code that imports `dialectic_ai.core.dialectical` (which is nearly everything) silently rewrites the process-wide global exception hook. This is surprising for anyone embedding the framework inside a larger application with its own exception handling — it will silently stop working for `DialecticalArchitectureError` specifically, and the override happens without any way to opt out.

### `core/schema.py`
- **[OK]** Pydantic v2 models, well-structured. The Rule 5 fields on `AgentOutput` (`opposite_process`, `contradiction`, `leap`, `leap_type`, `dialectical_resolution_missing`, `leap_action_mismatch`, added 2026-09-13/14) are correctly wired through from `engine/parser.py` → `engine/executor.py._phase_synthesize` → here.
- **[GAP]** `Hypothesis.assumption` is documented as playing the role of "the simplest process" in the newer Rule 5 prompt language, but the field is still literally named `assumption` and there is no `simplest_process` field on `Hypothesis` itself (the term only exists in prose in `agent/prompt_builder.py` and as a decorator-level field on `@dialectical`, which is a *different* simplest process — the class's own, not the current task's). This double meaning of "simplest process" (one for describing framework classes, one for describing an agent's current reasoning) is never disambiguated anywhere in writing. Low risk, but worth a one-line clarifying comment before it confuses someone doing a `grep`.

### `core/llm.py`
- **[OK]** `BaseLLM`, `MockLLM`, `FallbackLLM`, `BalancingLLM` are all straightforward and correctly implemented.
- **[SMELL]** `BalancingLLM.preflight_health_check()` evicts a provider only on 404/400/"decommissioned"/"not found" substrings in the error text. It does **not** evict on a persistent 429 (rate limit) or 401/403 (bad credentials) — those providers stay in the round-robin rotation forever, meaning every Nth call in a session can waste a full request-timeout cycle hitting a provider that will never succeed for the rest of that run. Live-observed this session: two GAIA2 scenarios failed outright with `RuntimeError('All providers failed in BalancingLLM. Last error: GigaChat API Error 429...')` after the single configured provider got rate-limited — with more than one provider in the pool, a 429'd provider would keep being retried every rotation instead of being backed off.
- **[GAP]** `__getattr__` at module level exists purely to print `DeprecationWarning` and redirect `GeminiLLM`/`OpenAILLM` imports from `dialectic_ai.core.llm` to their new integration modules. This works, but note `dialectic_ai/core/__init__.py` **still imports `GeminiLLM`/`OpenAILLM` directly** into the `dialectic_ai.core` public namespace (see Layer 0 `__init__.py` finding below) — so the deprecated path is simultaneously being kept alive by the package's own `__init__.py`, undermining the deprecation.

### `core/tool.py`
- **[OK]** `Tool`/`ObservationTool`/`ActionTool`/`AgentTool` hierarchy is clean, minimal, and correctly enforced via `DialecticalObject`.

### `core/decorators.py` (`@dialectical_tool`)
- **[OK]** Correctly turns a plain function into a `Tool` subclass with auto-generated JSON schema from type hints.
- **[SMELL]** The decorated name shadows the original function: after `@dialectical_tool(...) \n def web_search(...): ...`, the module-level name `web_search` is rebound to the generated `Tool` **class**, not the original function. Calling it (`web_search()`) instantiates the tool — which is the intended usage (see `examples/advanced_agent.py:28`) — but this is a non-obvious naming collision for anyone reading `tools/web_search.py` cold: it looks like you're calling a plain function, but you're actually instantiating a dynamically generated class of the same name. Worth a comment in `decorators.py` itself, since this is exactly the kind of "hidden magic" the file's own `own_contradictions` field already confesses to.
- **[SMELL]** `parameters()`'s type-inference only recognizes `int`/`bool`/`float`; everything else (including `list[str]`, `Optional[str]`, dataclasses) falls back to `"string"`. There is no container-type support at all here — contrast with the much more careful (if previously buggy, see Layer 2 GAIA2 findings) type mapping in `benchmarks/gaia2/adapter.py`. A `@dialectical_tool`-wrapped function that takes a `list[str]` argument will silently get a broken JSON schema.

### `core/logger.py`
- **[OK]** `DevelopmentLogger.trace_event()` is correctly used throughout the engine, including the new 2026-09-13/14 events (`dialectical_resolution_missing`, `leap_action_mismatch`) with full forensic payloads.
- **[SMELL]** `trace_event()` does one **synchronous, blocking file open+write per call** (wrapped in `asyncio.to_thread`, so it doesn't block the event loop, but it does mean every single trace event is a separate file-open syscall — no buffering, no batching). For a long-running multi-iteration scenario (GAIA2 scenarios routinely hit 20-30 iterations) this is dozens of file opens per task. Not a bug, but the file's own `own_contradictions` field already names this as a known limitation — it has not regressed, just never been addressed.
- **[BUG-ADJACENT]** No log rotation or size cap on `trace.jsonl`. In a long GAIA2 session this file grows unbounded and is never truncated between runs unless the caller deletes it manually (the benchmark runner does not).

### `dialectic_ai/__init__.py`, `core/__init__.py`, and other `__init__.py` files
- **[SMELL]** `dialectic_ai/multi/__init__.py` exports only `AgentMessage`, `AgentResult`, `AgentRouter` — it does **not** export `DialecticalTriad` or `DialecticalDebateEngine`. Both are real, working, tested components (`multi/triad.py`, `multi/debate.py`) that a user of the *public* package interface (`from dialectic_ai.multi import ...`) cannot discover without reading source. `examples/triad/run_triad.py` has to reach past the package interface (`from dialectic_ai.multi.triad import DialecticalTriad`) to use it. This is a real discoverability gap for exactly the two most philosophically important multi-agent patterns in the framework.
- **[SMELL]** No `dialectic_ai/integrations/__init__.py` and no `dialectic_ai/integrations/gigachat/__init__.py` exist. Python 3 namespace packages make this work anyway, but it's inconsistent with `dialectic_ai/integrations/mcp/__init__.py`, which *does* exist and re-exports its contents (`from .tool import MCPTool, load_mcp_tools`). GigaChat — despite being, as of this session, the single most reliable and heavily-used provider in the whole project — has no package-level export at all; every call site does `from dialectic_ai.integrations.gigachat.llm import GigaChatLLM` by reaching into the submodule directly.
- **[BUG]** `dialectic_ai/cli/config_parser.py`'s `TOOL_REGISTRY` and LLM-selection `if/elif` chain (`load_agent_from_config`) has **no GigaChat option at all** — a declarative JSON agent config can only choose `mock`/`gemini`/`openai`/`fallback`. Given GigaChat is the provider this session validated as actually working reliably, any declaratively-configured agent (`dialectic run agent.json`) is structurally unable to use it. Same gap in `dialectic_ai/cli/creator.py`'s interactive wizard (LLM menu offers Gemini/OpenAI/Mock/Fallback-Auto only, not GigaChat) — confirmed by re-reading `creator.py`'s step-4 menu text.

---

## Layer 1 — Agent & Memory (`dialectic_ai/agent/`, `dialectic_ai/memory/`)

### `agent/base.py`
- **[OK]** `DialecticalAgent` is simple and correct. `add_to_history`'s sublation-triggering logic (keep last 4 messages verbatim, summarize the rest) is a deliberate, documented fix for a real prior bug (see its own comment) and works as intended.

### `agent/prompt_builder.py`
- **[OK]** This is the single most load-bearing file in the entire framework — it is the *only* place the "how you should think" instructions and the JSON contract are defined, for every agent, everywhere (see `HANDOFF.md` for why this matters for the current work). As of 2026-09-14/15 it correctly documents: the five-step Rule 5 procedure, the mandatory `opposite_process`/`contradiction`/`leap`/`leap_type` fields, a worked example of correct task decomposition, and the parallel-tool-call-execution warning. All of these were added this session in response to live, reproduced failures — see [PROMPTS.md](PROMPTS.md) for the full current text and [HANDOFF.md](HANDOFF.md) for the incident history behind each addition.
- **[SMELL]** The `native_tool_calling=True` code path strips the `"tool_calls": [...]` block out of `FORMAT_INSTRUCTION` via **line-based string matching** (`if '"tool_calls": [' in line: skip = True ... elif skip and '],' in line: skip = False`). This is correct today only because the JSON template happens to be formatted in a way where no other array closes with `],` between those two markers. Any future edit to `FORMAT_INSTRUCTION` that adds another array field between `tool_calls` and its own closing bracket, or reformats the block across more lines, will silently corrupt the emitted prompt with no error raised. This should be a structured template (e.g., building the dict and conditionally omitting a key, then `json.dumps`-ing it) rather than string surgery on a hand-formatted code fence.
- **[GAP]** Rule 0 ("Reformulate as a process") and the parallel-execution warning are the only two "cheap, universal" prompt additions from this session — they cost zero extra LLM calls but were **never empirically A/B tested** against the previous phrasing the way the Yoga worked-example fix was (which had a documented before/after live comparison — see `development_log.md`, 2026-09-13). There is no evidence either way whether they help, hurt, or are simply ignored by any given model. Worth flagging so nobody mistakes "we wrote it in the prompt" for "we verified it changes behavior," which is a distinction this project's own `dialectics_rules.md` Rule 2 explicitly demands.

### `memory/base.py`
- **[SMELL]** Two competing memory contracts coexist: a `Protocol`-based `Memory` (structural typing, no inheritance required) and an ABC-based `BaseMemory` (nominal typing, requires inheriting `DialecticalObject`, and is explicitly marked `DEPRECATED` in its own docstring) — yet **every single concrete memory implementation in the codebase** (`KnowledgeGraphMemory`, `PersistentMemory`, `SQLiteKnowledgeGraphMemory`) still inherits from the "deprecated" `BaseMemory`, not the newer `Protocol`. The deprecation was declared but never acted on anywhere.
- **[BUG]** `BaseMemory.process_turn` is `@abstractmethod` **but has a concrete method body** (lines 49-59) that is dead code — an abstract method's body is never called through normal dispatch (subclasses override it), and indeed every concrete subclass overrides it with its own logic that does not call `super().process_turn(...)`. This body is unreachable and was almost certainly meant to be the *default* shared implementation, but the `@abstractmethod` decorator prevents it from ever running.

### `memory/knowledge_graph.py`
- **[OK]** Correct and simple. `get_context()`'s emoji-per-status rendering is a nice touch for LLM readability.

### `memory/sqlite_graph.py`
- **[BUG]** `SQLiteKnowledgeGraphMemory` defines `process_turn` **twice** (lines 52-61 and again at lines 76-87). Python silently keeps only the second definition; the first is dead code. This is accidental duplication (almost certainly a merge/edit artifact), not a deliberate override pattern — the two bodies are nearly identical except the second one adds a `details` field and an `if updates:` guard before calling `self.update(...)`. Low real-world impact (behavior is still correct, just via the second definition), but it is exactly the kind of "grep finds two definitions, which one is live?" trap that wastes a future debugging session.
- **[SMELL]** `_init_db()`/`update()`/`get_context()`/`clear()` all open a **new `sqlite3.connect()` per call** rather than holding one connection (or a pool) for the object's lifetime. For a single-agent session this is harmless; under the "swarm of agents… simultaneously read and write" scenario this class's own docstring advertises as its purpose, per-call connections plus SQLite's default locking behavior is a plausible contention point that has never been load-tested.

### `memory/persistent.py`
- **[SMELL]** `PersistentMemory.get_context()` delegates to `self.inner.get_context()`, but `_save()` special-cases `isinstance(self.inner, KnowledgeGraphMemory)` and falls back to `{"context": self.inner.get_context()}` (a plain string dump, not restorable structured data) for any other wrapped memory type. In practice this means `PersistentMemory` only *actually* persists and restores `KnowledgeGraphMemory` correctly — wrapping `ConversationMemory` or `SQLiteKnowledgeGraphMemory` in it will save a string blob on every turn that `_load()` never reads back (`_load()` also only handles the `KnowledgeGraphMemory` case). This is a decorator that only decorates one specific type despite its own docstring claiming "wraps any memory."

### `memory/conversation.py`
- **[OK]** Simple, correct, does not inherit `BaseMemory`/`DialecticalObject` at all (uses the `Protocol` instead) — this is actually the one file in the whole codebase that follows the "newer, non-deprecated" `Memory` contract from `memory/base.py`. Worth noting as the actual reference implementation for anyone migrating the other memory classes off the deprecated `BaseMemory`.

### `memory/sublation.py`
- **[OK]** Already reviewed and annotated with Rule 5 fields this session. No new issues found on re-read.

---

## Layer 2 — Confronting Reality (`dialectic_ai/reality/`, `dialectic_ai/tools/`, `dialectic_ai/integrations/`)

### `reality/python_executor.py`
- **[OK, with an explicit, self-documented caveat]** The sandboxing (`_check_ast` blocking `os`/`subprocess`/`socket`/`ctypes` imports and `eval`/`exec`/`open` calls, plus `resource.setrlimit` for CPU/memory) is a real, if incomplete, defense — its own docstring is honest that this is "a developer sandbox, not production-level isolation." Confirmed the AST check is a denylist (not an allowlist), which means it is bypassable in principle (e.g., `__import__('os')` as a string-built call, or any Python sandbox-escape technique not on the specific denylist) — this is disclosed, not hidden, but worth restating plainly: **do not point this tool at untrusted input in anything resembling a production or multi-tenant deployment.**

### `reality/human.py`
- **[OK]** `HumanRealityCheck` is correctly implemented; `input()` is wrapped in `asyncio.to_thread`, so it does not block the event loop (only the specific coroutine awaiting it).

### `reality/delegation.py`
- **[OK]** `SubAgentTool` is a clean, correct implementation of the "agent as tool" pattern. Not currently used by any test or example — it is the one Layer-2/4 component in the codebase with zero live usage anywhere, so its actual behavior under real multi-agent delegation has never been exercised beyond unit-level type-checking.

### `integrations/web/tool.py` (`WebFetchCheck`)
- **[OK]** Correctly implemented, does a real HTTP GET, truncates at 5000 chars.

### `tools/web_search.py`
- **[GAP — significant]** This is the framework's **default, most-advertised "confront reality via the internet" tool**, and its `execute()` body is:
  ```python
  return f"Search results for '{query}': Found {max_results} articles. (Mock implementation)"
  ```
  It never makes a network call. It is a hardcoded string template. Its own `@dialectical_tool` decorator claims `resolves="Gives the agent direct access to up-to-date information on the internet"` — which is false as written; the only tool that does this is `WebFetchCheck` (GET a specific URL, no search). Any agent that uses `web_search` for anything beyond a smoke test is being fed fabricated, static text that looks like a real tool result. This directly contradicts the framework's own foundational claim (Rule 3, "Collision with Reality") and should be either (a) implemented against a real search API, or (b) renamed/labeled unambiguously as a mock/placeholder so it cannot be mistaken for a working tool by a new user copying `examples/advanced_agent.py`.

### `tools/file_editor.py`
- **[OK]** `read_file`/`write_file` are correctly implemented, with a caveat: **no path sandboxing whatsoever** — `write_file` will happily write to any path the LLM asks for (`os.makedirs(os.path.dirname(path) or ".", exist_ok=True)` followed by an open-write, no allowlist/root-jail). Combined with `PythonExecutor`'s similar "developer sandbox only" caveat, this is consistent with the project's stated non-production posture, but both should be flagged together in any onboarding material as "do not expose these two tools to an agent processing untrusted instructions."

### `integrations/gemini/llm.py`, `integrations/openai/llm.py`, `integrations/gigachat/llm.py`
- **[OK]** All three reviewed. `OpenAILLM` has the most mature retry/backoff logic (added this session: exponential backoff + jitter, retries on 429/5xx/network errors, `max_retries` configurable). `GeminiLLM` has an older, simpler bounded-retry loop (5 attempts, linear backoff) that still works but does not share code with `OpenAILLM`'s newer retry helper — there are now **two different retry implementations** for two different providers, which is worth unifying (see REFACTOR_PLAN.md).
- **[SMELL]** `GigaChatLLM` has **no retry logic at all** — a single failed request (429, 5xx, network blip) raises immediately. Given GigaChat is, as of this session, the primary working provider for real benchmark runs, and given a live 429 actually killed two GAIA2 scenarios outright this session (`RuntimeError('All providers failed in BalancingLLM...GigaChat API Error 429')`), this is the highest-value remaining reliability gap in the LLM integration layer.
- **[OK]** `GigaChatLLM._load_env_file()`-style pattern is not present here (that pattern is in `gemini/llm.py` only) — worth noting `GeminiLLM` module-level `_load_env_file()` runs **at import time**, unconditionally, as a side effect of merely importing the module (not of instantiating the class). This is the same "surprising global side effect on import" pattern flagged for `core/dialectical.py`'s exception hook above — two independent instances of the same anti-pattern in this codebase.

### `integrations/mcp/tool.py`
- **[OK]** Correctly implemented, optional dependency handled gracefully (`MCP_AVAILABLE` flag).

---

## Layer 3 — Orchestration Engine (`dialectic_ai/engine/`)

### `engine/executor.py`
This file received the most changes this session and is now, line-for-line, the most heavily fortified file in the codebase. Current state:
- **[OK]** The empty-turn nudge (2026-09-13), the `leap_action_mismatch` second-order-contradiction loop-back (2026-09-14), the enriched forensic trace events, and the observation-length cap (currently 6000 chars, tuned twice this session — see `development_log.md` for the exact history of 3000→6000) are all live-verified working via both `MockLLM`-based unit tests and real GigaChat runs.
- **[SMELL]** `evidence_store._executed_actions = set()` (in `run()`) sets a private attribute on `EvidenceStore` **from outside the class**, immediately after construction — `EvidenceStore.__init__` (in `engine/evidence_store.py`) does not define this attribute at all. It works (Python allows arbitrary attribute assignment), but it means `EvidenceStore`'s own file is not a complete picture of its own state; anyone reading `evidence_store.py` in isolation will not know `_executed_actions` exists. This should be moved into `EvidenceStore.__init__` itself.
- **[SMELL]** `import json` appears **three separate times** inside `_phase_collide` (once at the top of the loop, twice more inline before `json.dumps` calls) despite `json` already being imported once at the top of the file. Harmless (Python caches imports), but a sign of copy-paste-under-time-pressure that a linter would catch immediately — there is no linter wired into CI yet (see Layer 6 findings).
- **[GAP]** The `leap_action_mismatch` loop-back is bounded to exactly one retry (`leap_mismatch_retries < 1`). This number was chosen by reasoning-by-analogy to the existing idle-loop counter, not derived from any measurement of how many retries are typically needed for a model to self-correct. It has not been tuned.
- **[BUG-ADJACENT]** `max_iterations` default is `5` on `DialecticalEngine.__init__`, but the GAIA2 adapter overrides it to `30` (`DialecticAREAgent.max_iterations = 30`). Every other consumer (examples, `tests/local_runner.py`, the CLI wizard's generated boilerplate) uses the framework default of 5. For any task requiring the kind of multi-step tool sequencing this session's GAIA2 scenarios needed (routinely 3-10+ iterations), the *default* ships too low to be useful out of the box, and a first-time user following `examples/advanced_agent.py` verbatim would likely hit `max_iterations` on anything non-trivial without knowing why.

### `engine/parser.py`
- **[OK]** The multi-strategy JSON extraction (`direct → markdown fence → first-`{...}`-match → json_repair`) is sound and its own docstring is honest about the tradeoff ("the smarter the parser, the more it hides discipline violations instead of forcing the format").
- **[OK]** `LeapType` (added 2026-09-14) as a `Literal[...]` with an empty-string escape hatch is the correct pattern — verified this session that an out-of-enum value correctly triggers a `ValidationError` → `ParseError` → repair cycle rather than silently coercing to something wrong.

### `engine/repair.py`
- **[OK]** Now embeds the actual `FORMAT_INSTRUCTION` schema in the repair prompt (fixed 2026-09-13, previously the single highest-impact bug found this whole engagement — a repair that "succeeded" while silently producing a schema-empty `{}`). The additional "schema-empty repair is itself a failure" check (`has_content` guard) is a good defense-in-depth addition.
- **[SMELL]** The repair prompt embeds the **entire original `raw_response`** verbatim, with no length cap. If the original malformed response was itself extremely long (e.g., a multi-paragraph analysis that ran off the rails before failing to close its JSON), the repair prompt inherits that entire length, compounding whatever budget pressure caused the original failure. This was very likely a contributing factor in at least one of the `ControlledRepairError` crashes observed this session (the raw text shown in logs before the crash was itself already quite long prose). Worth capping, mirroring the `_phase_collide` observation cap.

### `engine/evidence_store.py`, `engine/validator.py`
- **[OK]** Both small, correct, no issues found. `ClaimValidator`'s `max_calls_per_session` billing guard is a good, easily-missed detail worth preserving in any refactor.

---

## Layer 4 — Multi-Agent (`dialectic_ai/multi/`)

### `multi/protocol.py`, `multi/router.py`
- **[OK]** Both simple and correct. `AgentRouter`'s keyword/manual routing is intentionally primitive (its own `own_contradictions` field says so) — no issue, just not sophisticated.

### `multi/triad.py`
- **[OK]** `DialecticalTriad.run()` is correctly `async`, uses real `asyncio.gather` + `asyncio.wait_for` timeouts for the parallel Thesis/Antithesis phase. Verified working live this session (REST vs GraphQL example).
- **[BUG — in the example, not the framework]** See `examples/triad/run_triad.py` below; the framework code itself is correct, but its only shipped usage example is broken.

### `multi/debate.py`
- **[OK]** Rewritten this session from a non-functional hardcoded stub into a real implementation that reuses `DialecticalEngine` per role and reads structural `opposite_process`/`contradiction`/`leap` fields directly off `AgentOutput` (no more regex-parsing a "LEAP: subsumption|coexistence" text convention). Live-verified working.

---

## Layer 5 — Observability (`dialectic_ai/observability/`)

### `observability/tracer.py`
- **[OK]** `TraceReader` correctly parses `trace.jsonl`.
- **[SMELL]** `get_knowledge_graph()` reads from a hardcoded path `Path("memory_state.json")` in the current working directory — it does not take the actual memory instance or its configured path as a parameter, so it will silently return `{}` for any agent whose memory was configured with a different `storage_path`/`db_path` (e.g., every `SQLiteKnowledgeGraphMemory`-backed agent, which never writes a `memory_state.json` at all). The dashboard's knowledge-graph visualization is effectively broken for any agent not using the default `PersistentMemory(KnowledgeGraphMemory())` combination with the default filename.
- **[SMELL]** `get_all()` re-reads and re-parses the **entire trace file on every call**, with no caching. `get_by_session()` calls `get_all()` internally. For the dashboard (which presumably polls), this means a full file re-read+re-parse per request — its own docstring already names this as a known limitation.

### `observability/evaluator.py`
- **[OK]** `AgentEvaluator`'s scoring heuristics are reasonable and clearly documented as heuristics (not claimed to be more rigorous than they are).
- **[GAP]** `EvaluationReport`/`AgentEvaluator` predates the Rule 5 fields entirely (`opposite_process`/`contradiction`/`leap`/`leap_type`/`dialectical_resolution_missing`) added this session — it has **no awareness of them at all**. `dialectic eval` and `DialecticalAuditor.investigate_contradiction()` are now two separate, non-overlapping quality-assessment tools that look at different slices of the same trace file and would give a user two different, uncorrelated "how well is my agent doing dialectically" answers if run side by side. Worth unifying, or at minimum cross-referencing in their docstrings.

### `observability/auditor.py`
- **[OK]** `DialecticalAuditor` (including this session's `investigate_contradiction()` addition) is correctly implemented and live-verified against a real captured contradiction trace, producing a genuinely useful root-cause hypothesis.
- **[SMELL]** `_PROVIDER_FILE_MAP` (added 2026-09-14, inside `investigate_contradiction`'s support code) is a hardcoded dict mapping provider class names to file paths. It will silently produce an incomplete investigation (missing the provider's own source file) for any provider not in the map — currently this means any *future* integration added to `dialectic_ai/integrations/` needs a matching manual update here, with no test or lint enforcing that the two stay in sync.
- **[SMELL]** `cmd_audit` in `cli/main.py` tries `GeminiLLM()` then falls back to `OpenAILLM()` for the audit's own judge model — it never tries `GigaChatLLM`, even though `.env` in this project has a working `GIGACHAT_AUTH_KEY` and Gemini's free tier was observed this session to return `503 UNAVAILABLE` under load. Running `dialectic audit` with no explicit LLM argument is likely to fail or silently degrade to context-only mode on this project's own configured credentials.

---

## Layer 6 — Developer Experience (`dialectic_ai/cli/`, `examples/`, packaging, CI)

### `cli/main.py`, `cli/creator.py`, `cli/architect.py`, `cli/config_parser.py`
- **[OK]** All four reviewed and (for `creator.py`/`architect.py`) live-verified this session, including the `DialecticalArchitect` goal-refinement pass and its graceful-decline path.
- **[BUG]** (Restated from Layer 0 for completeness) Neither `creator.py`'s wizard nor `config_parser.py`'s `TOOL_REGISTRY`/LLM selector offers GigaChat.

### `examples/advanced_agent.py`
- **[OK, with a caveat]** Runs correctly as written (`web_search()` correctly instantiates the decorator-generated class — see `core/decorators.py` finding above for why this is non-obvious). Uses `OpenAILLM()` with no explicit key, relying on the `.env` fallback chain inside `OpenAILLM.__init__` (Groq/OpenRouter) — will silently do nothing useful if none of `OPENAI_API_KEY`/`GROQ_API_KEY`/`OPENROUTER_API_KEY` are set, since `OpenAILLM` does not validate key presence at construction time, only at the first failed HTTP call.

### `examples/triad/run_triad.py`
- **[FIXED 2026-09-15]** `main()` was a **synchronous** function (`def main():`, not `async def`), and called `triad.run(task)` **without `await`**, then immediately accessed `result.response`. `DialecticalTriad.run` is declared `async def run(self, task: str, session_id: str = "default") -> AgentResult` (see `multi/triad.py`). Calling an `async def` without `await` returns a coroutine object, not an `AgentResult`; `result.response` on a coroutine object raised `AttributeError: 'coroutine' object has no attribute 'response'`. Fixed by making `main()` async, `await`ing `triad.run(...)`, and wrapping the `if __name__` block in `asyncio.run(main())`. Not re-verified against a live Gemini call (would cost real API quota for a fix whose correctness is unambiguous from the bug's own nature), but confirmed via `py_compile` and the mechanical nature of the fix.

### `examples/researcher/run_researcher.py`
- **[FIXED 2026-09-15]** Same bug as `run_triad.py`, independently: synchronous `main()` called `engine.run(...)` without `await`. Fixed the same way, and additionally **verified end-to-end** (unlike the Triad fix) via its own `MockLLM` fallback path — runs to completion with a real, correct response and no crash. Also updated its `MockLLM` canned response to include `opposite_process`/`contradiction`/`leap`/`leap_type` (it predated those fields and was tripping a `dialectical_resolution_missing` Rule 5 warning on every clean run — cosmetic, not a crash, but confusing for anyone using this example to learn the framework).

### `examples/tutor/run_tutor.py`
- **[OK, but had a real Windows-encoding crash — FIXED 2026-09-15]** Its use of `DialecticalEngine`/`KnowledgeGraphMemory`/`DevelopmentLogger` all matched current signatures correctly — no async or API-drift bug. However, running it directly crashed with `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f393'` on this project's own Windows/Russian-locale dev environment (default console codepage `cp1251`, not UTF-8) — the same class of bug already fixed once in `tests/local_runner.py` (2026-09-13) but never generalized. Fixed by adding the same UTF-8-reconfigure guard at the top of the script. Verified end-to-end via piped stdin against the `MockLLM` path: completes a full Socratic-tutor turn (tool call, knowledge-graph update, guiding question) with no crash. Also updated its second `MockLLM` canned response to include the Rule 5 fields, same reasoning as `run_researcher.py` above.
- **Same crash class also fixed in `dialectic_ai/cli/main.py`'s `main()`** — the actual CLI entry point (`dialectic ...` / `python -m dialectic_ai.cli.main`) prints emoji via `cli/creator.py`'s wizard and `core/dialectical.py`'s architectural-error banner; both were equally crash-prone on this same machine before this fix. Verified live: `python -m dialectic_ai.cli.main map` now renders its emoji-heavy dialectical map cleanly (previously would have crashed the same way).

### `langchain_example/agent.py`, `dialectic_observability/*`
- **[AUDITED 2026-09-15, OK]** `langchain_example/agent.py` doesn't touch `dialectic_ai`'s async engine at all — it's a standalone LangChain comparison script using LangChain's own synchronous `AgentExecutor.invoke()` correctly. Not re-verified against a live LangChain/OpenRouter call (would need the optional `langchain`/`langchain-openai` deps and a real key), but structurally correct and not the class of bug being hunted here (stale internal async API usage). `dialectic_observability/server.py` was smoke-tested with FastAPI's `TestClient`: `/dashboard`, `/api/trace`, and `/api/graph` all return `200` with valid content against a real (large, 8000+ event) local `trace.jsonl` — the dashboard backend works as documented.
- **[NEW, unrelated to the above]** `test_app.py` (repo root, not under `examples/` or `tests/`) is untouched since the very first commit and duplicates `examples/advanced_agent.py`'s purpose with none of its since-added fixes or polish — likely dead scratch code from before the `examples/` directory existed. Not fixed here (out of scope for this audit pass); flagged as a candidate for deletion or consolidation into `examples/`.

### `pyproject.toml`, CI (`.github/workflows/`)
- **[SMELL]** Two CI workflow files exist (`ci.yml` and `python-app.yml`) doing overlapping jobs (both install deps and run `pytest`; `python-app.yml` additionally splits into a "zero-dependencies" and "full-dependencies" pass, which `ci.yml` does not). This is redundant CI spend and, more importantly, means the "does the core work with zero optional dependencies" guarantee the project's own `development_log.md` proudly documents (Stage 16, 2026-09-10) is only actually checked by *one* of the two workflow files — a change to `ci.yml` alone could silently stop testing that guarantee while still showing a green check from `python-app.yml`... or vice versa, depending on which one a branch-protection rule actually requires.
- **[GAP]** `pyproject.toml` (added this session) defines `[tool.ruff]` and `[tool.mypy]` configuration sections, but **neither tool is invoked anywhere in CI**. The configuration is currently inert — it documents an intention, not an enforced standard. This is explicitly flagged in this project's own prior review conversation as a "next step, not done yet"; it is still not done as of this document.
- **[SMELL]** Neither CI workflow does `pip install -e .` — they `pip install pytest pytest-asyncio pydantic requests` (or similar) directly and rely on implicit path resolution. `pyproject.toml` exists and works (verified `pip install -e .` succeeds and `import dialectic_ai; dialectic_ai.__version__` resolves this session) but CI does not exercise the packaging path at all, meaning a packaging regression (e.g., a missing package in `[tool.setuptools.packages.find]`) would not be caught by CI even though the tooling to catch it now exists.

---

## Cross-cutting findings (not specific to one file)

1. **Two independent retry/backoff implementations** (`OpenAILLM`'s new exponential-backoff-with-jitter, `GeminiLLM`'s older bounded-linear-backoff) and **one provider with none** (`GigaChatLLM`). See REFACTOR_PLAN.md Phase 1.
2. **Two independent "how good is this agent, dialectically" tools** (`AgentEvaluator` / `dialectic eval`, and `DialecticalAuditor` / `dialectic audit`) that do not share a model of the Rule 5 fields added this session. See REFACTOR_PLAN.md Phase 3.
3. **Import-time global side effects** appear twice, independently (`core/dialectical.py`'s `sys.excepthook` reassignment; `integrations/gemini/llm.py`'s `_load_env_file()`), suggesting this is a pattern worth a project-wide grep-and-fix rather than two isolated one-off issues.
4. **No provider in the codebase is exercised by CI against a real API** — all automated tests use `MockLLM` or mocked HTTP. Every finding in this session that mattered (the date-year bug, the type-classification bug, the placeholder-detection gap, the repair-schema-blindness bug) was found by manually running against a *real* provider (GigaChat) against *real* data (a live HuggingFace-hosted GAIA2 scenario), not by the existing test suite. This is the single biggest process gap behind why these bugs existed for as long as they did — see HANDOFF.md and REFACTOR_PLAN.md Phase 4 for a concrete proposal (a small, cheap, real-API "canary" test).
