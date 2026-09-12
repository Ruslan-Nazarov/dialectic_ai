"""
Tests for Stage 4: Validator and claim verification.
"""
import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.core import AgentInput, MockLLM, DevelopmentLogger, Claim, Evidence
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.engine.validator import ClaimValidator

@pytest.mark.asyncio
async def test_claim_validator_missing_id():
    llm = MockLLM(responses=[])
    validator = ClaimValidator(llm=llm)

    claim = Claim(text="The Earth is round", evidence_ids=["bad-id"])
    evidence = [Evidence(id="123", source="test", content="The Earth is flat")]

    err = await validator.validate(claim, evidence)
    assert err is not None
    assert "unknown evidence_id" in err

@pytest.mark.asyncio
async def test_claim_validator_success():
    # LLM will return is_supported: true
    llm = MockLLM(responses=['{"is_supported": true, "reason": "Yes, all good"}'])
    validator = ClaimValidator(llm=llm)

    claim = Claim(text="The Earth is round", evidence_ids=["123"], requires_validation=True)
    evidence = [Evidence(id="123", source="test", content="Scientists have proven that the Earth is round.")]

    err = await validator.validate(claim, evidence)
    assert err is None

@pytest.mark.asyncio
async def test_claim_validator_fail():
    # LLM will return is_supported: false
    llm = MockLLM(responses=['{"is_supported": false, "reason": "The text contradicts the facts."}'])
    validator = ClaimValidator(llm=llm)

    claim = Claim(text="The Earth is flat", evidence_ids=["123"], requires_validation=True)
    evidence = [Evidence(id="123", source="test", content="Scientists have proven that the Earth is round.")]

    err = await validator.validate(claim, evidence)
    assert err is not None
    assert "The text contradicts the facts." in err

@pytest.mark.asyncio
async def test_engine_validation_loop():
    # Response 1: Agent gives incorrect ID
    mock_resp_1 = """{
      "decision": "I think...",
      "tool_calls": [],
      "claims": [{"text": "Test", "evidence_ids": ["nonexistent"]}],
      "response": "Response"
    }"""
    # Response 2: Agent corrects ID (or removes it)
    mock_resp_2 = """{
      "decision": "Oh yes, mistake.",
      "tool_calls": [],
      "claims": [{"text": "Test without ID", "evidence_ids": []}],
      "response": "Correct answer"
    }"""

    llm = MockLLM(responses=[mock_resp_1, mock_resp_2])
    agent = DialecticalAgent(goal="Test", llm=llm)
    
    # We do not pass the validator, but the engine will check existence ID itself!
    engine = DialecticalEngine(agent, max_iterations=5)
    
    inp = AgentInput(user_message="Hello")
    out = await engine.run(inp)
    
    assert out.is_final
    assert out.response == "Correct answer"
    
    # Check that there is a message from the user about the error in the history
    history = agent.get_messages()
    error_msgs = [m["content"] for m in history if "The following evidence IDs do not exist" in m["content"]]
    assert len(error_msgs) == 1
    assert "unknown evidence_id 'nonexistent'" in error_msgs[0]