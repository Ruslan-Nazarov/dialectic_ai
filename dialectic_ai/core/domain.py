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

    def judge_criterion(self, move: MoveType) -> Optional[str]:
        return self.judge_criteria.get(move) or self.judge_criteria.get(move.value)
