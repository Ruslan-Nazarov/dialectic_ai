from typing import Dict, List, Optional
from dialectic_ai.v1.models import Evidence

class EvidenceStore:
    def __init__(self):
        self._evidence: Dict[str, Evidence] = {}

    def add(self, evidence: Evidence):
        self._evidence[evidence.id] = evidence

    def get(self, evidence_id: str) -> Optional[Evidence]:
        return self._evidence.get(evidence_id)

    def get_all(self) -> List[Evidence]:
        return list(self._evidence.values())
