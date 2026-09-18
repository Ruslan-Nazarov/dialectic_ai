"""
dialectic_ai/memory/knowledge_graph.py

DIALECTICAL DESCRIPTION:
  Origin: From the example of the Tutor, we understood: a simple message history
    (buffer) does not allow separating "what the student knows" from "what we talked about".
  Contradiction: The buffer grows linearly and clogs the LLM's context window. The agent
    drowns in the details of the conversation instead of remembering the essence.
  How it resolves: It stores not a history of words, but a graph of CONCEPTS and their statuses
    (learned/struggling). The context for the LLM is a compact structured
    knowledge map, not a long sheet of dialogue.
  What it leads to: PromptBuilder embeds the graph into the prompt. The visualization of the graph
    becomes a central element of the Observability dashboard (Layer 5).
  Its own contradictions: The graph needs to be updated — this means that the LLM must
    correctly classify concepts. If the LLM makes mistakes in classification,
    the graph accumulates incorrect data (garbage in, garbage out).
"""
import json
from pathlib import Path

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import AgentInput, MemoryUpdate
from dialectic_ai.memory.base import BaseMemory


@dialectical(
    origin="The Tutor forgot the student's progress between replies. The chat history grew and overflowed the context",
    contradiction="The buffer stores words, not knowledge. The agent cannot answer 'what exactly did the student understand'",
    resolves="Stores a dictionary of concepts with their statuses. Compact, semantically rich, easily readable by LLM",
    generates="A basis for Observability: the graph can be visualized, progress reports can be built, "
              "used to adapt the difficulty of the material",
    own_contradictions="Depends on the accuracy of LLM classification. The graph does not store temporal dynamics "
                       "(when exactly the concept was mastered). Persistence requires a separate module",
    layer=1,
)
class KnowledgeGraphMemory(BaseMemory):
    """
    The agent's memory in the form of a graph of concepts and their statuses.
    Optimal for educational agents.
    """

    VALID_STATUSES = {"learned", "struggling", "unknown", "introduced"}

    def __init__(self, initial_graph: dict[str, str] = None, storage_path: str = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self.graph: dict[str, str] = dict(initial_graph or {})
        if self.storage_path and self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.graph.update(data)
            except Exception:
                pass

    def process_turn(self, user_input: AgentInput, parsed_response: dict) -> None:
        updates = [
            MemoryUpdate(
                concept=u.get("concept", ""),
                status=u.get("status", "unknown"),
            )
            for u in parsed_response.get("knowledge_updates", [])
            if u.get("concept")
        ]
        self.update(updates)

    def update(self, updates: list[MemoryUpdate]) -> None:
        for item in updates:
            if item.status not in self.VALID_STATUSES:
                print(f"[Memory] Warning: unknown status '{item.status}' for '{item.concept}'")
                continue
            self.graph[item.concept] = item.status
            print(f"[Memory] Updated: '{item.concept}' → {item.status}")

        if self.storage_path:
            try:
                self.storage_path.write_text(json.dumps(self.graph, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

    def get_context(self) -> str:
        if not self.graph:
            return "The knowledge graph is empty — this is the first contact with the user."
        lines = ["Current knowledge graph of the user:"]
        for concept, status in self.graph.items():
            emoji = {"learned": "[OK]", "struggling": "[!]", "unknown": "[?]", "introduced": "[i]"}.get(status, "-")
            lines.append(f"  {emoji} {concept}: {status}")
        return "\n".join(lines)

    def get_graph(self) -> dict[str, str]:
        """Returns the graph for visualization in the dashboard."""
        return dict(self.graph)

    def clear(self) -> None:
        self.graph.clear()
