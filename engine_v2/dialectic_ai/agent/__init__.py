"""dialectic_ai/agent/__init__.py"""
from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.agent.prompt_builder import build_system_prompt

__all__ = ["DialecticalAgent", "build_system_prompt"]

