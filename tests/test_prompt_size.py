"""Model prompts carry the current graph once, without bookkeeping that grows every move."""
import json

import pytest

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.llm import MockLLM
from dialectic_ai.core.runtime import AllowedMovesResolver
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.core.semantic_validator import LLMSemanticValidator
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.engine.prompt import build_v2_prompt
from dialectic_ai.observability.fixtures import generate_scenario_1
from dialectic_ai.observability.read_model import RuntimeReadModel
from dialectic_ai.tools import web_search


def executed_state():
    state = generate_scenario_1()
    return state, next(iter(state._goals.values()))


def test_prompt_snapshot_drops_timeline_and_roadmap_copies():
    state, _ = executed_state()
    snapshot = RuntimeReadModel(state).get_prompt_snapshot()
    assert "timeline" not in snapshot
    assert snapshot["roadmaps"] and all("snapshot" not in r for r in snapshot["roadmaps"])
    assert snapshot["observations"] and snapshot["practice"]


def test_runtime_json_only_on_request():
    state, goal = executed_state()
    moves = [m.value for m in AllowedMovesResolver().allowed_moves(state)]
    plain, _ = build_v2_prompt(state, goal, moves)
    assert "RUNTIME_JSON" not in plain
    full, _ = build_v2_prompt(state, goal, moves, include_runtime_json=True)
    data = json.loads(full.split("RUNTIME_JSON:\n", 1)[1].split("\nEND_RUNTIME_JSON", 1)[0])
    assert "timeline" not in data


@pytest.mark.asyncio
async def test_real_models_do_not_receive_runtime_json():
    class Capture(MockLLM):
        reads_runtime_json = False
        prompts = []

        async def generate(self, messages, tools=None):
            self.prompts.append(messages[-1]["content"])
            return "not a proposal"

    llm = Capture()
    engine = DialecticalEngine(DialecticalAgent("g", llm, [web_search()]), max_rejected_proposals=1)
    await engine.run(AgentInput(user_message="Example"))
    assert llm.prompts and not any("RUNTIME_JSON" in p for p in llm.prompts)


@pytest.mark.asyncio
async def test_judge_sees_graph_without_timeline():
    class Capture:
        prompt = ""

        async def generate(self, messages, tools=None):
            Capture.prompt = messages[-1]["content"]
            return '{"accepted": true, "reason": "ok", "issues": []}'

    state, goal = executed_state()
    proposal = next(e for e in state._trace if hasattr(e, "move_type"))
    await LLMSemanticValidator(Capture()).validate(proposal, state, goal)
    runtime = json.loads(Capture.prompt.split("\nDATA:\n", 1)[1])["runtime"]
    assert "timeline" not in runtime
    assert all("snapshot" not in r for r in runtime["roadmaps"])


def test_actor_sees_guidance_only_for_allowed_moves():
    state, goal = executed_state()
    prompt, _ = build_v2_prompt(state, goal, ["DEVELOP_PROCESS", "COMPLETE"])
    core = prompt.split("# Core Dialectical Moves", 1)[1].split("# Current Runtime State", 1)[0]
    assert "- DEVELOP_PROCESS:" in core and "- COMPLETE:" in core
    assert "WITHOUT ever" in core  # the clear-path note travels with COMPLETE
    for unavailable in ("PROPOSE_ACTION", "ASSESS_PRACTICE", "REPORT_CONTRADICTION", "PROPOSE_SIMPLEST"):
        assert f"- {unavailable}:" not in core
