"""A Domain fixes what the task already knows, so the model neither chooses it nor argues with the judge over it."""
import json

import pytest

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.domain import Domain
from dialectic_ai.core.llm import MockLLM
from dialectic_ai.core.runtime import DesignationRole, MoveType
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.core.semantic_validator import LLMSemanticValidator, SemanticValidationResult
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.tools import web_search

DOMAIN = Domain(
    name="business-card",
    semantics="OPPOSITE: a student team that starts work knowing only the card.",
    opposite="A student team starts work knowing only the card",
    unjudged_moves=frozenset({MoveType.BEGIN_EXECUTION}),
    judge_criteria={MoveType.DEVELOP_PROCESS: "Judge only whether this development concretizes its source."},
)


class RecordingJudge:
    def __init__(self):
        self.moves = []

    async def validate(self, proposal, state, goal):
        self.moves.append(proposal.move_type)
        return SemanticValidationResult(accepted=True, reason="Test judge")


def engine(judge=None, domain=DOMAIN):
    return DialecticalEngine(DialecticalAgent("Build a task card", MockLLM(), [web_search()]),
                             semantic_validator=judge or RecordingJudge(), domain=domain)


@pytest.mark.asyncio
async def test_engine_designates_the_domain_opposite_itself():
    judge = RecordingJudge()
    e = engine(judge)
    result = await e.run(AgentInput(user_message="Хотим чат-бота"))
    assert result.status == "completed", result.stop_reason
    opposites = [d for d in e.state.get_all_designations() if d.role == DesignationRole.OPPOSITE]
    assert len(opposites) == 1
    assert e.state.get_process(opposites[0].process_id).content == DOMAIN.opposite
    assert MoveType.DESIGNATE_OPPOSITE not in judge.moves


@pytest.mark.asyncio
async def test_actor_is_never_offered_the_fixed_opposite():
    class Capture(MockLLM):
        prompts = []

        async def generate(self, messages, tools=None):
            self.prompts.append(messages[-1]["content"])
            return await super().generate(messages, tools)

    llm = Capture()
    e = DialecticalEngine(DialecticalAgent("Build a task card", llm, [web_search()]),
                          semantic_validator=RecordingJudge(), domain=DOMAIN)
    await e.run(AgentInput(user_message="Хотим чат-бота"))
    offered = [p.split("Allowed Move Specifications:", 1)[1] for p in llm.prompts]
    assert not any("- DESIGNATE_OPPOSITE:" in o for o in offered)
    assert all(DOMAIN.semantics in p for p in llm.prompts)


@pytest.mark.asyncio
async def test_unjudged_moves_skip_the_judge():
    judge = RecordingJudge()
    await engine(judge).run(AgentInput(user_message="Хотим чат-бота"))
    assert MoveType.BEGIN_EXECUTION not in judge.moves
    assert MoveType.DEVELOP_PROCESS in judge.moves


@pytest.mark.asyncio
async def test_without_domain_the_model_designates_the_opposite():
    judge = RecordingJudge()
    e = engine(judge, domain=None)
    await e.run(AgentInput(user_message="Example"))
    assert MoveType.DESIGNATE_OPPOSITE in judge.moves
    assert MoveType.BEGIN_EXECUTION in judge.moves


@pytest.mark.asyncio
async def test_judge_sees_domain_instead_of_role():
    class Capture:
        data = []

        async def generate(self, messages, tools=None):
            Capture.data.append(json.loads(messages[-1]["content"].split("\nDATA:\n", 1)[1]))
            return '{"accepted": true, "reason": "ok", "issues": []}'

    e = DialecticalEngine(DialecticalAgent("Role demands: call commit_card before COMPLETE", MockLLM(), [web_search()]),
                          semantic_validator=LLMSemanticValidator(Capture()), domain=DOMAIN)
    await e.run(AgentInput(user_message="Хотим чат-бота"))
    assert Capture.data and all("role" not in d and d["domain"]["semantics"] == DOMAIN.semantics for d in Capture.data)
    develop = [d for d in Capture.data if d["proposal"]["move_type"] == "DEVELOP_PROCESS"]
    assert develop and all(d["domain_criterion"] == DOMAIN.judge_criteria[MoveType.DEVELOP_PROCESS] for d in develop)
