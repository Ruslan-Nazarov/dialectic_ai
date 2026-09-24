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
