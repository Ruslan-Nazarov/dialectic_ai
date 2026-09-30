"""The world of a domain, rebuilt on prompt_1..6 (see PROMPTS_SNAPSHOT_PRE_REWRITE.md for the scheme
this replaced). Flatter than the previous version: only P0 gets its own multi-iteration development;
the opposite and the contradiction are single processes, not developed through their own bundles.
There is no "internal process" layer and no three-variant next-iteration mechanic -- prompt_1..6 do
not describe either, so neither exists here."""
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["p0", "developing", "opposite", "contradiction", "resolution"]


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:6]}"


class Process(BaseModel):
    """A process statement; prompt_2 development nodes do not have explicit endpoints."""
    id: str
    source: str                           # "from" -- the process that passes over
    target: str                           # "to" -- the process it passes into
    statement: str
    role: Role
    iteration: int = 0                    # >=1 for a developing process; 0 otherwise
    derived_from: list[str] = Field(default_factory=list)   # P0 + this iteration's processes so far,
    # + (if the process rests on the whole previous iteration) every process of that iteration
    status: Literal["active", "superseded"] = "active"

    def line(self) -> str:
        if self.source or self.target:
            return f"[{self.id}] {self.source} → {self.target}: {self.statement}"
        return f"[{self.id}] {self.statement}"


class IterationRecord(BaseModel):
    """One prompt_2 call: a finite disclosure of P0 through developing processes (prompt_2 section 9)."""
    n: int
    based_on_iteration: Optional[int] = None       # null for n=1; n-1 for n>1
    developing: list[str] = Field(default_factory=list)
    p0_revealed_content: str = ""
    iteration_practical_integrity: str = ""
    raw: dict = Field(default_factory=dict)   # prompt_2's full JSON reply, re-fed as {{previous_iteration}}


class ComparisonRecord(BaseModel):
    """One prompt_3 call: analysis of the accumulated development so far, cumulative over iterations."""
    iterations_analyzed: list[int] = Field(default_factory=list)
    opposition_candidates: list[dict] = Field(default_factory=list)   # prompt_3's own shape, kept as-is
    overall_development_pattern: str = ""
    raw: dict = Field(default_factory=dict)


class OppositionCheck(BaseModel):
    """One prompt_4 call: verification of the candidates prompt_3 flagged."""
    candidate_checks: list[dict] = Field(default_factory=list)
    confirmed_opposites: list[dict] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)


class Contradiction(BaseModel):
    """prompt_5's result for the confirmed opposite the engine acted on."""
    process_id: str
    unity: str
    raw: dict = Field(default_factory=dict)


class Resolution(BaseModel):
    """prompt_6's leap, when one was found."""
    process_id: str
    kind: Literal["replacement", "mediation"]
    explanation: str
    raw: dict = Field(default_factory=dict)


class Revision(BaseModel):
    at: str
    trigger: str
    affected: list[str]
    summary: str = ""


class World(BaseModel):
    schema_version: Literal[2] = 2
    id: str = Field(default_factory=lambda: new_id("w"))
    domain: str
    version: int = 1
    parent_version: Optional[int] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processes: dict[str, Process] = Field(default_factory=dict)
    p0: Optional[Process] = None
    p0_explanation: dict = Field(default_factory=dict)   # practical_link/why_initial/resolution_trace/development_potential
    rejected_p0: list[dict] = Field(default_factory=list)
    iterations: list[IterationRecord] = Field(default_factory=list)
    comparisons: list[ComparisonRecord] = Field(default_factory=list)
    opposition_checks: list[OppositionCheck] = Field(default_factory=list)
    opposite: Optional[Process] = None
    opposite_explanation: dict = Field(default_factory=dict)   # the confirmed_opposites entry prompt_4 gave for it
    contradiction: Optional[Contradiction] = None
    resolution: Optional[Resolution] = None
    revisions: list[Revision] = Field(default_factory=list)
    status: Literal["building", "built", "no_opposite", "no_p0", "mediated", "leap_not_found", "failed"] = "building"

    def add(self, process: Process) -> Process:
        self.processes[process.id] = process
        return process

    def get(self, pid: str) -> Process:
        return self.processes[pid]

    def last_iteration(self) -> Optional[IterationRecord]:
        return self.iterations[-1] if self.iterations else None

    def all_developing(self) -> list[Process]:
        """Every developing process of P0's development, across iterations, in order."""
        return [p for p in self.processes.values() if p.role == "developing"]
