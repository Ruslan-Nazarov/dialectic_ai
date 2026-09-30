# Repairs after the September 2026 audit

The audit compared public `main` at `0db0b11` with the working checkout at `fed8235`. The repair branch starts from the latter, retaining its three local research commits. The old experimental responses and scores have not been rewritten to improve results.

## Runtime repairs

- Revision no longer mixes a list with set operations. Both contradiction and resolution paths can be rebuilt.
- Replaced contradiction/resolution processes are marked `superseded` and omitted from the current brief. Prior World objects and saved versions remain unchanged.
- Failed attempts consume distinct version numbers; the next attempt points to the adopted parent. A mediated result can be adopted, just like a replacement.
- World files use exclusive creation. Repeated independent builds also allocate a fresh version. Concurrent writers cannot overwrite an existing version; version allocation remains a single-writer operation.
- The brief's character cap also covers its core. Malformed `world_fit` metadata returns no usable signal instead of crashing the agent. The current answer-format instruction does not preselect `fits=True`.
- Opposition references are checked against actual iteration process IDs. This is a structural check, not a semantic judge.
- Per-call token accounting uses task-local usage, avoiding subtraction of shared totals during concurrent calls. Tool-request calls are included in block traces.
- New build traces record schema, model, settings, source commit when available, prompt hashes and per-call request hashes. Historical runs retain their original missing metadata.

## Evidence and documentation

- The landing page starts with the research question and reports negative findings alongside positive signals. Current six-prompt architecture is documented separately from historical v2 and pre-rewrite v3.
- The previous architecture specification is retained in `docs/history/`; old result documents carry explicit historical banners.
- BFCL aggregates, selected v2 deception traces, old-world control and build/revision traces are exported in `research_artifacts/`, with 33 source/hash records. Evidence bytes are preserved across platforms through Git attributes.
- A read-only legacy renderer reproduces the frozen NDA and control briefs (7717 and 7960 characters) without loading historical data into the incompatible current schema.
- `tools/audit_evidence.py --check --bootstrap` verifies hashes and recomputes key metrics, including selected published confidence intervals. It requires no API credentials or downloaded corpus.
- Corrected reports distinguish compatibility probabilities from solver confidence; Jev solver confidence had useful AUROC around 0.78. Stage 14 repetition stability is distinguished from correctness. The deception report discloses the formatted-output bypass and the full run that never saw a lie.
- Historical evaluation/demo paths are repaired. ContractNLI runner output defaults to scratch files and refuses existing results. Other historical experiment scripts still require a disposable clone for live reruns.
- Offline CI covers the current engine on Windows and Linux, archived v2 tests, evidence recalculation and wheel building. Release builds run the same current checks first.

## What repairs cannot establish

These changes repair software, evidence access and the interpretation of existing data. They do not establish that the current builder improves reasoning. Baseline per-call deception traces, early control-world identity metadata and some exploratory pilot outputs were never recorded or were not available. Original provider aliases may have changed. Those limitations are documented rather than filled in with invented evidence.

See [reproducibility](REPRODUCIBILITY.md) for commands and [results](RESULTS.md) for the supported scientific conclusions. Final test and installation results are recorded in the repair commit/PR description.
