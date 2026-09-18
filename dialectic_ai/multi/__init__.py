"""dialectic_ai/multi/__init__.py"""
from dialectic_ai.multi.debate import DialecticalDebateEngine
from dialectic_ai.multi.protocol import AgentMessage, AgentResult
from dialectic_ai.multi.router import AgentRouter
from dialectic_ai.multi.triad import DialecticalTriad

__all__ = [
    "AgentMessage",
    "AgentResult",
    "AgentRouter",
    "DialecticalTriad",
    "DialecticalDebateEngine",
]
