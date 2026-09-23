# Runtime V2: world first, practice second

This contract records the owner's clarification on 2026-09-19. It supersedes the
interpretation that the dialectical chain is optional for routine requests, or a
checklist to complete immediately before returning an answer.

Every task starts with constructing its world-roadmap **in thought**:

1. Derive a simplest generative process from the task and assess it.
2. Develop it from abstract to concrete, recording the derivation.
3. Identify an opposite process whose development does not require the simplest
   process to exist. A negation, error, or competing technique is not enough.
4. Develop the opposite process as well.
5. Establish the contradiction as the unity of both developments.
6. Propose a leap from that unity: replacement or mediation.
7. Accept the complete roadmap with `BEGIN_EXECUTION`, including its execution route.

No domain tool, including an observation-only tool, runs before step 7. Existing
knowledge may inform planning; actual measurements belong to execution. This is not
a thesis/antithesis/synthesis debate. Planning is a graph, not a fixed number of turns:
branching development and multiple contradictions remain possible.

## Practice

`PROPOSE_ACTION` must reference a Process on the accepted execution route. Tool
names and arguments are validated before execution. Each actual result becomes an
Observation, separately from the model's `ASSESS_PRACTICE` interpretation.

The next action cannot bypass assessment. A `contradicted` assessment forces
`REVISE_WORLD`. This records the triggering observations, returns to planning, and
requires a changed roadmap before further actions. Previous roadmaps retain deep
snapshots; actions retain their roadmap IDs. Other assessments can also motivate revision.

`PROPOSE_LEAP` records an envisaged resolution and never marks a contradiction resolved.
`ASSESS_LEAP` separately judges realization, grounded in successful assessed observations
from the current execution. A mediation can permit task completion without claiming
that its conceptual contradiction has disappeared.

`COMPLETE` requires nonempty output, committed references, assessed observations,
and practice-grounded assessments of all selected leaps. Failed observations cannot
support success. An exhausted budget returns an error with the graph preserved,
never an automatically approved candidate or fabricated replacement.

## Enforcement boundary

- Runtime checks types, references, goal ownership, phase, provenance, evidence links,
  roadmap membership and completion prerequisites.
- The semantic judge sees the proposal, role, goal, graph, observations and assessments.
  Real providers use `LLMSemanticValidator` by default, failing closed on invalid verdicts.
  Developers can inject a validator through the trusted Python API.
- `MockLLM` is explicitly labelled **simulation**, with a deterministic validator.
  It demonstrates the protocol and does not solve the task.

The semantic judge is fallible, especially with the same model as proposer. Enforcing
the graph does not prove philosophical correctness, truth, or superiority over another
framework. These need separate adversarial and comparative evaluation. Tool failures
are not automatically classified as dialectical opposites.

## Lifecycle and limits

Each `run()` starts a fresh graph and run ID. Concurrent calls to one engine are
rejected. Use separate engines for independent runs. Conversational memory is not
implemented; repeated CLI messages are independent tasks.

Defaults: 30 iterations, 5 consecutive rejected proposals, 90 seconds per model/judge
await, 30 seconds per tool await, 300 seconds per run. Cancelling a thread-backed call
cannot undo side effects or guarantee that its thread stopped. Do not automatically
repeat actions after timeouts.

`RuntimeResult` exposes status, stop reason, run ID, roadmap ID and validation mode.
API and dashboard share RuntimeReadModel. `trace.jsonl` records committed/rejected
proposals, accepted roadmap snapshots, observations and exits. `dialectic eval`
checks structural traces, not task quality. Live runs are in memory; traces persist,
but automatic resume/replay is not implemented.

## Operational constraints

- Named providers never silently become Mock. Groq/Cerebras/OpenRouter use their own keys.
- GigaChat verifies TLS. Set `GIGACHAT_CA_BUNDLE` to a trusted PEM bundle if needed.
- Set `GEMINI_MODEL` explicitly to a model available to your account.
- `web_search` is a fixture; real API runs use `fetch_url` for supplied URLs.
- File tools stay under `DIALECTIC_WORKSPACE` (default `agent_workspace`). PythonExecutor
  is a trusted-local-code tool, not a security sandbox. Do not expose it to untrusted users.
- The API is a local developer service, not an authenticated multi-user product.
- Provider availability in UI means configuration exists, not a successful health check.
- Token dashboard estimates are labelled estimates, not billing measurements.
