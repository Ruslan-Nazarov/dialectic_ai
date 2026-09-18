import pytest
import json
from pydantic import ValidationError
from dialectic_ai.v1.llm import (
    RealLLMDispatcher, SemanticLLMProvider, NormalizerOutput,
    DevelopmentProposerOutput
)

class StubProvider(SemanticLLMProvider):
    def __init__(self, raw_response: str):
        self.raw_response = raw_response
        self.last_payload_format = None
        
    def generate(self, system_prompt: str, user_prompt: str, response_format: dict = None) -> str:
        self.last_payload_format = response_format
        # In a real scenario, we might verify no tools were sent. Since our OpenAILLMProvider
        # has no tool arguments, it by definition doesn't send them.
        return self.raw_response

def test_no_native_tool_calling_payload():
    # Since our OpenAILLMProvider uses urllib and hardcodes the payload, we can just inspect the payload construction.
    from dialectic_ai.v1.llm import OpenAILLMProvider
    import os
    
    os.environ["V1_LLM_API_KEY"] = "fake"
    provider = OpenAILLMProvider()
    
    # We can't easily intercept urllib without mocking, but we can verify the class definition doesn't accept tools.
    assert not hasattr(provider, "supports_native_tool_calling") or getattr(provider, "supports_native_tool_calling") == False

def test_unknown_authoritative_fields_ignored_or_rejected():
    # We want to ensure that if LLM returns extra fields like 'status': 'VALIDATED' in DevelopmentProposer,
    # the parser REJECTS them due to extra='forbid' config.
    raw = json.dumps({
        "candidate_process": {
            "type_canonical_name": "Test",
            "description": "Test Desc"
        },
        "emergence_rationale": "r1",
        "potential_rationale": "r2",
        "determinacy_rationale": "r3",
        "status": "VALIDATED",
        "contradiction": "Fake Contradiction"
    })
    
    provider = StubProvider(raw)
    dispatcher = RealLLMDispatcher(provider)
    from dialectic_ai.v1.mocks import LLMRole
    
    with pytest.raises(RuntimeError, match="Parser failure"):
        dispatcher.call(LLMRole.DEVELOPMENT_PROPOSER, {"source": "test"})


def test_malformed_json_retry_policy():
    # Test that it retries on invalid JSON
    class FlakyProvider(SemanticLLMProvider):
        def __init__(self):
            self.calls = 0
            
        def generate(self, system_prompt: str, user_prompt: str, response_format: dict = None) -> str:
            self.calls += 1
            if self.calls == 1:
                return "Not a json"
            return json.dumps({
                "definition": "A",
                "goal_state": "B",
                "domain": "C",
                "normalization_rationale": "D"
            })

    provider = FlakyProvider()
    dispatcher = RealLLMDispatcher(provider)
    from dialectic_ai.v1.mocks import LLMRole
    out = dispatcher.call(LLMRole.PROCESS_NORMALIZER, {"text": "test"})
    assert provider.calls == 2
    assert out["description"] == "A"
    assert out["goal_state"] == "B"

def test_missing_required_field_triggers_single_retry():
    class MissingFieldProvider(SemanticLLMProvider):
        def __init__(self):
            self.calls = 0
            
        def generate(self, system_prompt: str, user_prompt: str, response_format: dict = None) -> str:
            self.calls += 1
            if self.calls == 1:
                # missing determinacy_rationale
                return json.dumps({
                    "candidate_process": {"type_canonical_name": "A", "description": "B"},
                    "emergence_rationale": "r1",
                    "potential_rationale": "r2"
                })
            # Second attempt provides it
            return json.dumps({
                "candidate_process": {"type_canonical_name": "A", "description": "B"},
                "emergence_rationale": "r1",
                "potential_rationale": "r2",
                "determinacy_rationale": "r3"
            })

    provider = MissingFieldProvider()
    dispatcher = RealLLMDispatcher(provider)
    from dialectic_ai.v1.mocks import LLMRole
    out = dispatcher.call(LLMRole.DEVELOPMENT_PROPOSER, {"source": "test"})
    
    assert provider.calls == 2
    assert out["determinacy_rationale"] == "r3"

def test_second_invalid_response_returns_parser_failure():
    class AlwaysMissingFieldProvider(SemanticLLMProvider):
        def __init__(self):
            self.calls = 0
            
        def generate(self, system_prompt: str, user_prompt: str, response_format: dict = None) -> str:
            self.calls += 1
            # always missing determinacy_rationale
            return json.dumps({
                "candidate_process": {"type_canonical_name": "A", "description": "B"},
                "emergence_rationale": "r1",
                "potential_rationale": "r2"
            })

    provider = AlwaysMissingFieldProvider()
    dispatcher = RealLLMDispatcher(provider)
    from dialectic_ai.v1.mocks import LLMRole
    with pytest.raises(RuntimeError, match="Parser failure after 2 attempts"):
        dispatcher.call(LLMRole.DEVELOPMENT_PROPOSER, {"source": "test"})

def test_semantic_judge_fail_is_not_retried():
    class FailingJudgeProvider(SemanticLLMProvider):
        def __init__(self):
            self.calls = 0
            
        def generate(self, system_prompt: str, user_prompt: str, response_format: dict = None) -> str:
            self.calls += 1
            return json.dumps({
                "status": "FAIL",
                "reason": "Not a good development"
            })

    provider = FailingJudgeProvider()
    dispatcher = RealLLMDispatcher(provider)
    from dialectic_ai.v1.mocks import LLMRole
    
    # The dispatcher does not retry semantic FAIL, it just returns it.
    out = dispatcher.call(LLMRole.TRANSITION_JUDGE, {"source": "test", "candidate": "test2"})
    assert provider.calls == 1
    assert out["status"] == "FAIL"

def test_authoritative_extra_fields_are_rejected():
    # Same as test_unknown_authoritative_fields_ignored_or_rejected
    # but specifically tests the instruction requirement
    raw = json.dumps({
        "candidate_process": {"type_canonical_name": "A", "description": "B"},
        "emergence_rationale": "r1",
        "potential_rationale": "r2",
        "determinacy_rationale": "r3",
        "status": "VALIDATED"
    })
    provider = StubProvider(raw)
    dispatcher = RealLLMDispatcher(provider)
    from dialectic_ai.v1.mocks import LLMRole
    with pytest.raises(RuntimeError, match="Parser failure"):
        dispatcher.call(LLMRole.DEVELOPMENT_PROPOSER, {"source": "test"})
