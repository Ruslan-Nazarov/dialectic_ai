"""A jsonl trace: one line per block call (architecture section 8)."""
import json
from datetime import datetime, timezone
from pathlib import Path


class Trace:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.events: list[dict] = []

    def event(self, kind: str, **fields) -> None:
        record = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind, **fields}
        self.events.append(record)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
