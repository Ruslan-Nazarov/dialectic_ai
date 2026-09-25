"""The world of a domain (architecture section 3): processes as transitions, bundles with iterations,
opposite, contradiction, resolution, and the revisions that produced this version."""
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["p0", "developing", "internal", "contradiction", "resolution"]
BundleName = Literal["p0", "opposite", "contradiction"]


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:6]}"


class Process(BaseModel):
    """Always a transition of one process into another (A 1.1)."""
    id: str
    source: str                           # "from" -- the process that passes over
    target: str                           # "to" -- the process it passes into
    statement: str
    role: Role
    bundle: Optional[BundleName] = None
    iteration: int = 0
    derived_from: list[str] = Field(default_factory=list)   # A 4.2, 4.3
    parent_id: Optional[str] = None                         # internal -> its developing process (A 4.5)
    links_prev: list[str] = Field(default_factory=list)     # internal -> same P's internals on the last iteration
    status: Literal["active", "retired"] = "active"

    def line(self) -> str:
        return f"[{self.id}] {self.source} → {self.target}: {self.statement}"


class Comparison(BaseModel):
    """A 4.7, plus what the model decides from it: the opposite (A 4.8) and the next iteration (A 4.6)."""
    vs_root: str = ""
    among: str = ""
    internals: str = ""
    opposite_id: Optional[str] = None
    why_not_required: str = ""
    sufficient: bool = False
    next_variant: Optional[Literal[1, 2, 3]] = None
    next_changes: str = ""
    retire: list[str] = Field(default_factory=list)
    promote: list[str] = Field(default_factory=list)     # internal processes that become developing ones
    redo_internals: list[str] = Field(default_factory=list)


class Iteration(BaseModel):
    n: int
    variant: Optional[int] = None
    developing: list[str] = Field(default_factory=list)
    internal: dict[str, list[str]] = Field(default_factory=dict)
    comparison: Optional[Comparison] = None


class Bundle(BaseModel):
    root_id: str
    iterations: list[Iteration] = Field(default_factory=list)


class P0Record(BaseModel):
    process_id: str
    from_leap: str = ""        # which contradiction's resolution P0 is (A 3.1(1)); the engine does not check it
    attempt: int = 1


class Opposite(BaseModel):
    process_id: str
    why_not_required: str       # A 5.1


class Contradiction(BaseModel):
    process_id: str
    unity: str


class Resolution(BaseModel):
    process_id: str
    kind: Literal["replacement", "mediation"]
    explanation: str


class Revision(BaseModel):
    at: str
    trigger: str
    affected: list[str]
    bundle: BundleName
    summary: str = ""


class World(BaseModel):
    id: str = Field(default_factory=lambda: new_id("w"))
    domain: str
    version: int = 1
    parent_version: Optional[int] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processes: dict[str, Process] = Field(default_factory=dict)
    p0: Optional[P0Record] = None
    rejected_p0: list[dict] = Field(default_factory=list)
    bundles: dict[str, Bundle] = Field(default_factory=dict)
    opposite: Optional[Opposite] = None
    contradiction: Optional[Contradiction] = None
    resolution: Optional[Resolution] = None
    revisions: list[Revision] = Field(default_factory=list)
    status: Literal["building", "built", "no_opposite", "failed"] = "building"

    def add(self, process: Process) -> Process:
        self.processes[process.id] = process
        return process

    def get(self, pid: str) -> Process:
        return self.processes[pid]

    def last_iteration(self, bundle: str) -> Optional[Iteration]:
        b = self.bundles.get(bundle)
        return b.iterations[-1] if b and b.iterations else None

    def active_developing(self, bundle: str) -> list[Process]:
        it = self.last_iteration(bundle)
        return [self.processes[pid] for pid in (it.developing if it else [])]

    def all_developing(self, bundle: str) -> list[Process]:
        """Every developing process of the bundle across iterations, in order (A 4.2: the next one flows
        from these)."""
        return [p for p in self.processes.values() if p.bundle == bundle and p.role == "developing"]
