"""Ablation mode: the engine lays out the dialectical plan and the model starts at practice."""
import json

import pytest

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.llm import MockLLM
from dialectic_ai.core.runtime import MoveType
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.core.semantic_validator import SemanticValidationResult
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.tools import web_search

PLANNING = {MoveType.PROPOSE_SIMPLEST, MoveType.ASSESS_SIMPLEST, MoveType.DEVELOP_PROCESS,
            MoveType.DESIGNATE_OPPOSITE, MoveType.ESTABLISH_CONTRADICTION, MoveType.PROPOSE_LEAP,
            MoveType.BEGIN_EXECUTION}


class RecordingJudge:
    def __init__(self):
        self.moves = []

    async def validate(self, proposal, state, goal):
        self.moves.append(proposal.move_type)
        return SemanticValidationResult(accepted=True, reason="ok")


class RecordingLLM(MockLLM):
    def __init__(self):
        super().__init__()
        self.proposed = []

    async def generate(self, messages, tools=None):
        text = await super().generate(messages, tools)
        self.proposed.append(json.loads(text).get("move_type"))
        return text


@pytest.mark.asyncio
async def test_model_starts_at_practice_and_judge_never_sees_planning():
    llm, judge = RecordingLLM(), RecordingJudge()
    engine = DialecticalEngine(DialecticalAgent("g", llm, [web_search()]), semantic_validator=judge, auto_planning=True)
    result = await engine.run(AgentInput(user_message="Example"))
    assert result.status == "completed", result.stop_reason
    assert llm.proposed[0] == "PROPOSE_ACTION"
    assert not PLANNING & {MoveType(m) for m in llm.proposed}
    assert not PLANNING & set(judge.moves)
    assert len(engine.state._roadmaps) == 1


@pytest.mark.asyncio
async def test_revision_gets_a_new_auto_planned_route_and_can_end_unresolved():
    class AlwaysContradicted(MockLLM):
        async def generate(self, messages, tools=None):
            prompt = messages[-1]["content"]
            state = json.loads(prompt.split("RUNTIME_JSON:\n")[1].split("\nEND_RUNTIME_JSON")[0])
            def move(name, payload):
                return json.dumps({"move_type": name, "payload": payload})
            contradicted = [p["observation_id"] for p in state["practice"] if p["expected_actual_relation"] == "contradicted"]
            if "REPORT_CONTRADICTION" in state["allowed_moves"]:
                return move("REPORT_CONTRADICTION", {"contested_source": "web_search", "contradicting_observation_ids": contradicted,
                            "supported_answer": None, "supporting_observation_ids": [], "final_response": "Source unreliable."})
            if state["allowed_moves"] == ["REVISE_WORLD"]:
                return move("REVISE_WORLD", {"observation_ids": contradicted, "reason": "Result contradicts expectation"})
            proposal = json.loads(await super().generate(messages, tools))
            if proposal.get("move_type") == "PROPOSE_ACTION":
                proposal["payload"]["args"] = {"query": f"attempt {len(state['roadmaps'])}"}
            if proposal.get("move_type") == "ASSESS_PRACTICE":
                proposal["payload"]["expected_actual_relation"] = "contradicted"
            return json.dumps(proposal)

    engine = DialecticalEngine(DialecticalAgent("g", AlwaysContradicted(), [web_search()]),
                               semantic_validator=RecordingJudge(), auto_planning=True, max_iterations=30)
    result = await engine.run(AgentInput(user_message="Example"))
    assert result.status == "unresolved", result.stop_reason
    first, second = engine.state._roadmaps.values()
    assert first.resolution_ids != second.resolution_ids
    assert second.revision_observation_ids


@pytest.mark.asyncio
async def test_auto_planning_keeps_a_domain_fixed_opposite():
    from dialectic_ai.core.domain import Domain
    from dialectic_ai.core.runtime import DesignationRole
    domain = Domain(name="d", semantics="s", opposite="A team that knows only the card")
    engine = DialecticalEngine(DialecticalAgent("g", MockLLM(), [web_search()]), semantic_validator=RecordingJudge(),
                               auto_planning=True, domain=domain)
    await engine.run(AgentInput(user_message="Example"))
    opposite = next(d for d in engine.state.get_all_designations() if d.role == DesignationRole.OPPOSITE)
    assert engine.state.get_process(opposite.process_id).content == domain.opposite
