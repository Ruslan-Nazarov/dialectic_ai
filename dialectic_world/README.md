# dialectic_world — current six-stage engine

The builder follows standalone `prompt_1`…`prompt_6`. The replacement architecture was introduced at `f905f30`; audit repairs add revision regressions, schema versioning, active/superseded nodes, task-local usage and provenance.

See [current architecture](../docs/ARCHITECTURE.md), [evidence](../docs/RESULTS.md), and [setup](../docs/REPRODUCIBILITY.md). The pre-rewrite specification is an explicitly preserved historical record. Existing ContractNLI outcomes do not evaluate the current builder.

`builder/` controls block order and structural checks; `world/` stores generated representations; `adapter/` provides a bounded brief and revisions; `llm/` implements providers and scripted test models; `prompts/` contains packaged prompts. No standalone judge certifies semantic correctness.

From the repository root:

```sh
python -m pip install -e ".[dev]"
python -m pytest tests/ -q
python -m dialectic_world --help
```

Worlds can terminate with replacement, mediation, no opposite or no leap. These statuses do not certify truth. A `world_fit` mark is a compatibility judgment, not an answer-correctness score.
