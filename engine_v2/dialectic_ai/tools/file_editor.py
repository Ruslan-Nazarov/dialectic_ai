"""File tools confined to an explicitly configured workspace."""
import os
from pathlib import Path
from dialectic_ai.core.decorators import dialectical_tool


def workspace_path(path: str) -> Path:
    root = Path(os.getenv("DIALECTIC_WORKSPACE", "agent_workspace")).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Path escapes DIALECTIC_WORKSPACE")
    if any(part.startswith(".") for part in target.relative_to(root).parts):
        raise ValueError("Hidden configuration files are outside the file tool contract")
    return target


@dialectical_tool(origin="Agent needs artifacts", contradiction="Text alone cannot access artifacts",
                  resolves="Read a file within the configured workspace")
def read_file(path: str) -> str:
    """Read a UTF-8 file relative to DIALECTIC_WORKSPACE (default agent_workspace)."""
    return workspace_path(path).read_text(encoding="utf-8")


@dialectical_tool(origin="Agent needs artifacts", contradiction="Text alone cannot persist artifacts",
                  resolves="Write a file within the configured workspace")
def write_file(path: str, content: str) -> str:
    """Write a UTF-8 file relative to DIALECTIC_WORKSPACE (default agent_workspace)."""
    target = workspace_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Saved {path}"
