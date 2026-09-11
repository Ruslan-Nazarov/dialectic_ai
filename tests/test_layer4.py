"""
Test Layer 4: Multi-agentness.
"""
import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.core import AgentInput, MockLLM, DevelopmentLogger
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.multi import AgentRouter, AgentMessage

@pytest.fixture
def multi_agent_setup():
    tutor_agent = DialecticalAgent(
        goal="You are a Python tutor.",
        llm=MockLLM(responses=['{"thought":"explaining","knowledge_updates":[],"tool_calls":[],"response":"Great question!"}'])
    )
    coder_agent = DialecticalAgent(
        goal="You are a coding assistant.",
        llm=MockLLM(responses=['{"thought":"writing code","knowledge_updates":[],"tool_calls":[],"response":"Here is the solution"}'])
    )

    logger = DevelopmentLogger(log_path="multi_test_log.md", trace_path="multi_test_trace.jsonl")
    tutor_engine = DialecticalEngine(tutor_agent, logger=logger)
    coder_engine = DialecticalEngine(coder_agent, logger=logger)

    router = AgentRouter()
    router.register("tutor", tutor_agent, tutor_engine)
    router.register("coder", coder_agent, coder_engine)

    router.add_rule(lambda msg: "explain" in msg.lower() or "what is" in msg.lower(), "tutor")
    router.add_rule(lambda msg: "write code" in msg.lower() or "solve" in msg.lower(), "coder")
    
    return router

@pytest.mark.asyncio
async def test_router_tutor(multi_agent_setup):
    router = multi_agent_setup
    result = await router.route(AgentMessage(content="Explain to me what a variable is"))
    assert result.agent_name == "tutor"
    assert "Great question!" in result.response

@pytest.mark.asyncio
async def test_router_coder(multi_agent_setup):
    router = multi_agent_setup
    result = await router.route(AgentMessage(content="Write code for the sum from 1 to 10"))
    assert result.agent_name == "coder"
    assert "Here is the solution" in result.response

@pytest.mark.asyncio
async def test_router_fallback(multi_agent_setup):
    router = multi_agent_setup
    result = await router.route(AgentMessage(content="Hello!"))
    assert result.agent_name == "tutor" # fallback is the first one

def teardown_module(module):
    if os.path.exists("multi_test_log.md"):
        os.remove("multi_test_log.md")
    if os.path.exists("multi_test_trace.jsonl"):
        os.remove("multi_test_trace.jsonl")