import pytest

from dialectic_ai.core.runtime import Goal, MoveType, Proposal, RuntimeState
from dialectic_ai.core.semantic_validator import LLMSemanticValidator


@pytest.mark.asyncio
@pytest.mark.parametrize('response, accepted, reason', [
    ('```json\n{"accepted": true, "reason": "Grounded", "issues": []}\n```', True, 'Grounded'),
    ('```json\n{"accepted": false, "reason": "Unsupported"}\n```', False, 'Unsupported'),
    ('```\n{"accepted": true, "reason": "Grounded"}\n```', True, 'Grounded'),
    ('```json\n{"accepted": "true", "reason": "Grounded"}\n```', False, None),
    ('Comment\n```json\n{"accepted": true, "reason": "Grounded"}\n```', False, None),
    ('```json\n{"accepted": true, "reason": "Grounded"}\n```\n```json\n{}\n```', False, None),
    ('```json\n{"accepted": true, "reason": ""}\n```', False, None),
])
async def test_judge_accepts_only_complete_valid_verdict(response, accepted, reason):
    class Judge:
        async def generate(self, messages):
            return response

    proposal = Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={'content': 'Calculate'},
                        why_this_move_now='Begin', expected_goal_contribution='Compute')
    verdict = await LLMSemanticValidator(Judge()).validate(proposal, RuntimeState(), Goal(content='Calculate'))
    assert verdict.accepted is accepted
    if reason is not None:
        assert verdict.reason == reason
    else:
        assert verdict.reason.startswith('Validation error:')
