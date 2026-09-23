# Stage 14D Benchmark Plan

## User Review Required
None immediately required, this strictly follows the prompt. I will wait for user approval before starting execution because this is a massive benchmark that will consume significant LLM tokens and time.

## Objective
Execute a rigorous, frozen, repeated empirical benchmark (Stage 14D) to evaluate four semantic modes of the Dialectic AI framework. 
Produce paper-grade datasets, statistics, and a final scientific report.

## Benchmark Configuration Freeze
- **Commit**: Will record the current git HEAD commit.
- **Model**: GigaChat (as configured in the environment).
- **Prompt Versions**: The operational prompts frozen in Stage 14C.2.
- **Dataset**: 
  - 8 held-out cases (`H_POS_1`, `H_POS_2`, `H_WF_1`, `H_WF_2`, `H_ALT_1`, `H_ALT_2`, `H_DRIFT_1`, `H_DRIFT_2`).
  - 1 historical regression case (`Case 1`).
  - 1 operational failure case (Using `H_POS_2` semantics, but deliberately failing capability lookup to verify `EXECUTION_FAILURE`).

## Experimental Modes
We will test 4 modes by using custom `MockLLMDispatcher` classes that intercept the `DialecticalRuntime` calls:
- **Mode A (Integrated)**: Uses `TRANSITION_JUDGE`.
- **Mode B (Decomposed Single-Call)**: Uses `DEVELOPMENT_FACETS_JUDGE` (one LLM call returns all 6 binary facets).
- **Mode C (Decomposed Independent Binary)**: The dispatcher intercepts `DEVELOPMENT_FACETS_JUDGE`, makes 6 independent LLM calls (one for each facet), merges the results into a single dict, and returns it to the unchanged runtime.
- **Mode D (Decomposed Independent Ternary)**: The dispatcher intercepts `TERNARY_DEVELOPMENT_FACETS_JUDGE`, makes 6 independent LLM calls for ternary facets, merges them, and returns them to the unchanged runtime.

The proposer will be strictly mocked to return the exact frozen semantic candidates (`p1`, rationales) from the JSON dataset, ensuring identical inputs for all modes.

## Metrics & Execution
- **Runs**: 5 independent runs per case per mode (Total = 10 cases * 4 modes * 5 runs = 200 runs).
- **Cost/Latency**: I will record token usage (if available), wall time, and retry/429 counts.
- **Output Artifacts**: 
  - `stage14d_runs.jsonl` (raw data)
  - `stage14d_summary.csv` (aggregated stats)
  - `stage14d_facet_summary.csv` (facet-level stats)
  - `paper_results.csv`, `paper_results.jsonl`, `benchmark_methodology.md`, `v1_architecture_summary.md`, `limitations.md`.
  - `report_14d.md` (Scientific conclusion and answers to RQ1-RQ10).

## Implementation Steps
1. Write `experiments/stage14d_benchmark.py` containing the logic for the 4 dispatchers, rate-limit handling, and metric recording.
2. Ensure all existing tests pass (`pytest tests/v1/ -v`).
3. Freeze the repository state.
4. Execute the benchmark.
5. Generate the CSV summaries and markdown artifacts.
6. Write the final report.
