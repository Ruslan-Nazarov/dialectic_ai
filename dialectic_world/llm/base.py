"""The one thing the engine needs from a model: text in, text out, tokens counted."""
from dataclasses import dataclass, field
from contextvars import ContextVar


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, prompt: int, completion: int) -> None:
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion


@dataclass
class LLM:
    """Base class. Subclasses implement `_complete`; `generate` counts usage."""
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    _call_usage: ContextVar = field(default_factory=lambda: ContextVar("llm_call_usage", default=(0, 0)),
                                    repr=False)

    @property
    def last_call_usage(self) -> tuple[int, int]:
        """Usage of this task's latest call; unaffected by concurrent calls."""
        return self._call_usage.get()

    async def generate(self, messages: list[dict]) -> str:
        text, prompt_tokens, completion_tokens = await self._complete(messages)
        self.usage.add(prompt_tokens, completion_tokens)
        self._call_usage.set((prompt_tokens, completion_tokens))
        return text or ""

    async def _complete(self, messages: list[dict]) -> tuple[str, int, int]:
        raise NotImplementedError


class FallbackLLM(LLM):
    """Tries each model in turn; an exception or an empty reply moves on to the next."""

    def __init__(self, chain: list[LLM]):
        super().__init__(model="+".join(m.model for m in chain))
        self.chain = chain

    async def generate(self, messages: list[dict]) -> str:
        errors = []
        tokens = [0, 0]
        for llm in self.chain:
            try:
                text = await llm.generate(messages)
                prompt, completion = llm.last_call_usage
                self.usage.add(prompt, completion)
                tokens[0] += prompt
                tokens[1] += completion
                self._call_usage.set(tuple(tokens))
                if text.strip():
                    return text
                errors.append(f"{llm.model}: empty reply")
            except Exception as exc:  # noqa: BLE001 -- any failure falls through to the next model
                errors.append(f"{llm.model}: {type(exc).__name__}: {exc}"[:300])
        raise RuntimeError("all models failed: " + " | ".join(errors))
