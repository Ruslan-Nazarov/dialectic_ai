"""
dialectic_ai/memory/persistent.py

DIALECTICAL DESCRIPTION:
  Origin: KnowledgeGraph lives in RAM. Upon restarting the program,
    all accumulated knowledge about the student is erased.
  Contradiction: The agent claims to "teach" the user, but with each
    new launch, it starts the acquaintance anew. A fictitious memory.
  How it resolves: Wraps any BaseMemory (for example, KnowledgeGraphMemory)
    and automatically saves its state to a JSON file on disk with each
    update. Upon creation, it restores from the file.
  What it leads to: The agent can conduct long-term sessions across restarts.
    This is the foundation for future integration with a database (SQLite, Redis).
  Own contradictions: Synchronous disk writing on each update —
    slow. Competition for the file during parallel sessions. No schema migrations.
"""
import json
from pathlib import Path

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import AgentInput, MemoryUpdate
from dialectic_ai.memory.base import BaseMemory
from dialectic_ai.memory.knowledge_graph import KnowledgeGraphMemory


@dialectical(
    origin="KnowledgeGraphMemory lives in RAM and dies upon restart. Knowledge about the user is lost",
    contradiction="The agent calls itself 'educational', but forgets the user upon each restart",
    resolves="Decorator pattern: wraps any memory and adds persistence through a JSON file "
             "without changing the BaseMemory interface",
    generates="Long-term agent sessions. The basis for migration to a full database in the future",
    own_contradictions="Synchronous I/O on each update. No atomicity — on failure during writing "
                       "the file may become corrupted. No schema versioning",
    layer=1,
)
class PersistentMemory(BaseMemory):
    """
    A decorator wrapper that adds persistence to any BaseMemory.
    By default, it wraps KnowledgeGraphMemory.
    """

    def __init__(self, inner: BaseMemory = None, path: str = "memory_state.json"):
        self.inner = inner or KnowledgeGraphMemory()
        self.path = Path(path)
        self._load()

    def _load(self) -> None:
        """Restores state from the file upon initialization."""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(self.inner, KnowledgeGraphMemory):
                    self.inner.graph = data.get("graph", {})
                    print(f"[PersistentMemory] Loaded {len(self.inner.graph)} concepts from {self.path}")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[PersistentMemory] Load error: {e}. Starting with a clean memory.")

    def _save(self) -> None:
        """Saves the current state to disk."""
        if isinstance(self.inner, KnowledgeGraphMemory):
            data = {"graph": self.inner.graph}
        else:
            data = {"context": self.inner.get_context()}
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def process_turn(self, user_input: AgentInput, parsed_response: dict) -> None:
        self.inner.process_turn(user_input, parsed_response)
        self._save()

    def update(self, updates: list[MemoryUpdate]) -> None:
        self.inner.update(updates)
        self._save()

    def get_context(self) -> str:
        return self.inner.get_context()

    def clear(self) -> None:
        self.inner.clear()
        if self.path.exists():
            self.path.unlink()
