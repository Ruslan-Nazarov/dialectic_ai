import pytest
import json
import uuid
from dialectic_ai.core.schema import ModelResult, ModelUsage, ModelToolCall, AgentInput, AgentOutput, Evidence
from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.engine.executor import DialecticalEngine
from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.engine.evidence_store import EvidenceStore

@dialectical(origin="t", contradiction="t", resolves="t", generates="t", own_contradictions="t", layer=1)
class MockEvidenceLLM(BaseLLM):
    def __init__(self, responses, native_tools=None):
        self.responses = responses
        self.call_count = 0
        self.native_tools = native_tools
        self.last_messages = []

    async def generate(self, messages, tools=None):
        return ""

    async def generate_result(self, messages, tools=None):
        self.call_count += 1
        self.last_messages = messages

        if self.native_tools and self.call_count <= len(self.native_tools):
            return ModelResult(
                tool_calls=[self.native_tools[self.call_count - 1]],
            )

        resp = self.responses[min(self.call_count - 1, len(self.responses) - 1)]
        if isinstance(resp, ModelResult):
            return resp
            
        return ModelResult(text=resp)

class DummyTool:
    name = "test_tool"
    description = "dummy"
    def parameters(self): return {}
    def to_prompt_description(self): return "dummy"
    async def execute(self, args):
        return Evidence(source="test_tool", content="ok")


@pytest.mark.asyncio
async def test_agent_output_default_status_is_backward_compatible():
    out = AgentOutput(response="test")
    assert out.status == "completed"


@pytest.mark.asyncio
async def test_evidence_id_created_by_runtime():
    ev = Evidence(source="test", content="content")
    assert ev.id is not None
    assert isinstance(ev.id, str)
    # LLM doesn't pass id, it's generated


@pytest.mark.asyncio
async def test_native_tool_result_creates_evidence():
    llm = MockEvidenceLLM(
        responses=['{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": []}]}'], 
        native_tools=[ModelToolCall(name="test_tool", arguments={"a": 1})]
    )
    agent = DialecticalAgent(goal="test", llm=llm, tools=[DummyTool()])
    engine = DialecticalEngine(agent=agent, max_iterations=2)
    
    out = await engine.run(AgentInput(user_message="test"))
    
    assert out.status == "completed"
    assert len(out.evidence) == 1
    assert out.evidence[0].source == "test_tool"
    assert out.evidence[0].id is not None


@pytest.mark.asyncio
async def test_existing_evidence_id_is_accepted():
    # We will need the LLM to output a claim with the actual evidence ID
    # Since ID is dynamic, we'll patch the tool to return a fixed ID for testing
    class FixedIdTool(DummyTool):
        async def execute(self, args):
            return Evidence(id="12345", source="test", content="ok")

    llm = MockEvidenceLLM(
        responses=['{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["12345"]}]}'], 
        native_tools=[ModelToolCall(name="test_tool", arguments={})]
    )
    agent = DialecticalAgent(goal="test", llm=llm, tools=[FixedIdTool()])
    engine = DialecticalEngine(agent=agent, max_iterations=2)
    
    out = await engine.run(AgentInput(user_message="test"))
    assert out.status == "completed"


@pytest.mark.asyncio
async def test_nonexistent_evidence_id_is_rejected():
    llm = MockEvidenceLLM([
        '{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["random-uuid"]}]}',
        '{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["still-random"]}]}'
    ])
    agent = DialecticalAgent(goal="test", llm=llm, tools=[])
    engine = DialecticalEngine(agent=agent, max_iterations=2)
    
    out = await engine.run(AgentInput(user_message="test"))
    
    # Fails validation twice -> validation_failed
    assert out.status == "validation_failed"


@pytest.mark.asyncio
async def test_validation_retry_happens_exactly_once():
    llm = MockEvidenceLLM([
        '{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["random-uuid"]}]}', # 1. Attempt
        '{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["random-uuid2"]}]}', # 2. Retry Attempt (fails)
        '{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["random-uuid3"]}]}'  # Should not be reached
    ])
    agent = DialecticalAgent(goal="test", llm=llm, tools=[])
    engine = DialecticalEngine(agent=agent, max_iterations=5) # Max iterations is high
    
    out = await engine.run(AgentInput(user_message="test"))
    
    # Engine should stop after 2 validation failures, ignoring max_iterations
    assert out.status == "validation_failed"
    assert llm.call_count == 2


@pytest.mark.asyncio
async def test_previous_run_evidence_is_not_valid_in_new_run():
    class FixedIdTool(DummyTool):
        async def execute(self, args):
            return Evidence(id="old-id", source="test", content="ok")

    llm1 = MockEvidenceLLM(
        responses=['{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["old-id"]}]}'], 
        native_tools=[ModelToolCall(name="test_tool", arguments={})]
    )
    agent = DialecticalAgent(goal="test", llm=llm1, tools=[FixedIdTool()])
    engine1 = DialecticalEngine(agent=agent, max_iterations=2)
    
    out1 = await engine1.run(AgentInput(user_message="test 1"))
    assert out1.status == "completed"

    # Now run again, LLM tries to use "old-id" without calling tool again
    llm2 = MockEvidenceLLM([
        '{"response": "done", "decision": "ok", "claims": [{"text": "y", "evidence_ids": ["old-id"]}]}',
        '{"response": "done", "decision": "ok", "claims": [{"text": "y", "evidence_ids": ["old-id"]}]}'
    ])
    agent.llm = llm2 # Swap LLM mock
    engine2 = DialecticalEngine(agent=agent, max_iterations=2)
    
    out2 = await engine2.run(AgentInput(user_message="test 2"))
    
    # validation_failed because old-id is not in current EvidenceStore
    assert out2.status == "validation_failed"


@pytest.mark.asyncio
async def test_validation_error_message_contains_available_ids():
    llm = MockEvidenceLLM([
        '{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["random"]}]}',
        '{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["random"]}]}'
    ])
    agent = DialecticalAgent(goal="test", llm=llm, tools=[])
    engine = DialecticalEngine(agent=agent, max_iterations=2)
    
    await engine.run(AgentInput(user_message="test"))
    
    last_user_msg = llm.last_messages[-1]["content"]
    assert "The following evidence IDs do not exist" in last_user_msg
    assert "Available evidence IDs in current run:" in last_user_msg


@pytest.mark.asyncio
async def test_evidence_validation_does_not_trigger_json_repair():
    llm = MockEvidenceLLM([
        '{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["random"]}]}',
        '{"response": "done", "decision": "ok", "claims": [{"text": "x", "evidence_ids": ["random"]}]}'
    ])
    agent = DialecticalAgent(goal="test", llm=llm, tools=[])
    engine = DialecticalEngine(agent=agent, max_iterations=2)
    
    out = await engine.run(AgentInput(user_message="test"))
    
    # Should be 2 calls, not 3 (if json repair triggered it would be 3 or 4)
    assert llm.call_count == 2
    assert out.status == "validation_failed"

