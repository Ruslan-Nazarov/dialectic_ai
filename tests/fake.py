"""A scripted model that plays every block of the builder; tests set its behaviour."""
import asyncio
import re

from dialectic_world.llm.base import LLM


def block_of(prompt: str) -> str:
    m = re.search(r"\[БЛОК (\w+)\]", prompt)
    return m.group(1) if m else "AGENT"


def root_id(prompt: str) -> str:
    return re.search(r"Корень пучка[^\n]*\n\[(\w+)\]", prompt).group(1)


def developing_ids(prompt: str) -> list[str]:
    part = prompt.split("с их внутренними процессами:", 1)[1].split("Передача", 1)[0]
    return re.findall(r"^\[(\w+)\]", part, re.M)


def internal_ids(prompt: str) -> list[str]:
    return re.findall(r"внутренний: \[(\w+)\]", prompt)


class FakeModel(LLM):
    def __init__(self, opposite_at=1, sufficient_at=1, per_iteration=3, next_variant=2, retire_first=False,
                 p0_names=None, delay=0.0):
        super().__init__(model="fake")
        self.opposite_at, self.sufficient_at = opposite_at, sufficient_at
        self.per_iteration, self.next_variant, self.retire_first = per_iteration, next_variant, retire_first
        self.p0_names = list(p0_names or ["холодная еда"])
        self.delay = delay
        self.prompts: list[tuple[str, str]] = []
        self.in_flight = self.max_in_flight = 0
        self.overrides: dict[str, list] = {}     # block -> answers to give first, one per call
        self.p0_calls = 0

    def respond(self, block: str, prompt: str):
        if self.overrides.get(block):
            return self.overrides[block].pop(0)
        if block == "FindP0":
            self.p0_calls += 1
            name = self.p0_names[min(self.p0_calls - 1, len(self.p0_names) - 1)]
            return {"from": "горячая еда", "to": name, "statement": f"{name} как переход", "from_leap": "скачок", "carry": "c0"}
        if block == "NextDeveloping":
            got = int(re.search(r"уже получено новых: (\d+)", prompt).group(1))
            n = int(re.search(r"Итерация (\d+)", prompt).group(1))
            return {"from": f"x{n}.{got}", "to": f"y{n}.{got}", "statement": f"процесс {n}.{got}",
                    "derived_from": [root_id(prompt)], "more": got + 1 < self.per_iteration, "carry": f"c{n}.{got}"}
        if block == "Internals":
            prev = re.findall(r"^\[(I\w+)\]", prompt.split("на прошлой итерации:", 1)[1], re.M)
            return {"internals": [{"from": "a", "to": "b", "statement": f"внутр {k}", "links_prev": prev[:1]}
                                  for k in range(2)]}
        if block == "Compare":
            n = int(re.search(r"сравнение на итерации (\d+)", prompt).group(1))
            devs = developing_ids(prompt)
            p0_bundle = "противоположный процесс (п. 4.8" in prompt
            answer = {"vs_root": "v", "among": "a", "internals": "i", "opposite_id": None, "why_not_required": "",
                      "sufficient": False, "next_variant": self.next_variant, "retire": [], "promote": [],
                      "redo_internals": [], "next_changes": "меняем", "carry": f"cmp{n}"}
            if p0_bundle and self.opposite_at and n >= self.opposite_at:
                answer.update(opposite_id=devs[-1], why_not_required="для его развития P0 не нужен")
            if not p0_bundle and n >= self.sufficient_at:
                answer["sufficient"] = True
            if self.retire_first:
                answer["retire"] = devs[:1]
            return answer
        if block == "Contradiction":
            return {"from": "простейший и противоположный", "to": "их единство", "statement": "единство", "unity": "вместе дают", "carry": "cc"}
        if block == "Resolve":
            return {"from": "противоречие", "to": "разрешение", "statement": "подогрев холодной еды",
                    "kind": "replacement", "explanation": "вбирает оба"}
        raise AssertionError(f"unexpected block {block}")

    async def _complete(self, messages):
        prompt = "\n\n".join(m["content"] for m in messages)
        block = block_of(messages[0]["content"])
        self.prompts.append((block, prompt))
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            answer = self.respond(block, prompt)
        finally:
            self.in_flight -= 1
        import json
        text = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
        return text, len(prompt) // 4, len(text) // 4

    def calls(self, block: str) -> list[str]:
        return [p for b, p in self.prompts if b == block]
