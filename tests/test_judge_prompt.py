"""The judge sees only the criterion of the move it judges, with the text unchanged."""
import json

import pytest

from dialectic_ai.core.semantic_validator import LLMSemanticValidator, _CRITERION_LABEL
from dialectic_ai.observability.fixtures import generate_scenario_1

ALL_LABELS = set(_CRITERION_LABEL.values())


class Capture:
    def __init__(self):
        self.prompts = []

    async def generate(self, messages, tools=None):
        self.prompts.append(messages[-1]["content"].split("\nDATA:\n")[0])
        return '{"accepted": true, "reason": "ok", "issues": []}'


@pytest.mark.asyncio
async def test_each_move_is_judged_by_its_own_criterion_only():
    state = generate_scenario_1()
    goal = next(iter(state._goals.values()))
    proposals = [e for e in state._trace if hasattr(e, "move_type")]
    assert len({p.move_type for p in proposals}) >= 8
    for proposal in proposals:
        capture = Capture()
        await LLMSemanticValidator(capture).validate(proposal, state, goal)
        prompt = capture.prompts[0]
        label = _CRITERION_LABEL[proposal.move_type.value]
        present = {l for l in ALL_LABELS if f"\n- {l}:" in prompt}
        assert present == {label}, (proposal.move_type.value, present)
        assert f"CRITERION FOR THIS MOVE ({proposal.move_type.value})" in prompt
        assert "SCOPE DISCIPLINE" in prompt and "Return exactly JSON" in prompt and "DOMAIN:" in prompt


@pytest.mark.asyncio
async def test_practice_criterion_keeps_its_full_text():
    state = generate_scenario_1()
    goal = next(iter(state._goals.values()))
    practice = next(e for e in state._trace if getattr(e, "move_type", None) and e.move_type.value == "ASSESS_PRACTICE")
    capture = Capture()
    await LLMSemanticValidator(capture).validate(practice, state, goal)
    assert "a fluent explanation does not substitute for the numbers actually matching" in capture.prompts[0]
