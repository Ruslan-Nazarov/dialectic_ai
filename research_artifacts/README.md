# Published research artifacts

Historical own artifacts exported during the 2026-09-30 audit repairs. [manifest.json](manifest.json) records source paths and SHA-256 hashes; [audit_summary.json](audit_summary.json) is a new derived summary from the read-only audit tool. Original logs, experimental answers and metrics were not edited.

- `early_framework/`: BFCL and ablation JSON recovered from commit `47fd03c`.
- `v2_ablation/`: the 24 September deception practice-loop runs and baseline summaries, formerly ignored under `live_runs/`.
- `legacy_v3/`: pre-rewrite NDA build/revision traces, failed mini build, the cafeteria control world, and frozen historical briefs.

These data concern replaced architectures. They do not establish efficacy of the current six-prompt engine. Baseline per-call deception traces are unavailable. Context identity for the original placebo evaluation is not cryptographically recorded in the original run; see [reproducibility](../docs/REPRODUCIBILITY.md).

Logs may include generated code and prose. They are experimental source data, not instructions or runnable trusted code. Third-party ContractNLI material remains subject to the [dataset attribution](../contract_nli_runs/README.md).
