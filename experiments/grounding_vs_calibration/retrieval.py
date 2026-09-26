"""Verbatim quote check and single-quote re-verdict for variant 3: quote-anchored re-verdict
(renamed from "practice / external signal" -- see PREREGISTRATION.md's 2026-09-27 amendment. The
quote-found check is code-only and external, but the re-verdict step is a second model call, so
"external signal" overstated how independent of the model this variant actually is).

No ContractNLI evidence spans are used anywhere here -- only raw contract text and keyword/sentence
search, matching the preregistration's ban on evidence-span leakage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


def split_sentences(text: str) -> list[str]:
    # Simple sentence splitter; contracts are not narrative prose but this is good enough for
    # keyword-window search without touching gold evidence spans.
    parts = re.split(r"(?<=[.;])\s+", text.replace("\n", " "))
    return [p.strip() for p in parts if p.strip()]


def keyword_search(text: str, query: str, max_hits: int = 5) -> list[str]:
    """Sentence-level keyword search over the raw contract text (the only 'tool' variant 3 gets)."""
    sentences = split_sentences(text)
    query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
    if not query_terms:
        return []
    scored = []
    for s in sentences:
        s_lower = s.lower()
        score = sum(1 for t in query_terms if t in s_lower)
        if score:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:max_hits]]


def quote_found_verbatim(contract_text: str, quote: str) -> bool:
    """Whether `quote` appears verbatim (whitespace-normalized) in the contract text."""
    normalize = lambda s: re.sub(r"\s+", " ", s).strip()
    return normalize(quote) in normalize(contract_text)


@dataclass
class QuoteReverdictSignal:
    quote_found: bool
    reverdict: str | None
    reverdict_matches_original: bool | None

    @property
    def quote_not_found_signal(self) -> bool:
        return not self.quote_found

    @property
    def verdict_disagreement_signal(self) -> bool:
        return self.quote_found and self.reverdict_matches_original is False

    @property
    def error_signal(self) -> bool:
        """Union of the two sub-signals, for the combined variant-3 metric."""
        return self.quote_not_found_signal or self.verdict_disagreement_signal
