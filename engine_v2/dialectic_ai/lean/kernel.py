"""Generic, task-agnostic core of the lean dialectical runtime.

`graph.py` is a worked example where a human pre-solves what "opposite" means
for one task class (appeal triage) and bakes it into the schema as a fixed
Literal. That is a legitimate, fast choice when someone has 10 minutes to
think about the task before coding -- but it does not generalize: a genuinely
unknown case needs the AI itself to discover what counts as an opposite need,
which `graph.py`'s fixed Literal cannot express.

This module keeps everything that made the lean shape reliable (a fixed,
code-owned stage sequence; one call per stage with a small bounded retry;
prominent, structured rejection feedback) but makes three things pluggable
per task instead of hardcoded:

1. The stage/schema/parent tables (`stages`, `schemas`, `parents`) -- so a
   task can add stages (see `generic.py`'s extra `act` stage for real
   tool-collision, Rule 3 of dialectics_rules.md) without touching this file.
2. Structural checks beyond parent-reference matching (`structural_checks`,
   keyed by stage) -- e.g. quote-grounding rules specific to one task.
3. Semantic checks (`semantic_checks`, keyed by stage) -- an LLM judge call,
   on a SEPARATE provider from the actor, for the one thing schema validation
   cannot verify: whether a proposed "opposite" genuinely serves a different
   need, not the same need solved differently. This is the fix for the
   "opposite is human-pre-solved" limitation: the AI proposes it, a distinct
   judge checks it against the general Rule 5 criterion, with one bounded
   retry on rejection -- the same shape already proven today for schema
   rejections, just for a semantic property instead of a syntactic one.
"""
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from pydantic import BaseModel, ValidationError


class MoveRejected(ValueError):
    """A proposal cannot be admitted to the current graph."""


class BudgetExceeded(RuntimeError):
    """The finite proposal budget was exhausted."""


class Move(BaseModel):
    parents: list[str]


@dataclass(frozen=True)
class Node:
    id: str
    stage: str
    proposal: Move


# (proposal, graph) -> None; raise MoveRejected to reject.
StructuralCheck = Callable[[Move, "DialecticGraph"], None]
# (proposal, graph, judge_gateway) -> None; raise MoveRejected to reject.
SemanticCheck = Callable[[Move, "DialecticGraph", object], Awaitable[None]]


class DialecticGraph:
    """An append-only graph with a closed, code-chosen transition set."""

    def __init__(self, *, stages: tuple[str, ...], schemas: dict[str, type[Move]],
                 parents: dict[str, tuple[str, ...]], context: dict):
        self.stages = stages
        self.schemas = schemas
        self.parents = parents
        self.context = context  # task-specific read-only data (message, baseline, ...)
        self.nodes: dict[str, Node] = {}
        self.terminal = False
        self.terminal_reason: str | None = None

    @property
    def allowed_move(self) -> Optional[str]:
        return None if self.terminal else self.stages[len(self.nodes)]

    @property
    def required_parents(self) -> list[str]:
        if self.allowed_move is None:
            return []
        return [self.nodes[stage].id for stage in self.parents[self.allowed_move]]

    def accept(self, proposal: Move, *, structural_checks: dict[str, StructuralCheck]) -> Node:
        stage = self.allowed_move
        if stage is None or getattr(proposal, "move", None) != stage:
            raise MoveRejected("illegal_move")
        proposal = self.schemas[stage].model_validate(proposal.model_dump())
        if proposal.parents != self.required_parents:
            raise MoveRejected("invalid_parent_references")
        check = structural_checks.get(stage)
        if check:
            check(proposal, self)
        node = Node(id=f"n{len(self.nodes) + 1}", stage=stage,
                    proposal=proposal.model_copy(deep=True))
        self.nodes[stage] = node
        return node

    def mark_terminal(self, reason: str):
        self.terminal = True
        self.terminal_reason = reason

    def snapshot(self) -> list[dict]:
        return [dict(id=node.id, stage=node.stage,
                     proposal=node.proposal.model_dump(mode="json"))
                for node in self.nodes.values()]


class LeanRuntime:
    def __init__(self, *, stages: tuple[str, ...], schemas: dict[str, type[Move]],
                 parents: dict[str, tuple[str, ...]],
                 instructions: dict[str, str], common_instructions: str,
                 structural_checks: Optional[dict[str, StructuralCheck]] = None,
                 semantic_checks: Optional[dict[str, SemanticCheck]] = None,
                 judge_gateway: Optional[object] = None,
                 post_accept: Optional[dict[str, Callable[[Node, DialecticGraph], Awaitable[None]]]] = None,
                 is_terminal: Optional[Callable[[DialecticGraph, str, Move], tuple[bool, str] | None]] = None,
                 max_calls: int = 12, max_revisions: int = 1):
        if max_calls < 1 or max_revisions not in (0, 1, 2):
            raise ValueError("Invalid bounded runtime configuration")
        self.stages = stages
        self.schemas = schemas
        self.parents = parents
        self.instructions = instructions
        self.common_instructions = common_instructions
        self.structural_checks = structural_checks or {}
        self.semantic_checks = semantic_checks or {}
        self.judge_gateway = judge_gateway
        # Runs AFTER a node is structurally+semantically accepted, e.g. to actually
        # execute a tool call for an "act" stage and attach its real result to
        # graph.context for the next stage to see -- this is what makes a leap's
        # realization empirical (dialectics_rules.md Rule 3) instead of a second
        # self-review of the same unexecuted plan.
        self.post_accept = post_accept or {}
        self.is_terminal = is_terminal
        self.max_calls = max_calls
        self.max_revisions = max_revisions

    async def run(self, gateway, log, *, context: dict) -> DialecticGraph:
        graph = DialecticGraph(stages=self.stages, schemas=self.schemas,
                                parents=self.parents, context=context)
        calls = 0
        while not graph.terminal:
            stage = graph.allowed_move
            if stage is None:
                break
            feedback = None
            for revision in range(self.max_revisions + 1):
                if calls >= self.max_calls:
                    graph.mark_terminal("budget_exceeded")
                    log.emit("lean_budget_exceeded", calls=calls, stage=stage)
                    return graph
                calls += 1
                payload = dict(
                    context=context, accepted_nodes=graph.snapshot(), allowed_move=stage,
                    required_parents=graph.required_parents, rejection=feedback,
                )
                log.emit("lean_move_requested", stage=stage, call=calls, revision=revision)
                try:
                    proposal = await gateway.generate(
                        self.common_instructions + "\n" + self.instructions[stage],
                        payload, self.schemas[stage], stage=f"lean_{stage}",
                    )
                    node = graph.accept(proposal, structural_checks=self.structural_checks)
                    semantic_check = self.semantic_checks.get(stage)
                    if semantic_check:
                        if self.judge_gateway is None:
                            raise RuntimeError(f"semantic_checks[{stage!r}] configured without judge_gateway")
                        await semantic_check(node.proposal, graph, self.judge_gateway)
                    post = self.post_accept.get(stage)
                    if post:
                        await post(node, graph)
                except (MoveRejected, ValidationError) as exc:
                    if isinstance(exc, MoveRejected):
                        feedback = str(exc)
                    else:
                        details = []
                        for err in exc.errors():
                            loc = ".".join(str(p) for p in err["loc"])
                            msg = err["msg"].split(" [")[0]
                            details.append(f"{loc}: {msg}")
                        feedback = "invalid_schema: " + "; ".join(details[:5])
                    # A semantic rejection means graph.accept() already inserted the
                    # node before the judge ran; retract it so the stage is retried,
                    # not silently treated as committed.
                    graph.nodes.pop(stage, None)
                    log.emit("lean_move_rejected", stage=stage, call=calls, reason=feedback)
                    if revision >= self.max_revisions:
                        graph.mark_terminal("max_revisions_exceeded")
                        log.emit("lean_inconclusive", stage=stage, calls=calls)
                        return graph
                else:
                    log.emit("lean_move_accepted", node_id=node.id, stage=stage,
                             proposal=node.proposal.model_dump(mode="json"))
                    if self.is_terminal:
                        result = self.is_terminal(graph, stage, node.proposal)
                        if result and result[0]:
                            graph.mark_terminal(result[1])
                    if stage == self.stages[-1]:
                        graph.mark_terminal("sequence_complete")
                    break
        log.emit("lean_result", calls=calls, terminal_reason=graph.terminal_reason,
                 nodes=graph.snapshot())
        return graph
