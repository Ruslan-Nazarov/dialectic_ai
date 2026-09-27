"""A scripted model that plays every block of the builder; tests set its behaviour."""
import asyncio
import json
import re

from dialectic_world.llm.base import LLM


def block_of(prompt: str) -> str:
    m = re.search(r"\[BLOCK (\w+)\]", prompt)
    return m.group(1) if m else "AGENT"


def iteration_number(prompt: str) -> int:
    return int(re.search(r"НОМЕР ТЕКУЩЕЙ ИТЕРАЦИИ:\n\n(\d+)", prompt).group(1))


def candidate_refs(prompt: str) -> list[str]:
    part = prompt.split("КАНДИДАТЫ НА ПРОТИВОПОЛОЖНОСТЬ:", 1)[1]
    return re.findall(r'"process_ref":\s*"([^"]+)"', part)


def confirmed_ref(prompt: str) -> str:
    part = prompt.split("ПОДТВЕРЖДЁННЫЕ ПРОТИВОПОЛОЖНЫЕ ПРОЦЕССЫ:", 1)[1]
    return re.search(r'"process_ref":\s*"([^"]+)"', part).group(1)


class FakeModel(LLM):
    def __init__(self, opposite_at=1, per_iteration=3, confirm_opposite=True, p0_names=None, delay=0.0):
        super().__init__(model="fake")
        self.opposite_at, self.per_iteration = opposite_at, per_iteration
        self.confirm_opposite = confirm_opposite
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
            return {"from": "горячая еда", "to": name, "statement": f"{name} как переход",
                    "practical_link": "связь", "why_initial": "почему исходный", "resolution_trace": "разрешение",
                    "development_potential": "потенциал", "verdict": "candidate"}

        if block == "BuildIteration":
            n = iteration_number(prompt)
            procs = []
            for i in range(self.per_iteration):
                pid = f"P{i + 1}"
                cur = [f"P{j + 1}" for j in range(i)]
                procs.append({
                    "id": pid, "process": f"процесс {n}.{i + 1}",
                    "basis": {"p0": True, "previous_iteration_as_whole": n > 1, "current_iteration_processes": cur},
                    "development_relation": "вытекает", "reveals": "раскрывает", "practical_significance": "значимо",
                    "relation_type": "функциональная",
                })
            return {"iteration": n, "p0": {"process": "p0"}, "based_on_iteration": None if n == 1 else n - 1,
                    "developing_processes": procs, "development_chain": ["P0"] + [p["id"] for p in procs],
                    "p0_revealed_content": "раскрытое содержание", "iteration_practical_integrity": "целостность",
                    "status": "ITERATION_BUILT", "failure_reason": None}

        if block == "CompareDevelopment":
            analyzed = [int(x) for x in re.findall(r"Итерация (\d+):", prompt)]
            n = max(analyzed) if analyzed else 1
            candidates = []
            if self.opposite_at and n >= self.opposite_at:
                candidates = [{"process_ref": f"I{n}.P{self.per_iteration}", "process": "кандидат",
                              "reason_for_check": "причина", "p0_dependency_change": "изменение",
                              "practical_basis": "основание", "not_yet_proven": True}]
            return {"p0": {"process": "p0"}, "iterations_analyzed": analyzed, "development_steps": [],
                    "relations_to_p0": [], "relations_between_processes": [], "iteration_patterns": [],
                    "cross_iteration_development": [], "opposition_candidates": candidates,
                    "overall_development_pattern": "паттерн", "status": "COMPARISON_COMPLETED", "failure_reason": None}

        if block == "CheckOpposition":
            refs = candidate_refs(prompt)
            checks, confirmed = [], []
            for ref in refs:
                result = "OPPOSITE" if self.confirm_opposite else "NOT_OPPOSITE"
                checks.append({
                    "process_ref": ref, "process": "кандидат", "origin_in_p0_development": "происхождение",
                    "shared_content": {"content": "общее", "practical_basis": "основание", "status": "ESTABLISHED"},
                    "difference": {"description": "отличие", "practical_basis": "основание", "status": "ESTABLISHED"},
                    "replacement": {"what_is_replaced": "что", "how": "как", "practical_basis": "основание",
                                    "p0_still_required": result != "OPPOSITE"},
                    "exclusion_of_p0": {"description": "исключение",
                                        "status": "ESTABLISHED" if result == "OPPOSITE" else "NOT_ESTABLISHED"},
                    "result": result, "reason": "причина", "uncertainty": None,
                })
                if result == "OPPOSITE":
                    confirmed.append({"process_ref": ref, "process": "кандидат", "shared_content_with_p0": "общее",
                                      "difference_from_p0": "отличие", "replacement_of_p0": "замещение",
                                      "exclusion_of_p0": "исключение"})
            return {"p0": {"process": "p0", "essential_content_for_check": "содержание"}, "candidate_checks": checks,
                    "confirmed_opposites": confirmed, "status": "OPPOSITION_CHECK_COMPLETED", "failure_reason": None}

        if block == "FormContradiction":
            ref = confirmed_ref(prompt)
            return {"p0": {"process": "p0", "essential_content": "содержание"},
                    "contradictions": [{
                        "opposite_ref": ref, "opposite_process": "противоположный",
                        "development_path": {"origin": "начало", "development": "развитие", "emergence_of_opposite": "возникновение"},
                        "unity": {"shared_content": "единство", "practical_basis": "основание"},
                        "difference": {"description": "отличие", "practical_basis": "основание"},
                        "exclusion": {"description": "исключение", "not_destruction": "не уничтожение"},
                        "contradiction": "единство P0 и противоположного", "practical_manifestation": "проявление",
                        "status": "CONTRADICTION_FORMED", "uncertainty": None,
                    }], "status": "CONTRADICTIONS_FORMED", "failure_reason": None}

        if block == "ResolveLeap":
            return {"contradiction": {"p0": "p0", "opposite": "opp", "essential_relation": "отношение"},
                    "leap": {"type": "REPLACEMENT", "process": "подогрев холодной еды",
                            "emerges_from_contradiction": "возникает", "p0_content_transformed": "p0 преобразован",
                            "opposite_content_transformed": "opp преобразован", "new_unity": "новое единство",
                            "replacement": {"replaces_p0": True, "replaces_opposite": True, "explanation": "объяснение"},
                            "practical_basis": "основание"},
                    "previous_p0_status": "CONFIRMED_P0",
                    "next_cycle": {"candidate_p0": "подогрев холодной еды", "basis": "RESULT_OF_LEAP"},
                    "status": "CONTRADICTION_RESOLVED"}

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
        text = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
        return text, len(prompt) // 4, len(text) // 4

    def calls(self, block: str) -> list[str]:
        return [p for b, p in self.prompts if b == block]
