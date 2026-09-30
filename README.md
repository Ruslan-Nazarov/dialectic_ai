# DialecticAI — reasoning structure and verification experiments

**Research question:** where should AI-generated reasoning end, and external human or grounded judgement begin? This repository tests whether externally imposed reasoning structures, domain representations, and verification procedures change the behaviour of existing language models.

This is an experimental research project. It does not establish a new kind of AI, eliminate hallucinations, or prove that AI cannot handle contradictions. The current engine has offline regression tests and smoke builds; its comparative efficacy has not been established.

## Start here

- [Results and limitations](docs/RESULTS.md): completed experiments, negative findings, uncertainty, and planned work.
- [Current architecture](docs/ARCHITECTURE.md): the executable six-stage builder and revision policy.
- [Reproduce the evidence](docs/REPRODUCIBILITY.md): offline checks, historical treatments, API setup, and missing evidence.
- [Research program](docs/RESEARCH_PROGRAM.md): what follows from these experiments.
- [Audit repairs](docs/AUDIT_FIXES.md): changes made after the September 2026 audit.

## What the experiments show

| Experiment | Scope | Finding | Status |
|---|---|---|---|
| BFCL raw vs early framework | 125 tasks × 3 repeats per condition | 83.20% vs 80.53%; Wilcoxon p=0.5822 | Historical, no detected gain |
| Early orchestration ablations | 20 runs per condition per scenario | `flaky_retry` improved over bare; `decompose_or_block` worsened vs engineered baseline | Historical, mixed |
| ContractNLI gpt-5-mini | 129 selected pairs × 2 repeats × 3 conditions | No world / NDA / control: 57.36% / 54.26% / 56.20% | Historical world, no detected gain |
| World compatibility self-report | 258 NDA-world answers | `fits=True` for all, including 118 wrong answers | No error discrimination |
| Corrected compatibility probability | 258 answers, 129 pairs | Error AUROC 0.223 / 0.278; both CIs below 0.5 | Inverted fit signal; first design INVALID |
| ContractNLI Jev solver | 2091 pairs, 123 documents | 72.93% / 72.41% / 72.36%; world differences include zero | Historical briefs, no detected gain |
| Jev self-confidence | Same solver run | Correctness AUROC approximately 0.78 | Informative auxiliary signal |
| Separate Jev verifier | 773 saved answers, 129 pairs, 83 documents | AUROC 0.6358, 95% CI [0.5493, 0.7154] | Modest verification signal |
| v2 deception practice loop | Three runs per condition | Recovery and unresolved reports; only 2/3 full unknowable runs actually saw a lie | Preliminary synthetic small-N |
| Current `prompt_1`…`prompt_6` engine | Unit tests and individual builds | Execution and persistence demonstrated | No controlled efficacy result |

Details, confidence intervals, architecture provenance and counterexamples are in [RESULTS](docs/RESULTS.md). Fit probabilities, solver confidence and verifier confidence are different measurements; these experiments do not show that confidence is generally useless or that multi-agent systems are generally better.

## Current engine

`dialectic_world/` builds a revisable representation of a domain:

`P0 → development iterations → opposition candidates → opposition check → contradiction → replacement or mediation`

A **world** is a stored set of generated process statements, dependencies, and reasoning records. A **process** is a statement about change; development nodes need not have explicit endpoints. **Opposition** and **resolution** are judgments elicited from the builder model, not independently established facts. Code controls the sequence and checks JSON and structural consistency. The adapter supplies a bounded prose brief to another agent. The agent can flag incompatible observations; callers can also provide external signals.

The rewrite at `f905f30` replaced the earlier v3 bundle/internal-process implementation. ContractNLI findings above used that earlier representation and its historical renderer. `engine_v2/` is a separate, unsupported historical runtime. [Architecture details](docs/ARCHITECTURE.md).

## Install and verify without API calls

Python 3.10 or later:

```sh
python -m pip install -e ".[dev,research]"
python -m pytest tests/ experiments/grounding_vs_calibration/tests/ -q
python tools/audit_evidence.py --check --bootstrap
```

The audit command reads saved artifacts, verifies their SHA-256 hashes, and recomputes key metrics without calling APIs or overwriting results. Dataset-dependent tests skip until ContractNLI is downloaded. For archived v2 tests and a pinned environment, see [reproducibility](docs/REPRODUCIBILITY.md).

Live building uses a separately configured API account:

```sh
python -m dialectic_world build "a domain description" --model openai:gpt-5 --worlds worlds
python -m dialectic_world show "a domain description" --worlds worlds
```

`OPENAI_API_KEY` can be supplied through the environment or a local `.env`. Live calls consume API quota. See the complete [provider setup](docs/REPRODUCIBILITY.md#provider-configuration).

## Repository map

| Path | Purpose |
|---|---|
| `dialectic_world/`, `tests/` | Current engine and offline tests |
| `docs/` | Current research-facing documentation |
| `experiments/` | Preregistrations, experiment code and saved results |
| `research_artifacts/` | Published historical traces, context briefs and checksum manifest |
| `contract_nli_runs/` | Saved ContractNLI agent answers and historical evaluation code |
| `engine_v2/` | Unsupported earlier implementation and archived stress tests |
| `ENGINE_V3_*.md`, `PROMPTS_SNAPSHOT_PRE_REWRITE.md` | Explicitly marked historical records |

ContractNLI excerpts retain their [CC BY 4.0 attribution](contract_nli_runs/README.md). Source code is [MIT licensed](LICENSE). Downloaded third-party datasets and credentials are not committed. Own experimental evidence is kept in tracked artifact directories, not hidden with downloaded datasets.
