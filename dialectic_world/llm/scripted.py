"""A model for tests: answers each prompt with whatever a Python function returns for it."""
import json
from typing import Callable

from dialectic_world.llm.base import LLM


class ScriptedLLM(LLM):
    def __init__(self, respond: Callable[[str], object]):
        super().__init__(model="scripted")
        self.respond = respond
        self.prompts: list[str] = []

    async def _complete(self, messages):
        prompt = "\n\n".join(m["content"] for m in messages)
        self.prompts.append(prompt)
        answer = self.respond(prompt)
        text = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
        return text, len(prompt) // 4, len(text) // 4
