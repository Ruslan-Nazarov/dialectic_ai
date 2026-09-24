"""Block planning: a rigid block structure, each block one element of the dialectical analysis."""
import json

import pytest

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.llm import MockLLM
from dialectic_ai.core.runtime import DesignationRole
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.core.semantic_validator import SemanticValidationResult
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.tools import web_search

TASK = "The food is cold; the canteen staff confirmed they can heat it. What to do?"


class AcceptAll:
    async def validate(self, proposal, state, goal):
        return SemanticValidationResult(accepted=True, reason="ok")


class BlockLLM(MockLLM):
    """Answers the block prompts; the regular actor moves come from the MockLLM autopilot."""

    def __init__(self, opposite_numbers=(3,), needs_development=True):
        super().__init__()
        self.needs_development = needs_development
        self.block_prompts = {}
        self.opposite_numbers = list(opposite_numbers)

    async def generate(self, messages, tools=None):
        prompt = messages[-1]["content"]
        answers = [
            ("State this task as a PROCESS", {"process": "food has gone cold and the staff can heat it",
                                             "needs_development": self.needs_development}),
            ("Find the SIMPLEST process", {"simplest": "cold food"}),
            ("Name the processes that develop out of this process", None),
            ("Develop this element of the process", None),
            ("Choose the OPPOSITE", None),
            ("State the contradiction", {"contradiction": "cold food and heating in the unity of their development",
                                        "unity_of_development": "cooling and heating hold together"}),
            ("Resolve this contradiction", {"resolution": "heating of the cold food",
                                                "how_resolves": "heating is applied to this cold food",
                                                "outcome": "replacement"}),
        ]
        for marker, answer in answers:
            if marker in prompt:
                self.block_prompts.setdefault(marker, []).append(prompt)
                if answer is None:
                    answer = self._dynamic(marker, prompt)
                return json.dumps(answer)
        return await super().generate(messages, tools)


    def _dynamic(self, marker, prompt):
        if marker == "Name the processes that develop out of this process":
            if "Process: cold food" in prompt:
                return {"elements": ["food that was not heated", "food losing its taste", "heating of food"]}
            return {"elements": ["choosing a heating method", "bringing food to temperature"]}
        if marker == "Develop this element of the process":
            element = prompt.split("Element: ", 1)[1].split("\n", 1)[0]
            return {"steps": [{"process": f"{element}, made concrete", "how_it_arises": "it grows definite"}]}
        number = self.opposite_numbers.pop(0) if len(self.opposite_numbers) > 1 else self.opposite_numbers[0]
        return {"number": number, "independence": "food can be heated whether or not this food is cold"}


def engine(llm, **kwargs):
    return DialecticalEngine(DialecticalAgent("Answer the user", llm, [web_search()]), semantic_validator=AcceptAll(),
                             block_planning=True, **kwargs)


def trace_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.asyncio
async def test_blocks_run_in_order_and_the_actor_finishes():
    e = engine(BlockLLM())
    result = await e.run(AgentInput(user_message=TASK))
    assert result.status == "completed", result.stop_reason
    state = e.state
    simplest = next(d for d in state.get_all_designations() if d.role == DesignationRole.SIMPLEST)
    opposite = next(d for d in state.get_all_designations() if d.role == DesignationRole.OPPOSITE)
    assert state.get_process(simplest.process_id).content == "cold food"
    assert state.get_process(opposite.process_id).content == "heating of food"
    assert opposite.independence == "food can be heated whether or not this food is cold"
    # The engine links the opposite to the developing process it was found among.
    assert state.get_process(opposite.context_id).content == "heating of food"
    leap = next(iter(state._resolution_relations.values()))
    assert state.get_process(leap.resolution_process_id).content == "heating of the cold food"
    assert leap.how_resolves == "heating is applied to this cold food"


@pytest.mark.asyncio
async def test_development_is_a_bundle_with_a_block_per_element():
    llm = BlockLLM()
    e = engine(llm, stop_after_roadmap=True)
    await e.run(AgentInput(user_message=TASK))
    state = e.state
    simplest = next(d for d in state.get_all_designations() if d.role == DesignationRole.SIMPLEST)
    elements = [state.get_process(r.emergent_process_id).content
                for r in state.get_all_development_relations() if r.source_process_id == simplest.process_id]
    assert elements == ["food that was not heated", "food losing its taste", "heating of food"]
    # Each element of both bundles was developed in its own block.
    assert len(llm.block_prompts["Develop this element of the process"]) == 3 + 2
    for element in elements:
        element_id = next(p.id for p in state.get_all_processes() if p.content == element)
        step = next(r for r in state.get_all_development_relations() if r.source_process_id == element_id)
        assert state.get_process(step.emergent_process_id).content == f"{element}, made concrete"


@pytest.mark.asyncio
async def test_contradiction_receives_the_simplest_and_the_opposites_bundle():
    llm = BlockLLM()
    e = engine(llm, stop_after_roadmap=True)
    await e.run(AgentInput(user_message=TASK))
    prompt = llm.block_prompts["State the contradiction"][0]
    assert "Simplest: cold food\n" in prompt and "Opposite: heating of food" in prompt
    for text in ("choosing a heating method", "bringing food to temperature, made concrete"):
        assert text in prompt, text
    # The simplest comes without its bundle.
    assert "food that was not heated" not in prompt and "food losing its taste" not in prompt
    contradiction = e.state.get_all_contradictions()[0]
    assert len(contradiction.simplest_dev_ref_ids) == 1 and len(contradiction.opposite_dev_ref_ids) == 4


@pytest.mark.asyncio
async def test_only_the_first_block_sees_the_task():
    llm = BlockLLM()
    await engine(llm, stop_after_roadmap=True).run(AgentInput(user_message=TASK))
    assert TASK in llm.block_prompts["State this task as a PROCESS"][0]
    for marker in ("Find the SIMPLEST process", "Name the processes that develop out of this process",
                   "Develop this element of the process", "Choose the OPPOSITE", "State the contradiction",
                   "Resolve this contradiction"):
        assert all(TASK not in p and "What to do" not in p for p in llm.block_prompts[marker]), marker


@pytest.mark.asyncio
async def test_stop_after_roadmap_in_block_mode():
    e = engine(BlockLLM(), stop_after_roadmap=True)
    result = await e.run(AgentInput(user_message=TASK))
    assert result.status == "planned" and not e.state.get_all_actions()


@pytest.mark.asyncio
async def test_out_of_range_opposite_is_retried_with_feedback():
    llm = BlockLLM(opposite_numbers=(9, 3))
    result = await engine(llm, stop_after_roadmap=True).run(AgentInput(user_message=TASK))
    assert result.status == "planned"
    retry = llm.block_prompts["Choose the OPPOSITE"][1]
    assert "previous answer was rejected" in retry and "number must be 1..3" in retry


@pytest.mark.asyncio
async def test_no_opposite_hands_over_to_the_clear_path(tmp_path):
    from dialectic_ai.core.logger import DevelopmentLogger
    trace = tmp_path / "t.jsonl"
    e = engine(BlockLLM(opposite_numbers=(0,)), logger=DevelopmentLogger(trace_path=str(trace)))
    await e.run(AgentInput(user_message=TASK))
    events = trace_events(trace)
    assert next(ev for ev in events if ev["event_type"] == "block_planning")["outcome"] == "no_contradiction"
    by_blocks = [ev for ev in events if ev["event_type"] == "proposal_committed" and ev.get("origin") == "block"]
    assert not any(ev["proposal"]["move_type"] == "DESIGNATE_OPPOSITE" for ev in by_blocks)


@pytest.mark.asyncio
async def test_plain_fact_question_skips_the_blocks(tmp_path):
    from dialectic_ai.core.logger import DevelopmentLogger
    trace = tmp_path / "t.jsonl"
    llm = BlockLLM(needs_development=False)
    await engine(llm, logger=DevelopmentLogger(trace_path=str(trace))).run(
        AgentInput(user_message="What is the capital of France?"))
    events = trace_events(trace)
    assert next(ev for ev in events if ev["event_type"] == "block_planning")["outcome"] == "no_contradiction"
    assert "Find the SIMPLEST process" not in llm.block_prompts
    assert "Name the processes that develop out of this process" not in llm.block_prompts
