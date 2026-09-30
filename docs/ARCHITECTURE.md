# Current architecture

Scope: the six-prompt implementation introduced by `f905f30`, with audit repairs on 2026-09-30. The old [architectural specification](history/ENGINE_V3_ARCHITECTURE_PRE_REWRITE.md) describes the replaced bundle implementation.

## Builder

| Prompt | Function in `builder/blocks.py` | Code-controlled action |
|---|---|---|
| 1 | `find_p0` | Propose a simplest process; reject unsuitable candidates |
| 2 | `build_iteration` | Generate 1–6 developing statements in one call, checking declared cumulative basis |
| 3 | `compare_development` | Read accumulated iterations and propose existing process references |
| 4 | `check_opposition` | Check candidates; validate agreement between statuses and confirmed references |
| 5 | `form_contradiction` | Form a contradiction after an opposite is confirmed |
| 6 | `resolve_leap` | Return replacement, mediation, or no leap |

The default limits are three P0 attempts, three iterations per attempt, two form retries and three tool calls per block. `config.py` is authoritative. Each block loads its packaged Russian or English Markdown prompt. The semantic content comes from the LLM. Code does not certify that a process, opposition, or resolution is philosophically or factually correct.

Only P0 receives iterative development. There is no `Internals` stage, separate opposite/contradiction bundle, or three-way next-iteration variant. If several opposites are confirmed, the first is used and dropped alternatives are traced. Only the first formed contradiction is used.

`World.schema_version=2` distinguishes the flat representation from historical bundle worlds. Developing processes store their statement with empty source/target; P0 has explicit endpoints. The generated graph is rendered to prose for the agent; it is not executed as an independent inference calculus.

Terminal statuses: `built` (replacement), `mediated`, `leap_not_found`, `no_p0`, `no_opposite`, `failed`. These are procedural statuses, not quality scores.

## Agent and revision

`WorldAdapter.brief()` has a hard character limit, including the core. A small limit can truncate core content. Historical experiments use a separate renderer with the original soft-core behaviour.

`world_fit` asks whether encountered data are compatible with the representation. It does not certify answer correctness. Missing or invalid marks do not trigger revision. A caller may pass an externally justified `WorldFit` to `WorldSession.observe()`.

Revision names active process IDs and follows `derived_from` dependencies. A development/P0 change adds one iteration and re-evaluates opposition, contradiction and resolution. A downstream change recomputes downstream stages. Replaced contradiction/resolution nodes remain stored as `superseded`, and the original world is unchanged.

Both `built` and `mediated` revisions can be adopted. Partial revisions are saved for inspection but not adopted. A later attempt uses a fresh version number; `parent_version` points to the adopted hypothesis. Saved files cannot be overwritten. Version selection is intended for a single writer; simultaneous independent sessions can get a version conflict rather than silently overwrite data.

Revision does not automatically rerun the answer that triggered it. Applications must decide whether to retry, ask a human, or report unresolved uncertainty. Tool observations and self-report are not automatically trusted evidence.

## Trace and provenance

New builds log model ID, settings, prompt SHA-256 hashes, Git commit when available, and whether tracked package code is dirty. Calls record request hashes, response objects, and task-local token usage. This prevents concurrent calls from double-counting shared usage differences. A request hash identifies a request but cannot reconstruct it; exact live reproduction also requires storing inputs, dataset/context hashes and provider snapshots. Installed wheels may have no Git metadata.

## Limits of validation

Offline tests check order, retries, parsing, references, version persistence, revision branches and usage accounting. They do not establish semantic validity, reasoning efficacy, accuracy improvements or robustness to arbitrary adversaries.
