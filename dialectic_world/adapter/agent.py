"""A session of an agent in a world, and a small reference agent for tests and experiments.

Any other agent can be used instead: put `WorldAdapter.system_prompt()` into its context, read its mark
with `WorldAdapter.parse_world_fit()` and hand it to `WorldSession.observe()`."""
import json
from dataclasses import dataclass, field
from typing import Optional

from dialectic_world.adapter.adapter import WorldAdapter, WorldFit
from dialectic_world.adapter.revise import revise_world
from dialectic_world.builder.blocks import Context, FormError, Tool, extract_json
from dialectic_world.llm.base import LLM
from dialectic_world.world.model import World
from dialectic_world.world.store import WorldStore


class WorldSession:
    """Holds the current world version and revises it when the agent's data does not fit
    (at most `revisions_per_session` times)."""

    def __init__(self, world: World, builder: Context, store: Optional[WorldStore] = None):
        self.world, self.builder, self.store = world, builder, store
        self.revisions = 0

    @property
    def adapter(self) -> WorldAdapter:
        return WorldAdapter(self.world, self.builder.settings.brief_max_chars)

    async def observe(self, fit: Optional[WorldFit], agent_data: str) -> bool:
        if fit is None or fit.fits:
            return False
        if self.revisions >= self.builder.settings.revisions_per_session:
            self.builder.trace.event("revision_skipped", reason="revisions_per_session reached", note=fit.note)
            return False
        new = await revise_world(self.builder, self.world, fit, agent_data, self.store)
        if new is None:
            return False
        if new.status != "built":
            # A revision that broke the world (e.g. no opposite any more) is kept on disk for inspection;
            # the agent goes on in the last whole version.
            self.builder.trace.event("revision_not_adopted", version=new.version, status=new.status)
            self.revisions += 1
            return False
        self.world, self.revisions = new, self.revisions + 1
        return True


@dataclass
class AgentResult:
    answer: str
    fit: Optional[WorldFit]
    steps: list[dict] = field(default_factory=list)
    revised: bool = False


AGENT_FORMAT = """Отвечай JSON. Чтобы вызвать инструмент: {"tool": "<имя>", "args": {...}}.
Чтобы ответить: {"answer": "...", "world_fit": {"fits": true, "process_ids": [], "note": ""}}."""


async def run_agent(llm: LLM, session: WorldSession, task: str, role: str = "",
                    tools: Optional[dict[str, tuple[str, Tool]]] = None, max_steps: int = 6) -> AgentResult:
    tools = tools or {}
    listed = "\n".join(f"- {n}: {d}" for n, (d, _) in tools.items())
    system = session.adapter.system_prompt(role) + "\n\n" + AGENT_FORMAT + (f"\nИнструменты:\n{listed}" if listed else "")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    steps, seen = [], []
    for _ in range(max_steps):
        text = await llm.generate(messages)
        try:
            data = extract_json(text)
        except FormError:
            messages += [{"role": "assistant", "content": text}, {"role": "user", "content": "Ответь в формате JSON."}]
            continue
        if "tool" in data and data["tool"] in tools:
            fn = tools[data["tool"]][1]
            try:
                out = fn(**(data.get("args") or {}))
                out = await out if hasattr(out, "__await__") else out
            except Exception as exc:  # noqa: BLE001
                out = f"ошибка инструмента: {type(exc).__name__}: {exc}"
            steps.append({"tool": data["tool"], "args": data.get("args"), "result": str(out)[:2000]})
            seen.append(f"{data['tool']}({json.dumps(data.get('args'), ensure_ascii=False)}) -> {str(out)[:1000]}")
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": f"Результат инструмента:\n{out}"}]
            continue
        fit = WorldAdapter.parse_world_fit(text)
        revised = await session.observe(fit, "Задача: " + task + ("\nДанные: " + "\n".join(seen) if seen else ""))
        return AgentResult(answer=str(data.get("answer") or text), fit=fit, steps=steps, revised=revised)
    return AgentResult(answer="(нет ответа за отведённые шаги)", fit=None, steps=steps)
