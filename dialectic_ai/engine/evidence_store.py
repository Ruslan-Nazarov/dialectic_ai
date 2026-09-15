from typing import Optional
from dialectic_ai.core.schema import Evidence
from dialectic_ai.core.dialectical import dialectical

@dialectical(
    origin="Evidence was just a flat list inside the run() function, making it hard to manage and query.",
    contradiction="If Evidence is kept globally or in the agent, it leaks across runs. If it's just a list, it lacks structured lookup.",
    resolves="EvidenceStore is explicitly scoped to a single run, providing O(1) lookup and referential integrity guarantees.",
    generates="A clean API for Evidence validation without touching global state.",
    own_contradictions="Requires passing the store around within the run context.",
    layer=3,
)
class EvidenceStore:
    """Run-scoped storage for Evidence."""
    def __init__(self):
        self._store: dict[str, Evidence] = {}
        self._executed_actions: set = set()

    def add(self, evidence: Evidence) -> None:
        self._store[evidence.id] = evidence

    def get(self, evidence_id: str) -> Optional[Evidence]:
        return self._store.get(evidence_id)

    def exists(self, evidence_id: str) -> bool:
        return evidence_id in self._store

    def ids(self) -> list[str]:
        return list(self._store.keys())

    def all(self) -> list[Evidence]:
        return list(self._store.values())
