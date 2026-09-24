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
            ("Develop this process toward the target", {"chain": [
                {"process": "food that was not heated", "how_it_arises": "cold food is food left unheated"},
                {"process": "food that can be heated", "how_it_arises": "what was not heated can be"},
                {"process": "heating of food", "how_it_arises": "the possibility becomes the process"}]}),
            ("Develop this process in its own right", {"chain": [
                {"process": "choosing a heating method", "how_it_arises": "heating needs a means"},
                {"process": "bringing food to temperature", "how_it_arises": "the method is applied"}]}),
            ("Find the OPPOSITE", None),
            ("State the contradiction", {"contradiction": "cold food and heating in the unity of their development",
                                        "unity_of_development": "cooling and heating hold together"}),
            ("Find the process that resolves", {"resolution": "heating of the cold food",
                                                "how_resolves": "heating is applied to this cold food",
                                                "outcome": "replacement"}),
        ]
        for marker, answer in answers:
            if marker in prompt:
                self.block_prompts.setdefault(marker, []).append(prompt)
                if answer is None:
                    number = self.opposite_numbers.pop(0) if len(self.opposite_numbers) > 1 else self.opposite_numbers[0]
                    answer = {"number": number, "independence": "food can be heated whether or not this food is cold"}
                return json.dumps(answer)
        return await super().generate(messages, tools)


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
async def test_development_is_a_chain_not_a_list():
    e = engine(BlockLLM(), stop_after_roadmap=True)
    await e.run(AgentInput(user_message=TASK))
    state = e.state
    simplest = next(d for d in state.get_all_designations() if d.role == DesignationRole.SIMPLEST)
    relations = {r.source_process_id: r for r in state.get_all_development_relations()}
    source, texts = simplest.process_id, []
    while source in relations:
        emergent = relations[source].emergent_process_id
        texts.append(state.get_process(emergent).content)
        source = emergent
    assert texts == ["food that was not heated", "food that can be heated", "heating of food"]


@pytest.mark.asyncio
async def test_only_the_first_block_sees_the_task():
    llm = BlockLLM()
    await engine(llm, stop_after_roadmap=True).run(AgentInput(user_message=TASK))
    assert TASK in llm.block_prompts["State this task as a PROCESS"][0]
    for marker in ("Find the SIMPLEST process", "Develop this process toward the target", "Find the OPPOSITE",
                   "Develop this process in its own right", "State the contradiction", "Find the process that resolves"):
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
    retry = llm.block_prompts["Find the OPPOSITE"][1]
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
    assert "Develop this process toward the target" not in llm.block_prompts
