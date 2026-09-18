"""dialectic_ai/integrations/gigachat/__init__.py

GigaChat is the most reliable real provider in this project's own testing
(see HANDOFF.md, ARCHITECTURE.md §4c). Exposing it at the package level so
callers can use:
    from dialectic_ai.integrations.gigachat import GigaChatLLM
instead of reaching into the submodule directly.
"""
from dialectic_ai.integrations.gigachat.llm import GigaChatLLM

__all__ = ["GigaChatLLM"]
