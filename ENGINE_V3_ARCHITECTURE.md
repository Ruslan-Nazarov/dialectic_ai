# Engine v3: current architecture

The current executable architecture is documented in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). It uses standalone `prompt_1` through `prompt_6`, introduced by `f905f30` on 2026-09-27.

`FindP0 → BuildIteration → CompareDevelopment → CheckOpposition → FormContradiction → ResolveLeap`

Only P0 has iterative development. The old internal-process layer, three bundles, and iteration variants have been removed. Current worlds have schema version 2. Revision preserves versions and distinguishes replacement and mediation.

The original 25 September implementation specification is preserved in [the historical specification](docs/history/ENGINE_V3_ARCHITECTURE_PRE_REWRITE.md). The initial ContractNLI worlds and build/revision results used that replaced architecture, not the current engine. See [results](docs/RESULTS.md) and [reproducibility](docs/REPRODUCIBILITY.md).
