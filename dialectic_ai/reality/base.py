"""
dialectic_ai/reality/base.py

Here is an alias RealityCheck for backward compatibility.
In the new architecture, use dialectic_ai.core.tool.Tool.
"""
from dialectic_ai.core.tool import Tool as RealityCheck  # noqa: F401 — public re-export

__all__ = ["RealityCheck"]
