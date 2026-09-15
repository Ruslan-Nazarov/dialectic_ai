"""
dialectic_ai/observability/tracer.py

DIALECTICAL DESCRIPTION:
  Origin: The Engine logs events in trace.jsonl (DevelopmentLogger).
    But the data in the file is unstructured strings. No one reads them.
  Contradiction: Logs exist, but are not accessible for analysis. The dashboard cannot
    work with raw JSONL directly in the browser.
  How it resolves: TraceReader reads trace.jsonl, deserializes events into Python
    objects, and provides a convenient API: get_all(), get_by_session(),
    get_knowledge_graph(). The dashboard receives ready data.
  What it leads to: The Dashboard server (server.py) calls TraceReader and sends
    data to the browser via REST API. The Evaluator analyzes patterns in the traces.
  Own contradictions: Reads the entire file each time a request is made.
    With large logs — slow. Indexing or streaming is needed.
"""
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from dialectic_ai.core.dialectical import dialectical


@dataclass
class TraceEvent:
    timestamp: str
    event_type: str
    data: dict

    @property
    def session_id(self) -> Optional[str]:
        return self.data.get("session_id")

    @property
    def iteration(self) -> Optional[int]:
        return self.data.get("iteration")


@dialectical(
    origin="The Engine logs events in trace.jsonl (DevelopmentLogger). But raw JSONL is unstructured.",
    contradiction="Logs exist, but are not accessible for convenient analysis and visualization in the UI.",
    resolves="TraceReader deserializes events into typed TraceEvent and provides a summary API.",
    generates="The Dashboard server (server.py) and AgentEvaluator receive structured data.",
    own_contradictions="Synchronous reading of the entire file for each request; indexing is needed for large traces.",
    layer=5,
)
class TraceReader:
    """Reads and analyzes trace.jsonl for the Observability dashboard."""

    def __init__(self, trace_path: str = "trace.jsonl", memory_path: str = "memory_state.json"):
        self.trace_path = Path(trace_path)
        self.memory_path = Path(memory_path)

    def get_all(self) -> list[TraceEvent]:
        """Reads all events from trace.jsonl."""
        if not self.trace_path.exists():
            return []
        events = []
        current_session = None
        with open(self.trace_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    session = raw.get("session_id") or current_session
                    if raw.get("event_type") == "engine_start" and raw.get("session_id"):
                        current_session = raw.get("session_id")
                        session = current_session

                    data = {k: v for k, v in raw.items() if k not in ("timestamp", "event_type")}
                    if session and "session_id" not in data:
                        data["session_id"] = session

                    events.append(TraceEvent(
                        timestamp=raw.get("timestamp", ""),
                        event_type=raw.get("event_type", "unknown"),
                        data=data,
                    ))
                except json.JSONDecodeError:
                    continue
        return events

    def get_by_session(self, session_id: str) -> list[TraceEvent]:
        """Filters events by session_id."""
        return [e for e in self.get_all() if e.session_id == session_id]

    def get_knowledge_graph(self) -> dict[str, str]:
        """
        Restores the current knowledge graph from the memory file, if it exists.

        Only correct for a PersistentMemory(KnowledgeGraphMemory()) agent writing
        to `self.memory_path` (the default "memory_state.json") -- an agent using
        SQLiteKnowledgeGraphMemory, or PersistentMemory with a custom storage_path,
        writes elsewhere and this will silently return {} for it unless constructed
        with a matching `memory_path`. See CODE_REVIEW.md, Layer 5.
        """
        if self.memory_path.exists():
            try:
                data = json.loads(self.memory_path.read_text(encoding="utf-8"))
                return data.get("graph", {})
            except Exception:
                pass
        return {}

    def get_summary(self) -> dict:
        """Returns summary statistics for the dashboard."""
        events = self.get_all()
        return {
            "total_events": len(events),
            "collisions": sum(1 for e in events if e.event_type == "collision"),
            "syntheses": sum(1 for e in events if e.event_type == "synthesize"),
            "parse_errors": sum(1 for e in events if e.event_type == "parse_error"),
            "events": [
                {"timestamp": e.timestamp, "type": e.event_type, **e.data}
                for e in events[-50:]  # last 50 events for UI
            ],
        }
