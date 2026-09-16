# DialecticAI — Architecture & Usage Guide

**Date:** 2026-09-16
**Purpose:** A single, self-contained document explaining what this framework is, why it is built the way it is, and how to actually build an agent with it — written so a new AI session or developer, with zero prior context, can become productive without re-reading the whole codebase. This is the **teaching/reference** document; it complements, not replaces, the other root-level docs:

- **[HANDOFF.md](HANDOFF.md)** — start here first if you're picking up an in-progress session: current state, incident history, exact verification commands, what's mid-flight right now.
- **[CODE_REVIEW.md](CODE_REVIEW.md)** — file-by-file audit (bugs/smells/gaps), tagged and cross-referenced.
- **[REFACTOR_PLAN.md](REFACTOR_PLAN.md)** — the (as of 2026-09-15, fully completed) stability refactor plan; useful as a record of what was deliberately fixed and what was deliberately left alone.
- **[PROMPTS.md](PROMPTS.md)** — every LLM-facing prompt in the codebase, verbatim, with the history of why each part of the wording exists.
- **[dialectics_rules.md](dialectics_rules.md)** — the actual methodology text (Rules 1-5) this whole framework is built to enforce. Read it in full at least once; this document only summarizes it.
- **[development_log.md](development_log.md)** — the chronological, dated record of every architectural decision and bug fix, in the project's own Rule 4 format. When this document says "see development_log.md, <date>", that entry has the full reasoning trail (root cause, live verification, honest caveats) that this document deliberately keeps short.

If you only read one section before writing code, read **"How to build an agent"** below — it is the fastest path to being productive.

---

## 1. What this is, in one paragraph

DialecticAI is a Python framework for building LLM agents whose reasoning process is structured according to a specific philosophical method (Hegelian-style dialectics), and — this is the distinctive part — that structure is **enforced at the code level**, not just suggested in a prompt. A framework class that lacks a `@dialectical(...)` decorator physically refuses to instantiate (raises `DialecticalArchitectureError`). Every agent's own runtime reasoning is required to carry the same five-part structure on every finalized turn (see Rule 5 below), checked against what the agent actually did, not just what it claims. The project's own development process follows the same method on purpose (see `development_log.md`).

## 2. The philosophical foundation (condensed — read `dialectics_rules.md` for the real text)

Five rules, in increasing order of how much they demand:

1. **Generative Principle (Derivation):** each step of development must organically derive from the one before it, inheriting its features and limits — not be bolted on independently.
2. **Confrontation with Reality (Practice and Correction):** every significant step must be checked against a real run, not just reasoned about on paper. When reality reveals a problem, fix it while consciously deciding whether an industry "best practice" actually applies here.
3. **Reflection on the Leap:** when transitioning to a genuinely new architectural step (not routine work), pause and evaluate the *nature* of the transition itself, not just the code.
4. **Development Memory:** keep a continuous, dated log of architectural decisions (`development_log.md`) — every new step should look back at this history before proceeding.
5. **Driving to Contradiction** (the rule with real teeth in this codebase — see `dialectics_rules.md` §5 for the full definition): for significant steps, push development all the way through five named elements — **simplest process** (generative, connected back to itself) → **development** (abstract to concrete, "becoming" not mere succession) → **opposite process** (a process whose own development does *not* need the simplest process to exist — not merely "a different way to do the same thing") → **contradiction** (the two, in the unity of their development) → **leap** (the move that resolves it, either subsuming both or letting them coexist until a later leap resolves them).

**Why this matters for how the code is built:** Rule 5 is not just applied to the *framework's own architecture* (every `@dialectical(...)` class declares its `origin`/`contradiction`/`resolves`/`generates`/`own_contradictions`) — it is also **mandatory for every agent's own reasoning, on every turn**, enforced structurally through required JSON fields (`opposite_process`, `contradiction`, `leap`, `leap_type`) that the engine checks against the agent's *actual behavior* (via `evidence_store`), not just against what it wrote in prose. This was a deliberate architectural decision made mid-project (see `development_log.md`, 2026-09-13) specifically to close the gap between "the agent used the right vocabulary" and "the agent actually reasoned this way."

## 3. Layer architecture

The framework organizes itself into numbered layers (0-6), matching the `layer=N` argument every `@dialectical(...)` decorator declares. `dialectic map` (see §7) prints this map live from the actual running code.

| Layer | Directory | What lives here |
|---|---|---|
| 0 — Foundation | `dialectic_ai/core/` | The `@dialectical` decorator + `DialecticalObject` enforcement, Pydantic schemas, `BaseLLM` + providers, `Tool` base classes, `DevelopmentLogger`, shared retry logic |
| 1 — Agent & Memory | `dialectic_ai/agent/`, `dialectic_ai/memory/` | `DialecticalAgent`, system-prompt assembly, all memory implementations |
| 2 — Confronting Reality | `dialectic_ai/reality/`, `dialectic_ai/tools/`, `dialectic_ai/integrations/` | Tools that actually touch the outside world: code execution, human-in-the-loop, web fetch, MCP, LLM provider integrations |
| 3 — Orchestration Engine | `dialectic_ai/engine/` | `DialecticalEngine` (the turn loop), JSON parsing/repair, evidence store, claim validation |
| 4 — Multi-Agent | `dialectic_ai/multi/` | `AgentRouter`, `DialecticalTriad`, `DialecticalDebateEngine` |
| 5 — Observability | `dialectic_ai/observability/` | `DevelopmentLogger`'s reader (`TraceReader`), `AgentEvaluator` (fast heuristic scoring), `DialecticalAuditor` (LLM-as-judge + root-cause investigation) |
| 6 — Developer Experience | `dialectic_ai/cli/`, `examples/`, packaging | The `dialectic` CLI, the interactive agent-creation wizard, runnable examples |

Outside this numbered scheme: `dialectic_observability/` (an optional FastAPI dashboard, a separate installable extra).

## 4. Core abstractions

### 4a. `@dialectical` decorator and Rule 1 enforcement — `core/dialectical.py`

```python
@dialectical(
    origin="...",            # what gap/void this class fills
    contradiction="...",     # what problem/tension it resolves
    resolves="...",          # how, specifically
    generates="...",         # what it enables next
    own_contradictions="...",# what NEW tension it introduces by existing
    layer=0,                 # 0-6, per the table above
)
class MyComponent(DialecticalObject):
    ...
```
Any subclass of `DialecticalObject` (the base for `Tool`, `BaseLLM`, `DialecticalAgent`, `BaseMemory`, and most other framework classes) that is instantiated **without** this decorator raises `DialecticalArchitectureError` at `__new__` time — not a lint warning, a runtime failure. This is Rule 1 made physically load-bearing. `get_dialectical_map()` collects every decorated class into a registry; `dialectic map` prints it.

### 4b. Data schemas — `core/schema.py` (Pydantic v2)

- `AgentInput(user_message, session_id, metadata)` — what goes in.
- `Hypothesis(assumption, plan_steps)` — the agent's current simplest-process statement and its concrete development.
- `Evidence(id, source, content, tool_name, success, error, ...)` — a structured fact obtained from a tool; the unit the engine's evidence store and claim validator operate on.
- `Claim(text, evidence_ids, requires_validation)` — a statement the agent makes that can be checked against `Evidence`.
- `AgentOutput` — the final result of one `engine.run()` call. Besides the obvious (`status`, `response`, `decision`, `hypothesis`), it carries the Rule 5 fields: `opposite_process`, `contradiction`, `leap`, `leap_type` (one of `"decompose_and_act" | "ask_only" | "fully_resolved" | ""`), plus two engine-computed flags: `dialectical_resolution_missing` (a `response` was given with the Rule 5 fields empty) and `leap_action_mismatch` (the agent claimed `"decompose_and_act"` but `evidence_store` shows no tool was ever actually called — the structural "says vs. does" check).

### 4c. LLM providers — `core/llm.py` + `integrations/*/llm.py`

All inherit `BaseLLM` (`async def generate(messages, tools) -> str` and `generate_result(...) -> ModelResult`).

| Provider | Where | Notes |
|---|---|---|
| `MockLLM` | `core/llm.py` | Canned response queue, for tests/sandbox — no network. |
| `GigaChatLLM` | `integrations/gigachat/llm.py` | Sberbank GigaChat. The most reliable real provider found in this project's own testing (see `HANDOFF.md`). Has OAuth token management and full retry/backoff. |
| `OpenAILLM` | `integrations/openai/llm.py` | Any OpenAI-compatible `/v1/chat/completions` endpoint (OpenAI itself, Groq, OpenRouter, Cerebras, local vLLM/Ollama). Supports native tool calling. |
| `GeminiLLM` | `integrations/gemini/llm.py` | Google Gemini REST API. Free tier is very quota-limited (observed ~20 req/day) — not reliable for repeated runs. |
| `FallbackLLM` | `core/llm.py` | Tries providers in order, falls to the next on any exception. |
| `BalancingLLM` | `core/llm.py` | Round-robins across providers; evicts a provider that fails with a rate-limit/auth error twice in a row for a cooldown window (5 min default). |

Retry/backoff (`core/retry.py`, `RetryableError` + `retry_call` + `compute_backoff`) is shared across all three real providers — a provider's own `_do_attempt` decides what's retryable for it and raises `RetryableError`; the shared loop owns the exponential-backoff-with-jitter sleep.

### 4d. Tools — `core/tool.py`, `core/decorators.py`

- `Tool` (ABC) → `ObservationTool` (read-only, e.g. search) / `ActionTool` (has a side effect, e.g. send email) / `AgentTool` (delegates to another agent). Each tool implements `name`, `description`, `category`, `parameters() -> JSON Schema`, and `async execute(args) -> Evidence`.
- `@dialectical_tool(origin=..., contradiction=..., resolves=...)` (`core/decorators.py`) — turns a plain typed function into a `Tool` subclass automatically (schema inferred from type hints). Calling the decorated name (e.g. `web_search()`) constructs an instance of the generated class — a common point of confusion the first time you see it.
- Built-in tools: `reality.PythonExecutor` (sandboxed code exec — denylist-based, **not** production-grade isolation, says so in its own docstring), `reality.HumanRealityCheck` (ask a human, blocking on `input()` in a thread), `reality.WebFetchCheck` (real HTTP GET of one URL), `reality.SubAgentTool` (delegate to another agent — implemented, never actually exercised by any test/example), `tools.web_search` (**a mock — makes no real network call, clearly labeled `[MOCK]` as of 2026-09-15**, don't mistake it for working search), `tools.read_file`/`write_file` (no path sandboxing — don't expose to untrusted input), `integrations.mcp` (Model Context Protocol tools, optional dependency).

### 4e. Memory — `memory/`

Two coexisting contracts: `Memory` (a `Protocol` — structural typing, no inheritance needed: `process_turn`, `get_context`, `clear`) and `BaseMemory` (an ABC requiring `DialecticalObject`/`@dialectical`). Despite `Memory` being the newer, lighter-weight option, every concrete memory class except `ConversationMemory` still inherits `BaseMemory` — a known, deliberately-deferred inconsistency (see `REFACTOR_PLAN.md` Phase 5.3).

- `KnowledgeGraphMemory` — in-RAM concept→status graph, optional JSON persistence via `storage_path`. Default memory if none is given to `DialecticalAgent`.
- `SQLiteKnowledgeGraphMemory` — same idea, backed by SQLite for atomic, concurrent-safe updates (import directly: `dialectic_ai.memory.sqlite_graph`, not exported from the package `__init__`).
- `PersistentMemory` — wraps another memory and persists it to a JSON file; **only fully round-trips `KnowledgeGraphMemory`** — wrapping anything else saves a string blob that never gets read back correctly (see `CODE_REVIEW.md`, Layer 1).
- `ConversationMemory` — plain conversation buffer, the one class already on the `Memory` Protocol path (import from `dialectic_ai.memory.conversation`).

### 4f. `DialecticalAgent` — `agent/base.py`

The container: `goal` (the only thing you're required to set), `llm`, `memory`, `tools`. `get_system_prompt()` calls `agent/prompt_builder.build_system_prompt(goal, memory, tools, native_tool_calling)`, which assembles, in order: the goal text → `_AGENT_DIALECTICAL_RULES` (the mandatory "how you should think" block, see `PROMPTS.md` §1a for the exact, current text — it's the single most load-bearing prompt in the whole framework) → the JSON response-format contract → the tools section (schema + an explicit "this is shape, not values to copy" clarification added 2026-09-15) → the current memory context. `add_to_history` triggers `SublationEngine` (`memory/sublation.py`) once history exceeds 10 messages: keeps the last 4 verbatim, summarizes the rest via one extra LLM call (Aufheben — sublation, not deletion).

### 4g. `DialecticalEngine` — `engine/executor.py`

The orchestrator. `DialecticalEngine(agent, logger=None, max_iterations=5, validator=None, debug_mode=False)`. `await engine.run(AgentInput(...)) -> AgentOutput` runs a forced cycle per iteration:

1. **`_phase_generate`** — calls the LLM with the full message history, parses the JSON response (`engine/parser.py`; on failure, one controlled repair attempt via `engine/repair.py`'s `JsonRepairer`, which re-prompts with the actual schema embedded — never a second silent retry loop).
2. **`_phase_collide`** — executes every requested `tool_calls` entry **in parallel** (`asyncio.gather` — a later call in the same turn can never see an earlier call's result; this is explicitly taught to the agent in the prompt), records each result as `Evidence` in the run-scoped `EvidenceStore`, caps injected observation text at 6000 characters with a truncation note.
3. **`_phase_synthesize`** — once the agent gives a final `response` (no more tool calls), computes `dialectical_resolution_missing`/`leap_action_mismatch` from the parsed fields vs. `evidence_store`, and packages `AgentOutput`.
4. **`_phase_validate`** — checks any `Claim` marked `requires_validation` against its cited `Evidence` (`engine/validator.py`'s `ClaimValidator`, LLM-as-fact-checker, rate-limited per session).

Two engine-level self-corrections worth knowing about, both bounded to avoid infinite loops:
- **Empty-turn nudge:** if a turn has neither `tool_calls` nor `response`, the engine pushes a corrective message into history instead of silently repeating the same prompt (this was a real, previously-unfixed stall — see `development_log.md`, 2026-09-13).
- **Second-order contradiction loop-back:** if `leap_type == "decompose_and_act"` but `evidence_store` is empty (the agent *claims* it already acted but never called a tool), the engine treats this as a contradiction the agent must resolve, not a fact to log — it pushes the discrepancy back into the generative loop for one bounded retry (`development_log.md`, 2026-09-13/14).

### 4h. Observability — `observability/`

- `DevelopmentLogger` (`core/logger.py`) — writes `trace.jsonl` (structured events per phase) and appends to `development_log.md`-style markdown logs.
- `TraceReader` (`observability/tracer.py`) — reads `trace.jsonl` back into typed `TraceEvent`s; `get_knowledge_graph()` only works for the default `PersistentMemory(KnowledgeGraphMemory())` combination unless you construct it with a matching `memory_path`.
- `AgentEvaluator` (`observability/evaluator.py`, `dialectic eval`) — fast, local, heuristic scoring (no LLM call): collision coverage, synthesis-reached, memory-updated, and (since 2026-09-15) a `rule5_violations` count from `dialectical_resolution_missing`/`leap_action_mismatch` trace events.
- `DialecticalAuditor` (`observability/auditor.py`, `dialectic audit`) — slower, LLM-as-judge: reads the dialectical map + `development_log.md` + a live trace and produces a PRODUCT (architecture) + PROCESS (how it was built) compliance report. `investigate_contradiction()` (`dialectic audit --investigate`) is a **diagnostic-only** tool: given one captured contradiction trace event, it gathers the relevant framework source files and asks an LLM for a root-cause hypothesis — it never modifies code or re-runs the agent itself; a human (or a follow-up session) decides whether and how to act on the hypothesis.

## 5. How to build an agent

### Option A — interactive CLI wizard (fastest way to get something running)
```bash
pip install -e .[dev]
python -m dialectic_ai.cli.main create
```
Walks through: agent name → goal (in your own words — the wizard optionally runs `DialecticalArchitect` to sharpen it into proper Rule-5 form, see `cli/architect.py`) → tool selection (from `TOOL_REGISTRY`, see `cli/config_parser.py`) → LLM choice (Gemini / OpenAI / Mock / Fallback-Auto / **GigaChat**) → output format (a runnable `.py` script, or a declarative `.json` config). If the goal was auto-refined, a companion `<agent>_development_log.md` is written alongside the generated file, in the project's own Rule 5 log format.

### Option B — declarative JSON config
```json
{"name": "MyAgent", "goal": "...", "tools": ["python_executor", "fetch_url"], "llm": "gigachat"}
```
```bash
python -m dialectic_ai.cli.main run my_agent.json
```
Loaded by `cli/config_parser.py`'s `load_agent_from_config` — good for agents with no custom Python logic.

### Option C — manual construction (full control)
```python
import asyncio
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.integrations.gigachat.llm import GigaChatLLM
from dialectic_ai.memory.sqlite_graph import SQLiteKnowledgeGraphMemory
from dialectic_ai.reality import PythonExecutor, WebFetchCheck
from dialectic_ai.core.schema import AgentInput

async def main():
    agent = DialecticalAgent(
        goal="You are a research assistant. Confirm facts by fetching real pages before answering.",
        llm=GigaChatLLM(),                              # picks up GIGACHAT_AUTH_KEY from .env
        memory=SQLiteKnowledgeGraphMemory(db_path="agent_memory.db"),
        tools=[PythonExecutor(timeout=5), WebFetchCheck()],
    )
    engine = DialecticalEngine(agent, max_iterations=10)  # default is 5 -- too low for most real multi-step tasks
    output = await engine.run(AgentInput(user_message="..."))
    print(output.response, output.status)

asyncio.run(main())
```
This is exactly what the wizard's generated boilerplate and every `examples/*.py` script do under the hood. See `tests/local_runner.py` for a complete, cheap (mock-tool) sandbox version you can run without spending real API quota while iterating on engine/prompt changes, and `tests/mock_tools.py` for the pattern of writing a fast deterministic tool for that sandbox.

**Practical notes that will save you real debugging time:**
- `max_iterations` defaults to 5 — fine for a 1-2 tool-call task, too low for anything GAIA2-scale (routinely needs 10-30). Set it explicitly for real tasks.
- `native_tool_calling` is read from `llm.supports_native_tool_calling` automatically — `OpenAILLM` supports it, `GigaChatLLM`/`GeminiLLM` do not (they get the JSON-text tool-calling convention instead). You never set this by hand.
- If you see `DialecticalArchitectureError` on a class you wrote, you forgot the `@dialectical(...)` decorator — this is Rule 1 enforcement, not a bug.

## 6. Multi-agent patterns — `dialectic_ai/multi/`

**Not exported from the package `__init__`** — import directly from the submodule.

- **`AgentRouter`** (`multi/router.py`) — register named agents, add keyword/manual routing rules, dispatches one incoming message to the right one. Deliberately simple (its own `own_contradictions` says so).
- **`DialecticalTriad`** (`multi/triad.py`) — Thesis (generator) + Antithesis (independent critic, run in parallel via `asyncio.gather`, never sees the Thesis draft) + Synthesis (resolves the two into a final answer). Good for code/artifact-quality tasks where edge-case discovery matters. Antithesis's prompt was rewritten 2026-09-15 to match Debate's rigor (see `PROMPTS.md` §5's own history note).
- **`DialecticalDebateEngine`** (`multi/debate.py`) — the fuller Rule 5 procedure across three agents: Thesis names/develops the simplest process, Antithesis independently develops a process that does *not* need the Thesis's approach, Synthesis names the `contradiction` and resolves it with a `leap` — reading these directly off the core schema's structural fields (no regex parsing).

Both cost ~3x the tokens/latency of a single agent — reserve for tasks where that's worth it.

## 7. The `dialectic` CLI — `cli/main.py`

```
dialectic create                 # interactive agent-creation wizard (§5, Option A)
dialectic run <config.json>      # run a declaratively-configured agent (§5, Option B)
dialectic map                    # print the live dialectical map of every @dialectical component
dialectic audit [--config ...] [--investigate [N]]   # PRODUCT+PROCESS compliance report / root-cause investigation
dialectic eval                   # fast heuristic trace scoring
dialectic dashboard [--trace ...]  # launch the optional FastAPI observability dashboard
```
`dialectic audit`'s judge LLM tries GigaChat first, then Gemini, then OpenAI (in that order, since 2026-09-15 — GigaChat is this project's own most reliable credential).

## 8. Current quality state (pointers, not a re-statement)

- Test suite: `python -m pytest tests/ -q` → `77 passed, 2 skipped` as of 2026-09-16. Sandbox: `python tests/local_runner.py` → 3/3 `completed`.
- `REFACTOR_PLAN.md`'s five phases (LLM reliability, cheap bug fixes, dialectics-tooling consistency, real-provider test coverage, CI/tooling consolidation) are **all done** — see that file's own `✅ DONE` markers for exactly what each phase covered.
- Known, deliberately-not-yet-done items: `ruff`/`mypy` findings (142/64 respectively as of 2026-09-15) are visible in CI but non-blocking, not triaged; the `BaseMemory`→`Memory` Protocol migration is deliberately deferred (a real architectural decision, not an oversight — see `REFACTOR_PLAN.md` Phase 5.3).
- If you are about to "clean up" or "simplify" `engine/executor.py`, `engine/repair.py`, or `agent/prompt_builder.py` — **read the relevant `development_log.md` entries for that file first.** Several things in those files look like they shouldn't matter until you see the specific, real failure they were added to prevent.
- **Note on external benchmarking:** this project ran GAIA2, BFCL, and a purpose-built ablation study against the framework during 2026-09-14 through 2026-09-16 (see `development_log.md` entries in that date range for the full, honest findings — including real core-framework bugs those efforts found and fixed, e.g. a `max_iterations` exit path that was silently discarding evidence). The benchmark harness code itself (`benchmarks/`) was deliberately removed afterward to keep this repository to the framework itself; the findings and the fixes they produced remain in `dialectic_ai/` and in `development_log.md`, and the removed harnesses remain recoverable from git history if that investigation is ever resumed.

## 9. If you're an AI session picking this up cold

Read in this order: **this document** (architecture/how-to-build, what you just read) → **`HANDOFF.md`** (current state, exact next step, verification commands) → **`dialectics_rules.md`** (the actual methodology text) → skim the last ~10 entries of **`development_log.md`** (recent decisions and why). Only then start changing code. This project holds its own continuations to the same standard it holds itself: document the why, not just the what, in `development_log.md`, before moving to the next significant step.
