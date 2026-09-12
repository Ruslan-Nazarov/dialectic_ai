"""
Tests for Stage 6: Delegation (Multi-agent)
"""
import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.core import AgentInput, MockLLM, DevelopmentLogger, Claim, Evidence
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.reality.delegation import SubAgentTool

@pytest.mark.asyncio
async def test_delegation():
    # Mock response from sub-agent
    sub_mock_resp = """{
      "decision": "Solving the subtask.",
      "tool_calls": [],
      "claims": [],
      "response": "Subtask completed: answer 42."
    }"""
    
    sub_llm = MockLLM(responses=[sub_mock_resp])
    sub_agent = DialecticalAgent(goal="Solve subtasks.", llm=sub_llm)
    sub_engine = DialecticalEngine(sub_agent, max_iterations=1)
    
    # Mock response from supervisor
    super_mock_resp_1 = """{
      "decision": "Need to delegate.",
      "tool_calls": [{"name": "ask_worker", "args": {"task": "Calculate"}}],
      "claims": [],
      "response": ""
    }"""
    super_mock_resp_2 = """{
      "decision": "Received response from worker.",
      "tool_calls": [],
      "claims": [{"text": "Answer 42", "evidence_ids": [], "requires_validation": false}],
      "response": "Final answer: 42"
    }"""
    
    super_llm = MockLLM(responses=[super_mock_resp_1, super_mock_resp_2])
    
    sub_tool = SubAgentTool(name="ask_worker", description="Sub-agent", engine=sub_engine)
    
    super_agent = DialecticalAgent(goal="Main", llm=super_llm, tools=[sub_tool])
    super_engine = DialecticalEngine(super_agent, max_iterations=2)
    
    out = await super_engine.run(AgentInput(user_message="Solve everything."))
    
    assert out.is_final
    assert out.response == "Final answer: 42"
    assert len(out.evidence) == 1
    assert out.evidence[0].tool_name == "ask_worker"
    assert "Subtask completed: answer 42." in out.evidence[0].content