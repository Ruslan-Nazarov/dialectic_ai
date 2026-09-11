# Log of Dialectical Development (Process Memory)

*This document serves as the Memory of the development process itself. According to Rule 4, before each new step, we are required to refer to this log to maintain continuity.*

> **Dual Role of the Document:**  
> DialecticAI is being developed according to the same principles that a developer will later use to create agents with its help. Therefore, `development_log.md` simultaneously serves as:  
> 1. The memory of the framework's development — it records why specific architectural decisions were made.  
> 2. A living example for agent developers: this is how the log should look when creating an agent using DialecticAI.  
> Consequently, every significant step in the framework's development must be recorded here — with the same level of reflection that we require from users.


## [2026-09-01] Step 1: System Prompt (Thesis)
- **What was done:** Formulated the identity of the AI Tutor (`tutor_prompt.md`).
- **Logic:** The tutor does not provide ready-made answers but analyzes the student's mental model and generates guiding questions (Antithesis).

## [2026-09-01] Step 2 and 3: Interaction Mechanism and Action
- **What was done:** Wrote the basic script `tutor_agent.py`.
- **Reality Check:** Realized that regular text output does not allow the code to separate the agent's thoughts from the user's response and extract states.
- **Evaluation and Synthesis:** Made the prompt (Step 1) return strict JSON. The input-output logic began to be dictated by the structure of the prompt.

## [2026-09-02] Step 4: Agent Memory (Knowledge Graph)
- **Reality Check (Time):** If the dialogue lasts many turns, the agent forgets the student's progress. It needs a history.
- **Transition Evaluation (Best Practices):** Instead of simply passing the chat history (memory buffer) or a vector database, we chose the **Knowledge Graph** as the ideal practice for the tutor.
- **Implementation:** Added the `KnowledgeGraphMemory` class, which is updated from the agent's JSON response.

## [2026-09-02] Meta-Solution (Framework Strategy)
- **Context:** Realized that our principles form a unique framework for building agents.
- **Solution (From Specific to Abstract):** First, we fully go through all stages of creating an agent with a specific example (Tutor), perfect it, and then refactor (abstract) this experience into a universal framework.

## [2026-09-03] Step 5: Tools (Tools / External Actions)
- **Reality Check (Agent Blindness):** Realized that the LLM might mistakenly consider the sent code correct. Without actually running the code, the tutor is blind to physical reality and can give false praise.
- **Transition Evaluation (Best Practices):** Applied the industry practice of **ReAct (Reason + Act)**. One user message now generates a hidden micro-cycle for the LLM: Analysis -> Tool Call -> Result (Observation) -> Final Synthesis (Response).
- **Implementation:** Added `tool_calls` to the JSON schema of the prompt. Added `ToolRegistry` to the agent's code and a `while` loop that intercepts tool requests and returns execution errors to the agent.

## [2026-09-03] Layer 0 ✅: Core (dialectical.py, schema.py, llm.py, logger.py)
- **Implemented:** The `@dialectical` decorator (dialectical description of components), a unified data type schema, MockLLM abstraction, DevelopmentLogger.
- **Reality Check:** The test `test_layer0.py` passed. All components are working.

## [2026-09-04] Step 6: Birth of the Framework (Destruction of the Tutor)
- **Dialectical Leap:** The tutor has fulfilled its historical role. From its specific, "hardcoded" example, we derived universal development rules (from Identity to Tools).
- **Action:** We remove the old Tutor code (`tutor_agent.py`, `tutor_prompt.md`). The design of the architecture of the abstract framework, subordinated exclusively to the derived rules, begins. The tutor will be recreated later as the first test instance.

## [2026-09-04] Layer 2 and 3 ✅: Reality + Engine
- **Reality:** The `RealityCheck` contract and `PythonExecutor` (execution in an isolated subprocess with a timeout). The file `dialectics_rules.md` is dynamically loaded into each prompt.
- **Engine:** `DialecticalEngine` with a forced cycle of generate → collide → synthesize. Rule 3 (Collision with Reality) is physically enforced: the agent cannot bypass tool checks. The test `test_layer3.py` was successfully passed.

## [2026-09-05] Layer 4 ✅: Multi-Agent
- **Implemented:** Interaction protocol (`AgentMessage`, `AgentResult`) and smart dispatcher `AgentRouter`.
- **Contradiction:** The user should not manually select an agent, and one agent cannot be an expert in everything.
- **Transition Evaluation (Alternatives):**
  - `LangGraph` — powerful, but requires explicit state graph definition, which violates the dialectical autonomy of agents.
  - `AutoGen` — focused on free dialogue between agents, while we have a strict dispatch architecture.
  - `OpenAI Assistants API` — vendor lock-in, no control over the reasoning cycle.
  - **Own `AgentRouter`** — chosen: a fully controlled dialectical cycle, where routing is a synthesis itself.
- **Reality Check:** The test `test_layer4.py` was successfully passed: requests with code are automatically directed to a specialized code agent, while theoretical questions go to the tutor.

## [2026-09-05] Layer 5 ✅: Observability
- **Implemented:**
  - `TraceReader`: structured reading of events from `trace.jsonl` (generations, thoughts, collisions, synthesis).
  - `AgentEvaluator`: automatic audit of compliance with the dialectical cycle (Grounding Score, Dialectical Completeness, detection of violations).
  - `server.py` + `dashboard.html`: a fully functional web dashboard with a dark theme, timeline of thoughts/collisions, interactive chat, and visualization of the knowledge graph.
- **Transition Evaluation (Alternatives):**
  - `OpenTelemetry` — industry standard, but excessive for simple agent traces and requires complex infrastructure (Jaeger/Prometheus).
  - `Langfuse` / `Phoenix Arize` — excellent specialized solutions, but add external dependencies and require sending data to third-party servers (or complex self-hosting).
  - **Own lightweight Observability dashboard** — chosen: zero dependencies (only FastAPI for WebSockets), complete privacy, interface tailored specifically for the dialectical cycle (Thesis-Antithesis-Synthesis).
- **Reality Check:** The test `test_layer5.py` successfully verifies session extraction, quality assessment, and dashboard distribution.

## [2026-09-06] Layer 5 (Refinement) ✅: Dashboard on FastAPI + WebSockets

- **Reality Check (http.server Limitation):** The standard `http.server` from stdlib works synchronously. This makes it impossible to stream the agent's state to the browser without constant polling from the client — a gross violation of UX and architectural purity.
- **Transition Evaluation (Best Practices):** Considered:
  - `aiohttp` — a full async framework, but excessive for the dashboard, and lacks built-in OpenAPI.
  - `Starlette` — a minimalist foundation for FastAPI; a reasonable alternative, but lacks the conveniences of FastAPI.
  - **FastAPI + Uvicorn** — chosen as the best balance: native WebSockets, built-in documentation, widely adopted in the industry.
  - SSE (Server-Sent Events) without WebSocket — simpler, but only one-way communication (server → client), which limits interactive chat.
- **Solution:** FastAPI with WebSocket endpoint `/ws/stream`. The client receives real-time updates of traces.
- **Moved to an optional package:** `dialectic_observability` — to not violate the Zero-Dependencies principle of the core.

## [2026-09-06] Refactoring ✅: Moving LLM Clients to `integrations/`

- **Reality Check (Core Bloat):** `core/llm.py` had grown: Gemini, OpenAI, FallbackLLM — all in one file. Importing from `core` began to pull in provider logic even where it was not needed.
- **Transition Evaluation:** Considered:
  - Keeping everything in `core/llm.py` — simple, but violates the single responsibility principle.
  - Separate package `providers/` — standard practice in LangChain, but semantically inaccurate.
  - **`integrations/`** — chosen: the name directly signals "these are external integrations, not core."
- **Implementation:** `integrations/gemini/llm.py`, `integrations/openai/llm.py`. In `core/__init__.py`, deprecation aliases were left for backward compatibility.

## [2026-09-07] Refactoring ✅: Transition to asyncio (`async def run()`)

- **Reality Check (Blocking):** `DialecticalEngine.run()` makes HTTP requests to the LLM API. In synchronous mode, this blocks the event loop — it is impossible to run multiple agents in parallel and integrate the engine into async servers (FastAPI).
- **Transition Evaluation (Best Practices):**
  - `trio` — an alternative async library, stricter, but incompatible with the standard asyncio ecosystem.
  - `anyio` — an abstraction over asyncio/trio; excessive without a real need to support both runtimes.
  - Synchronous wrapper `asyncio.run()` from the outside — would maintain compatibility but would hide the nature of operations.
  - **Native `async def`** — chosen: an honest representation of what the engine does IO. Users who need a synchronous interface can wrap it themselves using `asyncio.run()`.
- **Consequences:** `run_tutor.py` and `cli/main.py` were updated for correct invocation via `asyncio.run()`.

## [2026-09-07] Refactoring ✅: Migration of Schemas to Pydantic v2

- **Reality Check (Invalid Data from LLM):** `dataclasses` do not perform runtime type validation. The LLM could return `tool_calls` as a string instead of a list — and the code would fail in an unpredictable place without a clear error message.
- **Transition Evaluation (Best Practices):**
  - `marshmallow` — a mature serialization library, but heavier to use and does not provide IDE hints.
  - `attrs` — more compact than dataclasses, but without built-in type validation.
  - `TypedDict` — without validation, only for annotations.
  - **Pydantic v2** — chosen: the de facto standard for FastAPI, Rust core (performance), strict runtime validation, excellent IDE integration.
- **Compromise:** Pydantic is added as a core dependency (not optional). This is a conscious violation of Zero-Dependencies, justified by the fact that without schema validation, the framework is unreliable.
- **Implementation:** `core/schema.py` rewritten to `BaseModel`. `CollisionResult` marked as `DEPRECATED`, added `Evidence`.

## [2026-09-08] Layer 3 (Refinement) ✅: ClaimValidator — Phase 4 (VALIDATE)

- **Reality Check (Hallucinations in Synthesis):** The agent could refer to a non-existent `evidence_id` or distort a fact during synthesis. `DialecticalEngine` did not check the correctness of claims.
- **Transition Evaluation:**
  - Rule-based hallucination check — can be implemented without LLM, but only covers primitive cases.
  - RAG-based validation — requires a vector database, excessive.
  - **LLM-as-a-judge (Fact-Checker)** — chosen: flexible, scalable, aligns with industry practice of LLM Evaluation.
- **Conscious Contradiction:** The validator itself is an LLM and can also make mistakes. This is recorded in `@dialectical(own_contradictions=...)` of the `ClaimValidator` class.
- **Implementation:** `engine/validator.py`. The engine calls it optionally — only if `claim.requires_validation=True`.

## [2026-09-08] Layer 2 (Expansion) ✅: WebFetchCheck and MCPTool

- **Reality Check (Tool Limitations):** `PythonExecutor` and `HumanRealityCheck` only cover code and human input. Real agents need to work with the web and external services.
- **Transition Evaluation:**
  - Custom HTTP tools — control, but endless support for integrations.
  - **WebFetchCheck** — minimal HTTP GET via `urllib` (Zero-Dependencies), sufficient for basic tasks.
  - **Model Context Protocol (MCP)** from Anthropic — standard for connecting external tool servers. Chosen as a strategic solution: one adapter (`MCPTool`) opens access to thousands of ready-made tools (GitHub, PostgreSQL, Slack).
- **Moved to `integrations/`:** Both integrations are optional and do not bloat the core.

## [2026-09-09] Layer 1 (Expansion) ✅: Additional Memory Types

- **Reality Check (Agent Specificity):** `KnowledgeGraphMemory` is well-suited for educational agents but poorly for exploratory agents (need persistence between sessions) or for dialectical triads (need to store thesis, antithesis, and synthesis as a structure).
- **Transition Evaluation:**
  - One universal memory type — loses semantics.
  - Hierarchy with a base class `BaseMemory` — chosen: flexible, extensible, each type described by its own `@dialectical`.
- **Implementation:**
  - `memory/persistent.py` (`PersistentMemory`) — JSON persistence between sessions.
  - `memory/sublation.py` (`SublationMemory`) — stores the dialectical triad: thesis, antithesis, synthesis.

## [2026-09-09] Layer 6 ✅: CLI and Declarative Agents

- **Reality Check (High Entry Barrier):** To launch an agent, it was necessary to write Python code. This is a barrier for non-technical users and slows down experimentation.
- **Transition Evaluation:**
  - YAML configs (like in Docker Compose) — familiar, but require a YAML parser.
  - Langflow/visual editor — excessive for the current stage.
  - **JSON + CLI** — chosen: Zero-Dependencies (stdlib `json`), close to the OpenAI function calling format, easy to read.
- **Implementation:**
  - `cli/config_parser.py` — loads the agent from a JSON file.
  - `cli/creator.py` — an interactive wizard that asks questions and generates the config.
  - `cli/main.py` — a single entry point: `dialectic map | dashboard | eval | run | create`.

## [2026-09-10] Stage 16 ✅: Tests and CI/CD

- **Reality Check:** After 15+ stages of refactoring, the tests were fragmented and did not check the Zero-Dependencies mode (core without optional packages).
- **Solution:**
  - All tests are structured by layers: `test_layerN.py`.
  - `.github/workflows/python-app.yml` — GitHub Actions with a double run: first only the core, then with optional dependencies.
- **Reality Check:** Run without `fastapi`, `json_repair` — **30 passed, 2 skipped**: the system works in Zero-Dependencies mode.