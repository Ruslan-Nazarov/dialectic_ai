# DialecticAI — Phase 6 (corrected): Reliability, Code Quality & Architecture Consistency

**Status of this document:** this is a corrected revision of a plan proposed by another agent session, which was built from `CODE_REVIEW.md` without cross-checking `REFACTOR_PLAN.md`'s own `✅ DONE` markers or the current code — 4 of its 11 structural items were already fixed earlier this session (2026-09-15). Every item below was re-verified against the actual current code on 2026-09-16 before being kept or dropped. Do not re-verify from scratch — this document already did that; just execute what's listed.

**Baseline (confirmed 2026-09-16):** `python -m pytest tests/ -q` → `75 passed, 2 skipped`. `python tests/local_runner.py` → 3/3 `completed`.

---

## Already done — do NOT redo these (verified against current code, 2026-09-16)

The original plan proposed these as open work. They are not open. Re-checking them would waste time; if you want to confirm, grep for the cited line, don't re-implement.

- **`sqlite_graph.py` duplicate `process_turn`** — only one definition exists now (line 65). Already fixed 2026-09-15.
- **`memory/base.py` dead abstract-method body** — already stripped to `...` (line 56-57). Already fixed 2026-09-15.
- **`EvidenceStore._executed_actions` set from outside the class** — already initialized in `EvidenceStore.__init__` (line 17); no external assignment remains anywhere in `executor.py`. Already fixed 2026-09-15.
- **`cmd_audit`'s judge LLM never tries GigaChat** — it already does, first in the fallback chain (`cli/main.py` lines 143-154: GigaChat → Gemini → OpenAI). Already fixed 2026-09-15.
- **`config_parser.py` missing a GigaChat option** — already present (line 43: `elif llm_name == "gigachat":`). Already fixed 2026-09-15. (The original plan correctly identified this one as done — no correction needed here.)
- **`BaseMemory`/`Memory` Protocol full migration** (the "open question" in the original plan) — **decision: do not do it.** `REFACTOR_PLAN.md` Phase 5.3 already deliberately deferred this as a bigger, disruptive architectural change; the specific bugs that made it feel urgent (the two dead-code items above) are already fixed. Nothing left to decide here.

---

## A. `ControlledRepairError` reliability (~35% crash rate on complex prompts)

**Correction to the original plan:** the original proposed fix ("if `has_content` passes but `leap_type` is invalid, normalize it to `""` instead of raising `ParseError`") does not address the actual observed failure. Direct evidence from a real captured trial (2026-09-16 ablation run, `decompose_or_block` scenario):

```
"hypothesis": {
    "assumption": "...",
    "plan_steps": [
      {"step": "Save the note"},
      {"s
```

This is a response that was **cut off mid-generation** (the JSON is never closed — this is a raw-text/length problem, not a schema-validation problem) and, separately, `plan_steps` was formatted as a **list of objects** (`{"step": ...}`) instead of the expected list of strings. Neither of these ever reaches `leap_type` validation: the failure happens at `json.loads()`/syntax level, before Pydantic would even check individual field values. A `leap_type`-normalization fix would not have prevented this crash.

**Also correct a factual gap:** this session's own ablation runner did not save full raw responses for crashed trials (only the exception message, `"Failed to repair JSON response."`) — so the single example above is real but not yet a confirmed *dominant* pattern across all ~35% of failures. Do not skip straight to a fix; gather evidence first, same discipline this project has used throughout.

### A1. [NEW] Capture real evidence before fixing anything
Write a small, throwaway repro script (not necessarily a permanent test) that:
- Builds a moderately complex, multi-tool prompt similar to what triggered the 35% rate (3+ tools, Rule 5 fields required).
- Runs it against real `GigaChatLLM` 10-15 times.
- On any `ControlledRepairError`, saves the **full** `raw_response` (the exception already carries this in `.raw_response` — just log/print it in full, don't truncate) plus the repair attempt's own output if available.
- Look for the actual dominant pattern: is it truncation (response cut off mid-JSON), a type-shape mismatch (`plan_steps` as objects), something else, or a mix? Do not assume the answer from one example — get several.

### A2. [MODIFY] `engine/repair.py` — only after A1 confirms the mechanism
Candidate fixes, to be chosen based on what A1 actually shows (do not implement blind):
- If truncation is dominant: the repair call currently shares the same LLM instance/`max_tokens` ceiling as the original call that already ran out of budget writing a malformed response — consider a larger, repair-specific `max_tokens`, or shorten the repair prompt (it currently re-embeds the full `FORMAT_INSTRUCTION` plus up to 6000 chars of the original response) to leave more output budget.
- If `plan_steps`-as-objects (or similar shape mismatches) is common: add an explicit one-line example to `FORMAT_INSTRUCTION` or the repair prompt showing `plan_steps` must be `["step one", "step two"]`, not `[{"step": "..."}]`.
- A `leap_type` normalization guard is harmless to add defensively regardless (it's a cheap, real hardening — `LeapType = Literal["decompose_and_act", "ask_only", "fully_resolved", ""]`, so anything else should map to `""` rather than fail) but treat it as a minor addition, not the headline fix.

### A3. [MODIFY] the ablation runner (if resurrected) or any new repro script
Whatever script is used for A1, make it save the **full** raw response on any crash, not just the exception message — this was a real, named gap in this session's own tooling (`development_log.md`, 2026-09-15) that made this exact diagnosis harder than it needed to be.

**Verification:** re-run the same repro 15-20 times before and after the fix; report the crash rate both times. Do not claim success from a single clean run — this project has a repeatedly-documented pattern of "looked fixed, wasn't" for exactly this failure mode (`development_log.md`, 2026-09-14).

---

## B. Lint / type cleanup (ruff + mypy)

The original plan's categorization is sound; keep it as-is:
- **Autofix now** (safe, mechanical): `I001` (unsorted imports, 49), `F541` (f-string without placeholder, 4), `E701` (multiple statements, 3), `E721` (`type(x) == Y` → `isinstance`, 3).
- **Manual review, fix where safe**: `F401` (unused import, 20 — check for intentional re-exports before removing), `F841` (unused variable, 2).
- **Leave alone deliberately**: `E501` (line-too-long, 55 — comments and prompts, not worth reformatting), `E402` (module-import-not-at-top, 6 — intentional conditional imports in the CLI).
- **mypy** (64 findings): after the ruff pass, re-run `mypy dialectic_ai --ignore-missing-imports`, add annotations where the fix is obvious, `# type: ignore` with a one-line reason where the mismatch is intentional (e.g., the `FallbackLLM`/provider-union patterns already known from `CODE_REVIEW.md`).

**Resolving the original plan's open question (commit granularity):** one commit for the autofix pass (it's mechanical and reviewable as a single diff — ruff's own `--fix` output is not something worth splitting file-by-file), a separate commit for manual `F401`/`F841` cleanup, a third for any mypy annotations/`type: ignore` additions. Three commits, not one per file.

---

## C. Structural fixes (genuinely still open, verified 2026-09-16)

### C1. [MODIFY] `dialectic_ai/multi/__init__.py` — export `DialecticalTriad`/`DialecticalDebateEngine`
Add:
```python
from dialectic_ai.multi.triad import DialecticalTriad
from dialectic_ai.multi.debate import DialecticalDebateEngine
```
and both names to `__all__`. Verify: `python -c "from dialectic_ai.multi import DialecticalTriad, DialecticalDebateEngine; print('OK')"`.

### C2. [NEW FILE] `dialectic_ai/integrations/gigachat/__init__.py`
Create with `from .llm import GigaChatLLM` (mirroring `integrations/mcp/__init__.py`'s pattern). GigaChat is this project's most-used real provider and is the one integration with no package-level export. Verify: `python -c "from dialectic_ai.integrations.gigachat import GigaChatLLM; print('OK')"`.

### C3. [MODIFY] `dialectic_ai/engine/executor.py` — redundant `import json`
`import json` appears 3 times: top of file (line 19, correct) plus twice more inline inside `_phase_collide` (lines 345, 420). Remove the two inline ones; `json` is already available module-wide.

### C4. [MODIFY] `dialectic_ai/cli/creator.py` + `dialectic_ai/cli/main.py` — `max_iterations` default too low
- `cli/creator.py` line 166 generates `"max_iterations": 3` in every wizard-created declarative config — too low for any real multi-step task (`DialecticalEngine`'s own default is 5, and even that is documented as too low for realistic tasks). Raise to `10`.
- `cli/main.py`'s `cmd_run` (line 213) falls back to `config.get("max_iterations", 3)` for configs that omit the field — raise this default to `10` too, for consistency.
- Optional, lower priority (real but not urgent SMELL): `cmd_run` currently parses the same JSON config file twice — once via `load_agent_from_config(args.config)`, once again directly to read `max_iterations` (its own comment admits this: "read again, as the parser currently returns only the agent"). A cleaner fix would have `load_agent_from_config` return `(agent, config_dict)` or similar; only do this if you have time left after the higher-priority items, since the double-read is harmless, just inelegant.

### C5. [MODIFY] `dialectic_ai/core/decorators.py` — document the `list[str]`/`Optional[str]` gap
`@dialectical_tool`'s auto-schema generation (`parameters()`) only recognizes `int`/`bool`/`float`; anything else (including `list[str]`, `Optional[str]`, dataclasses) falls back to `"string"`. Do not implement full type-hint introspection (real risk of regression for a low-traffic code path) — add a clear comment stating the limitation, so the next person doesn't discover it by surprise.

### C6. [MOVE/DELETE] `test_app.py` (repo root)
Duplicates `examples/advanced_agent.py`'s purpose, untouched since the project's first commit, not part of `examples/` or `tests/`. Read both files, and either delete `test_app.py` if it adds nothing `examples/advanced_agent.py` doesn't already do better, or move/rename it into `examples/` with the same polish as the other examples if it demonstrates something genuinely distinct. Verify `pytest` is unaffected either way (nothing imports this file).

---

## Verification plan (run after every section, not just at the end)

```bash
python -m pytest tests/ -q                              # expect: 75 passed, 2 skipped (must not decrease)
python tests/local_runner.py                             # expect: 3/3 completed
python -m ruff check dialectic_ai/ --statistics          # expect: ~55 remaining (E501/E402 only, left deliberately)
python -c "from dialectic_ai.multi import DialecticalTriad, DialecticalDebateEngine; print('OK')"
python -c "from dialectic_ai.integrations.gigachat import GigaChatLLM; print('OK')"
```

For section A specifically: do not consider it done until A1's evidence-gathering step has actually run and its output is reported, even if the conclusion is "inconclusive, needs more samples." A crash-rate claim without a fresh, real measurement is not acceptable for this section given the project's own repeated history of "looked fixed, wasn't."

## development_log.md

Add one entry per section (A, B, C), not one giant entry at the end, following the project's own established format (Simplest process → Development → Opposite process → Contradiction → Leap → Reality Check → Own contradictions — see any 2026-09-1x entry for the pattern). Section A's entry in particular must state the actual evidence found in A1, not just "fixed the crash rate."
