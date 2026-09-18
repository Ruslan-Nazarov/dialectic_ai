"""
Neutral event model and logger for the benchmark.
Records strictly Observed events during execution, with no subjective scoring.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Optional


@dataclass
class BenchmarkEvent:
    """Represents a single strictly observed event during framework execution."""
    event_type: str  # e.g., 'run_start', 'llm_call', 'agent_start', 'tool_call', 'tool_result', 'evidence_created', 'claim_created', 'validation', 'handoff', 'error', 'run_end'
    framework: str   # 'dialectic_ai' or 'openai_agents_sdk'
    run_id: str
    case_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent: Optional[str] = None
    phase: Optional[str] = None
    tool: Optional[str] = None
    arguments: Optional[dict[str, Any]] = None
    result: Optional[Any] = None
    evidence_id: Optional[str] = None
    claim: Optional[str] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BenchmarkEventLogger:
    """In-memory event sink with JSON serialization for benchmark runs."""
    def __init__(self, run_id: str, framework: str, case_id: str):
        self.run_id = run_id
        self.framework = framework
        self.case_id = case_id
        self.events: list[BenchmarkEvent] = []

    def record(
        self,
        event_type: str,
        agent: Optional[str] = None,
        phase: Optional[str] = None,
        tool: Optional[str] = None,
        arguments: Optional[dict[str, Any]] = None,
        result: Optional[Any] = None,
        evidence_id: Optional[str] = None,
        claim: Optional[str] = None,
        success: Optional[bool] = None,
        error: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> BenchmarkEvent:
        """Records an observed event."""
        event = BenchmarkEvent(
            event_type=event_type,
            framework=self.framework,
            run_id=self.run_id,
            case_id=self.case_id,
            agent=agent,
            phase=phase,
            tool=tool,
            arguments=arguments,
            result=result,
            evidence_id=evidence_id,
            claim=claim,
            success=success,
            error=error,
            metadata=metadata or {},
        )
        self.events.append(event)
        return event

    def filter(self, event_type: str) -> list[BenchmarkEvent]:
        """Returns all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def count(self, event_type: str) -> int:
        """Returns the number of events of a specific type."""
        return len(self.filter(event_type))

    def export_json(self, output_path: str | Path) -> None:
        """Saves all recorded events to a structured JSON file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        serializable = [asdict(e) for e in self.events]
        path.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")
