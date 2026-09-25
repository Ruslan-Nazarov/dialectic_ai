"""The adapter (architecture 5.1): gives any agent the knowledge of the world it acts in, and reads back
the agent's mark of whether what it met fits that world. Framework-agnostic: a text to put into the
agent's system prompt or context, and a parser for the mark."""
import json
import re
from typing import Optional

from pydantic import BaseModel, Field

from dialectic_world.world.model import World


class WorldFit(BaseModel):
    fits: bool = True
    process_ids: list[str] = Field(default_factory=list)
    note: str = ""


WORLD_FIT_RULE = """В каждом ответе отметь, укладывается ли то, с чем ты столкнулся (данные задачи, результаты инструментов),
в картину мира выше: поле "world_fit": {"fits": true|false, "process_ids": ["id процессов мира, с которыми это связано"],
"note": "что именно не укладывается"}. Если ответ не в JSON — последней строкой: WORLD_FIT: {...}."""


class WorldAdapter:
    def __init__(self, world: World, max_chars: int = 4000):
        self.world, self.max_chars = world, max_chars

    def brief(self) -> str:
        """The core first (P0, opposite, contradiction, resolution), then the bundles' developing
        processes, their internal processes last -- so a size limit cuts the least important part."""
        w = self.world
        core = [f"Область: {w.domain} (мир, версия {w.version})"]
        if w.p0:
            core.append(f"Простейший процесс P0: {w.get(w.p0.process_id).line()}")
        if w.opposite:
            core.append(f"Противоположный процесс: {w.get(w.opposite.process_id).line()}\n"
                        f"  для его развития P0 не требуется: {w.opposite.why_not_required}")
        if w.contradiction:
            core.append(f"Противоречие: {w.get(w.contradiction.process_id).line()}\n  единство: {w.contradiction.unity}")
        if w.resolution:
            core.append(f"Разрешение ({w.resolution.kind}): {w.get(w.resolution.process_id).line()}\n"
                        f"  {w.resolution.explanation}")
        developing, internal = [], []
        for name, title in (("p0", "Развитие P0"), ("opposite", "Развитие противоположного"),
                            ("contradiction", "Развитие противоречия")):
            it = w.last_iteration(name)
            if not it:
                continue
            developing.append(f"{title}:")
            developing += [f"  {w.get(pid).line()}" for pid in it.developing]
            for pid in it.developing:
                internal += [f"  · (внутри {pid}) {w.get(i).line()}" for i in it.internal.get(pid, [])]
        text = "\n".join(core)
        for block in (developing, internal):
            for line in block:
                if len(text) + len(line) + 1 > self.max_chars:
                    return text
                text += "\n" + line
        return text

    def system_prompt(self, role: str = "") -> str:
        return (f"{role}\n\n" if role else "") + (
            "Ты действуешь в мире, картина которого построена заранее. Опирайся на неё, а не на догадки: "
            "что в этой области простейшее, как оно развивается, какое в нём противоречие и чем оно разрешается.\n\n"
            f"КАРТИНА МИРА\n{self.brief()}\n\n{WORLD_FIT_RULE}")

    @staticmethod
    def parse_world_fit(text: str) -> Optional[WorldFit]:
        m = re.search(r"WORLD_FIT:\s*(\{.*\})", text or "", re.S)
        candidates = [m.group(1)] if m else []
        j = re.search(r"\{.*\}", text or "", re.S)
        if j:
            candidates.append(j.group(0))
        for raw in candidates:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            fit = data.get("world_fit", data) if isinstance(data, dict) else None
            if isinstance(fit, dict) and "fits" in fit:
                return WorldFit.model_validate(fit)
        return None
