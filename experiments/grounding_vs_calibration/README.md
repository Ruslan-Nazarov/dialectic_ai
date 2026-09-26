# Grounding vs calibration — experiment stand

Tests whether a calibrated confidence signal alone can tell a wrong agent answer from a right one, or
whether that needs an external (grounding) signal. Full design in [PREREGISTRATION.md](PREREGISTRATION.md),
full results in [RESULTS.md](RESULTS.md). This README is only about running the stand yourself.

## Setup

1. An `OPENAI_API_KEY` in a `.env` file two directories up (repo root), or in your environment. `gpt-5-mini`
   (variant 3's re-verdict call) and `gpt-4o-mini` (variant 2's surrogate Decider) both go through the
   OpenAI API.
2. Download ContractNLI (CC BY 4.0, Koreeda & Manning, EMNLP Findings 2021) from its official source —
   not committed to this repo:

```bash
python download_contract_nli.py
```

This fetches `https://stanfordnlp.github.io/contract-nli/resources/contract-nli.zip` into
`data/contract-nli/` (gitignored). Safe to re-run — skips the download if `test.json` is already there.

The NDA world file used by variant 2 (`data/world_nda_v1.json`) is already checked into this repo, since
it's this experiment's own artifact, not a third-party dataset.

## Run

Needs an `OPENAI_API_KEY` (env or repo-root `.env`) for `pilot.py`/`full_run.py` — `data.py` and
`pytest tests/` need no API key at all, only the downloaded dataset.

```bash
python data.py            # sanity check: recomputes 54.3% accuracy against ContractNLI gold
python -m pytest tests/    # unit tests -- data-dependent ones skip with a clear message until step 2 above
python pilot.py            # 10 real answers, all 3 variants, cost estimate
python full_run.py         # all 258 answers, all 3 variants, parallel -- writes raw_results.json
python analyze.py          # frozen metrics from PREREGISTRATION.md -- writes metrics_summary.json
python post_hoc.py         # exploratory breakdown only, does not touch frozen metrics
```

One command for the whole pipeline (assumes the dataset is already downloaded):

```bash
python -m pytest tests/ -q && python full_run.py && python analyze.py && python post_hoc.py
```

**Cost of a full run** (258 answers, all 3 variants; actual numbers from the run behind RESULTS.md):
~301k prompt + ~260 completion tokens on `gpt-4o-mini` (variant 2) and ~34k prompt + ~62k completion
tokens on `gpt-5-mini` (variant 3's re-verdict) — roughly 335k prompt / 63k completion tokens total,
~516 API calls, ~70s wall-clock with the default 16 parallel workers. Variant 1 makes no calls.

## Switching variant 2's Decider to Jev

Variant 2 talks to a `Decider` (`decider.py`), matched to Jev's `Choice` primitive:
`choice(state, options) -> {choice, probabilities, confidence}`. Which implementation runs is one
environment variable:

```bash
export DECIDER_IMPL=surrogate   # default: a real logprob-capable OpenAI model (gpt-4o-mini)
export DECIDER_IMPL=jev         # TypeSafe AI's Choice primitive, via POST /v1/systemone
export TYPESAFE_API_KEY=...     # only needed for DECIDER_IMPL=jev
```

**`JevDecider` is written from TypeSafe's public docs only and is untested: no access key was available
while building this stand.** It raises `NotImplementedError` immediately on any call — setting
`DECIDER_IMPL=jev` without also fixing that will fail loudly, on purpose, rather than silently running the
surrogate. Once real TypeSafe access exists, implement the actual request in `JevDecider.choice()` /
`choice_binary_none()` in `decider.py` and remove the `raise`; nothing else in `pilot.py`/`full_run.py`
needs to change.

## What each variant actually is

1. **Self-report** — the agent's own `world_fit` mark from the original run. No calls, no cost.
2. **Choice-with-probabilities** (calibration) — a Decider call per answer, main signal = `P(none fits)`.
3. **Quote-anchored re-verdict** (renamed from "practice / external signal" after the post-hoc analysis
   found the mechanical "quote not found" check never fires on this data by construction — see
   PREREGISTRATION.md's 2026-09-27 correction). Retrieval is code-only; the re-verdict step is a second
   model call, so this variant is only partially external, not a pure grounding check.

## Verified clean-clone run

This stand was cloned fresh into a temp directory and run end to end (`pytest` → `download_contract_nli.py`
→ `full_run.py` → `analyze.py` → `post_hoc.py`) with no repo-relative assumptions beyond this folder, to
confirm someone outside this environment can reproduce it from a bare `git clone`.
