# Reproducing evidence

## Offline audit (recommended first)

From the repository root, Python 3.10+:

```sh
python -m pip install -e ".[dev,research]"
python -m pytest tests/ experiments/grounding_vs_calibration/tests/ -q
python tools/audit_evidence.py --check --bootstrap
```

No API key, downloaded dataset or Git-history checkout is required for this audit command. It verifies artifact hashes and recomputes accuracy, fit counts, Stage 14 repeatability, deception exposure, BFCL Wilcoxon and selected bootstrap CIs. `--output scratch/audit.json` writes a new summary and refuses an existing output. [Checked summary](../research_artifacts/audit_summary.json).

The root [constraints file](../requirements-audit.txt) pins the core audit/test environment from the repair session. Use `python -m pip install -e ".[dev,research]" -c requirements-audit.txt` for it. Optional live providers and archived v2 dependencies have their own requirements and are not covered by this pin set.

Archived v2 tests:

```sh
python -m pip install -e "./engine_v2[dev,dashboard]" openai
cd engine_v2
python -m pytest -q
```

Live suites are opt-in through `DIALECTIC_RUN_LIVE=1` / `DIALECTIC_RUN_CANARY=1`; keep them unset for offline tests. Full v2 source snapshots may require an earlier checkout. The v2 archive is preserved rather than silently upgraded to the current engine.

## Historical treatments

The current World schema cannot load old `bundles`, `internal` and `retired` records as current worlds. [legacy_world.py](../experiments/legacy_world.py) provides a read-only historical renderer derived from `14d9114`. It preserves ordering and the old soft core limit. It does not migrate semantic content.

Committed contexts:

- NDA JSON: `experiments/grounding_vs_calibration/data/world_nda_v1.json`.
- Control JSON and frozen briefs: `research_artifacts/legacy_v3/`.
- SHA-256 and source paths: `research_artifacts/manifest.json`.

The NDA brief is 7717 characters, control 7960. Control identity with the original 25 September eval is inferred from text and the only available local version, not a stored world hash in that run. Later experiments explicitly used this control file. New provenance cannot retroactively remove the early uncertainty.

BFCL data and early ablations were recovered from `47fd03c`. Their runnable original source remains in Git history. `ENGINE_V3_ARCHITECTURE.md` and original revision outcomes belong to the pre-`f905f30` builder. Historical results must not be relabeled as current-engine outcomes.

## Dataset and live reruns

Download ContractNLI from the official source:

```sh
python experiments/grounding_vs_calibration/download_contract_nli.py
```

It writes `experiments/grounding_vs_calibration/data/contract-nli/`. See [attribution](../contract_nli_runs/README.md). The dataset is not committed. With it present, dataset-dependent tests cross-check the saved gold labels.

For corrected compatibility scoring, use `full_run_v2.py`, not the old `full_run.py` opaque-ID design. Work in a disposable clone/output directory: legacy experiment analysis scripts write their result JSON files, and historical baselines must be preserved.

```sh
python experiments/grounding_vs_calibration/full_run_v2.py
python experiments/grounding_vs_calibration/analyze_round2.py
```

These two commands make live calls and regenerate round-2 outputs; the offline audit above is the route for checking existing data. Jev experiments use `full_run_exp1.py` (single question) and `full_run_exp2.py` (batched verifier). A small pilot's batching guardrail is not a proof of independence.

Historical gpt-5-mini evaluation supports the published old worlds and a shared dataset path:

```sh
python contract_nli_runs/eval_v3.py --world experiments/grounding_vs_calibration/data/world_nda_v1.json --placebo research_artifacts/legacy_v3/control_world_v1.json --out scratch/eval_v3_new.json
```

It refuses existing result output. This is a rerun of a historical treatment using present API models; aliases and provider changes may prevent exact numeric reproduction.

The older v2 case and scan runners also support `--help`, a shared `--dataset` path, and new scratch output paths (`--out-dir` / `--out`). Install the archived v2 dependencies before running them.

Current local revision demo:

```sh
python contract_nli_runs/revise_demo.py --help
```

It requires a current-schema world, active process ID, explicit observation and mismatch explanation. No automatic factual evaluation is implied.

## Provider configuration

Use environment variables or an untracked root `.env`. No credentials belong in artifacts.

| Provider / task | Required | Optional |
|---|---|---|
| OpenAI / historical surrogate | `OPENAI_API_KEY` | `OPENAI_MODEL`, `OPENAI_BASE_URL` |
| Jev / TypeSafe experiments | `TYPESAFE_API_KEY` | Experiment code records `jev-latest`; alias may change |
| GigaChat current engine | `GIGACHAT_CREDENTIALS` | `GIGACHAT_MODEL`, `GIGACHAT_SCOPE`, `GIGACHAT_CA_BUNDLE`; install `.[gigachat]` |
| Anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL`; install `.[anthropic]` |
| Groq, Cerebras, OpenRouter, NVIDIA | respective `*_API_KEY` | respective `*_MODEL`, `*_BASE_URL` |
| v2 live/canary | Provider key (v2 GigaChat uses `GIGACHAT_AUTH_KEY`) | `DIALECTIC_LIVE_ACTOR`, `DIALECTIC_LIVE_JUDGE`, `DIALECTIC_LIVE_REPEATS`, `DIALECTIC_LIVE_CASES`, `DIALECTIC_LIVE_DIR`, `DIALECTIC_CANARY_PROVIDER`; see v2 README |

## Remaining limits

Baseline per-call deception traces were not saved; baseline summary/response excerpts are available. Some ad hoc and local pilot data remain excluded, and their prose claims are not independently reproducible from this repository. Builder model metadata was absent from some original traces. Historical provider prices are dated estimates, not current quotations. Exact prompts/configuration and a frozen provider snapshot are required for stronger live reproducibility.

CI exercises software tests, artifact integrity and metric recalculation without live calls. It cannot certify the correctness of generated worlds or validate a research hypothesis.
