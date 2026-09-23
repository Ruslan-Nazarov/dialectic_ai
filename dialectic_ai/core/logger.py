"""
dialectic_ai/core/logger.py

DIALECTICAL DESCRIPTION:
  Origin: According to Rule 4 (Development Memory), the process of creating an agent
    must have its own continuous memory from the very first step.
  Contradiction: Without a logger, the framework itself violates its own rules —
    it requires memory from the agent, but does not maintain any itself.
  How it resolves: Automatically logs every architectural step and every
    engine call in development_log.md. The developer should not do this manually.
  What it leads to: The Observability layer (tracing, dashboard) is built on top of these
    logs. The CLI command `dialectic map` reads them and builds a dialectical map.
  Its own contradictions: The logger writes to a file — this is an I/O operation in the critical
    path. Under high load, it creates a bottleneck. An async variant is needed.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from dialectic_ai.core.dialectical import dialectical
from typing import Optional


@dialectical(
    origin="Rule 4 of our dialectics_rules.md: development must have its own memory",
    contradiction="The framework requires memory from agents, but does not maintain any memory itself. "
                  "The contradiction violates the integrity of the system",
    resolves="Automatically logs every architectural event in a structured log. "
             "The developer is freed from manual record-keeping",
    generates="Observability layer: tracer and dashboard read these logs and visualize the agent's history",
    own_contradictions="Synchronous writing to a file creates an I/O bottleneck. "
                       "The growing log requires a rotation strategy. An async variant is needed for production",
    layer=0,
)
class DevelopmentLogger:
    """
    Automatic logger for the development process and framework operation.
    Implements Rule 4: Development Memory.
    """

    def __init__(self, log_path: str = "development_log.md", trace_path: str = "trace.jsonl"):
        self.log_path = Path(log_path)
        self.trace_path = Path(trace_path)

    async def log_step(self, step_name: str, description: str, layer: Optional[int] = None) -> None:
        """Logs an architectural step in development_log.md."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        layer_info = f" (Layer {layer})" if layer is not None else ""
        entry = f"\n## {step_name}{layer_info} — {timestamp}\n{description}\n"
        def _write():
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        await asyncio.to_thread(_write)

    async def trace_event(self, event_type: str, data: dict) -> None:
        """
        Logs an engine event in trace.jsonl for the Observability layer.
        Each line is a valid JSON object (JSON Lines format).
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **data,
        }
        def _write():
            with open(self.trace_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        await asyncio.to_thread(_write)

    async def log_collision(self, tool_name: str, success: bool, output: str, session_id: Optional[str] = None) -> None:
        """Logs the result of a collision with reality (Rule 2)."""
        data = {
            "tool": tool_name,
            "success": success,
            "output": output[:500],  # Trimming long outputs
        }
        if session_id:
            data["session_id"] = session_id
        await self.trace_event("collision", data)

    def log_dialectical_map(self) -> None:
        """
        Outputs the dialectical map of all registered components.
        Called by the `dialectic map` command from the CLI.
        """
        from dialectic_ai.core.dialectical import get_dialectical_map
        components = get_dialectical_map()
        print(f"\n{'='*60}")
        print(f"  DIALECTICAL MAP OF THE FRAMEWORK ({len(components)} components)")
        print(f"{'='*60}")
        for meta in components:
            print(f"\n  [Layer {meta.layer}] {meta.name}")
            print(f"    ➡ Generates: {meta.generates[:80]}...")
        print(f"\n{'='*60}\n")

