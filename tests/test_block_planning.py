"""Block planning: each dialectical block is its own narrow call, linked by the engine."""
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

    def __init__(self, opposite_numbers=(4,), needs_development=True):
        super().__init__()
        self.needs_development = needs_development
        self.block_prompts = {}
        self.opposite_numbers = list(opposite_numbers)

    async def generate(self, messages, tools=None):
        prompt = messages[-1]["content"]
        answers = [
            ("Name the GIVEN situation", {"simplest": "cold food", "needs_development": self.needs_development}),
            ("Unfold what this IS", {"determinations": ["tasteless", "unpleasant to eat", "can be harmful",
                                                        "food that was not heated"]}),
            ("points BEYOND", None),
            ("State their contradiction", {"contradiction": "the food is cold, and at the same time food can be heated",
                                           "how_each_develops": "cooling and heating"}),
            ("What results when the second acts on the first", {"acting": "heating acts on the cold food",
                                                                "result": "the cold food is heated",
                                                                "outcome": "replacement"}),
        ]
        for marker, answer in answers:
            if marker in prompt:
                self.block_prompts.setdefault(marker, []).append(prompt)
                if answer is None:
                    number = self.opposite_numbers.pop(0) if len(self.opposite_numbers) > 1 else self.opposite_numbers[0]
                    answer = {"number": number, "opposite": "heating of food", "how": "not heated -> can be heated"}
                return json.dumps(answer)
        return await super().generate(messages, tools)


def engine(llm, **kwargs):
    return DialecticalEngine(DialecticalAgent("Answer the user", llm, [web_search()]), semantic_validator=AcceptAll(),
                             block_planning=True, **kwargs)


@pytest.mark.asyncio
async def test_blocks_build_the_method_and_the_actor_finishes():
    llm = BlockLLM()
    e = engine(llm)
    result = await e.run(AgentInput(user_message=TASK))
    assert result.status == "completed", result.stop_reason
    state = e.state
    simplest = next(d for d in state.get_all_designations() if d.role == DesignationRole.SIMPLEST)
    opposite = next(d for d in state.get_all_designations() if d.role == DesignationRole.OPPOSITE)
    assert state.get_process(simplest.process_id).content == "cold food"
    assert opposite.caught_from == "food that was not heated"
    # The engine, not the model, links the opposite to the determination it was caught from.
    assert state.get_process(opposite.context_id).content == "food that was not heated"
    determinations = [r for r in state.get_all_development_relations() if r.source_process_id == simplest.process_id]
    assert len(determinations) == 4
    leap = next(iter(state._resolution_relations.values()))
    assert leap.opposite_acting_on_simplest == "heating acts on the cold food"
    assert state.get_process(leap.resolution_process_id).content == "the cold food is heated"


@pytest.mark.asyncio
async def test_only_the_simplest_block_sees_the_task():
    llm = BlockLLM()
    await engine(llm, stop_after_roadmap=True).run(AgentInput(user_message=TASK))
    assert TASK in llm.block_prompts["Name the GIVEN situation"][0]
    for marker in ("Unfold what this IS", "points BEYOND", "State their contradiction",
                   "What results when the second acts on the first"):
        assert all(TASK not in p and "What to do" not in p for p in llm.block_prompts[marker]), marker


@pytest.mark.asyncio
async def test_stop_after_roadmap_in_block_mode():
    e = engine(BlockLLM(), stop_after_roadmap=True)
    result = await e.run(AgentInput(user_message=TASK))
    assert result.status == "planned" and not e.state.get_all_actions()


@pytest.mark.asyncio
async def test_out_of_range_determination_is_retried_with_feedback():
    llm = BlockLLM(opposite_numbers=(9, 4))
    e = engine(llm, stop_after_roadmap=True)
    result = await e.run(AgentInput(user_message=TASK))
    assert result.status == "planned"
    retry = llm.block_prompts["points BEYOND"][1]
    assert "previous answer was rejected" in retry and "number must be 1..4" in retry


@pytest.mark.asyncio
async def test_no_determination_pointing_beyond_hands_over_to_the_clear_path(tmp_path):
    from dialectic_ai.core.logger import DevelopmentLogger
    trace = tmp_path / "t.jsonl"
    e = engine(BlockLLM(opposite_numbers=(0,)), logger=DevelopmentLogger(trace_path=str(trace)))
    await e.run(AgentInput(user_message="What is the capital of France?"))
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    assert next(ev for ev in events if ev["event_type"] == "block_planning")["outcome"] == "no_contradiction"
    by_blocks = [ev for ev in events if ev["event_type"] == "proposal_committed" and ev.get("origin") == "block"]
    assert not any(ev["proposal"]["move_type"] == "DESIGNATE_OPPOSITE" for ev in by_blocks)


@pytest.mark.asyncio
async def test_plain_fact_question_skips_the_blocks(tmp_path):
    from dialectic_ai.core.logger import DevelopmentLogger
    trace = tmp_path / "t.jsonl"
    llm = BlockLLM(needs_development=False)
    e = engine(llm, logger=DevelopmentLogger(trace_path=str(trace)))
    await e.run(AgentInput(user_message="What is the capital of France?"))
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    assert next(ev for ev in events if ev["event_type"] == "block_planning")["outcome"] == "no_contradiction"
    assert "Unfold what this IS" not in llm.block_prompts
    simplest = [d for d in e.state.get_all_designations() if d.role == DesignationRole.SIMPLEST]
    assert len(simplest) == 1
