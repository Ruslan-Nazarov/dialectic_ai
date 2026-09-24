"""Rejections the actor can act on, and judge outages that do not spend the rejection budget."""
import pytest
from jsonschema import Draft202012Validator

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.llm import MockLLM
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.core.semantic_validator import SemanticValidationResult
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.engine.executor import _schema_error
from dialectic_ai.tools import web_search


def test_schema_error_names_field_rule_and_hint():
    schema = {"type": "object", "properties": {"need": {"anyOf": [{"type": "null"}, {"type": "object", "properties": {
        "sources": {"type": "array", "minItems": 1, "description": "Set the field to null if unsupported."}}}]}}}
    message = _schema_error(list(Draft202012Validator(schema).iter_errors({"need": {"sources": []}})))
    assert message == "at need.sources: [] should be non-empty. Hint: Set the field to null if unsupported."


class FlakyJudge:
    """Returns no verdict the first `outages` times, then accepts everything."""

    def __init__(self, outages):
        self.outages = outages

    async def validate(self, proposal, state, goal):
        if self.outages:
            self.outages -= 1
            return SemanticValidationResult(accepted=False, reason="Validation error: empty reply", unavailable=True)
        return SemanticValidationResult(accepted=True, reason="ok")


def engine(judge, **limits):
    return DialecticalEngine(DialecticalAgent("g", MockLLM(), [web_search()]), semantic_validator=judge,
                             max_iterations=40, **limits)


@pytest.mark.asyncio
async def test_judge_outages_do_not_spend_rejection_budget():
    e = engine(FlakyJudge(outages=3), max_rejected_proposals=2, max_judge_outages=5)
    result = await e.run(AgentInput(user_message="Example"))
    assert result.status == "completed", result.stop_reason
    feedback = [ev.validation_error for ev in e.state._trace if getattr(ev, "event_type", "") == "proposal_rejected"]
    assert feedback and all("resubmit the same proposal unchanged" in f for f in feedback)
    assert not any("empty reply" in f for f in feedback)


@pytest.mark.asyncio
async def test_persistent_judge_outage_stops_honestly():
    result = await engine(FlakyJudge(outages=100), max_judge_outages=3).run(AgentInput(user_message="Example"))
    assert result.status == "error" and result.stop_reason == "judge_unavailable"


@pytest.mark.asyncio
async def test_fallback_skips_empty_replies():
    from dialectic_ai.core.llm import FallbackLLM

    class Empty(MockLLM):
        async def generate(self, messages, tools=None):
            return "  "

    llm = FallbackLLM([Empty(), MockLLM(['{"accepted": true}'])])
    assert await llm.generate([{"role": "user", "content": "x"}]) == '{"accepted": true}'


def test_tool_args_keep_ids_that_look_like_aliases():
    """A tool's own ids (answers A1, A2, ...) reach it verbatim even when an action is aliased A1;
    graph references outside args are still translated."""
    from dialectic_ai.engine.executor import _resolve_payload_aliases
    alias_to_uuid = {"A1": "action-uuid", "P3": "process-uuid"}
    payload = {"tool_name": "commit_card", "origin_ref": {"type": "Process", "id": "P3"},
               "args": {"data": {"value": "Excel", "sources": [{"source_id": "A1", "quote": "Excel"}]}}}
    resolved = _resolve_payload_aliases(payload, alias_to_uuid)
    assert resolved["args"]["data"]["sources"][0]["source_id"] == "A1"
    assert resolved["origin_ref"]["id"] == "process-uuid"
    assert _resolve_payload_aliases({"contradiction_id": "A1"}, alias_to_uuid) == {"contradiction_id": "action-uuid"}


@pytest.mark.asyncio
async def test_judge_outage_cause_stays_in_trace(tmp_path):
    import json
    from dialectic_ai.core.logger import DevelopmentLogger
    trace = tmp_path / "trace.jsonl"
    e = DialecticalEngine(DialecticalAgent("g", MockLLM(), [web_search()]), semantic_validator=FlakyJudge(outages=1),
                          logger=DevelopmentLogger(trace_path=str(trace)))
    await e.run(AgentInput(user_message="Example"))
    rejected = [json.loads(l) for l in trace.read_text(encoding="utf-8").splitlines()
                if json.loads(l)["event_type"] == "proposal_rejected"]
    assert rejected[0]["cause"] == "Validation error: empty reply"
    assert "empty reply" not in rejected[0]["reason"]


def test_explanatory_fields_are_optional():
    from dialectic_ai.core.proposal_schema import proposal_schema
    errors = list(Draft202012Validator(proposal_schema(["PROPOSE_SIMPLEST"])).iter_errors(
        {"move_type": "PROPOSE_SIMPLEST", "payload": {"content": "x"}}))
    assert not errors


@pytest.mark.asyncio
async def test_judge_waits_only_after_provider_failures(monkeypatch):
    import asyncio as aio
    from dialectic_ai.core.semantic_validator import LLMSemanticValidator
    from dialectic_ai.observability.fixtures import generate_scenario_1
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
    monkeypatch.setattr(aio, "sleep", fake_sleep)

    class RateLimited:
        calls = 0

        async def generate(self, messages, tools=None):
            RateLimited.calls += 1
            if RateLimited.calls < 3:
                raise RuntimeError("429 Too Many Requests")
            return '{"accepted": true, "reason": "ok"}'

    class Malformed:
        async def generate(self, messages, tools=None):
            return "not json"

    state = generate_scenario_1()
    goal = next(iter(state._goals.values()))
    proposal = next(e for e in state._trace if hasattr(e, "move_type"))
    assert (await LLMSemanticValidator(RateLimited()).validate(proposal, state, goal)).accepted
    assert slept == [2.0, 6.0]
    slept.clear()
    result = await LLMSemanticValidator(Malformed()).validate(proposal, state, goal)
    assert result.unavailable and slept == []


@pytest.mark.asyncio
async def test_identical_resubmission_in_same_state_is_refused_with_its_reason():
    import json
    invalid = json.dumps({"move_type": "PROPOSE_SIMPLEST", "payload": {"content": "   "},
                          "why_this_move_now": "x", "expected_goal_contribution": "y"})
    e = engine(FlakyJudge(0), max_rejected_proposals=3)
    e.agent.llm = MockLLM([invalid])
    result = await e.run(AgentInput(user_message="Example"))
    assert result.stop_reason == "max_rejected_proposals"
    reasons = [ev.validation_error for ev in e.state._trace if getattr(ev, "event_type", "") == "proposal_rejected"]
    assert not reasons[0].startswith("This exact proposal")
    assert all(r.startswith("This exact proposal was already rejected") for r in reasons[1:])
    assert reasons[0] in reasons[1]
