"""
dialectic_ai/core/domain.py

What a task domain already knows, handed to the engine instead of being written
into the actor's role text and re-litigated by the judge.
"""
from dataclasses import dataclass, field
from typing import Optional

from dialectic_ai.core.runtime import MoveType


@dataclass(frozen=True)
class Domain:
    """Domain knowledge the engine enforces rather than asks the model to guess.

    semantics: the domain meaning of the dialectical terms. The actor sees it next to
        its role; the judge sees it INSTEAD of the role, so the judge is never handed
        the role's demands on the finished result (tools to call, what COMPLETE must
        contain) and never holds an intermediate move to them.
    opposite: an opposite process the domain fixes in advance. The engine designates
        it itself once the simplest has developed, and the actor is not offered
        DESIGNATE_OPPOSITE at all -- it develops the opposite but does not choose it.
    unjudged_moves: moves checked only structurally, e.g. a route the domain fixes.
    judge_criteria: per-move criteria that override the judge's generic ones.
    tool_call_limits: the most times each named tool may be called in one run. Enforced by the
        engine before the judge; the model sees the remaining calls next to each tool. On the
        business-card domain the role's "at most 2 rounds of questions" was ignored and one run
        asked 4 rounds, chasing a field the business never knew, until the deadline.

    Observed on the business-card pilot without this (0/3 runs reached the first
    question): the judge rejected the domain's own opposite up to 8 times in a row,
    rejected DEVELOP_PROCESS because "the role requires a full card", and rejected a
    one-way route (ask, then commit the card) 7 times as incomplete.
    """

    name: str
    semantics: str
    opposite: Optional[str] = None
    opposite_justification: str = "Fixed by the task domain, not chosen by the model."
    unjudged_moves: frozenset = frozenset()
    judge_criteria: dict = field(default_factory=dict)
    tool_call_limits: dict = field(default_factory=dict)

    def calls_left(self, tool_name: str, calls_made: int) -> Optional[int]:
        limit = self.tool_call_limits.get(tool_name)
        return None if limit is None else max(0, limit - calls_made)

    def judge_criterion(self, move: MoveType) -> Optional[str]:
        return self.judge_criteria.get(move) or self.judge_criteria.get(move.value)
