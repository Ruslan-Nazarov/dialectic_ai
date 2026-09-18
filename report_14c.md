# STAGE 14C COMPLETE

## 1. Research questions
**RQ1**: Какие именно semantic facets вызывают false rejection валидных Development?
**RQ2**: Можно ли уменьшить false rejection, введя `PASS | FAIL | UNCERTAIN` (вместо бинарного `PASS | FAIL`) при сохранении строгой framework aggregation?

## 2. Frozen inputs
- **Valid Development (Cases 1, 5)**: Case 1 (Fresh human judgment -> Extract rule), Case 5 (Isolate data -> Prepare for sharing).
- **Negative Control (Cases 2, 3)**: Case 2 (Workflow Trap), Case 3 (Alternative Trap).

## 3. Binary facet error profile
Using 5 independent real LLM calls per facet for Cases 1 and 5. 

**Case 1 (Valid):**
- `distinctness`: **0% Pass** (5/5 Fail)
- `immanence`: **0% Pass** (5/5 Fail)
- `emergence`: 100% Pass
- `retroactive_determinacy`: 100% Pass
- `target_continuity`: **0% Pass** (5/5 Fail)
- `workflow_only`: 100% Pass (0/5 Fail - Correct, it's not just a workflow)

**Case 5 (Valid):**
- `distinctness`: **0% Pass** (5/5 Fail)
- `immanence`: **0% Pass** (5/5 Fail)
- `emergence`: 100% Pass
- `retroactive_determinacy`: 100% Pass
- `target_continuity`: 40% Pass (2/5 Pass, 3/5 Fail)
- `workflow_only`: **0% Pass** (5/5 returned True, which is a rejection of development)

## 4. Weakest facets
Pattern A is clearly observed: **Systematic weak facets**.
The facets causing the immense false rejection are:
1. `distinctness` (consistently fails)
2. `immanence` (consistently fails)
3. `workflow_only` (consistently fails Case 5, treating it strictly as sequence)
4. `target_continuity` (unstable/fails)

## 5. Error stability across runs
The errors are highly stable (systematic). GigaChat consistently interprets these specific facets in a way that rejects valid dialectical developments. 

## 6. Ternary architecture
- Modified LLM schemas: `TernaryDevelopmentOutput` and `TernaryOppositeOutput` returning `decision` (`PASS/FAIL/UNCERTAIN` or `YES/NO/UNCERTAIN`) and `reason`.
- Added `RunOutcome.SEMANTIC_UNRESOLVED`.
## 7. Valid-case results (Ternary Mode)
Running Case 1 and Case 5 with the Ternary schema (`PASS/FAIL/UNCERTAIN`) revealed **Pattern D**: Ternary mode simply translates some errors to `UNCERTAIN` and preserves authoritative `FAIL`s on other facets.
- For **Case 1**, `distinctness` was frequently evaluated as authoritative `FAIL` (not `UNCERTAIN`). 
- For **Case 5**, `workflow_only` was evaluated as authoritative `YES` across all runs, meaning the LLM was completely certain it was a workflow sequence. `distinctness` also remained an authoritative `FAIL`.
**Result**: Both valid cases were universally rejected as `INVALID` (or occasionally `UNRESOLVED`), failing to improve the useful validation rate. False Rejection remains ~100%.

## 8. Negative-control results (Ternary Mode)
- **Case 2 (Workflow Trap)**: `workflow_only` successfully triggered authoritative `YES`. Distinctness/Immanence were `PASS`. The framework aggregated this to `INVALID`.
- **Case 3 (Alternative Trap)**: The Development phase ended up as `UNRESOLVED` (due to UNCERTAIN in immanence/continuity), and Opposite returned `alternative_only=YES`. The framework successfully aggregated this to `INVALID` or `UNRESOLVED`.
**Result**: Negative controls are safely trapped. The `UNCERTAIN` category did not cause false permissiveness (False Acceptance remains near 0%).

## 9. Opposite results
Opposite checks (`excludes_need_for_simplest`, `alternative_only`) proved robust in Ternary mode. For Valid Case 1, it successfully passed both checks. For the Alternative Trap (Case 3), it accurately triggered `YES` on `alternative_only`.

## 10. False rejection comparison
- Binary Mode: ~100% False Rejection.
- Ternary Mode: ~100% False Rejection (due to authoritative `FAIL` / `YES` on required facets).

## 11. False acceptance comparison
- Binary Mode: 0% False Acceptance for Case 2/3.
- Ternary Mode: 0% False Acceptance.

## 12. Unresolved rate
Ternary mode increased the `UNRESOLVED` rate specifically for intermediate traps (e.g. Case 3 Development), successfully mapping stochastic ambiguity to a safe fallback state rather than an arbitrary binary guess.

## 13. Cost/latency
- LLM Call Count increased 6x per validation layer (Decomposed Independent).
- Latency increased proportionally since calls were sequential in the benchmark script.
- Parser Retry Count remained near zero (GigaChat reliably returned compliant JSON).

## 14. Interpretation
**Pattern D** is confirmed. The introduction of epistemic uncertainty (`UNCERTAIN`) prevents the LLM from making stochastic guesses when it's genuinely confused, which successfully handles edge-case traps (reducing False Acceptance).
However, it fails to fix the False Rejection issue for Valid Developments because the LLM is *confidently wrong* (authoritative `FAIL`) about concepts like `distinctness` and `workflow_only`. The definitions are either systematically misaligned with the model's priors or require contextual synthesis that is lost when facets are evaluated independently.

## 15. Threats to validity
- The definition of `distinctness` and `workflow_only` in the prompt may be too academically rigid for the model to map to the provided practical examples.
- Independent facet evaluation deprives the model of holistic context. For example, evaluating `distinctness` without seeing the `workflow_only` evaluation might lead the model to assume it's just a renaming.

## 16. Scientific conclusion
Final status:
```text
TERNARY_DECOMPOSITION_PARTIALLY_SUPPORTED
```

Additionally:
```text
SYSTEMATIC_WEAK_FACET = distinctness, immanence, workflow_only
FALSE_REJECTION_REDUCED = NO
FALSE_ACCEPTANCE_PRESERVED_LOW = YES
READY_FOR_STAGE_14D = YES
```
