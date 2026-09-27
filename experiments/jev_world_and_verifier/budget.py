"""Shared spend tracker across full_run_exp1.py and full_run_exp2.py, so the $3.50 cap
(PREREGISTRATION.md, user's full-run confirmation) applies to the combined full run, not
$3.50 per script. Both scripts run sequentially (exp2 first, cheap; exp1 second, the bulk of
the cost), so a plain JSON file read-modify-write is enough -- no cross-process lock needed,
only the in-process thread lock each script already keeps for its own concurrent workers.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent / "full_run_budget.json"
_lock = threading.Lock()


def load_spent() -> float:
    if not STATE_FILE.exists():
        return 0.0
    return json.loads(STATE_FILE.read_text(encoding="utf-8")).get("total_usd", 0.0)


def add_spent(amount_usd: float) -> float:
    """Adds `amount_usd` to the persisted total and returns the new total. Thread-safe within
    one process; scripts are run one after another, not concurrently with each other."""
    with _lock:
        total = load_spent() + amount_usd
        STATE_FILE.write_text(json.dumps({"total_usd": total}), encoding="utf-8")
        return total
