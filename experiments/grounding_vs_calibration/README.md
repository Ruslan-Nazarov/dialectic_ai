# Compatibility, self-report and quote-based re-verdict

See [RESULTS.md](RESULTS.md) and [PREREGISTRATION.md](PREREGISTRATION.md). Variant 2 round 1 is INVALID: only opaque process IDs were shown. Corrected round 2 uses the historical world brief and is the operative result. Variants 1 and 3 were not invalidated.

## Check existing evidence without API calls

From the repository root:

```sh
python -m pip install -e ".[dev,research]"
python tools/audit_evidence.py --check --bootstrap
python -m pytest tests/ experiments/grounding_vs_calibration/tests/ -q
```

The audit reads `raw_results_round2.json` and recomputes AUROC/CI without overwriting evidence. Dataset-dependent tests skip if ContractNLI has not been downloaded.

## Rerun corrected scoring

Use a disposable clone to preserve historical outcomes. `full_run_v2.py` makes live calls and writes round-2 outputs; `analyze_round2.py` writes its metric summary. The old `full_run.py` / `analyze.py` are retained only to inspect the INVALID round-1 design.

```sh
python experiments/grounding_vs_calibration/download_contract_nli.py
python experiments/grounding_vs_calibration/full_run_v2.py
python experiments/grounding_vs_calibration/analyze_round2.py
```

Required environment: `OPENAI_API_KEY` for surrogate gpt-4o-mini and quote re-verdict gpt-5-mini; `TYPESAFE_API_KEY` for implemented Jev Choice calls. `JevDecider` is implemented and was used in round 2; the former unimplemented-client description was obsolete. Root `.env` is supported and remains ignored.

`data/world_nda_v1.json` is committed own evidence. The pre-rewrite schema is deliberately loaded using `experiments/legacy_world.py`, not the current engine's World model. The renderer is tested against the 7717-character frozen brief. Full dataset, models and credentials are external dependencies; API aliases can change results.

## What is measured

1. Original `world_fit` self-report: no new calls.
2. `P(none fits)` in a historical brief as an error proxy: surrogate and real Jev; not a general test of solver confidence.
3. Quote-anchored re-verdict: mechanical retrieval and a second model verdict. All retrieved quotes passed the existence check, so this is not a demonstrated advantage of independent grounding.

The corrected score was inverted. Jev's confidence on its own answers was informative in another experiment. See [scientific limitations](../../docs/RESULTS.md) and [full reproduction guide](../../docs/REPRODUCIBILITY.md).
